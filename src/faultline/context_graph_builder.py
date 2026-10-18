"""Persist scoped source facts in a separate FalkorDB context graph, alongside the legacy demo graph."""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
import re
from pathlib import Path
import threading
import time
from faultline.code_relationship_extractor import extract_relationships
from faultline.context_declarations import trusted_declarations
from faultline.documentation_ingestor import ingest_documentation
from faultline.graph_repository import GraphUnavailable
from faultline.invariant_registry import discover_invariants, reviewed
from faultline.repository_indexer import RepositoryIndexer, scoped, INDEX_SCHEMA_VERSION

NODE_TYPES={'Repository','Commit','File','Symbol','Service','BusinessInvariant','TestCase','DocumentationSource','Investigation','VerifiedFinding'}
EDGE_TYPES={'CONTAINS','DEFINES','IMPORTS','CALLS','MODIFIES','BELONGS_TO','DEPENDS_ON','ENFORCES','VALIDATES','DOCUMENTED_BY','SUPPORTED_BY','REFERENCES','INVESTIGATES','PRODUCED'}


def build_context_graph(index: dict, declarations: list[dict]) -> dict:
    repo,rev=index['repository'],index['revision'];nodes={};edges=[]
    docs=ingest_documentation(index);rules=discover_invariants(index,docs,declarations);relationships=extract_relationships(index)
    def nid(kind,name):return scoped(repo,rev,kind,name)
    def node(identifier,kind,label,source,**extra):
        nodes[identifier]={'id':identifier,'kind':kind,'label':label,'repository':repo,'revision':rev,'source':source,**extra};return identifier
    def edge(source,relation,target,provenance,classification='FACT'):
        edges.append({'source':source,'relation':relation,'target':target,'provenance':provenance,'classification':classification})
    root=node(nid('repository',repo),'Repository',repo,{'origin':'git_tree','revision':rev})
    commit=node(nid('commit',rev),'Commit',rev[:12],{'origin':'git_commit',**index['commit']})
    edge(root,'CONTAINS',commit,{'origin':'git_tree','revision':rev})
    for f in index['files']:
        source={'path':f['path'],'revision':rev,'repository':repo,'sha256':f['sha256'],'origin':'git_blob'}
        file_id=node(nid('file',f['path']),'File',f['path'],source)
        edge(commit,'CONTAINS',file_id,source)
        for symbol in f['symbols']:
            node(nid('symbol',f['path']+'#'+symbol['name']),'Symbol',symbol['name'],{**source,'line':symbol['start'],'end_line':symbol['end']},symbol_kind=symbol['kind'])
            if f['is_test'] and symbol['kind']!='ClassDef':
                test=node(nid('test',f['path']+'#'+symbol['name']),'TestCase',f['path']+'#'+symbol['name'],{**source,'line':symbol['start']},execution_allowed=False)
                edge(test,'REFERENCES',nid('symbol',f['path']+'#'+symbol['name']),{**source,'line':symbol['start']})
    for doc in docs['documents']:
        did=node(nid('doc',doc['path']),'DocumentationSource',doc['path'],{'path':doc['path'],'sha256':doc['sha256'],'revision':rev,'origin':'git_blob'},document_type=doc['type'])
        edge(nid('file',doc['path']),'DOCUMENTED_BY',did,nodes[did]['source'])
    edges.extend(relationships['edges'])
    declaration_by_id={d['id']:d for d in declarations}
    for rule in rules:
        if rule['category']=='TEST-BACKED':
            owners={nid('symbol',test) for test in rule['associated_tests']}
            targets={e['target'] for e in relationships['edges'] if e['relation']=='REFERENCES' and e['source'] in owners}
            rule['related_functions']=[nodes[target]['label'] for target in targets if target in nodes]

    for rule in rules:
        declaration=declaration_by_id.get(rule['id'])
        test_source=verification_reference(declaration) if declaration else None
        if test_source:rule['sources'].append(test_source)
        rid=node(rule['key'],'BusinessInvariant',rule['description'],rule['sources'][0],rule=rule)
        for f in index['files']:
            for symbol in f['symbols']:
                if symbol['name'] in rule['related_functions']:
                    edge(rid,'SUPPORTED_BY',nid('symbol',f['path']+'#'+symbol['name']),rule['sources'][0],'DECLARED' if rule['category']=='DECLARED' else 'HYPOTHESIS')
        for source in rule['sources']:
            did=nid('doc',source['path'])
            node(did,'DocumentationSource',source['path'],source)
            edge(rid,'SUPPORTED_BY',did,source,'DECLARED' if rule['category']=='DECLARED' else 'HYPOTHESIS')
        declaration=declaration_by_id.get(rule['id'])
        if declaration:
            service=node(nid('service',declaration['service']),'Service',declaration['service_name'],declaration['source'],external_id=declaration['service'])
            edge(service,'ENFORCES',rid,declaration['source'],'DECLARED')
            for f in index['files']:
                for symbol in f['symbols']:
                    if symbol['name'] in rule['related_functions']:edge(nid('symbol',f['path']+'#'+symbol['name']),'BELONGS_TO',service,declaration['source'],'DECLARED')
            for test_id in rule['associated_tests']:
                source=verification_reference(declaration)
                if source is None:continue
                tid=node(nid('test',test_id),'TestCase',test_id,source,external_id=test_id,execution_allowed=True)
                edge(tid,'VALIDATES',rid,source,'DECLARED')
    unique={}
    for e in edges:
        if e['source'] not in nodes or e['target'] not in nodes:continue
        key=(e['source'],e['relation'],e['target'],json.dumps(e['provenance'],sort_keys=True))
        e['id']=hashlib.sha256(repr(key).encode()).hexdigest();unique[key]=e
    gaps=[*index['gaps'],*docs['gaps']]
    if not any(f['is_test'] for f in index['files']):gaps.append('No test files exist inside this Git revision. Bundled runner tests are explicitly external declarations.')
    return {'repository':repo,'revision':rev,'nodes':list(nodes.values()),'edges':list(unique.values()),'invariants':rules,
            'documents':docs['documents'],'unknown_dependencies':relationships['unknown_dependencies'],'gaps':gaps}


def verification_reference(declaration: dict) -> dict | None:
    """Read the operator-owned runner test source; do not execute it or pretend it is in the sample Git tree."""
    import ast
    name=declaration.get('scenario_function')
    if not name:return None
    source=Path(__file__).with_name('fixtures').joinpath('scenarios.py').read_text(encoding='utf-8')
    function=next((n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name),None)
    if function is None:return None
    return {'path':'package:faultline/fixtures/scenarios.py','line':function.lineno,'end_line':function.end_lineno,
            'origin':'operator_approved_runner','sha256':hashlib.sha256(source.encode()).hexdigest(),
            'assertions':[ast.unparse(n.test) for n in ast.walk(function) if isinstance(n,ast.Assert)]}


class FalkorContextStore:
    def __init__(self, graph):self.graph=graph; self._timing=threading.local()
    @property
    def query_ms(self):return getattr(self._timing,'query_ms',0.0)
    @query_ms.setter
    def query_ms(self,value):self._timing.query_ms=value
    def read(self, query, **params):
        started=time.perf_counter()
        try:return self.graph.ro_query(query,params=params).result_set
        except Exception as exc:raise GraphUnavailable('Project context graph read unavailable') from exc
        finally:self.query_ms+=(time.perf_counter()-started)*1000
    def write(self, query, **params):
        try:return self.graph.query(query,params=params).result_set
        except Exception as exc:raise GraphUnavailable('Project context graph write unavailable') from exc
    def load(self, repository, revision):
        rows=self.read('MATCH (s:ContextSnapshot {repository:$repository, revision:$revision}) WHERE s.complete=true RETURN s.payload',repository=repository,revision=revision)
        return json.loads(rows[0][0]) if rows else None
    def current(self, repository):
        rows=self.read('MATCH (p:ContextProject {id:$repository}) RETURN p.revision',repository=repository)
        return rows[0][0] if rows else None
    def save(self, index, context, promote=True):
        started=time.perf_counter()
        groups=defaultdict(list)
        for n in context['nodes']:
            if n['kind'] not in NODE_TYPES:raise ValueError('Unsupported context node type')
            if n['kind']=='BusinessInvariant':
                old=self.read('MATCH (n:BusinessInvariant {id:$id}) RETURN n.payload',id=n['id'])
                if old:
                    previous_rule=json.loads(old[0][0])['rule']
                    if previous_rule.get('review_history'):
                        for field in ('description','approval_status','approved_by','review_history'):n['rule'][field]=previous_rule.get(field)
                    n['rule']['verification_history']=previous_rule.get('verification_history',[])
                n['label']=n['rule']['description']
            groups[n['kind']].append({'id':n['id'],'name':n['label'],'payload':json.dumps(n),'repository':n['repository'],'revision':n['revision']})
        for kind,rows in groups.items():
            # Only fixed allowlisted labels are interpolated; all repository values are parameters.
            self.write(f'UNWIND $rows AS row MERGE (n:{kind} {{id:row.id}}) SET n.payload=row.payload, n.name=row.name, n.repository=row.repository, n.revision=row.revision',rows=rows)
        edge_groups=defaultdict(list)
        for e in context['edges']:
            if e['relation'] not in EDGE_TYPES:raise ValueError('Unsupported relationship')
            edge_groups[e['relation']].append({**e,'provenance':json.dumps(e['provenance']),'repository':index['repository'],'revision':index['revision']})
        for relation,rows in edge_groups.items():
            self.write(f'UNWIND $rows AS row MATCH (a {{id:row.source}}), (b {{id:row.target}}) MERGE (a)-[r:{relation} {{id:row.id}}]->(b) SET r.provenance=row.provenance, r.repository=row.repository, r.revision=row.revision, r.classification=row.classification',rows=rows)
        index["metrics"]["graph_persistence_ms"]=round((time.perf_counter()-started)*1000,3)
        # Completion marker is written last. Partial imports are never consumed as completed context.
        self.write('MERGE (s:ContextSnapshot {repository:$repository, revision:$revision}) SET s.payload=$payload, s.complete=true',repository=index['repository'],revision=index['revision'],payload=json.dumps({'index':index,'context':context}))
        if promote:self.write('MERGE (p:ContextProject {id:$repository}) SET p.revision=$revision',repository=index['repository'],revision=index['revision'])
    def rules(self, repository, revision):
        rows=self.read('MATCH (n:BusinessInvariant {repository:$repository, revision:$revision}) RETURN n.payload',repository=repository,revision=revision)
        return [json.loads(row[0])['rule'] for row in rows]
    def graph_snapshot(self, repository, revision):
        nodes=self.read('MATCH (n) WHERE n.repository=$repository AND n.revision=$revision AND n.payload IS NOT NULL AND NOT n:ContextSnapshot RETURN n.payload',repository=repository,revision=revision)
        edges=self.read('MATCH (a)-[r]->(b) WHERE r.repository=$repository AND r.revision=$revision RETURN a.id, type(r), b.id, r.provenance, r.classification',repository=repository,revision=revision)
        return {'nodes':[json.loads(n[0]) for n in nodes], 'edges':[{'source':r[0],'relation':r[1],'target':r[2],'provenance':json.loads(r[3]),'classification':r[4]} for r in edges]}
    def review(self, repository, revision, invariant_id, update, actor):
        rules=self.rules(repository,revision);rule=next((r for r in rules if r['id']==invariant_id),None)
        if rule is None:raise ValueError('Invariant does not exist in this revision')
        result=reviewed(rule,update,actor)
        rows=self.read('MATCH (n:BusinessInvariant {id:$id}) RETURN n.payload',id=rule['key'])
        node=json.loads(rows[0][0]);node['rule']=result;node['label']=result['description']
        self.write('MATCH (n:BusinessInvariant {id:$id}) SET n.payload=$payload, n.name=$name',id=rule['key'],payload=json.dumps(node),name=result['description'])
        return result
    def connected(self, repository, revision, symbols):
        started=time.perf_counter()
        rows=self.read("""MATCH (s:Symbol)-[:CALLS*0..2]->(f:Symbol)-[:BELONGS_TO]->(svc:Service)-[:ENFORCES]->(rule:BusinessInvariant)
          WHERE s.id IN $symbols AND s.repository=$repository AND s.revision=$revision
          AND svc.repository=$repository AND svc.revision=$revision AND rule.repository=$repository AND rule.revision=$revision
          RETURN DISTINCT svc.payload, rule.payload, f.payload LIMIT 40""",symbols=symbols,repository=repository,revision=revision)
        return [{'service':json.loads(r[0]),'invariant':json.loads(r[1]),'function':json.loads(r[2])} for r in rows]
    def promote(self, repository, revision):
        self.write('MERGE (p:ContextProject {id:$repository}) SET p.revision=$revision',repository=repository,revision=revision)
    def record(self, repository, revision, report):
        identifier=scoped(repository,revision,'investigation',report.id)
        self.write('MERGE (i:Investigation {id:$id}) SET i.repository=$repository, i.revision=$revision, i.report_id=$report_id, i.verdict=$verdict, i.payload=$payload',id=identifier,repository=repository,revision=revision,report_id=report.id,verdict=report.verdict.value,payload=json.dumps({'id':identifier,'kind':'Investigation','label':report.id,'repository':repository,'revision':revision,'report_id':report.id,'verdict':report.verdict.value,'source':{'origin':'actual_execution','revision':revision}}))
        for c in report.cases:
            if c.baseline.outcome!='pass' or c.candidate.outcome!='fail':continue
            fid=scoped(repository,revision,'finding',report.id+':'+c.testcase_id)
            payload={'id':fid,'kind':'VerifiedFinding','label':c.candidate.observed,'repository':repository,'revision':revision,'testcase':c.testcase_id,'invariant':c.invariant_id,'source':{'origin':'actual_execution','report_id':report.id},'baseline':c.baseline.model_dump(),'candidate':c.candidate.model_dump()}
            self.write('MERGE (f:VerifiedFinding {id:$id}) SET f.repository=$repository, f.revision=$revision, f.payload=$payload WITH f MATCH (i:Investigation {id:$investigation}) MERGE (i)-[r:PRODUCED]->(f) SET r.repository=$repository, r.revision=$revision, r.provenance=$provenance, r.classification="EXECUTED_EVIDENCE"',id=fid,repository=repository,revision=revision,payload=json.dumps(payload),investigation=identifier,provenance=json.dumps({'origin':'actual_execution','report_id':report.id}))
        for c in report.cases:
            rule_key=scoped(repository,revision,'invariant',c.invariant_id)
            rows=self.read('MATCH (n:BusinessInvariant {id:$id}) RETURN n.payload',id=rule_key)
            if not rows:continue
            node=json.loads(rows[0][0]);rule=node['rule']
            rule['verification_history']=[h for h in rule.get('verification_history',[]) if h['report_id']!=report.id][-19:]
            rule['verification_history'].append({'report_id':report.id,'testcase_id':c.testcase_id,'baseline':c.baseline.outcome,'candidate':c.candidate.outcome,'verdict':c.verdict.value,'revision':revision})
            self.write('MATCH (n:BusinessInvariant {id:$id}) SET n.payload=$payload',id=rule_key,payload=json.dumps(node))
    def history(self, repository, revision, limit=5):
        rows=self.read('MATCH (i:Investigation {repository:$repository, revision:$revision}) RETURN i.report_id, i.verdict ORDER BY i.report_id LIMIT 5',repository=repository,revision=revision)
        return [{'report_id':r[0],'verdict':r[1],'classification':'HISTORICAL_EXECUTED_EVIDENCE'} for r in rows]


class ContextGraphBuilder:
    def __init__(self, indexer: RepositoryIndexer, store, declarations=None):
        self.indexer,self.store=indexer,store
        self.declarations=trusted_declarations(indexer.repository) if declarations is None else declarations
        self.lock=threading.RLock()
    def index(self, revision: str, base_revision: str | None=None, promote=True):
        with self.lock:
            sha=self.indexer.resolve(revision);existing=self.store.load(self.indexer.repository,sha)
            if existing and existing['index'].get('schema_version')==INDEX_SCHEMA_VERSION:
                if promote:self.store.promote(self.indexer.repository,sha)
                return self.view(existing,cached=True)
            previous=None
            parent=base_revision or self.store.current(self.indexer.repository)
            if parent:
                parent_sha=parent if re.fullmatch(r'[0-9a-f]{40,64}',parent) else self.indexer.resolve(parent)
                saved=self.store.load(self.indexer.repository,parent_sha)
                previous=saved['index'] if saved and saved['index'].get('schema_version')==INDEX_SCHEMA_VERSION else None
            index=self.indexer.index(sha,previous);context=build_context_graph(index,self.declarations)
            self.store.save(index,context,promote=promote)
            return self.view({'index':index,'context':context},cached=False)
    def view(self, saved, cached=False):
        index=saved['index'];context={**saved['context']};context['invariants']=self.store.rules(index['repository'],index['revision'])
        return {**context,'index':index,'cached':cached,'current_revision':self.store.current(index['repository']),
                'historical':self.store.current(index['repository'])!=index['revision'],'metrics':index['metrics']}


if __name__ == '__main__':
    import argparse
    from falkordb import FalkorDB
    from faultline.config import get_settings
    parser=argparse.ArgumentParser(description='Operator-only source indexing; never execute repository code')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--repository',required=True)
    parser.add_argument('--revision',default='HEAD')
    parser.add_argument('--base-revision')
    args=parser.parse_args()
    settings=get_settings()
    client=FalkorDB(host=settings.graph_host,port=settings.graph_port,password=settings.graph_password)
    store=FalkorContextStore(client.select_graph(settings.graph_name+'_context'))
    store.write('RETURN 1')
    builder=ContextGraphBuilder(RepositoryIndexer(args.root,args.repository),store,declarations=[])
    result=builder.index(args.revision,args.base_revision)
    print(json.dumps({'repository':result['repository'],'revision':result['revision'],'metrics':result['metrics'],
                      'nodes':len(result['nodes']),'relationships':len(result['edges']),
                      'invariants':[{k:v for k,v in r.items() if k in {'id','description','category','approval_status','sources'}} for r in result['invariants']],
                      'execution':'Indexing only; no repository source code was executed. Operator CLI does not import demo declarations.'},indent=2))
