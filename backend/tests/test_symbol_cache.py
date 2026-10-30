from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import uuid

import pytest

from app.analysis.symbol_cache import SymbolCache, SymbolSnapshot, symbol_cache
from app.analysis.parsers import java
from app.services import code_search
from tests.test_code_search import search, upload
from tests.test_sources import create_project


@pytest.fixture(autouse=True)
def clean_cache():
    symbol_cache.clear()
    yield
    symbol_cache.clear()


def source(**changes):
    value = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), project_id=uuid.uuid4(),
        source_type='java', content='class Demo {\n void save() {}\n}\n')
    for key, item in changes.items():setattr(value, key, item)
    return value


def test_repeated_queries_reuse_immutable_symbols_and_keep_exact_results(client, monkeypatch):
    project = create_project(client)
    upload(client, project)
    calls=[]
    original=code_search.java_symbols
    def parse(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(code_search,'java_symbols',parse)
    first=search(client,project,'save')
    assert search(client,project,'SAVE')['items']==first['items']
    assert len(calls)==1 and symbol_cache.info()['hits']==1
    assert search(client,project,'label')['items'][0]['name']=='label'
    assert len(calls)==1
    hit=first['items'][0]
    assert hit['chunk_id'] and hit['task_id']


@pytest.mark.parametrize('field', ['id','user_id','project_id','content','source_type','version','limits'])
def test_cache_key_preserves_identity_content_language_and_parser_revision(monkeypatch,field):
    original=source()
    before=code_search._symbols(original)
    changed=SimpleNamespace(**vars(original))
    if field in {'id','user_id','project_id'}:setattr(changed,field,uuid.uuid4())
    if field=='content':changed.content='class Other {}'
    if field=='source_type':changed.source_type='python';changed.content='def save():\n pass\n'
    if field=='version':monkeypatch.setattr(java,'SYMBOL_PARSER_VERSION','new-test-parser')
    if field=='limits':monkeypatch.setattr(java,'MAX_STRUCTURE_SYMBOLS',1)
    after=code_search._symbols(changed)
    assert symbol_cache.info()['misses']==2 and before is not after
    assert code_search._symbols(changed) is after
    with pytest.raises(FrozenInstanceError):after.symbols[0].name='mutated'


def test_lru_entry_and_accounted_byte_limits_and_parse_failure():
    cache=SymbolCache(max_entries=2,max_bytes=2048)
    empty=SymbolSnapshot((),False)
    cache.get_or_compute('a',lambda:empty)
    cache.get_or_compute('b',lambda:empty)
    cache.get_or_compute('a',lambda:pytest.fail('cached'))
    cache.get_or_compute('c',lambda:empty)
    assert cache.info()==dict(entries=2,accounted_bytes=2048,hits=1,misses=3)
    cache.get_or_compute('b',lambda:empty)
    assert cache.info()['misses']==4
    too_small=SymbolCache(max_bytes=1)
    for _ in range(2):too_small.get_or_compute('large',lambda:empty)
    assert too_small.info()['entries']==0 and too_small.info()['misses']==2
    with pytest.raises(ValueError):cache.get_or_compute('error',lambda:(_ for _ in ()).throw(ValueError('parse failed')))
    assert cache.get_or_compute('error',lambda:empty) is empty


def test_syntax_and_truncation_flags_survive_cache_hits():
    broken=source(source_type='python',content='def broken(:\n pass\n')
    first=code_search._symbols(broken)
    assert first.has_syntax_errors
    assert code_search._symbols(broken)==first


def test_cached_source_still_requires_current_scope_and_readiness(client,db_session):
    from app.models.domain import SourceDocument
    project=create_project(client)
    uploaded=upload(client,project)
    assert search(client,project,'save')['items']
    record=db_session.get(SourceDocument,uuid.UUID(uploaded['source_id']))
    record.status='failed';db_session.commit()
    assert search(client,project,'save')['items']==[]
    assert symbol_cache.info()['hits']==0
