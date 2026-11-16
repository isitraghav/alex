# Executed inside build_report.py (shares its namespace: doc helpers, REP, SUMM, RANKED, short ...).
L, U = "nvidia/nemotron-3.5-lightning-30b-a3b", "nvidia/nemotron-3-ultra-550b-a55b"
sL, sU = SUMM[L], SUMM[U]

H("5.1 Run history and what it revealed", 2)
P("The benchmark was run several times while it was being built. Table 8 lists the runs; they show why each "
  "safeguard exists.")
CAPTION("Benchmark run history (Nemotron-3.5-Lightning unless stated)")
T(["Run", "Suite", "Score", "Pass", "API err", "Observation"],
  [["2026-11-03 05:59", "32fa9eaeab", "1.000", "100%", "0", "First complete run"],
   ["2026-11-03 11:27", "aad6a84ec7", "0.977", "92%", "0", "bad_ticker: correct refusal not recognised by phrase list → list widened"],
   ["2026-11-03 11:28", "aad6a84ec7", "0.615", "62%", "5", "5 cases lost to HTTP 429 rate limits (scored 0) → retry/back-off added"],
   ["2026-11-16 22:13", "32fa9eaeab", "1.000 / 0.977", "100% / 92%", "0", "Lightning / Ultra; Ultra's ZZZZQ refusal "
    "(\"No market data is available\") again missed by the phrase list"],
   ["2026-11-16 22:16", SUITE_HASH, "1.000 / 1.000", "100% / 100%", "0", "Final run after the phrase fix (Table 6)"]],
  widths=[2.6, 2.0, 1.9, 1.9, 1.3, 6.3], size=8)
P("Four other hosted models were also attempted — nemotron-3.5-bolt-e4b, gpt-oss-20b, deepseek-v4.1-flash and "
  "mistral-large-4. On the day of the final run the free endpoint timed out on the latter three (30 s with no "
  "response to a one-word prompt) and Bolt needed 122 s for its first case, so they were excluded rather than "
  "reported with scores that would measure the queue instead of the model. The runner recorded these as errors "
  "instead of crashing, as designed.")

H("6. Discussion")
P("The results lead to the following inferences:")
H("Nemotron-3.5-Lightning (30 B MoE, ~3 B active)", 3)
B(f"Solved all 13 cases (score {sL['score']:.3f}) with one batch of tool calls per case and the right arguments, "
  f"including the multi-tool case (3 calls) and the no-tool case (0 calls).")
B(f"Fastest: {sL['avg_latency_s']} s average and {sL['p95_latency_s']} s p95 per case; fuzzy suitability "
  f"{sL['rating']['suitability']} ({sL['rating']['label']}).")
B("Used about twice as many tokens as Ultra on the multi-tool case (6.7 k vs 3.2 k); on the other cases token "
  "use was similar.")
H("Nemotron-3-Ultra (550 B MoE, ~55 B active)", 3)
B(f"Also solved all 13 cases (score {sU['score']:.3f}) after the scorer fix, with slightly fewer tokens on "
  f"average ({sU['avg_tokens']} vs {sL['avg_tokens']}).")
B(f"About {sU['avg_latency_s'] / sL['avg_latency_s']:.1f}× slower ({sU['avg_latency_s']} s average, "
  f"{sU['p95_latency_s']} s p95), which the fuzzy system turns into suitability {sU['rating']['suitability']} "
  f"({sU['rating']['label']}): the rule \"accuracy high AND latency moderate → good\" fired with strength "
  f"{sU['rating']['fired'].get('good', 0)}.")
H("About the benchmark itself", 3)
B("Rule-based scoring is transparent but brittle on free-text refusals: two correct refusals were scored as "
  "failures until the phrase list was widened. Every such case was found by reading the recorded answer, which is "
  "only possible because the scorer is explainable — an LLM judge would have hidden the problem.")
B("Infrastructure errors must be separated from model errors: before retries were added, rate limits alone "
  "cut one model's score from 1.0 to 0.615.")
B("When accuracy saturates (both models at 1.0) a raw score cannot separate models; the fuzzy rating still does, "
  "on the dimensions a human cares about next (speed, cost). This is the intended human-insight contribution.")
B("Thirteen cases is a small suite: two strong models reach the ceiling, so harder cases (multi-step reasoning, "
  "conflicting data, longer horizons) are needed to separate top models on accuracy.")

H("7. Ethical Considerations")
B("The frozen fixtures are synthetic. They are clearly labelled as such in the code and must never be shown to "
  "users as real market data; live mode uses public free sources.", "No real financial advice. ")
B("Accepting a wrong-but-confident answer is the main risk in finance. The suite includes an invalid ticker with a "
  "forbidden-pattern constraint so that a model inventing a price is penalised to zero on the answer.",
  "Hallucination. ")
B("Scoring is by deterministic rules rather than by another LLM, avoiding the known biases of LLM judges (position, "
  "verbosity, self-preference) and favouring no vendor. All models get identical prompts, data and temperature.",
  "Fairness of evaluation. ")
B("The phrase lists that recognise refusals are English-only and could penalise a correct answer in another style "
  "or language; this bias was observed twice and is documented rather than hidden.", "Known bias. ")
B("API keys are read from a git-ignored .env file and never logged; the SEC user-agent contact is configurable.",
  "Privacy & security. ")
B("Results depend on a shared free service whose load varies; latency numbers are reported as service latency and "
  "model exclusions are disclosed.", "Transparency. ")

H("8. Conclusion and Future Scope")
P("alex shows that LLM tool use can be measured in a reproducible, explainable way. A constant 13-case "
  "financial suite, a frozen fact base and rule-based scoring of tools, arguments and answers give results that "
  "can be audited case by case, and a Mamdani fuzzy system turns accuracy, latency and token cost into a single "
  "linguistic rating that helps a human choose a model. In the final run both evaluated Nemotron models answered "
  "every case correctly; the fuzzy rating ranked the 30 B Lightning model as excellent (93.4) and the 550 B Ultra "
  "model as good (77.8) because it was about three times slower — the smaller model is the better choice for an "
  "interactive financial assistant. Building the benchmark also exposed two practical lessons: separate "
  "infrastructure failures from model failures, and keep scoring explainable so its own mistakes can be found.")
P("Future work:", "")
B("add harder cases (multi-step portfolio questions, contradictory tool outputs, unit conversions) and a numeric "
  "tolerance matcher in place of exact substrings;")
B("run more models with --repeats 3 when the endpoint is less loaded and report consistency (pass^k);")
B("learn the fuzzy membership parameters from human preference data (neuro-fuzzy / ANFIS);")
B("extend live mode with a web dashboard over the leaderboard.")
