"""Freeze new upstream documentation questions; no providers, tuning, or human grades."""
from collections import Counter
import json
from pathlib import Path
from scripts.evaluate_dataset import validate_dataset


def create(root):
    if (root/'manifest.json').exists():raise FileExistsError('Frozen holdout already exists')
    provenance=json.loads((root/'provenance.json').read_text(encoding='utf-8'))
    available={item['path']:item['available_at'] for item in provenance['sources']}
    sources={};cases=[]
    def save(name,value):
        (root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    def ref(path,needle):
        source='corpus/notes/'+path
        lines=(root/source).read_text(encoding='utf-8').splitlines()
        found=[i for i,line in enumerate(lines) if needle in line]
        if len(found)!=1:raise ValueError(f'Expected one evidence line: {path}: {needle}')
        line=found[0]
        return dict(source=source,start_line=line+1,end_line=line+1,quote=lines[line])
    def entity(path,key,name,needles):
        source='corpus/notes/'+path
        item=sources.setdefault(source,dict(source=source,available_at=available[source],entities=[],relations=[]))
        lines=[ref(path,needle)['start_line'] for needle in needles]
        item['entities'].append(dict(id=key,type='Concept',name=name,lines=lines))
    facts={
      'background':('background-tasks.md','后台任务执行时机',['You can define background tasks to be run']),
      'background-functions':('background-tasks.md','后台任务函数形式',['It can be an `async def` or normal `def` function']),
      'background-sharing':('background-tasks.md','后台任务依赖共享',['all the background tasks are merged together']),
      'background-heavy':('background-tasks.md','重型后台任务工具',['you might benefit from using other bigger tools like']),
      'dependency-call':('dependencies-current.md','依赖函数传入方式',["You **don't call it** directly"]),
      'dependency-functions':('dependencies-current.md','当前依赖函数定义形式',['You can use `async def` or normal `def`.']),
      'dependency-alias':('dependencies-current.md','Annotated 类型别名',['This is just standard Python, it\'s called a "type alias"']),
      'dependency-version':('dependencies-current.md','Annotated 版本要求',['at least 0.95.1 before using `Annotated`']),
      'cache':('sub-dependencies.md','每请求依赖缓存',['only once per request.']),
      'cache-disable':('sub-dependencies.md','禁用依赖缓存',['you can set the parameter `use_cache=False`']),
      'errors-raise':('handling-errors.md','抛出 HTTPException',["you don't `return` it, you `raise` it"]),
      'errors-detail':('handling-errors.md','错误详情 JSON 类型',['any value that can be converted to JSON']),
      'errors-validation':('handling-errors.md','请求校验错误',['internally raises a `RequestValidationError`']),
      'errors-404':('handling-errors.md','不存在资源的响应',['raise an exception with a status code of `404`']),
      'status-location':('response-status.md','状态码参数位置',['`status_code` is a parameter of the "decorator" method']),
      'status-201':('response-status.md','创建资源状态码',['`201` is the status code for "Created".']),
      'status-204':('response-status.md','无内容响应',['A special case is `204`, "No Content"']),
      'old-history':('dependencies-0941.md','历史依赖函数定义',['You can use `async def` or normal `def`.']),
      'new-history':('dependencies-0950.md','历史依赖函数定义',['You can use `async def` or normal `def`.','This is just standard Python, it\'s called a "type alias"']),
    }
    for key,(path,name,needles) in facts.items():entity(path,key,name,needles)
    def case(category,question,answer,required,keys,*,at=None,answerable=True):
        evidence=[];names=[]
        for key in keys:
            path,name,needles=facts[key];names.append(name)
            for needle in needles:
                item=ref(path,needle)
                if item not in evidence:evidence.append(item)
        cases.append(dict(id=f'holdout-v3-{len(cases)+1:02}',category=category,question=question,answerable=answerable,
            valid_at=at,gold_answer=answer,required_facts=required,gold_evidence=evidence,expected_entities=list(dict.fromkeys(names)),expected_relations=[]))
    case('direct_fact','FastAPI 后台任务在返回响应之前还是之后运行？','在返回响应之后运行。',['响应之后'],['background'])
    case('direct_fact','后台任务函数一定要使用 async def 吗？','不一定，可以使用 async def 或普通 def。',['async def','def'],['background-functions'])
    case('direct_fact','传给 Depends 的函数应立即调用吗？','不应立即调用，只传函数，不添加调用括号。',['不添加调用括号'],['dependency-call'])
    case('direct_fact','同一请求重复依赖默认计算几次？','共享子依赖每请求计算一次，并缓存结果。',['每请求计算一次'],['cache'])
    case('direct_fact','怎样让同一请求中的依赖重复计算？','在 Depends 中设置 use_cache=False。',['use_cache=False'],['cache-disable'])
    case('direct_fact','HTTPException 应 return 还是 raise？','应该 raise，而不是 return。',['raise','return'],['errors-raise'])
    case('direct_fact','HTTPException 的 detail 必须是字符串吗？','不必，可以是任何可转换为 JSON 的值。',['JSON'],['errors-detail'])
    case('direct_fact','成功创建资源通常使用什么状态码？','通常使用 201 Created。',['201'],['status-201'])
    case('cross_document','依赖函数和后台任务函数是否都能混用同步与异步定义？','两者都可以使用 async def 或普通 def。',['async def','def'],['dependency-functions','background-functions'])
    case('cross_document','如何同时避免同一请求重复计算依赖，并在响应后执行附带任务？','使用默认每请求缓存，并用后台任务在响应之后执行。',['每请求缓存','响应之后'],['cache','background'])
    case('cross_document','共享依赖和多个层级的后台任务分别怎样避免重复对象？','依赖按请求缓存；后台任务复用对象并合并任务。',['缓存','合并任务'],['cache','background-sharing'])
    case('cross_document','找不到资源与成功创建资源分别应返回什么状态码？','找不到资源返回 404，创建资源通常返回 201。',['404','201'],['errors-404','status-201'])
    case('cross_document','错误详情可以返回 JSON，但 204 响应也可以带 JSON 吗？','错误详情可以是 JSON；204 必须没有响应体。',['JSON','204','没有响应体'],['errors-detail','status-204'])
    case('cross_document','更改正常响应的状态码与中断请求分别在哪里设置？','正常状态码放在 decorator；中断请求使用 raise HTTPException。',['decorator','raise','HTTPException'],['status-location','errors-raise'])
    case('cross_document','当前指南的 Annotated 建议与 0.95.0 历史指南的类型别名是否相容？','当前要求至少 0.95.1；0.95.0 文档已介绍 type alias，但版本说明需要分别核对。',['0.95.1','type alias'],['dependency-version','new-history'])
    case('cross_document','重型后台计算与普通请求校验失败各使用什么工具或异常？','重型后台计算可考虑 Celery，请求校验失败是 RequestValidationError。',['Celery','RequestValidationError'],['background-heavy','errors-validation'])
    case('temporal','截至 2023-03-16，依赖函数允许哪些定义形式？','当时文档允许 async def 或普通 def。',['async def','def'],['old-history'],at='2023-03-16T00:00:00Z')
    case('temporal','截至 2023-03-20，依赖函数允许哪些定义形式？','当时文档允许 async def 或普通 def。',['async def','def'],['new-history'],at='2023-03-20T00:00:00Z')
    case('temporal','截至 2023-03-20，是否已有共享 Annotated 依赖的类型别名说明？','已有，文档说明它是标准 Python type alias。',['type alias'],['new-history'],at='2023-03-20T00:00:00Z')
    case('temporal','截至 2023-03-15，当时的文档是否要求依赖必须异步定义？','不要求，可以使用 async def 或普通 def。',['async def','def'],['old-history'],at='2023-03-15T00:00:00Z')
    for question in ['这些指南作者在生产环境的每月后台任务费用是多少？','本项目的生产数据库密码是什么？','Celery 在任意硬件上每秒能处理多少任务？','这些文档中实际人工盲评的正确率是多少？']:
        case('unanswerable',question,'文档没有足够证据，需要额外资料。',[],[],answerable=False)
    save('manifest.json',dict(dataset_id='knowledge-atlas-holdout-v3',version='3.0.0',language='zh-CN',created_at='2026-10-29',source_count=len(sources),case_count=len(cases),category_counts=dict(Counter(item['category'] for item in cases)),corpus_root='corpus',cases_file='cases.jsonl',license='Upstream FastAPI MIT; see LICENSE-fastapi.txt and pinned provenance.json'))
    (root/'cases.jsonl').write_text(''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in cases),encoding='utf-8',newline='\n')
    summary=validate_dataset(root)[2]
    save('reviewed_graph.json',dict(fixture_id='upstream-notes-holdout-v3',version='3.0.0',dataset_id=summary['dataset_id'],dataset_fingerprint_sha256=summary['fingerprint_sha256'],
        provenance='Agent-authored gold, not human review. Commit availability clocks are research replay only; no production backdating.',sources=list(sources.values()),changes=[dict(new='new-history',old='old-history',effective_at=available['corpus/notes/dependencies-0950.md'],evidence_line=ref('dependencies-0950.md','You can use `async def` or normal `def`.')['start_line'],reason='The 0.95.0 documentation snapshot replaces the 0.94.1 snapshot for this replay; not an assertion that the previous API became invalid.')]))
    save('protocol.json',dict(dataset=summary,development_datasets=['knowledge-atlas-eval-v1','knowledge-atlas-public-v2'],test_dataset=summary['dataset_id'],
        split_unit='source family; both historical versions stay in the test split',ranking_tuned_on_this_set=False,provider_calls=0,human_coverage=0,
        temporal_scope='Release-commit document availability, not real personal-note chronology',primary_metric='macro evidence Recall@5; report temporal and cross-document categories separately'))
    return summary


if __name__=='__main__':print(json.dumps(create(Path(__file__).resolve().parents[2]/'evaluation/holdout-v3'),indent=2))
