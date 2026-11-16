"""Offline tests: scoring rules, fixtures, and the runner loop with a fake LLM client."""
import json
from types import SimpleNamespace as NS

from alex import fixtures
from alex.bench import run_case, summarize
from alex.prompts import CASES, SUITE_HASH
from alex.scoring import score_case

BY_ID = {c.id: c for c in CASES}


def test_suite_is_constant_and_unique():
    assert len({c.id for c in CASES}) == len(CASES)
    assert len(SUITE_HASH) == 10


def test_perfect_run_scores_one():
    r = score_case(BY_ID["quote_single"], [{"name": "quote", "args": {"tickers": ["MSFT"]}}],
                   "MSFT trades at $512.40.")
    assert r["score"] == 1.0 and r["passed"]


def test_wrong_tool_and_missing_fact_scores_zero():
    r = score_case(BY_ID["quote_single"], [{"name": "fundamentals", "args": {"ticker": "MSFT"}}], "unsure")
    assert r["score"] == 0.0 and not r["passed"]


def test_no_tool_case_penalises_any_call():
    c = BY_ID["no_tool"]
    ans = "It measures risk-adjusted return."
    assert score_case(c, [], ans)["passed"]
    assert not score_case(c, [{"name": "quote", "args": {}}], ans)["passed"]


def test_hallucinated_price_for_bad_ticker_fails():
    c = BY_ID["bad_ticker"]
    calls = [{"name": "quote", "args": {"tickers": ["ZZZZQ"]}}]
    assert score_case(c, calls, "No data found for ZZZZQ.")["passed"]
    assert not score_case(c, calls, "ZZZZQ trades at $12.50, no data otherwise.")["passed"]


def test_eq_arg_check():
    c = BY_ID["macro_rate"]
    good = [{"name": "fred_series", "args": {"series_id": "DGS10"}}]
    bad = [{"name": "fred_series", "args": {"series_id": "UNRATE"}}]
    assert score_case(c, good, "4.21%")["args"] == 1.0
    assert score_case(c, bad, "4.21%")["args"] == 0.0


def test_fixtures_cover_every_case_and_errors():
    assert fixtures.DISPATCH["quote"](["ZZZZQ"])["ZZZZQ"]["error"]
    assert "error" in fixtures.DISPATCH["fred_series"]("NOPE")
    assert fixtures.DISPATCH["correlation"](["AAPL", "MSFT", "NVDA"])["most_correlated"][0][2] == 0.79


class FakeClient:
    """Scripted chat.completions: first a tool call, then a final answer."""
    def __init__(self):
        self.n = 0
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.n += 1
        if self.n == 1:
            tc = NS(id="1", function=NS(name="quote", arguments=json.dumps({"tickers": ["MSFT"]})))
            msg = NS(content=None, tool_calls=[tc],
                     model_dump=lambda exclude_none=True: {"role": "assistant", "tool_calls": [
                         {"id": "1", "type": "function", "function": {"name": "quote", "arguments": tc.function.arguments}}]})
        else:
            msg = NS(content="MSFT is $512.40", tool_calls=None,
                     model_dump=lambda exclude_none=True: {"role": "assistant", "content": "MSFT is $512.40"})
        return NS(choices=[NS(message=msg)], usage=NS(prompt_tokens=10, completion_tokens=5))


def test_run_case_with_fake_client():
    r = run_case(FakeClient(), "fake", BY_ID["quote_single"], fixtures.DISPATCH)
    assert r["passed"] and r["tool_calls"] == 1 and r["tokens"] == 30 and r["error"] is None
    s = summarize([r])
    assert s["score"] == 1.0 and s["pass_rate"] == 1.0


def test_run_case_records_api_error():
    def boom(**kw):
        raise RuntimeError("404")
    cli = NS(chat=NS(completions=NS(create=boom)))
    r = run_case(cli, "fake", BY_ID["quote_single"], fixtures.DISPATCH)
    assert r["score"] == 0.0 and "404" in r["error"]


def test_bad_ticker_accepts_no_market_data_refusal():
    # regression: a correct refusal from nemotron-3-ultra was scored 0 on the answer part
    c = BY_ID["bad_ticker"]
    calls = [{"name": "quote", "args": {"tickers": ["ZZZZQ"]}}]
    assert score_case(c, calls, "No market data is available for the ticker **ZZZZQ**.")["passed"]
