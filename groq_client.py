"""
Groq LLM client for the Convers conversation simulator.

Provides async chat completion and streaming via the Groq Python SDK,
with exponential backoff on rate-limit errors and automatic model fallback.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, List, Dict

from groq import AsyncGroq, RateLimitError, APIError

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("convers.groq_client")
logging.basicConfig(level=logging.INFO)

# ── Constants ─────────────────────────────────────────────────────────────────

PRIMARY_MODEL: str = config.DEFAULT_MODEL          # llama3-70b-8192
FALLBACK_MODEL: str = "llama-4-scout-17b-16e-instruct"
MAX_RETRIES: int = 3
BASE_BACKOFF: float = 1.0  # seconds

# ── Client Singleton ──────────────────────────────────────────────────────────

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    """Lazily initialise and return the shared AsyncGroq client."""
    global _client
    if _client is None:
        if not config.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file or export it as an environment variable."
            )
        _client = AsyncGroq(api_key=config.GROQ_API_KEY)
    return _client


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_messages(
    messages: List[Dict[str, str]], system_prompt: str
) -> List[Dict[str, str]]:
    """Prepend the system prompt to the conversation messages."""
    return [{"role": "system", "content": system_prompt}] + list(messages)


# ── Chat Completion (non-streaming) ──────────────────────────────────────────

async def chat_completion(
    messages: List[Dict[str, str]],
    system_prompt: str,
    temperature: float = 0.8,
) -> str:
    """
    Send a chat completion request to Groq and return the assistant's reply.

    - Prepends ``system_prompt`` as the system message.
    - Retries up to ``MAX_RETRIES`` times on rate-limit errors with
      exponential backoff.
    - Falls back to ``FALLBACK_MODEL`` if the primary model errors out.

    Args:
        messages: Conversation history (list of role/content dicts).
        system_prompt: The system instruction for this scenario.
        temperature: Sampling temperature (0.0 – 2.0).

    Returns:
        The assistant message content as a plain string.
    """
    client = _get_client()
    full_messages = _build_messages(messages, system_prompt)

    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=512,
                )

                # Log token usage
                usage = response.usage
                if usage:
                    logger.info(
                        "Token usage  model=%s  prompt=%d  completion=%d  total=%d",
                        model,
                        usage.prompt_tokens,
                        usage.completion_tokens,
                        usage.total_tokens,
                    )

                return response.choices[0].message.content

            except RateLimitError as exc:
                wait = BASE_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    "Rate-limited (attempt %d/%d, model=%s). "
                    "Retrying in %.1fs …",
                    attempt, MAX_RETRIES, model, wait,
                )
                if attempt == MAX_RETRIES:
                    logger.error(
                        "Max retries reached for model=%s. Trying fallback …",
                        model,
                    )
                    break  # try next model
                await asyncio.sleep(wait)

            except APIError as exc:
                logger.error(
                    "Groq API error (model=%s): %s. Trying fallback …",
                    model, exc,
                )
                break  # try next model

    # If both models fail, return a graceful error message
    return (
        "I'm sorry, I'm temporarily unable to respond. "
        "Please try again in a moment."
    )


# ── General-Purpose Generation ───────────────────────────────────────────────

async def generate_response(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
) -> str:
    """
    General-purpose LLM call (non-streaming). Takes pre-built messages
    (including system prompt). Used by resume builder, RAG, etc.
    """
    client = _get_client()

    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=1024,
                )
                return response.choices[0].message.content
            except RateLimitError:
                wait = BASE_BACKOFF * (2 ** (attempt - 1))
                if attempt == MAX_RETRIES:
                    break
                await asyncio.sleep(wait)
            except APIError as exc:
                logger.error("generate_response error (model=%s): %s", model, exc)
                break

    return "Unable to generate response at this time."


# ── Streaming Chat ───────────────────────────────────────────────────────────

async def stream_chat(
    messages: List[Dict[str, str]],
    system_prompt: str,
    temperature: float = 0.8,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat completion from Groq, yielding text chunks as they arrive.

    Same retry / fallback logic as ``chat_completion``.

    Yields:
        Individual text chunks (strings) from the assistant's response.
    """
    client = _get_client()
    full_messages = _build_messages(messages, system_prompt)

    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                stream = await client.chat.completions.create(
                    model=model,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=512,
                    stream=True,
                )

                logger.info("Streaming started  model=%s", model)

                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

                return  # successful stream — exit generator

            except RateLimitError:
                wait = BASE_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    "Rate-limited during stream (attempt %d/%d, model=%s). "
                    "Retrying in %.1fs …",
                    attempt, MAX_RETRIES, model, wait,
                )
                if attempt == MAX_RETRIES:
                    break
                await asyncio.sleep(wait)

            except APIError as exc:
                logger.error(
                    "Groq API error during stream (model=%s): %s", model, exc,
                )
                break

    # Both models failed
    yield (
        "I'm sorry, I'm temporarily unable to respond. "
        "Please try again in a moment."
    )
