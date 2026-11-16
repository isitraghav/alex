"""Fuzzy rating, repeat statistics and the leaderboard (all offline)."""
import json

from alex import fuzzy
from alex.bench import leaderboard, summarize
from alex.prompts import SUITE_HASH


def test_membership_shapes():
    f = fuzzy.tri(0, 5, 10)
    assert f(5) == 1.0 and f(0) == 0.0 and f(2.5) == 0.5
    g = fuzzy.trap(0, 2, 4, 6)
    assert g(3) == 1.0 and g(5) == 0.5 and g(7) == 0.0


def test_rating_is_monotone_in_accuracy_and_latency():
    hi_fast = fuzzy.rate(0.98, 2.0, 0.001)
    hi_slow = fuzzy.rate(0.98, 30.0, 0.001)
    low = fuzzy.rate(0.40, 2.0, 0.001)
    assert hi_fast["label"] == "excellent"
    assert low["label"] == "poor"
    assert low["suitability"] < hi_slow["suitability"] < hi_fast["suitability"]


def test_rating_outputs_in_range():
    for acc in (0, 0.5, 0.8, 1):
        for lat in (0.5, 8, 40):
            for cost in (0.0005, 0.02, 0.2, None):
                r = fuzzy.rate(acc, lat, cost)
                assert 0 <= r["suitability"] <= 100 and r["label"] in fuzzy.SUITABILITY


def _run(case, passed, score=None):
    return {"case": case, "category": "c", "score": score if score is not None else float(passed),
            "passed": passed, "error": None, "latency_s": 1.0, "tokens": 1000, "tool_calls": 1, "cost_usd": 0.001}


def test_summary_consistency_and_sd():
    s = summarize([_run("a", True), _run("a", True), _run("b", True), _run("b", False)])
    assert s["consistency"] == 0.5          # 'b' flipped between repeats
    assert s["score_sd"] > 0
    assert s["rating"]["label"] in fuzzy.SUITABILITY
    assert summarize([_run("a", True)])["consistency"] is None


def test_leaderboard_keeps_latest_per_model(tmp_path):
    def save(started, model, score, suite=SUITE_HASH):
        s = summarize([_run("a", score == 1.0, score)])
        rep = {"suite_hash": suite, "mode": "frozen", "started": started, "summary": {model: s}}
        (tmp_path / f"bench-{started}-{model}.json").write_text(json.dumps(rep))
    save("20260101-000000", "m1", 0.5)
    save("20260102-000000", "m1", 1.0)
    save("20260101-000000", "m2", 0.8)
    save("20260103-000000", "m3", 1.0, suite="otherhash")   # different suite -> ignored
    md = leaderboard(tmp_path)
    rows = [ln for ln in md.splitlines() if ln.startswith("| 1 ") or ln.startswith("| 2 ")]
    assert "m1" in rows[0] and "1.000" in rows[0] and "m2" in rows[1]
    assert "m3" not in md
    assert "no saved" in leaderboard(tmp_path, suite_hash="nope")


def test_cost_lowers_rating_at_equal_accuracy_and_speed():
    cheap = fuzzy.rate(1.0, 5.0, 0.001)["suitability"]
    pricey = fuzzy.rate(1.0, 5.0, 0.10)["suitability"]
    assert cheap > pricey
