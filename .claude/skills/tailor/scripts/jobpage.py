"""Fallback job-page reader, for when WebFetch returns a summary that drops details.

Most job boards (Greenhouse, Lever, Workday, Ashby, LinkedIn public pages, Naukri, Indeed,
company career pages) embed a schema.org JobPosting JSON-LD block with the full description.
Uses only the standard library.
"""

from __future__ import annotations

import html as htmllib
import json
import re
import urllib.request
from html.parser import HTMLParser
from typing import Any

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


class _JsonLd(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[str] = []
        self._in = False
        self._buf: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json":
            self._in, self._buf = True, []
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "script" and self._in:
            self.blocks.append("".join(self._buf))
            self._in = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in:
            self._buf.append(data)
        elif self._in_title:
            self.title += data


def html_to_text(fragment: str) -> str:
    if "&lt;" in fragment:  # many boards HTML-escape the description inside JSON-LD
        fragment = htmllib.unescape(fragment)
    s = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    s = re.sub(r"(?i)<li[^>]*>", "\n- ", s)
    s = re.sub(r"(?i)</(p|div|h[1-6]|ul|ol|li|section)>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", "", s)
    s = htmllib.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()


def _walk(node: Any):
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, list):
            stack.extend(n)
        elif isinstance(n, dict):
            yield n
            if "@graph" in n:
                stack.append(n["@graph"])


def _location(n: dict) -> str:
    locs = n.get("jobLocation") or []
    locs = locs if isinstance(locs, list) else [locs]
    out = []
    for loc in locs:
        addr = loc.get("address", {}) if isinstance(loc, dict) else {}
        if isinstance(addr, str):
            out.append(addr)
            continue
        vals = [addr.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
        vals = [v if isinstance(v, str) else (v or {}).get("name", "") for v in vals]
        out.append(", ".join(v for v in vals if v))
    s = "; ".join(x for x in out if x)
    if n.get("jobLocationType") == "TELECOMMUTE":
        s = f"Remote ({s})" if s else "Remote"
    return s


def _salary(n: dict) -> str:
    sal = n.get("baseSalary")
    if not isinstance(sal, dict):
        return ""
    val = sal.get("value", {})
    cur = sal.get("currency", "")
    if isinstance(val, dict):
        lo, hi, unit = val.get("minValue"), val.get("maxValue"), val.get("unitText", "")
        amt = f"{lo}–{hi}" if lo and hi else str(val.get("value") or lo or hi or "")
        return " ".join(x for x in [cur, amt, f"/{unit.lower()}" if unit else ""] if x)
    return f"{cur} {val}".strip()


def parse_job_html(page: str, url: str = "") -> dict[str, str]:
    parser = _JsonLd()
    parser.feed(page)
    for raw in parser.blocks:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for n in _walk(data):
            t = n.get("@type")
            if "JobPosting" not in (t if isinstance(t, list) else [t]):
                continue
            org = n.get("hiringOrganization") or {}
            emp = n.get("employmentType", "")
            exp = n.get("experienceRequirements", "")
            if isinstance(exp, dict):
                months = exp.get("monthsOfExperience")
                exp = f"{int(months) // 12}+ years" if isinstance(months, (int, float)) else exp.get("description", "")
            return {
                "url": url,
                "title": str(n.get("title", "")).strip(),
                "company": (org.get("name", "") if isinstance(org, dict) else str(org)).strip(),
                "location": _location(n),
                "employment_type": ", ".join(emp) if isinstance(emp, list) else str(emp),
                "experience": str(exp),
                "salary": _salary(n),
                "date_posted": str(n.get("datePosted", "")),
                "valid_through": str(n.get("validThrough", "")),
                "description": html_to_text(str(n.get("description", ""))),
                "source": "json-ld",
            }
    body = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", "", page)
    return {
        "url": url,
        "title": parser.title.strip(),
        "company": "",
        "location": "",
        "employment_type": "",
        "experience": "",
        "salary": "",
        "date_posted": "",
        "valid_through": "",
        "description": html_to_text(body)[:30000],
        "source": "page-text",
    }


def fetch_job(url: str, timeout: float = 25.0) -> dict[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - user-supplied job URL
        charset = resp.headers.get_content_charset() or "utf-8"
        page = resp.read().decode(charset, errors="replace")
    return parse_job_html(page, url)
