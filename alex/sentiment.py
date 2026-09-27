"""News sentiment via Laya — a local, calibrated System-1 classifier (not an LLM).

Laya scores each headline in one forward pass with calibrated probabilities; no
API cost, runs offline after the first checkpoint download (~800MB). Optional:
install with `uv sync --extra laya`. If not installed, the tool returns an error
dict instead of raising, so the rest of the agent keeps working.

Caveat: Laya base checkpoints ship over-confident and are zero-shot here — treat
scores as directional signal, not ground truth. Fine-tune on labelled finance
headlines for real accuracy (see Laya docs).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from .sources import company_news

_QUESTIONS = {
    "sentiment": {
        "type": "choice",
        "instructions": "What is the sentiment of this financial news headline for the company's stock?",
        "criteria": {
            "bullish": "positive: growth, beats, upgrades, wins, expansion",
            "bearish": "negative: losses, misses, downgrades, lawsuits, cuts",
            "neutral": "no clear directional signal for the stock price",
        },
    },
    "market_moving": {
        "type": "noul",
        "instructions": "Is this headline material enough to move the stock price?",
    },
}


@lru_cache(maxsize=1)
def router():
    """Shared Laya Router (loaded once, reused by sentiment + routing prefilter)."""
    from laya import Router  # lazy: only import if a Laya tool is actually used
    return Router(preload=True)  # english + multilingual resident


_router = router  # backward-compat alias


def news_sentiment(ticker: str, days: int = 7) -> dict[str, Any]:
    """Fetch recent headlines (Finnhub) and classify each with Laya. Returns a
    per-class distribution, mean market-moving probability, and the strongest
    bullish/bearish headlines."""
    news = company_news(ticker, days)
    if "error" in news:
        return news
    heads = [n["headline"] for n in news.get("news", []) if n.get("headline")]
    if not heads:
        return {"ticker": ticker, "error": "no headlines"}

    try:
        rt = router()
    except Exception as e:  # noqa: BLE001 - laya not installed / load failed
        return {"error": f"laya unavailable ({type(e).__name__}: {e}); run `uv sync --extra laya`"}

    counts = {"bullish": 0, "bearish": 0, "neutral": 0}
    scored = []
    mm_sum = 0.0
    for h in heads:
        r = rt.predict({"headline": h}, _QUESTIONS)["answers"]
        label = r["sentiment"]["choice"]
        mm = float(r["market_moving"]["noul"])
        counts[label] = counts.get(label, 0) + 1
        mm_sum += mm
        scored.append({"headline": h, "sentiment": label, "market_moving": round(mm, 3)})

    n = len(heads)
    net = (counts["bullish"] - counts["bearish"]) / n  # -1 (all bearish) .. +1 (all bullish)
    scored.sort(key=lambda s: s["market_moving"], reverse=True)
    return {
        "ticker": ticker, "days": days, "headline_count": n,
        "distribution": counts,
        "net_sentiment": round(net, 3),
        "avg_market_moving": round(mm_sum / n, 3),
        "top_headlines": scored[:5],
        "note": "Laya zero-shot; directional signal, not ground truth.",
    }
