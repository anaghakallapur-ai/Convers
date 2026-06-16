"""
Confidence scorer — combines sentiment, filler, and fluency results
into a single composite confidence score.
"""

from __future__ import annotations

from typing import Dict


# ── Label thresholds ─────────────────────────────────────────────────────────

def _label(score: float) -> str:
    """Map a 0–100 score to a human-readable confidence label."""
    if score >= 85:
        return "Excellent"
    if score >= 65:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


# ── Public API ───────────────────────────────────────────────────────────────

def compute_confidence_score(
    sentiment_result: Dict,
    filler_result: Dict,
    fluency_result: Dict,
) -> Dict:
    """
    Compute a composite confidence score from the three analysis modules.

    Formula
    -------
    ::

        sentiment_component = (mapped_score * 25 + 50)   →  0‑100 range
        fluency_component   = fluency_score               →  0‑100 range
        filler_component    = max(0, 100 - filler_rate*10) →  0‑100 range

        confidence = fluency   * 0.4
                   + sentiment * 0.3
                   + filler    * 0.3

    Args:
        sentiment_result: Output of ``sentiment.analyze_sentiment``.
        filler_result:    Output of ``filler_detector.detect_fillers``.
        fluency_result:   Output of ``fluency_scorer.score_fluency``.

    Returns:
        A dict with:
        - ``confidence_score`` — float 0–100
        - ``breakdown``        — per-component scores
        - ``label``            — ``"Low"`` / ``"Medium"`` / ``"High"`` / ``"Excellent"``
    """
    # ── Individual components ────────────────────────────────────────────
    mapped = sentiment_result.get("mapped_score", 0.0)
    sentiment_component = mapped * 25 + 50                          # → 0‑100
    sentiment_component = max(0.0, min(100.0, sentiment_component))

    fluency_component = fluency_result.get("fluency_score", 100.0)  # → 0‑100
    fluency_component = max(0.0, min(100.0, fluency_component))

    filler_rate = filler_result.get("filler_rate", 0.0)
    filler_component = max(0.0, 100.0 - filler_rate * 10)          # → 0‑100

    # ── Weighted composite ───────────────────────────────────────────────
    confidence = (
        fluency_component   * 0.4
        + sentiment_component * 0.3
        + filler_component    * 0.3
    )
    confidence = max(0.0, min(100.0, confidence))

    return {
        "confidence_score": round(confidence, 2),
        "breakdown": {
            "sentiment": round(sentiment_component, 2),
            "fluency": round(fluency_component, 2),
            "filler_penalty": round(100.0 - filler_component, 2),
        },
        "label": _label(confidence),
    }
