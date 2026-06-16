"""
Base scenario dispatcher.

Maps scenario type strings to their respective modules and provides
convenience functions for fetching default configs and opening messages.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Dict, Optional

# ── Registry ─────────────────────────────────────────────────────────────────

_SCENARIO_MAP: Dict[str, str] = {
    "hr_interview":     "scenarios.hr_interview",
    "upsc_test":        "scenarios.upsc_test",
    "customer_support": "scenarios.customer_support",
    "public_speaking":  "scenarios.public_speaking",
    "english_practice": "scenarios.english_practice",
}


def get_scenario_module(scenario_type: str) -> Optional[ModuleType]:
    """
    Dynamically import and return the module for *scenario_type*.

    Returns ``None`` if the scenario type is not registered.
    """
    module_path = _SCENARIO_MAP.get(scenario_type)
    if module_path is None:
        return None
    return importlib.import_module(module_path)


def get_default_config(scenario_type: str) -> Dict:
    """
    Return the default ``SCENARIO_CONFIG`` dict for a scenario.

    Falls back to an empty dict for unknown types.
    """
    mod = get_scenario_module(scenario_type)
    if mod is None:
        return {}
    return dict(getattr(mod, "SCENARIO_CONFIG", {}))


def get_opening(scenario_type: str, config: Dict | None = None) -> str:
    """
    Return the scenario's scripted opening message.

    Falls back to a generic greeting for unknown types.
    """
    mod = get_scenario_module(scenario_type)
    if mod is None:
        return (
            "Hello! I'm ready to start our conversation. "
            "Please go ahead whenever you're ready."
        )
    fn = getattr(mod, "get_opening_message", None)
    if fn is None:
        return "Hello! Let's get started."
    return fn(config)


def list_scenarios() -> list[Dict]:
    """
    Return metadata for every registered scenario.

    Each entry contains ``type``, ``label``, and ``default_config``.
    """
    _LABELS = {
        "hr_interview":     "HR Interview",
        "upsc_test":        "UPSC Mock Interview",
        "customer_support": "Customer Support Training",
        "public_speaking":  "Public Speaking Practice",
        "english_practice": "English Conversation Practice",
    }
    result = []
    for stype in _SCENARIO_MAP:
        result.append({
            "type": stype,
            "label": _LABELS.get(stype, stype.replace("_", " ").title()),
            "default_config": get_default_config(stype),
        })
    return result
