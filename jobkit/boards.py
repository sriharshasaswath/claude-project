"""Company career portals, read through the public job-board APIs their ATS vendors publish.

Supported: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Workday.
These endpoints exist so job boards can list a company's openings. They return clean JSON,
so they are far more reliable than scraping HTML. Standard library only.

The watchlist (job_search/watchlist.json) is a list of companies:
    {"name": "Acme", "ats": "greenhouse", "slug": "acme"}
    {"name": "Big Co", "ats": "workday", "host": "bigco.wd5.myworkdayjobs.com", "tenant": "bigco", "site": "External"}
`detect_ats(url)` turns any careers/job URL on these platforms into such an entry.
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import quote, quote_plus, urlsplit

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
INTERN_RE = re.compile(r"\b(intern|internship|interns|trainee|apprentice(ship)?|summer (analyst|associate|intern)|co-?op|fellowship)\b", re.I)


# ------------------------------------------------------------------ HTTP

def _get_json(url: str, timeout: float = 25.0, data: dict | None = None) -> Any:
    body = json.dumps(data).encode() if data is not None else None
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed vendor API hosts
        return json.loads(resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace"))


def _strip_html(s: str) -> str:
    s = htmllib.unescape(s or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


def _iso(value: Any) -> str:
    """Epoch ms/s or ISO-ish string -> YYYY-MM-DD ('' if unknown)."""
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        secs = value / 1000 if value > 1e11 else value
        return dt.datetime.fromtimestamp(secs, dt.timezone.utc).date().isoformat()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(value))
    return m.group(1) if m else ""


def _workday_posted(text: str) -> str:
    """'Posted Today' / 'Posted Yesterday' / 'Posted 3 Days Ago' / 'Posted 30+ Days Ago' -> date."""
    t = (text or "").lower()
    today = dt.date.today()
    if "today" in t:
        return today.isoformat()
    if "yesterday" in t:
        return (today - dt.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*days?", t)
    return (today - dt.timedelta(days=int(m.group(1)))).isoformat() if m else ""


def _job(company: str, ats: str, **kw: Any) -> dict[str, Any]:
    job = {
        "title": "", "company": company, "location": "", "work_mode": "", "type": "", "experience": "",
        "salary": "", "duration": "", "date_posted": "", "deadline": "", "source": f"{company} careers ({ats})",
        "found_via": "Career portal API", "apply_via": "", "contact": "", "key_skills": [], "why_relevant": "",
        "url": "", "description": "",
    }
    job.update({k: v for k, v in kw.items() if v is not None})
    job["description"] = (job["description"] or "")[:6000]
    if not job["type"]:
        job["type"] = "Internship" if INTERN_RE.search(job["title"]) else ""
    return job


# ------------------------------------------------------------------ fetchers

def fetch_greenhouse(e: dict) -> list[dict]:
    data = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{e['slug']}/jobs?content=true")
    out = []
    for j in data.get("jobs", []):
        out.append(_job(
            e["name"], "Greenhouse", title=j.get("title", ""), location=(j.get("location") or {}).get("name", ""),
            date_posted=_iso(j.get("first_published") or j.get("updated_at")), url=j.get("absolute_url", ""),
            description=_strip_html(j.get("content", "")),
        ))
    return out


def fetch_lever(e: dict) -> list[dict]:
    host = "api.eu.lever.co" if e.get("region") == "eu" else "api.lever.co"
    data = _get_json(f"https://{host}/v0/postings/{e['slug']}?mode=json")
    out = []
    for j in data if isinstance(data, list) else []:
        cat = j.get("categories") or {}
        sal = j.get("salaryRange") or {}
        salary = ""
        if sal.get("min") or sal.get("max"):
            salary = f"{sal.get('currency', '')} {sal.get('min', '')}–{sal.get('max', '')} {sal.get('interval', '')}".strip()
        commitment = cat.get("commitment", "")
        out.append(_job(
            e["name"], "Lever", title=j.get("text", ""), location=cat.get("location", ""),
            work_mode=(j.get("workplaceType") or "").replace("unspecified", "").title(),
            type="Internship" if INTERN_RE.search(f"{j.get('text', '')} {commitment}") else commitment,
            salary=salary, date_posted=_iso(j.get("createdAt")), url=j.get("hostedUrl", ""),
            apply_via=j.get("applyUrl", ""), description=j.get("descriptionPlain", ""),
        ))
    return out


def fetch_ashby(e: dict) -> list[dict]:
    data = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{e['slug']}?includeCompensation=true")
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        comp = j.get("compensation") or {}
        out.append(_job(
            e["name"], "Ashby", title=j.get("title", ""), location=j.get("location", ""),
            work_mode=j.get("workplaceType") or ("Remote" if j.get("isRemote") else ""),
            type="Internship" if INTERN_RE.search(f"{j.get('title', '')} {j.get('employmentType', '')}") else j.get("employmentType", ""),
            salary=comp.get("compensationTierSummary", "") or comp.get("scrapeableCompensationSalarySummary", ""),
            date_posted=_iso(j.get("publishedAt")), url=j.get("jobUrl", ""), apply_via=j.get("applyUrl", ""),
            description=j.get("descriptionPlain", ""),
        ))
    return out


def fetch_smartrecruiters(e: dict) -> list[dict]:
    out, offset = [], 0
    while offset < 1000:
        data = _get_json(f"https://api.smartrecruiters.com/v1/companies/{e['slug']}/postings?limit=100&offset={offset}")
        content = data.get("content", [])
        for j in content:
            loc = j.get("location") or {}
            emp = (j.get("typeOfEmployment") or {}).get("label", "")
            out.append(_job(
                e["name"], "SmartRecruiters", title=j.get("name", ""),
                location=", ".join(x for x in [loc.get("city"), loc.get("region"), loc.get("country", "").upper()] if x),
                work_mode="Remote" if loc.get("remote") else "",
                type="Internship" if INTERN_RE.search(f"{j.get('name', '')} {emp}") else emp,
                experience=(j.get("experienceLevel") or {}).get("label", ""),
                date_posted=_iso(j.get("releasedDate")),
                url=f"https://jobs.smartrecruiters.com/{e['slug']}/{j.get('id', '')}",
            ))
        offset += 100
        if len(content) < 100 or offset >= data.get("totalFound", 0):
            break
    return out


def fetch_workable(e: dict) -> list[dict]:
    data = _get_json(f"https://apply.workable.com/api/v1/widget/accounts/{e['slug']}?details=true")
    out = []
    for j in data.get("jobs", []):
        emp = j.get("employment_type", "")
        out.append(_job(
            e["name"], "Workable", title=j.get("title", ""),
            location=", ".join(x for x in [j.get("city"), j.get("state"), j.get("country")] if x),
            work_mode="Remote" if j.get("telecommuting") else "",
            type="Internship" if INTERN_RE.search(f"{j.get('title', '')} {emp}") else emp,
            experience=j.get("experience", ""), date_posted=_iso(j.get("published_on") or j.get("created_at")),
            url=j.get("url") or j.get("shortlink", ""), apply_via=j.get("application_url", ""),
            description=_strip_html(j.get("description", "")),
        ))
    return out


def fetch_recruitee(e: dict) -> list[dict]:
    data = _get_json(f"https://{e['slug']}.recruitee.com/api/offers/")
    out = []
    for j in data.get("offers", []):
        emp = j.get("employment_type_code", "")
        out.append(_job(
            e["name"], "Recruitee", title=j.get("title", ""),
            location=j.get("location") or ", ".join(x for x in [j.get("city"), j.get("country")] if x),
            work_mode="Remote" if j.get("remote") else "",
            type="Internship" if INTERN_RE.search(f"{j.get('title', '')} {emp}") else emp.replace("_", " ").title(),
            date_posted=_iso(j.get("published_at") or j.get("created_at")), url=j.get("careers_url", ""),
            description=_strip_html(j.get("description", "")),
        ))
    return out


def fetch_workday(e: dict, search_text: str = "", max_jobs: int = 400) -> list[dict]:
    host, tenant, site = e["host"], e["tenant"], e["site"]
    api = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    out, offset = [], 0
    while offset < max_jobs:
        data = _get_json(api, data={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": search_text})
        postings = data.get("jobPostings", [])
        for j in postings:
            path = j.get("externalPath", "")
            out.append(_job(
                e["name"], "Workday", title=j.get("title", ""), location=j.get("locationsText", ""),
                date_posted=_workday_posted(j.get("postedOn", "")), url=f"https://{host}/en-US/{site}{path}" if path else "",
            ))
        offset += 20
        if len(postings) < 20 or offset >= data.get("total", 0):
            break
    return out


FETCHERS = {
    "greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters, "workable": fetch_workable, "recruitee": fetch_recruitee,
    "workday": fetch_workday,
}


# ------------------------------------------------------------------ detection

def detect_ats(url: str) -> dict[str, str] | None:
    """Recognise a careers/job URL on a supported ATS and return a watchlist entry (without 'name')."""
    p = urlsplit(url.strip() if "://" in url else "https://" + url.strip())
    host = p.netloc.lower().removeprefix("www.")
    parts = [x for x in p.path.split("/") if x]
    first = parts[0] if parts else ""
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"} and first and first != "embed":
        return {"ats": "greenhouse", "slug": first}
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and first == "embed":
        m = re.search(r"for=([\w-]+)", p.query)
        return {"ats": "greenhouse", "slug": m.group(1)} if m else None
    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and first:
        return {"ats": "lever", "slug": first, **({"region": "eu"} if ".eu." in host else {})}
    if host == "jobs.ashbyhq.com" and first:
        return {"ats": "ashby", "slug": first}
    if host in {"jobs.smartrecruiters.com", "careers.smartrecruiters.com"} and first:
        # some links carry a short prefix segment, e.g. /ni/<CompanyId>/<job-id>
        slug = parts[1] if len(first) <= 3 and len(parts) > 1 and first.islower() else first
        return {"ats": "smartrecruiters", "slug": slug}
    if host == "apply.workable.com" and first and first not in {"api", "j"}:
        return {"ats": "workable", "slug": first}
    if host.endswith(".recruitee.com") and host.count(".") == 2:
        return {"ats": "recruitee", "slug": host.split(".")[0]}
    m = re.match(r"^([\w-]+)\.(wd\d+)\.myworkdayjobs\.com$", host)
    if m:
        segs = [s for s in parts if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", s)]
        if segs and segs[0] not in {"wday", "job"}:
            return {"ats": "workday", "host": host, "tenant": m.group(1), "site": segs[0]}
    return None


def entry_key(e: dict) -> str:
    return f"{e['ats']}:{e.get('host', '')}:{e.get('slug') or e.get('site', '')}".lower()


# ------------------------------------------------------------------ filtering

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#&/ ]+", " ", (s or "").lower())).strip()


def matches(job: dict, *, keywords: list[str], exclude: list[str], locations: list[str], job_type: str,
            days: int | None, title_only: bool = False) -> bool:
    title = _norm(job.get("title", ""))
    hay = title if title_only else f"{title} {_norm(job.get('description', ''))[:3000]}"
    if keywords and not any(re.search(rf"(?<![a-z0-9]){re.escape(_norm(k))}(?![a-z0-9])", hay) for k in keywords):
        return False
    if any(re.search(rf"(?<![a-z0-9]){re.escape(_norm(x))}(?![a-z0-9])", title) for x in exclude):
        return False
    if locations:
        loc = _norm(f"{job.get('location', '')} {job.get('work_mode', '')}")
        if not any(_norm(l) in loc for l in locations):
            return False
    is_intern = "intern" in (job.get("type") or "").lower() or bool(INTERN_RE.search(job.get("title", "")))
    if job_type == "internship" and not is_intern:
        return False
    if job_type == "fulltime" and is_intern:
        return False
    if days and job.get("date_posted"):
        try:
            if (dt.date.today() - dt.date.fromisoformat(job["date_posted"])).days > days:
                return False
        except ValueError:
            pass
    return True


def scan(watchlist: list[dict], *, keywords: list[str], exclude: list[str], locations: list[str],
         job_type: str = "any", days: int | None = None, title_only: bool = False, workers: int = 8):
    """Fetch every watchlist board concurrently and filter. Returns (jobs, per-company report)."""
    def run(e: dict) -> list[dict]:
        fn = FETCHERS[e["ats"]]
        if e["ats"] == "workday" and keywords:  # Workday supports server-side search; one call per keyword
            seen, res = set(), []
            for k in keywords:
                for j in fn(e, search_text=k):
                    if j["url"] not in seen:
                        seen.add(j["url"])
                        res.append(j)
            return res
        return fn(e)

    jobs, report = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run, e): e for e in watchlist if e.get("ats") in FETCHERS}
        for fut in as_completed(futures):
            e = futures[fut]
            try:
                found = fut.result()
                kept = [j for j in found if matches(j, keywords=keywords, exclude=exclude, locations=locations,
                                                     job_type=job_type, days=days, title_only=title_only)]
                jobs.extend(kept)
                report.append({"company": e["name"], "ats": e["ats"], "postings": len(found), "matched": len(kept)})
            except Exception as ex:  # noqa: BLE001 - one broken board must not stop the scan
                report.append({"company": e["name"], "ats": e["ats"], "error": f"{type(ex).__name__}: {ex}"[:200]})
    return jobs, sorted(report, key=lambda r: r["company"].lower())


# ------------------------------------------------------------------ search URLs for browser mode

def search_urls(keywords: str, location: str = "", job_type: str = "any", days: int = 7) -> dict[str, str]:
    """Pre-filled search pages for the big boards (for use in a logged-in browser)."""
    q, loc = quote_plus(keywords), quote_plus(location)
    slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")  # noqa: E731
    secs = max(1, days) * 86400
    li_type = "&f_JT=I" if job_type == "internship" else ("&f_JT=F" if job_type == "fulltime" else "")
    li_date = "past-24h" if days <= 1 else ("past-week" if days <= 7 else "past-month")
    intern = job_type == "internship"
    urls = {
        "LinkedIn Jobs": f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}&f_TPR=r{secs}{li_type}&sortBy=DD",
        "LinkedIn Posts (hiring)": "https://www.linkedin.com/search/results/content/?keywords="
        + quote(f'hiring {keywords}' + (" intern" if intern and "intern" not in keywords.lower() else ""))
        + f"&datePosted=%22{li_date}%22&sortBy=%22date_posted%22",
        "Indeed": f"https://in.indeed.com/jobs?q={q}&l={loc}&fromage={min(days, 14)}&sort=date" + ("&jt=internship" if intern else ""),
        "Naukri": f"https://www.naukri.com/{slug(keywords)}-jobs" + (f"-in-{slug(location)}" if location else "") + f"?jobAge={min(days, 30)}",
        "Glassdoor": f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={q}&locKeyword={loc}&fromAge={min(days, 30)}",
        "Google Jobs": f"https://www.google.com/search?q={quote_plus(keywords + ' jobs ' + location)}&ibp=htl;jobs",
        "Wellfound": f"https://wellfound.com/jobs?keywords={q}",
        "hiring.cafe": "https://hiring.cafe/  (type the search into the box, then set date and location filters)",
        "iimjobs": f"https://www.iimjobs.com/search/{slug(keywords)}-jobs",
        "foundit": f"https://www.foundit.in/srp/results?query={q}&locations={loc}",
        "Instahyre": f"https://www.instahyre.com/search-jobs/?q={q}",
        "Cutshort": f"https://cutshort.io/jobs?q={q}",
    }
    if intern or job_type == "any":
        urls["Internshala"] = f"https://internshala.com/internships/{slug(keywords)}-internship" + (f"-in-{slug(location)}" if location else "")
        urls["Unstop"] = f"https://unstop.com/internships?searchTerm={q}"
    return urls
