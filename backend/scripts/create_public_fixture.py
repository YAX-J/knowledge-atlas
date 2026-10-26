"""Author the separate public-v2 corpus annotations before the first provider experiment.

This is an agent-curated research fixture, never a human quality grade. Sources
are full, unmodified public files pinned in provenance.json. No model is called.
"""
from collections import Counter
import json
from pathlib import Path
from scripts.evaluate_dataset import validate_dataset


def create(root):
    if (root/'manifest.json').exists():
        raise FileExistsError('Frozen public-v2 already exists; create a separately versioned dataset instead')
    def save(name,value):
        (root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def line(path,needle):
        matches=[i for i,value in enumerate((root/'corpus'/path).read_text(encoding='utf-8').splitlines(),1) if needle in value]
        if len(matches)!=1:
            raise ValueError(f'Expected one exact source location: {path} / {needle}')
        return matches[0]
    sources={}
    def entity(path,key,name,needles):
        source=sources.setdefault(path,dict(source='corpus/'+path,available_at='2026-10-26T00:00:00Z',entities=[],relations=[]))
        source['entities'].append(dict(id=key,type='CodeEntity',name=name,lines=[line(path,n) for n in needles]))
    def relation(path,key,kind,start,end,needle):
        sources[path]['relations'].append(dict(id=key,type=kind,source=start,target=end,lines=[line(path,needle)]))
    entity('fastapi/first_steps.py','root','fastapi.first_steps.root',['@app.get("/")','"Hello World"'])
    entity('fastapi/paths.py','path-reader','fastapi.path_params.read_item',['@app.get("/items/{item_id}")','async def read_item(item_id):','return {"item_id": item_id}'])
    entity('fastapi/query.py','query-reader','fastapi.query_params.read_item',['fake_items_db =','async def read_item(skip:','return fake_items_db['])
    entity('fastapi/dependencies.py','common-parameters','fastapi.dependencies.common_parameters',['async def common_parameters(','return {"q": q'])
    entity('fastapi/dependencies.py','dependent-items','fastapi.dependencies.read_items',['@app.get("/items/")','async def read_items('])
    entity('fastapi/dependencies.py','dependent-users','fastapi.dependencies.read_users',['@app.get("/users/")','async def read_users('])
    relation('fastapi/dependencies.py','items-dependency','DEPENDS_ON','dependent-items','common-parameters','async def read_items(')
    relation('fastapi/dependencies.py','users-dependency','DEPENDS_ON','dependent-users','common-parameters','async def read_users(')
    entity('fastapi/body.py','body-item','fastapi.body.Item',['name: str','description:','price: float','tax:'])
    entity('fastapi/body.py','body-creator','fastapi.body.create_item',['@app.post(','async def create_item('])
    relation('fastapi/body.py','body-uses-item','USES','body-creator','body-item','async def create_item(')
    entity('fastapi/response.py','response-item','fastapi.response_model.Item',['name: str','price: float','tags:'])
    entity('fastapi/response.py','response-creator','fastapi.response_model.create_item',['@app.post(','async def create_item('])
    entity('fastapi/response.py','response-reader','fastapi.response_model.read_items',['@app.get(','async def read_items(', '"Portal Gun"','"Plumbus"'])
    relation('fastapi/response.py','response-uses-item','USES','response-reader','response-item','@app.get(')
    entity('petclinic/Pet.java','pet-visits','petclinic.Pet.visits',['@OneToMany(','@OrderBy("date ASC")','private final Set<Visit> visits'])
    entity('petclinic/Pet.java','pet-add-visit','petclinic.Pet.addVisit',['public void addVisit(','getVisits().add(visit);'])
    relation('petclinic/Pet.java','visit-collection','USES','pet-add-visit','pet-visits','getVisits().add(visit);')
    entity('petclinic/Visit.java','visit-date','petclinic.Visit.date',['@Column(name = "visit_date")','LocalDate.now().plusDays(1)'])
    entity('petclinic/Visit.java','visit-description','petclinic.Visit.description',['@NotBlank','@Size(max = 255)','private String description;'])
    entity('petclinic/PetType.java','pet-type','petclinic.PetType',['@Table(name = "types")','public class PetType extends NamedEntity'])
    entity('petclinic/Owner.java','owner-phone','petclinic.Owner.telephone',['@Pattern(regexp','private String telephone;'])
    entity('petclinic/Owner.java','owner-add-visit','petclinic.Owner.addVisit',['public void addVisit(Integer','Assert.notNull(petId,','Assert.notNull(visit,','Pet pet = getPet(petId);','pet.addVisit(visit);'])
    entity('petclinic/Owner.java','owner-pets','petclinic.Owner.pets',['private final List<Pet> pets'])
    relation('petclinic/Owner.java','owner-visit-pets','USES','owner-add-visit','owner-pets','Pet pet = getPet(petId);')
    cases=[]
    def case(category,question,answer,facts,refs,entities):
        evidence=[]
        for path,needle in refs:
            number=line(path,needle)
            quote=(root/'corpus'/path).read_text(encoding='utf-8').splitlines()[number-1]
            evidence.append(dict(source='corpus/'+path,start_line=number,end_line=number,quote=quote))
        cases.append(dict(id=f'public-{len(cases)+1:03}',category=category,question=question,answerable=bool(refs),
            valid_at=None,gold_answer=answer,required_facts=facts,gold_evidence=evidence,expected_entities=entities,expected_relations=[]))
    case('direct_fact','FastAPI first_steps 的根路径使用什么 HTTP 方法，返回的 message 是什么？','GET / 返回 message 为 Hello World。',['GET','Hello World'],[('fastapi/first_steps.py','@app.get("/")'),('fastapi/first_steps.py','"Hello World"')],['fastapi.first_steps.root'])
    case('direct_fact','query_params 示例的 read_item 分页参数 skip 和 limit 默认各是多少？','skip 默认 0，limit 默认 10。',['0','10'],[('fastapi/query.py','async def read_item(skip:')],['fastapi.query_params.read_item'])
    case('direct_fact','dependencies 示例的 common_parameters 有哪些参数，它们的默认值是什么？','q 为 None，skip 为 0，limit 为 100。',['None','0','100'],[('fastapi/dependencies.py','async def common_parameters(')],['fastapi.dependencies.common_parameters'])
    case('direct_fact','FastAPI 请求体 body 示例中，Item 的哪些字段必填，哪些字段可以省略？','name 和 price 必填；description 和 tax 默认为 None，可以省略。',['name','price','description','tax'],[('fastapi/body.py','name: str'),('fastapi/body.py','price: float'),('fastapi/body.py','description:'),('fastapi/body.py','tax:')],['fastapi.body.Item'])
    case('direct_fact','response_model 示例里，Item.tags 的类型和默认值是什么？','tags 类型为 list[str]，默认空列表。',['list[str]','空'],[('fastapi/response.py','tags:')],['fastapi.response_model.Item'])
    case('direct_fact','PetClinic 新建 Visit 时，默认日期是今天还是明天？','构造器使用 LocalDate.now().plusDays(1)，默认为明天。',['明天'],[('petclinic/Visit.java','LocalDate.now().plusDays(1)')],['petclinic.Visit.date'])
    case('direct_fact','PetClinic Visit.description 有哪些非空和长度约束？','使用 @NotBlank，并由 @Size(max = 255) 限制长度。',['NotBlank','255'],[('petclinic/Visit.java','@NotBlank'),('petclinic/Visit.java','@Size(max = 255)')],['petclinic.Visit.description'])
    case('direct_fact','PetClinic PetType 映射到哪张表，继承哪个基类？','映射 types 表，继承 NamedEntity。',['types','NamedEntity'],[('petclinic/PetType.java','@Table(name = "types")'),('petclinic/PetType.java','public class PetType extends NamedEntity')],['petclinic.PetType'])
    case('code_location','Owner.addVisit 中怎样定位宠物并把 Visit 交给它？','先调用 getPet(petId)，再调用 pet.addVisit(visit)。',['getPet(petId)','pet.addVisit(visit)'],[('petclinic/Owner.java','Pet pet = getPet(petId);'),('petclinic/Owner.java','pet.addVisit(visit);')],['petclinic.Owner.addVisit'])
    case('code_location','FastAPI query 示例的 fake_items_db 初始包含哪些 item_name？','包含 Foo、Bar 和 Baz。',['Foo','Bar','Baz'],[('fastapi/query.py','fake_items_db =')],['fastapi.query_params.read_item'])
    case('code_location','Pet 类如何声明就诊集合，并按什么字段顺序加载？','使用 LinkedHashSet 保存 Set<Visit>，按 date ASC 排序。',['LinkedHashSet','date ASC'],[('petclinic/Pet.java','private final Set<Visit> visits'),('petclinic/Pet.java','@OrderBy("date ASC")')],['petclinic.Pet.visits'])
    case('code_location','response_model 的 read_items 示例返回哪两件商品，价格分别是多少？','Portal Gun 的价格为 42.0，Plumbus 的价格为 32.0。',['Portal Gun','42.0','Plumbus','32.0'],[('fastapi/response.py','"Portal Gun"'),('fastapi/response.py','"Plumbus"')],['fastapi.response_model.read_items'])
    case('cross_document','body 与 response_model 两份示例中的 Item 共同包含哪些必填字段？','共同必填字段为 name 和 price。',['name','price'],[('fastapi/body.py','name: str'),('fastapi/body.py','price: float'),('fastapi/response.py','name: str'),('fastapi/response.py','price: float')],['fastapi.body.Item','fastapi.response_model.Item'])
    case('cross_document','query_params.read_item 与 dependencies.common_parameters 的默认 limit 相同吗？','不同，前者是 10，后者是 100。',['10','100'],[('fastapi/query.py','async def read_item(skip:'),('fastapi/dependencies.py','async def common_parameters(')],['fastapi.query_params.read_item','fastapi.dependencies.common_parameters'])
    case('cross_document','Owner.addVisit 把就诊记录交给 Pet 后，Pet.addVisit 最终做了什么？','Owner 调用 pet.addVisit(visit)，Pet 再调用 getVisits().add(visit) 加入就诊集合。',['pet.addVisit(visit)','getVisits().add(visit)'],[('petclinic/Owner.java','pet.addVisit(visit);'),('petclinic/Pet.java','getVisits().add(visit);')],['petclinic.Owner.addVisit','petclinic.Pet.addVisit'])
    case('cross_document','新建 Visit 的默认日期与 Pet 中访问就诊集合时的排序规则分别是什么？','Visit 默认为明天，Pet 的就诊集合按 date ASC 排序。',['明天','date ASC'],[('petclinic/Visit.java','LocalDate.now().plusDays(1)'),('petclinic/Pet.java','@OrderBy("date ASC")')],['petclinic.Visit.date','petclinic.Pet.visits'])
    for question in ['PetClinic 的生产数据库密码是什么？','这些 FastAPI 示例部署后每秒能处理多少请求？','宠物诊所账单如何计算增值税税率？','Owner 的电话字段为何选择这个长度，作者评估过哪些替代方案？']:
        case('unanswerable',question,'当前源码没有足够证据回答，需要额外资料。',[],[],[])
    (root/'cases.jsonl').write_text(''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in cases),encoding='utf-8')
    save('manifest.json',dict(dataset_id='knowledge-atlas-public-v2',version='2.0.0',language='zh-CN',created_at='2026-10-26',
        source_count=len(sources),case_count=len(cases),category_counts=dict(Counter(item['category'] for item in cases)),
        corpus_root='corpus',cases_file='cases.jsonl',license='Upstream MIT (FastAPI) and Apache-2.0 (Spring PetClinic); see license files and provenance.json'))
    summary=validate_dataset(root)[2]
    save('reviewed_graph.json',dict(fixture_id='public-repository-v2',version='2.0.0',dataset_id=summary['dataset_id'],
        dataset_fingerprint_sha256=summary['fingerprint_sha256'],provenance='Agent-curated code annotations, created before first experiment; not human review or extraction quality.',
        sources=list(sources.values()),changes=[]))
    save('protocol.json',dict(dataset=summary,modes=['keyword','bm25','vector','hybrid','rrf'],
        pipeline='online questions.answer_question, fresh retrieval each time; all modes share one immutable curated graph/index',
        primary_metric='macro evidence Recall@5',human_metrics=['answer_correct','explainability_score'],
        human_coverage=0,ranking_tuned_on_this_set=False,prospective_separation='New public sources/questions, separate from old synthetic development set; agent-authored, not independently human-curated.',
        default_selection='Select on primary metric, report ties/failed cases and human coverage; no claims of semantic answer superiority without real human grades.',
        provider_limits=dict(model=120,embedding=160),temporal_quality='Not evaluated by this set; existing temporal regressions remain separate.'))
    return summary


if __name__=='__main__':
    print(json.dumps(create(Path(__file__).resolve().parents[2]/'evaluation/public-v2'),ensure_ascii=False,indent=2))
