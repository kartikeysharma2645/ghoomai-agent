"""Integration boundary for the upcoming Fetch.ai Agent Chat Protocol (ACP) implementation.

This module is a placeholder that records the documented Fetch.ai SDK
imports and integration approach. No agent registration, ASI:One
discoverability, or message handling is implemented at this stage.

Official documentation sources reviewed:
  * uAgents Framework installation: https://uagents.fetch.ai/docs/getting-started/install
  * Fetch.ai Innovation Lab - Chat Protocol example:
    https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents
  * uAgents Core (PyPI): https://pypi.org/pypi/uagents-core

Documented imports (verified against uagents-core 0.4.12):

    from uagents_core.contrib.protocols.chat import (
        ChatAcknowledgement,
        ChatMessage,
        TextContent,
        chat_protocol_spec,
    )

Verified behavior:
    chat_protocol_spec.name    == "AgentChatProtocol"
    chat_protocol_spec.version == "0.3.0"

Distinction from the unrelated Agent Client Protocol (ACP):
    The Fetch.ai Agent Chat Protocol is a string-based chat protocol used
    by uAgents for agent-to-agent communication (expected format for
    ASI:One). The Agent Client Protocol (agentcommunicationprotocol.dev)
    is a separate, unrelated specification.

Planned integration steps (not implemented yet):
    1. Install/import uagents-core (done in requirements.txt).
    2. Define a uAgent with a seed phrase from configuration.
    3. Include the chat protocol (chat_protocol_spec) in the agent.
    4. Register message handlers for ChatMessage / ChatAcknowledgement.
    5. Optionally register the agent on Agentverse and connect to ASI:One.

No speculative protocol classes or method signatures are defined here.
"""


# Placeholder: the Fetch.ai agent instance will be constructed here once
# registration is implemented. Until then, this remains None to make the
# absence of an agent explicit rather than fabricating a mock.
AGENT = None

__all__ = ["AGENT"]
