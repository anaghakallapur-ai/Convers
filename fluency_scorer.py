"""
Fluency scorer (runs locally via LanguageTool + Java).

Uses ``language_tool_python`` for grammar/spell checking and adds
vocabulary-richness and sentence-length metrics.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List

logger = logging.getLogger("convers.ml.fluency")

# ── Lazy-loaded LanguageTool instance ────────────────────────────────────────

_tool = None


def _get_tool():
    """Initialise LanguageTool on first use and cache it."""
    global _tool
    if _tool is None:
        import language_tool_python

        logger.info("Starting LanguageTool server (requires Java) …")
        _tool = language_tool_python.LanguageTool("en-US")
        logger.info("LanguageTool ready.")
    return _tool


# ── Helpers ──────────────────────────────────────────────────────────────────

_SENTENCE_SPLIT = re.compile(r"[.!?]+")


def _sentences(text: str) -> List[str]:
    """Split text into non-empty sentences."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


# ── Public API ───────────────────────────────────────────────────────────────

def score_fluency(text: str) -> Dict:
    """
    Score the fluency of a text string.

    Args:
        text: The user utterance to analyse.

    Returns:
        A dict with keys:
        - ``grammar_errors``      — number of issues found
        - ``error_details``       — list of ``{message, suggestions}``
        - ``fluency_score``       — 0–100 (100 = perfect)
        - ``avg_sentence_length`` — average words per sentence
        - ``vocabulary_richness`` — unique words / total words (0–1)
    """
    if not text or not text.strip():
        return {
            "grammar_errors": 0,
            "error_details": [],
            "fluency_score": 100.0,
            "avg_sentence_length": 0.0,
            "vocabulary_richness": 0.0,
        }

    tool = _get_tool()
    matches = tool.check(text)

    # Error details
    error_details: List[Dict] = [
        {
            "message": m.message,
            "suggestions": m.replacements[:3] if m.replacements else [],
        }
        for m in matches
    ]

    # Fluency score: penalise 5 points per error, floor at 0
    words = text.split()
    word_count = len(words)
    penalty_per_error = 5
    raw_score = 100 - len(matches) * penalty_per_error
    fluency_score = max(0.0, min(100.0, float(raw_score)))

    # Average sentence length
    sents = _sentences(text)
    if sents:
        avg_sentence_length = word_count / len(sents)
    else:
        avg_sentence_length = float(word_count)

    # Vocabulary richness (type-token ratio)
    unique_words = set(w.lower().strip(".,!?;:\"'()[]") for w in words)
    unique_words.discard("")
    vocabulary_richness = len(unique_words) / word_count if word_count else 0.0

    return {
        "grammar_errors": len(matches),
        "error_details": error_details,
        "fluency_score": round(fluency_score, 2),
        "avg_sentence_length": round(avg_sentence_length, 2),
        "vocabulary_richness": round(vocabulary_richness, 4),
    }
