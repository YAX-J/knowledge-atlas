import os
from types import SimpleNamespace
import uuid
import pytest
from app.core.config import Settings
from app.services import code_agent, code_semantics


def source(path,content,language='typescript'):
    return SimpleNamespace(id=uuid.uuid4(),relative_path=path,original_name=path.rsplit('/',1)[-1],
        content=content,source_type=language)


def test_import_alias_candidates_cover_python_target_without_name_guessing(monkeypatch):
    main=source('pkg/main.py','from .helpers import actual as renamed\nrenamed()\n','python')
    target=source('pkg/helpers.py','def actual():\n    return 1\n','python')
    wrong=source('other/helpers.py','def actual():\n    return 2\n','python')
    calls,targets,detected,truncated,errors=code_agent._non_java_candidates(main,[target,wrong])
    assert detected==1 and len(calls)==1
    assert [targets[key].source_path for key in calls[0].candidate_ids]==['pkg/helpers.py']


def test_native_result_must_map_to_real_source_declaration(monkeypatch):
    main=source('main.ts','import { actual as renamed } from "./helper";\nrenamed();\n')
    target=source('helper.ts','export function actual() { return 1; }\n')
    monkeypatch.setattr(code_semantics,'analyze',lambda *_:dict(engine='test-compiler',calls=[
        dict(line=2,column=1,expression='renamed',target=dict(path='helper.ts',line=1,name='actual')),
        dict(line=2,column=10,expression='forged',target=dict(path='../private.ts',line=1))],diagnostics=[],truncated=False))
    result=code_agent.analyze_snapshot(source=main,related=[target],settings=Settings(_env_file=None),strategy='semantic')
    assert result.calls[0].resolution=='resolved' and result.calls[1].resolution=='unresolved'
    assert result.provider_call_count==0 and result.uncovered_call_count==1
    assert result.related_symbols[0].source_id==target.id


@pytest.mark.parametrize('path,other,code',[
    ('main.ts','main.ts','SEMANTIC_SNAPSHOT_AMBIGUOUS'),
    ('../main.ts','helper.ts','SEMANTIC_PATH_INVALID'),
    ('C:/private.ts','helper.ts','SEMANTIC_PATH_INVALID'),
])
def test_compiler_rejects_ambiguous_or_escaping_paths_before_process(monkeypatch,path,other,code):
    from app.core.errors import AppError
    monkeypatch.setattr(code_semantics.subprocess,'run',lambda *_a,**_k:pytest.fail('No compiler should start'))
    with pytest.raises(AppError) as failure:
        code_semantics.analyze(source(path,'function run() {}'),[source(other,'function help() {}')])
    assert failure.value.code==code


@pytest.mark.parametrize('language',['typescript','java','go'])
def test_missing_native_sdk_is_a_clear_error_without_provider(monkeypatch,language):
    from app.core.errors import AppError
    monkeypatch.setattr(code_semantics.shutil,'which',lambda _:None)
    with pytest.raises(AppError) as failure:
        code_semantics.analyze(source('main.code','',language),[])
    assert failure.value.code=='SEMANTIC_BACKEND_UNAVAILABLE'


@pytest.mark.parametrize('failure',['timeout','process-error','oversized','invalid-json'])
def test_compiler_failures_are_sanitized_and_bounded(monkeypatch,failure):
    from app.core.errors import AppError
    import subprocess
    monkeypatch.setattr(code_semantics.shutil,'which',lambda _:'trusted-node')
    def process(command,**kwargs):
        assert command[0]=='trusted-node' and command[1].endswith('typescript_semantics.cjs')
        assert kwargs['timeout']==30 and kwargs['cwd']==code_semantics.ROOT
        if failure=='timeout': raise subprocess.TimeoutExpired(command,30)
        return SimpleNamespace(returncode=1 if failure=='process-error' else 0,
            stdout='x'*2_000_001 if failure=='oversized' else 'invalid',stderr='secret user text')
    monkeypatch.setattr(code_semantics.subprocess,'run',process)
    with pytest.raises(AppError) as result:
        code_semantics.analyze(source('main.ts','const run = () => 1;'),[])
    assert result.value.code=='SEMANTIC_ANALYSIS_FAILED' and 'secret' not in result.value.message


@pytest.mark.skipif(os.environ.get('KA_NATIVE_COMPILERS')!='1',reason='explicit native compiler acceptance')
@pytest.mark.parametrize('language',['typescript','java','go'])
def test_real_compiler_resolves_import_alias_or_overload(language):
    if language=='typescript':
        main=source('main.ts','import { actual as renamed } from "./helper";\nrenamed(1);\n')
        target=source('helper.ts','export function actual(value: number) { return value; }\n')
    elif language=='java':
        main=source('Main.java','class Main { void run() { Helper.actual(1); } }','java')
        target=source('Helper.java','class Helper { static int actual(int value) { return value; }\nstatic String actual(String value) { return value; } }','java')
    else:
        main=source('main.go','package demo\nfunc run() { actual(1) }\n','go')
        target=source('helper.go','package demo\nfunc actual(value int) int { return value }\n','go')
    result=code_agent.analyze_snapshot(source=main,related=[target],settings=Settings(_env_file=None),strategy='semantic')
    assert any(symbol.source_id==target.id and symbol.start_line==(2 if language=='go' else 1) for symbol in result.related_symbols)
    assert result.provider_call_count==0
