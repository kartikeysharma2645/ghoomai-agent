"""Tests for the Agent Chat Protocol integration.

All tests mock the uAgents runtime (Context), GhoomAIClient, and
SessionStore dependencies. No real credentials, Agentverse registration,
or live GhoomAI calls are required.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, List, Optional, Tuple

import pytest
from pydantic.v1 import UUID4

from app.chat_protocol import (
    ChatAcknowledgement,
    ChatMessage,
    ChatHandler,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol,
)
from app.config import settings
from app.ghoomai_client import (
    GhoomAIClient,
    GhoomAIClientError,
    GhoomAIConnectionError,
    GhoomAIHTTPError,
    GhoomAIResponseError,
    GhoomAITimeoutError,
    INITIAL_SESSION,
)
from app.session_store import SessionStore


class FakeContext:
    """A test double for uagents.Context.

    Provides ``session``, ``logger``, and an async ``send`` method that
    records every destination/message pair sent.
    """

    def __init__(
        self,
        session: Optional[uuid.UUID] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.session = session or uuid.uuid4()
        self.logger = logger or logging.getLogger("test")
        self.sent: List[Tuple[str, Any]] = []

    async def send(self, destination: str, message: Any) -> None:
        self.sent.append((destination, message))

    @property
    def send_count(self) -> int:
        return len(self.sent)

    @property
    def last_destination(self) -> Optional[str]:
        return self.sent[-1][0] if self.sent else None

    @property
    def last_message(self) -> Optional[Any]:
        return self.sent[-1][1] if self.sent else None

    def messages_of_type(self, message_type: type) -> List[Any]:
        """Return all sent messages of the given type."""
        return [msg for _, msg in self.sent if isinstance(msg, message_type)]


class FakeGhoomAIClient:
    """A test double for GhoomAIClient.

    Returns canned results or raises canned exceptions from
    ``send_message``.
    """

    def __init__(
        self,
        result: Optional[dict] = None,
        exc: Optional[Exception] = None,
    ) -> None:
        self._result = result
        self._exc = exc
        self.last_message: Optional[str] = None
        self.last_session: Optional[dict] = None
        self.call_count = 0

    async def send_message(
        self, message: str, session: Optional[dict] = None
    ) -> dict:
        self.call_count += 1
        self.last_message = message
        self.last_session = session
        if self._exc is not None:
            raise self._exc
        if self._result is None:
            self._result = {
                "data": {
                    "ok": True,
                    "data": {"message": "Default response", "session": INITIAL_SESSION},
                },
                "session": INITIAL_SESSION,
            }
        return self._result


def _run(coro):
    """Run an async coroutine synchronously in tests."""
    return asyncio.run(coro)


def _make_text_message(text: str, msg_id: Optional[UUID4] = None) -> ChatMessage:
    return ChatMessage(
        content=[TextContent(text=text)],
        msg_id=msg_id,
    )


def _make_empty_message(msg_id: Optional[UUID4] = None) -> ChatMessage:
    return ChatMessage(
        content=[],
        msg_id=msg_id,
    )


def _make_start_message(msg_id: Optional[UUID4] = None) -> ChatMessage:
    return ChatMessage(
        content=[StartSessionContent()],
        msg_id=msg_id,
    )


def _make_end_message(msg_id: Optional[UUID4] = None) -> ChatMessage:
    return ChatMessage(
        content=[EndSessionContent()],
        msg_id=msg_id,
    )


def _make_mixed_message(text: str, msg_id: Optional[UUID4] = None) -> ChatMessage:
    return ChatMessage(
        content=[TextContent(text=text), StartSessionContent()],
        msg_id=msg_id,
    )


# ---------------------------------------------------------------------------
# ChatHandler tests
# ---------------------------------------------------------------------------


def test_text_message_extraction() -> None:
    """The handler should extract text from a ChatMessage."""
    store = SessionStore()
    client = FakeGhoomAIClient()
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    ctx = FakeContext(session=uuid.uuid4())

    _run(
        handler.handle_message(
            ctx, "sender-address", _make_text_message("Plan a trip to Paris")
        )
    )

    assert client.last_message == "Plan a trip to Paris"
    assert client.call_count == 1


def test_empty_content_is_acknowledged_only() -> None:
    """A message with no text and no session lifecycle content should be
    acknowledged but not forwarded to GhoomAI. No response content is
    delivered because there is nothing to respond to."""
    store = SessionStore()
    client = FakeGhoomAIClient()
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    ctx = FakeContext(session=uuid.uuid4())

    _run(handler.handle_message(ctx, "sender-address", _make_empty_message()))

    assert client.call_count == 0
    assert ctx.send_count == 1
    acks = ctx.messages_of_type(ChatAcknowledgement)
    assert len(acks) == 1
    assert acks[0].metadata.get("reason") == "no text content"
    # No ChatMessage response should be sent for empty content.
    assert len(ctx.messages_of_type(ChatMessage)) == 0


def test_start_session_initializes_store() -> None:
    """A start-session message should initialize a GhoomAI session."""
    store = SessionStore()
    client = FakeGhoomAIClient()
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, "sender-address", _make_start_message()))

    assert store.contains(conv_id)
    session = store.get(conv_id)
    assert session == INITIAL_SESSION


def test_end_session_resets_store() -> None:
    """An end-session message should reset the GhoomAI session."""
    store = SessionStore()
    client = FakeGhoomAIClient()
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    # Initialize first, then end.
    store.initialize(conv_id)
    assert store.contains(conv_id)

    _run(handler.handle_message(ctx, "sender-address", _make_end_message()))

    # Store should still contain the conversation (reset re-initializes).
    assert store.contains(conv_id)
    session = store.get(conv_id)
    assert session == INITIAL_SESSION

    # End-session should send acknowledgement and a response message.
    assert ctx.send_count == 2
    acks = ctx.messages_of_type(ChatAcknowledgement)
    assert len(acks) == 1
    assert acks[0].metadata.get("action") == "session-ended"
    responses = ctx.messages_of_type(ChatMessage)
    assert len(responses) == 1


def test_session_isolation_between_conversations() -> None:
    """Different envelope sessions must map to independent GhoomAI sessions."""
    store = SessionStore()
    client = FakeGhoomAIClient()
    handler = ChatHandler(session_store=store, ghoomai_client=client)

    conv_a = uuid.uuid4()
    conv_b = uuid.uuid4()

    ctx_a = FakeContext(session=conv_a)
    ctx_b = FakeContext(session=conv_b)

    _run(
        handler.handle_message(
            ctx_a, "sender-a", _make_text_message("message from A")
        )
    )
    _run(
        handler.handle_message(
            ctx_b, "sender-b", _make_text_message("message from B")
        )
    )

    session_a = store.get(str(conv_a))
    session_b = store.get(str(conv_b))

    assert session_a is not session_b
    assert client.last_session == session_b  # last call was for B


def test_successful_ghoomai_response_persists_session() -> None:
    """The handler should persist the session returned by GhoomAI."""
    store = SessionStore()
    updated = {
        "sessionVersion": 1,
        "transcript": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        "tripStatus": "DRAFT",
    }
    client = FakeGhoomAIClient(
        result={
            "data": {
                "ok": True,
                "data": {"message": "Hi there!", "session": updated},
            },
            "session": updated,
        }
    )
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, "sender-address", _make_text_message("Hello")))

    assert store.get(conv_id) == updated


def test_actual_ghoomai_response_is_delivered_as_chat_message() -> None:
    """The actual GhoomAI response text must be sent as a separate
    ChatMessage with TextContent, not confused with the acknowledgement."""
    store = SessionStore()
    updated = {
        "sessionVersion": 1,
        "transcript": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        "tripStatus": "DRAFT",
    }
    client = FakeGhoomAIClient(
        result={
            "data": {
                "ok": True,
                "data": {"message": "Hi there!", "session": updated},
            },
            "session": updated,
        }
    )
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    sender = "sender-address"
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, sender, _make_text_message("Hello")))

    # Exactly two messages should be sent: acknowledgement + response.
    assert ctx.send_count == 2

    # First message: ChatAcknowledgement.
    acks = ctx.messages_of_type(ChatAcknowledgement)
    assert len(acks) == 1
    assert acks[0].acknowledged_msg_id is not None
    assert acks[0].metadata.get("status") == "delivered"

    # Second message: ChatMessage with TextContent containing the response.
    responses = ctx.messages_of_type(ChatMessage)
    assert len(responses) == 1
    assert isinstance(responses[0], ChatMessage)
    assert responses[0].text() == "Hi there!"

    # All messages routed to the sender.
    for dest, _ in ctx.sent:
        assert dest == sender


def test_acknowledgement_and_response_are_not_confused() -> None:
    """The ChatAcknowledgement must not contain the response text, and the
    ChatMessage response must not be an acknowledgement."""
    store = SessionStore()
    client = FakeGhoomAIClient(
        result={
            "data": {
                "ok": True,
                "data": {"message": "Paris is lovely!", "session": INITIAL_SESSION},
            },
            "session": INITIAL_SESSION,
        }
    )
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    ctx = FakeContext(session=uuid.uuid4())

    _run(handler.handle_message(ctx, "sender", _make_text_message("Tell me about Paris")))

    acks = ctx.messages_of_type(ChatAcknowledgement)
    responses = ctx.messages_of_type(ChatMessage)

    assert len(acks) == 1
    assert len(responses) == 1

    # Acknowledgement carries metadata, not response text.
    assert acks[0].acknowledged_msg_id is not None
    assert acks[0].metadata.get("status") == "delivered"

    # Response is a ChatMessage with the actual text.
    assert isinstance(responses[0], ChatMessage)
    assert responses[0].text() == "Paris is lovely!"

    # Acknowledgement is not a ChatMessage.
    assert not isinstance(acks[0], ChatMessage)

    # Response is not a ChatAcknowledgement.
    assert not isinstance(responses[0], ChatAcknowledgement)


def test_ghoomai_timeout_sends_error_response() -> None:
    """A GhoomAI timeout should send both an acknowledgement and an
    error response message, without crashing."""
    store = SessionStore()
    client = FakeGhoomAIClient(exc=GhoomAITimeoutError("timeout"))
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, "sender-address", _make_text_message("Hello")))

    # Both acknowledgement and error response should be sent.
    assert ctx.send_count == 2
    acks = ctx.messages_of_type(ChatAcknowledgement)
    responses = ctx.messages_of_type(ChatMessage)
    assert len(acks) == 1
    assert acks[0].metadata.get("error") == "ghoomai_request_failed"
    assert len(responses) == 1
    assert "couldn't process" in responses[0].text().lower()


def test_ghoomai_connection_error_sends_error_response() -> None:
    """A GhoomAI connection error should send both an acknowledgement and
    an error response message."""
    store = SessionStore()
    client = FakeGhoomAIClient(exc=GhoomAIConnectionError("connection refused"))
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, "sender-address", _make_text_message("Hello")))

    assert ctx.send_count == 2
    acks = ctx.messages_of_type(ChatAcknowledgement)
    responses = ctx.messages_of_type(ChatMessage)
    assert len(acks) == 1
    assert len(responses) == 1


def test_ghoomai_http_error_sends_error_response() -> None:
    """A GhoomAI HTTP error should send both an acknowledgement and an
    error response message."""
    store = SessionStore()
    client = FakeGhoomAIClient(exc=GhoomAIHTTPError(500, "Internal Server Error"))
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, "sender-address", _make_text_message("Hello")))

    assert ctx.send_count == 2
    assert len(ctx.messages_of_type(ChatAcknowledgement)) == 1
    assert len(ctx.messages_of_type(ChatMessage)) == 1


def test_ghoomai_response_error_sends_error_response() -> None:
    """A GhoomAI response error should send both an acknowledgement and
    an error response message."""
    store = SessionStore()
    client = FakeGhoomAIClient(exc=GhoomAIResponseError("invalid response"))
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, "sender-address", _make_text_message("Hello")))

    assert ctx.send_count == 2
    assert len(ctx.messages_of_type(ChatAcknowledgement)) == 1
    assert len(ctx.messages_of_type(ChatMessage)) == 1


def test_response_is_routed_to_sender() -> None:
    """Both the acknowledgement and the response should be sent back to
    the message sender."""
    store = SessionStore()
    client = FakeGhoomAIClient(
        result={
            "data": {
                "ok": True,
                "data": {"message": "Hi!", "session": INITIAL_SESSION},
            },
            "session": INITIAL_SESSION,
        }
    )
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    sender = "agent1xyz"
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, sender, _make_text_message("Hello")))

    for dest, _ in ctx.sent:
        assert dest == sender


def test_mixed_text_and_start_session() -> None:
    """A message with both text and start-session content should forward
    the text and initialize the session."""
    store = SessionStore()
    client = FakeGhoomAIClient(
        result={
            "data": {
                "ok": True,
                "data": {"message": "Started!", "session": INITIAL_SESSION},
            },
            "session": INITIAL_SESSION,
        }
    )
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(
        handler.handle_message(
            ctx, "sender-address", _make_mixed_message("Plan a trip")
        )
    )

    assert client.last_message == "Plan a trip"
    assert store.contains(conv_id)
    assert ctx.send_count == 2  # acknowledgement + response


def test_missing_response_message_is_handled_as_error() -> None:
    """When the GhoomAI response lacks a usable ``message`` field, the
    handler must not fabricate a response. It sends an acknowledgement
    and an error response instead."""
    store = SessionStore()
    updated_session_no_message = {
        "sessionVersion": 1,
        "transcript": [],
        "tripStatus": "DRAFT",
    }
    client = FakeGhoomAIClient(
        result={
            "data": {
                "ok": True,
                "data": {"session": updated_session_no_message},
            },
            "session": updated_session_no_message,
        }
    )
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, "sender-address", _make_text_message("Hello")))

    # Session was still persisted (client returned one).
    assert store.get(conv_id) == updated_session_no_message

    # Both acknowledgement and error response were sent.
    assert ctx.send_count == 2
    acks = ctx.messages_of_type(ChatAcknowledgement)
    responses = ctx.messages_of_type(ChatMessage)
    assert len(acks) == 1
    assert acks[0].metadata.get("error") == "ghoomai_response_malformed"
    assert len(responses) == 1
    assert "invalid response" in responses[0].text().lower()


def test_empty_response_message_is_handled_as_error() -> None:
    """When the GhoomAI response message is an empty string, the handler
    must not fabricate a response."""
    store = SessionStore()
    client = FakeGhoomAIClient(
        result={
            "data": {
                "ok": True,
                "data": {"message": "   ", "session": INITIAL_SESSION},
            },
            "session": INITIAL_SESSION,
        }
    )
    handler = ChatHandler(session_store=store, ghoomai_client=client)
    conv_id = str(uuid.uuid4())
    ctx = FakeContext(session=uuid.UUID(conv_id))

    _run(handler.handle_message(ctx, "sender-address", _make_text_message("Hello")))

    assert ctx.send_count == 2
    acks = ctx.messages_of_type(ChatAcknowledgement)
    responses = ctx.messages_of_type(ChatMessage)
    assert len(acks) == 1
    assert acks[0].metadata.get("error") == "ghoomai_response_malformed"
    assert len(responses) == 1


# ---------------------------------------------------------------------------
# Protocol tests
# ---------------------------------------------------------------------------


def test_chat_protocol_has_chat_message_handler() -> None:
    """The protocol should register a handler for ChatMessage."""
    from uagents_core.models import Model

    model_digest = Model.build_schema_digest(ChatMessage)
    assert model_digest in chat_protocol.signed_message_handlers


def test_chat_protocol_spec_matches_official() -> None:
    """The protocol spec should match the verified AgentChatProtocol 0.3.0."""
    from uagents_core.contrib.protocols.chat import chat_protocol_spec

    assert chat_protocol_spec.name == "AgentChatProtocol"
    assert chat_protocol_spec.version == "0.3.0"


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------


def test_settings_agent_port_validation() -> None:
    """Settings should accept valid configuration."""
    settings.validate()  # should not raise with current env defaults


def test_settings_require_agent_credentials_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """require_agent_credentials should raise when no seed phrase is set."""
    monkeypatch.delenv("AGENT_SEED_PHRASE", raising=False)
    # Force settings to re-read from environment.
    import importlib
    import app.config as config_module

    importlib.reload(config_module)
    try:
        with pytest.raises(RuntimeError, match="AGENT_SEED_PHRASE"):
            config_module.settings.require_agent_credentials()
    finally:
        importlib.reload(config_module)
