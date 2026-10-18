"""Operator-only ingestion demonstration on a fresh, independently named Python Git repository.

This script commits test sources but NEVER executes them. It writes context to FalkorDB.
"""
import json
from pathlib import Path
import tempfile
from falkordb import FalkorDB
from faultline.config import get_settings
from faultline.git_demo import git
from faultline.repository_indexer import RepositoryIndexer
from faultline.context_graph_builder import ContextGraphBuilder,FalkorContextStore
from faultline.context_retriever import ContextRetriever
from faultline.invariant_registry import InvariantReview


def main():
    settings=get_settings();client=FalkorDB(host=settings.graph_host,port=settings.graph_port,password=settings.graph_password)
    store=FalkorContextStore(client.select_graph(settings.graph_name+'_context'));store.write('RETURN 1')
    with tempfile.TemporaryDirectory(prefix='fz-source-index-') as folder:
        root=Path(folder);git(root,'init');git(root,'config','user.name','FAULTLINE context demonstration');git(root,'config','user.email','context@example.invalid')
        (root/'orders.py').write_text('def bounded_total(subtotal, discount):\n    return max(0, subtotal - discount)\n')
        (root/'test_orders.py').write_text('from orders import bounded_total\n\ndef test_floor():\n    assert bounded_total(10, 20) == 0\n')
        (root/'README.md').write_text('# Ordering example\nOrder totals should never be negative.\n')
        git(root,'add','.');git(root,'commit','-m','Initial independent Python example')
        first_sha=git(root,'rev-parse','HEAD');indexer=RepositoryIndexer(root,'independent-python-example');builder=ContextGraphBuilder(indexer,store,declarations=[])
        first=builder.index(first_sha)
        (root/'orders.py').write_text('def bounded_total(subtotal, discount):\n    return max(subtotal - discount, 0)\n')
        git(root,'add','orders.py');git(root,'commit','-m','Equivalent implementation, independent revision')
        second_sha=git(root,'rev-parse','HEAD');second=builder.index(second_sha,first_sha);again=builder.index(second_sha)
        changed=second['index']['modified_symbols'];package=ContextRetriever(store).retrieve('independent-python-example',second_sha,changed,expected_revision=second_sha)
        assert second['metrics']['parsed_files']==1 and second['metrics']['reused_files']==2
        assert again['cached'] and not package['validated_invariants']
        candidate=next(r for r in store.rules('independent-python-example',second_sha) if r['category']=='TEST-BACKED')
        lifecycle=[]
        for action in ['approve','edit','reject','disable']:
            update=InvariantReview(action=action,reason='Operator-only demonstration of persistent review',description='A maintainer-reviewed example constraint' if action=='edit' else None)
            reviewed=store.review('independent-python-example',second_sha,candidate['id'],update,'operator-context-demonstration')
            lifecycle.append({'action':action,'persisted_status':reviewed['approval_status']})
        assert [r['persisted_status'] for r in lifecycle]==['APPROVED','NEEDS_REVIEW','REJECTED','DISABLED']
        query='MATCH (a)-[r]->(b) WHERE a.repository=$repository AND a.revision=$revision RETURN a.name, type(r), b.name ORDER BY a.name, b.name LIMIT 12'
        rows=store.read(query,repository='independent-python-example',revision=second_sha)
        return {'repository':'independent-python-example','first_revision':first_sha,'revision':second_sha,
                'index_metrics':second['metrics'],'idempotent_repeat_cached':again['cached'],
                'context':package,'review_lifecycle':lifecycle,'query':query,'query_output':rows,
                'source_execution':'No source or test code executed; indexing and Git object reads only.'}


if __name__=='__main__':print(json.dumps(main(),indent=2))
