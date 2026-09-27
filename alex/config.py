"""Central config. All secrets & tunables from .env (see .env.example)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM (NVIDIA NIM, OpenAI-compatible cloud) ---
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3-super-120b-a12b"  # live NIM model w/ tool calling
    llm_temperature: float = 0.2
    llm_max_tool_turns: int = 8  # cap agentic loop iterations

    # --- Laya query prefilter (needs the `laya` extra; fails open if absent) ---
    laya_prefilter: bool = True          # classify query intent before the LLM call
    prefilter_threshold: float = 0.6     # min confidence to reject an off-topic query

    # Show the agent's reasoning + tool calls live (CLI) / in the API response.
    show_trace: bool = True

    # --- Free data APIs ---
    fred_api_key: str = ""       # set in .env (loaded automatically), not here
    finnhub_api_key: str = ""    # https://finnhub.io free tier
    # SEC EDGAR requires a descriptive User-Agent (their rule), not a key.
    sec_user_agent: str = "alex/0.1 (contact@example.com)"

    # --- Storage ---
    postgres_dsn: str = "postgresql://fintel:fintel@localhost:5432/fintel"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "fintelpass"

    # If a DB is unreachable, keep running (analysis still works) instead of crashing.
    storage_best_effort: bool = True


settings = Settings()
