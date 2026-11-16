"""One command from benchmark results to the finished report (course template).

    python report/build/make_report.py results/final/bench-*.json   # merge runs, then build
    python report/build/make_report.py                              # rebuild from data/bench.json

Steps: merge result files -> report/build/data/bench.json -> figures -> .docx (in the course
template, report/reference/Final_Project_Report_Template.docx) -> .pdf with the table of
contents updated. The PDF step needs Microsoft Word (Windows, via COM) or LibreOffice.
Needs the `report` extra: `uv sync --extra report`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "data" / "bench.json"
DOCX = ROOT / "report" / "alex_Final_Project_Report.docx"


def merge(paths: list[Path]) -> dict:
    reps = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    hashes = {r["suite_hash"] for r in reps}
    if len(hashes) > 1:
        sys.exit(f"cannot merge reports from different suites: {hashes}")
    provs = {r.get("provider") for r in reps}
    if len(provs) > 1:
        sys.exit(f"cannot merge reports from different providers: {provs} (use alex --compare)")
    out = dict(reps[0])
    out["runs"] = [x for r in reps for x in r["runs"]]
    out["variants"] = sorted({v for r in reps for v in r.get("variants", [])})
    out["repeats"] = max(int(r.get("repeats") or 1) for r in reps)
    out["started"] = min(r["started"] for r in reps)
    out.pop("analysis", None)   # recomputed by the report builder
    # summaries are recomputed from the raw runs so every configuration uses the same definitions
    sys.path.insert(0, str(ROOT))
    from alex.bench import summarize
    keys = sorted({k for r in reps for k in r["summary"]})
    out["summary"] = {k: summarize([x for x in out["runs"] if x.get("key") == k]) for k in keys}
    return out


def to_pdf(docx: Path) -> Path | None:
    pdf = docx.with_suffix(".pdf")
    if sys.platform == "win32":
        ps = (
            "$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
            f"$d = $w.Documents.Open('{docx}'); $d.Fields.Update() | Out-Null; "
            "foreach ($t in $d.TablesOfContents) { $t.Update(); $t.Range.Font.Name = 'Cambria'; "
            "$t.Range.Font.Size = 12 }; "
            f"$d.SaveAs2('{pdf}', 17); $d.Save(); $d.Close(); $w.Quit()"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        if r.returncode == 0 and pdf.exists():
            return pdf
        print("Word export failed:", r.stderr.strip()[:300])
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(docx.parent), str(docx)],
                       check=False)
        if pdf.exists():
            return pdf
    print("PDF step skipped: needs Microsoft Word or LibreOffice")
    return None


def main() -> None:
    args = [Path(a) for a in sys.argv[1:]]
    if args:
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(merge(args), indent=1), encoding="utf-8")
    if not DATA.exists():
        sys.exit(f"no results: pass result files or create {DATA}")
    py = sys.executable
    subprocess.run([py, str(HERE / "figures.py"), str(DATA)], check=True)
    subprocess.run([py, str(HERE / "final_report.py"), str(DATA)], check=True)
    pdf = to_pdf(DOCX)
    print("report:", DOCX, *(["and", pdf] if pdf else []))


if __name__ == "__main__":
    main()
