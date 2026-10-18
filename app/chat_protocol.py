"""Fetch.ai Agent Chat Protocol integration for the GhoomAI Agent.

This module implements the inbound/outbound Agent Chat Protocol (ACP)
integration using the documented ``uagents`` SDK pattern.

It defines a testable ``ChatHandler`` class that connects incoming
``ChatMessage`` envelopes to the GhoomAI backend, plus a ``uagents``
``Protocol`` that wires the handler into an ``Agent``.

No agent registration, ASI:One discoverability, or deployment is
performed here. The protocol is constructed from the verified
``chat_protocol_spec`` (AgentChatProtocol 0.3.0).

Official documentation sources:
  * uAgents Framework: https://uagents.fetch.ai/docs/getting-started/install
  * Chat Protocol example:
    https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents
  * uAgents Core (PyPI): https://pypi.org/pypi/uagents-core

Verified imports (uagents-core 0.4.12, uagents 0.26.1):

    from uagents import Agent, Context
    from uagents import Protocol
    from uagents_core.contrib.protocols.chat import (
        ChatAcknowledgement,
        ChatMessage,
        TextContent,
        StartSessionContent,
        EndSessionContent,
        chat_protocol_spec,
    )

The conversation identifier is the envelope ``session`` UUID, exposed
via ``ctx.session``. This maps 1:1 to a GhoomAI conversation.

Protocol behavior (verified AgentChatProtocol 0.3.0):
  * ``ChatMessage`` interactions specify ``ChatAcknowledgement`` as the
    valid reply. The handler acknowledges every incoming ``ChatMessage``
    with a ``ChatAcknowledgement``.
  * The actual response content is delivered as a separate ``ChatMessage``
    containing ``TextContent``. The acknowledgement is never confused with
    the response content.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from uagents import Context
from uagents import Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from app.config import settings
from app.ghoomai_client import (
    GhoomAIClient,
    GhoomAIClientError,
    GhoomAIResponseError,
    INITIAL_SESSION,
)
from app.session_store import SessionStore


class ChatHandler:
    """Handles incoming Agent Chat Protocol messages.

    Dependencies (``SessionStore`` and ``GhoomAIClient``) are injected so
    the handler can be unit-tested without the uAgents runtime or network
    calls.
    """

    def __init__(
        self,
        session_store: SessionStore,
        ghoomai_client: GhoomAIClient,
    ) -> None:
        self._session_store = session_store
        self._ghoomai_client = ghoomai_client

    @property
    def session_store(self) -> SessionStore:
        return self._session_store

    @property
    def ghoomai_client(self) -> GhoomAIClient:
        return self._ghoomai_client

    def _conversation_id(self, session_uuid: uuid.UUID) -> str:
        """Convert the ACP envelope session UUID to a conversation key."""
        return str(session_uuid)

    def _extract_text(self, msg: ChatMessage) -> str:
        """Extract text content from a ChatMessage.

        Returns the concatenated text from all ``TextContent`` elements.
        Returns an empty string if there is no text content.
        """
        return msg.text()

    def _has_content_type(
        self, msg: ChatMessage, content_type: type
    ) -> bool:
        """Return True if the message contains the given content type."""
        return any(isinstance(c, content_type) for c in msg.content)

    def _extract_response_text(self, data: dict) -> str:
        """Extract the user-facing response message from GhoomAI API response data.

        The GhoomAI API response contract nests the user-facing text under
        ``data["data"]["message"]``. No heuristic field search or transcript
        fallback is used; if the message is missing or invalid, a
        :class:`GhoomAIResponseError` is raised so the caller can handle it
        as a clear application error rather than fabricating a response.
        """
        if not isinstance(data, dict):
            raise GhoomAIResponseError("GhoomAI API response data is not an object")

        inner_data = data.get("data")
        if not isinstance(inner_data, dict):
            raise GhoomAIResponseError("GhoomAI API response missing 'data' object")

        message = inner_data.get("message")
        if not isinstance(message, str) or not message.strip():
            raise GhoomAIResponseError("GhoomAI API response missing 'message' field")

        return message.strip()

    async def _send_acknowledgement(
        self, ctx: Context, sender: str, msg: ChatMessage, metadata: dict
    ) -> None:
        """Send a ``ChatAcknowledgement`` to the originating agent."""
        await ctx.send(
            sender,
            ChatAcknowledgement(
                acknowledged_msg_id=msg.msg_id,
                metadata=metadata,
            ),
        )

    async def _send_response(
        self, ctx: Context, sender: str, text: str
    ) -> None:
        """Send the actual response as a ``ChatMessage`` with ``TextContent``."""
        await ctx.send(
            sender,
            ChatMessage(
                content=[TextContent(text=text)],
                msg_id=uuid.uuid4(),
                timestamp=datetime.now(timezone.utc),
            ),
        )

    async def handle_message(
        self,
        ctx: Context,
        sender: str,
        msg: ChatMessage,
    ) -> None:
        """Handle an incoming ``ChatMessage``.

        Steps:
          1. Identify the conversation from ``ctx.session`` (the envelope
             session UUID).
          2. Handle start/end-session content per protocol semantics.
          3. Extract text content; handle empty/unsupported content.
          4. Retrieve or initialize the GhoomAI session.
          5. Forward the message and session to GhoomAI.
          6. Persist the returned ``data.session``.
          7. Acknowledge the incoming message with ``ChatAcknowledgement``.
          8. Send the actual response as a ``ChatMessage`` with
             ``TextContent``.
          9. Handle errors without crashing.
        """
        session_uuid: uuid.UUID = ctx.session
        conversation_id = self._conversation_id(session_uuid)

        # Detect session lifecycle content.
        is_start = self._has_content_type(msg, StartSessionContent)
        is_end = self._has_content_type(msg, EndSessionContent)

        # Extract text content.
        text = self._extract_text(msg)

        # Handle end-session: reset the GhoomAI session, acknowledge, and
        # inform the sender.
        if is_end:
            self._session_store.reset(conversation_id)
            await self._send_acknowledgement(
                ctx, sender, msg, {"action": "session-ended"}
            )
            await self._send_response(
                ctx, sender, "Session ended. Your trip plan has been cleared."
            )
            return

        # Handle empty / unsupported content: acknowledge but do not
        # forward to GhoomAI. No response content to deliver.
        if not text and not is_start:
            await self._send_acknowledgement(
                ctx, sender, msg, {"reason": "no text content"}
            )
            return

        # Handle start-session: ensure a fresh session exists.
        if is_start:
            self._session_store.initialize(conversation_id)

        # Retrieve or initialize the GhoomAI session for this conversation.
        current_session = self._session_store.get(conversation_id)
        if current_session is None:
            current_session = self._session_store.initialize(conversation_id)

        # Forward to GhoomAI.
        try:
            result = await self._ghoomai_client.send_message(
                message=text,
                session=current_session,
            )
        except GhoomAIClientError as exc:
            # Log without exposing sensitive details.
            ctx.logger.error(
                "GhoomAI request failed for conversation %s: %s",
                conversation_id,
                type(exc).__name__,
            )
            await self._send_acknowledgement(
                ctx, sender, msg, {"error": "ghoomai_request_failed"}
            )
            await self._send_response(
                ctx,
                sender,
                "Sorry, I couldn't process your request at the moment. "
                "Please try again later.",
            )
            return

        # Persist the complete session object returned by GhoomAI.
        updated_session = result["session"]
        self._session_store.update(conversation_id, updated_session)

        # Extract the actual response text from GhoomAI's response data.
        try:
            response_text = self._extract_response_text(result["data"])
        except GhoomAIResponseError as exc:
            # Log without exposing sensitive details.
            ctx.logger.error(
                "GhoomAI response malformed for conversation %s: %s",
                conversation_id,
                type(exc).__name__,
            )
            await self._send_acknowledgement(
                ctx, sender, msg, {"error": "ghoomai_response_malformed"}
            )
            await self._send_response(
                ctx,
                sender,
                "Sorry, I received an invalid response from the travel service. "
                "Please try again later.",
            )
            return

        # Acknowledge the incoming message (per protocol spec:
        # ChatMessage -> ChatAcknowledgement).
        await self._send_acknowledgement(
            ctx, sender, msg, {"status": "delivered"}
        )

        # Send the actual response as a separate ChatMessage with
        # TextContent. The acknowledgement is never confused with the
        # response content.
        await self._send_response(ctx, sender, response_text)


def create_chat_protocol(handler: ChatHandler) -> Protocol:
    """Create the Agent Chat Protocol with the message handler registered.

    The protocol is built from the verified ``chat_protocol_spec`` so its
    digest and interaction rules match the official specification.
    """
    proto = Protocol(spec=chat_protocol_spec)

    @proto.on_message(ChatMessage)
    async def _on_chat_message(
        ctx: Context, sender: str, msg: ChatMessage
    ) -> None:
        await handler.handle_message(ctx, sender, msg)

    @proto.on_message(ChatAcknowledgement)
    async def _on_chat_acknowledgement(
        ctx: Context, sender: str, msg: ChatAcknowledgement
    ) -> None:
        # Acknowledgements are reply-only in AgentChatProtocol 0.3.0.
        # No action required; logged for observability.
        ctx.logger.debug(
            "Received ChatAcknowledgement for msg %s from %s",
            msg.acknowledged_msg_id,
            sender,
        )

    return proto


# Module-level instances for use by app/agent.py.
# These are constructed without a seed phrase so they can be imported and
# tested without credentials. The Agent in app/agent.py requires a seed.
chat_handler = ChatHandler(
    session_store=SessionStore(),
    ghoomai_client=GhoomAIClient(
        base_url=settings.api_base_url,
        timeout=settings.api_timeout,
    ),
)

chat_protocol = create_chat_protocol(chat_handler)

__all__ = [
    "ChatHandler",
    "chat_handler",
    "chat_protocol",
    "create_chat_protocol",
]
