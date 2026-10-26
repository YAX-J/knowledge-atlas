"""Explicit compiler parsing/type analysis, never build scripts or imported program execution."""
import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import os

from app.core.errors import AppError

ROOT=Path(__file__).resolve().parents[2]


def analyze(source, related):
    items=[source,*related]
    paths={item.id:(item.relative_path or item.original_name).replace('\\','/') for item in items}
    # Ambiguous versions must be selected explicitly rather than silently overwritten by a compiler host.
    if len(set(paths.values())) != len(paths):
        raise AppError(status_code=409,code='SEMANTIC_SNAPSHOT_AMBIGUOUS',message='同路径存在多个来源版本，请选择单一提交的仓库快照')
    if any(PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or ':' in path for path in paths.values()):
        raise AppError(status_code=409,code='SEMANTIC_PATH_INVALID',message='编译分析需要仓库内相对路径')
    environment=None
    if source.source_type in {'javascript','jsx','typescript','tsx'}:
        executable=shutil.which('node')
        script=ROOT/'scripts/typescript_semantics.cjs'
        if not executable or not (ROOT.parent/'frontend/node_modules/typescript/lib/typescript.js').is_file():
            raise AppError(status_code=503,code='SEMANTIC_BACKEND_UNAVAILABLE',message='请安装项目 Node.js 与 TypeScript 依赖')
        payload=json.dumps(dict(path=paths[source.id],sources=[dict(path=paths[item.id],content=item.content) for item in items]))
        command=[executable,str(script)]
    elif source.source_type=='go':
        executable=shutil.which('go')
        if not executable:
            raise AppError(status_code=503,code='SEMANTIC_BACKEND_UNAVAILABLE',message='Go 静态类型分析需要本机 Go SDK')
        payload=json.dumps(dict(path=paths[source.id],sources=[dict(path=paths[item.id],content=item.content) for item in items]))
        command=[executable,'run',str(ROOT/'scripts/go_semantics.go')]
        environment={**os.environ,'GO111MODULE':'off','GOPROXY':'off','GOSUMDB':'off','CGO_ENABLED':'0'}
    elif source.source_type=='java':
        executable=shutil.which('java')
        if not executable:
            raise AppError(status_code=503,code='SEMANTIC_BACKEND_UNAVAILABLE',message='Java 编译分析需要 JDK 17 或更新版本')
        encode=lambda value:base64.b64encode(value.encode()).decode()
        payload=encode(paths[source.id])+'\n'+'\n'.join(encode(paths[item.id])+'\t'+encode(item.content) for item in items)+'\n'
        command=[executable,'--source','17',str(ROOT/'scripts/JavaSemantics.java')]
    else:
        raise AppError(status_code=422,code='SEMANTIC_LANGUAGE_UNSUPPORTED',message='原生编译分析支持 Java、JavaScript/TypeScript 和 Go 同包源码；其他语言可使用语法候选和只读 Agent')
    try:
        result=subprocess.run(command,input=payload,text=True,encoding='utf-8',capture_output=True,timeout=30,
            cwd=ROOT,env=environment,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
        if result.returncode or len(result.stdout)>2_000_000:
            raise ValueError('Compiler output unavailable')
        if source.source_type!='java':
            return json.loads(result.stdout)
        calls=[]
        diagnostics=0
        syntax_errors=0
        for line in result.stdout.splitlines():
            parts=line.split('\t')
            if parts[0]=='DIAGNOSTICS':
                diagnostics=int(parts[1]);continue
            if parts[0]=='SYNTAX_ERRORS':
                syntax_errors=int(parts[1]);continue
            row,column,expression,path,target_line,name,end_line,identity=parts
            target = dict(path=base64.b64decode(path).decode(),line=int(target_line),name=base64.b64decode(name).decode(),
                end_line=int(end_line),identity=base64.b64decode(identity).decode()) if path else None
            calls.append(dict(line=int(row),column=int(column),expression=base64.b64decode(expression).decode(),target=target))
        return dict(engine='javac-17',calls=calls,diagnostics=([{'kind':'syntax','count':syntax_errors}] if syntax_errors else [])+
            ([{'kind':'type-context','count':diagnostics-syntax_errors}] if diagnostics>syntax_errors else []),truncated=False)
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        raise AppError(status_code=503,code='SEMANTIC_ANALYSIS_FAILED',message='静态编译分析失败或超时；未执行项目代码，可改用语法候选模式') from exc
