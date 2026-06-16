"""
HR Interview scenario defaults and opening message.
"""

from __future__ import annotations
from typing import Dict

SCENARIO_CONFIG: Dict = {
    "company_type": "tech startup",
    "job_role": "Software Engineer",
    "difficulty": "mid-level",
    "question_style": "behavioral+technical",
    "num_questions": 8,
}


def get_opening_message(config: Dict | None = None) -> str:
    """Return the first message the AI interviewer should say."""
    cfg = {**SCENARIO_CONFIG, **(config or {})}
    return (
        f"Good morning! Thank you for coming in today. I'm the HR manager here "
        f"at our {cfg['company_type']}. We're looking to fill the "
        f"{cfg['job_role']} position — this will be a {cfg['difficulty']} level "
        f"interview covering {cfg['question_style']} questions. "
        f"Let's start — could you please introduce yourself and walk me "
        f"through your background?"
    )
