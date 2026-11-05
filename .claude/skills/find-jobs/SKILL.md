---
name: find-jobs
description: Deep job and internship search by role, keywords, and location across company career portals (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, Recruitee), job boards (LinkedIn, Indeed, Naukri, Internshala, Unstop, hiring.cafe, iimjobs, Glassdoor, Wellfound and more), and LinkedIn hiring posts, then appends verified, de-duplicated results to the running Excel tracker ranked by resume match. Works locally and in cloud sessions, including the Claude mobile app. Use when the user runs /find-jobs or asks to find, scrape, or search for jobs or internships.
argument-hint: <what to look for, e.g. "supply chain internship, Bengaluru or remote, last 14 days">
allowed-tools: WebSearch, WebFetch, Read, Write, Edit, Glob, Grep, Agent, Bash(python3 jobkit/kit.py *), Bash(python3 -m venv .venv), Bash(.venv/bin/python3 -m pip install -r requirements.txt), Bash(mkdir -p job_search/*), Bash(git add *), Bash(git status*), Bash(git fetch origin *), Bash(git merge --no-edit origin/*)
---

# /find-jobs: search every corner for matching jobs and internships

Search request: **$ARGUMENTS**

Run commands from the repository root. `kit` means `python3 jobkit/kit.py`.
**First, follow "Start of run" in `jobkit/sessions.md`.** It checks dependencies, detects whether this is a cloud
or phone session, and pulls the latest tracker and watchlist. Follow its phone-friendly rules for the rest of the run.
Results go to `applications/job_tracker.xlsx`, sheet **Jobs**. This is the same tracker `/tailor` uses.
The resume used for match % is `resume/base_resume.json`.

**Ground rules**
- Never invent a job, URL, company, salary, stipend, date, or contact. Every row must come from a page or API
  response you actually saw. Leave a field empty if it is unknown.
- Only include postings that are open. Drop anything marked closed or expired, or whose deadline has passed.
- Search engines and job boards are read-only sources. Never apply, message, connect, like, or comment unless
  the user explicitly asks.

## 1. Pin down the search

From `$ARGUMENTS` (or by asking one short question if it's too vague), decide on:
- **Roles and keywords**: the main titles plus synonyms. For example, for "supply chain": supply chain analyst,
  SCM, demand planning, inventory analyst, procurement, logistics, S&OP, operations analyst.
- **Type**: internship, full-time, or any.
- **Locations and work mode**: cities, "remote", "hybrid".
- **Freshness**: posted within N days. Default to 14, or 30 for internships.
- **Level**: fresher, 0-2 years, MBA, and so on. Also note anything to **exclude** (for example "senior", "director", "sales").

Name the run `<YYYY-MM-DD>_<short-slug>`, run `mkdir -p job_search/runs/<run>`, and save the plan to
`job_search/runs/<run>/criteria.json`. Tell the user the plan in 3 to 4 lines, then start searching.
Don't wait for approval unless something is genuinely unclear.

## 2. Sweep every source

Each source group below writes its own `job_search/runs/<run>/<group>.json` file (the job record shape is
in `.claude/skills/tailor/reference/schemas.md`). Set `found_via` on every record.

**Go deep.** Run many varied queries per group, use synonyms, open the result pages, and follow "similar jobs"
links. If the Agent tool is available, run groups B to E as **parallel subagents**, one per group. Give each one
the criteria, its group's instructions from this file, the ground rules, and the exact output path, and have it
return only a one-line summary. This keeps the search results out of the main conversation. Otherwise, run the
groups yourself one after another.

### A. Company career portals (API scan, fast and reliable)
1. `kit watch list` shows which companies are on the watchlist (`job_search/watchlist.json`).
2. Grow it. Use WebSearch to find companies hiring for these roles on supported ATS platforms, for example:
   `site:boards.greenhouse.io "<keyword>"`, `site:job-boards.greenhouse.io`, `site:jobs.lever.co`,
   `site:jobs.ashbyhq.com`, `site:myworkdayjobs.com "<keyword>" <city>`, `site:jobs.smartrecruiters.com`,
   `site:apply.workable.com`, `site:recruitee.com`. Also find the careers pages of the top companies in the
   user's field and location (for example FMCG, e-commerce, 3PL, consulting, and manufacturing for supply chain)
   and check whether they run on a supported ATS. For every match, run `kit watch add <careers-or-job-url> --name "<Company>"`.
3. `kit scan-boards --keywords "<k1,k2,...>" --exclude "<x1,...>" --locations "<city1,city2,remote,india>" --type <internship|fulltime|any> --days <N> --out job_search/runs/<run>/portals.json`
   This calls every portal's public job API in parallel. If almost nothing matches, re-run with broader keywords
   or without `--locations`, then filter by reading the results. Report any portals that fail. If a slug is
   wrong, fix or remove that watchlist entry.

### B. Job boards (web search)
Run site-scoped searches with the keywords, location, and type across LinkedIn Jobs (`site:linkedin.com/jobs/view`),
Indeed, Naukri, Glassdoor, foundit, Internshala, Unstop, iimjobs, Instahyre, Wellfound, Cutshort, hiring.cafe,
and Google Jobs. Get more from each: open listing pages with WebFetch and collect every relevant posting on them,
not just the first one. Prefer the employer's own posting URL over an aggregator's when both exist.

### C. LinkedIn and social hiring posts (jobs that are never formally posted)
Recruiters and hiring managers often post "We're hiring… DM me / send your CV to …" without a job listing. Search for them:
- `site:linkedin.com/posts ("hiring" OR "we are hiring" OR "looking for" OR "openings") "<role keyword>" <location>`
- `site:linkedin.com/posts ("internship" OR "interns") "<keyword>"`, `site:linkedin.com/feed/update "<keyword>" hiring`
- the same with "#hiring", "#internship", "immediate joiners", "freshers", "MBA" and the city name
- `site:x.com hiring "<keyword>"` and relevant subreddits, where appropriate

For each post you can verify, record: the role, company, location, the **post URL** as `url`, the poster's name
and profile URL as `contact`, how to apply (email address, form link, or "DM") as `apply_via`, and the post date.
Set `source` to "LinkedIn post" and `found_via` to "Social post". Skip posts older than the freshness window and
posts with no real opening, such as "open to work" posts or tips.

### D. Company career pages that aren't on a supported ATS
For important target companies whose careers site isn't API-readable (for example SAP SuccessFactors, Oracle
Taleo/iCIMS, or a custom site), WebSearch `"<Company>" careers <keyword> <city>` and WebFetch the listings.

### E. Logged-in browser (only if Claude in Chrome tools are available, meaning Claude Code was started with `claude --chrome`)
In cloud or phone sessions, skip this group. Instead, make group C deeper, as described in `jobkit/sessions.md`, and
list the sites a local browser run would add in the final report.
This reaches content that blocks bots or needs a login. It is the best way to find LinkedIn posts.
1. `kit search-urls --keywords "<main keywords>" --location "<city>" --type <type> --days <N>` gives pre-filled search links.
2. Open **LinkedIn Posts (hiring)** first and read the results sorted by latest. Then do the same on
   **LinkedIn Jobs**, **hiring.cafe** (enter the query and filters), **Indeed**, **Naukri**, and (for internships)
   **Internshala** and **Unstop**. Try two or three keyword variants per site.
3. Browse at a human pace. Scroll a few pages per query and read only what is shown. Don't use bulk-scraping
   tricks, and don't open hundreds of profiles. If a site shows a CAPTCHA, a login prompt, or an unusual-activity
   warning, stop on that site and tell the user. Heavy automated use can get a LinkedIn account restricted.
4. Write what you collect to `job_search/runs/<run>/browser.json`. Use the same fields as groups B and C.

## 3. Verify and enrich

For every candidate that didn't come from the portal API (group A), WebFetch the posting, or use `kit fetch-job <url>`
if WebFetch fails:
- Confirm it's still open, and fill in location, work mode, experience, salary or stipend, duration (for internships),
  date posted, and deadline.
- Add 5 to 10 `key_skills` taken from the posting, plus a one-line `why_relevant` that ties it to the user's search
  and background.
- Remove postings you couldn't verify, but keep LinkedIn posts if the post itself loaded.
For group A results, skim the descriptions in the JSON, fill in `key_skills` and `why_relevant` for the strong
matches, and remove clear mismatches (wrong level or function).

## 4. Merge into the tracker

`kit add-jobs job_search/runs/<run>/*.json --tracker applications/job_tracker.xlsx --found-for "find-jobs: <short query>" --resume resume/base_resume.json`

The tracker drops duplicates across sources and across earlier runs (it normalizes URLs and matches on
title + company), adds a match % against the resume, and sorts the new rows by match.

## 5. Report

Run `kit export-md` first to refresh `applications/JOBS.md`, the phone-friendly view. In cloud mode, send the
tracker and `JOBS.md` if you have a tool for sending files.


Tell the user:
- How many jobs were added, broken down by source, and how many were skipped as already tracked.
- The **top 10** by fit, as a table: role, company, location, type, posted date, stipend or salary, and link.
- LinkedIn posts with a direct contact (email or DM), listed separately, since the user can act on these quickly.
- Which sources were blocked or thin, and whether browser mode (`claude --chrome`) would reach more.
- Offer: "Run `/tailor <link>` on any of these" and "Save this as a saved search" (append the criteria to
  `job_search/saved_searches.json` so the user can later say "run my saved searches").

Then follow "End of run: save" in `jobkit/sessions.md`, with a commit message like `find-jobs: <query> (<N> new)`.

## Saved searches

If the user says "run my saved searches", go through `job_search/saved_searches.json` (a list of criteria objects
with a `name`). For each one, use its `last_run` date to set the freshness window, so you only fetch what's new
since then. Afterwards, update `last_run`.
