"""Builds report/alex_LLM_Tool_Use_Benchmark_Report.docx from the latest bench JSON.

    python report/build/charts.py  results/bench-XXXX.json
    python report/build/build_report.py results/bench-XXXX.json
"""
import json
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from alex import fuzzy  # noqa: E402
from alex.prompts import CASES, SUITE_HASH  # noqa: E402

FIG = Path(__file__).parent / "fig"
OUT = ROOT / "report" / "alex_LLM_Tool_Use_Benchmark_Report.docx"
REP = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
SUMM = REP["summary"]
RANKED = sorted(SUMM, key=lambda m: (-SUMM[m]["score"], -SUMM[m]["rating"]["suitability"]))
short = lambda m: m.split("/")[-1]
ACCENT = RGBColor(0x1D, 0x5A, 0xA6)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
for side in ("left_margin", "right_margin"):
    setattr(sec, side, Cm(2.3))
sec.top_margin = sec.bottom_margin = Cm(2.2)

st = doc.styles
st["Normal"].font.name = "Calibri"
st["Normal"].font.size = Pt(11)
st["Normal"].paragraph_format.space_after = Pt(6)
st["Normal"].paragraph_format.line_spacing = 1.15
for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
    s = st[name]
    s.font.name, s.font.size, s.font.bold = "Calibri", Pt(size), True
    s.font.color.rgb = ACCENT if name != "Heading 3" else RGBColor(0x22, 0x22, 0x22)
    s.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 10)
    s.paragraph_format.space_after = Pt(6)
    s.paragraph_format.keep_with_next = True
    rpr = s.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts"); rpr.append(fonts)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(a), "Calibri")
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        fonts.attrib.pop(qn(a), None)


def H(text, lvl=1):
    return doc.add_heading(text, lvl)


def P(text="", bold_lead=None, italic=False, align=None):
    p = doc.add_paragraph()
    if bold_lead:
        p.add_run(bold_lead).bold = True
    r = p.add_run(text)
    r.italic = italic
    if align:
        p.alignment = align
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def B(text, bold_lead=None, style="List Bullet"):
    p = doc.add_paragraph(style=style)
    if bold_lead:
        p.add_run(bold_lead).bold = True
    p.add_run(text)
    return p


def N(text, bold_lead=None):
    return B(text, bold_lead, style="List Number")


def CODE(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.6)
    r = p.add_run(text)
    r.font.name, r.font.size = "Consolas", Pt(9)
    _shade(p, "F3F2EF")
    return p


def _shade(p, hexfill):
    ppr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hexfill)
    ppr.append(shd)


def _cell_shade(cell, hexfill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hexfill)
    tcpr.append(shd)


def T(header, rows, widths=None, size=9):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(str(h)); r.bold = True; r.font.size = Pt(size)
        _cell_shade(c, "DCE8F7")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    trpr = t.rows[0]._tr.get_or_add_trPr()
    hdr = OxmlElement("w:tblHeader"); hdr.set(qn("w:val"), "true"); trpr.append(hdr)
    doc.add_paragraph()
    return t


_fig_n = [0]
_tab_n = [0]


def FIGURE(name, caption, width=15.5):
    doc.add_picture(str(FIG / name), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    _fig_n[0] += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"Figure {_fig_n[0]}: {caption}"); r.italic = True; r.font.size = Pt(9.5)


def CAPTION(text):
    _tab_n[0] += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    r = p.add_run(f"Table {_tab_n[0]}: {text}"); r.italic = True; r.font.size = Pt(9.5)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ------------------------------------------------------------- title page ----
for _ in range(5):
    doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("alex"); r.bold = True; r.font.size = Pt(36); r.font.color.rgb = ACCENT
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("A Rule-Scored, Fuzzy-Rated Benchmark of\nLLM Tool Use for Financial Analysis"); r.font.size = Pt(18); r.bold = True
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("End-Semester AI Project Report"); r.font.size = Pt(13); r.italic = True
for _ in range(6):
    doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run("Submitted by: ").bold = True; p.add_run("Raghav Yadav")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run("Theme: ").bold = True; p.add_run("AI for Human Insight and Capability Enhancement — Finance")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run("Code: ").bold = True; p.add_run("github.com/isitraghav/alex")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run(f"Suite hash {SUITE_HASH}  ·  benchmark run {REP['started']}").font.size = Pt(9)
page_break()

# ------------------------------------------------------------------- TOC ----
p = doc.add_paragraph(); r = p.add_run("Table of Contents"); r.bold = True; r.font.size = Pt(16); r.font.color.rgb = ACCENT
p = doc.add_paragraph()
for tag, text in (("begin", None), (None, 'TOC \\o "1-2" \\h \\z \\u'), ("separate", None),
                  ("text", "Right-click and choose “Update Field” to refresh the table of contents."), ("end", None)):
    run = p.add_run()
    if tag in ("begin", "separate", "end"):
        fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), tag); run._r.append(fc)
    elif tag == "text":
        run.text = text
    else:
        it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = text; run._r.append(it)
upd = OxmlElement("w:updateFields"); upd.set(qn("w:val"), "true")
doc.settings.element.append(upd)
page_break()

# --------------------------------------------------------- 1 Introduction ----
best = RANKED[0]
H("1. Introduction")
H("1.1 What is LLM tool use?", 2)
P("Large Language Models (LLMs) such as GPT, Llama, Nemotron or DeepSeek are no longer used only to generate "
  "text. Modern models can call functions (\"tools\"): instead of guessing the price of a stock, the model emits a "
  "structured request such as quote(tickers=[\"MSFT\"]), receives the real result, and writes its answer from it. "
  "This agentic loop of think → call a tool → read the result → answer is the basis of AI assistants for finance, "
  "research and customer support. Whether a model calls the right tool, with the right arguments, and then reports "
  "the returned numbers faithfully decides whether an assistant is useful or dangerous.")
H("1.2 Problem Statement", 2)
P("Different LLMs differ widely in how reliably they use tools, but most public comparisons either rely on another "
  "LLM as a judge (which is itself biased and non-reproducible) or test generic APIs rather than a concrete domain. "
  "A student, analyst or company choosing a model for a financial assistant has no simple, reproducible way to ask: "
  "\"Given the same questions and the same data, which model calls the right tools, passes correct arguments, "
  "reports the true numbers, refuses to invent data — and how fast and costly is it?\"")
H("1.3 Objective", 2)
P("To design and build alex, a reproducible benchmark that:")
B("runs a constant suite of 13 financial questions against any OpenAI-compatible model (NVIDIA NIM);")
B("gives every model the same deterministic (\"frozen\") market data so results are comparable and fact-checkable;")
B("scores each run purely by rules — tool choice, argument correctness and factual answer — with no LLM judge;")
B("combines accuracy, latency and token cost into a single interpretable rating using fuzzy logic; and")
B("produces JSON/Markdown reports and a leaderboard that a human can read to choose a model.")
H("1.4 Motivation", 2)
P("Financial questions are a high-stakes setting for hallucination: a confidently invented price, P/E ratio or "
  "filing date can mislead a decision. During early experiments with a single model we observed exactly the two "
  "failure modes that motivate this project: a model that answered a question about a non-existent ticker "
  "(ZZZZQ) in a way the rules had to catch, and a run in which five of thirteen cases failed only because the free API "
  "returned HTTP 429 (rate limit) errors — a reliability problem that a naive benchmark would silently report as the "
  "model being \"wrong\". We wanted a tool that separates these effects and helps a human make an informed choice.")
H("1.5 Significance", 2)
B("Decision support: the leaderboard and fuzzy rating tell a human which model is fit for a financial assistant, "
  "not merely which scored highest — augmenting human judgement as required by the project theme.")
B("Reproducibility: a suite hash is stamped on every report, temperature is fixed at 0 and data is frozen, so two "
  "runs can be compared fairly; changing a case changes the hash.")
B("Safety: explicit hallucination guards (e.g. no dollar figure may appear for an invalid ticker) measure whether a "
  "model refuses to invent data.")
B("Education: the project exercises state-space search, knowledge representation, constraint checking, fuzzy "
  "inference and modern neural language models in one working system.")
H("1.6 Challenges", 2)
B("Free-text answers vary (\"52%\", \"0.52\", \"$512.40\", \"512.4\"); scoring must be strict yet tolerant of "
  "formatting.")
B("Models return tool arguments in different shapes (string vs list, upper vs lower case).")
B("Hosted free-tier endpoints rate-limit (HTTP 429) and some listed models 404 — the runner must never crash and "
  "must not confuse infrastructure errors with model errors.")
B("A single number hides trade-offs between accuracy, speed and cost; a crisp threshold (\"score > 0.9 is good\") "
  "is arbitrary near its boundary.")
H("1.7 Novelty Proposed", 2)
P("alex combines three ideas that are usually separate: (i) a domain-specific, frozen-world tool-use suite for "
  "finance, (ii) fully rule-based, explainable scoring split into tools/arguments/answer with an explicit "
  "anti-hallucination constraint, and (iii) a Mamdani fuzzy inference system that turns accuracy, latency and token "
  "use into a linguistic suitability rating (poor / fair / good / excellent). The same tools can be switched to live "
  "data (yfinance, FRED, SEC EDGAR, Finnhub) with one flag, so the benchmark doubles as a working financial "
  "analysis agent.")

# --------------------------------------------------- 2 Literature Review ----
page_break()
H("2. Literature Review")
P("Schick et al. [1] introduced Toolformer, showing that a language model can teach itself, in a self-supervised "
  "way, when to call external APIs (calculator, search, calendar, QA) and how to insert their results into text. "
  "It established that tool calls improve factual accuracy of smaller models, but evaluation was on downstream "
  "text tasks rather than on the correctness of the calls themselves.")
P("Yao et al. [2] proposed ReAct, which interleaves reasoning traces with actions in an environment. ReAct "
  "reduced hallucination on HotpotQA and FEVER by grounding the model in retrieved facts. Our runner follows the "
  "same loop (reason → act → observe), bounded to eight turns.")
P("Li et al. [3] built API-Bank, a benchmark of 73 APIs and 314 annotated dialogues, evaluating whether a model "
  "decides to call an API, retrieves the correct one and calls it correctly. It is general-purpose and uses "
  "annotated reference calls; it inspired our separate tool and argument scores.")
P("Qin et al. [4] released ToolLLM/ToolBench with 16,000+ real REST APIs and the ToolEval metric. Because the "
  "space is so large, ToolEval uses ChatGPT as a judge of pass rate and win rate, which makes results depend on the "
  "judge model. alex deliberately avoids an LLM judge.")
P("Patil et al. [5] presented Gorilla and the Berkeley Function-Calling Leaderboard, which checks generated calls "
  "by abstract-syntax-tree matching against reference calls — a rule-based approach close to ours, but it scores "
  "single calls rather than the full loop including the final natural-language answer.")
P("Liu et al. [6] (AgentBench) and Yao et al. [7] (τ-bench) evaluate LLMs as multi-turn agents in simulated "
  "environments; τ-bench additionally reports consistency over repeated trials (pass^k), which motivated our "
  "repeat-consistency statistic.")
P("Islam et al. [8] introduced FinanceBench, an open-book QA benchmark over company filings, finding that even "
  "strong models with retrieval answer a large fraction of financial questions incorrectly. It tests document QA, "
  "not tool calling. Zheng et al. [9] analysed LLM-as-a-judge and documented position, verbosity and "
  "self-enhancement biases — the main reason alex scores by rules.")
P("Fuzzy logic for multi-criteria evaluation originates with Zadeh's fuzzy sets [10] and Mamdani's rule-based "
  "inference with linguistic rules [11]; it has been widely used for ranking alternatives under imprecise criteria. "
  "To our knowledge it has not been applied to rate LLMs on combined accuracy/latency/cost.")

CAPTION("Comparison of existing techniques with the proposed system")
T(["Work", "Domain", "Evaluation method", "LLM judge?", "Hallucination check", "Latency/cost", "Reproducible data"],
  [["Toolformer [1]", "General", "Downstream task accuracy", "No", "Indirect", "No", "Yes"],
   ["ReAct [2]", "QA / web", "Task success (EM)", "No", "Indirect", "No", "Partly (live wiki)"],
   ["API-Bank [3]", "73 general APIs", "Reference-call match + ROUGE", "No", "No", "No", "Yes"],
   ["ToolLLM / ToolEval [4]", "16k REST APIs", "Pass/win rate", "Yes (ChatGPT)", "No", "No", "No (live APIs)"],
   ["Gorilla / BFCL [5]", "Function calling", "AST match of calls", "No", "Irrelevance cases", "Partial", "Yes"],
   ["AgentBench [6]", "8 environments", "Task success", "Partly", "No", "No", "Yes"],
   ["τ-bench [7]", "Retail/airline", "DB state + pass^k", "User simulator", "Policy rules", "No", "Yes"],
   ["FinanceBench [8]", "Finance filings", "Human-graded QA", "No", "Yes (manual)", "No", "Yes"],
   ["alex (proposed)", "Finance tools", "Rules: tools 0.4 / args 0.3 / answer 0.3", "No",
    "Yes (forbid regex)", "Yes + fuzzy rating", "Yes (frozen + suite hash)"]],
  widths=[2.6, 2.0, 3.2, 1.7, 2.1, 1.9, 2.4], size=8)

# --------------------------------------------------------- 3 Methodology ----
page_break()
H("3. Methodology")
H("3.1 System Overview", 2)
P("Figure 1 shows the complete flow. For every model, every case and every repeat, the runner sends a fixed system "
  "prompt and the user question together with seven tool schemas. The model either emits tool calls — which are "
  "dispatched to the frozen fixtures or the live data sources and fed back — or a final answer. The answer and the "
  "log of calls are then scored by rules; per-model statistics and the fuzzy rating are computed and written to "
  "JSON and Markdown. Orange boxes are AI components; blue boxes are conventional (non-AI) software.")
FIGURE("flowchart.png", "Flowchart of the alex benchmark (AI components in orange, non-AI in blue)", 13.5)

H("3.2 Problem as State-Space Search", 2)
P("Answering one benchmark question is a search through the space of conversations that the agent can produce.", "")
P("A state is the full message history: system prompt, user question, every tool call made so far and every tool "
  "result received. Formally s = (q, [(a₁, o₁), …, (aₖ, oₖ)]) where aᵢ is an action and oᵢ its observation.",
  "State: ")
P("s₀ = (system prompt, user question) with no tool calls.", "Initial state: ")
P("A state ending in a final natural-language answer that (i) used the required tools, (ii) with correct "
  "arguments, (iii) contains every required fact and (iv) violates no forbidden pattern. The goal test is exactly "
  "the rule-based scorer: passed = True.", "Goal state: ")
P("call any of the seven tools — quote, fundamentals, risk_metrics, correlation, fred_series, sec_filings, "
  "company_news — with any arguments that satisfy its JSON schema, or emit a final answer (terminal action).",
  "Actions: ")
P("T(s, a) = s + (a, dispatch(a)): the tool backend deterministically returns the fixture for that call "
  "(or an {\"error\"} object for unknown tickers/series), so the environment is deterministic, fully observable "
  "and episodic.", "Transition model: ")
P("number of turns (LLM calls), and secondarily tokens and seconds; an optimal path reaches the goal in the "
  "fewest turns (usually two: one batch of tool calls, then the answer).", "Path cost: ")
P("The branching factor is effectively infinite (free-text arguments), so exhaustive uninformed search such as "
  "BFS or DFS is impossible. The LLM acts as a learned heuristic policy that proposes the single most promising "
  "action at each state — a greedy best-first search guided by the model's internal estimate of usefulness, with "
  "no backtracking. The search is depth-limited to eight turns (LLM_MAX_TOOL_TURNS); exceeding the limit is "
  "recorded as a failure. This choice is appropriate because the environment is deterministic and episodic, the "
  "goal is usually reachable within two steps, and the benchmark's purpose is precisely to measure how good each "
  "model's heuristic is.", "Search strategy: ")
CAPTION("State-space formulation of one benchmark case")
T(["Element", "In alex"],
  [["State", "Message history (prompt + tool calls + tool results)"],
   ["Initial state", "System prompt + user question"],
   ["Actions", "7 tool calls with schema-valid arguments, or final answer"],
   ["Transition", "Deterministic fixture lookup (frozen) / API call (live)"],
   ["Goal test", "Rule-based scorer returns passed = True"],
   ["Path cost", "Turns, then tokens and latency"],
   ["Strategy", "LLM-guided greedy best-first, depth limit 8"]], widths=[4, 12])

H("3.3 Knowledge Representation", 2)
P("alex uses three complementary, explicit representations — all human-readable and versioned in code:")
B("Each benchmark case is a frozen Case record with slots id, category, prompt, tools, no_tools, args, facts and "
  "forbid. This is a frame (slot-filler) representation: a stereotyped situation (\"a question about a price\") "
  "whose slots state what a correct run must contain.", "Frames for test cases. ")
B("The seven tools are declared as JSON-Schema function definitions (name, description, typed parameters, "
  "required fields). This is a small ontology of the financial-data domain that the LLM reads to decide which "
  "concept (quote, risk, macro series, filing, news) a question refers to.", "Tool ontology. ")
B("The frozen fixtures are a closed-world fact base (prices, ratios, risk metrics, correlations, FRED series, filing "
  "dates, headlines). Anything not in it is unknown and yields an explicit error, so the suite can test whether the "
  "model respects missing knowledge.", "Fact base. ")
B("Scoring is a set of IF–THEN production rules, e.g. IF case.no_tools AND any call made THEN tool score = 0; "
  "IF forbid pattern matches answer THEN answer score = 0; and the ten fuzzy rules of Section 3.6.",
  "Production rules. ")
P("These representations were chosen because they are transparent and auditable: a reviewer can read why a model "
  "failed, and the SHA-256 suite hash over all frames guarantees the knowledge base did not change between runs.")
CAPTION("Example frame: case \"risk_single\"")
T(["Slot", "Value"],
  [["prompt", "How risky is NVDA? Give me its annual volatility and max drawdown over the last 2 years."],
   ["category", "risk"], ["tools", "risk_metrics"],
   ["args", "tickers has NVDA; period = 2y"], ["facts", "(0.52 | 52%), (0.27 | 27%)"], ["forbid", "—"]],
  widths=[3, 13])

H("3.4 Intelligent System Design", 2)
P("The system is a small, layered Python package (Table 4). The central innovation is the separation of the "
  "agent loop from the tool backend: identical schemas are served either by deterministic fixtures (for fair "
  "benchmarking) or by real data sources (for actual analysis), so the measured behaviour transfers to production.")
CAPTION("Components and their AI / non-AI nature")
T(["Module", "Responsibility", "AI or non-AI"],
  [["prompts.py", "Constant suite of 13 case frames + system prompt; suite hash", "Knowledge base (non-AI)"],
   ["llm.py", "OpenAI-compatible client for NVIDIA NIM, retries with exponential backoff", "Non-AI"],
   ["Hosted LLM", "Chooses tools/arguments and writes the answer (transformer)", "AI"],
   ["bench.py", "Agent loop (≤ 8 turns), error isolation, summary, Markdown, leaderboard, CLI", "Non-AI (orchestration)"],
   ["tools.py", "JSON schemas; frozen vs live dispatch", "Non-AI"],
   ["fixtures.py", "Deterministic closed-world data", "Non-AI"],
   ["sources.py / analysis.py", "Live yfinance, FRED, SEC, Finnhub; Sharpe, VaR, CVaR, beta, correlation", "Non-AI (statistics)"],
   ["scoring.py", "Rule-based scoring and constraint checks", "Symbolic AI (rules)"],
   ["fuzzy.py", "Mamdani fuzzy inference → suitability rating", "AI (fuzzy logic)"]],
  widths=[3.3, 9.0, 3.7])
P("Scoring of a single run uses the weights tools 0.4, arguments 0.3 and answer 0.3; parts that do not apply to a "
  "case are dropped and the remaining weights renormalised. A run passes only if every applicable part is perfect. "
  "Any API error forces the score to zero but is recorded separately, so infrastructure problems are visible.")
CAPTION("The 13-case constant suite")
T(["Case", "Category", "Prompt", "Required tools"],
  [[c.id, c.category, c.prompt, ", ".join(c.tools) or "none (no tool allowed)"] for c in CASES],
  widths=[2.6, 2.0, 8.4, 3.0], size=8)

H("3.5 Constraint Satisfaction Problem (CSP)", 2)
P("The overall task — producing a good answer — is open-ended text generation and is not naturally a CSP: there is "
  "no finite set of discrete variables whose assignment is the answer, and the LLM generates its actions "
  "sequentially without backtracking. However, the verification of a run is exactly a constraint-satisfaction "
  "check, and we formulate it as such.")
P("for each case, one variable per required tool (was it called?), one per argument check, one per required "
  "fact, plus one for the forbidden pattern.", "Variables: ")
P("tool variables ∈ {called, not called}; argument variables ∈ the set of values the model passed (e.g. "
  "tickers ∈ subsets of symbols, period ∈ {6mo, 1y, 2y, 5y, …}); fact variables ∈ {present, absent} in the "
  "answer.", "Domains: ")
P("e.g. for risk_single: called(risk_metrics) = true; NVDA ∈ tickers; period = 2y; answer contains "
  "(\"0.52\" ∨ \"52%\") and (\"0.27\" ∨ \"27%\"). For bad_ticker the global constraint ¬match(\\$\\s?\\d) forbids "
  "any dollar figure. For no_tool the constraint is |calls| = 0.", "Constraints: ")
P("Because the model has already assigned all variables, solving reduces to consistency checking of a complete "
  "assignment (generate-and-test, with the LLM as the generator). The score is the fraction of satisfied "
  "constraints per group (a soft-CSP / weighted MAX-CSP view), and \"passed\" means all hard constraints hold. "
  "Backtracking is not used because the model's choices cannot be revised by the scorer — the benchmark measures "
  "how well the model satisfies the constraints unaided.", "Solving strategy: ")

H("3.6 Fuzzy Logic Application", 2)
P("A model scoring 0.95 in 25 s per answer is not obviously better than one scoring 0.90 in 2 s, and a crisp "
  "rule such as \"score ≥ 0.9 is good\" treats 0.899 and 0.901 completely differently. We therefore implemented a "
  "Mamdani fuzzy inference system (alex/fuzzy.py) that rates each model.")
P("accuracy (mean score, 0–1) with sets low, medium, high; latency (mean seconds per case) with fast, moderate, "
  "slow; tokens (mean tokens per case) with lean, moderate, heavy. The output suitability (0–100) has sets poor, "
  "fair, good, excellent. Triangular and trapezoidal membership functions are used (Figure 2).", "Fuzzy sets: ")
FIGURE("fuzzy_sets.png", "Membership functions of the three inputs and the output", 15.5)
P("ten rules, AND = minimum, rule aggregation = maximum:", "Rule base: ")
for ante, out in fuzzy.RULES:
    B("IF " + " AND ".join(f"{v} is {t}" for v, t in ante.items()) + f" THEN suitability is {out}")
P("each output set is clipped at its rule strength, the clipped sets are combined by maximum, and the centroid "
  "of the aggregate (evaluated on 1001 points) gives the crisp suitability. The label is the output set with the "
  "highest membership at that value. Because memberships overlap, small changes in latency or accuracy produce "
  "small changes in the rating, which handles the uncertainty of borderline cases gracefully.",
  "Inference & defuzzification: ")

H("3.7 Other AI Techniques", 2)
B("Every benched model is a decoder-only transformer trained by next-token prediction and instruction / function-"
  "calling fine-tuning. Mixture-of-experts variants (e.g. Nemotron 30B-A3B: 30 B parameters with ~3 B active per "
  "token) trade quality for speed — directly visible in our latency results.", "Large language models. ")
B("The model is used as an autonomous agent (ReAct-style perceive → reason → act loop) with a bounded number of "
  "steps.", "Agentic tool use. ")
B("In live mode the tools compute annualised volatility, Sharpe ratio, maximum drawdown, historical 95 % "
  "VaR/CVaR, beta to SPY and Pearson correlation from daily returns (252 trading days).", "Quantitative analytics (non-AI). ")
P("Machine-learning training is not part of this project: the goal is to evaluate pre-trained models fairly, and "
  "training a model would mix the evaluator with the evaluated.")

# ------------------------------------------------------ 4 Implementation ----
page_break()
H("4. Implementation")
P("alex is a Python 3.11+ package managed with uv and packaged with Docker. Configuration (API key, models, "
  "temperature, retries) is read from a .env file through pydantic-settings; keys are never committed.")
H("4.1 Running the benchmark", 2)
CODE("uv sync --extra dev\nuv run pytest                       # 17 offline tests\n"
     "uv run alex --models a,b --repeats 3 # bench models on the frozen suite\n"
     "uv run alex --leaderboard           # rank all saved runs of this suite\n"
     "uv run alex --live                  # real yfinance / FRED / SEC / Finnhub data\n"
     "docker compose run --rm bench --models a,b")
H("4.2 Agent loop", 2)
P("run_case() builds the messages, calls chat.completions with the tool schemas at temperature 0, executes every "
  "returned tool call against the selected backend (bad tool names or arguments become an {\"error\"} result fed "
  "back to the model, not a crash), and stops at the first message without tool calls or after eight turns. "
  "Latency, tokens, number of calls and tool errors are recorded per run.")
H("4.3 Features added in this iteration", 2)
P("Reviewing the project against the guidelines and earlier run logs showed gaps, which were implemented:")
B("an earlier run lost 5 of 13 cases to HTTP 429. The client now retries with exponential backoff "
  "(LLM_MAX_RETRIES = 6, honouring Retry-After) and a --delay option paces requests.", "Rate-limit resilience: ")
B("alex/fuzzy.py rates every model (Section 3.6); the rating is stored in the JSON summary and shown in reports.",
  "Fuzzy-logic rating: ")
B("with --repeats N each model gets score_sd and consistency (share of cases whose pass/fail verdict never "
  "changes across repeats).", "Repeat statistics: ")
B("alex --leaderboard ranks the latest result of every model across all saved reports with the same suite hash "
  "and writes results/leaderboard.md.", "Leaderboard: ")
B("the bad_ticker case did not accept the correct refusal \"No market data is available\"; the accepted "
  "phrases were extended (new suite hash f4a0b1059f) and both models re-run.", "Scorer fix: ")
B("six new unit tests cover membership functions, rating monotonicity, consistency, the leaderboard and a "
  "scorer regression for a missed refusal (17 tests in total, all offline).", "Tests: ")
H("4.4 Testing", 2)
P("All tests run without network access: scoring rules are checked on hand-written runs; the agent loop is "
  "exercised with a scripted fake client (one tool call, then an answer) and with a client that raises an API "
  "error; the risk mathematics is checked on a synthetic price panel; and the fuzzy system is checked for range "
  "and monotonicity (higher accuracy or lower latency never lowers the rating).")

# ------------------------------------------------------------ 5 Results ----
page_break()
H("5. Results / Performance")
P(f"All models below were run on the frozen suite (hash {REP['suite_hash']}) at temperature "
  f"{REP['temperature']}, {REP['repeats']} repeat(s) per case, on {REP['started'][:4]}-{REP['started'][4:6]}-"
  f"{REP['started'][6:8]} through the NVIDIA NIM free endpoint. Latency includes network time and any rate-limit "
  "back-off, so it reflects the hosted service rather than raw model speed.")
CAPTION("Overall results (ranked by score, then fuzzy suitability)")
T(["#", "Model", "Score", "Pass", "API err", "Avg s", "p95 s", "Avg tokens", "Calls", "Fuzzy rating"],
  [[i, short(m), f"{SUMM[m]['score']:.3f}", f"{SUMM[m]['pass_rate']:.0%}", SUMM[m]["errors"],
    SUMM[m]["avg_latency_s"], SUMM[m]["p95_latency_s"], SUMM[m]["avg_tokens"], SUMM[m]["avg_tool_calls"],
    f"{SUMM[m]['rating']['suitability']} ({SUMM[m]['rating']['label']})"] for i, m in enumerate(RANKED, 1)],
  widths=[0.6, 4.2, 1.2, 1.1, 1.1, 1.1, 1.1, 1.5, 1.1, 2.6], size=8)
FIGURE("latency.png", "Latency per case for each model", 15)
FIGURE("rating.png", "Fuzzy suitability: equal accuracy, separated by latency", 14)
CAPTION("Per-case results (✗ = failed)")
mods = RANKED
rows = []
for c in CASES:
    row = [c.id]
    for m in mods:
        rs = [r for r in REP["runs"] if r["model"] == m and r["case"] == c.id]
        row.append(", ".join(f"{r['score']:.2f}{'' if r['passed'] else ' ✗'}" for r in rs) or "-")
    rows.append(row)
T(["Case"] + [short(m) for m in mods], rows, size=7.5)

exec((Path(__file__).parent / "discussion.py").read_text(encoding="utf-8"))

# --------------------------------------------------------- References ----
H("References")
refs = [
    "T. Schick, J. Dwivedi-Yu, R. Dessì, R. Raileanu, M. Lomeli, L. Zettlemoyer, N. Cancedda and T. Scialom, "
    "\"Toolformer: Language Models Can Teach Themselves to Use Tools,\" Advances in Neural Information Processing "
    "Systems (NeurIPS), 2023. arXiv:2302.04761.",
    "S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan and Y. Cao, \"ReAct: Synergizing Reasoning and Acting "
    "in Language Models,\" International Conference on Learning Representations (ICLR), 2023. arXiv:2210.03629.",
    "M. Li, Y. Zhao, B. Yu, F. Song, H. Li, H. Yu, Z. Li, F. Huang and Y. Li, \"API-Bank: A Comprehensive Benchmark "
    "for Tool-Augmented LLMs,\" Proc. EMNLP, 2023. arXiv:2304.08244.",
    "Y. Qin et al., \"ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs,\" International "
    "Conference on Learning Representations (ICLR), 2024. arXiv:2307.16789.",
    "S. G. Patil, T. Zhang, X. Wang and J. E. Gonzalez, \"Gorilla: Large Language Model Connected with Massive APIs,\" "
    "Advances in Neural Information Processing Systems (NeurIPS), 2024. arXiv:2305.15334.",
    "X. Liu et al., \"AgentBench: Evaluating LLMs as Agents,\" International Conference on Learning Representations "
    "(ICLR), 2024. arXiv:2308.03688.",
    "S. Yao, N. Shinn, P. Razavi and K. Narasimhan, \"τ-bench: A Benchmark for Tool-Agent-User Interaction in "
    "Real-World Domains,\" 2024. arXiv:2406.12045.",
    "P. Islam, A. Kannappan, D. Kiela, R. Qian, N. Scherrer and B. Vidgen, \"FinanceBench: A New Benchmark for "
    "Financial Question Answering,\" 2023. arXiv:2311.11944.",
    "L. Zheng et al., \"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena,\" Advances in Neural Information "
    "Processing Systems (NeurIPS) Datasets and Benchmarks, 2023. arXiv:2306.05685.",
    "L. A. Zadeh, \"Fuzzy sets,\" Information and Control, vol. 8, no. 3, pp. 338–353, 1965.",
    "E. H. Mamdani and S. Assilian, \"An experiment in linguistic synthesis with a fuzzy logic controller,\" "
    "International Journal of Man-Machine Studies, vol. 7, no. 1, pp. 1–13, 1975.",
    "S. Russell and P. Norvig, Artificial Intelligence: A Modern Approach, 4th ed. Pearson, 2020.",
]
for i, r in enumerate(refs, 1):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.8)
    p.paragraph_format.first_line_indent = Cm(-0.8)
    p.add_run(f"[{i}]  ").bold = True
    p.add_run(r)

# page numbers in footer
fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
    run = fp.add_run()
    if tag:
        fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), tag); run._r.append(fc)
    else:
        it = OxmlElement("w:instrText"); it.text = text; run._r.append(it)
sec.different_first_page_header_footer = True

doc.save(OUT)
print("saved", OUT)
