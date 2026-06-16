"""
Feedback engine — post-session analysis combining ML modules + LLM narrative.

Runs sentiment, filler, fluency, and confidence analysis on every user message,
aggregates the results, then asks the LLM for structured coaching feedback.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.session_manager import SessionData
from core.groq_client import chat_completion
from ml.sentiment import analyze_sentiment
from ml.filler_detector import detect_fillers
from ml.fluency_scorer import score_fluency
from ml.confidence_scorer import compute_confidence_score

logger = logging.getLogger("convers.feedback_engine")


# ── Public API ───────────────────────────────────────────────────────────────

async def generate_feedback(session: SessionData) -> Dict:
    """
    Produce a comprehensive post-session feedback report.

    Steps
    -----
    1. Extract all **user** messages from the session history.
    2. Run each through sentiment, filler, and fluency analysers.
    3. Aggregate averages / totals.
    4. Ask the LLM (via Groq) for a structured coaching narrative.
    5. Return the combined result dict.

    Returns:
        A dict with ``overall_score``, per-category scores, strengths,
        improvements, an AI narrative, and raw ML stats.
    """

    # ── 1. Extract user messages ─────────────────────────────────────────
    user_messages: List[str] = [
        m["content"]
        for m in session.history
        if m.get("role") == "user"
    ]

    if not user_messages:
        return _empty_feedback()

    # ── 2. Per-message analysis ──────────────────────────────────────────
    sentiment_results: List[Dict] = []
    filler_results: List[Dict] = []
    fluency_results: List[Dict] = []
    confidence_results: List[Dict] = []

    for msg in user_messages:
        s = analyze_sentiment(msg)
        f = detect_fillers(msg)
        fl = score_fluency(msg)
        c = compute_confidence_score(s, f, fl)

        sentiment_results.append(s)
        filler_results.append(f)
        fluency_results.append(fl)
        confidence_results.append(c)

    # ── 3. Aggregate stats ───────────────────────────────────────────────
    n = len(user_messages)

    avg_sentiment = round(
        sum(r["mapped_score"] for r in sentiment_results) / n, 4
    )
    total_fillers = sum(r["filler_count"] for r in filler_results)
    avg_filler_rate = round(
        sum(r["filler_rate"] for r in filler_results) / n, 2
    )
    avg_fluency = round(
        sum(r["fluency_score"] for r in fluency_results) / n, 2
    )
    avg_confidence = round(
        sum(r["confidence_score"] for r in confidence_results) / n, 2
    )
    total_grammar_errors = sum(
        r["grammar_errors"] for r in fluency_results
    )
    avg_vocab_richness = round(
        sum(r["vocabulary_richness"] for r in fluency_results) / n, 4
    )

    # Collect the most common grammar error messages
    all_errors: List[str] = []
    for r in fluency_results:
        for e in r.get("error_details", []):
            all_errors.append(e["message"])
    common_errors = _top_n(all_errors, 5)

    # All fillers found across messages
    all_fillers: List[str] = []
    for r in filler_results:
        all_fillers.extend(r["fillers_found"])

    stats = {
        "avg_sentiment": avg_sentiment,
        "total_fillers": total_fillers,
        "avg_filler_rate": avg_filler_rate,
        "avg_fluency": avg_fluency,
        "avg_confidence": avg_confidence,
        "total_grammar_errors": total_grammar_errors,
        "avg_vocabulary_richness": avg_vocab_richness,
        "common_errors": common_errors,
        "total_user_messages": n,
    }

    # ── 4. Build transcript & ask LLM for narrative ──────────────────────
    transcript = _build_transcript(session.history)

    system_prompt = (
        "You are an expert communication coach. "
        "Be constructive, specific, and encouraging. "
        "Always give actionable advice."
    )

    user_prompt = (
        "Analyze this conversation transcript and give structured feedback.\n\n"
        f"SCENARIO: {session.scenario_type}\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        f"AGGREGATE STATS:\n{_format_stats(stats)}\n\n"
        "Please provide:\n"
        "1. Strengths (bullet list)\n"
        "2. Areas to improve (bullet list)\n"
        "3. Specific examples from the transcript\n"
        "4. A score out of 10 for each category: "
        "Communication, Confidence, Grammar, Vocabulary, Relevance\n"
        "5. An overall score out of 10\n"
        "Keep it concise but thorough."
    )

    ai_narrative = await chat_completion(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        temperature=0.6,
    )

    # ── 5. Parse category scores from ML data ────────────────────────────
    #    (LLM narrative is free-text; ML scores are the reliable numbers)
    overall_score = round(avg_confidence / 10, 1)  # 0-10 scale

    categories = {
        "communication": {
            "score": round(avg_confidence / 10, 1),
            "feedback": f"Confidence score: {avg_confidence}/100. "
                        f"Filler rate: {avg_filler_rate} per 100 words.",
        },
        "confidence": {
            "score": round(avg_confidence / 10, 1),
            "feedback": _confidence_feedback(avg_confidence, total_fillers),
        },
        "grammar": {
            "score": round(avg_fluency / 10, 1),
            "feedback": f"{total_grammar_errors} grammar issues detected. "
                        f"Fluency score: {avg_fluency}/100.",
        },
        "vocabulary": {
            "score": round(avg_vocab_richness * 10, 1),
            "feedback": f"Vocabulary richness (type-token ratio): "
                        f"{avg_vocab_richness:.2%}.",
        },
        "relevance": {
            "score": round((avg_sentiment * 25 + 50) / 10, 1),
            "feedback": f"Average sentiment: {avg_sentiment} "
                        f"(positive engagement correlates with relevance).",
        },
    }

    strengths, improvements = _extract_bullet_points(
        avg_fluency, avg_confidence, total_fillers, avg_vocab_richness
    )

    return {
        "overall_score": overall_score,
        "categories": categories,
        "strengths": strengths,
        "improvements": improvements,
        "ai_narrative": ai_narrative,
        "ml_stats": {
            "avg_sentiment": avg_sentiment,
            "total_fillers": total_fillers,
            "avg_fluency": avg_fluency,
            "avg_confidence": avg_confidence,
        },
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _empty_feedback() -> Dict:
    """Return a zeroed-out feedback dict when there are no user messages."""
    return {
        "overall_score": 0.0,
        "categories": {
            cat: {"score": 0.0, "feedback": "No data available."}
            for cat in ("communication", "confidence", "grammar",
                        "vocabulary", "relevance")
        },
        "strengths": [],
        "improvements": ["No user messages found in this session."],
        "ai_narrative": "No conversation data to analyse.",
        "ml_stats": {
            "avg_sentiment": 0.0,
            "total_fillers": 0,
            "avg_fluency": 0.0,
            "avg_confidence": 0.0,
        },
    }


def _build_transcript(history: List[Dict[str, str]]) -> str:
    """Format conversation history as a readable transcript."""
    lines: List[str] = []
    for msg in history:
        role = msg.get("role", "unknown").capitalize()
        lines.append(f"{role}: {msg.get('content', '')}")
    return "\n".join(lines)


def _format_stats(stats: Dict) -> str:
    """Pretty-print aggregate stats for the LLM prompt."""
    lines = [f"  {k}: {v}" for k, v in stats.items()]
    return "\n".join(lines)


def _top_n(items: List[str], n: int) -> List[str]:
    """Return the *n* most frequent items."""
    from collections import Counter
    return [item for item, _ in Counter(items).most_common(n)]


def _confidence_feedback(avg_confidence: float, total_fillers: int) -> str:
    """Generate a one-liner for the confidence category."""
    if avg_confidence >= 85:
        tone = "Excellent confidence level"
    elif avg_confidence >= 65:
        tone = "Good confidence"
    elif avg_confidence >= 40:
        tone = "Moderate confidence — room for improvement"
    else:
        tone = "Low confidence detected"
    return f"{tone}. Total filler words used: {total_fillers}."


def _extract_bullet_points(
    fluency: float,
    confidence: float,
    fillers: int,
    vocab: float,
) -> tuple[List[str], List[str]]:
    """Derive rule-based strengths and improvements from ML scores."""
    strengths: List[str] = []
    improvements: List[str] = []

    if fluency >= 80:
        strengths.append("Strong grammar and sentence structure.")
    else:
        improvements.append(
            "Work on grammar — consider reviewing common error patterns."
        )

    if confidence >= 70:
        strengths.append("Good overall confidence in responses.")
    else:
        improvements.append(
            "Build confidence by practising structured responses."
        )

    if fillers <= 3:
        strengths.append("Minimal use of filler words — very clean speech.")
    else:
        improvements.append(
            f"Reduce filler words (used {fillers} total). "
            "Pause instead of saying 'um' or 'like'."
        )

    if vocab >= 0.6:
        strengths.append("Rich and varied vocabulary.")
    else:
        improvements.append(
            "Expand vocabulary — try using synonyms and more precise terms."
        )

    return strengths, improvements
