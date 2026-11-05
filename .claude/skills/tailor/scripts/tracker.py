"""The running Excel tracker: similar jobs (appended, de-duplicated) and a log of tailored resumes."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

JOBS_SHEET = "Similar Jobs"
LOG_SHEET = "Tailored Resumes"

JOB_COLUMNS = [
    ("Date Found", 12), ("Found For", 28), ("Match %", 9), ("Job Title", 34), ("Company", 22),
    ("Location", 20), ("Work Mode", 11), ("Experience", 12), ("Salary", 18), ("Date Posted", 12),
    ("Source", 14), ("Key Skills", 40), ("Why Similar", 42), ("URL", 50), ("Status", 13), ("Notes", 30),
]
LOG_COLUMNS = [
    ("Date", 12), ("Company", 22), ("Role", 32), ("Job URL", 50), ("ATS Before", 11),
    ("ATS After", 10), ("Resume File", 55), ("Status", 13), ("Notes", 30),
]
TRACKING_PARAMS = ("utm_", "ref", "src", "source", "trk", "tracking", "gh_src", "lever-origin", "refid", "trackingid")


def canonical_url(url: str) -> str:
    """Drop tracking params, fragments, trailing slashes and case so the same posting dedupes."""
    p = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(TRACKING_PARAMS)]
    host = p.netloc.lower().removeprefix("www.")
    return urlunsplit(("https", host, p.path.rstrip("/").lower(), urlencode(sorted(query)), ""))


def _style_header(ws, columns) -> None:
    fill = PatternFill("solid", fgColor="1F3864")
    for i, (_, width) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"


def _sheet(wb, name: str, columns):
    if name in wb.sheetnames:
        return wb[name]
    ws = wb.create_sheet(name)
    ws.append([c for c, _ in columns])
    _style_header(ws, columns)
    return ws


def open_tracker(path: Path):
    if path.exists():
        wb = load_workbook(str(path))
    else:
        wb = Workbook()
        wb.remove(wb.active)
    _sheet(wb, JOBS_SHEET, JOB_COLUMNS)
    _sheet(wb, LOG_SHEET, LOG_COLUMNS)
    return wb


def _finish_rows(ws, columns, first_new_row: int, url_cols: list[str]) -> None:
    names = [c for c, _ in columns]
    for row in range(first_new_row, ws.max_row + 1):
        for col in range(1, len(columns) + 1):
            ws.cell(row=row, column=col).alignment = Alignment(vertical="top", wrap_text=True)
        for uc in url_cols:
            cell = ws.cell(row=row, column=names.index(uc) + 1)
            if isinstance(cell.value, str) and cell.value.startswith("http"):
                cell.hyperlink = cell.value
                cell.font = Font(color="0563C1", underline="single")
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{ws.max_row}"


def append_jobs(path: Path, jobs: list[dict[str, Any]], found_for: str, match_fn=None) -> dict[str, int]:
    """Append jobs that are not already in the tracker. Returns counts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = open_tracker(path)
    ws = wb[JOBS_SHEET]
    names = [c for c, _ in JOB_COLUMNS]
    url_i, title_i, comp_i = names.index("URL"), names.index("Job Title"), names.index("Company")

    seen_urls, seen_pairs = set(), set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[url_i]:
            seen_urls.add(canonical_url(str(row[url_i])))
        if row[title_i] and row[comp_i]:
            seen_pairs.add((str(row[title_i]).strip().lower(), str(row[comp_i]).strip().lower()))

    first_new = ws.max_row + 1
    added = skipped = invalid = 0
    today = dt.date.today().isoformat()
    new_rows = []
    for j in jobs:
        url = str(j.get("url", "")).strip()
        title, company = str(j.get("title", "")).strip(), str(j.get("company", "")).strip()
        if not url.startswith(("http://", "https://")) or not title:
            invalid += 1
            continue
        key, pair = canonical_url(url), (title.lower(), company.lower())
        if key in seen_urls or (company and pair in seen_pairs):
            skipped += 1
            continue
        seen_urls.add(key)
        seen_pairs.add(pair)
        skills = j.get("key_skills") or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",")]
        pct = match_fn(skills) if match_fn else None
        new_rows.append([
            today, found_for, pct, title, company, j.get("location", ""), j.get("work_mode", ""),
            j.get("experience", ""), j.get("salary", ""), j.get("date_posted", ""), j.get("source", ""),
            ", ".join(skills), j.get("why_similar", ""), url, "Not applied", "",
        ])
        added += 1
    new_rows.sort(key=lambda r: -(r[2] or 0))
    for r in new_rows:
        ws.append(r)
    _finish_rows(ws, JOB_COLUMNS, first_new, ["URL"])
    wb.save(str(path))
    return {"added": added, "duplicates_skipped": skipped, "invalid_skipped": invalid, "total_rows": ws.max_row - 1}


def log_application(path: Path, *, company: str, role: str, url: str, before: int | None, after: int | None, resume_file: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = open_tracker(path)
    ws = wb[LOG_SHEET]
    first_new = ws.max_row + 1
    ws.append([dt.date.today().isoformat(), company, role, url, before, after, resume_file, "Tailored", ""])
    _finish_rows(ws, LOG_COLUMNS, first_new, ["Job URL"])
    wb.save(str(path))
