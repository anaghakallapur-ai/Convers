"""
Convers — Conversation Simulator API

Entry point for the FastAPI application.
Run with:  cd backend && uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import config

# ── Route imports ─────────────────────────────────────────────────────────────

from api.routes import session as api_session
from api.routes import chat as api_chat
from api.routes import feedback as api_feedback
from api.routes import tts_stt as api_voice
from api.routes import auth as api_auth
from api.routes import history as api_history
from api.routes import gamification as api_gamification
from api.routes import resume as api_resume
from api.routes import rag as api_rag

# ── Middleware import ─────────────────────────────────────────────────────────

from api.middleware import RequestLoggingMiddleware

# ── Scenario registry ────────────────────────────────────────────────────────

from scenarios.base_scenario import list_scenarios

logger = logging.getLogger("convers")
logging.basicConfig(level=logging.INFO)


# ── Model preloading (background thread) ─────────────────────────────────────

def _preload_models():
    """Load heavy ML models in a background thread at startup."""
    try:
        logger.info("⏳ Preloading sentiment model …")
        from ml.sentiment import _get_pipeline
        _get_pipeline()
        logger.info("✅ Sentiment model ready.")
    except Exception as exc:
        logger.warning("⚠️  Sentiment model preload failed: %s", exc)

    try:
        logger.info("⏳ Preloading Whisper model …")
        from voice.whisper_stt import _get_model
        _get_model()
        logger.info("✅ Whisper model ready.")
    except Exception as exc:
        logger.warning("⚠️  Whisper model preload failed: %s", exc)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # Init database
    import database
    database.init_db()
    logger.info("✅ Database initialized.")

    # Kick off model loading in a background thread so the server starts fast
    loader = threading.Thread(target=_preload_models, daemon=True)
    loader.start()
    logger.info("🚀 Convers API starting (model=%s)", config.DEFAULT_MODEL)
    yield
    logger.info("🛑 Convers API shutting down.")


# ── App Initialisation ───────────────────────────────────────────────────────

app = FastAPI(
    title="Convers API",
    description="Backend for the Convers conversation simulator.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Custom Middleware ─────────────────────────────────────────────────────────

app.add_middleware(RequestLoggingMiddleware)

# ── Routers (all under /api prefix) ──────────────────────────────────────────

app.include_router(api_session.router,  prefix="/api")
app.include_router(api_chat.router,     prefix="/api")
app.include_router(api_feedback.router, prefix="/api")
app.include_router(api_voice.router,    prefix="/api")
app.include_router(api_auth.router)
app.include_router(api_history.router)
app.include_router(api_gamification.router)
app.include_router(api_resume.router)
app.include_router(api_rag.router)


# ── Root & Health ─────────────────────────────────────────────────────────────

@app.get("/api/info", tags=["root"])
async def root():
    """API root — welcome message."""
    return {
        "app": "Convers",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Quick liveness / readiness probe."""
    return {"status": "ok", "model": config.DEFAULT_MODEL}


# ── Scenarios endpoint ────────────────────────────────────────────────────────

@app.get("/api/scenarios", tags=["scenarios"])
async def get_scenarios():
    """Return all available conversation scenarios with default configs."""
    return {"scenarios": list_scenarios()}


# ── Serve Frontend Static Files ──────────────────────────────────────────────

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


# ── Dev Server ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
