"""Provider-free bounded extraction planning over exact immutable source slices."""
import hashlib
import json
import uuid
from types import SimpleNamespace

from app.core.errors import AppError
from app.llm.prompts import PROMPT_VERSION
from app.services import deepseek

MAX_BATCHES = 8
MAX_CHUNKS = 800
PROTOCOL = 'extraction-batches-v1'


def _size(items):
    return len(json.dumps({'chunks':items},ensure_ascii=False))


def build_plan(source, chunks, settings):
    limit=settings.extraction_max_input_chars
    if not chunks:
        raise AppError(status_code=409,code='SOURCE_HAS_NO_CHUNKS',message='资料没有可提取的原文分块')
    if len(chunks)>MAX_CHUNKS or sum(len(chunk.content) for chunk in chunks)>limit*MAX_BATCHES:
        raise AppError(status_code=413,code='EXTRACTION_BATCH_LIMIT',message='资料超过最多8批的抽取预算，请按章节拆分')
    fragments=[];evidence={}
    for chunk in chunks:
        offset=0
        while offset<len(chunk.content):
            low=offset+1;high=min(len(chunk.content),offset+limit);end=offset
            while low<=high:
                middle=(low+high)//2
                if _size([dict(chunk_id=str(chunk.id),content=chunk.content[offset:middle])])<=limit:
                    end=middle;low=middle+1
                else:high=middle-1
            if end==offset:
                raise AppError(status_code=413,code='EXTRACTION_BATCH_LIMIT',message='单段输入无法放入抽取预算')
            if end<len(chunk.content):
                newline=chunk.content.rfind('\n',offset+(end-offset)//2,end)
                if newline>=0:end=newline+1
            identifier=chunk.id if offset==0 and end==len(chunk.content) else uuid.uuid5(chunk.id,f'{PROTOCOL}:{offset}:{end}')
            content=chunk.content[offset:end]
            fragments.append(dict(chunk_id=str(identifier),content=content))
            evidence[identifier]=dict(chunk_id=chunk.id,content=content,
                start_line=chunk.start_line+chunk.content[:offset].count('\n'),heading_path=list(chunk.heading_path))
            offset=end
    batches=[];current=[]
    for fragment in fragments:
        if current and (len(current)>=100 or _size([*current,fragment])>limit):
            batches.append(current);current=[]
        current.append(fragment)
    if current:batches.append(current)
    if len(batches)>MAX_BATCHES:
        raise AppError(status_code=413,code='EXTRACTION_BATCH_LIMIT',message='资料超过最多8批的抽取预算，请按章节拆分')
    signature=dict(protocol=PROTOCOL,source_id=str(source.id),source_sha256=source.content_sha256,
        prompt=PROMPT_VERSION,model=settings.deepseek_model,endpoint=settings.deepseek_base_url,
        limit=limit,batches=batches)
    digest=hashlib.sha256(json.dumps(signature,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    public=dict(protocol=PROTOCOL,plan_sha256=digest,batch_count=len(batches),max_batches=MAX_BATCHES,
        chunk_count=len(chunks),fragment_count=len(fragments),input_chars=[_size(batch) for batch in batches],
        input_limit=limit,model=settings.deepseek_model)
    return SimpleNamespace(public=public,batches=batches,evidence=evidence)


def invoke_batches(plan,settings,task_id,before_batch):
    from app.agents.registry import get_agent
    entities=[];relations=[];seen_entities={};seen_relations={}
    def signature(item,endpoints=None):
        value=item.model_dump(mode='json',exclude={'local_id','evidence','source','target'})
        value['evidence']=sorted((str(plan.evidence[ref.chunk_id]['chunk_id']),ref.quote,
            plan.evidence[ref.chunk_id]['start_line']+plan.evidence[ref.chunk_id]['content'][:plan.evidence[ref.chunk_id]['content'].index(ref.quote)].count('\n')) for ref in item.evidence)
        value['endpoints']=endpoints
        return json.dumps(value,ensure_ascii=False,sort_keys=True)
    for index,batch in enumerate(plan.batches):
        before_batch(index,len(plan.batches))
        draft=get_agent('knowledge_extraction').run('single_step',dict(settings=settings,chunks=batch))
        supplied={uuid.UUID(item['chunk_id']):item['content'] for item in batch}
        for item in [*draft.entities,*draft.relations]:
            if any(ref.chunk_id not in supplied or ref.quote not in supplied[ref.chunk_id] for ref in item.evidence):
                raise deepseek.ExtractionError('EXTRACTION_EVIDENCE_INVALID','分批抽取引用不属于当前批次，本次候选未保存')
        names={item.local_id:'b'+uuid.uuid5(task_id,f'{index}:{item.local_id}').hex for item in [*draft.entities,*draft.relations]}
        for item in draft.entities:
            key=signature(item)
            if key in seen_entities:names[item.local_id]=seen_entities[key]
            else:
                seen_entities[key]=names[item.local_id]
                entities.append(item.model_copy(update={'local_id':names[item.local_id]}))
        for item in draft.relations:
            key=signature(item,[names[item.source],names[item.target]])
            if key not in seen_relations:
                seen_relations[key]=names[item.local_id]
                relations.append(item.model_copy(update={'local_id':names[item.local_id],'source':names[item.source],
                    'target':names[item.target]}))
    return SimpleNamespace(entities=entities,relations=relations)
