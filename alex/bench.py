"""LLM tool-use benchmark runner (Claude API).

Runs the constant suite (alex/prompts.py) against one or more Claude models through an
agentic tool-use loop, scores each run with rules, diagnoses failures with a small
expert system, and writes a JSON + Markdown report. Default backend is frozen fixtures
so models are compared on identical data.

  alex                       bench BENCH_MODELS (Haiku, Sonnet, Opus) on the frozen suite
  alex --models a,b          bench chosen models
  alex --variant grounded    use another system-prompt variant (prompt-engineering experiment)
  alex --live                use real data sources instead of fixtures
  alex --list                show models the API key can use
  alex --provider openrouter run through OpenRouter instead of the Claude API
  alex --provider claude-code run through the local Claude Code CLI (subscription login)
  alex --leaderboard         rank model@variant across all saved reports of this suite
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from . import claude_code
from .config import settings
from .diagnose import diagnose
from .fuzzy import rate
from .llm import canonical, client, cost_usd, default_models, provider
from .prompts import CASES, SUITE_HASH, VARIANTS, Case
from .scoring import score_case
from .stats import analyze, compare
from .tools import OPENAI_SCHEMAS, SCHEMAS, Dispatch, frozen_dispatch, live_dispatch


class _Trace:
    """Mutable record of one run, filled by whichever provider loop runs it."""
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.answer, self.error = "", None
        self.tok_in = self.tok_out = self.turns = self.tool_errors = 0
        self.billed: float | None = None   # provider-reported cost (OpenRouter), if any

    def call_tool(self, dispatch: Dispatch, name: str, args: Any) -> tuple[str, bool]:
        args = args if isinstance(args, dict) else {}
        try:
            result = dispatch[name](**args)
        except Exception as e:  # noqa: BLE001 - bad tool/args is a model error, not ours
            result = {"error": f"{type(e).__name__}: {e}"}
        bad = isinstance(result, dict) and "error" in result
        self.tool_errors += bad
        self.calls.append({"name": name, "args": args})
        return json.dumps(result, default=str), bad


def _loop_anthropic(cli: Any, model: str, case: Case, dispatch: Dispatch, system: str,
                    effort: str, tr: _Trace) -> None:
    msgs: list[dict] = [{"role": "user", "content": case.prompt}]
    for tr.turns in range(1, settings.llm_max_tool_turns + 1):
        resp = cli.messages.create(
            model=model, max_tokens=settings.llm_max_tokens, system=system,
            tools=SCHEMAS, messages=msgs, output_config={"effort": effort},
        )
        if resp.usage:
            tr.tok_in += resp.usage.input_tokens or 0
            tr.tok_out += resp.usage.output_tokens or 0
        if resp.stop_reason == "refusal":
            cat = getattr(getattr(resp, "stop_details", None), "category", None)
            tr.error = f"refusal ({cat})"
            return
        if resp.stop_reason == "max_tokens":
            tr.error = "max_tokens reached"
            return
        # keep the full content (thinking + tool_use blocks): the API expects it back unchanged
        msgs.append({"role": "assistant", "content": resp.content})
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            tr.answer = "\n".join(b.text for b in resp.content if b.type == "text").strip()
            return
        results = []
        for tu in uses:
            content, bad = tr.call_tool(dispatch, tu.name, tu.input)
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": content, "is_error": bad})
        msgs.append({"role": "user", "content": results})  # all results in one message
    tr.error = "max tool turns reached without a final answer"


def _loop_openrouter(cli: Any, model: str, case: Case, dispatch: Dispatch, system: str,
                     effort: str, tr: _Trace) -> None:
    """OpenRouter's OpenAI-compatible chat completions. Effort maps to OpenRouter's
    `reasoning.effort` (low|medium|high); no temperature is sent."""
    eff = effort if effort in ("low", "medium", "high") else "high"
    msgs: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": case.prompt}]
    for tr.turns in range(1, settings.llm_max_tool_turns + 1):
        resp = cli.chat.completions.create(
            model=model, messages=msgs, tools=OPENAI_SCHEMAS, max_tokens=settings.llm_max_tokens,
            extra_body={"reasoning": {"effort": eff}},
        )
        u = resp.usage
        if u:
            tr.tok_in += u.prompt_tokens or 0
            tr.tok_out += u.completion_tokens or 0
            c = getattr(u, "cost", None) or (getattr(u, "model_extra", None) or {}).get("cost")
            if isinstance(c, (int, float)):
                tr.billed = (tr.billed or 0.0) + float(c)
        ch = resp.choices[0]
        if ch.finish_reason == "length":
            tr.error = "max_tokens reached"
            return
        m = ch.message
        # model_dump keeps provider extras (e.g. reasoning details) so they go back unchanged
        msgs.append(m.model_dump(exclude_none=True))
        if not m.tool_calls:
            tr.answer = (m.content or "").strip()
            if ch.finish_reason in ("content_filter", "refusal") and not tr.answer:
                tr.error = f"refusal ({ch.finish_reason})"
            return
        for tc in m.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            content, _ = tr.call_tool(dispatch, tc.function.name, args)
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": content})
    tr.error = "max tool turns reached without a final answer"


def run_case(cli: Any, model: str, case: Case, dispatch: Dispatch,
             system: str = VARIANTS["default"], effort: str | None = None,
             prov: str = "anthropic", live: bool = False) -> dict[str, Any]:
    """Run one prompt through the manual tool-use loop. Never raises; errors are recorded.

    A manual loop (rather than an SDK tool runner) because the benchmark needs per-turn
    control: a hard turn cap, timing, and a log of every call even when the model errs.
    """
    tr = _Trace()
    effort = effort or settings.llm_effort
    loop = _loop_openrouter if prov == "openrouter" else _loop_anthropic
    meta: dict[str, Any] = {}
    t0 = time.perf_counter()
    try:
        if prov == "claude-code":
            meta = claude_code.run(model, case.prompt, system, effort, tr, live=live)
        else:
            loop(cli, model, case, dispatch, system, effort, tr)
    except Exception as e:  # noqa: BLE001 - API/network failure for this case
        tr.error = f"{type(e).__name__}: {str(e)[:200]}"
    latency = time.perf_counter() - t0
    if meta.get("duration_ms"):  # session time, without the CLI's process start-up
        meta["wall_s"] = round(latency, 2)
        latency = meta["duration_ms"] / 1000

    s = score_case(case, tr.calls, tr.answer)
    if tr.error:
        s.update(score=0.0, passed=False)
    run = {
        "case": case.id, "category": case.category, "model": canonical(model), "model_slug": model,
        "provider": prov, **s,
        "latency_s": round(latency, 2), "turns": tr.turns, "tool_calls": len(tr.calls),
        "tool_errors": tr.tool_errors, "input_tokens": tr.tok_in, "output_tokens": tr.tok_out,
        "tokens": tr.tok_in + tr.tok_out,
        # list-price cost so providers are comparable; what OpenRouter actually billed is kept too
        "cost_usd": cost_usd(model, tr.tok_in, tr.tok_out), "billed_usd": tr.billed,
        "calls": tr.calls, "answer": tr.answer, "error": tr.error,
    }
    if meta:
        rl = meta.get("rate_limit") or {}
        run.update(served_model=meta.get("served_model"), wall_s=meta.get("wall_s"),
                   rate_limit_utilization=rl.get("utilization"))
    run["diagnosis"] = diagnose(case, run)
    return run


def key(model: str, variant: str) -> str:
    return f"{canonical(model)}@{variant}"


def summarize(runs: list[dict]) -> dict[str, Any]:
    lat = sorted(r["latency_s"] for r in runs)
    cats: dict[str, list[float]] = {}
    per_case: dict[str, list[dict]] = {}
    for r in runs:
        cats.setdefault(r["category"], []).append(r["score"])
        per_case.setdefault(r["case"], []).append(r)
    # consistency: share of repeated cases whose pass/fail verdict never flips across repeats
    rep = [rs for rs in per_case.values() if len(rs) > 1]
    consistency = (round(sum(len({r["passed"] for r in rs}) == 1 for rs in rep) / len(rep), 4)
                   if rep else None)
    score = statistics.mean(r["score"] for r in runs)
    avg_lat = statistics.mean(lat)
    costs = [r["cost_usd"] for r in runs if r.get("cost_usd") is not None]
    avg_cost = statistics.mean(costs) if costs else None
    diags: dict[str, int] = {}
    for r in runs:
        if r.get("diagnosis"):
            d = r["diagnosis"]["primary"]
            diags[d] = diags.get(d, 0) + 1
    return {
        "runs": len(runs),
        "score": round(score, 4),
        "score_sd": round(statistics.stdev(r["score"] for r in runs), 4) if len(runs) > 1 else 0.0,
        "consistency": consistency,
        "pass_rate": round(sum(r["passed"] for r in runs) / len(runs), 4),
        "errors": sum(bool(r["error"]) for r in runs),
        "avg_latency_s": round(avg_lat, 2),
        "p95_latency_s": lat[min(len(lat) - 1, int(0.95 * len(lat)))],
        "avg_tokens": round(statistics.mean(r["tokens"] for r in runs)),
        "avg_tool_calls": round(statistics.mean(r["tool_calls"] for r in runs), 2),
        "avg_cost_usd": round(avg_cost, 6) if avg_cost is not None else None,
        "total_cost_usd": round(sum(costs), 4) if costs else None,
        "by_category": {k: round(statistics.mean(v), 3) for k, v in sorted(cats.items())},
        "diagnoses": diags,
        "rating": rate(score, avg_lat, avg_cost),
    }


def money(v: float | None) -> str:
    return "-" if v is None else f"${v:.4f}"


def markdown(report: dict) -> str:
    models = report["summary"]
    cats = sorted({c for s in models.values() for c in s["by_category"]})
    out = [f"# alex bench — suite `{report['suite_hash']}` ({report['mode']}, effort "
           f"{report.get('effort', '-')}, via {report.get('provider', 'anthropic')}, {report['started']})", "",
           "| model@variant | score | pass | err | avg s | p95 s | avg tok | $/case | calls | fuzzy rating |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for m, s in sorted(models.items(), key=lambda kv: -kv[1]["score"]):
        rt = s.get("rating") or {}
        out.append(f"| {m} | {s['score']:.3f} | {s['pass_rate']:.0%} | {s['errors']} | "
                   f"{s['avg_latency_s']} | {s['p95_latency_s']} | {s['avg_tokens']} | "
                   f"{money(s.get('avg_cost_usd'))} | {s['avg_tool_calls']} | "
                   f"{rt.get('suitability', '-')} ({rt.get('label', '-')}) |")
    out += ["", "## Score by category", "", "| model@variant | " + " | ".join(cats) + " |",
            "|---|" + "---|" * len(cats)]
    for m, s in models.items():
        out.append(f"| {m} | " + " | ".join(f"{s['by_category'].get(c, '')}" for c in cats) + " |")
    an = report.get("analysis") or {}
    if an.get("hypotheses"):
        out += ["", "## Hypotheses", "", "| | claim | verdict |", "|---|---|---|"]
        out += [f"| {h} | {v['claim']} | **{v['verdict']}** |" for h, v in an["hypotheses"].items()]
    if an.get("pareto_front"):
        out += ["", "Cost-accuracy Pareto front: " + ", ".join(an["pareto_front"])]
    out += ["", "## Per case (✗ = failed, with the expert-system diagnosis)", "",
            "| case | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for c in CASES:
        row = []
        for m in models:
            rs = [r for r in report["runs"] if r.get("key", r["model"]) == m and r["case"] == c.id]
            row.append(", ".join(
                f"{r['score']:.2f}" + ("" if r["passed"] else
                                       f" ✗ {(r.get('diagnosis') or {}).get('primary', '')}")
                for r in rs) or "-")
        out.append(f"| {c.id} | " + " | ".join(row) + " |")
    return "\n".join(out) + "\n"


def leaderboard(out_dir: Path, suite_hash: str = SUITE_HASH, mode: str = "frozen") -> str:
    """Latest summary per model@variant across every saved report of this suite + mode, ranked."""
    best: dict[str, tuple[str, dict]] = {}
    for f in sorted(out_dir.glob("bench-*.json")):
        try:
            rep = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if rep.get("suite_hash") != suite_hash or rep.get("mode") != mode:
            continue
        for m, s in rep["summary"].items():
            if m not in best or rep["started"] >= best[m][0]:
                best[m] = (rep["started"], s)
    if not best:
        return f"no saved {mode} reports for suite {suite_hash} in {out_dir}\n"
    out = [f"# alex leaderboard — suite `{suite_hash}` ({mode})", "",
           "| # | model@variant | score | pass | err | avg s | $/case | fuzzy rating | run |",
           "|---|---|---|---|---|---|---|---|---|"]
    ranked = sorted(best.items(), key=lambda kv: (-kv[1][1]["score"],
                                                  -(kv[1][1].get("rating") or {}).get("suitability", 0)))
    for i, (m, (started, s)) in enumerate(ranked, 1):
        rt = s.get("rating") or rate(s["score"], s["avg_latency_s"], s.get("avg_cost_usd"))
        out.append(f"| {i} | {m} | {s['score']:.3f} | {s['pass_rate']:.0%} | {s['errors']} | "
                   f"{s['avg_latency_s']} | {money(s.get('avg_cost_usd'))} | "
                   f"{rt['suitability']} ({rt['label']}) | {started} |")
    return "\n".join(out) + "\n"


def bench(models: list[str], cases: tuple[Case, ...], live: bool, repeats: int,
          out_dir: Path, cli: Any = None, log=print, delay: float = 0.0,
          variants: tuple[str, ...] = ("default",), effort: str | None = None,
          prov: str = "anthropic") -> dict[str, Any]:
    """Each model@variant runs its cases in order; different models run in parallel threads."""
    if cli is None and prov != "claude-code":
        cli = client(prov)
    effort = effort or settings.llm_effort
    dispatch = live_dispatch() if live else frozen_dispatch()
    started = datetime.now().strftime("%Y%m%d-%H%M%S")

    def one(model: str, variant: str) -> list[dict]:
        out = []
        for case in cases:
            for _ in range(repeats):
                r = run_case(cli, model, case, dispatch, system=VARIANTS[variant], effort=effort, prov=prov,
                             live=live)
                r["variant"], r["key"] = variant, key(model, variant)
                out.append(r)
                flag = "PASS" if r["passed"] else "FAIL"
                cost = "" if r["cost_usd"] is None else f" ${r['cost_usd']:.4f}"
                log(f"  [{r['key']}] {flag} {case.id:<13} score={r['score']:.2f} {r['latency_s']:>6.1f}s "
                    f"calls={r['tool_calls']}{cost}" + (f"  ! {r['error']}" if r["error"] else ""))
                if delay:
                    time.sleep(delay)
        return out

    jobs = [(m, v) for v in variants for m in models]
    with ThreadPoolExecutor(max_workers=max(1, len(models))) as ex:
        runs = [r for rs in ex.map(lambda mv: one(*mv), jobs) for r in rs]
    keys = [key(m, v) for m, v in jobs]
    report = {
        "suite_hash": SUITE_HASH, "mode": "live" if live else "frozen", "started": started,
        "provider": prov, "effort": effort, "repeats": repeats, "variants": list(variants),
        "summary": {k: summarize([r for r in runs if r["key"] == k]) for k in keys},
        "runs": runs,
    }
    report["analysis"] = analyze(report)   # CIs, Pareto front, fairness, hypotheses H1-H6
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"bench-{started}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = markdown(report)
    (out_dir / f"bench-{started}.md").write_text(md, encoding="utf-8")
    log("\n" + md)
    log(f"saved: {out_dir / f'bench-{started}.json'}")
    return report


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", line_buffering=True)  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="alex", description="Bench Claude tool use on a constant prompt suite.")
    ap.add_argument("--models", help="comma-separated model ids (default: BENCH_MODELS)")
    ap.add_argument("--cases", help="comma-separated case ids (default: all)")
    ap.add_argument("--variant", default=settings.prompt_variant,
                    help=f"comma-separated system-prompt variants: {', '.join(VARIANTS)}")
    ap.add_argument("--effort", default=settings.llm_effort, help="low|medium|high|xhigh|max")
    ap.add_argument("--provider", default=None,
                    help="anthropic | openrouter | claude-code (default: LLM_PROVIDER, auto-picked from "
                         "which key is set)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--live", action="store_true", help="real data sources instead of frozen fixtures")
    ap.add_argument("--out", default=settings.results_dir)
    ap.add_argument("--list", action="store_true", help="list models the API key can use and exit")
    ap.add_argument("--show-cases", action="store_true", help="print the prompt suite and exit")
    ap.add_argument("--delay", type=float, default=settings.request_delay_s,
                    help="seconds to wait between cases (rate-limit friendly)")
    ap.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"),
                    help="paired comparison of the same model@variant across two reports "
                         "(e.g. Claude API vs Claude Code CLI) and exit")
    ap.add_argument("--leaderboard", action="store_true",
                    help="rank model@variant across saved reports of the current suite and exit")
    a = ap.parse_args(argv)

    if a.show_cases:
        print(f"suite {SUITE_HASH}: {len(CASES)} cases; prompt variants: {', '.join(VARIANTS)}")
        for c in CASES:
            print(f"  {c.id:<13} [{c.category}] {c.prompt}")
        return
    if a.compare:
        ra, rb = (json.loads(Path(f).read_text(encoding="utf-8")) for f in a.compare)
        c = compare(ra, rb)
        print(f"A = {c['a']}", f"B = {c['b']}", f"same suite: {c['same_suite']}", "", sep="\n")
        print("| model@variant | cases | score A | score B | mean diff | p (sign-flip) | p (McNemar) | s A | s B |")
        print("|---|---|---|---|---|---|---|---|---|")
        for x in c["comparisons"]:
            print(f"| {x['a']} | {x['cases']} | {x['score_a']:.3f} | {x['score_b']:.3f} | "
                  f"{x['score']['mean_diff']:+.3f} | {x['score']['p']} | {x['pass']['p']} | "
                  f"{x['latency_a']} | {x['latency_b']} |")
        return
    if a.leaderboard:
        md = leaderboard(Path(a.out), mode="live" if a.live else "frozen")
        print(md)
        if not md.startswith("no saved"):
            (Path(a.out) / "leaderboard.md").write_text(md, encoding="utf-8")
        return
    prov = (a.provider or provider()).lower()
    if prov not in ("anthropic", "openrouter", "claude-code"):
        sys.exit(f"unknown provider {prov!r}; use anthropic, openrouter or claude-code")
    if prov == "claude-code" and not claude_code.available():
        sys.exit("`claude` CLI not found on PATH. Install Claude Code and run `claude` once to log in.")
    if prov == "openrouter" and not settings.openrouter_api_key:
        sys.exit("OPENROUTER_API_KEY not set. Add it to .env (openrouter.ai -> Keys).")
    if a.list and prov == "claude-code":
        print("\n".join(m.strip() for m in settings.bench_models.split(",")))
        return
    if a.list:
        ids = sorted(m.id for m in client(prov).models.list())
        print("\n".join(i for i in ids if prov != "openrouter" or "claude" in i) or "(none)")
        return

    models = [m.strip() for m in (a.models or default_models(prov)).split(",") if m.strip()]
    variants = tuple(v.strip() for v in a.variant.split(",") if v.strip())
    if bad := [v for v in variants if v not in VARIANTS]:
        sys.exit(f"unknown variant(s) {bad}; choose from {list(VARIANTS)}")
    wanted = {c.strip() for c in a.cases.split(",")} if a.cases else None
    cases = tuple(c for c in CASES if wanted is None or c.id in wanted)
    if wanted and len(cases) != len(wanted):
        sys.exit(f"unknown case id(s): {wanted - {c.id for c in cases}}")
    print(f"provider: {prov}")
    bench(models, cases, a.live, a.repeats, Path(a.out), delay=a.delay, variants=variants,
          effort=a.effort, prov=prov)


if __name__ == "__main__":
    main()
