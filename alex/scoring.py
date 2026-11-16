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
    """Formatting-insensitive text for fact matching: 1,234 -> 1234; 52.0% / 52 % -> 52%;
    512.40 -> 512.4; a sentence-final period after a number is dropped."""
    t = re.sub(r"(?<=\d),(?=\d)", "", text.lower())
    t = re.sub(r"(?<=\d)\s+%", "%", t)
    t = re.sub(r"(\d\.\d*?)0+(?!\d)", r"\1", t)     # trailing decimal zeros
    return re.sub(r"(?<=\d)\.(?!\d)", "", t)          # "52." -> "52"


_KG_ARGS = {("kg_neighbors", "entity"), ("kg_path", "entities")}


def _arg_values(tool: str, arg: str, v: Any) -> list[str]:
    """Flattened, lower-cased argument values. Knowledge-graph entities are resolved to their
    canonical id first, so "NVIDIA" and "NVDA" count as the same (the graph treats them so)."""
    vals = _flat(v)
    if (tool, arg) in _KG_ARGS:
        from .kg import memory_graph
        g = memory_graph()
        vals = [(g.resolve(x) or {}).get("id", x).lower() for x in vals]
    return vals


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
        seen = [_arg_values(tool, arg, c["args"].get(arg))
                for c in calls if c["name"] == tool and arg in c["args"]]
        if mode == "has":
            have = {s for v in seen for s in v}
            ok += bool(seen) and all(v.lower() in have for v in values)
        else:  # eq: some call passes one of the accepted values
            ok += any(x.lower() in v for v in seen for x in values)
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
        "tools": parts["tools"][0], "args": parts["args"][0], "answer_score": parts["answer"][0],
        "forbidden_hit": bool(case.forbid and re.search(case.forbid, answer)),
        "score": round(score, 4), "passed": all(s == 1.0 for s, _ in live.values()),
    }
