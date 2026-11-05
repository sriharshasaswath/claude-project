---
name: tailor
description: Tailor the user's base resume to a job posting link, or to a role name (find open postings and pick one, or build a general resume for that role), for a strong ATS score. Iterate with the user in chat until they approve, save the result as a new DOCX named after the company and role, and append similar open jobs to the running Excel tracker. Works locally and in cloud sessions, including the Claude mobile app. Use when the user runs /tailor <job-url or role> or asks to tailor their resume.
argument-hint: <job-posting-url | role, e.g. "Supply Chain Analyst, Bengaluru">
allowed-tools: WebFetch, WebSearch, Agent, Read, Write, Edit, Glob, Grep, Bash(python3 jobkit/kit.py *), Bash(python3 -m venv .venv), Bash(.venv/bin/python3 -m pip install -r requirements.txt), Bash(mkdir -p applications/*), Bash(git add *), Bash(git status*), Bash(git fetch origin *), Bash(git merge --no-edit origin/*)
---

# /tailor — tailor the resume to a job, review until approved, track similar jobs

Request: **$ARGUMENTS**

Run every command from the repository root. The helper is `python3 jobkit/kit.py <subcommand>` (called `kit` below).
No API key is used. You do the fetching, research, and writing with your own WebFetch and WebSearch tools.

**First, follow "Start of run" in `jobkit/sessions.md`.** It checks dependencies, detects whether this is a cloud
or phone session, and pulls the latest tracker. Follow its phone-friendly rules for the rest of the run.

## Files

| Path | What it is |
|---|---|
| `resume/base_resume.json` | **Source of truth** for the candidate's facts. Never edit it during a tailoring run. |
| `resume/base_resume.docx` | The original resume file, kept for reference. |
| `applications/<Slug>/` | One folder per job. `<Slug>` comes from `kit slug "<Company>" "<Role>"`. |
| `applications/<Slug>/<Slug>_Resume.docx` | The approved tailored resume, plus `.md` and `.json` copies alongside it. |
| `applications/job_tracker.xlsx` | The single running Excel tracker. Sheet `Jobs` gets new rows appended (shared with `/find-jobs`), de-duplicated across runs. Sheet `Tailored Resumes` gets one row per approved resume. |

Read `reference/schemas.md` for the JSON shapes and `reference/ats-rules.md` for the writing rules before drafting.

## Step 1: Get the job posting

Decide which mode the request is:
- **Link mode**: `$ARGUMENTS` contains a URL. Continue with "1A".
- **Role mode**: `$ARGUMENTS` is a role or title, optionally with a location, type, or company (for example
  "Supply Chain Analyst, Bengaluru", "operations internship remote", "business analyst at Deloitte"). Continue with "1B".
- If it's empty, ask: *"Send me a job link, or a role (plus location) to search for."* Then stop and wait.

### 1A. From a link
1. WebFetch the URL. Ask for the **complete** posting: title, company, location, work mode, experience needed,
   salary, date posted, full responsibilities, and full required and preferred qualifications.
2. If WebFetch fails or returns too little (login wall, JavaScript-only page, summary missing the requirements),
   run `kit fetch-job "<url>"`. It reads the page's schema.org JSON-LD. If that also fails, WebSearch the title
   and company to find the same posting on another board. As a last resort, ask the user to paste the job text.
3. If the page shows the posting as closed or expired, tell the user and ask whether to continue.
4. Run `kit slug "<Company>" "<Role>"`, then `mkdir -p applications/<Slug>/drafts`. If the folder already exists,
   tell the user this job was tailored before and ask whether to redo it or stop.
5. Write `applications/<Slug>/job_posting.md`: the URL, the fetch date, the metadata, and the full description text.

### 1B. From a role
1. Run a **quick search** for currently open postings that match the role. Use the `/find-jobs` method
   (`.claude/skills/find-jobs/SKILL.md`, groups A to C) but keep it light: about 6 to 10 searches plus a
   `kit scan-boards` with the role keywords. Aim for 8 to 12 verified, open postings that fit the user's
   background. Default the location to India unless the user gave one. Save them to
   `job_search/runs/<date>_<role-slug>/quick.json` and add them to the tracker with
   `kit add-jobs ... --found-for "tailor: <role>"`.
2. Show a short numbered list (role, company, location, posted date, link, and one line on fit), then ask:
   *"Reply with a number to tailor for that posting, several numbers (one at a time), or **general** for one
   resume aimed at this role in general."* End your turn and wait.
3. **A number** means: continue with 1A using that posting's link. After it's approved, offer the next number if
   they picked several.
4. **general** means:
   - Pick 5 to 8 of the best-matching postings and WebFetch each one. For each, write a short analysis file
     `applications/General_<RoleSlug>/postings/<n>.json` (same shape as `job_analysis.json`).
   - Run `kit merge-analyses applications/General_<RoleSlug>/postings/*.json --title "<Role>" --out applications/General_<RoleSlug>/job_analysis.json`.
     Skills that recur across postings become required, and the rest become preferred.
   - Use `<Slug>` = `General_<RoleSlug>` (from `kit slug "General" "<Role>"`) and list the postings you used in
     `applications/General_<RoleSlug>/job_posting.md`. Skip Step 2 and go straight to Step 3. In the review
     summary, show "<Role> (general)" instead of a company.

## Step 2: Analyze the job

Write `applications/<Slug>/job_analysis.json` (shape in `reference/schemas.md`):
- `required_skills` holds the hard skills, tools, and qualifications the posting requires. `preferred_skills` holds the nice-to-haves.
  `keywords` holds the remaining terms an ATS or recruiter would search for: domain terms, methods, and certifications.
- Spell each term **exactly as the posting does** (for example "Power BI", "S&OP", "SQL"), as a short phrase.
  Leave out generic soft skills unless the posting stresses them.
- `search_queries` holds 8 to 12 varied web queries for finding similar open roles.

## Step 3: Draft the tailored resume

1. Read `resume/base_resume.json` and run `kit score resume/base_resume.json applications/<Slug>/job_analysis.json`
   to get the baseline.
2. Write `applications/<Slug>/drafts/draft_1.json`, a tailored copy that follows `reference/ats-rules.md`.
   Honesty comes first: rephrase, reorder, emphasize, and trim only what is true in the base resume. You may
   add facts the user has stated in this chat. Never invent skills, tools, metrics, employers, titles, or dates.
3. Check the draft:
   - `kit audit resume/base_resume.json applications/<Slug>/drafts/draft_1.json` flags any number, employer,
     role, date, or certification that is not in the base resume. Fix each flag unless the user confirmed that fact in this chat.
   - `kit compare resume/base_resume.json applications/<Slug>/drafts/draft_1.json applications/<Slug>/job_analysis.json`
   - If a missing keyword is honestly supported by the base resume (the candidate did the work but used other words),
     revise the draft and run the checks again. Don't keyword-stuff, and don't add anything just to raise the score.
4. Render it: `kit render applications/<Slug>/drafts/draft_1.json --docx applications/<Slug>/drafts/draft_1.docx --md applications/<Slug>/drafts/draft_1.md`
   If it estimates more than one page, cut low-relevance content (for example older school results, hobbies, or
   off-target bullets) and render again.

## Step 4: Ask the user to verify (repeat until they approve)

Show this in chat, then **end your turn and wait for the reply**:

```
## <Role> at <Company> — Draft <N>
ATS score: <base> → <new>/100   (keyword match <x>/50, title <y>/10, …)

**What I changed**
- …(concrete edits: which bullets were reworded toward which job keywords, what was reordered, what was cut)

**Please confirm. These are in the job but not in your resume, so I did NOT add them:**
- <gap 1>: do you have real experience with this? If yes, tell me where and what you did.
- …

**Still missing:** <missing required keywords, if any>

<the full draft as Markdown, from drafts/draft_<N>.md>

Reply **approve** to finalize, or tell me what to change.
```

When the user replies:
- **Feedback** (corrections, new facts, tone, length, what to emphasize or drop): write `drafts/draft_<N+1>.json`,
  then run audit, compare, and render again, and show the same summary for the new draft. Facts the user gives you
  in chat may go into the resume, but use only what they actually said and don't embellish it. Keep going for as many rounds as they want.
- If the user asks you to add something false or unverifiable, such as a skill they say they don't have or a made-up
  metric, explain why it is risky (interviews, background checks) and offer an honest alternative.
- **Approve** (for example "approve", "looks good", "finalize", or "yes"): go to Step 5.

## Step 5: Finalize

1. Copy the approved draft JSON to `applications/<Slug>/<Slug>_Resume.json`.
2. `kit render applications/<Slug>/<Slug>_Resume.json --docx applications/<Slug>/<Slug>_Resume.docx --md applications/<Slug>/<Slug>_Resume.md`
3. `kit score applications/<Slug>/<Slug>_Resume.json applications/<Slug>/job_analysis.json --json > applications/<Slug>/ats_report.json`
4. `kit log --tracker applications/job_tracker.xlsx --company "<Company>" --role "<Role>" --url "<job url>" --before <base score> --after <final score> --file applications/<Slug>/<Slug>_Resume.docx`
5. Tell the user the resume file path and the final score. In cloud mode, send the DOCX file if you have a tool
   for sending files. Unless they said to skip it, start Step 6.

## Step 6: Deep research for similar jobs, appended to the Excel tracker

Goal: about **15 to 25 currently open** postings similar to this one in role, seniority, skills, and location,
where the user has a realistic chance.

Run this as a focused version of the `/find-jobs` sweep. Read `.claude/skills/find-jobs/SKILL.md` and follow its
steps 2 to 4 (career-portal scan, job boards, LinkedIn hiring posts, browser mode if available, then verify).
Build the criteria from `job_analysis.json`: its title and synonyms, required skills, location, and seniority.
Use these settings:
- Run folder: `applications/<Slug>/research/`. Write one JSON file per source group there.
- Leave out the original posting.
- Merge with `kit add-jobs applications/<Slug>/research/*.json --tracker applications/job_tracker.xlsx --found-for "<Company> – <Role>" --resume applications/<Slug>/<Slug>_Resume.json`.
  This appends new rows only, skips jobs already in the tracker, and ranks the new rows by match %.
- Report how many jobs were added and skipped, the top 5 by match % with their links, and any LinkedIn posts with a direct contact.
- Refresh the phone view with `kit export-md`.
- In role mode, the quick search in 1B already covers this. Run only the parts it skipped (groups D and E, plus a
  deeper LinkedIn-post search).

If the user wants research only, or wants to research before approving, run Step 6 by itself. Use the base resume
for match % if no approved resume exists yet.

## Step 7: Save

Follow "End of run: save" in `jobkit/sessions.md`, with a commit message like `Tailor resume: <Company> – <Role>`.

## Updating the base resume

If the user gives you a new resume file, run `kit extract-text <file>`, rebuild `resume/base_resume.json` faithfully
(no rewording), run `kit validate`, show them the result to confirm, and then replace `resume/base_resume.docx`.
If they confirm a new fact during tailoring (such as a skill they really have), offer to add it to the base resume too.
