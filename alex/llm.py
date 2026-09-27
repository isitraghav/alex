"""NVIDIA NIM client. NIM is OpenAI-compatible, so we reuse the openai SDK
pointed at integrate.api.nvidia.com/v1."""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from .config import settings


@lru_cache(maxsize=1)
def client() -> OpenAI:
    if not settings.nvidia_api_key:
        raise RuntimeError("NVIDIA_API_KEY not set — put it in .env")
    return OpenAI(api_key=settings.nvidia_api_key, base_url=settings.nvidia_base_url)
