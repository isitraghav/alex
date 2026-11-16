"""LLM clients (Claude API direct, or OpenRouter) + per-model pricing.

Two providers, one benchmark:
  anthropic   - official Anthropic SDK, Messages API (ANTHROPIC_API_KEY)
  openrouter  - OpenRouter's OpenAI-compatible endpoint (OPENROUTER_API_KEY);
                Claude models are addressed as e.g. "anthropic/claude-sonnet-5.5"
Results from both are keyed by the canonical model id (claude-sonnet-5-5) so they
stay comparable; each run also records which provider served it.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# USD per million tokens (input, output) - Claude API list prices.
# Haiku 5.5's rate applies to prompts up to 100K tokens; every suite prompt is far below that.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def canonical(model: str) -> str:
    """'anthropic/claude-sonnet-5.5' -> 'claude-sonnet-5-5'; direct ids pass through."""
    return model.split("/")[-1].replace(".", "-")


def provider() -> str:
    """Explicit LLM_PROVIDER wins; 'auto' prefers a Claude API key, else OpenRouter."""
    p = settings.llm_provider.lower()
    if p in ("anthropic", "openrouter", "claude-code"):
        return p
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.openrouter_api_key:
        return "openrouter"
    return "anthropic"  # SDK may still find credentials (env var / `ant auth login`)


def default_models(prov: str) -> str:
    return settings.openrouter_models if prov == "openrouter" else settings.bench_models


@lru_cache(maxsize=2)
def client(prov: str | None = None) -> Any:
    prov = prov or provider()
    if prov == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set - put it in .env")
        from openai import OpenAI
        return OpenAI(api_key=settings.openrouter_api_key, base_url=OPENROUTER_BASE_URL,
                      max_retries=settings.llm_max_retries, timeout=settings.llm_timeout_s)
    import anthropic
    # max_retries: the SDK backs off exponentially (honouring retry-after) on 429/5xx/timeouts,
    # so a rate limit slows a run down instead of zeroing cases.
    kw: dict[str, Any] = {"max_retries": settings.llm_max_retries, "timeout": settings.llm_timeout_s}
    if settings.anthropic_api_key:
        kw["api_key"] = settings.anthropic_api_key
    return anthropic.Anthropic(**kw)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    p = PRICES.get(canonical(model))
    if p is None:
        return None
    return (input_tokens * p[0] + output_tokens * p[1]) / 1_000_000
