"""Tests for Phase 53's OAuth2 client-credentials token acquisition/caching
(common/clients/auth_client/oauth_client.py). httpx is faked - no real
network call, matching every other client test in this project."""

import httpx

from src.hrb_chatbot.common.clients.auth_client import oauth_client


class FakeResponse:
    def __init__(self, body: dict):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


class FakeAsyncClient:
    def __init__(self, calls, body):
        self._calls = calls
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, json):
        self._calls.append((url, json))
        return FakeResponse(self._body)


def _reset_cache():
    oauth_client._cached_token = None
    oauth_client._cached_token_expires_at = 0.0


async def test_fetches_a_new_token_when_none_cached(monkeypatch):
    _reset_cache()
    calls = []
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(calls, {"access_token": "tok-1", "expires_in": 1800}))

    token = await oauth_client.get_access_token()

    assert token == "tok-1"
    assert len(calls) == 1


async def test_reuses_cached_token_without_a_new_request(monkeypatch):
    _reset_cache()
    calls = []
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(calls, {"access_token": "tok-1", "expires_in": 1800}))

    first = await oauth_client.get_access_token()
    second = await oauth_client.get_access_token()

    assert first == second == "tok-1"
    assert len(calls) == 1  # only one real token fetch, not two


async def test_refetches_once_the_cached_token_is_near_expiry(monkeypatch):
    _reset_cache()
    calls = []
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(calls, {"access_token": "tok-1", "expires_in": 10}))

    await oauth_client.get_access_token()
    oauth_client._cached_token_expires_at -= 3600  # simulate time passing

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(calls, {"access_token": "tok-2", "expires_in": 1800}))
    second = await oauth_client.get_access_token()

    assert second == "tok-2"
    assert len(calls) == 2
