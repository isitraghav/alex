"""Central config. Secrets & tunables come from .env (see .env.example)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM endpoint (NVIDIA NIM, OpenAI-compatible) ---
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # --- Bench ---
    # Comma-separated model ids to bench when --models is not given.
    bench_models: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    llm_temperature: float = 0.0     # constant, so runs are comparable
    llm_max_tokens: int = 4096
    llm_max_tool_turns: int = 8      # cap agentic loop iterations per prompt
    llm_max_retries: int = 6         # SDK retries w/ exponential backoff on 429 / 5xx / timeouts
    llm_timeout_s: float = 120.0
    request_delay_s: float = 0.0     # pause between cases; helps stay under free-tier rate limits
    results_dir: str = "results"

    # --- Live-mode data APIs (only used with `alex --live`; default is frozen fixtures) ---
    fred_api_key: str = ""
    finnhub_api_key: str = ""
    sec_user_agent: str = "alex/0.2 (contact@example.com)"  # SEC requires a contact


settings = Settings()
