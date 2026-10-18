"""Revision-scoped business-rule registry. Suggestions never confer verification authority."""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import hashlib
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from faultline.repository_indexer import scoped


class InvariantReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action: Literal['approve','edit','reject','disable']
    description: str | None = Field(default=None,min_length=1,max_length=1500)
    reason: str = Field(min_length=3,max_length=500)


def discover_invariants(index: dict, documents: dict, declarations: list[dict]) -> list[dict]:
    repo,rev=index['repository'],index['revision'];rules=[]
    def candidate(description,category,source,functions=None,tests=None,declared=None):
        identifier=declared['id'] if declared else 'CAND-'+hashlib.sha256((description+source['path']+str(source['line'])).encode()).hexdigest()[:12].upper()
        return {'id':identifier,'key':scoped(repo,rev,'invariant',identifier),'description':description,'repository':repo,'revision':rev,
                'service':declared['service'] if declared else None,'related_functions':functions or [],'sources':[source],
                'category':category,'approval_status':'APPROVED' if declared else 'NEEDS_REVIEW','associated_tests':tests or [],
                'verification_history':[],'approved_by':declared.get('declared_by') if declared else None}
    available={s['name'] for f in index['files'] for s in f['symbols']}
    for d in declarations:
        functions=[name for name in d['functions'] if name in available]
        if functions:rules.append(candidate(d['description'],'DECLARED',d['source'],functions,d['tests'],d))
    for f in index['files']:
        if f['language']!='Python' or f.get('parse_error'):continue
        if f['is_test']:
            for assertion in f['assertions']:
                owner=next((s['name'] for s in sorted(f['symbols'],key=lambda s:s['end']-s['start']) if s['start']<=assertion['line']<=s['end']),None)
                rules.append(candidate('Existing test asserts: '+assertion['expression'],'TEST-BACKED',
                    {'path':f['path'],'line':assertion['line'],'revision':rev,'repository':repo,'origin':'test_assertion'},[],[f['path']+'#'+owner] if owner else []))
        for line_no,line in enumerate(f['source'].splitlines(),1):
            if line.strip().startswith('#') and 'invariant:' in line.lower():
                owner=next((s['name'] for s in sorted(f['symbols'],key=lambda s:s['end']-s['start']) if s['start']<=line_no<=s['end']),None)
                rules.append(candidate(line.split(':',1)[1].strip(),'INFERRED',{'path':f['path'],'line':line_no,'revision':rev,'repository':repo,'origin':'source_comment'},[owner] if owner else []))
    for item in documents['candidate_constraints']:rules.append(candidate(item['description'],'INFERRED',item['source']))
    return rules[:200]


def validated(rules: list[dict], repository: str, revision: str) -> list[dict]:
    return [r for r in rules if r['repository']==repository and r['revision']==revision and r['approval_status']=='APPROVED' and r.get('approved_by') and r['sources']]


def reviewed(rule: dict, update: InvariantReview, actor: str) -> dict:
    """Caller must authenticate maintainer authorization before entering this operation."""
    result={**rule,'sources':list(rule['sources'])}
    state={'approve':'APPROVED','edit':'NEEDS_REVIEW','reject':'REJECTED','disable':'DISABLED'}[update.action]
    if update.action=='edit':
        if not update.description:raise ValueError('An edited description is required')
        result['description']=update.description
    result['approval_status']=state;result['approved_by']=actor if state=='APPROVED' else None
    result['review_history']=[*rule.get('review_history',[]),{'action':update.action,'actor':actor,'reason':update.reason,'timestamp':datetime.now(timezone.utc).isoformat()}]
    return result
