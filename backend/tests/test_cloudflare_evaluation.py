"""Offline CF protocol tests; every HTTP request is handled by MockTransport."""
import json
import sys

import httpx
from pydantic import SecretStr, ValidationError
import pytest

from app.core.config import Settings
from app.llm.providers import cloudflare, evaluation
from scripts import jev_evaluation as runner


QUESTIONS = {'relation': dict(type='choice', instructions='Judge support', criteria=runner.RELATION)}
STATE = dict(claim='Uses a database.', passages=[dict(quote='Uses a database.', context='Uses a database.')])


def settings(**changes):
    values = dict(evaluation_provider='cloudflare', cloudflare_account_id='a' * 32,
                  cloudflare_api_token=SecretStr('test-cf-token'))
    values.update(changes)
    return Settings(_env_file=None, **values)


def result(questions=QUESTIONS):
    return dict(model='clef-flash', answers={name: dict(
        type='choice', choice='supported' if 'supported' in question['criteria'] else list(question['criteria'])[0], confidence=.9,
        probabilities={key: float(key == ('supported' if 'supported' in question['criteria'] else list(question['criteria'])[0]))
                       for key in question['criteria']}
    ) for name, question in questions.items()}, usage=dict(input_tokens=50, output_tokens=0))


def envelope(value):
    return dict(success=True, result=value, errors=[], messages=[])


def mock_transport(monkeypatch, handler):
    original = httpx.Client
    def client(**kwargs):
        assert kwargs['follow_redirects'] is False
        return original(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(cloudflare.httpx, 'Client', client)


@pytest.mark.parametrize('mode', [
    'success', 'full_model', 'missing_usage', 'null_usage', 'chat_usage', '401', '429', 'redirect', 'timeout',
    'oversized', 'failure_envelope', 'errors', 'missing_result', 'result_list', 'malformed', 'foreign_model',
    'missing_model', 'missing_answer', 'extra_answer', 'bad_choice', 'bad_sum', 'nan', 'bad_usage', 'usage_list',
    'finish_length', 'duplicate_json',
])
def test_cf_decision_native_rest_bounded_validation_and_no_retry(monkeypatch, mode):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers['Authorization'] == 'Bearer test-cf-token'
        assert str(request.url) == f'https://api.cloudflare.com/client/v4/accounts/{"a" * 32}/ai/run/@cf/cloudflare/clef-flash'
        payload = json.loads(request.content)
        assert payload == dict(model='clef-flash', state=STATE, questions=QUESTIONS)
        if mode == 'timeout':
            raise httpx.ReadTimeout('test-cf-token private text', request=request)
        if mode in {'401', '429', 'redirect'}:
            return httpx.Response({'401': 401, '429': 429, 'redirect': 302}[mode],
                                  headers={'location': 'https://example.com'}, text='test-cf-token private text')
        if mode == 'oversized':
            return httpx.Response(200, content=b'x' * (128 * 1024 + 1))
        if mode == 'malformed':
            return httpx.Response(200, text='not JSON test-cf-token private text')
        if mode == 'duplicate_json':
            return httpx.Response(200, text='{"success":true,"success":false}')
        value = result()
        answer = value['answers']['relation']
        if mode == 'full_model': value['model'] = '@cf/cloudflare/clef-flash'
        if mode == 'missing_usage': value.pop('usage')
        if mode == 'null_usage': value['usage'] = None
        if mode == 'chat_usage': value['usage'] = dict(prompt_tokens=50, completion_tokens=0)
        if mode == 'foreign_model': value['model'] = 'other-model'
        if mode == 'missing_model': value.pop('model')
        if mode == 'missing_answer': value['answers'] = {}
        if mode == 'extra_answer': value['answers']['extra'] = answer
        if mode == 'bad_choice': answer['choice'] = 'invented'
        if mode == 'bad_sum': answer['probabilities'] = {key: .5 for key in runner.RELATION}
        if mode == 'nan': answer['confidence'] = float('nan')
        if mode == 'bad_usage': value['usage']['input_tokens'] = True
        if mode == 'usage_list': value['usage'] = []
        if mode == 'finish_length': value['finish_reason'] = 'length'
        data = envelope(value)
        if mode == 'failure_envelope': data['success'] = False
        if mode == 'errors': data['errors'] = [{'message': 'test-cf-token private text'}]
        if mode == 'missing_result': data.pop('result')
        if mode == 'result_list': data['result'] = []
        return httpx.Response(200, content=json.dumps(data).encode())
    mock_transport(monkeypatch, handler)
    if mode in {'success', 'full_model', 'missing_usage', 'null_usage', 'chat_usage'}:
        value = cloudflare.judge(settings(), STATE, QUESTIONS)
        assert value['model'] == '@cf/cloudflare/clef-flash'
        assert value['answers']['relation']['confidence'] == .9
        assert value['usage'] == (None if mode in {'missing_usage', 'null_usage'} else dict(input_tokens=50, output_tokens=0))
    else:
        with pytest.raises(cloudflare.CloudflareError) as caught:
            cloudflare.judge(settings(), STATE, QUESTIONS)
        assert 'test-cf-token' not in str(caught.value) and 'private' not in str(caught.value)
    assert len(calls) == 1


@pytest.mark.parametrize('mode', ['string', 'object', 'unknown', 'missing', 'extra', 'confidence', 'markdown', 'duplicate'])
def test_cf_chat_uses_json_schema_and_preserves_missing_probabilities(monkeypatch, mode):
    config = settings(cloudflare_judge_mode='chat', cloudflare_model='@cf/qwen/qwen3-30b-a3b-fp8')
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path.endswith('/ai/run/@cf/qwen/qwen3-30b-a3b-fp8')
        payload = json.loads(request.content)
        assert 'model' not in payload and 'state' not in payload and 'thinking' not in payload
        assert payload['stream'] is False and payload['temperature'] == 0 and payload['max_tokens'] == 2048
        assert json.loads(payload['messages'][1]['content']) == dict(state=STATE, questions=QUESTIONS)
        schema = payload['response_format']['json_schema']['properties']['answers']
        assert schema['required'] == ['relation']
        assert schema['properties']['relation']['properties']['choice']['enum'] == list(runner.RELATION)
        answer = dict(answers=dict(relation=dict(choice='supported')))
        if mode == 'unknown': answer['answers']['relation']['choice'] = 'invented'
        if mode == 'missing': answer['answers'] = {}
        if mode == 'extra': answer['reasoning'] = 'private text'
        if mode == 'confidence': answer['answers']['relation']['confidence'] = .99
        content = answer if mode == 'object' else json.dumps(answer)
        if mode == 'markdown': content = '```json\n' + content + '\n```'
        if mode == 'duplicate': content = '{"answers":{"relation":{"choice":"supported","choice":"insufficient"}}}'
        return httpx.Response(200, json=envelope(dict(response=content, usage=dict(prompt_tokens=70, completion_tokens=12))))
    mock_transport(monkeypatch, handler)
    if mode in {'string', 'object'}:
        value = cloudflare.judge(config, STATE, QUESTIONS)
        assert value['reported_model'] is None
        assert value['usage'] == dict(input_tokens=70, output_tokens=12)
        assert value['answers']['relation'] == dict(type='choice', choice='supported', confidence=None, probabilities=None)
    else:
        with pytest.raises(cloudflare.CloudflareError, match='OUTPUT_INVALID'):
            cloudflare.judge(config, STATE, QUESTIONS)
    assert len(calls) == 1


@pytest.mark.parametrize('changes,code', [
    ({'cloudflare_account_id': 'account/secret'}, 'ACCOUNT_INVALID'),
    ({'cloudflare_model': '../model'}, 'MODEL_INVALID'),
    ({'cloudflare_model': '@cf/qwen/qwen3-30b-a3b-fp8'}, 'DECISION_MODEL_REQUIRED'),
    ({'cloudflare_judge_mode': 'chat'}, 'CHAT_MODEL_REQUIRED'),
    ({'cloudflare_account_id': ''}, 'NOT_CONFIGURED'),
    ({'cloudflare_api_token': None}, 'NOT_CONFIGURED'),
    ({'cloudflare_api_token': SecretStr('   ')}, 'NOT_CONFIGURED'),
])
def test_cf_invalid_config_fails_before_transport(monkeypatch, changes, code):
    def forbidden(**_kwargs): pytest.fail('Invalid config must not open a client')
    monkeypatch.setattr(cloudflare.httpx, 'Client', forbidden)
    with pytest.raises(cloudflare.CloudflareError, match=code):
        cloudflare.judge(settings(**changes), STATE, QUESTIONS)


@pytest.mark.parametrize('mode', ['decision', 'chat'])
def test_cf_input_budget_counts_final_wire_payload(mode):
    config = settings(cloudflare_judge_mode=mode, **(
        {'cloudflare_model': '@cf/qwen/qwen3-30b-a3b-fp8'} if mode == 'chat' else {}))
    with pytest.raises(cloudflare.CloudflareError, match='INPUT_TOO_LARGE'):
        cloudflare.request_payload(config, {'text': '中' * 9000}, QUESTIONS)
    for questions in ({}, {'bad/id': QUESTIONS['relation']}, {'x': dict(type='score', criteria=['a'])}):
        with pytest.raises(cloudflare.CloudflareError, match='QUESTIONS_INVALID'):
            cloudflare.request_payload(config, STATE, questions)


def packet(tmp_path):
    root = tmp_path / 'packet'
    root.mkdir()
    rows = [dict(review_id='review-0001', question='Storage?', answer='Uses a database.', supported=True,
                 reference_answer='Uses a database.', required_facts=['database'], answerable=True,
                 granularity='claim', units=[STATE])]
    runner.write(root / 'packet.json', rows)
    runner.write(root / 'packet-manifest.json', dict(protocol=runner.jev.PROTOCOL, packet_sha256=runner.digest(rows)))
    return root


def test_cf_dry_run_reports_selected_provider_without_credentials_or_calls(tmp_path, monkeypatch):
    root = packet(tmp_path)
    def forbidden(*_args, **_kwargs): pytest.fail('Preflight must not call any provider')
    monkeypatch.setattr(cloudflare, 'judge', forbidden)
    monkeypatch.setattr(runner.jev, 'judge', forbidden)
    value = runner.run(root, tmp_path / 'dry', settings=settings(cloudflare_account_id='', cloudflare_api_token=None))
    assert value['status'] == 'prepared' and value['planned_requests'] == 3
    assert value['reserved_requests'] == value['completed_requests'] == value['model_graded_reviews'] == 0
    assert value['human_grading_coverage'] == 0 and value['evaluator'] == 'Cloudflare Workers AI'
    assert value['judge_config']['model_revision_pinned'] is False
    assert 'account' not in json.dumps(value['judge_config']) and 'token' not in json.dumps(value['judge_config'])
    with pytest.raises(ValueError, match='NOT_CONFIGURED'):
        runner.run(root, tmp_path / 'no-auth', allow_calls=True, max_requests=3,
                   settings=settings(cloudflare_api_token=None))
    with pytest.raises(ValueError, match='BUDGET'):
        runner.run(root, tmp_path / 'no-budget', allow_calls=True, max_requests=2, settings=settings())
    assert not (tmp_path / 'no-auth').exists() and not (tmp_path / 'no-budget').exists()


@pytest.mark.parametrize('mode', ['decision', 'chat'])
def test_cf_runner_dispatch_reservation_anonymity_order_and_config(tmp_path, monkeypatch, mode):
    root = packet(tmp_path)
    config = settings(cloudflare_judge_mode=mode, **(
        {'cloudflare_model': '@cf/qwen/qwen3-30b-a3b-fp8'} if mode == 'chat' else {}))
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        saved = json.loads((tmp_path / 'graded' / 'run.json').read_text())
        assert saved['reserved_requests'] == len(calls)
        value = calls[-1]
        if mode == 'chat': value = json.loads(value['messages'][1]['content'])
        assert 'review_id' not in value['state'] and 'model' not in value['state']
        questions = value['questions']
        if 'relation' in questions:
            assert 'reference_answer' not in value['state'] and 'required_facts' not in value['state']
        answer = result(questions)
        if mode == 'chat':
            answer = dict(response=json.dumps(dict(answers={name: dict(choice=item['choice']) for name, item in answer['answers'].items()})))
        return httpx.Response(200, json=envelope(answer))
    mock_transport(monkeypatch, handler)
    value = runner.run(root, tmp_path / 'graded', settings=config, allow_calls=True, max_requests=3)
    assert value['status'] == 'succeeded' and value['completed_requests'] == 3 and value['model_graded_reviews'] == 1
    assert value['judge_config_sha256'] == runner.digest(value['judge_config'])
    assert value['reviews'][0]['uncertain_units'] == ([0] if mode == 'chat' else [])
    assert value['judge_config']['confidence_source'] == ('unavailable' if mode == 'chat' else 'provider_reported')
    states = calls if mode == 'decision' else [json.loads(item['messages'][1]['content']) for item in calls]
    assert list(states[1]['questions']['relation']['criteria']) == list(reversed(states[2]['questions']['relation']['criteria']))
    with pytest.raises(FileExistsError):
        runner.run(root, tmp_path / 'graded', settings=config, allow_calls=True, max_requests=3)
    assert len(calls) == 3


def test_cf_failure_persists_attempt_without_retry_or_provider_fallback(tmp_path, monkeypatch):
    root = packet(tmp_path)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, text='test-cf-token private text')
    mock_transport(monkeypatch, handler)
    def forbidden(*_args): pytest.fail('No provider fallback')
    monkeypatch.setattr(runner.jev, 'judge', forbidden)
    with pytest.raises(cloudflare.CloudflareError, match='CF_PROVIDER_FAILED'):
        runner.run(root, tmp_path / 'failed', settings=settings(), allow_calls=True, max_requests=3)
    value = json.loads((tmp_path / 'failed' / 'run.json').read_text())
    assert value['status'] == 'failed' and value['reserved_requests'] == len(calls) == 1
    assert value['completed_requests'] == value['model_graded_reviews'] == 0
    assert value['error_code'] == 'CF_PROVIDER_FAILED'
    assert 'test-cf-token' not in json.dumps(value) and 'private text' not in json.dumps(value)


@pytest.mark.parametrize('uncertainty', ['low_confidence', 'order_disagreement'])
def test_cf_uncertainty_keeps_both_original_judgments(tmp_path, monkeypatch, uncertainty):
    root = packet(tmp_path)
    def handler(request):
        questions = json.loads(request.content)['questions']
        value = result(questions)
        if 'relation' in questions:
            answer = value['answers']['relation']
            if uncertainty == 'low_confidence': answer['confidence'] = .7
            elif list(questions['relation']['criteria'])[0] == 'insufficient':
                answer['choice'] = 'insufficient'
                answer['probabilities'] = {key: float(key == 'insufficient') for key in runner.RELATION}
        return httpx.Response(200, json=envelope(value))
    mock_transport(monkeypatch, handler)
    value = runner.run(root, tmp_path / 'graded', settings=settings(), allow_calls=True, max_requests=3)
    assert value['reviews'][0]['uncertain_units'] == [0] and len(value['results']) == 3
    assert value['human_grading_coverage'] == 0


def test_cf_cli_requires_provider_specific_authorization(tmp_path, monkeypatch, capsys):
    root = packet(tmp_path)
    monkeypatch.setattr(runner, 'get_settings', lambda: settings())
    monkeypatch.setattr(sys, 'argv', ['judge_evaluation', 'run', '--packet', str(root), '--output', str(tmp_path / 'bad'), '--allow-jev-calls'])
    with pytest.raises(SystemExit): runner.main()
    assert 'only authorizes Jev' in capsys.readouterr().err
    assert not (tmp_path / 'bad').exists()
    monkeypatch.setattr(sys, 'argv', ['judge_evaluation', 'run', '--provider', 'cloudflare', '--packet', str(root), '--output', str(tmp_path / 'dry')])
    runner.main()
    assert json.loads(capsys.readouterr().out)['reserved_requests'] == 0


def test_cf_settings_normalize_secrets_and_reject_unknown_modes():
    config = settings(cloudflare_api_token='  ')
    assert config.cloudflare_api_token is None
    assert evaluation.adapter(Settings(_env_file=None)) is runner.jev
    with pytest.raises(ValidationError): settings(cloudflare_judge_mode='automatic')
    with pytest.raises(ValidationError): settings(evaluation_provider='unknown')
