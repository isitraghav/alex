"""The constant benchmark suite. Edit deliberately: any change alters SUITE_HASH,
which is stamped on every report so results from different suites aren't compared.

Each case declares what a correct run looks like, scored by rules (no LLM judge):
  tools      tools that must be called          (no_tools=True: none may be called)
  args       argument checks over all calls to a tool
  facts      each entry = alternatives; one must appear in the final answer
  forbid     regex that must NOT appear in the final answer (hallucination guard)
Fact values come from alex/fixtures.py (frozen mode).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

SYSTEM = (
    "You are a financial analyst assistant with access to market-data tools. "
    "Use the tools to fetch real data; never invent prices, ratios, macro values or "
    "filing dates. If a tool returns an error, say so plainly. If the question needs "
    "no data, answer directly without calling tools. Be concise and quantitative."
)


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    prompt: str
    tools: tuple[str, ...] = ()
    no_tools: bool = False
    # (tool, arg, "has"|"eq", values): "has" = every value appears in that arg
    # (case-insensitive) across calls; "eq" = some call has arg == value.
    args: tuple[tuple[str, str, str, tuple[str, ...]], ...] = ()
    facts: tuple[tuple[str, ...], ...] = ()
    forbid: str = ""


CASES: tuple[Case, ...] = (
    Case("quote_single", "prices", "What is the latest price of MSFT?",
         tools=("quote",), args=(("quote", "tickers", "has", ("MSFT",)),),
         facts=(("512.4",),)),
    Case("quote_multi", "prices", "Give me current prices for AAPL, NVDA and TSLA.",
         tools=("quote",), args=(("quote", "tickers", "has", ("AAPL", "NVDA", "TSLA")),),
         facts=(("338.32",), ("187.65",), ("421.15",))),
    Case("fundamentals", "prices", "What sector is JPM in and what is its trailing P/E ratio?",
         tools=("fundamentals",), args=(("fundamentals", "ticker", "eq", ("JPM",)),),
         facts=(("financial services",), ("15.4",))),
    Case("risk_single", "risk",
         "How risky is NVDA? Give me its annual volatility and max drawdown over the last 2 years.",
         tools=("risk_metrics",),
         args=(("risk_metrics", "tickers", "has", ("NVDA",)), ("risk_metrics", "period", "eq", ("2y",))),
         facts=(("0.52", "52%"), ("0.27", "27%"))),
    Case("risk_compare", "risk",
         "Compare the 1-year Sharpe ratios of TSLA and AAPL. Which one is better?",
         tools=("risk_metrics",), args=(("risk_metrics", "tickers", "has", ("TSLA", "AAPL")),),
         facts=(("0.62",), ("1.05",))),
    Case("correlation", "risk",
         "How correlated are AAPL, MSFT and NVDA? Which pair moves together the most?",
         tools=("correlation",), args=(("correlation", "tickers", "has", ("AAPL", "MSFT", "NVDA")),),
         facts=(("0.79",),)),
    Case("macro_cpi", "macro", "What is the latest CPI reading from FRED?",
         tools=("fred_series",), args=(("fred_series", "series_id", "eq", ("CPIAUCSL",)),),
         facts=(("327.8",),)),
    Case("macro_rate", "macro", "What is the current 10-year Treasury yield?",
         tools=("fred_series",), args=(("fred_series", "series_id", "eq", ("DGS10",)),),
         facts=(("4.21",),)),
    Case("filings", "filings", "Link me the most recent 10-K filing for AAPL.",
         tools=("sec_filings",),
         args=(("sec_filings", "ticker", "eq", ("AAPL",)), ("sec_filings", "form", "eq", ("10-K",))),
         facts=(("2025-10-31",),)),
    Case("news", "news", "Summarize the latest news headlines for TSLA from the past 3 days.",
         tools=("company_news",),
         args=(("company_news", "ticker", "eq", ("TSLA",)), ("company_news", "days", "eq", ("3",))),
         facts=(("robotaxi",),)),
    Case("multi_tool", "multi",
         "Is NVDA more volatile than the market? Also give me its current price and trailing P/E.",
         tools=("risk_metrics", "quote", "fundamentals"),
         args=(("quote", "tickers", "has", ("NVDA",)), ("fundamentals", "ticker", "eq", ("NVDA",))),
         facts=(("187.65",), ("52.8",), ("1.68", "1.7"))),
    Case("no_tool", "reasoning", "In one sentence, what does the Sharpe ratio measure?",
         no_tools=True, facts=(("risk-adjusted", "risk adjusted", "excess return", "per unit of"),)),
    Case("bad_ticker", "robustness", "What is the current price of ZZZZQ?",
         tools=("quote",), args=(("quote", "tickers", "has", ("ZZZZQ",)),),
         facts=(("no data", "not found", "unable", "couldn't", "could not", "unavailable",
                 "invalid", "error", "doesn't appear", "not available", "no price", "no pricing",
                 "doesn't exist", "does not exist", "isn't available", "sorry", "cannot", "can't",
                 "no market data", "is not available", "delisted"),),
         forbid=r"\$\s?\d"),
)

SUITE_HASH = hashlib.sha256(
    json.dumps([asdict(c) for c in CASES] + [SYSTEM], sort_keys=True).encode()
).hexdigest()[:10]
