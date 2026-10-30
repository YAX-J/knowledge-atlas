"""Offline typed judge transport; bounded input/output, no retries or generated rationales."""
import json
import re

import httpx
from pydantic import ValidationError

from app.llm.providers.judging import Choice, JudgeError, validate_choices


PROTOCOL = 'jev-anonymous-claims-v1'


class JevError(JudgeError):
    pass


def request_payload(settings, state, questions):
    if not re.fullmatch(r'jev-\d+\.\d+\.\d+', settings.typesafe_model):
        raise JevError('JEV_PINNED_MODEL_REQUIRED')
    payload=dict(model=settings.typesafe_model,state=state,questions=questions)
    if len(json.dumps(payload,ensure_ascii=False).encode())>24000:
        raise JevError('JEV_INPUT_TOO_LARGE')
    return payload


def judge(settings, state, questions):
    if not settings.typesafe_api_key or not settings.typesafe_api_key.get_secret_value().strip():
        raise JevError('JEV_NOT_CONFIGURED')
    payload=request_payload(settings,state,questions)
    try:
        with httpx.Client(timeout=settings.typesafe_timeout_seconds,follow_redirects=False) as client:
            with client.stream('POST',settings.typesafe_base_url.rstrip('/')+'/v1/systemone',
                headers={'Authorization':'Bearer '+settings.typesafe_api_key.get_secret_value()},json=payload) as response:
                if response.status_code!=200:raise JevError('JEV_PROVIDER_FAILED')
                raw=bytearray()
                for part in response.iter_bytes(chunk_size=16384):
                    raw.extend(part)
                    if len(raw)>128*1024:raise JevError('JEV_OUTPUT_TOO_LARGE')
        data=json.loads(raw)
        if data['model']!=settings.typesafe_model or set(data['answers'])!=set(questions):
            raise JevError('JEV_OUTPUT_INVALID')
        answers=validate_choices(data['answers'],questions)
        usage=data.get('usage',{})
        if not isinstance(usage,dict) or any(type(usage.get(key)) is not int or usage[key]<0 for key in ('input_tokens','output_tokens')):
            raise JevError('JEV_OUTPUT_INVALID')
        return dict(model=data['model'],answers=answers,usage={key:usage[key] for key in ('input_tokens','output_tokens')})
    except httpx.HTTPError as exc:raise JevError('JEV_PROVIDER_FAILED') from exc
    except (KeyError,TypeError,ValueError,ValidationError) as exc:raise JevError('JEV_OUTPUT_INVALID') from exc
