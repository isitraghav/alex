"""The tool set the benched model can call: OpenAI-style function schemas plus
two interchangeable backends:

  * frozen (default) — deterministic fixtures, identical for every model/run
  * live             — real yfinance / FRED / SEC EDGAR / Finnhub data
"""
from __future__ import annotations

from typing import Any, Callable

Dispatch = dict[str, Callable[..., Any]]


def live_dispatch() -> Dispatch:
    from . import analysis, sources  # lazy: frozen mode needs no network libs
    return {
        "quote": lambda tickers: sources.quote(tickers),
        "fundamentals": lambda ticker: sources.fundamentals(ticker),
        "risk_metrics": lambda tickers, period="1y": analysis.risk_metrics(tickers, period=period),
        "correlation": lambda tickers, period="1y": analysis.correlation(tickers, period=period),
        "fred_series": lambda series_id, limit=24: sources.fred_series(series_id, limit),
        "sec_filings": lambda ticker, form="10-K", count=5: sources.sec_filings(ticker, form, count),
        "company_news": lambda ticker, days=7: sources.company_news(ticker, days),
    }


def frozen_dispatch() -> Dispatch:
    from . import fixtures
    return dict(fixtures.DISPATCH)


_STR = {"type": "string"}
_TICKERS = {"type": "array", "items": {"type": "string"},
            "description": "Ticker symbols, e.g. ['AAPL','MSFT']"}


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
    _tool("company_news", "Recent company news headlines.",
          {"ticker": _STR, "days": {"type": "integer"}}, ["ticker"]),
]
