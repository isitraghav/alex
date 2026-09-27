"""Tool registry for the agent: OpenAI-style function schemas + a dispatch map.

Each tool wraps a source/analysis function and (where useful) persists results
to Postgres/Neo4j as a side effect, so the graph & history build up as the
agent works.
"""
from __future__ import annotations

from typing import Any, Callable

from . import analysis, sentiment, sources, storage


# ---- thin wrappers that also persist ----
def _risk(tickers: list[str], period: str = "1y") -> dict[str, Any]:
    res = analysis.risk_metrics(tickers, period=period)
    storage.save_analysis("risk", tickers, res)
    return res


def _corr(tickers: list[str], period: str = "1y") -> dict[str, Any]:
    res = analysis.correlation(tickers, period=period)
    if "most_correlated" in res:
        storage.upsert_correlations(period, res["most_correlated"] + res["least_correlated"])
    storage.save_analysis("correlation", tickers, res)
    return res


def _fund(ticker: str) -> dict[str, Any]:
    res = sources.fundamentals(ticker)
    storage.tag_sector(ticker, res.get("sector"))
    return res


# name -> (callable, json schema)
DISPATCH: dict[str, Callable[..., Any]] = {
    "quote": lambda tickers: sources.quote(tickers),
    "fundamentals": _fund,
    "risk_metrics": _risk,
    "correlation": _corr,
    "fred_series": lambda series_id, limit=24: sources.fred_series(series_id, limit),
    "sec_filings": lambda ticker, form="10-K", count=5: sources.sec_filings(ticker, form, count),
    "company_news": lambda ticker, days=7: sources.company_news(ticker, days),
    "news_sentiment": lambda ticker, days=7: sentiment.news_sentiment(ticker, days),
}

_STR = {"type": "string"}
_TICKERS = {"type": "array", "items": {"type": "string"}, "description": "Ticker symbols, e.g. ['AAPL','MSFT']"}


def _tool(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


SCHEMAS = [
    _tool("quote", "Latest price, day range, market cap for tickers.",
          {"tickers": _TICKERS}, ["tickers"]),
    _tool("fundamentals", "Key ratios & profile (sector, PE, beta, margins, ROE) for one ticker.",
          {"ticker": _STR}, ["ticker"]),
    _tool("risk_metrics",
          "Volatility, annual return, Sharpe, max drawdown, 1-day VaR/CVaR(95%), beta vs SPY from price history.",
          {"tickers": _TICKERS, "period": {**_STR, "description": "yfinance period e.g. 6mo,1y,2y,5y"}},
          ["tickers"]),
    _tool("correlation",
          "Return-correlation matrix across tickers + most/least correlated pairs. Needs >=2 tickers.",
          {"tickers": _TICKERS, "period": _STR}, ["tickers"]),
    _tool("fred_series",
          "Latest observations of a FRED macro series id (CPIAUCSL, GDP, INDPRO, DGS10, UNRATE, ...).",
          {"series_id": _STR, "limit": {"type": "integer"}}, ["series_id"]),
    _tool("sec_filings",
          "Recent SEC EDGAR filings (10-K/10-Q/8-K) links for a US ticker.",
          {"ticker": _STR, "form": _STR, "count": {"type": "integer"}}, ["ticker"]),
    _tool("company_news", "Recent company news headlines (Finnhub).",
          {"ticker": _STR, "days": {"type": "integer"}}, ["ticker"]),
    _tool("news_sentiment",
          "Classify recent headlines (Laya, calibrated) into bullish/bearish/neutral with a net "
          "sentiment score and market-moving probability. Use for news-driven sentiment/risk.",
          {"ticker": _STR, "days": {"type": "integer"}}, ["ticker"]),
]
