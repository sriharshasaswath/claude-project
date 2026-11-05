"""Tests for the /tailor skill helper scripts. Run: python3 -m pytest -q"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / ".claude/skills/tailor/scripts"
BASE = ROOT / "resume/base_resume.json"
sys.path.insert(0, str(SCRIPTS))

import ats  # noqa: E402
from jobpage import parse_job_html  # noqa: E402
from resume_schema import load_resume  # noqa: E402
from tracker import append_jobs, canonical_url  # noqa: E402

JOB = {
    "title": "Supply Chain Analyst", "required_skills": ["SQL", "Power BI", "Inventory Management", "Tableau"],
    "preferred_skills": ["S&OP"], "keywords": ["KPI"],
}


def kit(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "resume_kit.py"), *map(str, args)],
                          capture_output=True, text=True, cwd=ROOT)


def test_base_resume_is_valid():
    assert kit("validate", BASE).returncode == 0


def test_keyword_matching():
    hit, miss = ats.keyword_coverage("Built k8s CI/CD; Power-BI dashboards; KPIs", ["Kubernetes", "CI/CD", "PowerBI", "KPI", "Go"])
    assert miss == ["Go"] and len(hit) == 4
    assert ats.keyword_coverage("Worked at Google", ["Go"])[0] == []


def test_score_and_missing():
    rep = ats.score_resume(load_resume(BASE), JOB)
    assert 0 <= rep["score"] <= 100
    assert rep["missing_required"] == ["Tableau"]


def test_audit_flags_invented_metric(tmp_path):
    r = json.loads(BASE.read_text())
    r["experience"][0]["bullets"][0] += ", cutting release time by 37%"
    new = tmp_path / "new.json"
    new.write_text(json.dumps(r))
    out = kit("audit", BASE, new).stdout
    assert "37%" in out
    assert "OK" in kit("audit", BASE, BASE).stdout


def test_render(tmp_path):
    res = kit("render", BASE, "--docx", tmp_path / "r.docx", "--md", tmp_path / "r.md")
    assert res.returncode == 0, res.stderr
    from docx import Document
    d = Document(str(tmp_path / "r.docx"))
    assert not d.tables
    assert "EXPERIENCE" in "\n".join(p.text for p in d.paragraphs)


def test_tracker_dedupes_across_runs(tmp_path):
    x = tmp_path / "t.xlsx"
    a = append_jobs(x, [{"title": "Analyst", "company": "A", "url": "https://www.a.com/j/1/?utm_source=x"}], "T1")
    b = append_jobs(x, [{"title": "Analyst", "company": "A", "url": "https://a.com/j/1"},
                        {"title": "Planner", "company": "B", "url": "https://b.com/2"}], "T2")
    assert (a["added"], b["added"], b["duplicates_skipped"], b["total_rows"]) == (1, 1, 1, 2)
    assert canonical_url("https://WWW.x.com/a/?utm_medium=y&id=3") == "https://x.com/a?id=3"


def test_jobpage_jsonld_escaped_description():
    page = ('<script type="application/ld+json">{"@type":"JobPosting","title":"Analyst",'
            '"hiringOrganization":{"name":"Acme"},"description":"&lt;p&gt;Need &lt;b&gt;SQL&lt;/b&gt;&lt;/p&gt;"}</script>')
    job = parse_job_html(page, "u")
    assert job["company"] == "Acme" and job["description"] == "Need SQL"


def test_slug():
    assert kit("slug", "Procter & Gamble", "Analyst (SCM)").stdout.strip() == "Procter-and-Gamble_Analyst-SCM"
