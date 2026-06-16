"""
Sentiment analysis module (runs locally).

Uses the ``cardiffnlp/twitter-roberta-base-sentiment-latest`` model via
the HuggingFace Transformers pipeline.  The model is downloaded and cached
on the first call.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger("convers.ml.sentiment")

# ── Lazy-loaded pipeline ─────────────────────────────────────────────────────

_pipeline = None
_MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"


def _get_pipeline():
    """Load the sentiment-analysis pipeline on first use and cache it."""
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline as hf_pipeline

        logger.info("Loading sentiment model: %s …", _MODEL_NAME)
        _pipeline = hf_pipeline(
            "sentiment-analysis",
            model=_MODEL_NAME,
            tokenizer=_MODEL_NAME,
            top_k=None,           # return scores for all labels
        )
        logger.info("Sentiment model loaded.")
    return _pipeline


# ── Label → numeric mapping ──────────────────────────────────────────────────

_LABEL_MAP: Dict[str, float] = {
    "positive": 1.0,
    "neutral":  0.0,
    "negative": -1.0,
}


# ── Public API ───────────────────────────────────────────────────────────────

def analyze_sentiment(text: str) -> Dict:
    """
    Analyse the sentiment of a single text string.

    Args:
        text: The user utterance to analyse.

    Returns:
        A dict with keys:
        - ``label``        — ``"positive"`` / ``"neutral"`` / ``"negative"``
        - ``score``        — model confidence for the winning label (0–1)
        - ``mapped_score`` — sentiment mapped to the range **-1 … +1**
    """
    if not text or not text.strip():
        return {"label": "neutral", "score": 0.0, "mapped_score": 0.0}

    pipe = _get_pipeline()
    results = pipe(text[:512])  # truncate to model max

    # ``top_k=None`` returns a list of lists; grab the inner list
    scores = results[0] if isinstance(results[0], list) else results

    # Find the label with the highest score
    best = max(scores, key=lambda x: x["score"])
    label = best["label"].lower()

    # Compute a continuous mapped score: weighted sum of all labels
    mapped_score = 0.0
    for entry in scores:
        lbl = entry["label"].lower()
        mapped_score += _LABEL_MAP.get(lbl, 0.0) * entry["score"]

    return {
        "label": label,
        "score": round(best["score"], 4),
        "mapped_score": round(mapped_score, 4),
    }
