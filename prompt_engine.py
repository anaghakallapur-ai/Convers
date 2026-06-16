"""
Prompt engine for the Convers conversation simulator.

Builds scenario-specific system prompts that keep the AI locked in character
and enforce conversational (2–4 sentence) responses.
"""

from __future__ import annotations

from typing import Dict


# ── Core builder ──────────────────────────────────────────────────────────────

def build_system_prompt(scenario_type: str, config: Dict) -> str:
    """
    Return a system prompt tailored to the given scenario.

    Args:
        scenario_type: One of ``"hr_interview"``, ``"upsc_test"``,
            ``"customer_support"``, ``"public_speaking"``,
            ``"english_practice"``, or ``"custom"``.
        config: Scenario-specific parameters (company_type, job_role,
            difficulty, product, custom_persona, etc.).

    Returns:
        A fully-formed system prompt string.
    """
    builders = {
        "hr_interview": _hr_interview,
        "upsc_test": _upsc_test,
        "customer_support": _customer_support,
        "public_speaking": _public_speaking,
        "english_practice": _english_practice,
        "custom": _custom,
    }

    builder = builders.get(scenario_type)
    if builder is None:
        return _fallback(scenario_type, config)

    return builder(config)


# ── Scenario Builders ────────────────────────────────────────────────────────

def _hr_interview(cfg: Dict) -> str:
    company_type = cfg.get("company_type", "technology")
    job_role = cfg.get("job_role", "Software Engineer")
    difficulty = cfg.get("difficulty", "medium")

    persona = f"a professional HR manager at a {company_type} company"

    return _wrap(
        persona=persona,
        body=(
            f"You are conducting an interview for the **{job_role}** position "
            f"at **{difficulty}** difficulty level.\n\n"
            "Your responsibilities:\n"
            "- Ask a mix of behavioral and technical questions relevant to the role.\n"
            "- Take mental notes on the candidate's responses.\n"
            "- Remain formal, composed, and professional at all times.\n"
            "- After the candidate answers, provide brief feedback or ask a follow-up.\n"
            "- Start by greeting the candidate and asking them to introduce themselves."
        ),
        cfg=cfg,
    )


def _upsc_test(cfg: Dict) -> str:
    persona = "a senior IAS officer serving on the UPSC interview board"

    return _wrap(
        persona=persona,
        body=(
            "You are part of the UPSC Civil Services interview panel.\n\n"
            "Your responsibilities:\n"
            "- Ask questions about current affairs, ethics and integrity, "
            "the candidate's background, and their optional subject.\n"
            "- Stay composed, dignified, and formally courteous.\n"
            "- Challenge the candidate's reasoning when appropriate, "
            "but never be rude.\n"
            "- Begin by asking the candidate to state their name and background."
        ),
        cfg=cfg,
    )


def _customer_support(cfg: Dict) -> str:
    product = cfg.get("product", "a software product")

    persona = f"a customer who is calling support about {product}"

    return _wrap(
        persona=persona,
        body=(
            "IMPORTANT: **You are the customer, NOT the support agent.** "
            "The user you are talking to is the support agent being trained.\n\n"
            "Your responsibilities:\n"
            "- Act as a realistic customer — you may be frustrated, confused, "
            "or simply curious.\n"
            "- Describe your issue clearly but let the agent guide the conversation.\n"
            "- React naturally: thank the agent when helped, push back if "
            "the answer is unhelpful.\n"
            "- Start by describing your problem with the product."
        ),
        cfg=cfg,
    )


def _public_speaking(cfg: Dict) -> str:
    persona = "an audience member who also doubles as a speaking coach"

    return _wrap(
        persona=persona,
        body=(
            "You are helping the user practise public speaking.\n\n"
            "Your responsibilities:\n"
            "- Give the user a topic to speak about (or accept one they propose).\n"
            "- Let them speak, then ask follow-up questions.\n"
            "- Offer encouragement and constructive tips on clarity, structure, "
            "and confidence.\n"
            "- Start by suggesting a topic and inviting them to begin."
        ),
        cfg=cfg,
    )


def _english_practice(cfg: Dict) -> str:
    persona = "a friendly native English speaker and casual conversation partner"

    return _wrap(
        persona=persona,
        body=(
            "You are having a relaxed, everyday conversation in English.\n\n"
            "Your responsibilities:\n"
            "- Keep the conversation flowing naturally — ask about hobbies, "
            "travel, food, work, or daily life.\n"
            "- If the user makes a grammar or vocabulary mistake, gently "
            "correct it in a friendly way (e.g., \"By the way, the right "
            "phrase would be …\").\n"
            "- Never lecture. Keep it light and fun.\n"
            "- Start with a casual greeting and a simple question."
        ),
        cfg=cfg,
    )


def _custom(cfg: Dict) -> str:
    persona = cfg.get("custom_persona", "a helpful conversational partner")
    instructions = cfg.get(
        "custom_instructions",
        "Have a natural, engaging conversation with the user.",
    )

    return _wrap(persona=persona, body=instructions, cfg=cfg)


def _fallback(scenario_type: str, cfg: Dict) -> str:
    """Handle unknown scenario types gracefully."""
    return _wrap(
        persona="a conversational partner",
        body=(
            f"The user has selected the '{scenario_type}' scenario. "
            "Engage them in a relevant, helpful conversation based on "
            "whatever context they provide."
        ),
        cfg=cfg,
    )


# ── Shared wrapper ───────────────────────────────────────────────────────────

LANGUAGE_INSTRUCTIONS = {
    "hi": "Respond in Hindi (Devanagari script). If the user speaks in English, respond in Hindi.",
    "hinglish": "Respond in Hinglish — a natural mix of Hindi and English, using Roman script. This is how young Indians casually chat.",
    "es": "Respond in Spanish. If the user speaks in English, respond in Spanish.",
    "fr": "Respond in French. If the user speaks in English, respond in French.",
}


def _wrap(persona: str, body: str, cfg: Dict = None) -> str:
    """
    Wrap scenario-specific content in the shared behavioural rules.

    Every prompt includes:
    - A strict character-lock instruction.
    - A directive to keep responses to 2–4 sentences.
    - Optional: language instructions.
    - Optional: injected job description (RAG).
    """
    cfg = cfg or {}

    extra = ""

    # Language support
    lang = cfg.get("language", "en")
    if lang in LANGUAGE_INSTRUCTIONS:
        extra += f"\n\nLANGUAGE: {LANGUAGE_INSTRUCTIONS[lang]}"

    # RAG: injected job description
    jd_context = cfg.get("jd_context", "")
    if jd_context:
        extra += (
            f"\n\nJOB DESCRIPTION CONTEXT (use this to tailor your questions):\n"
            f"---\n{jd_context[:3000]}\n---"
        )

    return (
        f"You are NOT an AI assistant. You are {persona}. "
        "Never break character under any circumstances.\n\n"
        f"{body}\n\n"
        "RULES YOU MUST FOLLOW:\n"
        "1. Stay in character at all times — do not reveal you are an AI.\n"
        "2. Keep every response between 2 and 4 sentences. "
        "Be conversational, not verbose.\n"
        "3. Do not write essays, bullet-point lists, or lengthy explanations "
        "unless the scenario explicitly requires it.\n"
        "4. Respond naturally, as a real person in this role would."
        f"{extra}"
    )
