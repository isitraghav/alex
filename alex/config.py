"""Central config. Secrets & tunables come from .env (see .env.example)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Claude API (console API key; a claude.ai Pro plan does not include API usage) ---
    anthropic_api_key: str = ""      # empty -> SDK default resolution (env var / `ant auth login`)

    # --- OpenRouter (alternative route to the same models; openrouter.ai -> Keys) ---
    openrouter_api_key: str = ""
    # OpenRouter model slugs - check with `alex --provider openrouter --list`
    openrouter_models: str = "anthropic/claude-haiku-5.5,anthropic/claude-sonnet-5.5,anthropic/claude-opus-5.5"

    # auto = Claude API if ANTHROPIC_API_KEY is set, else OpenRouter if OPENROUTER_API_KEY is set
    # claude-code = the local Claude Code CLI (`claude -p`) with its own login, e.g. a Pro plan
    llm_provider: str = "auto"       # auto | anthropic | openrouter | claude-code

    # --- Bench ---
    # Comma-separated model ids to bench when --models is not given.
    bench_models: str = "claude-haiku-5-5,claude-sonnet-5-5,claude-opus-5-5"
    llm_effort: str = "medium"       # low|medium|high|xhigh|max - same for every model so runs are comparable
    llm_max_tokens: int = 16000      # per response (thinking + answer); non-streaming safe ceiling
    llm_max_tool_turns: int = 8      # cap agentic loop iterations per prompt
    llm_max_retries: int = 6         # SDK retries w/ exponential backoff on 429 / 5xx / timeouts
    llm_timeout_s: float = 180.0
    cli_timeout_s: float = 120.0     # claude-code provider: one case; a stalled call is retried (max 3 tries)
    request_delay_s: float = 0.0     # pause between cases; helps stay under rate limits
    prompt_variant: str = "default"  # system prompt variant (see alex/prompts.py VARIANTS)
    results_dir: str = "results"

    # --- Live-mode data APIs (only used with `alex --live`; default is frozen fixtures) ---
    fred_api_key: str = ""
    finnhub_api_key: str = ""
    sec_user_agent: str = "alex/0.3 (contact@example.com)"  # SEC requires a contact

    # --- Knowledge graph (alex/kg.py). Frozen runs always use the in-memory seed graph. ---
    kg_backend: str = "memory"       # memory | neo4j (live mode, `alex-kg` CLI)
    kg_user_file: str = ".alex/kg_user.json"   # memory backend: the user's saved graph (seed + changes)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"


settings = Settings()
