"""
UPSC Interview scenario defaults and opening message.
"""

from __future__ import annotations
from typing import Dict

SCENARIO_CONFIG: Dict = {
    "board_type": "UPSC Civil Services",
    "optional_subject": "Public Administration",
    "candidate_background": "Engineering graduate",
    "focus_areas": "current affairs, ethics, governance",
    "num_questions": 10,
}


def get_opening_message(config: Dict | None = None) -> str:
    """Return the first message the UPSC board member should say."""
    cfg = {**SCENARIO_CONFIG, **(config or {})}
    return (
        f"Good morning. Please have a seat. This is your "
        f"{cfg['board_type']} interview panel. I can see from your dossier "
        f"that you have a background in {cfg['candidate_background']} and "
        f"your optional subject is {cfg['optional_subject']}. "
        f"Let's begin — please tell us your name, your hometown, and what "
        f"motivated you to pursue civil services."
    )
