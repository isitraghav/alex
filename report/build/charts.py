"""Figures for the project report. Reads the latest frozen bench report in results/."""
import glob
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from alex import fuzzy  # noqa: E402

OUT = Path(__file__).parent / "fig"
OUT.mkdir(exist_ok=True)
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
SEQ = ["#e8f1fc", "#b9d3f4", "#86b4ec", "#4f92e0", "#2a78d6", "#1d5aa6", "#123d72"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURF, "axes.facecolor": SURF})

rep = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
summ = rep["summary"]
short = lambda m: m.split("/")[-1]
models = sorted(summ, key=lambda m: summ[m]["score"])


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight")
    plt.close(fig)


# 1. overall score bar (single series -> one hue)
fig, ax = plt.subplots(figsize=(7, 0.55 * len(models) + 0.8))
vals = [summ[m]["score"] for m in models]
ax.barh([short(m) for m in models], vals, color=S1, height=0.55)
for i, v in enumerate(vals):
    ax.text(v + 0.01, i, f"{v:.3f}  ({summ[models[i]]['pass_rate']:.0%} pass)", va="center", color=INK, fontsize=9)
ax.set_xlim(0, 1.25); ax.set_xlabel("weighted score (0–1)")
ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.set_title("Overall benchmark score by model", loc="left", color=INK, fontsize=11)
save(fig, "scores.png")

# 2. latency per case, grouped by model (2 series -> slots 1,2 + legend + direct labels)
import numpy as np
cases = list(dict.fromkeys(r["case"] for r in rep["runs"]))
fig, ax = plt.subplots(figsize=(8, 5.2))
h = 0.38
for k, (m, c) in enumerate(zip(sorted(summ), [S1, S2])):
    lat = [next(r["latency_s"] for r in rep["runs"] if r["model"] == m and r["case"] == cs) for cs in cases]
    y = np.arange(len(cases)) + (k - 0.5) * h
    ax.barh(y, lat, height=h - 0.04, color=c, label=short(m))
    for yy, v in zip(y, lat):
        ax.text(v + 0.1, yy, f"{v:.1f}", va="center", fontsize=7, color=INK2)
ax.set_yticks(range(len(cases)), cases); ax.invert_yaxis()
ax.set_xlabel("latency (s)"); ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.legend(frameon=False, loc="lower right", fontsize=8)
ax.set_title("Latency per case (all cases passed for both models)", loc="left", color=INK, fontsize=11)
save(fig, "latency.png")

# 3. fuzzy suitability per model
fig, ax = plt.subplots(figsize=(7, 0.6 * len(models) + 0.9))
vals = [summ[m]["rating"]["suitability"] for m in models]
ax.barh([short(m) for m in models], vals, color=S1, height=0.5)
for i, m in enumerate(models):
    rt = summ[m]["rating"]
    ax.text(vals[i] + 1, i, f"{rt['suitability']} ({rt['label']})  ·  {summ[m]['avg_latency_s']} s avg",
            va="center", fontsize=9, color=INK)
ax.set_xlim(0, 130); ax.set_xlabel("fuzzy suitability (0–100)")
ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.set_title("Fuzzy suitability rating by model", loc="left", color=INK, fontsize=11)
save(fig, "rating.png")

# 4. fuzzy membership functions
import numpy as np
fig, axes = plt.subplots(2, 2, figsize=(9, 6.4))
panels = [("accuracy (score)", fuzzy.ACCURACY, np.linspace(0, 1, 400)),
          ("latency (s)", fuzzy.LATENCY, np.linspace(0, 30, 400)),
          ("tokens per case", fuzzy.TOKENS, np.linspace(0, 12000, 400)),
          ("suitability (output)", fuzzy.SUITABILITY, np.linspace(0, 100, 400))]
for ax, (title, sets, xs) in zip(axes.flat, panels):
    cols = [S1, S2, S3, "#6250d6"]
    for (name, f), c in zip(sets.items(), cols):
        ax.plot(xs, [f(x) for x in xs], color=c, lw=2, label=name)
    ax.set_title(title, loc="left", color=INK, fontsize=10); ax.set_ylim(0, 1.08)
    ax.grid(True, color=GRID)
    ax.legend(fontsize=7.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4)
fig.suptitle("Fuzzy sets (membership μ vs crisp value)", x=0.02, ha="left", color=INK, fontsize=11)
fig.tight_layout()
save(fig, "fuzzy_sets.png")


# 5. architecture flowchart
def box(ax, x, y, w, h, text, fill="#e8f1fc", edge=S1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fill, ec=edge, lw=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5, color=INK, wrap=True)


def arrow(ax, x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2))
    if label:
        ax.text((x1 + x2) / 2 + 0.08, (y1 + y2) / 2 + (0.15 if y1 == y2 else 0), label,
                fontsize=7.5, color=INK2, va="bottom" if y1 == y2 else "center")


fig, ax = plt.subplots(figsize=(8.5, 9.5)); ax.set_xlim(0, 10); ax.set_ylim(0, 12.6); ax.axis("off")
AI, NON = ("#fdeee6", S2), ("#e8f1fc", S1)
box(ax, 3.2, 11.6, 3.6, 0.7, "Start: CLI  `alex --models …`", *NON)
box(ax, 3.2, 10.4, 3.6, 0.8, "Load config (.env) +\nconstant prompt suite (13 cases)", *NON)
box(ax, 3.2, 9.2, 3.6, 0.8, "Next model × case × repeat\n[system + user prompt]", *NON)
box(ax, 3.2, 7.8, 3.6, 0.9, "LLM (NVIDIA NIM)\nchooses: tool call OR answer", *AI)
ax.add_patch(plt.Polygon([[5, 7.3], [6.4, 6.6], [5, 5.9], [3.6, 6.6]], fc="#ffffff", ec=INK2, lw=1.2))
ax.text(5, 6.6, "tool_calls?", ha="center", va="center", fontsize=8.5)
box(ax, 7.0, 6.2, 2.8, 0.8, "Dispatch tool\nfrozen fixtures | live APIs", *NON)
box(ax, 3.2, 4.6, 3.6, 0.8, "Final answer + call log", *NON)
box(ax, 3.2, 3.3, 3.6, 0.9, "Rule-based scoring\n(tools 0.4 · args 0.3 · answer 0.3)", *NON)
box(ax, 3.2, 2.0, 3.6, 0.9, "Summary stats + fuzzy rating\n(Mamdani, centroid)", *AI)
box(ax, 3.2, 0.7, 3.6, 0.9, "Write JSON + Markdown report\n→ leaderboard", *NON)
arrow(ax, 5, 11.6, 5, 11.2); arrow(ax, 5, 10.4, 5, 10.0); arrow(ax, 5, 9.2, 5, 8.7)
arrow(ax, 5, 7.8, 5, 7.3); arrow(ax, 6.4, 6.6, 7.0, 6.6, "yes")
ax.annotate("", xy=(6.8, 8.25), xytext=(8.4, 7.0), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2,
            connectionstyle="arc3,rad=0.3"))
ax.text(8.3, 7.75, "tool result\n(≤ 8 turns)", fontsize=7.5, color=INK2)
arrow(ax, 5, 5.9, 5, 5.4, "no"); arrow(ax, 5, 4.6, 5, 4.2); arrow(ax, 5, 3.3, 5, 2.9); arrow(ax, 5, 2.0, 5, 1.6)
ax.annotate("", xy=(3.2, 9.6), xytext=(3.2, 3.75), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2,
            connectionstyle="arc3,rad=-0.5"))
ax.text(0.2, 6.6, "more cases /\nmodels", fontsize=7.5, color=INK2)
box(ax, 0.2, 0.1, 1.0, 0.35, "AI", *AI); box(ax, 1.4, 0.1, 1.3, 0.35, "non-AI", *NON)
save(fig, "flowchart.png")
print("figures ->", OUT)
