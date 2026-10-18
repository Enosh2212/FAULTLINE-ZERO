"""Bounded, non-executing indexing of operator-selected local Git snapshots."""
from __future__ import annotations
import ast
import hashlib
import os
from pathlib import Path
import re
import subprocess
import time

INDEX_SCHEMA_VERSION = 2
MAX_FILES = 500
MAX_BLOB = 512_000
MAX_TOTAL = 8_000_000


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def scoped(repository: str, revision: str, kind: str, name: str) -> str:
    return f"{repository}@{revision}:{kind}:{name}"


class RepositoryIndexer:
    """Construction is an operator trust decision; HTTP accepts neither paths nor arbitrary refs."""
    def __init__(self, root: Path, repository: str):
        self.root = Path(root).resolve()
        if not (self.root / '.git').exists() or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', repository):
            raise ValueError('A local Git repository and a bounded repository identifier are required')
        self.repository = repository

    def git(self, *args: str) -> str:
        env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0')
        return subprocess.run(['git','-c','core.hooksPath='+os.devnull,'-C',str(self.root),*args],
                              capture_output=True, check=True, timeout=10, env=env).stdout.decode('utf-8')

    def resolve(self, ref: str) -> str:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]{0,159}', ref) or '..' in ref:
            raise ValueError('Unsupported revision reference')
        sha = self.git('rev-parse','--verify',ref+'^{commit}').strip()
        if not re.fullmatch(r'[0-9a-f]{40,64}', sha):
            raise ValueError('Expected immutable commit identifier')
        return sha

    def blob(self, sha: str, path: str) -> str:
        if path.startswith('/') or '..' in Path(path).parts or '\x00' in path:
            raise ValueError('Invalid repository-relative path')
        spec = sha+':'+path
        if int(self.git('cat-file','-s',spec)) > MAX_BLOB:
            raise ValueError('Blob exceeds indexing limit')
        return self.git('show',spec)

    def index(self, revision: str, previous: dict | None = None) -> dict:
        started = time.perf_counter()
        sha = self.resolve(revision)
        rows = self.git('ls-tree','-r','-z',sha).split('\x00')
        entries=[]; gaps=[]
        for row in rows:
            if not row: continue
            meta, path = row.split('\t',1)
            mode, kind, blob = meta.split()
            if mode not in {'100644','100755'} or kind != 'blob':
                gaps.append({'path':path,'reason':'Symlink/submodule or non-regular object skipped'});continue
            entries.append((path,blob))
        if len(entries)>MAX_FILES: raise ValueError('Repository exceeds the supported 500-file bound')
        files=[];total=0;reused=0
        old={f['path']:f for f in (previous or {}).get('files',[])} if previous and previous.get('repository')==self.repository else {}
        for path,blob in entries:
            suffix=Path(path).suffix.lower()
            supported=suffix in {'.py','.md','.markdown','.json','.yaml','.yml','.toml','.ini','.cfg'} or Path(path).name.lower().startswith('readme')
            if not supported: continue
            try:
                source=self.blob(sha,path);total+=len(source.encode())
                if total>MAX_TOTAL: raise ValueError('Repository text exceeds 8MB bound')
            except (ValueError,UnicodeError) as exc:
                gaps.append({'path':path,'reason':str(exc)});continue
            is_test=Path(path).name.startswith('test_') or Path(path).name.endswith('_test.py') or 'tests' in Path(path).parts
            info={'path':path,'blob':blob,'language':'Python' if suffix=='.py' else 'Documentation/configuration',
                  'source':source,'sha256':digest(source),'is_test':is_test,'symbols':[],'imports':[],'assertions':[]}
            if path in old and old[path]['blob']==blob:
                for key in ('symbols','imports','assertions','parse_error'): 
                    if key in old[path]: info[key]=old[path][key]
                reused+=1
            elif suffix=='.py':
                try: info.update(parse_python(source))
                except (SyntaxError,RecursionError) as exc:
                    info['parse_error']=str(exc)[:200];gaps.append({'path':path,'reason':'Python AST parse failed'})
            files.append(info)
        modified=[]
        for f in files:
            baseline={s['name']:s for s in old.get(f['path'],{}).get('symbols',[])}
            for symbol in f['symbols']:
                if symbol['name'] not in baseline or baseline[symbol['name']]['fingerprint']!=symbol['fingerprint']:
                    modified.append({'path':f['path'],'name':symbol['name'],'start':symbol['start'],'end':symbol['end']})
        deleted=[p for p in old if p not in {f['path'] for f in files}]
        removed_symbols=[{'path':f['path'],'name':s['name']} for f in old.values() for s in f['symbols']
                         if not any(n['path']==f['path'] and any(t['name']==s['name'] for t in n['symbols']) for n in files)]
        commit=self.git('show','-s','--format=%H%n%P%n%aI%n%s',sha).splitlines()
        return {'schema_version':INDEX_SCHEMA_VERSION,'repository':self.repository,'revision':sha,'commit':{'sha':sha,'parents':commit[1].split(),'authored_at':commit[2],'subject':commit[3]},
                'structure':[p for p,_ in entries],'languages':sorted({f['language'] for f in files}),
                'files':files,'modified_symbols':modified,'removed_symbols':removed_symbols,'deleted_files':deleted,
                'gaps':gaps,'metrics':{'indexing_ms':round((time.perf_counter()-started)*1000,3),'parsed_files':len(files)-reused,'reused_files':reused,'indexed_files':len(files)}}


def parse_python(source: str) -> dict:
    tree=ast.parse(source);symbols=[];imports=[];assertions=[]
    def walk(body, prefix='',parent=None):
        for node in body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                name=prefix+node.name
                symbols.append({'name':name,'kind':type(node).__name__,'start':node.lineno,'end':node.end_lineno,
                                'parent':parent,'fingerprint':digest(ast.dump(node,include_attributes=False))})
                walk(node.body,name+'.',name)
    walk(tree.body)
    for node in ast.walk(tree):
        scope=next((s['name'] for s in sorted(symbols,key=lambda s:s['end']-s['start']) if s['start']<getattr(node,'lineno',0)<=s['end']),None)
        if isinstance(node,ast.Import):
            imports.extend({'module':alias.name,'alias':alias.asname or alias.name.split('.')[0],'member':None,'explicit_alias':alias.asname is not None,'level':0,'line':node.lineno,'scope':scope} for alias in node.names)
        elif isinstance(node,ast.ImportFrom):
            imports.extend({'module':node.module or '','alias':alias.asname or alias.name,'member':alias.name,'level':node.level,'line':node.lineno,'scope':scope} for alias in node.names)
        elif isinstance(node,ast.Assert): assertions.append({'line':node.lineno,'expression':ast.unparse(node.test)[:500]})
    return {'symbols':symbols,'imports':imports,'assertions':assertions}
