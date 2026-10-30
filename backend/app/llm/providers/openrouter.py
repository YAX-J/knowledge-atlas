"""OpenRouter Jev Decisions API; bounded, proxy-aware and without retries."""
from datetime import datetime
import json
import math
import re

import httpx

from app.llm.providers.judging import JudgeError, validate_choices


ENDPOINT = 'https://openrouter.ai/api/alpha/decisions'
PROTOCOL = 'or-jev-anonymous-claims-v1'
MODEL_PATTERN = r'(typesafe/jev-\d+\.\d+)(?:-(\d{8}))?'


class OpenRouterError(JudgeError):
    pass


def model_parts(model):
    match = re.fullmatch(MODEL_PATTERN, model)
    if not match:
        raise OpenRouterError('OR_VERSIONED_JEV_REQUIRED')
    if match[2]:
        try:
            datetime.strptime(match[2], '%Y%m%d')
        except ValueError as exc:
            raise OpenRouterError('OR_VERSIONED_JEV_REQUIRED') from exc
    return match[1], match[2]


def request_payload(settings, state, questions):
    model_parts(settings.openrouter_model)
    if not isinstance(questions, dict) or not questions or any(
        not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', name)
        or question.get('type') != 'choice'
        or not isinstance(question.get('criteria'), dict) or not question['criteria']
        for name, question in questions.items()
    ):
        raise OpenRouterError('OR_QUESTIONS_INVALID')
    payload = dict(model=settings.openrouter_model, state=state, questions=questions,
                   provider=dict(allow_fallbacks=False))
    if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()) > 24000:
        raise OpenRouterError('OR_INPUT_TOO_LARGE')
    return payload


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _usage(value):
    if not isinstance(value, dict) or any(
        type(value.get(key)) is not int or value[key] < 0 for key in ('input_tokens', 'output_tokens')
    ):
        raise ValueError('Invalid usage')
    usage = {key: value[key] for key in ('input_tokens', 'output_tokens')}
    cost = value.get('cost')
    if cost is not None and (type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0):
        raise ValueError('Invalid cost')
    usage['cost'] = cost  # Provider-reported USD; missing cost stays null.
    return usage


def _check_model(requested, returned):
    release, snapshot = model_parts(requested)
    actual_release, _actual_snapshot = model_parts(returned)
    if actual_release != release or (snapshot and returned != requested):
        raise OpenRouterError('OR_MODEL_MISMATCH')


def judge(settings, state, questions):
    payload = request_payload(settings, state, questions)
    if not settings.openrouter_api_key or not settings.openrouter_api_key.get_secret_value().strip():
        raise OpenRouterError('OR_NOT_CONFIGURED')
    try:
        # Leaving transport unset preserves HTTPX environment/system proxy discovery.
        # HTTPX's default transport has zero retries.
        with httpx.Client(timeout=httpx.Timeout(settings.openrouter_timeout_seconds, connect=10),
                          follow_redirects=False, trust_env=True) as client:
            with client.stream('POST', ENDPOINT,
                               headers={'Authorization': 'Bearer ' + settings.openrouter_api_key.get_secret_value()},
                               json=payload) as response:
                if response.status_code != 200:
                    code = {401: 'OR_AUTH_FAILED', 403: 'OR_AUTH_FAILED', 402: 'OR_PAYMENT_REQUIRED',
                            429: 'OR_RATE_LIMITED'}.get(response.status_code, 'OR_PROVIDER_FAILED')
                    raise OpenRouterError(code)
                raw = bytearray()
                for part in response.iter_bytes(chunk_size=16384):
                    raw.extend(part)
                    if len(raw) > 128 * 1024:
                        raise OpenRouterError('OR_OUTPUT_TOO_LARGE')
        data = json.loads(raw, object_pairs_hook=_unique_object)
        if not isinstance(data, dict) or data.get('error') is not None:
            raise OpenRouterError('OR_PROVIDER_FAILED')
        _check_model(settings.openrouter_model, data['model'])
        answers = validate_choices(data['answers'], questions)
        return dict(model=data['model'], requested_model=settings.openrouter_model,
                    answers=answers, usage=_usage(data.get('usage')))
    except httpx.TimeoutException as exc:
        code = 'OR_CONNECT_TIMEOUT' if isinstance(exc, httpx.ConnectTimeout) else 'OR_READ_TIMEOUT' if isinstance(exc, httpx.ReadTimeout) else 'OR_TIMEOUT'
        raise OpenRouterError(code) from exc
    except httpx.HTTPError as exc:
        raise OpenRouterError('OR_PROVIDER_FAILED') from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise OpenRouterError('OR_OUTPUT_INVALID') from exc
