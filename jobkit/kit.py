#!/usr/bin/env python3
"""Helper CLI for the /tailor and /find-jobs skills. No API keys; deterministic local work only.

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
  add-jobs JOBS.json [MORE.json ...] --tracker X.xlsx --found-for "..." [--resume R.json]
  detect-ats URL [URL ...]                  which career-portal ATS a URL uses (+ watchlist entry)
  watch add URL --name NAME | watch list | watch remove NAME   manage job_search/watchlist.json
  scan-boards --keywords "a,b" [--exclude ...] [--locations ...] [--type internship|fulltime|any]
              [--days N] [--title-only] --out FILE.json     scan every watchlist career portal
  search-urls --keywords "..." [--location ..] [--type ..] [--days N]   board search links (browser mode)
  merge-analyses A.json B.json ... --title T --out OUT.json   combine several job analyses into one role profile
  export-md --tracker X.xlsx --out JOBS.md [--limit N]        phone-friendly Markdown view of the tracker
  env                                       cloud/mobile vs local, git branches, saved preferences
  config [KEY [VALUE]]                      show/set job_search/config.json (auto_save, save_branch)
  log --tracker X.xlsx --company C --role R --url U --before N --after N --file PATH
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _use_project_venv() -> None:
    """If the deps are missing here but the repo has a .venv (e.g. Homebrew Python on macOS,
    which blocks system-wide pip installs), re-run this command with the venv's Python."""
    import importlib.util
    import os

    if importlib.util.find_spec("docx") and importlib.util.find_spec("openpyxl"):
        return
    root = Path(__file__).resolve().parent.parent
    for py in (root / ".venv/bin/python3", root / ".venv/Scripts/python.exe"):
        if py.exists() and Path(sys.executable).resolve() != py.resolve() and not os.environ.get("JOBKIT_REEXEC"):
            os.environ["JOBKIT_REEXEC"] = "1"
            os.execv(str(py), [str(py), *sys.argv])


_use_project_venv()


def _need_deps() -> None:
    missing = []
    for mod, pkg in [("docx", "python-docx"), ("openpyxl", "openpyxl")]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        sys.exit(f"Missing Python packages: {' '.join(missing)}\nInstall them in a project venv (works everywhere, incl. Homebrew Python):\n"
                 "  python3 -m venv .venv && .venv/bin/python3 -m pip install -r requirements.txt")


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

    jobs = []
    for f in a.jobs:
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        jobs.extend(data["jobs"] if isinstance(data, dict) else data)
    match_fn = None
    if a.resume:
        text = all_text(_load(a.resume))
        match_fn = lambda skills: match_percent(text, skills)  # noqa: E731
    res = append_jobs(Path(a.tracker), jobs, a.found_for, match_fn)
    print(f"Tracker {a.tracker}: added {res['added']}, skipped {res['duplicates_skipped']} already in tracker, "
          f"{res['invalid_skipped']} without URL/title; {res['total_rows']} jobs total.")
    for src, n in sorted(res["added_by_source"].items(), key=lambda x: -x[1]):
        print(f"  + {n:3d}  {src}")


WATCHLIST = Path("job_search/watchlist.json")


def _read_watchlist(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def cmd_detect_ats(a) -> None:
    from boards import detect_ats

    for url in a.urls:
        e = detect_ats(url)
        print(json.dumps({"url": url, "entry": e}))


def cmd_watch(a) -> None:
    from boards import detect_ats, entry_key

    path = Path(a.watchlist)
    wl = _read_watchlist(path)
    if a.action == "list":
        for e in sorted(wl, key=lambda x: x["name"].lower()):
            print(f"{e['name']:<30} {e['ats']:<16} {e.get('slug') or e.get('host', '') + '/' + e.get('site', '')}")
        print(f"{len(wl)} companies")
        return
    if a.action == "remove":
        keep = [e for e in wl if e["name"].lower() != (a.name or "").lower()]
        path.write_text(json.dumps(keep, indent=2) + "\n", encoding="utf-8")
        print(f"Removed {len(wl) - len(keep)}")
        return
    if not a.target:
        sys.exit("watch add needs a careers/job URL")
    e = detect_ats(a.target)
    if not e:
        sys.exit(f"Not a supported ATS URL (Greenhouse/Lever/Ashby/SmartRecruiters/Workable/Recruitee/Workday): {a.target}")
    e = {"name": a.name or (e.get("slug") or e.get("tenant", "")).replace("-", " ").title(), **e}
    if entry_key(e) in {entry_key(x) for x in wl}:
        print(f"Already watching: {e['name']}")
        return
    wl.append(e)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(wl, indent=2) + "\n", encoding="utf-8")
    print(f"Watching {e['name']} ({e['ats']}); {len(wl)} companies")


def _csv(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def cmd_scan_boards(a) -> None:
    from boards import scan

    wl = _read_watchlist(Path(a.watchlist))
    if a.only:
        wanted = {x.lower() for x in _csv(a.only)}
        wl = [e for e in wl if e["name"].lower() in wanted]
    if not wl:
        sys.exit(f"Watchlist {a.watchlist} is empty. Add companies with: kit watch add <careers-url> --name <Company>")
    jobs, report = scan(wl, keywords=_csv(a.keywords), exclude=_csv(a.exclude), locations=_csv(a.locations),
                        job_type=a.type, days=a.days, title_only=a.title_only)
    for j in jobs:
        j.pop("description", None) if a.no_description else None
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"jobs": jobs}, indent=2, ensure_ascii=False), encoding="utf-8")
    errors = [r for r in report if "error" in r]
    print(f"Scanned {len(wl)} career portals: {len(jobs)} matching jobs -> {a.out}")
    for r in report:
        if "error" not in r and r["matched"]:
            print(f"  {r['matched']:3d}/{r['postings']:<4d} {r['company']} ({r['ats']})")
    if errors:
        print(f"{len(errors)} portals failed:")
        for r in errors:
            print(f"  ! {r['company']} ({r['ats']}): {r['error']}")


def cmd_search_urls(a) -> None:
    from boards import search_urls

    for name, url in search_urls(a.keywords, a.location, a.type, a.days).items():
        print(f"{name:<24} {url}")


def cmd_merge_analyses(a) -> None:
    """Combine several job analyses into one role profile.

    A skill is 'required' for the role when at least max(2, 40%) of postings require it, or when
    at least 60% of postings mention it at all. Everything else mentioned goes to 'preferred'.
    """
    import math
    from collections import Counter

    analyses = [json.loads(Path(f).read_text(encoding="utf-8")) for f in a.files]
    n = len(analyses)
    req_count, any_count, kw_count = Counter(), Counter(), Counter()
    spelling: dict[str, str] = {}
    for an in analyses:
        req = {t.strip().lower() for t in an.get("required_skills") or [] if t.strip()}
        pref = {t.strip().lower() for t in an.get("preferred_skills") or [] if t.strip()}
        kws = {t.strip().lower() for t in an.get("keywords") or [] if t.strip()}
        for t in (an.get("required_skills") or []) + (an.get("preferred_skills") or []) + (an.get("keywords") or []):
            spelling.setdefault(t.strip().lower(), t.strip())
        req_count.update(req)
        any_count.update(req | pref)
        kw_count.update(kws - req - pref)
    need_req, need_any = max(2, math.ceil(0.4 * n)), max(2, math.ceil(0.6 * n))
    order = sorted(any_count, key=lambda t: (-req_count[t], -any_count[t], t))
    required = [spelling[t] for t in order if req_count[t] >= need_req or any_count[t] >= need_any]
    preferred = [spelling[t] for t in order if spelling[t] not in required][:15]
    keywords = [spelling[t] for t, c in sorted(kw_count.items(), key=lambda x: (-x[1], x[0])) if c >= 2][:20]
    out = {
        "url": "", "title": a.title, "company": f"{n} postings",
        "location": ", ".join(dict.fromkeys(x.get("location", "") for x in analyses if x.get("location")))[:200],
        "seniority": Counter(x.get("seniority", "") for x in analyses).most_common(1)[0][0] if analyses else "",
        "required_skills": required, "preferred_skills": preferred, "keywords": keywords,
        "responsibilities": [r for x in analyses for r in (x.get("responsibilities") or [])][:12],
        "search_queries": list(dict.fromkeys(q for x in analyses for q in (x.get("search_queries") or [])))[:12],
        "sources": [x.get("url", "") for x in analyses],
    }
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Role profile from {n} postings -> {a.out}\n  required: {', '.join(required) or '(none recurring)'}"
          f"\n  preferred: {', '.join(preferred)}")


def cmd_export_md(a) -> None:
    _need_deps()
    from openpyxl import load_workbook

    ws = load_workbook(a.tracker, read_only=True)["Jobs"]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        sys.exit("Tracker is empty")
    h = [str(x) if x else "" for x in rows[0]]
    get = lambda r, k: (str(r[h.index(k)]) if k in h and r[h.index(k)] not in (None, "") else "")  # noqa: E731
    data = [r for r in rows[1:] if any(r)]
    data.sort(key=lambda r: (get(r, "Date Found"), int(get(r, "Match %") or 0)), reverse=True)
    lines = [f"# Job tracker ({len(data)} jobs)", "", "Newest first, then best match. Full details: `applications/job_tracker.xlsx`.", "",
             "| Found | Match | Role | Company | Location | Type | Pay | Posted | Status |", "|---|---|---|---|---|---|---|---|---|"]
    esc = lambda x: x.replace("|", "/").replace("\n", " ")  # noqa: E731
    for r in data[: a.limit]:
        role = esc(get(r, "Job Title"))
        url = get(r, "URL")
        lines.append("| " + " | ".join([
            get(r, "Date Found"), (get(r, "Match %") + "%") if get(r, "Match %") else "",
            f"[{role}]({url})" if url else role, esc(get(r, "Company")), esc(get(r, "Location")),
            get(r, "Type"), esc(get(r, "Salary / Stipend")), get(r, "Date Posted"), get(r, "Status"),
        ]) + " |")
    posts = [r for r in data if get(r, "Apply Via") or get(r, "Poster / Contact")]
    if posts:
        lines += ["", "## Direct contacts (hiring posts)", ""]
        for r in posts[:30]:
            lines.append(f"- **{esc(get(r, 'Job Title'))}** at {esc(get(r, 'Company'))}: apply via {esc(get(r, 'Apply Via'))}"
                         + (f"; poster {esc(get(r, 'Poster / Contact'))}" if get(r, "Poster / Contact") else "") + f" ([post]({get(r, 'URL')}))")
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {min(len(data), a.limit)} rows to {a.out}")


CONFIG = Path("job_search/config.json")
CONFIG_DEFAULTS = {"auto_save": None, "save_branch": None}


def _read_config() -> dict:
    cfg = dict(CONFIG_DEFAULTS)
    if CONFIG.exists():
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    return cfg


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def cmd_env(_a) -> None:
    import importlib.util
    import os

    cloud = os.environ.get("CLAUDE_CODE_REMOTE") == "true"
    default = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").removeprefix("origin/")
    if not default:  # fresh clones in cloud sessions often lack origin/HEAD; ask the remote
        m = re.search(r"ref: refs/heads/(\S+)\s+HEAD", _git("ls-remote", "--symref", "origin", "HEAD"))
        default = m.group(1) if m else ""
    deps = all(importlib.util.find_spec(m) for m in ("docx", "openpyxl"))
    cfg = _read_config()
    info = {
        "mode": "cloud (Claude app / web / mobile)" if cloud else "local",
        "browser_mode": "unavailable in cloud sessions" if cloud else "available only if started with `claude --chrome` (check for Chrome tools)",
        "current_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "default_branch": default,
        "save_branch": cfg["save_branch"] or default,
        "auto_save": cfg["auto_save"],
        "deps_installed": deps,
    }
    print(json.dumps(info, indent=2))
    if not deps:
        print("Install dependencies: python3 -m venv .venv && .venv/bin/python3 -m pip install -r requirements.txt")
    if cloud and cfg["auto_save"] is None:
        print("auto_save not set: ask the user once whether results should be committed and pushed automatically.")


def cmd_config(a) -> None:
    cfg = _read_config()
    if a.key is None:
        print(json.dumps(cfg, indent=2))
        return
    if a.key not in CONFIG_DEFAULTS:
        sys.exit(f"Unknown key {a.key}; valid: {', '.join(CONFIG_DEFAULTS)}")
    if a.value is None:
        print(json.dumps(cfg[a.key]))
        return
    val: object = {"true": True, "false": False, "null": None}.get(a.value.lower(), a.value)
    cfg[a.key] = val
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"{a.key} = {json.dumps(val)}")


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
    s = sub.add_parser("add-jobs"); s.add_argument("jobs", nargs="+"); s.add_argument("--tracker", required=True)
    s.add_argument("--found-for", required=True); s.add_argument("--resume"); s.set_defaults(f=cmd_add_jobs)
    s = sub.add_parser("detect-ats"); s.add_argument("urls", nargs="+"); s.set_defaults(f=cmd_detect_ats)
    s = sub.add_parser("watch"); s.add_argument("action", choices=["add", "list", "remove"]); s.add_argument("target", nargs="?")
    s.add_argument("--name"); s.add_argument("--watchlist", default=str(WATCHLIST)); s.set_defaults(f=cmd_watch)
    s = sub.add_parser("scan-boards"); s.add_argument("--keywords", default=""); s.add_argument("--exclude", default="")
    s.add_argument("--locations", default=""); s.add_argument("--type", choices=["any", "internship", "fulltime"], default="any")
    s.add_argument("--days", type=int); s.add_argument("--title-only", action="store_true")
    s.add_argument("--only", help="Comma-separated company names to scan"); s.add_argument("--no-description", action="store_true")
    s.add_argument("--watchlist", default=str(WATCHLIST)); s.add_argument("--out", required=True); s.set_defaults(f=cmd_scan_boards)
    s = sub.add_parser("search-urls"); s.add_argument("--keywords", required=True); s.add_argument("--location", default="")
    s.add_argument("--type", choices=["any", "internship", "fulltime"], default="any"); s.add_argument("--days", type=int, default=7)
    s.set_defaults(f=cmd_search_urls)
    s = sub.add_parser("merge-analyses"); s.add_argument("files", nargs="+"); s.add_argument("--title", required=True)
    s.add_argument("--out", required=True); s.set_defaults(f=cmd_merge_analyses)
    s = sub.add_parser("export-md"); s.add_argument("--tracker", default="applications/job_tracker.xlsx")
    s.add_argument("--out", default="applications/JOBS.md"); s.add_argument("--limit", type=int, default=100); s.set_defaults(f=cmd_export_md)
    sub.add_parser("env").set_defaults(f=cmd_env)
    s = sub.add_parser("config"); s.add_argument("key", nargs="?"); s.add_argument("value", nargs="?"); s.set_defaults(f=cmd_config)
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
