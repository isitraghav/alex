"""Laya query prefilter: classify a user request's intent BEFORE the (slow, paid)
NVIDIA LLM call. Two wins:

  1. Reject clearly off-topic requests cheaply, without burning an LLM turn.
  2. Pass the detected category as a hint so the model picks tools faster.

Fails open: if Laya isn't installed / fails to load, or prefilter is disabled,
`prefilter` returns on_topic=True with no category — the agent runs normally.
"""
from __future__ import annotations

from typing import Any

from .config import settings

_Q = {
    "category": {
        "type": "choice",
        "instructions": "Classify this request to a financial-analysis terminal by topic.",
        "criteria": {
            "prices": "stock price, quote, valuation, or fundamentals of a company",
            "risk": "volatility, correlation, drawdown, beta, VaR, portfolio risk analytics",
            "macro": "macroeconomic indicators: inflation, GDP, interest rates, unemployment",
            "filings": "SEC filings, 10-K, 10-Q, 8-K, annual or quarterly report",
            "news": "news headlines or sentiment about a company",
            "off_topic": "not about financial markets, economics, or companies",
        },
    },
}


def _confidence(ans: dict) -> float:
    """Probability of the chosen label. NOTE: Laya's top-level `confidence` is a
    calibration margin, not the class prob — use `answer_confidence` /
    probabilities[choice] instead."""
    v = ans.get("answer_confidence")
    if isinstance(v, (int, float)):
        return float(v)
    probs = ans.get("probabilities") or ans.get("probs")
    if isinstance(probs, dict) and ans.get("choice") in probs:
        return float(probs[ans["choice"]])
    if isinstance(probs, dict) and probs:
        return float(max(probs.values()))
    return 1.0


def prefilter(question: str) -> dict[str, Any]:
    if not settings.laya_prefilter:
        return {"enabled": False, "on_topic": True}
    try:
        from .sentiment import router
        ans = router().predict({"query": question}, _Q)["answers"]["category"]
    except Exception as e:  # noqa: BLE001 - laya missing / load failed -> fail open
        return {"enabled": False, "on_topic": True, "error": str(e)}
    cat = ans.get("choice", "prices")
    conf = _confidence(ans)
    return {
        "enabled": True, "category": cat, "confidence": round(conf, 3),
        "on_topic": cat != "off_topic",
    }
