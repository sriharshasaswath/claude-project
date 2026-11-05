"""Tests for the /find-jobs helpers: portal parsers (with recorded API shapes), filters, watchlist, tracker."""

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "jobkit"))

import boards  # noqa: E402
from tracker import append_jobs, canonical_url  # noqa: E402

TODAY = dt.date.today()
RECENT = (TODAY - dt.timedelta(days=2)).isoformat()
OLD = (TODAY - dt.timedelta(days=90)).isoformat()

API = {
    "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true": {"jobs": [
        {"title": "Supply Chain Analyst Intern", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
         "location": {"name": "Bengaluru, India"}, "first_published": RECENT + "T10:00:00Z",
         "content": "&lt;p&gt;Use &lt;b&gt;SQL&lt;/b&gt; and Power BI&lt;/p&gt;"},
        {"title": "Senior Supply Chain Manager", "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
         "location": {"name": "Bengaluru"}, "first_published": RECENT, "content": "lead"},
        {"title": "Supply Chain Analyst", "absolute_url": "https://boards.greenhouse.io/acme/jobs/3",
         "location": {"name": "Pune"}, "first_published": OLD, "content": "old"},
    ]},
    "https://api.lever.co/v0/postings/zed?mode=json": [
        {"text": "Demand Planning Analyst", "hostedUrl": "https://jobs.lever.co/zed/abc", "applyUrl": "https://jobs.lever.co/zed/abc/apply",
         "categories": {"location": "Remote - India", "commitment": "Full-time"}, "workplaceType": "remote",
         "createdAt": int(dt.datetime.now().timestamp() * 1000), "descriptionPlain": "forecasting",
         "salaryRange": {"currency": "INR", "min": 800000, "max": 1200000, "interval": "per-year-salary"}},
    ],
    "https://api.ashbyhq.com/posting-api/job-board/ash?includeCompensation=true": {"jobs": [
        {"title": "Operations Intern", "location": "Bengaluru", "employmentType": "Intern", "publishedAt": RECENT,
         "jobUrl": "https://jobs.ashbyhq.com/ash/1", "isListed": True, "descriptionPlain": "supply chain ops",
         "compensation": {"compensationTierSummary": "₹40K/month"}},
        {"title": "Hidden", "isListed": False, "jobUrl": "https://jobs.ashbyhq.com/ash/2"},
    ]},
}
WORKDAY_PAGE = {"total": 1, "jobPostings": [
    {"title": "Supply Chain Analyst", "externalPath": "/job/Bangalore/Supply-Chain-Analyst_R1", "locationsText": "Bangalore", "postedOn": "Posted 3 Days Ago"},
]}


@pytest.fixture
def fake_api(monkeypatch):
    def fake(url, timeout=25.0, data=None):
        if "myworkdayjobs.com" in url:
            assert data["searchText"]
            return WORKDAY_PAGE
        if url not in API:
            raise OSError(f"HTTP 404 {url}")
        return API[url]
    monkeypatch.setattr(boards, "_get_json", fake)


WATCH = [
    {"name": "Acme", "ats": "greenhouse", "slug": "acme"},
    {"name": "Zed", "ats": "lever", "slug": "zed"},
    {"name": "Ash", "ats": "ashby", "slug": "ash"},
    {"name": "BigCo", "ats": "workday", "host": "bigco.wd5.myworkdayjobs.com", "tenant": "bigco", "site": "External"},
    {"name": "Broken", "ats": "greenhouse", "slug": "nope"},
]


def test_scan_filters_and_reports(fake_api):
    jobs, report = boards.scan(WATCH, keywords=["supply chain", "demand planning"], exclude=["senior"],
                               locations=["bengaluru", "bangalore", "remote"], days=30)
    titles = sorted(j["title"] for j in jobs)
    assert titles == ["Demand Planning Analyst", "Operations Intern", "Supply Chain Analyst", "Supply Chain Analyst Intern"]
    gh = next(j for j in jobs if j["company"] == "Acme")
    assert gh["type"] == "Internship" and gh["date_posted"] == RECENT and "SQL" in gh["description"]
    lever = next(j for j in jobs if j["company"] == "Zed")
    assert lever["work_mode"] == "Remote" and "800000" in lever["salary"]
    wd = next(j for j in jobs if j["company"] == "BigCo")
    assert wd["url"] == "https://bigco.wd5.myworkdayjobs.com/en-US/External/job/Bangalore/Supply-Chain-Analyst_R1"
    assert wd["date_posted"] == (TODAY - dt.timedelta(days=3)).isoformat()
    assert any("error" in r and r["company"] == "Broken" for r in report)


def test_scan_internship_only(fake_api):
    jobs, _ = boards.scan(WATCH[:3], keywords=["supply chain"], exclude=[], locations=[], job_type="internship")
    assert sorted(j["title"] for j in jobs) == ["Operations Intern", "Supply Chain Analyst Intern"]


def test_detect_ats():
    assert boards.detect_ats("https://job-boards.greenhouse.io/acme/jobs/9") == {"ats": "greenhouse", "slug": "acme"}
    assert boards.detect_ats("https://job-boards.eu.greenhouse.io/groww/jobs/1") == {"ats": "greenhouse", "slug": "groww", "region": "eu"}
    assert boards.detect_ats("jobs.eu.lever.co/zed/1") == {"ats": "lever", "slug": "zed", "region": "eu"}
    wd = boards.detect_ats("https://bigco.wd5.myworkdayjobs.com/en-US/External/job/X_R1")
    assert wd == {"ats": "workday", "host": "bigco.wd5.myworkdayjobs.com", "tenant": "bigco", "site": "External"}
    assert boards.detect_ats("https://www.naukri.com/job-listings-1") is None
    sr = boards.detect_ats("https://jobs.smartrecruiters.com/ni/DrReddysLaboratoriesLimited/ca1b-team-member")
    assert sr == {"ats": "smartrecruiters", "slug": "DrReddysLaboratoriesLimited"}


def test_watch_cli(tmp_path):
    wl = tmp_path / "w.json"
    run = lambda *a: subprocess.run([sys.executable, str(ROOT / "jobkit/kit.py"), *a], capture_output=True, text=True)  # noqa: E731
    assert "Watching Acme" in run("watch", "add", "https://boards.greenhouse.io/acme", "--name", "Acme", "--watchlist", str(wl)).stdout
    assert "Already watching" in run("watch", "add", "https://boards.greenhouse.io/acme/jobs/5", "--watchlist", str(wl)).stdout
    assert run("watch", "add", "https://naukri.com/x", "--watchlist", str(wl)).returncode != 0
    assert json.loads(wl.read_text()) == [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}]


def test_tracker_fields_types_and_linkedin_dedupe(tmp_path):
    x = tmp_path / "t.xlsx"
    res = append_jobs(x, [
        {"title": "SCM Intern", "company": "A", "url": "https://www.linkedin.com/jobs/view/scm-intern-at-a-4012345678/?trk=x",
         "source": "LinkedIn", "salary": "₹20k/month", "duration": "6 months"},
        {"title": "Hiring: supply chain analysts", "company": "B", "url": "https://www.linkedin.com/posts/jane_hiring-activity-1",
         "source": "LinkedIn post", "found_via": "Social post", "apply_via": "jobs@b.com", "contact": "Jane – https://linkedin.com/in/jane"},
    ], "find-jobs: scm")
    assert res["added"] == 2 and res["added_by_source"] == {"LinkedIn": 1, "LinkedIn post": 1}
    again = append_jobs(x, [{"title": "SCM Intern (dup)", "company": "Z", "url": "https://linkedin.com/jobs/view/4012345678"}], "x")
    assert again["duplicates_skipped"] == 1
    ws = load_workbook(x)["Jobs"]
    h = [c.value for c in ws[1]]
    row = {h[i]: c.value for i, c in enumerate(ws[2])}
    assert row["Type"] == "Internship" and row["Duration"] == "6 months" and row["Status"] == "Not applied"
    assert canonical_url("https://in.linkedin.com/jobs/view/abc-123/") == "https://in.linkedin.com/jobs/view/123"


def test_tracker_upgrades_old_layout(tmp_path):
    x = tmp_path / "old.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Similar Jobs"
    ws.append(["Job Title", "Company", "URL", "My Column"])
    ws.append(["Old job", "Q", "https://q.com/1", "keep me"])
    wb.save(x)
    append_jobs(x, [{"title": "New", "company": "R", "url": "https://r.com/2"}, {"title": "Old job", "company": "Q", "url": "https://q.com/1"}], "t")
    ws = load_workbook(x)["Jobs"]
    h = [c.value for c in ws[1]]
    assert h[:4] == ["Job Title", "Company", "URL", "My Column"] and "Type" in h
    assert ws.max_row == 3 and ws.cell(row=2, column=4).value == "keep me"


def test_search_urls():
    urls = boards.search_urls("supply chain", "Bengaluru", "internship", 7)
    assert "f_JT=I" in urls["LinkedIn Jobs"] and "past-week" in urls["LinkedIn Posts (hiring)"]
    assert urls["Internshala"].endswith("supply-chain-internship-in-bengaluru")


def kit(*args, cwd=ROOT):
    return subprocess.run([sys.executable, str(ROOT / "jobkit/kit.py"), *map(str, args)], capture_output=True, text=True, cwd=cwd)


def test_merge_analyses_role_profile(tmp_path):
    files = []
    for i, (req, pref) in enumerate([(["SQL", "Power BI", "Excel"], ["Python"]), (["sql", "Excel", "SAP"], ["Power BI"]),
                                     (["Excel", "Tableau"], ["SQL"])]):
        f = tmp_path / f"{i}.json"
        f.write_text(json.dumps({"title": "Supply Chain Analyst", "seniority": "Entry", "location": "Bengaluru",
                                 "required_skills": req, "preferred_skills": pref, "keywords": ["S&OP", "KPI"] if i else ["KPI"],
                                 "url": f"https://x.com/{i}"}))
        files.append(f)
    out = tmp_path / "role.json"
    res = kit("merge-analyses", *files, "--title", "Supply Chain Analyst", "--out", out)
    assert res.returncode == 0, res.stderr
    role = json.loads(out.read_text())
    assert role["required_skills"][:2] == ["Excel", "SQL"]  # recurring across postings; first spelling kept
    assert "SAP" in role["preferred_skills"] and "Tableau" in role["preferred_skills"]
    assert role["keywords"] == ["KPI", "S&OP"] and len(role["sources"]) == 3


def test_export_md(tmp_path):
    x = tmp_path / "t.xlsx"
    append_jobs(x, [{"title": "Analyst | Ops", "company": "A", "url": "https://a.com/1", "source": "Naukri"},
                    {"title": "Hiring post", "company": "B", "url": "https://linkedin.com/posts/1", "apply_via": "hr@b.com"}], "q")
    md = tmp_path / "JOBS.md"
    assert kit("export-md", "--tracker", x, "--out", md).returncode == 0
    text = md.read_text()
    assert "# Job tracker (2 jobs)" in text and "[Analyst / Ops](https://a.com/1)" in text
    assert "apply via hr@b.com" in text


def test_config_and_env(tmp_path):
    (tmp_path / "job_search").mkdir()
    assert kit("config", "auto_save", "true", cwd=tmp_path).stdout.strip() == "auto_save = true"
    assert json.loads((tmp_path / "job_search/config.json").read_text())["auto_save"] is True
    assert kit("config", "bogus", "1", cwd=tmp_path).returncode != 0
    env = json.loads(kit("env").stdout.split("\nInstall")[0].split("\nauto_save")[0])
    assert env["mode"] in {"local", "cloud (Claude app / web / mobile)"} and "deps_installed" in env
