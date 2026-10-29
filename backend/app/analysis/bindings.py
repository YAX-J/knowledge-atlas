"""Conservative local import bindings; parsing never imports or runs user code."""
import ast
import posixpath
import re


def bindings(content, language):
    result={}
    if language=='python':
        try:
            tree=ast.parse(content)
        except (SyntaxError,ValueError,RecursionError):
            return result
        for node in tree.body:
            if isinstance(node,ast.ImportFrom):
                module='.'*node.level+(node.module or '')
                for item in node.names:
                    if item.name!='*':
                        result[item.asname or item.name]=(module,item.name)
            elif isinstance(node,ast.Import):
                for item in node.names:
                    result[item.asname or item.name.split('.')[0]]=(item.name,'*')
    elif language in {'javascript','jsx','typescript','tsx'}:
        # Only syntax-tree import statements are inspected, never comment/string matches.
        from tree_sitter import Parser
        from app.services.code_source import _language,_text
        raw=content.encode()
        tree=Parser(_language(language)).parse(raw)
        for node in tree.root_node.named_children:
            if node.type!='import_statement' or node.has_error:
                continue
            text=_text(node,raw)
            module=re.search(r'\bfrom\s*[\'"]([^\'"]+)[\'"]',text)
            if not module:
                continue
            path=module.group(1)
            clause=text[len('import'):module.start()].strip()
            for group in re.findall(r'\{([^}]+)\}',clause):
                for entry in group.split(','):
                    parts=re.split(r'\s+as\s+',entry.strip().removeprefix('type '))
                    if parts and parts[0]:
                        result[parts[-1].strip()]=(path,parts[0].strip())
            namespace=re.search(r'\*\s+as\s+(\w+)',clause)
            if namespace:
                result[namespace.group(1)]=(path,'*')
            default=re.match(r'^([A-Za-z_$][\w$]*)',clause)
            if default and default.group(1)!='type':
                result[default.group(1)]=(path,'default')
    return result


def module_matches(source_path, target_path, module, language):
    target=posixpath.normpath(target_path.replace('\\','/'))
    parent=posixpath.dirname(source_path.replace('\\','/'))
    if language=='python':
        if module.startswith('.'):
            dots=len(module)-len(module.lstrip('.'))
            base=parent
            for _ in range(dots-1):
                base=posixpath.dirname(base)
            module=posixpath.join(base,module[dots:].replace('.','/'))
        else:
            module=module.replace('.','/')
            return target in {module+'.py',module+'/__init__.py',
                posixpath.join(parent,module)+'.py',posixpath.join(parent,module,'__init__.py')}
        return target in {module+'.py',module+'/__init__.py'}
    if not module.startswith('.'):
        return False # External packages are not guessed from matching filenames.
    base=posixpath.normpath(posixpath.join(parent,module))
    base=re.sub(r'\.(?:m?js|jsx|tsx?|cjs)$','',base)
    return target in {base+suffix for suffix in ('.ts','.tsx','.js','.jsx','/index.ts','/index.tsx','/index.js','/index.jsx')}


def imported_candidates(source, call, targets, imports):
    root=(call.receiver or call.callee_name).split('.')[0]
    binding=imports.get(root)
    if binding is None:
        return None
    module,name=binding
    actual=call.callee_name if name=='*' else name
    matches=[]
    for target in targets.values():
        if not module_matches(source.relative_path or source.original_name,target.source_path,module,source.source_type):
            continue
        if actual=='default':
            # Native TypeScript mode resolves default/re-export semantics exactly.
            continue
        if target.name==actual:
            matches.append(target)
    return matches
