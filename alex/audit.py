"""Post-hoc scoring audit (sensitivity analysis).

The suite's scoring rules are pre-registered and stay the primary result. After a run, every
failed answer is read by a human; where a correct answer was rejected only because of its
wording, the missed phrasing is recorded here with the reason. `rescore` re-scores the STORED
answers with those additions (no model is called) so the report can show whether any
hypothesis verdict depends on the scorer's wording. Nothing here may make a wrong answer pass:
additions are phrasings of the same fact, and every addition is listed in the report.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

from .prompts import CASES

# case id -> (fact-group index, extra accepted phrasings, why)
ADDITIONS: dict[str, list[tuple[int, tuple[str, ...], str]]] = {
    "no_tool": [(0, ("above the risk-free rate", "over the risk-free rate", "for each unit of"),
                 "Claude Opus 5.5 defined the Sharpe ratio correctly as return above the risk-free rate "
                 "for each unit of volatility/risk, without the words 'excess', 'risk-adjusted' or "
                 "'per unit of'.")],
}


def audited_cases() -> dict[str, Any]:
    out = {}
    for c in CASES:
        facts = list(c.facts)
        for idx, extra, _ in ADDITIONS.get(c.id, []):
            facts[idx] = tuple(facts[idx]) + extra
        out[c.id] = replace(c, facts=tuple(facts))
    return out


def rescore(report: dict) -> tuple[dict, list[dict]]:
    """Copy of the report with every run re-scored under the audited cases, re-summarised and
    re-analysed; plus the list of runs whose verdict changed."""
    from .bench import summarize
    from .diagnose import diagnose
    from .scoring import score_case
    from .stats import analyze

    cases = audited_cases()
    rep = copy.deepcopy(report)
    changed = []
    for r in rep["runs"]:
        c = cases.get(r["case"])
        if c is None or r.get("error"):
            continue
        s = score_case(c, r["calls"], r.get("answer") or "")
        if s["passed"] != r["passed"]:
            changed.append({"key": r.get("key"), "case": r["case"], "answer": r.get("answer", ""),
                            "before": r["score"], "after": s["score"]})
        r.update(s)
        r["diagnosis"] = diagnose(c, r)
    for k in rep["summary"]:
        rep["summary"][k] = summarize([r for r in rep["runs"] if r.get("key") == k])
    rep.pop("analysis", None)
    rep["analysis"] = analyze(rep)
    return rep, changed
