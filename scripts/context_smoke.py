"""Live HTTP checks for source context and its effect on the real controlled investigation pipeline."""
import json
import os
from pathlib import Path
from urllib.request import Request,urlopen
BASE=os.getenv('FZ_BASE_URL','http://localhost:8000')


def request(path,payload=None):
    headers={'Content-Type':'application/json'}
    if os.getenv('FZ_API_KEY'):headers['Authorization']='Bearer '+os.environ['FZ_API_KEY']
    with urlopen(Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers),timeout=180) as response:return json.load(response)


def main():
    first=request('/api/v1/context/understanding')
    repeated=request('/api/v1/context/index',{'revision':'baseline'})
    assert first['revision']==repeated['revision'] and repeated['cached']
    assert first['counts']==repeated['counts']
    assert first['counts']['files']==1 and first['counts']['symbols']==5
    assert first['counts']['repository_test_files']==0 and first['counts']['external_runner_tests']==3
    rule=next(r for r in first['invariants'] if r['id']=='INV-PAY-01')
    assert rule['category']=='DECLARED' and rule['approval_status']=='APPROVED'
    assert any(s['path'].endswith('scenarios.py') and 'captures == 1' in s.get('assertions',[]) for s in rule['sources'])
    assert all(r['approval_status']!='APPROVED' for r in first['invariants'] if r['category']=='INFERRED')
    scenarios=[];trace=None
    for key,expected in [('payment','reproduced'),('inventory','reproduced'),('refund','reproduced'),('control','not_reproduced'),('uncovered','inconclusive')]:
        report=request('/api/v1/git/investigations',{'change':key,'mode':'deterministic'})
        assert report['verdict']==expected,report
        context=report['project_context']
        assert context['repository']=='trusted-commerce' and context['revision']==report['revisions']['candidate']
        assert context['metrics']['context_bytes']<=24000
        assert any(s['tool']=='retrieve_project_context' for s in report['steps'])
        assert not any(s['status']=='error' for s in report['steps'])
        if key=='uncovered':assert not context['validated_invariants'] and not report['cases']
        else:assert context['validated_invariants']
        scenarios.append({'change':key,'verdict':report['verdict'],'approved_rules':[r['id'] for r in context['validated_invariants']],
                          'metrics':context['metrics'],'indexing_metrics':context['indexing_metrics'],'index_cached':context['index_cached']})
        if key=='payment':trace={'report_id':report['id'],'context':context,'context_step':next(s for s in report['steps'] if s['tool']=='retrieve_project_context')}
        print(key,report['verdict'],context['status'],context['metrics'],flush=True)
    output={'counts':first['counts'],'revision':first['revision'],'cached_repeat':repeated['cached'],'invariant_provenance':rule,'scenarios':scenarios,'agent_context_trace':trace}
    Path('output').mkdir(exist_ok=True);Path('output/project-context-evaluation.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print('PASS: persistent idempotent context, provenance, approval boundaries, bounded retrieval and all five investigation outcomes')


if __name__=='__main__':main()
