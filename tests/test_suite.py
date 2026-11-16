"""The suite itself is sound: every case is solvable from the frozen tools (an oracle run
passes), so a failed case is the model's fault, never the benchmark's."""
import json

from alex.prompts import CASES, FAIR_PAIRS
from alex.scoring import score_case
from alex.tools import SCHEMAS, frozen_dispatch

D = frozen_dispatch()

# Ideal tool plans where the case args alone are not the whole plan.
ORACLE = {
    "kg_supply": [("kg_neighbors", {"entity": "NVDA", "relation": "SUPPLIES", "direction": "in"}),
                  ("kg_neighbors", {"entity": "TSM", "relation": "SUPPLIES", "direction": "in"})],
    "kg_path": [("kg_path", {"entities": ["AAPL", "NVDA"], "relations": ["SUPPLIES"]})],
    "kg_macro": [("kg_neighbors", {"entity": "DGS10"}), ("fred_series", {"series_id": "DGS10"})],
    "multi_tool": [("risk_metrics", {"tickers": ["NVDA"]}), ("quote", {"tickers": ["NVDA"]}),
                   ("fundamentals", {"ticker": "NVDA"})],
}
PHRASE_ONLY = {"no_tool", "bad_ticker", "injection"}   # facts are wording, not tool data


def _plan(case):
    if case.id in ORACLE:
        return ORACLE[case.id]
    args = {}
    for tool, arg, mode, vals in case.args:
        args.setdefault(tool, {})[arg] = vals[0] if mode == "eq" else list(vals)
    for tool in case.tools:
        args.setdefault(tool, {})
    if "days" in args.get("company_news", {}):
        args["company_news"]["days"] = int(args["company_news"]["days"])
    return list(args.items())


def test_every_case_is_solvable_from_frozen_tools():
    names = {s["name"] for s in SCHEMAS}
    for case in CASES:
        assert set(case.tools) <= names, case.id
        plan = _plan(case)
        outputs = [json.dumps(D[t](**a)) for t, a in plan]
        calls = [{"name": t, "args": a} for t, a in plan]
        if case.id not in PHRASE_ONLY:
            blob = " ".join(outputs).lower()
            for alts in case.facts:
                assert any(x.lower() in blob for x in alts), (case.id, alts)
            # an answer that just repeats the first alternative of each fact passes
            answer = " ".join(alts[0] for alts in case.facts)
            if case.category == "fairness":
                answer = "MEDIUM " + answer
            assert score_case(case, calls, answer)["passed"], case.id


def test_fairness_pairs_have_identical_data_except_identity():
    by = {c.id: c for c in CASES}
    for a, b in FAIR_PAIRS:
        ta, tb = by[a].args[0][3][0], by[b].args[0][3][0]
        fa, fb = D["fundamentals"](ta), D["fundamentals"](tb)
        strip = lambda f: {k: v for k, v in f.items() if k not in ("longName", "country")}
        assert strip(fa) == strip(fb) and fa["country"] != fb["country"]
        assert by[a].prompt.replace(ta, "X") == by[b].prompt.replace(tb, "X")   # same wording
        assert by[a].facts == by[b].facts
