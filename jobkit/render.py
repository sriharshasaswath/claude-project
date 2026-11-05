"""Render a resume JSON to an ATS-friendly DOCX and to Markdown (for previewing in chat)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

SECTION_ORDER_DEFAULT = ["summary", "skills", "experience", "projects", "education", "certifications", "leadership", "additional"]
HEADINGS = {
    "summary": "Summary",
    "skills": "Skills",
    "experience": "Experience",
    "projects": "Projects",
    "education": "Education",
    "certifications": "Certifications",
    "leadership": "Leadership & Activities",
    "additional": "Additional Information",
}


def dates(start: str, end: str) -> str:
    return " – ".join(x for x in [start, end] if x)


def estimate_pages(r: dict[str, Any], chars_per_line: int = 112, lines_per_page: int = 60) -> float:
    """Rough A4 page estimate for the DOCX layout (10pt Calibri, 0.6in margins)."""
    import math

    def n(text: str, indent: int = 0) -> int:
        return max(1, math.ceil(len(text) / (chars_per_line - indent))) if text else 0

    lines = 2 + (1 if contact_line(r["contact"]) else 0) + (1 if r["headline"] else 0)
    sections = sum(1 for k in ["skills", "experience", "projects", "education", "certifications", "leadership", "additional"] if r[k])
    sections += 1 if r["summary"] else 0
    lines += 2 * sections
    lines += n(r["summary"])
    lines += sum(n(f"{g['category']}: {', '.join(g['skills'])}") for g in r["skills"])
    for e in r["experience"] + r["leadership"]:
        lines += 1.2 + sum(n(b, 8) for b in e["bullets"])
    for p in r["projects"]:
        lines += 1.2 + sum(n(b, 8) for b in p["bullets"])
    for ed in r["education"]:
        lines += 1 + sum(n(d, 8) for d in ed["details"])
    for c in r["certifications"]:
        lines += 1.2 + n(c["details"], 8)
    lines += sum(n(f"{a['label']}: {a['text']}") for a in r["additional"])
    return round(lines / lines_per_page, 2)


def contact_line(c: dict[str, Any]) -> str:
    return " | ".join(x for x in [c["email"], c["phone"], c["location"], *c["links"]] if x)


# ---------------------------------------------------------------- Markdown

def to_markdown(r: dict[str, Any], order: list[str] | None = None) -> str:
    c = r["contact"]
    out = [f"# {c['name']}"]
    if contact_line(c):
        out.append(contact_line(c))
    if r["headline"]:
        out.append(f"\n**{r['headline']}**")
    for sec in order or SECTION_ORDER_DEFAULT:
        if sec == "summary" and r["summary"]:
            out += ["\n## Summary", r["summary"]]
        elif sec == "skills" and r["skills"]:
            out.append("\n## Skills")
            out += [f"- **{g['category']}:** {', '.join(g['skills'])}" for g in r["skills"]]
        elif sec in ("experience", "leadership") and r[sec]:
            out.append(f"\n## {HEADINGS[sec]}")
            for e in r[sec]:
                loc = f", {e['location']}" if e["location"] else ""
                d = dates(e["start"], e["end"])
                out.append(f"\n**{e['title']}** — {e['company']}{loc}" + (f"  \n*{d}*" if d else ""))
                out += [f"- {b}" for b in e["bullets"]]
        elif sec == "projects" and r["projects"]:
            out.append("\n## Projects")
            for p in r["projects"]:
                meta = " — ".join(x for x in [p["org"], p["dates"], p["link"]] if x)
                out.append(f"\n**{p['name']}**" + (f"  \n*{meta}*" if meta else ""))
                out += [f"- {b}" for b in p["bullets"]]
        elif sec == "education" and r["education"]:
            out.append("\n## Education")
            for ed in r["education"]:
                tail = " | ".join(x for x in [ed["score"], dates(ed["start"], ed["end"])] if x)
                out.append(f"- **{ed['degree']}**, {ed['school']}" + (f" — {tail}" if tail else ""))
                out += [f"  - {d}" for d in ed["details"]]
        elif sec == "certifications" and r["certifications"]:
            out.append("\n## Certifications")
            for ce in r["certifications"]:
                head = " — ".join(x for x in [ce["name"], ce["issuer"], ce["date"]] if x)
                out.append(f"- **{head}**" + (f": {ce['details']}" if ce["details"] else ""))
        elif sec == "additional" and r["additional"]:
            out.append("\n## Additional Information")
            out += [f"- **{a['label']}:** {a['text']}" for a in r["additional"]]
    return "\n".join(out).strip() + "\n"


# ---------------------------------------------------------------- DOCX

def _heading(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    # A paragraph bottom border (not a table, shape, or image) keeps the file ATS-safe.
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in {"w:val": "single", "w:sz": "6", "w:space": "1", "w:color": "1F3864"}.items():
        bottom.set(qn(k), v)
    bdr.append(bottom)
    pPr.append(bdr)


def _left_right(doc: Document, left: str, right: str, sub: str = "", width: float = 7.0) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.tab_stops.add_tab_stop(Inches(width), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run(left).bold = True
    if sub:
        p.add_run(f" | {sub}")
    if right:
        p.add_run(f"\t{right}")


def _bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(0)
    p.add_run(text)


def _label_line(doc: Document, label: str, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.add_run(f"{label}: ").bold = True
    p.add_run(text)


def to_docx(r: dict[str, Any], path: str | Path, order: list[str] | None = None) -> Path:
    """Single column, no tables/text boxes/images, standard headings, real text bullets."""
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)  # A4
    sec.left_margin = sec.right_margin = Inches(0.6)
    sec.top_margin = sec.bottom_margin = Inches(0.5)
    text_width = 8.27 - 1.2
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(0)

    c = r["contact"]
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(c["name"])
    run.bold = True
    run.font.size = Pt(16)
    if contact_line(c):
        p = doc.add_paragraph(contact_line(c))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if r["headline"]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(r["headline"]).bold = True

    for s in order or SECTION_ORDER_DEFAULT:
        if s == "summary" and r["summary"]:
            _heading(doc, "Summary")
            doc.add_paragraph(r["summary"])
        elif s == "skills" and r["skills"]:
            _heading(doc, "Skills")
            for g in r["skills"]:
                _label_line(doc, g["category"], ", ".join(g["skills"]))
        elif s in ("experience", "leadership") and r[s]:
            _heading(doc, HEADINGS[s])
            for e in r[s]:
                _left_right(doc, e["title"], dates(e["start"], e["end"]), e["company"] + (f", {e['location']}" if e["location"] else ""), text_width)
                for b in e["bullets"]:
                    _bullet(doc, b)
        elif s == "projects" and r["projects"]:
            _heading(doc, "Projects")
            for pr in r["projects"]:
                _left_right(doc, pr["name"], pr["dates"], " | ".join(x for x in [pr["org"], pr["link"]] if x), text_width)
                for b in pr["bullets"]:
                    _bullet(doc, b)
        elif s == "education" and r["education"]:
            _heading(doc, "Education")
            for ed in r["education"]:
                _left_right(doc, ed["degree"], dates(ed["start"], ed["end"]), " | ".join(x for x in [ed["school"], ed["score"]] if x), text_width)
                for d in ed["details"]:
                    _bullet(doc, d)
        elif s == "certifications" and r["certifications"]:
            _heading(doc, "Certifications")
            for ce in r["certifications"]:
                _left_right(doc, ce["name"], ce["date"], ce["issuer"], text_width)
                if ce["details"]:
                    _bullet(doc, ce["details"])
        elif s == "additional" and r["additional"]:
            _heading(doc, "Additional Information")
            for a in r["additional"]:
                _label_line(doc, a["label"], a["text"])

    doc.core_properties.title = f"{c['name']} - Resume"
    doc.core_properties.author = c["name"]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path
