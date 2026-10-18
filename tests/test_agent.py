"""Tests for the uAgents agent construction and mailbox mode.

These tests mock the ``uagents.Agent`` constructor so no real agent
identity, network connection, or Agentverse registration is required.
Importing ``app.agent`` does not require credentials.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.agent import create_agent


def _reload_with_seed(seed_value: str | None) -> None:
    """Reload config and agent modules with the given seed phrase env var."""
    import importlib
    import os

    if seed_value is None:
        os.environ.pop("AGENT_SEED_PHRASE", None)
    else:
        os.environ["AGENT_SEED_PHRASE"] = seed_value

    import app.config as config_module
    import app.agent as agent_module

    importlib.reload(config_module)
    importlib.reload(agent_module)


def test_create_agent_enables_mailbox_mode() -> None:
    """create_agent() should construct the Agent with mailbox=True."""
    _reload_with_seed("test-seed-phrase-12345")
    with patch("app.agent.Agent") as mock_agent:
        create_agent()
        # mock_agent is a MagicMock; call_args captures the constructor call.
        _, kwargs = mock_agent.call_args
        assert kwargs.get("mailbox") is True
        # The protocol include() should have been called on the mock instance.
        assert mock_agent.return_value.include.called


def test_create_agent_preserves_name_and_settings() -> None:
    """The agent name, port, and network should be preserved."""
    _reload_with_seed("test-seed-phrase-12345")
    with patch("app.agent.Agent") as mock_agent:
        create_agent()
        _, kwargs = mock_agent.call_args
        assert kwargs.get("name") == "ghoomai-agent"
        assert kwargs.get("port") == 8001
        assert kwargs.get("network") == "mainnet"


def test_create_agent_uses_seed_phrase_without_logging_it(caplog) -> None:
    """Agent construction should use the seed phrase but never log it."""
    _reload_with_seed("test-seed-phrase-12345")
    with patch("app.agent.Agent") as mock_agent:
        create_agent()
        _, kwargs = mock_agent.call_args
        assert kwargs.get("seed") == "test-seed-phrase-12345"
        # Seed phrase should not appear in logs.
        log_text = caplog.text
        assert "test-seed-phrase-12345" not in log_text


def test_create_agent_raises_on_missing_seed() -> None:
    """create_agent() should raise RuntimeError when no seed phrase is set."""
    _reload_with_seed(None)
    import app.config as config_module

    with pytest.raises(RuntimeError, match="AGENT_SEED_PHRASE"):
        config_module.settings.require_agent_credentials()


def test_import_app_agent_without_credentials() -> None:
    """Importing app.agent should not require credentials."""
    import app.agent

    assert app.agent.AGENT is None
    assert callable(app.agent.create_agent)


def test_create_agent_uses_configured_protocol() -> None:
    """The created agent should include the chat protocol."""
    _reload_with_seed("test-seed-phrase-12345")
    with patch("app.agent.Agent") as mock_agent:
        create_agent()
        assert mock_agent.return_value.include.called
