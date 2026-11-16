"""Statistics and hypothesis verdicts."""
from alex import stats


def test_bootstrap_ci_brackets_mean_and_is_seeded():
    xs = [1, 1, 1, 0.5, 0, 1, 1, 0.7]
    lo, hi = stats.bootstrap_ci(xs)
    assert lo <= sum(xs) / len(xs) <= hi and stats.bootstrap_ci(xs) == (lo, hi)
    assert stats.bootstrap_ci([1.0, 1.0]) == (1.0, 1.0) and stats.bootstrap_ci([]) is None


def test_paired_test_exact():
    assert stats.paired_test([1, 1], [1, 1])["p"] == 1.0
    # 6 cases all better by 1: exact two-sided p = 2 / 2^6
    assert stats.paired_test([1] * 6, [0] * 6)["p"] == round(2 / 64, 4)
    assert stats.paired_test([1, 0, 1, 0], [0, 1, 0, 1])["p"] == 1.0


def test_mcnemar_exact():
    assert stats.mcnemar([True] * 8, [False] * 8)["p"] == round(2 / 256, 4)
    assert stats.mcnemar([True, False], [True, False])["p"] == 1.0


def test_pass_hat_k():
    runs = [{"case": "a", "passed": p} for p in (True, True, False)] + \
           [{"case": "b", "passed": True} for _ in range(3)]
    assert stats.pass_hat_k(runs, 1) == round((2 / 3 + 1) / 2, 4)
    assert stats.pass_hat_k(runs, 3) == 0.5                          # only b always passes


def test_pareto_front():
    s = {"cheap": {"score": 0.8, "avg_cost_usd": 0.001}, "mid": {"score": 0.8, "avg_cost_usd": 0.01},
         "best": {"score": 0.95, "avg_cost_usd": 0.05}}
    assert stats.pareto(s) == ["cheap", "best"]                       # mid is dominated by cheap


def test_fairness_labels():
    runs = [{"case": "fair_us", "answer": "MEDIUM. Beta 0.92."}, {"case": "fair_in", "answer": "**High** risk"}]
    f = stats.fairness(runs)
    assert f["consistency"] == 0.0 and f["detail"][0]["labels"] == ["MEDIUM", "HIGH"]
    runs[1]["answer"] = "Medium - same numbers"
    assert stats.fairness(runs)["consistency"] == 1.0


def _run(key, case, cat, score, answer=""):
    return {"key": key, "case": case, "category": cat, "score": score, "passed": score == 1.0, "answer": answer}


def test_analyze_verdicts():
    H, S, O = "claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"
    runs, summ = [], {}
    quality = {H: 0.5, S: 0.75, O: 1.0}
    for m, q in quality.items():
        for v in ("minimal", "default", "grounded"):
            k = f"{m}@{v}"
            sc = q if v != "minimal" else q * (0.6 if m == H else 0.95)
            rs = [_run(k, f"c{i}", "prices", 1.0 if i < sc * 8 else 0.0) for i in range(8)]
            rs += [_run(k, "injection", "safety", 1.0 if v == "grounded" or m == O else 0.0),
                   _run(k, "fair_us", "fairness", 1.0, "LOW"), _run(k, "fair_in", "fairness", 1.0, "LOW")]
            runs += rs
            summ[k] = {"score": sum(r["score"] for r in rs) / len(rs), "avg_latency_s": 1.0,
                       "avg_cost_usd": {H: 0.0005, S: 0.01, O: 0.02}[m]}
    a = stats.analyze({"runs": runs, "summary": summ, "variants": ["minimal", "default", "grounded"],
                       "repeats": 1})
    h = a["hypotheses"]
    assert h["H1"]["verdict"].startswith(("supported", "direction"))
    assert h["H3"]["verdict"] == "supported"                           # Haiku's prompt spread is largest
    assert h["H4"]["verdict"] == "supported"                           # grounded fixes injection
    assert h["H5"]["verdict"] == "supported"
    assert "H6" not in h                                               # needs repeats
    assert summ[f"{H}@default"]["fairness_consistency"] == 1.0 and summ[f"{O}@default"]["score_ci95"]
