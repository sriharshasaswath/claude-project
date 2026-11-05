#!/usr/bin/env python3
"""Helper CLI for the /tailor skill. No API keys; deterministic local work only.

  check                                     verify python-docx/openpyxl are installed
  slug COMPANY ROLE                         -> file-safe name, e.g. Deloitte_Supply-Chain-Analyst
  validate RESUME.json                      check the resume JSON shape
  render RESUME.json --docx OUT [--md OUT]  ATS-friendly DOCX (+ Markdown)
  preview RESUME.json                       print Markdown to stdout
  score RESUME.json JOB.json [--json]       ATS score + missing keywords
  compare BASE.json NEW.json JOB.json       before/after scores
  audit BASE.json NEW.json                  flag numbers/employers/titles/dates not in the base resume
  fetch-job URL                             fallback job-page reader (JSON-LD), prints JSON
  extract-text FILE                         plain text from .docx/.pdf/.txt (to rebuild the base resume)
  add-jobs JOBS.json --tracker X.xlsx --found-for "Company – Role" [--resume R.json]
  log --tracker X.xlsx --company C --role R --url U --before N --after N --file PATH
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _need_deps() -> None:
    missing = []
    for mod, pkg in [("docx", "python-docx"), ("openpyxl", "openpyxl")]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        sys.exit(f"Missing Python packages: {' '.join(missing)}\nInstall with: python3 -m pip install {' '.join(missing)}")


def slug(text: str) -> str:
    text = re.sub(r"[^\w\s&+-]", "", text, flags=re.UNICODE).replace("&", "and").replace("+", "plus")
    return re.sub(r"[\s_-]+", "-", text).strip("-")[:50] or "Unknown"


def cmd_slug(a) -> None:
    print(f"{slug(a.company)}_{slug(a.role)}")


def _load(path: str):
    from resume_schema import load_resume

    return load_resume(path)


def _job(path: str) -> dict:
    job = json.loads(Path(path).read_text(encoding="utf-8"))
    for k in ("required_skills", "preferred_skills", "keywords"):
        if not isinstance(job.get(k, []), list):
            sys.exit(f"{path}: '{k}' must be a list")
    return job


def cmd_validate(a) -> None:
    r = _load(a.resume)
    from resume_schema import all_text

    print(f"OK: {r['contact']['name']} — {len(r['experience'])} roles, {len(all_text(r).split())} words")


def cmd_render(a) -> None:
    _need_deps()
    from render import estimate_pages, to_docx, to_markdown

    r = _load(a.resume)
    order = a.order.split(",") if a.order else None
    print(f"DOCX: {to_docx(r, a.docx, order)}")
    pages = estimate_pages(r)
    print(f"Estimated length: ~{pages} pages" + ("  <- over one page; trim low-relevance content" if pages > 1.0 else ""))
    if a.md:
        Path(a.md).parent.mkdir(parents=True, exist_ok=True)
        Path(a.md).write_text(to_markdown(r, order), encoding="utf-8")
        print(f"MD:   {a.md}")


def cmd_preview(a) -> None:
    from render import to_markdown

    print(to_markdown(_load(a.resume), a.order.split(",") if a.order else None))


def cmd_score(a) -> None:
    from ats import render_report, score_resume

    rep = score_resume(_load(a.resume), _job(a.job))
    print(json.dumps(rep, indent=2) if a.json else render_report(rep))


def cmd_compare(a) -> None:
    from ats import render_report, score_resume

    job = _job(a.job)
    before, after = score_resume(_load(a.base), job), score_resume(_load(a.new), job)
    print(f"ATS score: {before['score']} (base) -> {after['score']} (tailored)\n")
    print("Tailored resume detail:\n" + render_report(after))
    newly = [k for k in after["matched"] if k not in before["matched"]]
    if newly:
        print(f"\nNewly matched keywords: {', '.join(newly)}")


NUM = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|\+|x\b|k\b|m\b|cr\b|lakh)?", re.I)


def cmd_audit(a) -> None:
    """Catch accidental fabrication: anything factual in NEW that isn't in BASE."""
    from resume_schema import all_text

    base, new = _load(a.base), _load(a.new)
    base_text = all_text(base).lower()
    issues = []
    base_nums = {n.strip().lower().replace(",", "") for n in NUM.findall(base_text)}
    for n in sorted({x.strip() for x in NUM.findall(all_text(new))}):
        if n.lower().replace(",", "") not in base_nums:
            issues.append(f"Number '{n}' does not appear in the base resume")
    for key in ("experience", "leadership", "education"):
        base_entries = {(e.get("company") or e.get("school", "")).lower() for e in base[key]}
        for e in new[key]:
            org = (e.get("company") or e.get("school", "")).lower()
            if org not in base_entries:
                issues.append(f"{key}: organisation '{org}' is not in the base resume")
    base_roles = {(e["company"].lower(), e["title"].lower(), e["start"], e["end"]) for e in base["experience"] + base["leadership"]}
    for e in new["experience"] + new["leadership"]:
        if (e["company"].lower(), e["title"].lower(), e["start"], e["end"]) not in base_roles:
            issues.append(f"Role changed or new: '{e['title']}' at '{e['company']}' ({e['start']}–{e['end']})")
    base_certs = {c["name"].lower() for c in base["certifications"]}
    for c in new["certifications"]:
        if c["name"].lower() not in base_certs:
            issues.append(f"Certification not in base resume: '{c['name']}'")
    for field in ("name", "email", "phone"):
        if new["contact"][field] != base["contact"][field]:
            issues.append(f"Contact {field} changed: '{base['contact'][field]}' -> '{new['contact'][field]}'")
    if issues:
        print("REVIEW THESE (fine only if the user confirmed them in chat):")
        print("\n".join(f"  - {i}" for i in issues))
    else:
        print("OK: no new numbers, employers, roles, dates, certifications, or contact changes.")


def cmd_fetch_job(a) -> None:
    from jobpage import fetch_job

    try:
        print(json.dumps(fetch_job(a.url), indent=2, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 - report any network/HTTP failure plainly
        sys.exit(f"Could not fetch {a.url}: {e}")


def cmd_extract_text(a) -> None:
    p = Path(a.file)
    if p.suffix.lower() == ".docx":
        _need_deps()
        from docx import Document

        d = Document(str(p))
        lines = [para.text for para in d.paragraphs if para.text.strip()]
        for t in d.tables:
            for row in t.rows:
                cells = []
                for c in row.cells:  # merged cells repeat; keep each once
                    if c.text.strip() and c.text not in cells:
                        cells.append(c.text)
                if cells:
                    lines.append(" | ".join(cells))
        print("\n".join(lines))
    elif p.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("Install pypdf to read PDFs: python3 -m pip install pypdf")
        print("\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages))
    else:
        print(p.read_text(encoding="utf-8"))


def cmd_add_jobs(a) -> None:
    _need_deps()
    from ats import match_percent
    from resume_schema import all_text
    from tracker import append_jobs

    data = json.loads(Path(a.jobs).read_text(encoding="utf-8"))
    jobs = data["jobs"] if isinstance(data, dict) else data
    match_fn = None
    if a.resume:
        text = all_text(_load(a.resume))
        match_fn = lambda skills: match_percent(text, skills)  # noqa: E731
    res = append_jobs(Path(a.tracker), jobs, a.found_for, match_fn)
    print(f"Tracker {a.tracker}: added {res['added']}, skipped {res['duplicates_skipped']} duplicates, "
          f"{res['invalid_skipped']} without URL/title; {res['total_rows']} jobs total.")


def cmd_log(a) -> None:
    _need_deps()
    from tracker import log_application

    log_application(Path(a.tracker), company=a.company, role=a.role, url=a.url, before=a.before, after=a.after, resume_file=a.file)
    print(f"Logged {a.company} – {a.role} in {a.tracker}")


def cmd_check(_a) -> None:
    _need_deps()
    print("OK: python-docx and openpyxl are installed.")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(f=cmd_check)
    s = sub.add_parser("slug"); s.add_argument("company"); s.add_argument("role"); s.set_defaults(f=cmd_slug)
    s = sub.add_parser("validate"); s.add_argument("resume"); s.set_defaults(f=cmd_validate)
    s = sub.add_parser("render"); s.add_argument("resume"); s.add_argument("--docx", required=True); s.add_argument("--md")
    s.add_argument("--order", help="Comma-separated section order, e.g. summary,skills,experience,education,..."); s.set_defaults(f=cmd_render)
    s = sub.add_parser("preview"); s.add_argument("resume"); s.add_argument("--order"); s.set_defaults(f=cmd_preview)
    s = sub.add_parser("score"); s.add_argument("resume"); s.add_argument("job"); s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_score)
    s = sub.add_parser("compare"); s.add_argument("base"); s.add_argument("new"); s.add_argument("job"); s.set_defaults(f=cmd_compare)
    s = sub.add_parser("audit"); s.add_argument("base"); s.add_argument("new"); s.set_defaults(f=cmd_audit)
    s = sub.add_parser("fetch-job"); s.add_argument("url"); s.set_defaults(f=cmd_fetch_job)
    s = sub.add_parser("extract-text"); s.add_argument("file"); s.set_defaults(f=cmd_extract_text)
    s = sub.add_parser("add-jobs"); s.add_argument("jobs"); s.add_argument("--tracker", required=True)
    s.add_argument("--found-for", required=True); s.add_argument("--resume"); s.set_defaults(f=cmd_add_jobs)
    s = sub.add_parser("log"); s.add_argument("--tracker", required=True); s.add_argument("--company", required=True)
    s.add_argument("--role", required=True); s.add_argument("--url", default=""); s.add_argument("--before", type=int)
    s.add_argument("--after", type=int); s.add_argument("--file", required=True); s.set_defaults(f=cmd_log)
    a = p.parse_args(argv)
    try:
        a.f(a)
    except (ValueError, FileNotFoundError, KeyError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
