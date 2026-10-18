"""Treat repository documentation as cited data, never as agent instructions."""
from __future__ import annotations
import re


def ingest_documentation(index: dict) -> dict:
    documents=[];candidates=[]
    for file in index['files']:
        if file['language']=='Python':continue
        path=file['path'];text=file['source'];lines=text.splitlines()
        api_spec=path.lower().endswith(('.json','.yml','.yaml')) and any(word in text[:4000].lower() for word in ('openapi','swagger','asyncapi'))
        document={'path':path,'sha256':file['sha256'],'revision':index['revision'],'repository':index['repository'],
                  'type':'api_specification' if api_spec else 'documentation_or_configuration','headings':[], 'source_excerpt':text[:1200]}
        for line_no,line in enumerate(lines,1):
            if line.startswith('#'):document['headings'].append({'line':line_no,'title':line.lstrip('# ').strip()[:180]})
            if re.search(r'\b(must|never|at most|exactly one|should|non.?negative)\b',line,re.I):
                candidates.append({'description':line.strip(' #-*')[:500],'source':{'path':path,'line':line_no,'revision':index['revision'],'repository':index['repository'],'origin':'repository_documentation'},'category':'INFERRED'})
        documents.append(document)
    return {'documents':documents,'candidate_constraints':candidates[:100],
            'gaps':[] if documents else ['No supported repository documentation was present at this revision.']}
