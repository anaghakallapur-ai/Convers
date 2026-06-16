"""
Offline text-to-speech engine using pyttsx3.

No internet required — uses the OS-native speech synthesis backend
(SAPI5 on Windows, NSSpeechSynthesizer on macOS, espeak on Linux).
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from typing import Dict, List, Optional

import pyttsx3

logger = logging.getLogger("convers.voice.tts_engine")

# ── Lazy-loaded engine ───────────────────────────────────────────────────────

_engine: pyttsx3.Engine | None = None


def _get_engine() -> pyttsx3.Engine:
    """Initialise the pyttsx3 engine on first use and cache it."""
    global _engine
    if _engine is None:
        logger.info("Initialising pyttsx3 TTS engine …")
        _engine = pyttsx3.init()
        # Sensible defaults
        _engine.setProperty("rate", 175)
        _engine.setProperty("volume", 1.0)
        logger.info("TTS engine ready.")
    return _engine


# ── Public API ───────────────────────────────────────────────────────────────

def text_to_speech(text: str, output_path: Optional[str] = None) -> bytes:
    """
    Convert *text* to speech audio (WAV).

    Args:
        text: The text to synthesise.
        output_path: If provided, the WAV file is also saved here.

    Returns:
        The raw WAV audio bytes.
    """
    engine = _get_engine()

    # Always render to a temp file first, then read the bytes
    tmp_path: str | None = None
    try:
        if output_path:
            target = output_path
        else:
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            target = tmp_path

        engine.save_to_file(text, target)
        engine.runAndWait()

        with open(target, "rb") as f:
            audio_bytes = f.read()

        return audio_bytes

    finally:
        # Clean up temp file only if we created one
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def get_available_voices() -> List[Dict]:
    """
    List every voice installed on the host OS.

    Returns:
        A list of dicts, each with ``id``, ``name``, and ``language``.
    """
    engine = _get_engine()
    voices = engine.getProperty("voices")
    return [
        {
            "id": v.id,
            "name": v.name,
            "language": getattr(v, "languages", [b"unknown"])[0]
                        if getattr(v, "languages", None) else "unknown",
        }
        for v in voices
    ]


def set_voice_properties(
    rate: int = 175,
    volume: float = 1.0,
    voice_id: Optional[str] = None,
) -> None:
    """
    Adjust the TTS engine properties.

    Args:
        rate: Words per minute (default 175).
        volume: Volume level 0.0 – 1.0 (default 1.0).
        voice_id: OS-specific voice identifier. Pass ``None`` to keep
            the current voice.
    """
    engine = _get_engine()
    engine.setProperty("rate", rate)
    engine.setProperty("volume", volume)
    if voice_id is not None:
        engine.setProperty("voice", voice_id)
