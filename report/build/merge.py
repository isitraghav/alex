"""Merge several single-model bench JSONs (same suite + mode) into one report file.

    python report/build/merge.py results/bench-A.json results/bench-B.json ... -o results/merged.json
"""
import json
import sys
from pathlib import Path

args = sys.argv[1:]
i = args.index("-o")
out = Path(args[i + 1])
files = [Path(a) for a in args[:i] + args[i + 2:]]
reps = [json.loads(f.read_text(encoding="utf-8")) for f in files]
assert len({(r["suite_hash"], r["mode"]) for r in reps}) == 1, "different suites/modes"
merged = {k: reps[0][k] for k in ("suite_hash", "mode", "temperature", "repeats")}
merged["started"] = min(r["started"] for r in reps)
merged["summary"] = {m: s for r in reps for m, s in r["summary"].items()}
merged["runs"] = [x for r in reps for x in r["runs"]]
merged["sources"] = [f.name for f in files]
out.write_text(json.dumps(merged, indent=2), encoding="utf-8")
print("merged", len(reps), "->", out)
