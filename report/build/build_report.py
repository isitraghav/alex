"""Builds report/alex_LLM_Tool_Use_Benchmark_Report.docx, optionally from one bench JSON.

    python report/build/make_report.py results/bench-XXXX.json   # charts + docx + pdf in one go
    python report/build/build_report.py [report/build/data/bench.json]

Without a bench JSON the report is built in "protocol" mode: methodology, knowledge graph,
pre-registered hypotheses and ethics are complete; the results sections say how to run them.

Content lives in sections.py (methodology etc.), discussion.py (results-dependent text)
and literature_survey.md (literature review, rendered from Markdown)."""
import json
import re
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
from alex import fuzzy, kg  # noqa: E402
from alex.diagnose import RULES as XRULES  # noqa: E402
from alex.prompts import CASES, FAIR_PAIRS, SUITE_HASH, VARIANTS  # noqa: E402
from alex.stats import HYPOTHESES, analyze  # noqa: E402
from alex.tools import SCHEMAS  # noqa: E402

FIG = Path(__file__).parent / "fig"
OUT = ROOT / "report" / "alex_LLM_Tool_Use_Benchmark_Report.docx"
_src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
REP = json.loads(_src.read_text(encoding="utf-8")) if _src and _src.exists() else None
if REP and not any(k.startswith("claude-") for k in REP.get("summary", {})):
    REP = None                       # e.g. the open-model pilot file: not results of this study
PENDING = REP is None
SUMM = REP["summary"] if REP else {}
AN = analyze(REP) if REP else None   # recomputed from the runs: CIs, Pareto front, hypotheses
RANKED = sorted(SUMM, key=lambda m: (-SUMM[m]["score"], -SUMM[m]["rating"]["suitability"]))
N_TESTS = sum(len(re.findall(r"^def test_", f.read_text(encoding="utf-8"), re.M))
              for f in (ROOT / "tests").glob("test_*.py"))
nice = lambda m: m.replace("claude-", "Claude ").replace("-5-5", " 5.5").replace("haiku", "Haiku").replace("sonnet", "Sonnet").replace("opus", "Opus")
short = lambda k: nice(k.split("@")[0]) + (f" · {k.split('@')[1]}" if "@" in k else "")
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



import re as _re


def _runs_md(p, text):
    """Add text with **bold** and *italic* spans as runs."""
    for i, part in enumerate(_re.split(r"\*\*", text)):
        for j, sub in enumerate(_re.split(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", part)):
            if sub:
                r = p.add_run(sub.replace("`", ""))
                r.bold = i % 2 == 1
                r.italic = j % 2 == 1


def _orient(landscape):
    from docx.enum.section import WD_ORIENT
    ns = doc.add_section(WD_SECTION.NEW_PAGE)
    ns.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    ns.page_width, ns.page_height = (Cm(29.7), Cm(21)) if landscape else (Cm(21), Cm(29.7))
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(ns, side, Cm(1.8) if landscape else getattr(sec, side))
    return ns


def MD(path, level_offset=0, skip_title=True, number_prefix=None):
    """Render a simple Markdown file: #-headings, |tables|, - bullets, paragraphs.
    Tables with 8+ columns go on their own landscape pages."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    i, first, sub = 0, True, 0
    landscape_open = [False]
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1; continue
        if ln.startswith("#"):
            lvl = len(ln) - len(ln.lstrip("#"))
            text = ln.lstrip("#").strip()
            if not (skip_title and first and lvl == 1):
                text = text.replace("**", "")
                if number_prefix and lvl == 2:
                    sub += 1
                    text = f"{number_prefix}.{sub} " + _re.sub(r"^\d+(\.\d+)*\.?\s+", "", text)
                # a heading directly above a wide table moves onto the landscape page with it
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and lines[j].lstrip().startswith("|") and lines[j].count("|") - 1 >= 8:
                    _orient(True)
                    landscape_open[0] = True
                H(text, min(3, max(1, lvl + level_offset)))
            first = False
            i += 1; continue
        first = False
        if ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(_re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append([c.replace("**", "").replace("`", "") for c in cells])
                i += 1
            if rows:
                n = len(rows[0])
                wide = n >= 8
                if wide and not landscape_open[0]:
                    _orient(True)
                landscape_open[0] = False
                T(rows[0], [r + [""] * (n - len(r)) for r in rows[1:]], size=7 if n > 6 else 8)
                if wide:
                    _orient(False)
            continue
        m = _re.match(r"\s*(?:[-*]|\d+\.)\s+(.*)", ln)
        if m:
            p = doc.add_paragraph(style="List Bullet"); _runs_md(p, m.group(1))
            i += 1; continue
        buf = [ln.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not _re.match(r"\s*([#|]|[-*]\s|\d+\.\s)", lines[i]):
            buf.append(lines[i].strip()); i += 1
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        _runs_md(p, " ".join(buf))


HERE = Path(__file__).parent

exec((HERE / "sections.py").read_text(encoding="utf-8"))
exec((HERE / "discussion.py").read_text(encoding="utf-8"))

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
