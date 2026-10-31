"""Pytest transport barrier for the explicit M5 engineering acceptance command."""
import os
import httpx
import pytest

@pytest.fixture(autouse=True)
def block_provider_transports(monkeypatch):
    def blocked(*_args,**_kwargs):raise AssertionError('M5 offline acceptance forbids real HTTP transports')
    async def blocked_async(*_args,**_kwargs):raise AssertionError('M5 offline acceptance forbids real HTTP transports')
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport,'handle_async_request',blocked_async)
    if os.environ.get('KA_GITHUB_ACCEPTANCE'):raise AssertionError('Real GitHub acceptance is outside M5 offline scope')
