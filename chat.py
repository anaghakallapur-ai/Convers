"""
Chat endpoints — handles sending messages and receiving AI responses.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import session_manager

router = APIRouter(prefix="/chat", tags=["chat"])


# ── Request / Response Models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    history_length: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/send", response_model=ChatResponse)
async def send_message(req: ChatRequest):
    """
    Send a user message and receive an AI-generated reply.
    (LLM integration will be wired in a later module.)
    """
    session = session_manager.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Record the user message
    session_manager.append_message(req.session_id, "user", req.message)

    # Placeholder: actual Groq / LLM call will be added in the chat service
    assistant_reply = (
        f"[Placeholder] Received your message in scenario "
        f"'{session.scenario_type}'. LLM integration pending."
    )
    session_manager.append_message(req.session_id, "assistant", assistant_reply)

    return ChatResponse(
        reply=assistant_reply,
        history_length=len(session.history),
    )


@router.get("/{session_id}/history")
async def get_history(session_id: str):
    """Return the full message history for a session."""
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "history": session.history}
