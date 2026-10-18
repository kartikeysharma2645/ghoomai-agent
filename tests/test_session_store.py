"""Tests for the in-memory session store."""

from __future__ import annotations

from app.session_store import INITIAL_SESSION, SessionStore


def test_new_conversation_receives_initial_session() -> None:
    """A new conversation should initialize with the documented session structure."""
    store = SessionStore()
    session = store.initialize("conv-1")

    assert session == INITIAL_SESSION
    assert session["sessionVersion"] == 1
    assert session["transcript"] == []
    assert session["tripStatus"] == "DRAFT"


def test_different_conversation_ids_are_independent() -> None:
    """Different conversation IDs must not share session state."""
    store = SessionStore()
    store.initialize("conv-a")
    store.initialize("conv-b")

    session_a = store.get("conv-a")
    session_b = store.get("conv-b")

    assert session_a is not session_b  # different objects
    assert session_a == session_b      # same initial contents

    # Mutating one must not affect the other.
    session_a["tripStatus"] = "BOOKED"
    assert store.get("conv-b")["tripStatus"] == "DRAFT"


def test_updated_session_is_persisted() -> None:
    """Updating a session should persist the returned session state."""
    store = SessionStore()
    store.initialize("conv-1")

    updated = {
        "sessionVersion": 1,
        "transcript": [{"role": "user", "content": "hello"}],
        "tripStatus": "DRAFT",
    }
    store.update("conv-1", updated)

    retrieved = store.get("conv-1")
    assert retrieved == updated


def test_reset_conversation() -> None:
    """Resetting a conversation should restore the initial session."""
    store = SessionStore()
    store.initialize("conv-1")
    store.update(
        "conv-1",
        {
            "sessionVersion": 1,
            "transcript": [{"role": "user", "content": "hello"}],
            "tripStatus": "BOOKED",
        },
    )

    reset_session = store.reset("conv-1")
    assert reset_session == INITIAL_SESSION
    assert store.get("conv-1") == INITIAL_SESSION


def test_get_unknown_conversation_returns_none() -> None:
    """Retrieving a nonexistent conversation should return None."""
    store = SessionStore()
    assert store.get("does-not-exist") is None


def test_update_unknown_conversation_raises() -> None:
    """Updating a nonexistent conversation should raise KeyError."""
    store = SessionStore()
    try:
        store.update("unknown", INITIAL_SESSION)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError for unknown conversation")
