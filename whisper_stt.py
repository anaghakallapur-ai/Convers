"""
Whisper-based speech-to-text (runs 100 % locally, no API calls).

Uses the ``openai-whisper`` library with the ``base`` model for a good
speed / accuracy trade-off.  The model is downloaded and cached on
first load.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Dict

logger = logging.getLogger("convers.voice.whisper_stt")

# ── Lazy-loaded Whisper model ────────────────────────────────────────────────

_model = None
_MODEL_SIZE = "base"  # tiny | base | small | medium | large


def _get_model():
    """Load the Whisper model on first use and cache it in-process."""
    global _model
    if _model is None:
        import whisper

        logger.info("Loading Whisper model '%s' …", _MODEL_SIZE)
        _model = whisper.load_model(_MODEL_SIZE)
        logger.info("Whisper model loaded.")
    return _model


# ── Public API ───────────────────────────────────────────────────────────────

def transcribe_audio(audio_file_path: str) -> Dict:
    """
    Transcribe an audio file on disk.

    Args:
        audio_file_path: Absolute or relative path to the audio file
            (wav, mp3, m4a, webm, etc.).

    Returns:
        A dict with keys:
        - ``text``     — the transcribed text
        - ``language`` — detected language code (e.g. ``"en"``)
        - ``duration`` — audio duration in seconds (float)
    """
    model = _get_model()
    result = model.transcribe(audio_file_path)

    # Whisper doesn't expose duration directly; compute from segments
    segments = result.get("segments", [])
    if segments:
        duration = segments[-1].get("end", 0.0)
    else:
        duration = 0.0

    return {
        "text": result.get("text", "").strip(),
        "language": result.get("language", "unknown"),
        "duration": round(duration, 2),
    }


def transcribe_bytes(audio_bytes: bytes, fmt: str = "wav") -> Dict:
    """
    Transcribe raw audio bytes.

    Saves the bytes to a temporary file, runs transcription, then
    deletes the temp file.

    Args:
        audio_bytes: Raw audio data.
        fmt: File extension / format (default ``"wav"``).

    Returns:
        Same dict as :func:`transcribe_audio`.
    """
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=f".{fmt}")
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)
        return transcribe_audio(tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
