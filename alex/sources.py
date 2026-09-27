"""Free data sources: prices/fundamentals (yfinance), macro (FRED),
filings (SEC EDGAR), news (Finnhub). Each returns plain JSON-able dicts so the
LLM agent can consume tool results directly.

Errors are returned as {"error": "..."} rather than raised — the agent decides
what to do; a single failing source never kills the loop.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import requests
import yfinance as yf

from .config import settings

_TIMEOUT = 20


def _err(e: Exception) -> dict[str, str]:
    return {"error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- prices ----
def price_history(tickers: list[str], period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Adjusted close price panel (columns = tickers). Used by analysis.
    Not an agent tool itself — analysis tools call it. Raises on total failure."""
    data = yf.download(
        tickers, period=period, interval=interval,
        auto_adjust=True, progress=False, group_by="column",
    )
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
    else:  # single ticker -> flat columns
        close = data[["Close"]].rename(columns={"Close": tickers[0]})
    return close.dropna(how="all")


def quote(tickers: list[str]) -> dict[str, Any]:
    """Latest price + day change + basic profile per ticker."""
    out: dict[str, Any] = {}
    for t in tickers:
        try:
            fi = yf.Ticker(t).fast_info
            out[t] = {
                "last": fi.get("last_price"),
                "prev_close": fi.get("previous_close"),
                "day_high": fi.get("day_high"),
                "day_low": fi.get("day_low"),
                "currency": fi.get("currency"),
                "market_cap": fi.get("market_cap"),
            }
        except Exception as e:  # noqa: BLE001 - per-ticker isolation
            out[t] = _err(e)
    return out


def fundamentals(ticker: str) -> dict[str, Any]:
    """Key ratios / profile from yfinance .info (best-effort, keys vary)."""
    try:
        info = yf.Ticker(ticker).info
    except Exception as e:  # noqa: BLE001
        return _err(e)
    keep = [
        "sector", "industry", "longName", "trailingPE", "forwardPE", "beta",
        "marketCap", "dividendYield", "profitMargins", "returnOnEquity",
        "debtToEquity", "revenueGrowth", "recommendationKey", "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
    ]
    return {k: info.get(k) for k in keep if k in info}


# ------------------------------------------------------------------ macro ----
def fred_series(series_id: str, limit: int = 24) -> dict[str, Any]:
    """Latest observations for a FRED macro series (e.g. CPIAUCSL, GDP, INDPRO, DGS10)."""
    if not settings.fred_api_key:
        return {"error": "FRED_API_KEY not set in .env"}
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id, "api_key": settings.fred_api_key,
                "file_type": "json", "sort_order": "desc", "limit": limit,
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        obs = [
            {"date": o["date"], "value": o["value"]}
            for o in r.json().get("observations", [])
            if o["value"] not in ("", ".")
        ]
        return {"series_id": series_id, "observations": obs}
    except Exception as e:  # noqa: BLE001
        return _err(e)


# --------------------------------------------------------------- filings ----
def _cik(ticker: str) -> str | None:
    r = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": settings.sec_user_agent}, timeout=_TIMEOUT,
    )
    r.raise_for_status()
    for row in r.json().values():
        if row["ticker"].upper() == ticker.upper():
            return str(row["cik_str"]).zfill(10)
    return None


def sec_filings(ticker: str, form: str = "10-K", count: int = 5) -> dict[str, Any]:
    """Recent SEC EDGAR filings of a form type for a US ticker (links only —
    parsing the document bodies is a separate/later concern)."""
    try:
        cik = _cik(ticker)
        if not cik:
            return {"error": f"no CIK for {ticker} (US SEC filers only)"}
        r = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers={"User-Agent": settings.sec_user_agent}, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        recent = r.json()["filings"]["recent"]
        rows = []
        for i, ftype in enumerate(recent["form"]):
            if ftype == form:
                acc = recent["accessionNumber"][i].replace("-", "")
                doc = recent["primaryDocument"][i]
                rows.append({
                    "form": ftype,
                    "filed": recent["filingDate"][i],
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}",
                })
                if len(rows) >= count:
                    break
        return {"ticker": ticker, "cik": cik, "filings": rows}
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ------------------------------------------------------------------ news ----
def company_news(ticker: str, days: int = 7) -> dict[str, Any]:
    """Recent company news headlines via Finnhub free tier."""
    if not settings.finnhub_api_key:
        return {"error": "FINNHUB_API_KEY not set in .env"}
    from datetime import date, timedelta

    to = date.today()
    frm = to - timedelta(days=days)
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": ticker, "from": frm.isoformat(), "to": to.isoformat(),
                "token": settings.finnhub_api_key,
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        items = [
            {"datetime": n["datetime"], "headline": n["headline"], "source": n["source"], "url": n["url"]}
            for n in r.json()[:20]
        ]
        return {"ticker": ticker, "news": items}
    except Exception as e:  # noqa: BLE001
        return _err(e)
