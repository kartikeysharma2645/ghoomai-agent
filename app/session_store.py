"""In-memory session store for GhoomAI conversation state.

Sessions are stored in memory keyed by conversation ID. Because this is a
purely in-memory store, all session state is lost when the Python service
restarts. A persistent store (database, Redis, etc.) should be added before
production use.
"""

from __future__ import annotations

from typing import Dict, Optional

# Documented initial session structure for a new GhoomAI conversation.
INITIAL_SESSION: dict = {
    "sessionVersion": 1,
    "transcript": [],
    "tripStatus": "DRAFT",
}


class SessionStore:
    """Thread-safe in-memory store for GhoomAI session state."""

    def __init__(self) -> None:
        self._sessions: Dict[str, dict] = {}

    def get(self, conversation_id: str) -> Optional[dict]:
        """Retrieve the session state for a conversation.

        Returns a copy so callers cannot mutate internal state accidentally.
        Returns None if no session exists for the conversation ID.
        """
        session = self._sessions.get(conversation_id)
        if session is None:
            return None
        return dict(session)

    def initialize(self, conversation_id: str) -> dict:
        """Create a new conversation with the initial session structure.

        If a session already exists for the conversation ID, it is returned
        unchanged (no overwrite).
        """
        if conversation_id not in self._sessions:
            self._sessions[conversation_id] = dict(INITIAL_SESSION)
        return dict(self._sessions[conversation_id])

    def update(self, conversation_id: str, session_state: dict) -> None:
        """Replace the session state for a conversation.

        Raises:
            KeyError: If no session exists for the conversation ID.
        """
        if conversation_id not in self._sessions:
            raise KeyError(f"No session found for conversation: {conversation_id}")
        self._sessions[conversation_id] = dict(session_state)

    def reset(self, conversation_id: str) -> dict:
        """Reset a conversation to the initial session structure.

        Returns the freshly initialized session state.
        """
        self._sessions[conversation_id] = dict(INITIAL_SESSION)
        return dict(self._sessions[conversation_id])

    def contains(self, conversation_id: str) -> bool:
        """Return True if a session exists for the conversation ID."""
        return conversation_id in self._sessions

    def clear_all(self) -> None:
        """Remove all sessions. Primarily useful for testing."""
        self._sessions.clear()
