# Executed inside build_report.py after sections.py (shares its namespace).
def S(m, v=BASE):
    return SUMM.get(f"{m}@{v}")


H("5.4 Pilot study and what it revealed", 2)
P("Before the Claude study, a pilot of the same harness was run on two open models through NVIDIA NIM's free "
  "endpoint (Nemotron-3.5-Lightning 30B and Nemotron-3-Ultra 550B, 13 cases; data in report/build/data/"
  "pilot-nim.json). It shaped three design decisions:")
B("one run lost 5 of 13 cases to HTTP 429 rate limits and scored 0.615 instead of 1.0 → API errors are now retried "
  "with back-off and, if they persist, diagnosed as not_a_model_error rather than counted as wrong answers;")
B("two correct refusals for the invalid ticker (\"No market data is available…\") were marked wrong because the "
  "accepted phrase list was too narrow → the list was widened and an oracle test now proves every case solvable;")
B("when both pilot models scored 1.0 the raw score could not separate them, while the fuzzy rating could "
  "(93.4 vs 77.8, driven by latency) → cost was added as a fuzzy input, harder graph cases were added, and "
  "verdicts now report a ceiling explicitly instead of declaring a winner.")

# ------------------------------------------------------------- 6 Discussion ----
H("6. Discussion")
EXPECT = {
    "H1": "likely in direction; Section 2 shows commercial-tier gaps on agent tasks [4], [9], but single-call "
          "tool use is near-saturated for frontier models [11], so a ceiling on the simple cases is plausible — "
          "the graph and safety cases are where tiers should separate.",
    "H2": "likely; on easy tool calls cost grows ~40× from Haiku to Opus while accuracy gains are small [17], [18].",
    "H3": "plausible; prompt sensitivity is documented for smaller models [23], but strong instruction-tuned models "
          "can also be prompt-robust.",
    "H4": "uncertain; prompting defences reduce but do not remove indirect-injection success [15], [16].",
    "H5": "expected to hold for a frontier model on identical numbers, but [22] finds measurable group bias in "
          "financial LLM decisions, so a single flipped label would be a meaningful finding.",
    "H6": "likely; τ-bench shows pass^k falling well below pass^1 [10].",
}
if PENDING:
    H("6.1 What the literature predicts", 2)
    P("Until the result file exists, this section records the expected outcome of each hypothesis and why, so the "
      "results can be read against an explicit prior rather than rationalised afterwards.")
    for h, claim in HYPOTHESES.items():
        B(EXPECT[h], f"{h} — {claim} Expected: ")
    H("6.2 How the results will be read", 2)
    B("a verdict is 'supported' only if the predicted direction holds and, where a test applies, p < 0.05;")
    B("'inconclusive (ceiling)' means every configuration scored ≈ 1.0 on the cases that decide the hypothesis — the "
      "suite, not the models, is then the limit, and the recommended configuration is chosen on cost and latency "
      "(the fuzzy rating) instead of accuracy;")
    B("the recommended configuration is the one with the highest fuzzy suitability among those on the Pareto front.")
else:
    hyp = AN["hypotheses"]
    H("6.1 Answers to the research questions", 2)

    def _ev(h, d):
        if h == "H1":
            t = d["test"]["score"]
            return ("scores " + ", ".join(f"{nice(m)} {v:.3f}" for m, v in d["scores"].items())
                    + f"; Opus − Haiku mean diff {t['mean_diff']:+.3f} over {d['test']['cases']} cases, p = {t['p']}")
        if h == "H2":
            return (f"{short(d['config'])}: {'on' if d['on_pareto_front'] else 'not on'} the Pareto front, "
                    f"{d['gap_to_best']:.3f} below the best score")
        if h == "H3":
            return "spread across prompts: " + ", ".join(f"{nice(m)} {v:.3f}" for m, v in d["spread"].items())
        if h == "H4":
            return "; ".join(f"{nice(m)} {v['minimal']:.0%} → {v['grounded']:.0%}"
                             for m, v in d["safety_pass_rate"].items())
        if h == "H5":
            return ("all pairs consistent" if not d["inconsistent"] else
                    "inconsistent: " + "; ".join(short(x.split(": ", 1)[0]) + " " + x.split(": ", 1)[1]
                                                    for x in d["inconsistent"][:4]))
        if h == "H6":
            return "; ".join(f"{short(k)} " + " → ".join(f"{a} {b}" for a, b in v.items())
                             for k, v in list(d["reliability"].items())[:3])
        return ""

    CAPTION("Hypotheses: verdicts computed from the result file")
    T(["", "Claim", "Verdict", "Evidence"],
      [[h, d["claim"], d["verdict"], _ev(h, d)] for h, d in hyp.items()], widths=[0.8, 5.0, 2.8, 7.4], size=8)
    missing = [h for h in HYPOTHESES if h not in hyp]
    if missing:
        P(f"Not tested in this run: {', '.join(missing)} (needs all three prompt variants for H3/H4 and "
          "--repeats ≥ 2 for H6).", italic=True)
    for h, d in hyp.items():
        expected = re.split(r"[;,]", EXPECT[h])[0]
        B(f"predicted '{expected}', observed '{d['verdict']}'.", f"{h}: ")

    best_k = max(AN["pareto_front"] or RANKED, key=lambda k: SUMM[k]["rating"]["suitability"])
    H("6.2 Model tier", 2)
    for m in MODELS:
        s = S(m)
        if not s:
            continue
        fails = s.get("diagnoses", {})
        fail_txt = ("no failed cases" if not fails else
                    "failures diagnosed as " + ", ".join(f"{d} ({n})" for d, n in fails.items()))
        B(f"score {s['score']:.3f} (95% CI {s['score_ci95'][0]:.2f}–{s['score_ci95'][1]:.2f}), pass rate "
          f"{s['pass_rate']:.0%}, {s['avg_latency_s']} s and {(s['avg_cost_usd'] or 0) * 100:.3f}¢ per case on the "
          f"{BASE} prompt; {fail_txt}; fuzzy suitability {s['rating']['suitability']} ({s['rating']['label']}).",
          nice(m) + ": ")
    if len(MODELS) == 3 and all(S(m) for m in MODELS):
        h_, o_ = S(MODELS[0]), S(MODELS[2])
        if h_.get("avg_cost_usd") and o_.get("avg_cost_usd"):
            P(f"Opus cost {o_['avg_cost_usd'] / h_['avg_cost_usd']:.0f}× as much as Haiku per case and took "
              f"{o_['avg_latency_s'] / max(h_['avg_latency_s'], 0.01):.1f}× as long, for a score difference of "
              f"{o_['score'] - h_['score']:+.3f}.")
    H("6.3 Knowledge-graph reasoning", 2)
    for cid in ("kg_supply", "kg_path", "kg_macro"):
        rs = [r for r in REP["runs"] if r["case"] == cid]
        if rs:
            ok = sum(r["passed"] for r in rs)
            B(f"passed in {ok} of {len(rs)} runs" + ("" if ok == len(rs) else "; failures: " + ", ".join(
                f"{short(r['key'])} ({(r.get('diagnosis') or {}).get('primary', '?')})"
                for r in rs if not r["passed"])) + ".", f"{cid}: ")
    P("kg_path is the discriminating case: answering it requires restricting the search to SUPPLIES; a model that "
      "accepts the first (correlation) path reports a statistical link instead of the supply-chain one.")
    H("6.4 Safety and fairness cases", 2)
    for cid, lab in (("bad_ticker", "Hallucination guard (invalid ticker): "),
                     ("injection", "Prompt injection in a headline: ")):
        rs = [r for r in REP["runs"] if r["case"] == cid]
        if rs:
            ok = sum(r["passed"] for r in rs)
            B(f"passed in {ok} of {len(rs)} model × prompt runs" + ("" if ok == len(rs) else "; failures: " + ", ".join(
                f"{short(r['key'])} ({(r.get('diagnosis') or {}).get('primary', '?')})"
                for r in rs if not r["passed"])) + ".", lab)
    if "H5" in hyp:
        B(f"{hyp['H5']['verdict']}; " + _ev("H5", hyp["H5"]) + ".", "Counterfactual fairness: ")
    H("6.5 Recommendation", 2)
    P(f"Among the Pareto-optimal configurations, {short(best_k)} has the highest fuzzy suitability "
      f"({SUMM[best_k]['rating']['suitability']}, {SUMM[best_k]['rating']['label']}) and is the recommended choice "
      "for a financial assistant built on these tools.")

H("6.6 Threats to validity", 2)
B(f"{N_CASES} cases give low statistical power; only large effects reach p < 0.05, and the verdicts say so rather "
  "than over-claiming. Repeats (--repeats k) and a larger suite raise power.", "Small suite: ")
B("frozen fixtures and the seed graph are synthetic; they make runs reproducible but are not the real market.",
  "Synthetic world: ")
B("substring scoring can miss a correct answer phrased unusually; every failure keeps its answer text and the "
  "expert-system trace so it can be audited.", "Rule-based scoring: ")
B("one model family, one effort level, one language (English).", "Scope: ")
B("the CLI route still adds a small amount of harness context and a process start-up (excluded from latency).",
  "Harness: ")

# --------------------------------------------------------------- 7 Ethics ----
H("7. Ethical Considerations and Responsible AI")
P("Financial assistants affect people's money, so the benchmark tests ethical behaviour directly instead of only "
  "discussing it.")
B("the counterfactual pair gives two IT-services firms identical fundamentals and changes only the name and the "
  "country (United States vs India). A different risk label can only come from the identity of the company — the "
  "kind of social-group bias reported for AI in finance [22]. The probe is judge-free (the label is matched by a "
  "rule) and a test guarantees the two cases are identical apart from identity. Limits: one pair, one attribute "
  "(nationality); a fuller audit would vary region, company size and naming across many pairs.",
  "Bias and fairness (measured): ")
B("deterministic rules, identical prompts, data and effort for every model, and no LLM judge — judges are known to "
  "favour their own outputs and answer positions [19], [20], and Claude grading Claude would be a conflict of "
  "interest.", "Fairness of the evaluation itself: ")
B("an invented price can mislead a decision; the invalid-ticker case penalises any dollar figure and the grounded "
  "prompt requires every number to come from a tool.", "Misinformation and hallucination: ")
B("tool outputs are untrusted; the injection case measures whether a model obeys instructions hidden in data, "
  "and the knowledge graph exposes no free-form query language, so an injected tool call cannot alter the "
  "database.", "Security (prompt injection): ")
B("the system is decision support, not an adviser: the grounded prompt forbids buy/sell recommendations, frozen "
  "data must never be presented as real market data, and the fuzzy rating informs a human's choice of model "
  "rather than making it.", "No financial advice; human oversight: ")
B("API keys live in a git-ignored .env file, are redacted from any error text before it reaches the model or a "
  "result file, and only synthetic data is sent to the model in frozen mode.", "Privacy and secrets: ")
B("every run records tokens and dollar cost; recommending the cheapest adequate tier (H2) is also the "
  "lowest-energy choice.", "Cost and environmental impact: ")
B("the refusal phrase lists are English-only and could penalise a correct answer phrased differently (observed "
  "in the pilot); all costs, exclusions, pilot problems and threats to validity are reported.",
  "Known bias and transparency: ")

# ----------------------------------------------------------- 8 Conclusion ----
H("8. Conclusion and Future Scope")
if PENDING:
    P(f"alex is a complete, reproducible protocol for measuring how Claude Haiku, Sonnet and Opus 5.5 use tools for "
      f"financial analysis: {N_CASES} cases over {N_TOOLS} tools including a {KGS['nodes']}-entity knowledge graph "
      "served from Neo4j or memory, rule-based scoring with hallucination, prompt-injection and counterfactual-"
      "fairness probes, an expert system that explains every failure, a fuzzy rating of suitability from accuracy, "
      "latency and cost, and six pre-registered hypotheses with exact paired tests. Running the benchmark fills "
      "Sections 5–6 and turns each hypothesis into a verdict automatically.")
else:
    sup = [h for h, d in AN["hypotheses"].items() if d["verdict"] == "supported"]
    nsup = [h for h, d in AN["hypotheses"].items() if d["verdict"] == "not supported"]
    P(f"Across {len(SUMM)} model × prompt configurations and {len(REP['runs'])} runs, the study supports "
      f"{', '.join(sup) or 'none'} of the pre-registered hypotheses and rejects {', '.join(nsup) or 'none'}. "
      f"The recommended configuration is {short(best_k)}: on the cost–accuracy Pareto front and rated "
      f"'{SUMM[best_k]['rating']['label']}' by the fuzzy system. The expert system attributes every failure to a "
      "named cause, and the knowledge-graph, fairness and injection cases show where the tiers differ beyond "
      "simple tool calls.")
P("Future work:")
B("a larger suite with harder multi-hop graph questions and conflicting tool outputs, to escape the ceiling;")
B("more counterfactual pairs (region, size, naming) for a proper fairness audit;")
B("sweep the effort level (low → max) and run every configuration with --repeats 5;")
B("learn the fuzzy membership functions from human preference data (neuro-fuzzy / ANFIS);")
B("grow the knowledge graph from filings (SEC 10-K supplier and customer disclosures) with `alex-kg sync`.")

H("References")
P("Literature references [1]–[24] are listed in Section 2.4. Foundational references:", italic=True)
F = [
    "S. Russell and P. Norvig, Artificial Intelligence: A Modern Approach, 4th ed. Pearson, 2020.",
    "E. Rich, K. Knight and S. B. Nair, Artificial Intelligence, 3rd ed. McGraw Hill, 2009.",
    "A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, Ł. Kaiser and I. Polosukhin, "
    "\"Attention is all you need,\" Advances in Neural Information Processing Systems 30, 2017.",
    "S. Raschka, Build a Large Language Model (From Scratch). Manning, 2024.",
    "L. A. Zadeh, \"Fuzzy sets,\" Information and Control, vol. 8, no. 3, pp. 338–353, 1965.",
    "E. H. Mamdani and S. Assilian, \"An experiment in linguistic synthesis with a fuzzy logic controller,\" "
    "International Journal of Man-Machine Studies, vol. 7, no. 1, pp. 1–13, 1975.",
    "Anthropic, \"Claude API documentation: tool use, models and pricing,\" platform.claude.com/docs, accessed 2026.",
    "B. Efron and R. J. Tibshirani, An Introduction to the Bootstrap. Chapman & Hall, 1993.",
]
for i, r in enumerate(F, 1):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.8)
    p.paragraph_format.first_line_indent = Cm(-0.8)
    p.add_run(f"[F{i}]  ").bold = True
    p.add_run(r)
