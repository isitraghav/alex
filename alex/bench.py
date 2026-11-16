"""LLM tool-use benchmark runner.

Runs the constant suite (alex/prompts.py) against one or more models through an
agentic tool-calling loop, scores each run with rules, and writes a JSON + Markdown
report. Default backend is frozen fixtures so models are compared on identical data.

  alex                       bench BENCH_MODELS from .env on the frozen suite
  alex --models a,b          bench several models
  alex --live                use real data sources instead of fixtures
  alex --list                show models the endpoint serves
  alex --leaderboard         rank models across all saved reports of this suite
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import settings
from .fuzzy import rate
from .prompts import CASES, SUITE_HASH, SYSTEM, Case
from .scoring import score_case
from .tools import SCHEMAS, Dispatch, frozen_dispatch, live_dispatch


def run_case(cli: Any, model: str, case: Case, dispatch: Dispatch) -> dict[str, Any]:
    """Run one prompt through the tool loop. Never raises; errors are recorded."""
    msgs: list[dict] = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": case.prompt}]
    calls: list[dict] = []
    answer, error = "", None
    tokens = {"prompt": 0, "completion": 0}
    turns = tool_errors = 0
    t0 = time.perf_counter()
    try:
        for turns in range(1, settings.llm_max_tool_turns + 1):
            resp = cli.chat.completions.create(
                model=model, messages=msgs, tools=SCHEMAS,
                temperature=settings.llm_temperature, max_tokens=settings.llm_max_tokens,
            )
            if resp.usage:
                tokens["prompt"] += resp.usage.prompt_tokens or 0
                tokens["completion"] += resp.usage.completion_tokens or 0
            m = resp.choices[0].message
            msgs.append(m.model_dump(exclude_none=True))
            if not m.tool_calls:
                answer = m.content or ""
                break
            for tc in m.tool_calls:
                name, args = tc.function.name, {}
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    result = dispatch[name](**args)
                except Exception as e:  # noqa: BLE001 - bad tool/args is a model error, not ours
                    result = {"error": f"{type(e).__name__}: {e}"}
                if isinstance(result, dict) and "error" in result:
                    tool_errors += 1
                calls.append({"name": name, "args": args if isinstance(args, dict) else {}})
                msgs.append({"role": "tool", "tool_call_id": tc.id, "name": name,
                             "content": json.dumps(result, default=str)})
        else:
            error = "max tool turns reached without a final answer"
    except Exception as e:  # noqa: BLE001 - API/network failure for this case
        error = f"{type(e).__name__}: {str(e)[:200]}"
    latency = time.perf_counter() - t0

    s = score_case(case, calls, answer)
    if error:
        s.update(score=0.0, passed=False)
    return {
        "case": case.id, "category": case.category, "model": model, **s,
        "latency_s": round(latency, 2), "turns": turns, "tool_calls": len(calls),
        "tool_errors": tool_errors, "tokens": tokens["prompt"] + tokens["completion"],
        "calls": calls, "answer": answer, "error": error,
    }


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
    avg_tok = statistics.mean(r["tokens"] for r in runs)
    return {
        "runs": len(runs),
        "score": round(score, 4),
        "score_sd": round(statistics.stdev(r["score"] for r in runs), 4) if len(runs) > 1 else 0.0,
        "consistency": consistency,
        "pass_rate": round(sum(r["passed"] for r in runs) / len(runs), 4),
        "errors": sum(bool(r["error"]) for r in runs),
        "avg_latency_s": round(statistics.mean(lat), 2),
        "p95_latency_s": lat[min(len(lat) - 1, int(0.95 * len(lat)))],
        "avg_tokens": round(statistics.mean(r["tokens"] for r in runs)),
        "avg_tool_calls": round(statistics.mean(r["tool_calls"] for r in runs), 2),
        "by_category": {k: round(statistics.mean(v), 3) for k, v in sorted(cats.items())},
        "rating": rate(score, avg_lat, avg_tok),
    }


def markdown(report: dict) -> str:
    models = report["summary"]
    cats = sorted({c for s in models.values() for c in s["by_category"]})
    out = [f"# alex bench — suite `{report['suite_hash']}` ({report['mode']}, {report['started']})", "",
           "| model | score | pass | err | avg s | p95 s | avg tok | avg calls | fuzzy rating |",
           "|---|---|---|---|---|---|---|---|---|"]
    for m, s in sorted(models.items(), key=lambda kv: -kv[1]["score"]):
        rt = s.get("rating") or {}
        out.append(f"| {m} | {s['score']:.3f} | {s['pass_rate']:.0%} | {s['errors']} | "
                   f"{s['avg_latency_s']} | {s['p95_latency_s']} | {s['avg_tokens']} | {s['avg_tool_calls']} | "
                   f"{rt.get('suitability', '-')} ({rt.get('label', '-')}) |")
    out += ["", "## Score by category", "", "| model | " + " | ".join(cats) + " |",
            "|---|" + "---|" * len(cats)]
    for m, s in models.items():
        out.append(f"| {m} | " + " | ".join(f"{s['by_category'].get(c, '')}" for c in cats) + " |")
    out += ["", "## Per case", "", "| case | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for c in CASES:
        row = []
        for m in models:
            rs = [r for r in report["runs"] if r["model"] == m and r["case"] == c.id]
            row.append(", ".join(f"{r['score']:.2f}{'' if r['passed'] else ' ✗'}" for r in rs) or "-")
        out.append(f"| {c.id} | " + " | ".join(row) + " |")
    return "\n".join(out) + "\n"


def leaderboard(out_dir: Path, suite_hash: str = SUITE_HASH, mode: str = "frozen") -> str:
    """Latest summary per model across every saved report of this suite + mode, ranked."""
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
           "| # | model | score | pass | err | avg s | avg tok | fuzzy rating | run |",
           "|---|---|---|---|---|---|---|---|---|"]
    ranked = sorted(best.items(), key=lambda kv: (-kv[1][1]["score"],
                                                  -(kv[1][1].get("rating") or {}).get("suitability", 0)))
    for i, (m, (started, s)) in enumerate(ranked, 1):
        rt = s.get("rating") or rate(s["score"], s["avg_latency_s"], s["avg_tokens"])
        out.append(f"| {i} | {m} | {s['score']:.3f} | {s['pass_rate']:.0%} | {s['errors']} | "
                   f"{s['avg_latency_s']} | {s['avg_tokens']} | {rt['suitability']} ({rt['label']}) | {started} |")
    return "\n".join(out) + "\n"


def bench(models: list[str], cases: tuple[Case, ...], live: bool, repeats: int,
          out_dir: Path, cli: Any = None, log=print, delay: float = 0.0) -> dict[str, Any]:
    if cli is None:
        from .llm import client
        cli = client()
    dispatch = live_dispatch() if live else frozen_dispatch()
    started = datetime.now().strftime("%Y%m%d-%H%M%S")
    runs: list[dict] = []
    for model in models:
        log(f"\n== {model}")
        for case in cases:
            for _ in range(repeats):
                r = run_case(cli, model, case, dispatch)
                runs.append(r)
                if delay:
                    time.sleep(delay)
                flag = "PASS" if r["passed"] else "FAIL"
                log(f"  {flag} {case.id:<13} score={r['score']:.2f} {r['latency_s']:>6.1f}s "
                    f"calls={r['tool_calls']}" + (f"  ! {r['error']}" if r["error"] else ""))
    report = {
        "suite_hash": SUITE_HASH, "mode": "live" if live else "frozen", "started": started,
        "temperature": settings.llm_temperature, "repeats": repeats,
        "summary": {m: summarize([r for r in runs if r["model"] == m]) for m in models},
        "runs": runs,
    }
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
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="alex", description="Bench LLM tool use on a constant prompt suite.")
    ap.add_argument("--models", help="comma-separated model ids (default: BENCH_MODELS)")
    ap.add_argument("--cases", help="comma-separated case ids (default: all)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--live", action="store_true", help="real data sources instead of frozen fixtures")
    ap.add_argument("--out", default=settings.results_dir)
    ap.add_argument("--list", action="store_true", help="list models the endpoint serves and exit")
    ap.add_argument("--show-cases", action="store_true", help="print the prompt suite and exit")
    ap.add_argument("--delay", type=float, default=settings.request_delay_s,
                    help="seconds to wait between cases (rate-limit friendly)")
    ap.add_argument("--leaderboard", action="store_true",
                    help="rank models across saved reports of the current suite and exit")
    a = ap.parse_args(argv)

    if a.show_cases:
        print(f"suite {SUITE_HASH}: {len(CASES)} cases")
        for c in CASES:
            print(f"  {c.id:<13} [{c.category}] {c.prompt}")
        return
    if a.leaderboard:
        md = leaderboard(Path(a.out), mode="live" if a.live else "frozen")
        print(md)
        if not md.startswith("no saved"):
            (Path(a.out) / "leaderboard.md").write_text(md, encoding="utf-8")
        return
    if not settings.nvidia_api_key:
        sys.exit("NVIDIA_API_KEY not set. Copy .env.example -> .env and fill it.")
    if a.list:
        from .llm import client
        print("\n".join(sorted(m.id for m in client().models.list().data)))
        return

    models = [m.strip() for m in (a.models or settings.bench_models).split(",") if m.strip()]
    wanted = {c.strip() for c in a.cases.split(",")} if a.cases else None
    cases = tuple(c for c in CASES if wanted is None or c.id in wanted)
    if wanted and len(cases) != len(wanted):
        sys.exit(f"unknown case id(s): {wanted - {c.id for c in cases}}")
    bench(models, cases, a.live, a.repeats, Path(a.out), delay=a.delay)


if __name__ == "__main__":
    main()
