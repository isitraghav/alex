"""One command from a benchmark result to the finished report.

    python report/build/make_report.py results/bench-XXXX.json   # results edition
    python report/build/make_report.py                           # protocol edition (no results yet)
    python report/build/make_report.py results/a.json results/b.json   # merge single-model runs first

Steps: (merge) -> copy to report/build/data/bench.json -> charts -> .docx -> .pdf.
The PDF step needs Microsoft Word (Windows, via COM) or LibreOffice (`soffice`) and is
skipped with a message if neither is available. Needs the `report` extra:
`uv sync --extra report` (python-docx, matplotlib).
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
DOCX = ROOT / "report" / "alex_LLM_Tool_Use_Benchmark_Report.docx"


def merge(paths: list[Path]) -> dict:
    reps = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    hashes = {r["suite_hash"] for r in reps}
    if len(hashes) > 1:
        sys.exit(f"cannot merge reports from different suites: {hashes}")
    out = dict(reps[0])
    out["summary"] = {k: v for r in reps for k, v in r["summary"].items()}
    out["runs"] = [x for r in reps for x in r["runs"]]
    out["variants"] = sorted({v for r in reps for v in r.get("variants", [])})
    out.pop("analysis", None)   # recomputed by the report builder
    return out


def to_pdf(docx: Path) -> Path | None:
    pdf = docx.with_suffix(".pdf")
    if sys.platform == "win32":
        ps = (
            "$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
            f"$d = $w.Documents.Open('{docx}'); $d.Fields.Update() | Out-Null; "
            "foreach ($t in $d.TablesOfContents) { $t.Update() }; "
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
        rep = merge(args) if len(args) > 1 else json.loads(args[0].read_text(encoding="utf-8"))
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(rep, indent=1), encoding="utf-8")
        src = [str(DATA)]
    else:
        src = []
    py = sys.executable
    subprocess.run([py, str(HERE / "charts.py"), *src], check=True)
    subprocess.run([py, str(HERE / "build_report.py"), *src], check=True)
    pdf = to_pdf(DOCX)
    print("report:", DOCX, *(["and", pdf] if pdf else []))


if __name__ == "__main__":
    main()
