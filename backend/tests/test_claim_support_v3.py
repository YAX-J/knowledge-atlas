"""Provider-free regression with fictional development data, independent of frozen evals."""
from copy import deepcopy
import json
from pathlib import Path
import uuid

import httpx
import pytest
from pydantic import ValidationError

from app.agents.evidence_qa.agent import EvidenceQAAgent
from app.core.errors import AppError
from app.llm.prompts import ANSWER_PROMPT_VERSION, ANSWER_SYSTEM_PROMPT
from app.schemas.questions import ClaimAnswerDraft, ClaimAnswerDraftV2, QuestionEvidenceRead, RetrievalSummary
from app.services import deepseek
from app.services.questions import validated_answer
from app.tools.evidence import EvidenceTools
from tests.test_knowledge import configured


DATA = json.loads((Path(__file__).resolve().parents[2] /
    'evaluation/development/claim-support-v3/cases.json').read_text(encoding='utf-8'))
CASES = DATA['cases']


def evidence():
    return {uuid.UUID(item['id']): QuestionEvidenceRead(**item,
        source_id=uuid.UUID(int=10), chunk_id=uuid.UUID(int=11), entity_id=uuid.UUID(int=12),
        entity_name='Fictional Nimbus', title='Synthetic ledger note', uri='synthetic:nimbus',
        start_line=index + 1, end_line=index + 1, heading_path=[])
        for index, item in enumerate(DATA['evidence'])}


def result(draft):
    return validated_answer('Synthetic question', evidence(),
        RetrievalSummary(keyword_hits=1, vector_hits=0, graph_hits=0, indexed_count=0, eligible_count=1), draft)


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_development_cases_derive_api_state_and_keep_claim_mapping(case):
    draft = ClaimAnswerDraft.model_validate(case['draft'])
    answer = result(draft)
    assert answer.supported is case['expected_supported']
    assert answer.answer_protocol == 'evidence-claims-v3'
    assert answer.claims == draft.claims
    assert answer.answer == '\n\n'.join(claim.text for claim in draft.claims)
    assert [item.id for item in answer.evidence] == draft.citation_ids
    assert answer.missing_information == case['draft']['missing_information']
    assert set(draft.model_dump()) == {'confidence', 'claims', 'missing_information'}


def test_wire_schema_and_prompt_exclude_aggregate_support():
    schema = ClaimAnswerDraft.model_json_schema()
    assert ANSWER_PROMPT_VERSION == 'evidence-claims-v3'
    assert set(schema['properties']) == set(schema['required']) == {'confidence', 'claims', 'missing_information'}
    assert schema['additionalProperties'] is False
    prompt_schema = json.loads(ANSWER_SYSTEM_PROMPT.split('JSON Schema:\n')[1])
    assert prompt_schema == schema


@pytest.mark.parametrize('supported', [True, False])
def test_redundant_provider_aggregate_is_rejected_even_if_consistent(supported):
    with pytest.raises(ValidationError) as exc:
        ClaimAnswerDraft.model_validate({**CASES[0]['draft'], 'supported': supported})
    assert exc.value.errors(include_input=False)[0]['type'] == 'extra_forbidden'


@pytest.mark.parametrize('mutation', ['missing-cite', 'insufficient-cited', 'missing-reason', 'duplicate-cite',
    'unknown-status', 'extra-field', 'too-many-claims', 'too-long', 'text-budget', 'citation-budget'])
def test_synthetic_invalid_claims_remain_strict(mutation):
    value = deepcopy(CASES[1]['draft'])
    claim = value['claims'][0]
    if mutation == 'missing-cite': claim['citation_ids'] = []
    if mutation == 'insufficient-cited': claim['status'] = 'insufficient'
    if mutation == 'missing-reason': value['missing_information'] = []
    if mutation == 'duplicate-cite': claim['citation_ids'] *= 2
    if mutation == 'unknown-status': claim['status'] = 'maybe'
    if mutation == 'extra-field': claim['explanation'] = 'Unbound text'
    if mutation == 'too-many-claims': value['claims'] = [claim] * 9
    if mutation == 'too-long': claim['text'] = 'x' * 501
    if mutation == 'text-budget':
        claim['text'] = 'x' * 500
        value['claims'] = [claim] * 8  # Joining separators also count toward 4000.
    if mutation == 'citation-budget':
        value['claims'] = [dict(text='Synthetic fact', status='supported', citation_ids=[str(uuid.UUID(int=i))])
            for i in range(1, 7)]
    with pytest.raises(ValidationError): ClaimAnswerDraft.model_validate(value)


def test_unknown_citations_are_rejected_after_schema_validation():
    value = deepcopy(CASES[0]['draft'])
    value['claims'][0]['citation_ids'] = [str(uuid.UUID(int=99))]
    with pytest.raises(AppError) as exc: result(ClaimAnswerDraft.model_validate(value))
    assert exc.value.code == 'QUESTION_EVIDENCE_INVALID'


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_v2_diagnostic_adapter_retains_original_protocol(case):
    old = ClaimAnswerDraftV2.model_validate({**case['draft'], 'supported': case['expected_supported']})
    assert result(old).answer_protocol == 'evidence-claims-v2'
    with pytest.raises(ValidationError):
        ClaimAnswerDraftV2.model_validate({**case['draft'], 'supported': not case['expected_supported']})


@pytest.mark.parametrize('strategy', ['single_step', 'tools'])
@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_both_provider_paths_accept_v3_without_aggregate(strategy, case, configured, monkeypatch):
    assert run_provider(strategy, case['draft'], configured, monkeypatch).supported is case['expected_supported']


@pytest.mark.parametrize('strategy', ['single_step', 'tools'])
def test_both_provider_paths_reject_v2_without_retry(strategy, configured, monkeypatch):
    with pytest.raises(deepseek.QuestionError) as exc:
        run_provider(strategy, {**CASES[0]['draft'], 'supported': True}, configured, monkeypatch)
    assert exc.value.code == ('QUESTION_OUTPUT_INVALID' if strategy == 'single_step' else 'CALL_AGENT_OUTPUT_INVALID')


def run_provider(strategy, value, settings, monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': json.dumps(value)}}]})
    original = httpx.Client
    monkeypatch.setattr(deepseek.httpx, 'Client', lambda **kwargs:
        original(transport=httpx.MockTransport(handler), **kwargs))
    try:
        return EvidenceQAAgent().run(strategy, dict(settings=settings, question='Synthetic Nimbus?',
            evidence=DATA['evidence'], conversation=[], tools=EvidenceTools(lambda *_: {}, evidence())))
    finally:
        assert len(calls) == 1  # Includes strict rejection: no retry or fallback.
