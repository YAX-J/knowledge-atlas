"""OpenRouter protocol and evaluation integration, entirely provider-free."""
import json
import sys

import httpx
from pydantic import SecretStr, ValidationError
import pytest

from app.core.config import Settings
from app.llm.providers import cloudflare, evaluation, jev, openrouter
from scripts import jev_evaluation as runner


QUESTIONS = {'relation': dict(type='choice', instructions='Judge support', criteria=runner.RELATION)}
STATE = dict(claim='Uses a database.', passages=[dict(quote='Uses a database.', context='Uses a database.')])


def settings(**changes):
    values = dict(evaluation_provider='openrouter', openrouter_api_key=SecretStr('test-or-key'))
    values.update(changes)
    return Settings(_env_file=None, **values)


def response(questions=QUESTIONS, model='typesafe/jev-1.14-20261014'):
    answers = {}
    for name, question in questions.items():
        options = list(question['criteria'])
        choice = 'supported' if 'supported' in options else options[0]
        answers[name] = dict(type='choice', choice=choice, confidence=.9,
                             probabilities={key: float(key == choice) for key in options})
    return dict(model=model, provider='TypeSafe', answers=answers,
                usage=dict(input_tokens=50, output_tokens=0, cost=.0000021))


def mock_transport(monkeypatch, handler):
    original = httpx.Client
    def client(**kwargs):
        # Passing an explicit transport in production would disable env proxies.
        assert 'transport' not in kwargs and kwargs['trust_env'] is True
        assert kwargs['follow_redirects'] is False
        assert kwargs['timeout'].connect == 10
        return original(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(openrouter.httpx, 'Client', client)


@pytest.mark.parametrize('mode', [
    'success', 'same_release', 'cost_absent', 'cost_null', '401', '402', '403', '429', '502', 'redirect',
    'connect_timeout', 'read_timeout', 'write_timeout', 'network', 'oversized', 'invalid_json', 'duplicate_key',
    'error_envelope', 'root_array', 'missing_model', 'foreign_model', 'wrong_release', 'invalid_snapshot',
    'missing_answer', 'extra_answer', 'unknown_choice', 'extra_choice_field', 'bad_sum', 'nan',
    'negative_probability', 'missing_usage', 'usage_null', 'usage_bool', 'cost_negative', 'cost_nan', 'cost_bool',
])
def test_transport_exact_contract_sanitization_and_no_retry(monkeypatch, mode):
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url) == 'https://openrouter.ai/api/alpha/decisions'
        assert request.headers['authorization'] == 'Bearer test-or-key'
        assert json.loads(request.content) == dict(model='typesafe/jev-1.14', state=STATE, questions=QUESTIONS,
                                                  provider=dict(allow_fallbacks=False))
        if mode in {'connect_timeout', 'read_timeout', 'write_timeout', 'network'}:
            kind = {'connect_timeout': httpx.ConnectTimeout, 'read_timeout': httpx.ReadTimeout,
                    'write_timeout': httpx.WriteTimeout, 'network': httpx.ConnectError}[mode]
            raise kind('test-or-key private text', request=request)
        if mode in {'401', '402', '403', '429', '502', 'redirect'}:
            return httpx.Response(302 if mode == 'redirect' else int(mode),
                                  headers={'location': 'https://example.com/'}, text='test-or-key private text')
        if mode == 'oversized': return httpx.Response(200, content=b'x' * (128 * 1024 + 1))
        if mode == 'invalid_json': return httpx.Response(200, text='test-or-key private text')
        if mode == 'duplicate_key': return httpx.Response(200, text='{"model":"a","model":"b"}')
        value = response()
        answer = value['answers']['relation']
        if mode == 'same_release': value['model'] = 'typesafe/jev-1.14'
        if mode == 'cost_absent': value['usage'].pop('cost')
        if mode == 'cost_null': value['usage']['cost'] = None
        if mode == 'root_array': value = []
        if mode == 'error_envelope': value['error'] = {'code': 402, 'message': 'test-or-key private text'}
        if mode == 'missing_model': value.pop('model')
        if mode == 'foreign_model': value['model'] = 'other/jev-1.14'
        if mode == 'wrong_release': value['model'] = 'typesafe/jev-1.13-20260917'
        if mode == 'invalid_snapshot': value['model'] = 'typesafe/jev-1.14-20261340'
        if mode == 'missing_answer': value['answers'] = {}
        if mode == 'extra_answer': value['answers']['extra'] = answer
        if mode == 'unknown_choice': answer['choice'] = 'invented'
        if mode == 'extra_choice_field': answer['reason'] = 'private text'
        if mode == 'bad_sum': answer['probabilities'] = {key: .5 for key in runner.RELATION}
        if mode == 'nan': answer['confidence'] = float('nan')
        if mode == 'negative_probability': answer['probabilities']['supported'] = -1
        if mode == 'missing_usage': value.pop('usage')
        if mode == 'usage_null': value['usage'] = None
        if mode == 'usage_bool': value['usage']['input_tokens'] = True
        if mode == 'cost_negative': value['usage']['cost'] = -1
        if mode == 'cost_nan': value['usage']['cost'] = float('nan')
        if mode == 'cost_bool': value['usage']['cost'] = True
        return httpx.Response(200, content=json.dumps(value).encode())
    mock_transport(monkeypatch, handler)
    if mode in {'success', 'same_release', 'cost_absent', 'cost_null'}:
        value = openrouter.judge(settings(), STATE, QUESTIONS)
        assert value['answers']['relation']['choice'] == 'supported'
        assert value['requested_model'] == 'typesafe/jev-1.14'
        assert value['model'] == ('typesafe/jev-1.14' if mode == 'same_release' else 'typesafe/jev-1.14-20261014')
        assert value['usage']['cost'] == (None if mode in {'cost_absent', 'cost_null'} else .0000021)
    else:
        with pytest.raises(openrouter.OpenRouterError) as caught:
            openrouter.judge(settings(), STATE, QUESTIONS)
        assert 'test-or-key' not in str(caught.value) and 'private' not in str(caught.value)
        codes = {'401': 'OR_AUTH_FAILED', '403': 'OR_AUTH_FAILED', '402': 'OR_PAYMENT_REQUIRED',
                 '429': 'OR_RATE_LIMITED', 'connect_timeout': 'OR_CONNECT_TIMEOUT', 'read_timeout': 'OR_READ_TIMEOUT',
                 'write_timeout': 'OR_TIMEOUT', 'wrong_release': 'OR_MODEL_MISMATCH'}
        if mode in codes: assert str(caught.value) == codes[mode]
    assert len(calls) == 1


@pytest.mark.parametrize('model', [
    '~typesafe/jev-latest', 'typesafe/jev', 'typesafe/jev-1.14.0', '@cf/typesafe/jev-1.14.0',
    'typesafe/jev-1.14-20260230', 'other/model',
])
def test_wrong_provider_identifiers_and_aliases_fail_before_http(monkeypatch, model):
    def forbidden(**_kwargs): pytest.fail('Invalid model must not open transport')
    monkeypatch.setattr(openrouter.httpx, 'Client', forbidden)
    with pytest.raises(openrouter.OpenRouterError, match='VERSIONED_JEV_REQUIRED'):
        openrouter.judge(settings(openrouter_model=model), STATE, QUESTIONS)


@pytest.mark.parametrize('returned', ['typesafe/jev-1.14-20261014', 'typesafe/jev-1.14-20261015', 'typesafe/jev-1.14'])
def test_explicit_snapshot_requires_exact_response_identity(monkeypatch, returned):
    def handler(_request): return httpx.Response(200, json=response(model=returned))
    mock_transport(monkeypatch, handler)
    config = settings(openrouter_model='typesafe/jev-1.14-20261014')
    assert evaluation.identity(config)['model_revision_pinned'] is True
    if returned == config.openrouter_model:
        assert openrouter.judge(config, STATE, QUESTIONS)['model'] == returned
    else:
        with pytest.raises(openrouter.OpenRouterError, match='MODEL_MISMATCH'):
            openrouter.judge(config, STATE, QUESTIONS)


def packet(tmp_path):
    root = tmp_path / 'packet'
    root.mkdir()
    rows = [dict(review_id='review-0001', question='Storage?', answer='Uses a database.', supported=True,
                 reference_answer='Uses a database.', required_facts=['database'], answerable=True,
                 granularity='claim', units=[STATE])]
    runner.write(root / 'packet.json', rows)
    runner.write(root / 'packet-manifest.json', dict(protocol=jev.PROTOCOL, packet_sha256=runner.digest(rows)))
    return root


def test_preflight_missing_key_budget_and_packet_integrity_are_provider_free(tmp_path, monkeypatch):
    root = packet(tmp_path)
    def forbidden(*_args, **_kwargs): pytest.fail('No provider allowed')
    for provider in (openrouter, cloudflare, jev): monkeypatch.setattr(provider, 'judge', forbidden)
    config = settings(openrouter_api_key=None)
    value = runner.run(root, tmp_path / 'dry', settings=config)
    assert value['status'] == 'prepared' and value['planned_requests'] == 3
    assert value['evaluator'] == 'Jev via OpenRouter' and value['requested_model'] == 'typesafe/jev-1.14'
    assert value['judge_config']['model_revision_pinned'] is False
    assert value['reserved_requests'] == value['completed_requests'] == value['model_graded_reviews'] == 0
    assert value['human_grading_coverage'] == 0 and 'test-or-key' not in json.dumps(value)
    with pytest.raises(ValueError, match='OR_NOT_CONFIGURED'):
        runner.run(root, tmp_path / 'no-key', settings=config, allow_calls=True, max_requests=3)
    with pytest.raises(ValueError, match='BUDGET'):
        runner.run(root, tmp_path / 'no-budget', settings=settings(), allow_calls=True, max_requests=2)
    rows = json.loads((root / 'packet.json').read_text())
    rows[0]['answer'] = 'Changed'
    runner.write(root / 'packet.json', rows)
    with pytest.raises(ValueError, match='PACKET_CHANGED'):
        runner.run(root, tmp_path / 'changed', settings=settings())
    for name in ('no-key', 'no-budget', 'changed'): assert not (tmp_path / name).exists()


@pytest.mark.parametrize('mode', ['success', 'payment', 'drift', 'low_confidence', 'order_disagreement'])
def test_runner_reserves_before_transport_and_preserves_model_anonymity_and_outcomes(tmp_path, monkeypatch, mode):
    root = packet(tmp_path)
    calls = []
    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        saved = json.loads((tmp_path / 'graded' / 'run.json').read_text())
        assert saved['reserved_requests'] == len(calls)
        state, questions = payload['state'], payload['questions']
        assert not {'review_id', 'case_id', 'mode', 'confidence'} & set(state)
        if 'relation' in questions: assert not {'reference_answer', 'required_facts'} & set(state)
        if mode == 'payment': return httpx.Response(402, text='test-or-key private text')
        value = response(questions)
        if mode == 'drift' and len(calls) == 2: value['model'] = 'typesafe/jev-1.14-20261015'
        if mode == 'low_confidence' and 'relation' in questions: value['answers']['relation']['confidence'] = .7
        if mode == 'order_disagreement' and 'relation' in questions and list(questions['relation']['criteria'])[0] == 'insufficient':
            answer = value['answers']['relation']
            answer.update(choice='insufficient', probabilities={key: float(key == 'insufficient') for key in runner.RELATION})
        return httpx.Response(200, json=value)
    mock_transport(monkeypatch, handler)
    def forbidden(*_args): pytest.fail('No fallback to CF or TypeSafe')
    monkeypatch.setattr(cloudflare, 'judge', forbidden)
    monkeypatch.setattr(jev, 'judge', forbidden)
    if mode in {'payment', 'drift'}:
        with pytest.raises(openrouter.OpenRouterError, match='PAYMENT_REQUIRED' if mode == 'payment' else 'MODEL_CHANGED_DURING_RUN'):
            runner.run(root, tmp_path / 'graded', settings=settings(), allow_calls=True, max_requests=3)
        value = json.loads((tmp_path / 'graded' / 'run.json').read_text())
        assert value['status'] == 'failed' and value['model_graded_reviews'] == 0
        assert value['reserved_requests'] == len(calls) == (1 if mode == 'payment' else 2)
        assert value['completed_requests'] == (0 if mode == 'payment' else 2)
        assert len(value['results']) == value['completed_requests']
    else:
        value = runner.run(root, tmp_path / 'graded', settings=settings(), allow_calls=True, max_requests=3)
        assert value['status'] == 'succeeded' and value['model_graded_reviews'] == 1
        assert value['resolved_model'] == 'typesafe/jev-1.14-20261014'
        assert value['completed_requests'] == value['reserved_requests'] == len(calls) == 3
        assert value['reviews'][0]['uncertain_units'] == ([] if mode == 'success' else [0])
        assert list(calls[1]['questions']['relation']['criteria']) == list(reversed(calls[2]['questions']['relation']['criteria']))
    assert value['human_grading_coverage'] == 0 and 'test-or-key' not in json.dumps(value)
    assert 'private text' not in json.dumps(value)
    assert value['judge_config_sha256'] == runner.digest(value['judge_config'])
    with pytest.raises(FileExistsError):
        runner.run(root, tmp_path / 'graded', settings=settings(), allow_calls=True, max_requests=3)


def test_payload_limits_secret_normalization_and_direct_missing_key(monkeypatch):
    def forbidden(**_kwargs): pytest.fail('No HTTP client allowed')
    monkeypatch.setattr(openrouter.httpx, 'Client', forbidden)
    config = settings(openrouter_api_key='  ')
    assert config.openrouter_api_key is None and not evaluation.configured(config)
    with pytest.raises(openrouter.OpenRouterError, match='NOT_CONFIGURED'):
        openrouter.judge(config, STATE, QUESTIONS)
    with pytest.raises(openrouter.OpenRouterError, match='INPUT_TOO_LARGE'):
        openrouter.request_payload(settings(), {'text': '中' * 9000}, QUESTIONS)
    for questions in ({}, {'bad/id': QUESTIONS['relation']}, {'x': dict(type='score', criteria=['a'])}):
        with pytest.raises(openrouter.OpenRouterError, match='QUESTIONS_INVALID'):
            openrouter.request_payload(settings(), STATE, questions)
    assert evaluation.adapter(settings()) is openrouter
    with pytest.raises(ValidationError): settings(evaluation_provider='unknown')


def test_cli_explicit_provider_preflight_and_generic_call_authorization(tmp_path, monkeypatch, capsys):
    root = packet(tmp_path)
    monkeypatch.setattr(runner, 'get_settings', lambda: settings())
    arguments = ['judge_evaluation', 'run', '--provider', 'openrouter', '--packet', str(root)]
    monkeypatch.setattr(sys, 'argv', arguments + ['--output', str(tmp_path / 'forbidden'), '--allow-jev-calls'])
    with pytest.raises(SystemExit): runner.main()
    assert 'only authorizes Jev' in capsys.readouterr().err
    assert not (tmp_path / 'forbidden').exists()
    monkeypatch.setattr(sys, 'argv', arguments + ['--output', str(tmp_path / 'dry')])
    runner.main()
    assert json.loads(capsys.readouterr().out)['reserved_requests'] == 0
    calls = []
    def handler(_request):
        calls.append(1)
        return httpx.Response(402, text='test-or-key private text')
    mock_transport(monkeypatch, handler)
    monkeypatch.setattr(sys, 'argv', arguments + ['--output', str(tmp_path / 'failed'), '--allow-judge-calls', '--max-requests', '3'])
    with pytest.raises(SystemExit, match='OR_PAYMENT_REQUIRED'): runner.main()
    assert len(calls) == 1
