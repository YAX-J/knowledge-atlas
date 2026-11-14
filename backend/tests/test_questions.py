import uuid
from datetime import datetime, timezone

import pytest
from pydantic import SecretStr

from app.api.routes import questions as question_routes
from app.api.routes import search as search_routes
from app.core.config import Settings
from app.schemas.questions import AnswerDraft
from app.services import deepseek, embeddings, questions
from app.services.question_time import resolve_question_time
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured


@pytest.mark.parametrize(('text', 'source', 'expected'), [
    ('今天的主库？', 'question', '2026-11-13T18:00:00Z'),
    ('昨天的主库？', 'question', '2026-11-13T00:00:00Z'),
    ('What was the database yesterday?', 'question', '2026-11-13T00:00:00Z'),
    ('现在用什么？', 'current', '2026-11-13T18:00:00Z'),
    ('2024年2月29号的主库？', 'question', '2024-02-29T00:00:00Z'),
    ('2026-06-01 的主库？', 'question', '2026-06-01T00:00:00Z'),
    ('2026-02-29 的主库？', 'clarification', None),
    ('上次迁移前用什么？', 'clarification', None),
    ('上周主库是什么？', 'clarification', None),
    ('4 月 1 日使用什么？', 'clarification', None),
    ('2026-04-01 到 2026-06-01 用了什么？', 'clarification', None),
    ('2026-04-01-10 期间用什么？', 'clarification', None),
    ('2026-04-01 下午 3 点，用什么？', 'clarification', None),
    ('2026-04-01T11:30:00+08:00 用什么？', 'clarification', None),
])
def test_question_time_resolution(text, source, expected):
    now = datetime(2026, 11, 13, 18, tzinfo=timezone.utc)
    scope = resolve_question_time(text, None, now)
    assert scope.source == source
    assert scope.model_dump(mode='json')['valid_at'] == expected


def test_ambiguous_question_asks_for_time_before_retrieval_or_provider(client, monkeypatch):
    monkeypatch.setattr(question_routes, 'get_settings', lambda: Settings(_env_file=None))
    monkeypatch.setattr(questions, 'search_knowledge', lambda **_: pytest.fail('Clarification must not retrieve'))
    project = client.post('/api/v1/projects', json={'name': 'Ambiguous question'}).json()['id']
    response = client.post(f'/api/v1/projects/{project}/questions', json={
        'question': '上次迁移前，订单服务的主数据库是什么？',
    })
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer['time_scope']['source'] == 'clarification'
    assert answer['time_scope']['valid_at'] is None
    assert not answer['supported'] and answer['evidence'] == []
    assert '手动选择' in answer['missing_information'][0]


def prepared_project(client, monkeypatch):
    settings = Settings(
        _env_file=None,
        deepseek_api_key=SecretStr('question-secret'),
        embedding_api_key=SecretStr('embedding-secret'),
        embedding_base_url='https://embeddings.example/v1',
        embedding_model='test-embedding-1024',
    )
    monkeypatch.setattr(question_routes, 'get_settings', lambda: settings)
    monkeypatch.setattr(search_routes, 'get_settings', lambda: settings)

    def fake_embeddings(_settings, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 1024
            vector[0 if 'PostgreSQL' in text or 'database' in text.lower() else 1] = 1.0
            vectors.append(vector)
        return vectors
    monkeypatch.setattr(embeddings, 'embed_texts', fake_embeddings)

    project_id, _, items = extracted(client, monkeypatch)
    for item in sorted(items, key=lambda item: item['kind'] != 'entity'):
        confirm(client, item)
    rebuilt = client.post(f'/api/v1/projects/{project_id}/embeddings/rebuild')
    assert rebuilt.status_code == 200
    return project_id, settings


def test_question_answer_uses_only_validated_retrieval_evidence(
    client, configured, monkeypatch,
):
    project_id, _ = prepared_project(client, monkeypatch)
    calls = []

    def answer(_settings, question, evidence):
        calls.append((question, evidence))
        assert 1 <= len(evidence) <= 12
        assert all(item['quote'] == 'Use PostgreSQL for storage.' for item in evidence)
        return AnswerDraft(
            supported=True,
            answer='该项目使用 PostgreSQL 保存知识。',
            confidence=.92,
            citation_ids=[evidence[0]['id']],
            missing_information=[],
        )
    monkeypatch.setattr(deepseek, 'answer_question', answer)

    response = client.post(f'/api/v1/projects/{project_id}/questions', json={
        'question': 'Which database does this project use for durable knowledge storage today?',
    })
    assert response.status_code == 200
    data = response.json()
    assert data['supported'] and data['confidence'] == .92
    assert data['answer'] == '该项目使用 PostgreSQL 保存知识。'
    assert len(data['evidence']) == len(data['entity_ids']) == 1
    assert data['evidence'][0]['quote'] == 'Use PostgreSQL for storage.'
    assert data['evidence'][0]['entity_id'] == data['entity_ids'][0]
    assert data['retrieval']['keyword_hits'] >= 0
    assert data['retrieval']['vector_hits'] >= 1
    assert data['retrieval']['indexed_count'] == data['retrieval']['eligible_count'] == 2
    assert calls[0][0].startswith('Which database')
    assert 'user_id' not in str(calls) and 'candidate_id' not in str(calls)


def test_question_rejects_model_citations_outside_retrieved_evidence(
    client, configured, monkeypatch,
):
    project_id, _ = prepared_project(client, monkeypatch)
    monkeypatch.setattr(deepseek, 'answer_question', lambda *_: AnswerDraft(
        supported=True, answer='Unsupported citation.', confidence=.5,
        citation_ids=[uuid.uuid4()], missing_information=[],
    ))
    response = client.post(f'/api/v1/projects/{project_id}/questions', json={
        'question': 'Which database is used?',
    })
    assert response.status_code == 502
    assert response.json()['error']['code'] == 'QUESTION_EVIDENCE_INVALID'


def test_question_without_evidence_refuses_without_calling_answer_model(
    client, monkeypatch,
):
    settings = Settings(
        _env_file=None,
        deepseek_api_key=SecretStr('question-secret'),
        embedding_api_key=SecretStr('embedding-secret'),
        embedding_base_url='https://embeddings.example/v1',
        embedding_model='test-embedding-1024',
    )
    monkeypatch.setattr(question_routes, 'get_settings', lambda: settings)
    monkeypatch.setattr(embeddings, 'embed_texts', lambda _settings, _texts: [[1.0] + [0.0] * 1023])
    monkeypatch.setattr(
        deepseek, 'answer_question',
        lambda *_: (_ for _ in ()).throw(AssertionError('No evidence must not call the answer model')),
    )
    project_id = client.post('/api/v1/projects', json={'name': 'Empty questions'}).json()['id']
    response = client.post(f'/api/v1/projects/{project_id}/questions', json={
        'question': 'What has been decided?',
    })
    assert response.status_code == 200
    data = response.json()
    assert not data['supported'] and data['confidence'] == 0
    assert data['evidence'] == [] and data['entity_ids'] == []
    assert data['answer_protocol'] == 'evidence-claims-v3'
    assert data['claims'] == [dict(text=data['answer'],status='insufficient',citation_ids=[])]
    assert data['missing_information']


def test_question_requires_deepseek_only_after_evidence_is_found(
    client, configured, monkeypatch,
):
    project_id, settings = prepared_project(client, monkeypatch)
    settings.deepseek_api_key = None
    response = client.post(f'/api/v1/projects/{project_id}/questions', json={
        'question': 'Which database is used?',
    })
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'QUESTION_NOT_CONFIGURED'


def test_question_maps_provider_failures_and_validates_input(
    client, configured, monkeypatch,
):
    project_id, _ = prepared_project(client, monkeypatch)
    monkeypatch.setattr(
        deepseek, 'answer_question',
        lambda *_: (_ for _ in ()).throw(deepseek.QuestionError(
            'QUESTION_PROVIDER_FAILED', 'DeepSeek 暂时不可用，请稍后手动重试',
        )),
    )
    response = client.post(f'/api/v1/projects/{project_id}/questions', json={
        'question': 'Which database is used?',
    })
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'QUESTION_PROVIDER_FAILED'
    assert client.post(f'/api/v1/projects/{project_id}/questions', json={'question': '   '}).status_code == 422
    assert client.post(f'/api/v1/projects/{project_id}/questions', json={
        'question': 'x' * 201,
    }).status_code == 422
