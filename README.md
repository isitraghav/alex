# alex — LLM tool-use benchmark

Benches LLMs (NVIDIA NIM, OpenAI-compatible) on a **constant suite of 13 prompts**
that require calling financial-data tools. Each run is scored by rules — no LLM
judge — and written to `results/` as JSON + Markdown.

## What is measured

Per prompt (`alex/prompts.py`), weighted score:

| part | weight | checks |
|---|---|---|
| tools | 0.4 | required tools called; `no_tool` case must call none |
| args | 0.3 | correct tickers / series id / form / period / days |
| answer | 0.3 | final answer contains the fixture values; no invented numbers on error cases |

Plus latency (avg/p95), tokens, tool calls, API errors. `pass` = every part perfect.
With `--repeats N` each model also gets `score_sd` and `consistency` (share of cases whose
pass/fail verdict never flips across repeats).

**Fuzzy rating** (`alex/fuzzy.py`): accuracy, latency and token use are fuzzified
(low/medium/high, fast/moderate/slow, lean/moderate/heavy), run through 10 Mamdani rules
and defuzzified by centroid into a 0–100 *suitability* with a label
(poor / fair / good / excellent). It answers "which model should I actually use?" when
the raw score alone hides a slow or token-hungry model.
Cases: prices, risk, macro, filings, news, multi-tool, no-tool reasoning, bad-ticker robustness.

**Frozen by default:** tools return deterministic fixtures (`alex/fixtures.py`), so every
model sees identical data and results are reproducible. `--live` uses real yfinance /
FRED / SEC / Finnhub instead (answers then can't be fact-checked against fixtures).
Reports carry a `suite_hash`; only compare runs with the same hash. Temperature is 0.

Tools: `quote`, `fundamentals`, `risk_metrics`, `correlation`, `fred_series`,
`sec_filings`, `company_news`.

## Run

```bash
cp .env.example .env            # set NVIDIA_API_KEY (FRED/FINNHUB only for --live)
uv sync --extra dev
uv run pytest                   # offline checks of scoring + runner
uv run alex                     # bench BENCH_MODELS from .env
uv run alex --models nvidia/nemotron-3.5-lightning-30b-a3b,nvidia/nemotron-3-ultra-550b-a55b
uv run alex --cases quote_single,bad_ticker --repeats 3
uv run alex --list              # models the endpoint serves
uv run alex --show-cases        # print the prompt suite
uv run alex --leaderboard       # rank models across all saved reports of this suite
uv run alex --delay 2           # pause between cases to stay under rate limits
```

Docker:

```bash
docker compose build
docker compose run --rm bench                       # reports appear in ./results
docker compose run --rm bench --models a,b --repeats 3
```

## Notes

- Some listed NIM models 404 on chat (e.g. `nemotron-3-super-120b-a12b` at time of writing);
  such a model scores 0 with the error recorded rather than crashing the run.
- Adding/changing a case changes `suite_hash` — re-bench all models afterwards.
- HTTP 429 / 5xx are retried with exponential backoff (`LLM_MAX_RETRIES`, default 6) so a
  rate-limited free tier slows a run down instead of zeroing cases.
- `.env` is gitignored. Never hardcode keys.
- `report/` holds the project report (`alex_LLM_Tool_Use_Benchmark_Report.docx`).
