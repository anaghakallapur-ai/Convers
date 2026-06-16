"""
Filler-word detector (regex + word-list, no ML required).

Detects common conversational fillers and computes a filler rate
per 100 words.
"""

from __future__ import annotations

import re
from typing import Dict, List

# ── Filler word list (ordered longest-first for greedy matching) ──────────

FILLER_PHRASES: List[str] = sorted(
    [
        "um", "uh", "like", "you know", "basically", "literally",
        "actually", "so", "right", "I mean", "kind of", "sort of",
    ],
    key=len,
    reverse=True,
)

# Build a single compiled regex that matches any filler as a whole word.
# Longer phrases are tried first so "sort of" is matched before "sort".
_FILLER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in FILLER_PHRASES) + r")\b",
    re.IGNORECASE,
)


# ── Public API ───────────────────────────────────────────────────────────────

def detect_fillers(text: str) -> Dict:
    """
    Scan *text* for filler words / phrases.

    Args:
        text: The user utterance to analyse.

    Returns:
        A dict with keys:
        - ``filler_count``  — total number of filler occurrences
        - ``fillers_found`` — list of each filler occurrence (lowercased)
        - ``filler_rate``   — fillers per 100 words (float)
    """
    if not text or not text.strip():
        return {"filler_count": 0, "fillers_found": [], "filler_rate": 0.0}

    matches = _FILLER_PATTERN.findall(text)
    fillers_found = [m.lower() for m in matches]

    word_count = len(text.split())
    filler_rate = (len(fillers_found) / word_count * 100) if word_count else 0.0

    return {
        "filler_count": len(fillers_found),
        "fillers_found": fillers_found,
        "filler_rate": round(filler_rate, 2),
    }
