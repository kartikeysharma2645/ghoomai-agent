"""Fetch.ai Agent integration for the GhoomAI Agent service.

This module constructs a ``uagents`` ``Agent`` with the Agent Chat
Protocol (``chat_protocol`` from :mod:`app.chat_protocol``) included.

The agent requires ``AGENT_SEED_PHRASE`` to establish a deterministic
identity. Without it, :func:`create_agent` raises a clear
:class:`RuntimeError`. The health endpoint (``GET /status``) does not
require the agent or any credentials.

No agent registration, ASI:One discoverability, or deployment is
performed here. Call :func:`create_agent` to obtain an ``Agent``
instance; call ``agent.run()`` only when you are ready to run the agent
runtime locally.

Official documentation sources:
  * uAgents Framework: https://uagents.fetch.ai/docs/getting-started/install
  * uAgents Core (PyPI): https://pypi.org/pypi/uagents-core
"""

from __future__ import annotations

import logging

from uagents import Agent

from app.chat_protocol import chat_protocol
from app.config import settings

logger = logging.getLogger(__name__)


def create_agent() -> Agent:
    """Create and configure the GhoomAI Fetch.ai agent.

    The agent is constructed with:
      * A deterministic identity derived from ``AGENT_SEED_PHRASE``.
      * The Agent Chat Protocol (``chat_protocol``) included.
      * The configured agent port and network.
      * Mailbox mode (``AGENT_MAILBOX``, default ``true``) so the agent can
        connect to Agentverse via a secure mailbox channel without requiring
        a publicly reachable HTTP endpoint.

    Raises:
        RuntimeError: If ``AGENT_SEED_PHRASE`` is not set.
    """
    settings.require_agent_credentials()

    agent = Agent(
        name="ghoomai-agent",
        seed=settings.agent_seed_phrase,
        port=settings.agent_port,
        network=settings.agent_network,  # type: ignore[arg-type]
        mailbox=settings.agent_mailbox,
        publish_agent_details=False,
        store_message_history=False,
        handle_messages_concurrently=False,
    )

    agent.include(chat_protocol)

    logger.info(
        "GhoomAI agent created (address=%s, port=%d, network=%s)",
        agent.address,
        settings.agent_port,
        settings.agent_network,
    )

    return agent


# Placeholder: no agent is constructed at import time. The agent must be
# created explicitly via :func:`create_agent`, which requires
# ``AGENT_SEED_PHRASE``. This keeps imports and tests credential-free.
AGENT = None

__all__ = ["AGENT", "create_agent"]
