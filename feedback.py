"""
Feedback endpoints — request and retrieve conversation feedback / analytics.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import session_manager

router = APIRouter(prefix="/feedback", tags=["feedback"])


# ── Request / Response Models ─────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    session_id: str


class FeedbackResponse(BaseModel):
    session_id: str
    scenario_type: str
    total_messages: int
    metadata: dict
    feedback: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/request", response_model=FeedbackResponse)
async def request_feedback(req: FeedbackRequest):
    """
    Generate feedback for a conversation session.
    (Detailed analysis will be added in a later module.)
    """
    session = session_manager.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.feedback_requested = True

    # Placeholder: real feedback analysis will be wired later
    feedback_text = (
        f"Session '{session.session_id}' for scenario '{session.scenario_type}' "
        f"has {len(session.history)} messages. Detailed feedback pending."
    )

    return FeedbackResponse(
        session_id=session.session_id,
        scenario_type=session.scenario_type,
        total_messages=len(session.history),
        metadata=session.metadata,
        feedback=feedback_text,
    )
