"""
In-memory session manager for the Convers conversation simulator.

Thread-safe, uses uuid4 for session IDs, and supports automatic cleanup
of sessions that exceed SESSION_TIMEOUT.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class SessionData:
    """Represents a single conversation session."""

    session_id: str
    scenario_type: str                          # e.g. "hr_interview", "upsc_test"
    scenario_config: dict                       # role, difficulty, context
    history: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    feedback_requested: bool = False
    metadata: dict = field(default_factory=dict) # filler count, avg sentiment, etc.


# ── Session Store ─────────────────────────────────────────────────────────────

_sessions: Dict[str, SessionData] = {}
_lock = threading.Lock()


def create_session(scenario_type: str, scenario_config: dict) -> str:
    """
    Create a new session and return its unique ID.

    Args:
        scenario_type: Category of the scenario (e.g. "hr_interview").
        scenario_config: Dict containing role, difficulty, context, etc.

    Returns:
        The newly generated session_id (uuid4 hex string).
    """
    session_id = uuid.uuid4().hex
    session = SessionData(
        session_id=session_id,
        scenario_type=scenario_type,
        scenario_config=scenario_config,
    )
    with _lock:
        _sessions[session_id] = session
    return session_id


def get_session(session_id: str) -> Optional[SessionData]:
    """
    Retrieve a session by its ID.

    Returns:
        The SessionData if found, otherwise None.
    """
    with _lock:
        return _sessions.get(session_id)


def append_message(session_id: str, role: str, content: str) -> bool:
    """
    Append a message to the session history.

    Automatically trims history to MAX_HISTORY (oldest messages removed first).

    Args:
        session_id: Target session.
        role: "user" or "assistant".
        content: The message text.

    Returns:
        True if the message was appended, False if the session was not found.
    """
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return False
        session.history.append({"role": role, "content": content})
        # Trim to MAX_HISTORY, keeping the most recent messages
        if len(session.history) > config.MAX_HISTORY:
            session.history = session.history[-config.MAX_HISTORY:]
        return True


def end_session(session_id: str) -> Optional[SessionData]:
    """
    End (remove) a session and return its final snapshot.

    Returns:
        The removed SessionData, or None if not found.
    """
    with _lock:
        return _sessions.pop(session_id, None)


def list_active_sessions() -> List[str]:
    """Return a list of all active session IDs."""
    with _lock:
        return list(_sessions.keys())


def cleanup_expired() -> int:
    """
    Remove sessions that have exceeded SESSION_TIMEOUT.

    Returns:
        The number of sessions removed.
    """
    now = datetime.now(timezone.utc)
    expired_ids: List[str] = []

    with _lock:
        for sid, session in _sessions.items():
            age = (now - session.created_at).total_seconds()
            if age > config.SESSION_TIMEOUT:
                expired_ids.append(sid)
        for sid in expired_ids:
            del _sessions[sid]

    return len(expired_ids)
