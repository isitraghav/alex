"""Figures for the project report. Results figures need a bench JSON (keys are model@variant);
the method figures (fuzzy sets, knowledge graph, flowchart) are always drawn.

    python report/build/charts.py [results/bench-XXXX.json]
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from alex import fuzzy, kg  # noqa: E402
from alex.prompts import CASES, VARIANTS  # noqa: E402
from alex.stats import pareto  # noqa: E402
from alex.tools import SCHEMAS  # noqa: E402

OUT = Path(__file__).parent / "fig"
OUT.mkdir(exist_ok=True)
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff"
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
SEQ = ["#e8f1fc", "#b9d3f4", "#86b4ec", "#4f92e0", "#2a78d6", "#1d5aa6", "#123d72"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURF, "axes.facecolor": SURF})

_src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
rep = json.loads(_src.read_text(encoding="utf-8")) if _src and _src.exists() else {"summary": {}}
summ = {k: v for k, v in rep["summary"].items() if k.startswith("claude-")}
MODEL_ORDER = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
models = [m for m in MODEL_ORDER if any(k.startswith(m + "@") for k in summ)]
variants = [v for v in ("minimal", "default", "grounded") if any(k.endswith("@" + v) for k in summ)]
MCOL = dict(zip(MODEL_ORDER, [S1, S2, S3]))          # colour follows the model, never its rank
VCOL = dict(zip(("minimal", "default", "grounded"), [S1, S2, S3]))
nice = lambda m: m.replace("claude-", "").replace("-5-5", " 5.5").title()
base = "default" if "default" in variants or not variants else variants[0]


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight")
    plt.close(fig)


def results_figures():
  # 1. score per model, grouped by prompt variant
  fig, ax = plt.subplots(figsize=(8, 4))
  w = 0.8 / max(1, len(variants))
  for j, v in enumerate(variants):
      xs = np.arange(len(models)) + (j - (len(variants) - 1) / 2) * w
      vals = [summ.get(f"{m}@{v}", {}).get("score", 0) for m in models]
      ax.bar(xs, vals, width=w - 0.03, color=VCOL[v], label=f"{v} prompt")
      for x, val in zip(xs, vals):
          ax.text(x, val + 0.01, f"{val:.2f}", ha="center", fontsize=7.5, color=INK2)
  ax.set_xticks(range(len(models)), [nice(m) for m in models])
  ax.set_ylim(0, 1.12); ax.set_ylabel("weighted score")
  ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
  ax.legend(frameon=False, fontsize=8, ncol=len(variants), loc="upper center", bbox_to_anchor=(0.5, -0.1))
  ax.set_title("Score by model and system-prompt variant", loc="left", color=INK, fontsize=11)
  save(fig, "variants.png")

  # 2. category heatmap (base variant)
  cats = sorted({c for s in summ.values() for c in s["by_category"]})
  mat = [[summ[f"{m}@{base}"]["by_category"].get(c, 0) for c in cats] for m in models]
  fig, ax = plt.subplots(figsize=(8.5, 0.55 * len(models) + 1.3))
  im = ax.imshow(mat, cmap=LinearSegmentedColormap.from_list("seq", SEQ), vmin=0, vmax=1, aspect="auto")
  ax.set_xticks(range(len(cats)), cats, rotation=30, ha="right")
  ax.set_yticks(range(len(models)), [nice(m) for m in models])
  for i, row in enumerate(mat):
      for j, v in enumerate(row):
          ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8, color=INK if v < 0.6 else "#ffffff")
  ax.spines[:].set_visible(False); ax.tick_params(length=0)
  ax.set_title(f"Mean score per task category ({base} prompt)", loc="left", color=INK, fontsize=11)
  fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
  save(fig, "categories.png")

  # 3. cost vs score (one point per model@variant; colour = model, direct labels)
  fig, ax = plt.subplots(figsize=(7.5, 4.3))
  for m in models:
      for v in variants:
          s = summ.get(f"{m}@{v}")
          if not s or s.get("avg_cost_usd") is None:
              continue
          x = s["avg_cost_usd"] * 100   # cents
          ax.scatter(x, s["score"], s=70, color=MCOL[m], edgecolor=SURF, linewidth=2, zorder=3,
                     label=nice(m) if v == base else None)
          dy = {"minimal": -11, "default": 2, "grounded": 14}.get(v, 2)   # keep coincident points readable
          ax.annotate(v, (x, s["score"]), xytext=(7, dy), textcoords="offset points", fontsize=7.5, color=INK2)
  front = pareto(summ)
  if len(front) > 1:
      ax.plot([summ[k]["avg_cost_usd"] * 100 for k in front], [summ[k]["score"] for k in front],
              color=INK2, lw=1, ls="--", zorder=2, label="Pareto front")
  ax.set_xscale("log"); ax.set_xlabel("average cost per case (US cents, log scale)")
  ax.set_ylabel("weighted score"); ax.grid(True, color=GRID, which="both"); ax.set_axisbelow(True)
  ax.legend(frameon=False, fontsize=8, loc="lower right")
  ax.set_title("Accuracy vs cost", loc="left", color=INK, fontsize=11)
  save(fig, "cost.png")

  # 4. fuzzy suitability (base variant) with latency + cost annotation
  fig, ax = plt.subplots(figsize=(7.5, 0.65 * len(models) + 0.9))
  vals = [summ[f"{m}@{base}"]["rating"]["suitability"] for m in models]
  ax.barh([nice(m) for m in models], vals, color=[MCOL[m] for m in models], height=0.5)
  for i, m in enumerate(models):
      s = summ[f"{m}@{base}"]
      ax.text(vals[i] + 1, i, f"{s['rating']['suitability']} ({s['rating']['label']})  ·  "
              f"{s['avg_latency_s']} s  ·  {s['avg_cost_usd'] * 100:.2f}¢/case", va="center", fontsize=8.5, color=INK)
  ax.set_xlim(0, 150); ax.set_xlabel("fuzzy suitability (0–100)")
  ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
  ax.set_title(f"Fuzzy suitability rating ({base} prompt)", loc="left", color=INK, fontsize=11)
  save(fig, "rating.png")



if models and variants:
    results_figures()
else:
    print("no Claude results: skipping result figures")

# 5. fuzzy membership functions
fig, axes = plt.subplots(2, 2, figsize=(9, 6.4))
panels = [("accuracy (score)", fuzzy.ACCURACY, np.linspace(0, 1, 400), 1),
          ("latency (s)", fuzzy.LATENCY, np.linspace(0, 30, 400), 1),
          ("cost per case (US cents)", fuzzy.COST, np.linspace(0, 0.12, 400), 100),
          ("suitability (output)", fuzzy.SUITABILITY, np.linspace(0, 100, 400), 1)]
for ax, (title, sets, xs, k) in zip(axes.flat, panels):
    for (name, f), c in zip(sets.items(), [S1, S2, S3, S4]):
        ax.plot(xs * k, [f(x) for x in xs], color=c, lw=2, label=name)
    ax.set_title(title, loc="left", color=INK, fontsize=10); ax.set_ylim(0, 1.08)
    ax.grid(True, color=GRID)
    ax.legend(fontsize=7.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4)
fig.suptitle("Fuzzy sets (membership μ vs crisp value)", x=0.02, ha="left", color=INK, fontsize=11)
fig.tight_layout()
save(fig, "fuzzy_sets.png")


# 5b. knowledge graph (seed): fixed layered layout, colour = node type
G = kg.MemoryGraph()
LAY = {"Sector": 0.0, "Industry": 1.0, "Company": 2.2, "Country": 3.4, "MacroSeries": 3.4}
TYPE_COL = {"Company": S1, "Industry": "#86b4ec", "Sector": "#123d72", "Country": S3, "MacroSeries": "#c8960c"}
groups = {}
for n in sorted(G.nodes.values(), key=lambda n: n["id"]):
    groups.setdefault(n["label"], []).append(n)
pos = {}
for lab, ns in groups.items():
    if lab == "Company":   # order companies by industry so related ones sit together
        ind = {e["from"]: e["to"] for e in G.edges if e["type"] == "IN_INDUSTRY"}
        ns = sorted(ns, key=lambda n: (ind.get(n["id"], ""), n["id"]))
    xs = np.linspace(0.04, 0.96 if lab != "Country" else 0.46, len(ns)) if lab != "MacroSeries" else \
        np.linspace(0.58, 0.96, len(ns))
    for x, n in zip(xs, ns):
        pos[n["id"]] = (x, -LAY[lab])
fig, ax = plt.subplots(figsize=(11, 6.4))
EDGE_COL = {"SUPPLIES": S2, "COMPETES_WITH": S4, "CORRELATED": GRID, "SENSITIVE_TO": "#c8960c"}
for e in G.edges:
    (x1, y1), (x2, y2) = pos[e["from"]], pos[e["to"]]
    col = EDGE_COL.get(e["type"], "#b9b8b3")
    lw = 1.6 if e["type"] in ("SUPPLIES", "SENSITIVE_TO", "COMPETES_WITH") else 0.7
    if y1 == y2:   # same layer: arc so the edge is visible
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(
            arrowstyle="-|>" if e["type"] == "SUPPLIES" else "-", color=col, lw=lw,
            connectionstyle=f"arc3,rad={0.35 if x2 > x1 else -0.35}"), zorder=1)
    else:
        ax.plot([x1, x2], [y1, y2], color=col, lw=lw, zorder=1)
for nid, (x, y) in pos.items():
    n = G.nodes[nid]
    ax.scatter(x, y, s=260, color=TYPE_COL[n["label"]], edgecolor=SURF, linewidth=2, zorder=3)
    lab = nid if n["label"] in ("Company", "MacroSeries") else n["name"]
    ax.text(x, y - 0.17, lab, ha="center", va="top", fontsize=7, color=INK, rotation=0 if len(lab) < 12 else 20)
from matplotlib.lines import Line2D  # noqa: E402
handles = [Line2D([], [], marker="o", ls="", color=c, label=t, markersize=8) for t, c in TYPE_COL.items()]
handles += [Line2D([], [], color=c, lw=2, label=t) for t, c in EDGE_COL.items()]
ax.legend(handles=handles, frameon=False, fontsize=7.5, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.02))
ax.set_ylim(-3.9, 0.35); ax.set_xlim(-0.02, 1.02); ax.axis("off")
st_ = G.stats()
ax.set_title(f"Seed knowledge graph — {st_['nodes']} entities, {st_['edges']} relations "
             "(IN_INDUSTRY / PART_OF / DOMICILED_IN in grey)", loc="left", color=INK, fontsize=11)
save(fig, "kg.png")


# 6. architecture flowchart
def box(ax, x, y, w, h, text, fill="#e8f1fc", edge=S1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fill, ec=edge, lw=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5, color=INK, wrap=True)


def arrow(ax, x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2))
    if label:
        ax.text((x1 + x2) / 2 + 0.08, (y1 + y2) / 2 + (0.15 if y1 == y2 else 0), label,
                fontsize=7.5, color=INK2, va="bottom" if y1 == y2 else "center")


fig, ax = plt.subplots(figsize=(8.5, 10.6)); ax.set_xlim(0, 10); ax.set_ylim(0, 13.9); ax.axis("off")
AI, NON = ("#fdeee6", S2), ("#e8f1fc", S1)
box(ax, 3.2, 12.9, 3.6, 0.7, "Start: CLI  `alex --variant …`", *NON)
box(ax, 3.2, 11.7, 3.6, 0.8, f"Load config (.env) + constant suite\n({len(CASES)} cases, {len(VARIANTS)} prompt variants)", *NON)
box(ax, 3.2, 10.5, 3.6, 0.8, "Next model@variant × case\n(models run in parallel)", *NON)
box(ax, 3.2, 9.1, 3.6, 0.9, f"Claude (Haiku / Sonnet / Opus 5.5)\nchooses: one of {len(SCHEMAS)} tools OR answer", *AI)
ax.add_patch(plt.Polygon([[5, 8.6], [6.4, 7.9], [5, 7.2], [3.6, 7.9]], fc="#ffffff", ec=INK2, lw=1.2))
ax.text(5, 7.9, "tool_use?", ha="center", va="center", fontsize=8.5)
box(ax, 7.0, 7.5, 2.8, 0.8, "Dispatch tool: fixtures |\nlive APIs | knowledge graph", *NON)
box(ax, 3.2, 5.9, 3.6, 0.8, "Final answer + call log + cost", *NON)
box(ax, 3.2, 4.6, 3.6, 0.9, "Rule-based scoring\n(tools 0.4 · args 0.3 · answer 0.3)", *NON)
box(ax, 3.2, 3.3, 3.6, 0.9, "Expert system diagnosis\n(forward chaining, 13 rules)", *AI)
box(ax, 3.2, 2.0, 3.6, 0.9, "Stats, hypotheses H1-H6\n+ fuzzy rating (Mamdani)", *AI)
box(ax, 3.2, 0.7, 3.6, 0.9, "Write JSON + Markdown report\n→ leaderboard", *NON)
arrow(ax, 5, 12.9, 5, 12.5); arrow(ax, 5, 11.7, 5, 11.3); arrow(ax, 5, 10.5, 5, 10.0)
arrow(ax, 5, 9.1, 5, 8.6); arrow(ax, 6.4, 7.9, 7.0, 7.9, "yes")
ax.annotate("", xy=(6.8, 9.55), xytext=(8.4, 8.3), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2,
            connectionstyle="arc3,rad=0.3"))
ax.text(8.3, 9.05, "tool_result\n(≤ 8 turns)", fontsize=7.5, color=INK2)
arrow(ax, 5, 7.2, 5, 6.7, "no"); arrow(ax, 5, 5.9, 5, 5.5); arrow(ax, 5, 4.6, 5, 4.2)
arrow(ax, 5, 3.3, 5, 2.9); arrow(ax, 5, 2.0, 5, 1.6)
ax.annotate("", xy=(3.2, 10.9), xytext=(3.2, 3.75), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2,
            connectionstyle="arc3,rad=-0.5"))
ax.text(0.2, 7.3, "more cases /\nmodels", fontsize=7.5, color=INK2)
box(ax, 0.2, 0.1, 1.0, 0.35, "AI", *AI); box(ax, 1.4, 0.1, 1.3, 0.35, "non-AI", *NON)
save(fig, "flowchart.png")
print("figures ->", OUT)
