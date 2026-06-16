"""
Public Speaking scenario defaults and opening message.
"""

from __future__ import annotations
from typing import Dict

SCENARIO_CONFIG: Dict = {
    "topic_category": "technology and society",
    "audience_size": "medium (50-100 people)",
    "speech_duration": "3-5 minutes",
    "style": "persuasive",
}


def get_opening_message(config: Dict | None = None) -> str:
    """Return the first message the speaking coach should say."""
    cfg = {**SCENARIO_CONFIG, **(config or {})}
    return (
        f"Welcome! I'm here to help you practise your public speaking skills. "
        f"Today, let's imagine you're addressing a {cfg['audience_size']} "
        f"audience. I'd like you to give a {cfg['style']} speech on the topic "
        f"of {cfg['topic_category']} — aim for about {cfg['speech_duration']}. "
        f"Take a moment to gather your thoughts, and whenever you're ready, "
        f"go ahead and begin."
    )
