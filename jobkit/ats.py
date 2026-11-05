"""Deterministic ATS-style scoring of a resume JSON against a job-analysis JSON.

Applicant tracking systems (Workday, Greenhouse, Lever, iCIMS, Taleo, SuccessFactors...)
parse the file into text, then recruiters filter and rank by keyword and title matches.
This approximates that so every draft gets a repeatable 0-100 number:

    Keyword match ........ 50  (required skills x2, preferred x1, other keywords x1)
    Title alignment ...... 10
    Section completeness . 10
    Bullet quality ....... 15  (numbers, action verbs, sensible length)
    Length ............... 5
    Parse safety ......... 10  (email, phone, dated roles, no emoji/icons)

It is a heuristic, not any vendor's real algorithm.
"""

from __future__ import annotations

import re
from typing import Any

from resume_schema import all_bullets, all_text

ACTION_VERBS = {
    "accelerated", "achieved", "added", "analysed", "analyzed", "architected", "assessed", "automated", "built",
    "championed", "collaborated", "conducted", "configured", "consolidated", "coordinated", "created", "cut",
    "debugged", "decreased", "defined", "delivered", "deployed", "designed", "developed", "devised", "directed",
    "drove", "enabled", "engineered", "established", "evaluated", "executed", "expanded", "facilitated",
    "forecasted", "generated", "grew", "guided", "handled", "identified", "implemented", "improved", "increased",
    "initiated", "integrated", "introduced", "launched", "led", "maintained", "managed", "mapped", "mentored",
    "migrated", "modelled", "modeled", "modernized", "monitored", "negotiated", "optimised", "optimized",
    "orchestrated", "organised", "organized", "oversaw", "owned", "partnered", "performed", "piloted", "planned",
    "presented", "prototyped", "published", "raised", "ran", "rebuilt", "redesigned", "reduced", "refactored",
    "resolved", "restructured", "revamped", "saved", "scaled", "secured", "served", "shipped", "simplified",
    "simulated", "spearheaded", "standardised", "standardized", "streamlined", "supported", "taught", "tested",
    "tracked", "trained", "transformed", "troubleshot", "upgraded", "validated", "won", "wrote", "co-authored",
}

# Spelling variants so "NodeJS" matches "Node.js", "k8s" matches "Kubernetes", etc.
ALIASES = {
    "nodejs": ["node js"], "node js": ["nodejs"],
    "javascript": ["js"], "kubernetes": ["k8s"],
    "postgresql": ["postgres"], "postgres": ["postgresql"],
    "amazon web services": ["aws"], "aws": ["amazon web services"],
    "google cloud platform": ["gcp", "google cloud"], "gcp": ["google cloud platform", "google cloud"],
    "microsoft azure": ["azure"],
    "machine learning": ["ml"], "artificial intelligence": ["ai"],
    "ci cd": ["cicd", "continuous integration"], "continuous integration": ["ci cd"],
    "react": ["reactjs", "react js"], "c#": ["c sharp"],
    "power bi": ["powerbi"], "powerbi": ["power bi"],
    "microsoft excel": ["excel"], "ms excel": ["excel"], "excel": ["ms excel", "microsoft excel"],
    "sap": ["sap erp"], "erp": ["sap erp"],
    "supply chain management": ["scm", "supply chain"], "scm": ["supply chain management", "supply chain"],
    "key performance indicators": ["kpis", "kpi"], "kpi": ["kpis"], "kpis": ["kpi"],
    "economic order quantity": ["eoq"], "eoq": ["economic order quantity"],
    "devops": ["dev ops"], "analytics": ["analytical", "analysis"],
}


def normalize(text: str) -> str:
    """Lowercase; keep + and # (C++, C#); turn other punctuation into spaces."""
    text = text.lower().replace("’", "'").replace("/", " ").replace(".", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9+# ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _plural_variants(term: str) -> set[str]:
    out = {term}
    if term.endswith("s") and len(term) > 4:
        out.add(term[:-1])
    else:
        out.add(term + "s")
    return out


def contains(haystack_norm: str, term: str) -> bool:
    base = normalize(term)
    candidates = set()
    for c in {base, *(normalize(a) for a in ALIASES.get(base, []))}:
        candidates |= _plural_variants(c)
    return any(
        cand and re.search(rf"(?<![a-z0-9+#]){re.escape(cand)}(?![a-z0-9+#])", haystack_norm)
        for cand in candidates
    )


def keyword_coverage(text: str, terms: list[str]) -> tuple[list[str], list[str]]:
    hay = normalize(text)
    hit, miss = [], []
    for t in dict.fromkeys(x.strip() for x in terms if x and x.strip()):
        (hit if contains(hay, t) else miss).append(t)
    return hit, miss


def score_resume(resume: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    text = all_text(resume)
    required = list(job.get("required_skills") or [])
    preferred = list(job.get("preferred_skills") or [])
    seen = {x.lower() for x in required + preferred}
    other = [k for k in (job.get("keywords") or []) if k.lower() not in seen]
    breakdown: dict[str, list[float]] = {}
    suggestions: list[str] = []

    # 1. Keywords (50)
    req_hit, req_miss = keyword_coverage(text, required)
    pref_hit, pref_miss = keyword_coverage(text, preferred)
    kw_hit, kw_miss = keyword_coverage(text, other)
    total_w = 2 * (len(req_hit) + len(req_miss)) + len(pref_hit) + len(pref_miss) + len(kw_hit) + len(kw_miss)
    got_w = 2 * len(req_hit) + len(pref_hit) + len(kw_hit)
    breakdown["Keyword match"] = [50 * got_w / total_w if total_w else 50.0, 50]
    if req_miss:
        suggestions.append("Required keywords not found: " + ", ".join(req_miss) + " (add only if truly applicable).")

    # 2. Title alignment (10)
    stop = {"and", "the", "for", "with", "of", "ii", "iii", "i"}
    title_words = {w for w in normalize(job.get("title", "")).split() if len(w) > 1 and w not in stop}
    cand = set(normalize(" ".join([resume["headline"]] + [e["title"] for e in resume["experience"][:2]])).split())
    title_pts = 10 * len(title_words & cand) / len(title_words) if title_words else 10.0
    breakdown["Title alignment"] = [title_pts, 10]
    if title_pts < 7 and job.get("title"):
        suggestions.append(f"Use a headline that mirrors the job title ('{job['title']}') where it is accurate.")

    # 3. Sections (10)
    present = {
        "headline": bool(resume["headline"].strip()),
        "summary": bool(resume["summary"].strip()),
        "skills": bool(resume["skills"]),
        "experience": bool(resume["experience"]),
        "education": bool(resume["education"]),
    }
    breakdown["Section completeness"] = [10 * sum(present.values()) / len(present), 10]
    suggestions += [f"Add a {k} section." for k, ok in present.items() if not ok]

    # 4. Bullet quality (15)
    bullets = all_bullets(resume)
    if bullets:
        metric = sum(1 for b in bullets if re.search(r"\d", b)) / len(bullets)
        verbs = sum(1 for b in bullets if (b.split() or [""])[0].lower().strip(",.;:") in ACTION_VERBS) / len(bullets)
        good_len = sum(1 for b in bullets if 8 <= len(b.split()) <= 35) / len(bullets)
        breakdown["Bullet quality"] = [6 * min(1.0, metric / 0.6) + 5 * verbs + 4 * good_len, 15]
        if metric < 0.5:
            suggestions.append(f"Only {metric:.0%} of bullets contain a number; quantify impact where you truly can.")
        if verbs < 0.8:
            suggestions.append("Start every bullet with a strong past-tense action verb (Built, Led, Reduced...).")
        if good_len < 0.8:
            suggestions.append("Keep bullets to 8-35 words (1-2 lines).")
    else:
        breakdown["Bullet quality"] = [0.0, 15]
        suggestions.append("Add bullet points describing your experience.")

    # 5. Length (5)
    words = len(text.split())
    if 350 <= words <= 850:
        length_pts = 5.0
    elif words < 350:
        length_pts = 5 * words / 350
        suggestions.append(f"Resume is short ({words} words).")
    else:
        length_pts = max(0.0, 5 - (words - 850) / 100)
        suggestions.append(f"Resume is long ({words} words); aim for one page (~450-750 words) unless senior.")
    breakdown["Length"] = [length_pts, 5]

    # 6. Parse safety (10)
    c = resume["contact"]
    parse = 0.0
    parse += 3 if re.search(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", c["email"].strip(), re.I) else 0
    parse += 2 if len(re.sub(r"\D", "", c["phone"])) >= 10 else 0
    roles = resume["experience"]
    parse += 3 * sum(1 for e in roles if e["start"] or e["end"]) / len(roles) if roles else 0
    odd = re.findall(r"[☀-➿■-◿\U0001F300-\U0001FAFF]", text)
    parse += 0 if odd else 2
    if not c["email"]:
        suggestions.append("Add an email address.")
    if not c["phone"]:
        suggestions.append("Add a phone number.")
    if odd:
        suggestions.append("Remove icon/emoji/box characters (e.g. ▪); many ATS parsers garble them.")
    breakdown["Parse safety"] = [parse, 10]

    score = round(sum(p for p, _ in breakdown.values()))
    return {
        "score": max(0, min(100, score)),
        "breakdown": {k: [round(p, 1), m] for k, (p, m) in breakdown.items()},
        "matched": req_hit + pref_hit + kw_hit,
        "missing_required": req_miss,
        "missing_preferred": pref_miss,
        "missing_keywords": kw_miss,
        "word_count": words,
        "suggestions": suggestions,
    }


def render_report(rep: dict[str, Any]) -> str:
    lines = [f"ATS score: {rep['score']}/100  ({rep['word_count']} words)"]
    for name, (pts, mx) in rep["breakdown"].items():
        lines.append(f"  {name:<22}{pts:5.1f} / {mx}")
    if rep["matched"]:
        lines.append(f"Matched ({len(rep['matched'])}): {', '.join(rep['matched'])}")
    if rep["missing_required"]:
        lines.append(f"Missing REQUIRED: {', '.join(rep['missing_required'])}")
    if rep["missing_preferred"]:
        lines.append(f"Missing preferred: {', '.join(rep['missing_preferred'])}")
    if rep["missing_keywords"]:
        lines.append(f"Missing other keywords: {', '.join(rep['missing_keywords'])}")
    if rep["suggestions"]:
        lines.append("Suggestions:")
        lines += [f"  - {s}" for s in rep["suggestions"]]
    return "\n".join(lines)


def match_percent(resume_text: str, skills: list[str]) -> int | None:
    """Share of a job's key skills found in the resume (ranks similar jobs)."""
    skills = [s for s in dict.fromkeys(x.strip() for x in skills) if s]
    if not skills:
        return None
    hit, _ = keyword_coverage(resume_text, skills)
    return round(100 * len(hit) / len(skills))
