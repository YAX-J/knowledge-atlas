"""Explicit provider selection for offline evaluation only."""
from app.llm.providers import cloudflare, jev


def adapter(settings):
    return cloudflare if settings.evaluation_provider == 'cloudflare' else jev


def identity(settings):
    if settings.evaluation_provider == 'jev':
        return dict(provider='jev', evaluator='Jev', model=settings.typesafe_model,
                    protocol=jev.PROTOCOL, mode='decision', confidence_source='provider_reported',
                    model_revision_pinned=True)
    mode = settings.cloudflare_judge_mode
    return dict(provider='cloudflare', evaluator='Cloudflare Workers AI', model=settings.cloudflare_model,
                protocol=f'cf-{mode}-anonymous-claims-v1', mode=mode,
                confidence_source='unavailable' if mode == 'chat' else 'provider_reported',
                model_revision_pinned=False,
                **(dict(temperature=0, max_tokens=settings.cloudflare_max_tokens) if mode == 'chat' else {}))


def configured(settings):
    if settings.evaluation_provider == 'jev':
        return bool(settings.typesafe_api_key and settings.typesafe_api_key.get_secret_value().strip())
    return bool(settings.cloudflare_account_id and settings.cloudflare_api_token
                and settings.cloudflare_api_token.get_secret_value().strip())
