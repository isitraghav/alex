"""The post-hoc audit only accepts rephrasings of the same fact; wrong answers stay wrong."""
from alex.audit import ADDITIONS, audited_cases, rescore
from alex.prompts import CASES


def _rep(answer):
    run = {"key": "m@default", "case": "no_tool", "category": "reasoning", "calls": [], "answer": answer,
           "score": 0.57, "passed": False, "error": None, "latency_s": 1.0, "tokens": 1, "tool_calls": 0,
           "cost_usd": 0.0}
    return {"runs": [run], "summary": {"m@default": {}}, "variants": ["default"], "repeats": 1}


def test_rephrased_correct_answer_passes_after_audit():
    rep, changed = rescore(_rep("Return above the risk-free rate for each unit of volatility."))
    assert len(changed) == 1 and rep["runs"][0]["passed"]


def test_wrong_answer_still_fails_after_audit():
    rep, changed = rescore(_rep("It measures how big a company is."))
    assert not changed and not rep["runs"][0]["passed"]


def test_audit_only_extends_existing_fact_groups():
    base = {c.id: c for c in CASES}
    for cid, adds in ADDITIONS.items():
        new = audited_cases()[cid]
        for idx, _extra, why in adds:
            assert set(base[cid].facts[idx]) < set(new.facts[idx]) and why
        assert new.tools == base[cid].tools and new.forbid == base[cid].forbid
