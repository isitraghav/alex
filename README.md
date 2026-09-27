# alex — agentic financial analysis terminal

NVIDIA NIM LLM + free data (yfinance, FRED, SEC EDGAR, Finnhub) + risk/correlation
analytics, persisting to **Postgres** (analysis history) and **Neo4j**
(ticker/sector/correlation graph). CLI + FastAPI.

## What it does

You ask in plain English; the LLM plans and calls local tools for **real** data,
then answers with citations. Tools:

| tool | source | output |
|---|---|---|
| `quote` / `fundamentals` | yfinance | price, ratios, sector, beta |
| `risk_metrics` | yfinance history | vol, ann. return, Sharpe, max drawdown, VaR/CVaR(95%), beta vs SPY |
| `correlation` | yfinance history | return-corr matrix + most/least correlated pairs |
| `fred_series` | FRED | macro series (CPI, GDP, INDPRO, DGS10, …) |
| `sec_filings` | SEC EDGAR | 10-K/10-Q/8-K links |
| `company_news` | Finnhub | recent headlines |
| `news_sentiment` | Finnhub + **Laya** | headlines classified bullish/bearish/neutral, net sentiment, market-moving prob (local, calibrated, free) |

Risk & correlation results are written to Postgres; correlation edges and sectors
to Neo4j (`(:Ticker)-[:CORRELATED]->(:Ticker)`, `(:Ticker)-[:IN_SECTOR]->(:Sector)`).

## Setup

```bash
cp .env.example .env      # fill NVIDIA_API_KEY (required); FRED/FINNHUB optional
uv sync --extra dev
docker compose up -d postgres neo4j     # start the databases
uv run pytest             # offline math checks
uv run alex               # CLI REPL   (needs NVIDIA_API_KEY)
uv run alex-api           # REST API on :8000

uv sync --extra laya      # optional: local Laya classifier for news_sentiment (~3GB torch)
```

Laya note: `news_sentiment` uses the base Laya checkpoint zero-shot — treat scores
as directional, not ground truth. Fine-tune on labelled finance headlines (Laya
docs) for real accuracy. First call downloads ~800MB.

Full stack in Docker (app + both DBs):

```bash
docker compose up --build
# API on http://localhost:8000  (POST /ask, GET /risk?tickers=AAPL,MSFT)
```

Neo4j browser: http://localhost:7474 (neo4j / fintelpass).

## Keys (all free)

- **NVIDIA_API_KEY** — build.nvidia.com (required for the agent)
- **FRED_API_KEY** — fred.stlouisfed.org/docs/api/api_key.html (macro)
- **FINNHUB_API_KEY** — finnhub.io (news)
- **SEC_USER_AGENT** — any real contact string (SEC requires it; no key)

`.env` is gitignored. Never hardcode keys in `config.py` — it commits to git.

## Notes / ceilings

- Storage is best-effort (`STORAGE_BEST_EFFORT`): agent runs with DBs down.
- Risk metrics are historical estimates, not forward guarantees.
- Document parsing (Docling/Tesseract), WebSocket streaming, and 10-K RAG are
  **not** in this cut — `sec_filings` returns links only. Add when needed.
- Session memory in the API is in-process; move to Redis for multi-worker.
```
