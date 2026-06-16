"""
TTS / STT endpoints — text-to-speech and speech-to-text stubs.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/voice", tags=["tts_stt"])


# ── Request / Response Models ─────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str
    language: str = "en"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    """
    Convert text to speech audio.
    (pyttsx3 / audio generation will be wired in a later module.)
    """
    return {
        "status": "pending",
        "message": "TTS integration not yet implemented.",
        "text": req.text,
        "language": req.language,
    }


@router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    """
    Convert uploaded audio to text.
    (Whisper integration will be wired in a later module.)
    """
    if not audio.content_type or not audio.content_type.startswith("audio"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an audio file.")

    return {
        "status": "pending",
        "message": "STT integration not yet implemented.",
        "filename": audio.filename,
    }
