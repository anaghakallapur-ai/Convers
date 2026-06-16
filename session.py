"""
Session management endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import session_manager

router = APIRouter(prefix="/session", tags=["session"])


# ── Request / Response Models ─────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    scenario_type: str
    scenario_config: dict


class SessionResponse(BaseModel):
    session_id: str
    scenario_type: str
    scenario_config: dict
    history: list
    feedback_requested: bool
    metadata: dict


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/create", response_model=dict)
async def create_session(req: CreateSessionRequest):
    """Start a new conversation session."""
    session_id = session_manager.create_session(req.scenario_type, req.scenario_config)
    return {"session_id": session_id}


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Retrieve an active session by ID."""
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        session_id=session.session_id,
        scenario_type=session.scenario_type,
        scenario_config=session.scenario_config,
        history=session.history,
        feedback_requested=session.feedback_requested,
        metadata=session.metadata,
    )


@router.post("/{session_id}/end")
async def end_session(session_id: str):
    """End a session and return its final snapshot."""
    session = session_manager.end_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "scenario_type": session.scenario_type,
        "total_messages": len(session.history),
        "metadata": session.metadata,
    }


@router.get("/", response_model=dict)
async def list_sessions():
    """List all active session IDs."""
    ids = session_manager.list_active_sessions()
    return {"active_sessions": ids, "count": len(ids)}


@router.post("/cleanup")
async def cleanup_sessions():
    """Remove expired sessions."""
    removed = session_manager.cleanup_expired()
    return {"removed": removed}
