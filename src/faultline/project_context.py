"""Application integration for the single operator-registered trusted repository."""
from __future__ import annotations
import threading
import json
_service_lock=threading.Lock()
from faultline.context_graph_builder import ContextGraphBuilder, FalkorContextStore
from faultline.context_retriever import ContextRetriever
from faultline.git_demo import repo_path
from faultline.repository_indexer import RepositoryIndexer


class ProjectContextService:
    def __init__(self, legacy_repository):
        from faultline.config import get_settings
        self.store=FalkorContextStore(legacy_repository.db.select_graph(get_settings().graph_name+'_context'))
        self.store.write('RETURN 1')
        self.builder=ContextGraphBuilder(RepositoryIndexer(repo_path(),'trusted-commerce'),self.store)
        self.retriever=ContextRetriever(self.store)
    def index(self, revision='baseline',base_revision=None,promote=True):
        return self.builder.index(revision,base_revision,promote)
    def prepare_change(self, data):
        base,candidate=data['revisions']['baseline'],data['revisions']['candidate']
        self.index(base,promote=True);view=self.index(candidate,base,promote=False)
        symbols=[{'path':f['path'],'name':s['name'],'start':s['start']} for f in view['index']['files'] for s in f['symbols'] if s['name'] in data['modified_symbols'] and f['path'] in data['files']]
        package=self.retriever.retrieve('trusted-commerce',candidate,symbols,expected_revision=candidate)
        package['indexing_metrics']=view['metrics'];package['index_cached']=view['cached']
        for _ in range(4):package['metrics']['context_bytes']=len(json.dumps(package).encode())
        if package['metrics']['context_bytes']>24000:raise ValueError('Context package exceeds the supported model limit')
        return package
    def summary(self, revision='baseline'):
        view=self.index(revision);index=view['index'];rules=view['invariants']
        graph=self.store.graph_snapshot('trusted-commerce',view['revision'])
        safe_index={k:v for k,v in index.items() if k!='files'}
        files=[{k:v for k,v in f.items() if k!='source'} for f in index['files']]
        return {**view,'index':{**safe_index,'files':files},'nodes':graph['nodes'],'edges':graph['edges'],
                'counts':{'files':len(files),'symbols':sum(len(f['symbols']) for f in files),'services':sum(n['kind']=='Service' for n in graph['nodes']),
                          'repository_test_files':sum(f['is_test'] for f in files),'approved_invariants':sum(r['approval_status']=='APPROVED' for r in rules),
                          'candidates':sum(r['approval_status']=='NEEDS_REVIEW' for r in rules),'external_runner_tests':sum(n['kind']=='TestCase' and n.get('execution_allowed',False) for n in graph['nodes'])},
                'review_mode':'READ_ONLY_PREVIEW','boundary':'Only the trusted bundled local Git repository is exposed. Indexing never executes source code.'}


def service_for(repository):
    if not hasattr(repository,'db'):raise ValueError('Project context requires the persistent FalkorDB repository')
    with _service_lock:
        if not hasattr(repository,'_project_context_service'):repository._project_context_service=ProjectContextService(repository)
    return repository._project_context_service

