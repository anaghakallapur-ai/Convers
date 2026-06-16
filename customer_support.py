"""
Customer Support scenario defaults and opening message.
"""

from __future__ import annotations
from typing import Dict

SCENARIO_CONFIG: Dict = {
    "product": "cloud storage service",
    "issue_type": "billing discrepancy",
    "customer_mood": "frustrated",
    "escalation_level": "first contact",
}


def get_opening_message(config: Dict | None = None) -> str:
    """Return the first message the customer should say."""
    cfg = {**SCENARIO_CONFIG, **(config or {})}
    return (
        f"Hi, yes, I've been trying to sort this out for days now. "
        f"I'm calling about your {cfg['product']} — there's a "
        f"{cfg['issue_type']} on my last statement and nobody seems to "
        f"be able to help me. I'm honestly pretty {cfg['customer_mood']} "
        f"at this point. Can you actually fix this?"
    )
