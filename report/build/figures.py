"""Figures for the final report, in the template's typeface (Cambria).

    python report/build/figures.py report/build/data/bench.json

pipeline.png   architecture of the benchmark harness
kg.png         the seed knowledge graph
tiers.png      cost and median latency per model tier (two panels, one measure each)
"""
import json
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from alex import kg  # noqa: E402
from alex.prompts import CASES, VARIANTS  # noqa: E402
from alex.tools import SCHEMAS  # noqa: E402

OUT = Path(__file__).parent / "fig"
OUT.mkdir(exist_ok=True)
INK, INK2, GRID, SURF = "#1b1b1b", "#55534e", "#e2e0da", "#ffffff"
BLUE, ORANGE, GREEN, VIOLET, GOLD = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#c8960c"
AI_FILL, NON_FILL = "#fdeee6", "#e8f1fc"
plt.rcParams.update({"font.family": "Cambria", "font.size": 11, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURF, "axes.facecolor": SURF})


def save(fig, name):
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ pipeline ----
def box(ax, x, y, w, h, title, sub, ai=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=AI_FILL if ai else NON_FILL, ec=ORANGE if ai else BLUE, lw=1.6))
    ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=11.5, color=INK, weight="bold")
    ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", fontsize=9.2, color=INK2, linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, text="", rad=0.0, dy=0.12):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.4, shrinkA=2, shrinkB=2,
                                connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, text, ha="center", va="bottom", fontsize=8.8, color=INK2)


def pipeline():
    fig, ax = plt.subplots(figsize=(13.4, 7.2))
    ax.set_xlim(-0.15, 13.7); ax.set_ylim(0, 7.4); ax.axis("off")
    W, H = 2.55, 1.15
    # stage labels
    for y, lab in ((6.35, "1  RUN"), (3.85, "2  ACT"), (1.35, "3  EVALUATE")):
        ax.text(0.0, y + 0.6, lab, fontsize=9.5, color=INK2, weight="bold")
    # row 1: run
    box(ax, 0.0, 5.0, W, H, "Benchmark suite", f"{len(CASES)} cases × {len(VARIANTS)} prompts\nfrozen, hashed")
    box(ax, 3.1, 5.0, W, H, "Runner", "alex bench · one thread\nper model, retries")
    box(ax, 6.2, 5.0, W, H, "Provider", "Claude Code CLI ·\nClaude API · OpenRouter")
    box(ax, 9.3, 5.0, W, H, "Claude 5.5", "Haiku · Sonnet · Opus\nchooses tool or answer", ai=True)
    arrow(ax, 2.55, 5.58, 3.1, 5.58); arrow(ax, 5.65, 5.58, 6.2, 5.58); arrow(ax, 8.75, 5.58, 9.3, 5.58)
    # row 2: act (tools)
    box(ax, 9.3, 2.55, W, H, "MCP tool server", f"{len(SCHEMAS)} tools, JSON schemas\nonly alex tools exposed")
    box(ax, 6.2, 2.55, W, H, "Market data tools", "prices · risk · macro\nfilings · news (fixtures)")
    box(ax, 3.1, 2.55, W, H, "Knowledge graph", "31 entities · 59 relations\nmemory or Neo4j")
    arrow(ax, 10.25, 5.0, 10.25, 3.7)
    arrow(ax, 11.05, 3.7, 11.05, 5.0)
    ax.text(10.15, 4.35, "tool call", ha="right", va="center", fontsize=8.8, color=INK2)
    ax.text(11.15, 4.35, "result", ha="left", va="center", fontsize=8.8, color=INK2)
    arrow(ax, 9.3, 3.12, 8.75, 3.12)
    ax.annotate("", xy=(4.4, 2.55), xytext=(9.6, 2.55), arrowprops=dict(
        arrowstyle="-|>", color=INK2, lw=1.4, connectionstyle="arc3,rad=-0.22"))
    ax.text(7.0, 1.62, "dispatch", ha="center", fontsize=8.8, color=INK2)
    # row 3: evaluate
    box(ax, 9.3, 0.1, W, H, "Run record", "answer · tool calls\ntokens · latency · cost")
    box(ax, 6.2, 0.1, W, H, "Rule scorer", "tools 0.4 · args 0.3\nanswer facts 0.3")
    box(ax, 3.1, 0.1, W, H, "Expert system", "13 IF–THEN rules\nexplains each failure", ai=True)
    box(ax, 0.0, 0.1, W, H, "Analysis & report", "statistics · hypotheses\naudit · report")
    ax.annotate("", xy=(11.85, 0.68), xytext=(11.85, 5.3), arrowprops=dict(
        arrowstyle="-|>", color=INK2, lw=1.4, connectionstyle="arc3,rad=-0.4"))
    ax.text(12.98, 3.05, "final\nanswer", fontsize=8.8, color=INK2, ha="left")
    arrow(ax, 9.3, 0.68, 8.75, 0.68); arrow(ax, 6.2, 0.68, 5.65, 0.68); arrow(ax, 3.1, 0.68, 2.55, 0.68)
    # legend
    for i, (fill, edge, lab) in enumerate(((AI_FILL, ORANGE, "AI component"), (NON_FILL, BLUE, "non-AI component"))):
        ax.add_patch(FancyBboxPatch((7.6 + i * 2.1, 6.95), 0.32, 0.22, boxstyle="round,pad=0.01",
                                    fc=fill, ec=edge, lw=1.3))
        ax.text(8.0 + i * 2.1, 7.06, lab, va="center", fontsize=9, color=INK)
    save(fig, "pipeline.png")


# ---------------------------------------------------------------- knowledge graph ----
def graph():
    G = kg.MemoryGraph()
    LAY = {"Sector": 0.0, "Industry": 1.0, "Company": 2.2, "Country": 3.4, "MacroSeries": 3.4}
    TYPE = {"Company": BLUE, "Industry": "#86b4ec", "Sector": "#123d72", "Country": GREEN, "MacroSeries": GOLD}
    EDGE = {"SUPPLIES": ORANGE, "COMPETES_WITH": VIOLET, "CORRELATED": GRID, "SENSITIVE_TO": GOLD}
    groups = {}
    for n in sorted(G.nodes.values(), key=lambda n: n["id"]):
        groups.setdefault(n["label"], []).append(n)
    ind = {e["from"]: e["to"] for e in G.edges if e["type"] == "IN_INDUSTRY"}
    pos = {}
    for lab, ns in groups.items():
        if lab == "Company":
            ns = sorted(ns, key=lambda n: (ind.get(n["id"], ""), n["id"]))
        xs = (np.linspace(0.58, 0.96, len(ns)) if lab == "MacroSeries" else
              np.linspace(0.04, 0.46 if lab == "Country" else 0.96, len(ns)))
        for x, n in zip(xs, ns):
            pos[n["id"]] = (x, -LAY[lab])
    fig, ax = plt.subplots(figsize=(11, 6.2))
    for e in G.edges:
        (x1, y1), (x2, y2) = pos[e["from"]], pos[e["to"]]
        col = EDGE.get(e["type"], "#c9c7c0")
        lw = 1.6 if e["type"] in ("SUPPLIES", "SENSITIVE_TO", "COMPETES_WITH") else 0.7
        if y1 == y2:
            ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(
                arrowstyle="-|>" if e["type"] == "SUPPLIES" else "-", color=col, lw=lw,
                connectionstyle=f"arc3,rad={0.35 if x2 > x1 else -0.35}"), zorder=1)
        else:
            ax.plot([x1, x2], [y1, y2], color=col, lw=lw, zorder=1)
    for nid, (x, y) in pos.items():
        n = G.nodes[nid]
        ax.scatter(x, y, s=240, color=TYPE[n["label"]], edgecolor=SURF, linewidth=2, zorder=3)
        lab = nid if n["label"] in ("Company", "MacroSeries") else n["name"]
        ax.text(x, y - 0.17, lab, ha="center", va="top", fontsize=8, color=INK, rotation=0 if len(lab) < 12 else 20)
    hs = [Line2D([], [], marker="o", ls="", color=c, label=t, markersize=8) for t, c in TYPE.items()]
    hs += [Line2D([], [], color=c, lw=2, label=t) for t, c in EDGE.items()]
    ax.legend(handles=hs, frameon=False, fontsize=8.5, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.02))
    ax.set_ylim(-3.9, 0.35); ax.set_xlim(-0.02, 1.02); ax.axis("off")
    save(fig, "kg.png")


# ------------------------------------------------------------------- tiers ----
def tiers(rep):
    summ = rep["summary"]
    order = [("claude-haiku-5-5", "Haiku 5.5", BLUE), ("claude-sonnet-5-5", "Sonnet 5.5", ORANGE),
             ("claude-opus-5-5", "Opus 5.5", GREEN)]
    rows = []
    for m, name, col in order:
        ks = [k for k in summ if k.startswith(m + "@")]
        if ks:
            rows.append((name, col, statistics.fmean(summ[k]["avg_cost_usd"] * 100 for k in ks),
                         statistics.median([x["latency_s"] for x in rep["runs"] if x["key"] in ks])))
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    for ax, idx, title, fmt in ((axes[0], 2, "Cost per case (US cents)", "{:.2f}¢"),
                                (axes[1], 3, "Median latency per case (seconds)", "{:.1f} s")):
        vals = [r[idx] for r in rows]
        ax.bar([r[0] for r in rows], vals, color=[r[1] for r in rows], width=0.55)
        for i, v in enumerate(vals):
            ax.text(i, v * 1.02, fmt.format(v), ha="center", va="bottom", fontsize=10, color=INK)
        ax.set_title(title, loc="left", fontsize=11.5, color=INK)
        ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.set_ylim(0, max(vals) * 1.2)
    fig.tight_layout()
    save(fig, "tiers.png")


if __name__ == "__main__":
    pipeline()
    graph()
    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        tiers(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    print("figures ->", OUT)
