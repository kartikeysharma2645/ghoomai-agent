"""Tests for the GhoomAI HTTP client.

All network calls are mocked using a fake httpx AsyncClient. No real
API keys, live services, or internet access are required.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
import pytest

from app.ghoomai_client import (
    GhoomAIClient,
    GhoomAIConnectionError,
    GhoomAIHTTPError,
    GhoomAIResponseError,
    GhoomAITimeoutError,
    INITIAL_SESSION,
)


class FakeResponse:
    """A minimal stand-in for httpx.Response."""

    def __init__(
        self,
        status_code: int,
        json_data: Optional[Dict[str, Any]] = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self) -> Dict[str, Any]:
        if self._json is None:
            raise ValueError("No JSON")
        return self._json


class FakeAsyncClient:
    """A fake httpx.AsyncClient that records and returns canned responses."""

    def __init__(
        self,
        response: Optional[httpx.Response] = None,
        exc: Optional[Exception] = None,
    ) -> None:
        self._response = response
        self._exc = exc
        self.last_url: Optional[str] = None
        self.last_json: Optional[Dict[str, Any]] = None
        self.closed = False

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def post(
        self,
        url: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        self.last_url = url
        self.last_json = json
        if self._exc is not None:
            raise self._exc
        return self._response  # type: ignore[return-value]

    async def aclose(self) -> None:
        self.closed = True


def _make_success_response(session: Dict[str, Any]) -> FakeResponse:
    return FakeResponse(
        status_code=200,
        json_data={
            "ok": True,
            "data": {
                "message": "Default response",
                "session": session,
            },
        },
        text='{"ok": true, "data": {"message": "...", "session": ...}}',
    )


def test_client_sends_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """The client should POST { session, message } to /api/agent."""
    updated_session = {
        "sessionVersion": 1,
        "transcript": [{"role": "assistant", "content": "Hi!"}],
        "tripStatus": "DRAFT",
    }
    fake = FakeAsyncClient(response=_make_success_response(updated_session))

    # Patch _get_client to return our fake without closing it.
    async def fake_get_client() -> FakeAsyncClient:
        return fake

    client = GhoomAIClient(
        base_url="https://ghoomai.netlify.app",
        timeout=10.0,
    )
    monkeypatch.setattr(client, "_get_client", fake_get_client)

    import asyncio

    result = asyncio.run(
        client.send_message("Plan a trip", session=INITIAL_SESSION)
    )

    assert fake.last_url == "https://ghoomai.netlify.app/api/agent"
    assert fake.last_json is not None
    assert fake.last_json["message"] == "Plan a trip"
    assert fake.last_json["session"] == INITIAL_SESSION
    assert result["session"] == updated_session
    assert result["data"]["ok"] is True
    assert result["data"]["data"]["session"] == updated_session


def test_client_uses_initial_session_when_none_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no session is provided, the initial session structure is sent."""
    fake = FakeAsyncClient(response=_make_success_response(INITIAL_SESSION))

    async def fake_get_client() -> FakeAsyncClient:
        return fake

    client = GhoomAIClient(base_url="https://ghoomai.netlify.app", timeout=10.0)
    monkeypatch.setattr(client, "_get_client", fake_get_client)

    import asyncio

    asyncio.run(client.send_message("Hello", session=None))

    assert fake.last_json is not None
    assert fake.last_json["session"] == INITIAL_SESSION


def test_client_returns_nested_session_from_valid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: a valid nested response returns its session correctly."""
    updated_session = {
        "sessionVersion": 1,
        "transcript": [{"role": "user", "content": "Hello"}],
        "tripStatus": "DRAFT",
    }
    fake = FakeAsyncClient(
        response=_make_success_response(updated_session)
    )

    async def fake_get_client() -> FakeAsyncClient:
        return fake

    client = GhoomAIClient(base_url="https://ghoomai.netlify.app", timeout=10.0)
    monkeypatch.setattr(client, "_get_client", fake_get_client)

    import asyncio

    result = asyncio.run(
        client.send_message("Plan a trip", session=updated_session)
    )

    assert result["session"] == updated_session
    assert result["data"]["ok"] is True
    assert result["data"]["data"]["session"] == updated_session
    assert isinstance(result["data"]["data"]["message"], str)
    assert len(result["data"]["data"]["message"]) > 0


def test_client_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timeout should raise GhoomAITimeoutError."""
    fake = FakeAsyncClient(exc=httpx.TimeoutException("read timed out"))

    async def fake_get_client() -> FakeAsyncClient:
        return fake

    client = GhoomAIClient(base_url="https://ghoomai.netlify.app", timeout=10.0)
    monkeypatch.setattr(client, "_get_client", fake_get_client)

    import asyncio

    with pytest.raises(GhoomAITimeoutError):
        asyncio.run(client.send_message("Hello"))


def test_client_handles_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A connection failure should raise GhoomAIConnectionError."""
    fake = FakeAsyncClient(exc=httpx.ConnectError("connection refused"))

    async def fake_get_client() -> FakeAsyncClient:
        return fake

    client = GhoomAIClient(base_url="https://ghoomai.netlify.app", timeout=10.0)
    monkeypatch.setattr(client, "_get_client", fake_get_client)

    import asyncio

    with pytest.raises(GhoomAIConnectionError):
        asyncio.run(client.send_message("Hello"))


def test_client_handles_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-2xx HTTP status should raise GhoomAIHTTPError."""
    fake_response = FakeResponse(
        status_code=500,
        text="Internal Server Error",
    )
    fake = FakeAsyncClient(response=fake_response)

    async def fake_get_client() -> FakeAsyncClient:
        return fake

    client = GhoomAIClient(base_url="https://ghoomai.netlify.app", timeout=10.0)
    monkeypatch.setattr(client, "_get_client", fake_get_client)

    import asyncio

    with pytest.raises(GhoomAIHTTPError) as excinfo:
        asyncio.run(client.send_message("Hello"))

    assert excinfo.value.status_code == 500


def test_client_handles_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid JSON should raise GhoomAIResponseError."""
    fake = FakeResponse(status_code=200, json_data=None, text="not json")

    async_client = FakeAsyncClient(response=fake)

    async def fake_get_client() -> FakeAsyncClient:
        return async_client

    client = GhoomAIClient(base_url="https://ghoomai.netlify.app", timeout=10.0)
    monkeypatch.setattr(client, "_get_client", fake_get_client)

    import asyncio

    with pytest.raises(GhoomAIResponseError):
        asyncio.run(client.send_message("Hello"))


def test_client_handles_missing_session_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 response without a 'session' field should raise GhoomAIResponseError."""
    fake = FakeResponse(
        status_code=200,
        json_data={"status": "success"},
        text='{"status": "success"}',
    )

    async_client = FakeAsyncClient(response=fake)

    async def fake_get_client() -> FakeAsyncClient:
        return async_client

    client = GhoomAIClient(base_url="https://ghoomai.netlify.app", timeout=10.0)
    monkeypatch.setattr(client, "_get_client", fake_get_client)

    import asyncio

    with pytest.raises(GhoomAIResponseError):
        asyncio.run(client.send_message("Hello"))


def test_client_handles_data_object_without_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 200 response with a 'data' object but no 'session' field should
    raise GhoomAIResponseError."""
    fake = FakeResponse(
        status_code=200,
        json_data={"ok": True, "data": {}},
        text='{"ok": true, "data": {}}',
    )
    fake_async_client = FakeAsyncClient(response=fake)

    async def fake_get_client() -> FakeAsyncClient:
        return fake_async_client

    client = GhoomAIClient(base_url="https://ghoomai.netlify.app", timeout=10.0)
    monkeypatch.setattr(client, "_get_client", fake_get_client)

    import asyncio

    with pytest.raises(GhoomAIResponseError):
        asyncio.run(client.send_message("Hello"))
