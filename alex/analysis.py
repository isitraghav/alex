"""Risk & correlation analytics on real price history.

All metrics are computed from daily log/simple returns of adjusted close.
Annualization uses 252 trading days. These are estimates from historical data,
NOT forward guarantees.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .sources import price_history

TRADING_DAYS = 252


def _returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna(how="all")


def risk_metrics(tickers: list[str], period: str = "1y",
                 benchmark: str = "SPY", rf_annual: float = 0.04) -> dict[str, Any]:
    """Per-ticker volatility, annualized return, Sharpe, max drawdown, VaR/CVaR,
    and beta vs benchmark. rf_annual = risk-free rate for Sharpe."""
    uniq = list(dict.fromkeys(tickers + [benchmark]))
    prices = price_history(uniq, period=period)
    if prices.empty:
        return {"error": "no price data returned"}
    rets = _returns(prices)
    rf_daily = rf_annual / TRADING_DAYS
    bench = rets[benchmark] if benchmark in rets else None

    out: dict[str, Any] = {}
    for t in tickers:
        if t not in rets or rets[t].dropna().empty:
            out[t] = {"error": "no data"}
            continue
        r = rets[t].dropna()
        ann_ret = float((1 + r).prod() ** (TRADING_DAYS / len(r)) - 1)
        ann_vol = float(r.std(ddof=1) * np.sqrt(TRADING_DAYS))
        sharpe = float((r.mean() - rf_daily) / r.std(ddof=1) * np.sqrt(TRADING_DAYS)) if r.std(ddof=1) else None
        curve = (1 + r).cumprod()
        max_dd = float((curve / curve.cummax() - 1).min())
        var95 = float(np.percentile(r, 5))            # 1-day historical VaR (5%)
        cvar95 = float(r[r <= var95].mean()) if (r <= var95).any() else var95
        beta = None
        if bench is not None:
            j = pd.concat([r, bench], axis=1, join="inner").dropna()
            if len(j) > 2 and j.iloc[:, 1].var(ddof=1):
                beta = float(j.cov().iloc[0, 1] / j.iloc[:, 1].var(ddof=1))
        out[t] = {
            "annual_return": ann_ret, "annual_volatility": ann_vol,
            "sharpe": sharpe, "max_drawdown": max_dd,
            "var_95_1d": var95, "cvar_95_1d": cvar95, "beta_vs_" + benchmark: beta,
            "observations": int(len(r)),
        }
    return {"period": period, "benchmark": benchmark, "metrics": out}


def correlation(tickers: list[str], period: str = "1y",
                method: str = "pearson") -> dict[str, Any]:
    """Return-correlation matrix + the most and least correlated pairs."""
    if len(tickers) < 2:
        return {"error": "need >=2 tickers for correlation"}
    prices = price_history(list(dict.fromkeys(tickers)), period=period)
    if prices.empty:
        return {"error": "no price data returned"}
    corr = _returns(prices).corr(method=method)
    # rank off-diagonal pairs
    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = corr.iloc[i, j]
            if pd.notna(v):
                pairs.append((cols[i], cols[j], float(v)))
    pairs.sort(key=lambda p: p[2], reverse=True)
    return {
        "period": period, "method": method,
        "matrix": corr.round(3).to_dict(),
        "most_correlated": pairs[:3],
        "least_correlated": pairs[-3:][::-1],
    }
