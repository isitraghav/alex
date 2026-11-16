# Literature Survey: LLM Tool Use, Finance Benchmarks, Agent Security and Cost-Aware Evaluation

*Survey compiled 16 Nov 2026. Every entry below was checked against its arXiv abstract page, proceedings page, or full-text HTML. Where a source does not state a detail (for example the exact models or the scoring mechanism), the table says "not stated" rather than filling it in.*

## 1. Literature survey table

| Ref | Authors | Year & venue | Domain | Task / benchmark | Models evaluated | Evaluation method | Key findings | Limitation relative to alex |
|---|---|---|---|---|---|---|---|---|
| [1] | Islam et al. | 2023, arXiv preprint | Finance | FinanceBench: 10,231 open-book QA items over public-company filings | 16 configurations incl. GPT-4-Turbo, Llama 2, Claude 2 (retrieval and long-context) | Human review of 2,400 answers on a 150-case sample | GPT-4-Turbo with retrieval answered wrongly or refused 81% of questions. Long context helps but adds latency. All models hallucinated | Document QA with no tool calling. Grading is manual. No model-tier, prompt or cost ablation |
| [2] | Xie et al. | 2024, arXiv preprint (shared task at FinNLP-AgentScen, IJCAI-2024) | Finance | FinBen: 36 datasets, 24 tasks, 7 aspects (extraction, QA, risk, forecasting, trading...) | 15 LLMs incl. GPT-4, ChatGPT, Gemini | Automatic task metrics | Strong on extraction and text analysis. Weak on advanced reasoning, generation and forecasting. Instruction tuning gives limited gains on complex QA | Broad but static NLP tasks. Not an agentic tool-calling setting. No injection or hallucination guard per case |
| [3] | Qian et al. | 2025, arXiv preprint | Finance | Fino1 / FinReason: multi-table, long-context and equation-based financial reasoning | 29 LLMs incl. GPT-o1, DeepSeek-R1, finance-tuned R1 variants | Automatic accuracy (exact grader not stated in abstract) | General reasoning models degrade in finance. Small targeted RL (GRPO) models beat larger models. Data and optimisation matter more than scale | Studies reasoning *models*, not a reasoning-effort *setting*. No tools, cost or latency |
| [4] | Bigeard et al. (Vals AI) | 2025, arXiv preprint | Finance | Finance Agent Benchmark: 537 expert questions, 9 task categories, tools incl. Google Search and EDGAR | Multiple frontier LLMs (best: OpenAI o3) | LLM-as-judge with expert rubrics | Best accuracy 46.8% (o3) at about US$3.79 per query. Retrieval is easier than modelling or market analysis | Live web data, so not reproducible. Grading relies on an LLM judge. No injection test |
| [5] | Lu et al. | 2026, arXiv preprint | Finance | FinToolBench: 760 executable free-tier financial tools, 295 tool-required queries | Not stated in abstract | Execution traces, plus finance-specific criteria (timeliness, intent, regulatory alignment) | Argues that earlier finance benchmarks are document-centric QA. Proposes the FATR retrieval baseline | Live tools, so results drift over time. No model-tier, prompt or effort ablation reported in abstract |
| [6] | Zhu et al. | 2026, ICASSP 2026 | Finance | FinMCP-Bench: 613 samples, 65 real financial MCP servers, single / multi-tool / multi-turn | Qwen3 (4B, 30B-A3B, 235B-A22B Thinking), DeepSeek-R1, GPT-OSS-20B, Seed-OSS-36B | Rule-based: tool precision, recall, F1, exact match | Best tool F1 was 64.27 (Qwen3-235B). Multi-turn exact match was near zero for most models | Scores tool selection only, not answer facts. No cost or latency. No injection or hallucination traps |
| [7] | Cao et al. | 2026, arXiv preprint | Finance | FinTrace: 800 expert-annotated trajectories, 34 financial scenarios, 9 metrics on 4 axes | 13 LLMs. Qwen-3-8B and 32B fine-tuned | Rubric-based trajectory scoring (judge mechanism not stated in abstract) | Frontier models pick tools well but fail to *use* tool outputs in final answers. DPO beats SFT alone | Focus is training data. No frozen-data reproducibility claim. No cost or tier ablation |
| [8] | Li et al. | 2023, EMNLP 2023 | General tool use | API-Bank: 73 APIs, 314 dialogues, 753 API calls | GPT-3, GPT-3.5, GPT-4, Alpaca, Lynx | Automatic API-call checking | GPT-4 is strongest at planning. Lynx (+26 pts over Alpaca) approaches GPT-3.5 | Generic APIs, no finance. Older model generation. No cost metrics |
| [9] | Liu et al. | 2023, ICLR 2024 | General agents | AgentBench: 8 interactive environments | Many commercial and open LLMs (count not stated on abstract page) | Per-environment automatic metrics | Large gap between top commercial models and open models of 70B or smaller. Failures come from long-term reasoning and instruction following | No finance tools. No security or cost dimension |
| [10] | Yao et al. | 2024, arXiv preprint | Tool-agent-user (retail, airline) | τ-bench, with the pass^k reliability metric | Function-calling agents incl. gpt-4o | Rule-based: final database state compared with goal state | gpt-4o solves fewer than 50% of tasks. pass^8 is below 25% in retail | Customer-service domain. No finance or injection |
| [11] | Patil et al. | 2025, ICML 2025 (PMLR 267) | Function calling | BFCL: serial and parallel calls, abstention, multi-turn stateful agentic calls | Many proprietary and open models (live leaderboard) | Rule-based AST matching plus executable checks | SOTA models handle single-turn calls well. Memory, dynamic decisions and long horizons remain open | No financial semantics or factual-answer scoring. No per-case cost/latency ablation of prompts or effort |
| [12] | Wang et al. | 2025, arXiv preprint | Tool use via MCP | MCP-Bench: 28 live MCP servers, 250 tools | 20 LLMs (top: gpt-5, o3, gpt-oss-120b) | Hybrid: rule-based schema/execution checks plus an o4-mini LLM judge | Persistent challenges in cross-tool planning. gpt-5 scored 0.749 overall | Live servers and an LLM judge, so not fully reproducible. Not finance-specific |
| [13] | Zhang et al. | 2024, arXiv preprint | Tool-use hallucination | ToolBeHonest: 7 tasks, 700 samples (missing / potential / limited tools) | Incl. Gemini-1.5-Pro (45.3) and GPT-4o (37.0) | Automatic diagnostic metrics | Main error is judging solvability. Larger models are not reliably better | Hallucination only. No finance. No cost |
| [14] | Greshake et al. | 2023, arXiv preprint | Security | Indirect prompt injection against LLM-integrated apps | Bing Chat (GPT-4), synthetic GPT-4 apps | Qualitative attack demonstrations | Retrieved data can act as instructions: data theft, API control, "worming" | Not a benchmark. Not quantitative |
| [15] | Zhan et al. | 2024, Findings of ACL 2024 | Agent security | InjecAgent: 1,054 cases, 17 user tools, 62 attacker tools | 30 LLM agents | Automatic attack-success rate | ReAct GPT-4 was attacked successfully 24% of the time, and nearly twice as often with a "hacking prompt" | Security only. No task-accuracy, cost or finance-specific data |
| [16] | Debenedetti et al. | 2024, NeurIPS 2024 D&B | Agent security | AgentDojo: 97 tasks (incl. e-banking), 629 security cases | Multiple LLMs incl. GPT-4o | Rule-based: deterministic utility/security functions on environment state. LLM judges avoided because they can be injected too | GPT-4o utility 69.0% benign, 50.1% under attack, 47.7% targeted attack success | Not finance analytics. No cost/latency or model-tier ablation as a primary axis |
| [17] | Kapoor et al. | 2024, arXiv preprint | Agent evaluation methodology | Critique of agent benchmarks | Various agents | Analysis plus cost-accuracy Pareto evaluation | Accuracy-only leaderboards produce needlessly costly agents. Cost and accuracy should be optimised jointly | Methodology paper with no finance suite |
| [18] | Sun et al. | 2026, arXiv preprint | Agent efficiency | Reasoning-effort levels across 4 benchmarks (incl. long-horizon agentic) | Proprietary and open-weight (not named in abstract) | Automatic task success, tokens, cost | Higher effort sometimes fails where lower succeeds, and costs up to 42x more on easy tasks. Low-then-escalate matches fixed max effort | No finance domain. Latency not reported in abstract |
| [19] | Zheng et al. | 2023, NeurIPS 2023 D&B | LLM-as-judge | MT-Bench and Chatbot Arena | GPT-4 and others as judges | LLM judge vs. human preference | GPT-4 agrees with humans >80% of the time, but shows position, verbosity and self-enhancement bias | Open-ended chat. Motivates *avoiding* judges for checkable financial facts |
| [20] | Wang (Peiyi) et al. | 2023, arXiv preprint | LLM-as-judge | Pairwise judging of Vicuna-13B vs. ChatGPT | ChatGPT, GPT-4 as judges | LLM judge vs. human annotation | Swapping answer order alone made Vicuna-13B "win" 66/80 queries. Calibration methods proposed | Shows how fragile judges are. Not a tool-use study |
| [21] | He et al. | 2026, arXiv preprint | Evaluation with fuzzy MCDM | Fuzzy AHP and DualJudge on JudgeBench | Several LLM scales (not named in abstract) | LLM judge structured by (fuzzy) AHP | Crisp and fuzzy AHP beat direct scoring. Fuzzy AHP is more stable under uncertain comparisons | Fuzzy logic is applied to *judging answers*, not to rating model suitability from accuracy, latency and cost |
| [22] | Cook & Kazinnik | 2025, arXiv preprint | Finance (fairness) | Counterfactual tests of LLM financial decisions (e.g. mortgage applicants differing only in group identity) | Several commercial LLMs | Counterfactual comparison of decisions | Race-based discrepancies above historical levels; a control-vector intervention cut them by up to 70% | Credit decisions, not tool use; no tools, cost or injection |
| [23] | Sclar et al. | 2024, ICLR 2024 | LLM evaluation methodology | Sensitivity of LLMs to meaning-preserving prompt-format changes (FormatSpread) | Open models incl. LLaMA-2 family | Accuracy spread across prompt formats | Accuracy can vary by tens of points across formats; sensitivity persists with size and instruction tuning | Formatting, not system-prompt content; no tools or finance |
| [24] | Pan et al. | 2024, IEEE TKDE | LLMs + knowledge graphs | Roadmap: KG-enhanced LLMs, LLM-augmented KGs, synergised reasoning | Survey | Survey | KGs give LLMs explicit, verifiable, multi-hop relational knowledge and reduce hallucination | No benchmark; no finance tool-use evaluation |

## 2. Ongoing progress

**Finance moves from document QA to agents.** Early finance benchmarks tested reading comprehension and numerical reasoning over filings: FinanceBench found GPT-4-Turbo with retrieval failing or refusing 81% of questions [1], and FinBen spread evaluation across 24 tasks [2]. From 2025 the focus turned to agents that call tools. The Finance Agent Benchmark gives models EDGAR and web search and reports at most 46.8% accuracy [4]. In 2026 a group of finance tool-use benchmarks appeared: FinToolBench with executable tools [5], FinMCP-Bench over Model Context Protocol servers [6], and FinTrace for trajectory-level scoring [7]. A shared finding is that models now *select* tools reasonably well but still fail to *use* tool outputs correctly in the final answer [7], and that multi-turn tool use remains near zero on exact match [6]. Reasoning-tuned models do not transfer automatically to finance either [3].

**Tool-use evaluation becomes more rigorous and stateful.** Function-calling evaluation has moved from single-call correctness (API-Bank [8]) to AST and executable checking with abstention and multi-turn state (BFCL [11]), to database-state goals with a reliability metric (τ-bench pass^k [10]), and to many live MCP servers [12]. Live environments add realism but lose reproducibility, and several benchmarks still fall back on an LLM judge for task completion [4], [12].

**Agent security is now part of evaluation.** Indirect prompt injection, where instructions arrive inside retrieved data, was demonstrated in 2023 [14] and turned into benchmarks: InjecAgent [15] and AgentDojo [16]. Notably, AgentDojo scores with deterministic state checks because an LLM judge can itself be injected [16]. Tool-use hallucination is now diagnosed separately [13].

**Cost and effort become evaluation axes.** Kapoor et al. argue that accuracy-only leaderboards reward needlessly expensive agents and call for cost-accuracy Pareto reporting [17]. Late-2026 work on reasoning-effort settings shows that maximum effort can cost up to 42x more without helping on easy tasks [18]. The Finance Agent Benchmark now reports per-query cost [4].

**Judge reliability and structured aggregation.** Documented position, verbosity and self-preference biases in LLM judges [19], [20] push benchmarks toward programmatic scoring wherever answers are checkable. Fuzzy multi-criteria methods are starting to appear in LLM evaluation, but so far mainly to structure the judge [21].

**Knowledge graphs as tools.** Pairing LLMs with knowledge graphs is an active direction: graphs supply explicit, checkable relations and support multi-hop reasoning that a model otherwise has to recall from its weights [24]. Finance is a natural fit — supply chains, competitors and macro exposures are relations, not numbers — yet the finance tool-use benchmarks above [4]–[7] give agents price, filing and search tools but no graph to traverse. Prompt sensitivity is also well documented: meaning-preserving prompt changes can move accuracy by tens of points [23], which motivates ablating the system prompt rather than fixing one.

## 3. How alex differs / novelty

| Work / group | Finance domain | Tool use | Deterministic frozen data | Rule-based scoring (no LLM judge) | Hallucination guard | Prompt-injection test | Model-tier ablation | Prompt ablation | Cost & latency | Failure diagnosis | Fuzzy multi-criteria rating |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FinanceBench [1], FinBen [2], Fino1 [3] | Yes | No | Yes (static datasets) | Partial ([1] human; [2],[3] automatic) | Partial ([1] reports hallucination) | No | Partial | No | No | No | No |
| Finance Agent Benchmark [4] | Yes | Yes | No (live web/EDGAR) | No (LLM judge) | No | No | Partial | No | Partial (cost) | Partial (by category) | No |
| FinToolBench [5], FinMCP-Bench [6], FinTrace [7] | Yes | Yes | No / Partial | Partial ([6] Yes) | No | No | Partial ([6] Qwen3 sizes) | No | No | Partial ([7] failure modes) | No |
| API-Bank [8], AgentBench [9], τ-bench [10], BFCL [11], MCP-Bench [12] | No (MCP-Bench: partly) | Yes | Partial ([10],[11] yes; [12] live) | Partial ([10],[11] yes; [12] hybrid) | Partial ([11] abstention) | No | Partial | No | No | Partial ([8],[9] error analysis) | No |
| ToolBeHonest [13] | No | Yes | Yes | Yes | Yes | No | Partial | No | No | Yes (diagnostic levels) | No |
| InjecAgent [15], AgentDojo [16] | No (AgentDojo has e-banking) | Yes | Yes | Yes | No | Yes | Partial | No ([16] tests defences) | No | No | No |
| Kapoor et al. [17], Sun et al. [18] | No | Partial / Yes | Not stated | Not stated | No | No | Partial | No | Yes (cost; [18] effort) | No | No |
| He et al. (Fuzzy AHP) [21] | No | No | Yes | No (LLM judge) | No | No | Partial | No | No | No | Partial (fuzzy AHP for judging) |
| **alex (this project)** | **Yes** | **Yes (7 tools)** | **Yes (frozen fixtures, plus a live mode)** | **Yes** | **Yes** | **Yes (1 case)** | **Yes (3 tiers)** | **Yes (3 variants)** | **Yes (plus effort level)** | **Yes (forward-chaining expert system)** | **Yes (Mamdani)** |

| Contribution | Closest prior work | What is different in alex |
|---|---|---|
| Knowledge-graph tools | KG-LLM roadmap [24]; FinMCP-Bench tools [6] | Graph neighbour/path tools inside a finance tool-use suite; frozen (memory) and live (Neo4j) backends return identical answers |
| Counterfactual fairness probe | Cook & Kazinnik [22] | Applied to tool-grounded risk ratings, scored by rule, data identity enforced by a test |
| Harness ablation | Kapoor et al. [17] (scaffolds matter) | Same model, prompts and tools via raw API vs Claude Code CLI + MCP, paired tests |
| Prompt ablation per tier | Sclar et al. [23] | System-prompt content (minimal / default / grounded) crossed with three tiers of one family |
| Pre-registered verdicts | τ-bench pass^k [10]; cost Pareto [17] | Six hypotheses with automatic verdicts in every report |

**What is and is not novel.** None of alex's individual parts is new. Finance tool-use benchmarks exist and are much larger [4]–[7]. Rule-based function-call scoring is established [6], [10], [11]. Indirect-injection and tool-hallucination tests are standard in security work [13], [15], [16]. Cost-aware and effort-aware evaluation has been argued for and measured [17], [18]. What we could not find in the surveyed literature is one small, reproducible harness that combines all of the following: (a) a financial tool-use suite on frozen deterministic data, (b) purely rule-based scoring of tool choice, arguments *and* factual answer, without an LLM judge, (c) hallucination and indirect-injection traps in the same suite, (d) a joint ablation over model tier × system prompt × reasoning effort with per-case latency and US$ cost, (e) a symbolic expert system that labels *why* each case failed, and (f) a Mamdani fuzzy system that combines accuracy, latency and cost into a linguistic suitability rating, (g) a financial knowledge graph exposed as generic neighbour / path tools, identical in memory and in Neo4j, so multi-hop relational reasoning is measured reproducibly, (h) a judge-free counterfactual fairness pair, (i) a harness ablation (raw API vs an agent CLI serving the same tools over MCP), and (j) hypotheses fixed before the runs and answered with exact paired tests, bootstrap intervals, pass^k [10] and a Pareto front [17]. The fuzzy rating is the most distinctive element. The closest work [21] uses fuzzy AHP to structure an LLM judge, not to aggregate operational criteria for model selection.

The limits must be stated just as clearly. The suite has only 19 cases, with a single injection case, a single invalid-ticker case and one fairness pair. It covers one model family (Claude). Its fuzzy membership functions and rule weights are hand-designed, not learned or validated against users. Frozen fixtures trade realism for reproducibility. The results are therefore a controlled ablation and a methodology demonstration. They are not a leaderboard comparable in statistical power to [4]–[12].

**Ethical considerations (related work).** LLMs used in financial decisions can be measurably biased. In counterfactual mortgage-applicant tests, Cook and Kazinnik found race-based discrepancies above historically observed levels, and a control-vector intervention reduced them by up to 70% [22]. alex does not make credit decisions, but it adopts the counterfactual method of [22] for risk ratings: two companies with identical fundamentals that differ only in name and country (United States vs India) must get the same label. Its other ethics-relevant design choices are refusing to hallucinate figures for invalid tickers, resisting injected instructions in third-party news, and evaluating transparently and reproducibly (no opaque judge, published fixtures, cost disclosure). A natural extension is more pairs varying region, size and naming.

## 4. References

[1] P. Islam, A. Kannappan, D. Kiela, R. Qian, N. Scherrer, and B. Vidgen, "FinanceBench: A new benchmark for financial question answering," arXiv:2311.11944, 2023. [Online]. Available: https://arxiv.org/abs/2311.11944

[2] Q. Xie *et al.*, "FinBen: A holistic financial benchmark for large language models," arXiv:2402.12659, 2024. [Online]. Available: https://arxiv.org/abs/2402.12659

[3] L. Qian *et al.*, "Fino1: On the transferability of reasoning-enhanced LLMs and reinforcement learning to finance," arXiv:2502.08127, 2025. [Online]. Available: https://arxiv.org/abs/2502.08127

[4] A. Bigeard, L. Nashold, R. Krishnan, and S. Wu, "Finance Agent Benchmark: Benchmarking LLMs on real-world financial research tasks," arXiv:2508.00828, 2025. [Online]. Available: https://arxiv.org/abs/2508.00828

[5] J. Lu *et al.*, "FinToolBench: Evaluating LLM agents for real-world financial tool use," arXiv:2603.08262, 2026. [Online]. Available: https://arxiv.org/abs/2603.08262

[6] J. Zhu *et al.*, "FinMCP-Bench: Benchmarking LLM agents for real-world financial tool use under the Model Context Protocol," in *Proc. IEEE ICASSP*, 2026; arXiv:2603.24943. [Online]. Available: https://arxiv.org/abs/2603.24943

[7] Y. Cao *et al.*, "FinTrace: Holistic trajectory-level evaluation of LLM tool calling for long-horizon financial tasks," arXiv:2604.10015, 2026. [Online]. Available: https://arxiv.org/abs/2604.10015

[8] M. Li *et al.*, "API-Bank: A comprehensive benchmark for tool-augmented LLMs," in *Proc. EMNLP*, 2023; arXiv:2304.08244. [Online]. Available: https://arxiv.org/abs/2304.08244

[9] X. Liu *et al.*, "AgentBench: Evaluating LLMs as agents," in *Proc. ICLR*, 2024; arXiv:2308.03688. [Online]. Available: https://arxiv.org/abs/2308.03688

[10] S. Yao, N. Shinn, P. Razavi, and K. Narasimhan, "τ-bench: A benchmark for tool-agent-user interaction in real-world domains," arXiv:2406.12045, 2024. [Online]. Available: https://arxiv.org/abs/2406.12045

[11] S. G. Patil, H. Mao, F. Yan, C. C.-J. Ji, V. Suresh, I. Stoica, and J. E. Gonzalez, "The Berkeley Function Calling Leaderboard (BFCL): From tool use to agentic evaluation of large language models," in *Proc. 42nd ICML*, PMLR vol. 267, pp. 48371–48392, 2025. [Online]. Available: https://proceedings.mlr.press/v267/patil25a.html

[12] Z. Wang *et al.*, "MCP-Bench: Benchmarking tool-using LLM agents with complex real-world tasks via MCP servers," arXiv:2508.20453, 2025. [Online]. Available: https://arxiv.org/abs/2508.20453

[13] Y. Zhang *et al.*, "ToolBeHonest: A multi-level hallucination diagnostic benchmark for tool-augmented large language models," arXiv:2406.20015, 2024. [Online]. Available: https://arxiv.org/abs/2406.20015

[14] K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, and M. Fritz, "Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection," arXiv:2302.12173, 2023. [Online]. Available: https://arxiv.org/abs/2302.12173

[15] Q. Zhan, Z. Liang, Z. Ying, and D. Kang, "InjecAgent: Benchmarking indirect prompt injections in tool-integrated large language model agents," in *Findings of ACL*, 2024; arXiv:2403.02691. [Online]. Available: https://arxiv.org/abs/2403.02691

[16] E. Debenedetti, J. Zhang, M. Balunović, L. Beurer-Kellner, M. Fischer, and F. Tramèr, "AgentDojo: A dynamic environment to evaluate prompt injection attacks and defenses for LLM agents," in *Advances in Neural Information Processing Systems 37 (NeurIPS 2024), Datasets and Benchmarks Track*, 2024; arXiv:2406.13352. [Online]. Available: https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract.html

[17] S. Kapoor, B. Stroebl, Z. S. Siegel, N. Nadgir, and A. Narayanan, "AI agents that matter," arXiv:2407.01502, 2024. [Online]. Available: https://arxiv.org/abs/2407.01502

[18] K. Sun, Y. Kwon, Z. Hasan, S. Zhu, K. Zhou, and F. Bianchi, "What effort level should I choose? On the economics of reasoning effort in LLM agents," arXiv:2610.34491, 2026. [Online]. Available: https://arxiv.org/abs/2610.34491

[19] L. Zheng *et al.*, "Judging LLM-as-a-judge with MT-Bench and Chatbot Arena," in *NeurIPS Datasets and Benchmarks Track*, 2023; arXiv:2306.05685. [Online]. Available: https://arxiv.org/abs/2306.05685

[20] P. Wang *et al.*, "Large language models are not fair evaluators," arXiv:2305.17926, 2023. [Online]. Available: https://arxiv.org/abs/2305.17926

[21] Y. He, I. Smirnov, D. Fedrushkov, S. Kovalchuk, and I. Revin, "Structured multi-criteria evaluation of large language models with fuzzy analytic hierarchy process and DualJudge," arXiv:2604.03742, 2026. [Online]. Available: https://arxiv.org/abs/2604.03742

[22] T. R. Cook and S. Kazinnik, "Social group bias in AI finance," arXiv:2506.17490, 2025. [Online]. Available: https://arxiv.org/abs/2506.17490

[23] M. Sclar, Y. Choi, Y. Tsvetkov, and A. Suhr, "Quantifying language models' sensitivity to spurious features in prompt design or: How I learned to start worrying about prompt formatting," in *Proc. ICLR*, 2024; arXiv:2310.11324. [Online]. Available: https://arxiv.org/abs/2310.11324

[24] S. Pan, L. Luo, Y. Wang, C. Chen, J. Wang, and X. Wu, "Unifying large language models and knowledge graphs: A roadmap," *IEEE Transactions on Knowledge and Data Engineering*, 2024, doi:10.1109/TKDE.2024.3352100; arXiv:2306.08302. [Online]. Available: https://arxiv.org/abs/2306.08302
