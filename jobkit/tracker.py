"""The running Excel tracker (applications/job_tracker.xlsx).

Sheet "Jobs": every job found by /find-jobs or /tailor, appended and de-duplicated across runs.
Sheet "Tailored Resumes": one row per approved tailored resume.

Columns are matched by header name, so new columns can be added later without breaking
existing files, and users can reorder columns or add their own.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

JOBS_SHEET = "Jobs"
LOG_SHEET = "Tailored Resumes"

# (header, width, job-dict key or None for computed/user columns)
JOB_COLUMNS = [
    ("Date Found", 12, None), ("Found For", 26, None), ("Type", 11, "type"), ("Match %", 9, None),
    ("Job Title", 34, "title"), ("Company", 22, "company"), ("Location", 20, "location"),
    ("Work Mode", 11, "work_mode"), ("Experience", 12, "experience"), ("Salary / Stipend", 18, "salary"),
    ("Duration", 11, "duration"), ("Date Posted", 12, "date_posted"), ("Deadline", 12, "deadline"),
    ("Source", 16, "source"), ("Found Via", 14, "found_via"), ("Apply Via", 30, "apply_via"),
    ("Poster / Contact", 26, "contact"), ("Key Skills", 36, "key_skills"), ("Why Relevant", 40, "why_relevant"),
    ("URL", 50, "url"), ("Status", 13, None), ("Notes", 30, None),
]
LOG_COLUMNS = [
    ("Date", 12, None), ("Company", 22, None), ("Role", 32, None), ("Job URL", 50, None), ("ATS Before", 11, None),
    ("ATS After", 10, None), ("Resume File", 55, None), ("Status", 13, None), ("Notes", 30, None),
]
URL_HEADERS = {"URL", "Job URL", "Apply Via", "Poster / Contact"}
TRACKING_PARAMS = (
    "utm_", "ref", "src", "source", "trk", "tracking", "gh_src", "lever-origin", "refid", "trackingid",
    "currentjobid", "eborigin", "originalsubdomain", "rcm", "lipi", "from", "vjk", "jsa",
)
INTERN_WORDS = ("intern", "internship", "trainee", "apprentice", "summer analyst", "summer associate", "co-op", "fellowship")


def canonical_url(url: str) -> str:
    """Drop tracking params, fragments, www, trailing slashes and case so the same posting dedupes."""
    p = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(TRACKING_PARAMS)]
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/").lower()
    if host.endswith("linkedin.com") and "/jobs/view/" in path:  # /jobs/view/title-slug-12345 -> id only
        path = "/jobs/view/" + path.rsplit("-", 1)[-1].rsplit("/", 1)[-1]
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def guess_type(title: str, text: str = "") -> str:
    t = f"{title} {text[:400]}".lower()
    return "Internship" if any(w in t for w in INTERN_WORDS) else ""


def _headers(ws) -> list[str]:
    return [str(c.value) if c.value is not None else "" for c in ws[1]]


def _ensure_sheet(wb, name: str, columns) -> None:
    if name in wb.sheetnames:
        ws = wb[name]
        have = _headers(ws)
        for header, _, _ in columns:
            if header not in have:
                ws.cell(row=1, column=len(have) + 1, value=header)
                have.append(header)
    else:
        ws = wb.create_sheet(name)
        ws.append([c[0] for c in columns])
    fill = PatternFill("solid", fgColor="1F3864")
    widths = {c[0]: c[1] for c in columns}
    for i, header in enumerate(_headers(ws), 1):
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        if header in widths:
            ws.column_dimensions[get_column_letter(i)].width = widths[header]
    ws.freeze_panes = "A2"


def open_tracker(path: Path):
    if path.exists():
        wb = load_workbook(str(path))
        if "Similar Jobs" in wb.sheetnames and JOBS_SHEET not in wb.sheetnames:  # older layout
            wb["Similar Jobs"].title = JOBS_SHEET
    else:
        wb = Workbook()
        wb.remove(wb.active)
    _ensure_sheet(wb, JOBS_SHEET, JOB_COLUMNS)
    _ensure_sheet(wb, LOG_SHEET, LOG_COLUMNS)
    return wb


def _append(ws, values: dict[str, Any]) -> None:
    headers = _headers(ws)
    row = ws.max_row + 1
    for header, value in values.items():
        if header in headers and value not in (None, ""):
            ws.cell(row=row, column=headers.index(header) + 1, value=value)


def _format_rows(ws, first_row: int) -> None:
    headers = _headers(ws)
    for r in range(first_row, ws.max_row + 1):
        for c, header in enumerate(headers, 1):
            cell = ws.cell(row=r, column=c)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if header in URL_HEADERS and isinstance(cell.value, str) and cell.value.startswith("http"):
                cell.hyperlink = cell.value
                cell.font = Font(color="0563C1", underline="single")
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"


def _as_list(v: Any) -> list[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return []


def append_jobs(
    path: Path,
    jobs: list[dict[str, Any]],
    found_for: str,
    match_fn: Callable[[list[str]], int | None] | None = None,
) -> dict[str, Any]:
    """Append jobs not already in the tracker. Returns counts (overall and per source)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = open_tracker(path)
    ws = wb[JOBS_SHEET]
    headers = _headers(ws)
    url_i, title_i, comp_i = headers.index("URL"), headers.index("Job Title"), headers.index("Company")

    seen_urls, seen_pairs = set(), set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[url_i]:
            seen_urls.add(canonical_url(str(row[url_i])))
        if row[title_i] and row[comp_i]:
            seen_pairs.add((str(row[title_i]).strip().lower(), str(row[comp_i]).strip().lower()))

    today = dt.date.today().isoformat()
    added, dupes, invalid = 0, 0, 0
    by_source: dict[str, int] = {}
    new_rows: list[dict[str, Any]] = []
    for j in jobs:
        url = str(j.get("url", "")).strip()
        title, company = str(j.get("title", "")).strip(), str(j.get("company", "")).strip()
        if not url.startswith(("http://", "https://")) or not title:
            invalid += 1
            continue
        key, pair = canonical_url(url), (title.lower(), company.lower())
        if key in seen_urls or (company and pair in seen_pairs):
            dupes += 1
            continue
        seen_urls.add(key)
        if company:
            seen_pairs.add(pair)
        skills = _as_list(j.get("key_skills"))
        values: dict[str, Any] = {"Date Found": today, "Found For": found_for, "Status": "Not applied"}
        for header, _, k in JOB_COLUMNS:
            if k and k != "key_skills":
                v = j.get(k, "")
                values[header] = ", ".join(v) if isinstance(v, list) else (str(v).strip() if v is not None else "")
        values["Key Skills"] = ", ".join(skills)
        values["Why Relevant"] = values.get("Why Relevant") or str(j.get("why_similar", "")).strip()
        values["Type"] = values.get("Type") or guess_type(title, str(j.get("description", ""))) or "Full-time"
        values["Match %"] = match_fn(skills) if match_fn else None
        new_rows.append(values)
        src = values.get("Source") or "unknown"
        by_source[src] = by_source.get(src, 0) + 1
        added += 1

    new_rows.sort(key=lambda v: -(v.get("Match %") or 0))
    first = ws.max_row + 1
    for values in new_rows:
        _append(ws, values)
    _format_rows(ws, first)
    wb.save(str(path))
    return {
        "added": added, "duplicates_skipped": dupes, "invalid_skipped": invalid,
        "total_rows": ws.max_row - 1, "added_by_source": by_source,
    }


def log_application(path: Path, *, company: str, role: str, url: str, before: int | None, after: int | None, resume_file: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = open_tracker(path)
    ws = wb[LOG_SHEET]
    first = ws.max_row + 1
    _append(ws, {
        "Date": dt.date.today().isoformat(), "Company": company, "Role": role, "Job URL": url,
        "ATS Before": before, "ATS After": after, "Resume File": resume_file, "Status": "Tailored",
    })
    _format_rows(ws, first)
    wb.save(str(path))
