"""Resume JSON shape: loading, light validation, and flattening to plain text.

Plain dicts on purpose, so the scripts only need python-docx and openpyxl.
See ../reference/schemas.md for the full shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LIST_SECTIONS = ["skills", "education", "experience", "projects", "certifications", "leadership", "additional"]
ENTRY_KEYS = {
    "skills": {"category": "", "skills": []},
    "education": {"degree": "", "school": "", "location": "", "start": "", "end": "", "score": "", "details": []},
    "experience": {"title": "", "company": "", "location": "", "start": "", "end": "", "bullets": []},
    "leadership": {"title": "", "company": "", "location": "", "start": "", "end": "", "bullets": []},
    "projects": {"name": "", "org": "", "dates": "", "link": "", "bullets": []},
    "certifications": {"name": "", "issuer": "", "date": "", "details": ""},
    "additional": {"label": "", "text": ""},
}


class ResumeError(ValueError):
    pass


def normalize_resume(data: dict[str, Any]) -> dict[str, Any]:
    """Fill missing optional keys with empty defaults and check basic types."""
    if not isinstance(data, dict):
        raise ResumeError("Resume JSON must be an object")
    contact = data.get("contact") or {}
    if not contact.get("name"):
        raise ResumeError("contact.name is required")
    out: dict[str, Any] = {
        "contact": {
            "name": contact.get("name", ""),
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
            "location": contact.get("location", ""),
            "links": list(contact.get("links") or []),
        },
        "headline": data.get("headline", "") or "",
        "summary": data.get("summary", "") or "",
    }
    for section in LIST_SECTIONS:
        items = data.get(section) or []
        if not isinstance(items, list):
            raise ResumeError(f"'{section}' must be a list")
        norm = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise ResumeError(f"{section}[{i}] must be an object")
            entry = {k: (list(v) if isinstance(v, list) else v) for k, v in ENTRY_KEYS[section].items()}
            entry.update({k: v for k, v in item.items() if k in entry and v is not None})
            for k, default in ENTRY_KEYS[section].items():
                if isinstance(default, list) and not isinstance(entry[k], list):
                    raise ResumeError(f"{section}[{i}].{k} must be a list")
            norm.append(entry)
        out[section] = norm
    unknown = set(data) - set(out)
    if unknown:
        raise ResumeError(f"Unknown top-level keys: {', '.join(sorted(unknown))}")
    return out


def load_resume(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ResumeError(f"{path} is not valid JSON: {e}") from e
    return normalize_resume(data)


def all_text(r: dict[str, Any]) -> str:
    """Flatten the resume into the plain text an ATS parser would extract."""
    parts: list[str] = [r["contact"]["name"], r["headline"], r["summary"]]
    for g in r["skills"]:
        parts.append(f"{g['category']}: {', '.join(g['skills'])}")
    for e in r["experience"] + r["leadership"]:
        parts.append(f"{e['title']} {e['company']} {e['location']}")
        parts.extend(e["bullets"])
    for p in r["projects"]:
        parts.append(f"{p['name']} {p['org']}")
        parts.extend(p["bullets"])
    for ed in r["education"]:
        parts.append(f"{ed['degree']} {ed['school']} {ed['score']}")
        parts.extend(ed["details"])
    for c in r["certifications"]:
        parts.append(f"{c['name']} {c['issuer']} {c['details']}")
    for a in r["additional"]:
        parts.append(f"{a['label']}: {a['text']}")
    return "\n".join(x.strip() for x in parts if x and x.strip())


def all_bullets(r: dict[str, Any]) -> list[str]:
    return [b for e in r["experience"] + r["leadership"] for b in e["bullets"]] + [
        b for p in r["projects"] for b in p["bullets"]
    ]
