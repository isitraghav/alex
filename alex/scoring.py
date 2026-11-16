"""Rule-based scoring of one case run. Pure functions, no network."""
from __future__ import annotations

import re
from typing import Any

from .prompts import Case

W_TOOLS, W_ARGS, W_ANSWER = 0.4, 0.3, 0.3


def _flat(v: Any) -> list[str]:
    if isinstance(v, (list, tuple, set)):
        return [s for x in v for s in _flat(x)]
    return [str(v).strip().lower()]


def _norm(text: str) -> str:
    return re.sub(r"(?<=\d),(?=\d)", "", text.lower())  # 1,234 -> 1234


def score_tools(case: Case, calls: list[dict]) -> float:
    used = {c["name"] for c in calls}
    if case.no_tools:
        return 0.0 if calls else 1.0
    if not case.tools:
        return 1.0
    return sum(t in used for t in case.tools) / len(case.tools)


def score_args(case: Case, calls: list[dict]) -> float | None:
    if not case.args:
        return None
    ok = 0
    for tool, arg, mode, values in case.args:
        seen = [c["args"].get(arg) for c in calls if c["name"] == tool and arg in c["args"]]
        if mode == "has":
            have = {s for v in seen for s in _flat(v)}
            ok += bool(seen) and all(v.lower() in have for v in values)
        else:  # eq
            ok += any(values[0].lower() in _flat(v) for v in seen)
    return ok / len(case.args)


def score_answer(case: Case, answer: str) -> float | None:
    if not case.facts and not case.forbid:
        return None
    text = _norm(answer)
    if case.forbid and re.search(case.forbid, answer):
        return 0.0
    if not case.facts:
        return 1.0
    hit = sum(any(_norm(alt) in text for alt in alts) for alts in case.facts)
    return hit / len(case.facts)


def score_case(case: Case, calls: list[dict], answer: str) -> dict[str, Any]:
    parts = {"tools": (score_tools(case, calls), W_TOOLS),
             "args": (score_args(case, calls), W_ARGS),
             "answer": (score_answer(case, answer), W_ANSWER)}
    live = {k: v for k, v in parts.items() if v[0] is not None}
    total_w = sum(w for _, w in live.values())
    score = sum(s * w for s, w in live.values()) / total_w
    return {
        "tools": parts["tools"][0], "args": parts["args"][0], "answer": parts["answer"][0],
        "score": round(score, 4), "passed": all(s == 1.0 for s, _ in live.values()),
    }
