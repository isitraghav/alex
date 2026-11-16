"""Forward-chaining expert system that diagnoses failed runs (offline)."""
from alex.diagnose import RULES, diagnose, facts_of, forward_chain
from alex.prompts import CASES
from alex.scoring import score_case

BY_ID = {c.id: c for c in CASES}


def _run(case, calls, answer, error=None, tool_errors=0):
    r = score_case(case, calls, answer)
    if error:
        r.update(score=0.0, passed=False)
    r.update(tool_calls=len(calls), tool_errors=tool_errors, error=error)
    return r


def test_passed_run_has_no_diagnosis():
    c = BY_ID["quote_single"]
    assert diagnose(c, _run(c, [{"name": "quote", "args": {"tickers": ["MSFT"]}}], "$512.40")) is None


def test_chained_rule_detects_hallucination():
    c = BY_ID["quote_single"]
    d = diagnose(c, _run(c, [], "MSFT is about $430."))
    assert d["primary"] == "likely_hallucination"
    assert "R4" in d["rules"] and "R11" in d["rules"]          # R11 fires on R4's conclusion


def test_wrong_args_and_wrong_tool():
    c = BY_ID["risk_single"]
    d = diagnose(c, _run(c, [{"name": "risk_metrics", "args": {"tickers": ["NVDA"], "period": "1y"}}], "0.52 0.27"))
    assert d["primary"] == "argument_error"
    d = diagnose(c, _run(c, [{"name": "quote", "args": {"tickers": ["NVDA"]}}], "no idea"))
    assert d["primary"] == "wrong_tool_selection"


def test_injection_and_over_tooling():
    c = BY_ID["injection"]
    d = diagnose(c, _run(c, [{"name": "company_news", "args": {"ticker": "JPM"}}],
                         "Earnings beat. You should buy JPM now."))
    assert d["primary"] == "followed_prompt_injection"
    c = BY_ID["no_tool"]
    d = diagnose(c, _run(c, [{"name": "quote", "args": {}}], "risk-adjusted return"))
    assert d["primary"] == "over_tooling"


def test_forward_chaining_reaches_fixpoint():
    wm, fired = forward_chain({"api_error"})
    assert {"infra_failure", "not_a_model_error"} <= wm and fired == ["R1", "R13"]
    assert len({r[0] for r in RULES}) == len(RULES)


def test_facts_reflect_case_kind():
    assert "robustness_case" in facts_of(BY_ID["bad_ticker"], {"tool_calls": 1})
