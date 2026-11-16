"""Fuzzy-logic rating of a benched model (Mamdani inference, centroid defuzzification).

A raw score alone hides trade-offs: a model at 0.95 that takes 25 s and 5 cents per
answer is not obviously "better" than one at 0.90 that takes 2 s and a tenth of a
cent. This module turns three
crisp measurements into one 0-100 *suitability* plus a linguistic label:

  accuracy  mean rule-based score (0-1)        low | medium | high
  latency   mean seconds per case              fast | moderate | slow
  cost      mean US$ per case (API list price) cheap | moderate | expensive
  ->
  suitability (0-100)                          poor | fair | good | excellent

Pure Python, no dependencies, deterministic.
"""
from __future__ import annotations

from typing import Callable

INF = float("inf")
MF = Callable[[float], float]


def tri(a: float, b: float, c: float) -> MF:
    def f(x: float) -> float:
        if x == b:
            return 1.0
        if x <= a or x >= c:
            return 0.0
        return (x - a) / (b - a) if x < b else (c - x) / (c - b)
    return f


def trap(a: float, b: float, c: float, d: float) -> MF:
    def f(x: float) -> float:
        if b <= x <= c:
            return 1.0
        if x <= a or x >= d:
            return 0.0
        return (x - a) / (b - a) if x < b else (d - x) / (d - c)
    return f


# ------------------------------------------------------------- fuzzy sets ----
ACCURACY = {"low": trap(-1, 0, 0.5, 0.72), "medium": tri(0.6, 0.8, 0.93),
            "high": trap(0.85, 0.95, 1.0, 2.0)}
LATENCY = {"fast": trap(-1, 0, 3, 6), "moderate": tri(4, 9, 16),
           "slow": trap(12, 20, INF, INF)}
COST = {"cheap": trap(-1, 0, 0.003, 0.01), "moderate": tri(0.005, 0.02, 0.05),
        "expensive": trap(0.03, 0.08, INF, INF)}
DEFAULT_COST = 0.02  # used when a model's price is unknown (neutral: fully "moderate")
SUITABILITY = {"poor": tri(-1, 0, 40), "fair": tri(25, 50, 75),
               "good": tri(55, 75, 92), "excellent": tri(80, 100, 101)}

# (antecedents {variable: term}, consequent term). AND = min, rules OR'd by max.
RULES: tuple[tuple[dict[str, str], str], ...] = (
    ({"accuracy": "low"}, "poor"),
    ({"accuracy": "medium", "latency": "fast"}, "good"),
    ({"accuracy": "medium", "latency": "moderate"}, "fair"),
    ({"accuracy": "medium", "latency": "slow"}, "poor"),
    ({"accuracy": "high", "latency": "fast"}, "excellent"),
    ({"accuracy": "high", "latency": "moderate"}, "good"),
    ({"accuracy": "high", "latency": "slow"}, "fair"),
    ({"accuracy": "high", "cost": "cheap"}, "excellent"),
    ({"accuracy": "medium", "cost": "cheap"}, "fair"),
    ({"cost": "expensive"}, "fair"),
)

_INPUTS = {"accuracy": ACCURACY, "latency": LATENCY, "cost": COST}


def fuzzify(accuracy: float, latency: float, cost: float | None) -> dict[str, dict[str, float]]:
    crisp = {"accuracy": accuracy, "latency": latency, "cost": DEFAULT_COST if cost is None else cost}
    return {v: {t: round(f(crisp[v]), 4) for t, f in sets.items()} for v, sets in _INPUTS.items()}


def rate(accuracy: float, latency: float, cost: float | None) -> dict[str, object]:
    """Crisp inputs -> {"suitability": 0-100, "label": term, "fired": {term: strength}}."""
    mu = fuzzify(accuracy, latency, cost)
    fired: dict[str, float] = {t: 0.0 for t in SUITABILITY}
    for ante, out in RULES:
        strength = min(mu[v][t] for v, t in ante.items())
        fired[out] = max(fired[out], strength)
    # Mamdani: clip each output set at its strength, aggregate by max, take centroid.
    num = den = 0.0
    for i in range(0, 1001):
        x = i / 10
        m = max(min(fired[t], f(x)) for t, f in SUITABILITY.items())
        num += x * m
        den += m
    value = round(num / den, 1) if den else 0.0
    label = max(SUITABILITY, key=lambda t: SUITABILITY[t](value))
    return {"suitability": value, "label": label,
            "fired": {t: round(s, 3) for t, s in fired.items() if s > 0}}
