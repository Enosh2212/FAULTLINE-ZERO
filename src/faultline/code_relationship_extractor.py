"""Static relationships; unresolved/dynamic calls are recorded rather than guessed."""
from __future__ import annotations
import ast
from pathlib import PurePosixPath
from faultline.repository_indexer import scoped


def extract_relationships(index: dict) -> dict:
    repo,rev=index['repository'],index['revision'];edges=[];unknown=[]
    sources={f['path']:f for f in index['files'] if f['language']=='Python' and not f.get('parse_error')}
    shadowed={}
    for path,file in sources.items():
        bound=set()
        def bindings(node):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):return
            if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Store):bound.add(node.id)
            for child in ast.iter_child_nodes(node):bindings(child)
        bindings(ast.parse(file['source']));shadowed[path]=bound
    modules={path.removesuffix('.py').replace('/','.').removesuffix('.__init__'):path for path in sources}
    def sid(path,name):return scoped(repo,rev,'symbol',path+'#'+name)
    def ref(path,line):return {'path':path,'line':line,'repository':repo,'revision':rev,'origin':'python_ast'}
    def add(source,relation,target,path,line):edges.append({'source':source,'relation':relation,'target':target,'provenance':ref(path,line),'classification':'FACT'})
    for path,f in sources.items():
        fid=scoped(repo,rev,'file',path)
        by_name={s['name']:s for s in f['symbols']}
        for symbol in f['symbols']:
            add(fid,'DEFINES',sid(path,symbol['name']),path,symbol['start'])
            add(sid(path,symbol['name']),'BELONGS_TO',fid,path,symbol['start'])
            if symbol['parent']:add(sid(path,symbol['parent']),'DEFINES',sid(path,symbol['name']),path,symbol['start'])
        aliases={}
        for imp in f['imports']:
            module=imp['module']
            if imp['level']:
                parent=path.removesuffix('.py').split('.') if '/' not in path else path.split('/')[:-1]
                module='.'.join(parent[:len(parent)-imp['level']+1]+([module] if module else []))
            target=modules.get(module)
            if target:
                add(fid,'IMPORTS',scoped(repo,rev,'file',target),path,imp['line'])
                if imp.get('scope') is None and ('.' not in module or imp.get('member') or imp.get('explicit_alias')):aliases[imp['alias']]=(target,imp['member'])
            else:unknown.append({'kind':'import','name':module,'reason':'External or unresolved module; no dependency edge guessed','source':ref(path,imp['line'])})
        tree=ast.parse(f['source'])
        class Visitor(ast.NodeVisitor):
            def __init__(self):self.stack=[];self.shadow=[]
            def visit_ClassDef(self,node):
                self.stack.append(node.name);self.shadow.append(set());self.generic_visit(node);self.shadow.pop();self.stack.pop()
            def visit_FunctionDef(self,node):
                self.stack.append(node.name)
                bound={a.arg for a in [*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs]}
                # A name rebound locally cannot be assumed to reference a module-level function.
                bound.update(n.id for n in ast.walk(node) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store))
                bound.update(n.name for n in ast.walk(node) if n is not node and isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)))
                self.shadow.append(bound)
                for statement in node.body:self.visit(statement)
                self.shadow.pop();self.stack.pop()
            visit_AsyncFunctionDef=visit_FunctionDef
            def visit_Call(self,node):
                owner='.'.join(self.stack)
                target=None;name=ast.unparse(node.func)[:200]
                if isinstance(node.func,ast.Name):
                    if node.func.id in shadowed[path] or any(node.func.id in names for names in self.shadow):pass
                    elif node.func.id in by_name and not by_name[node.func.id]['parent']:target=(path,node.func.id)
                    elif node.func.id in aliases:
                        file,member=aliases[node.func.id]
                        if member and member not in shadowed[file] and any(s['name']==member for s in sources[file]['symbols']):target=(file,member)
                elif isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name):
                    base=node.func.value.id
                    if base in aliases and base not in shadowed[path] and not any(base in names for names in self.shadow):
                        file,member=aliases[base]
                        if member is None and node.func.attr not in shadowed[file] and any(s['name']==node.func.attr for s in sources[file]['symbols']):target=(file,node.func.attr)
                if owner in by_name and target:
                    add(sid(path,owner),'CALLS',sid(*target),path,node.lineno)
                    if f['is_test']:add(sid(path,owner),'REFERENCES',sid(*target),path,node.lineno)
                elif owner in by_name:unknown.append({'kind':'call','name':name,'reason':'Dynamic, built-in, external or shadowed target; not statically resolved','source':ref(path,node.lineno)})
                self.generic_visit(node)
        Visitor().visit(tree)
    for symbol in index['modified_symbols']:
        add(scoped(repo,rev,'commit',rev),'MODIFIES',sid(symbol['path'],symbol['name']),symbol['path'],symbol['start'])
    return {'edges':edges,'unknown_dependencies':unknown}
