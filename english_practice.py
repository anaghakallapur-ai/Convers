"""
English Practice scenario defaults and opening message.
"""

from __future__ import annotations
from typing import Dict

SCENARIO_CONFIG: Dict = {
    "level": "intermediate",
    "topic_preference": "daily life and hobbies",
    "correction_style": "gentle",
    "conversation_tone": "casual and friendly",
}


def get_opening_message(config: Dict | None = None) -> str:
    """Return the first message the conversation partner should say."""
    cfg = {**SCENARIO_CONFIG, **(config or {})}
    return (
        f"Hey there! Nice to meet you! I'm here to have a nice, "
        f"{cfg['conversation_tone']} chat with you in English. We can talk "
        f"about anything — {cfg['topic_preference']}, whatever you like! "
        f"If you make any mistakes, I'll gently point them out so you can "
        f"improve. So, how's your day going?"
    )
