# Job Search Toolkit: Claude Code skills

| Command | What it does |
|---|---|
| `/tailor <job-url>` | Tailors your resume to one posting, iterates with you until you approve, saves it as `<Company>_<Role>_Resume.docx`, and adds similar jobs to the tracker |
| `/find-jobs <what you want>` | Deep search for jobs and internships across career portals, job boards, and LinkedIn hiring posts, added to the same tracker |

Example: `/find-jobs supply chain / operations internship, Bengaluru or remote, last 14 days`

You don't need an API key. Claude Code uses its own web fetch and search tools.

## What happens
1. **Reads the posting.** Claude fetches the job page. If that fails, a JSON-LD fallback reader tries, and as a
   last resort Claude asks you to paste the job text.
2. **Analyzes it.** Claude lists the required skills, preferred skills, and ATS keywords, spelled exactly as the posting has them.
3. **Tailors your base resume** (`resume/base_resume.json`) for a strong ATS score without inventing anything.
   An `audit` check flags any number, employer, role, date, or certification that isn't in your base resume.
4. **Asks you to verify in chat.** You see the before/after ATS score, what changed, the skills the job wants that
   your resume doesn't show (so you can confirm whether you have them), and the full draft. Reply with feedback
   and it iterates. Reply **approve** when you're happy with it.
5. **Saves** `applications/<Company>_<Role>/<Company>_<Role>_Resume.docx` (plus `.md` and `.json`), as a
   single-column ATS-friendly DOCX.
6. **Researches similar open jobs** on the web and appends them to the running tracker
   `applications/job_tracker.xlsx`. Jobs found on earlier runs are skipped, and each new job is ranked by how many
   of its key skills your resume covers. A second sheet logs every resume you tailor.

## How `/find-jobs` searches
1. **Company career portals** via the public job APIs of Greenhouse, Lever, Ashby, SmartRecruiters, Workable,
   Recruitee, and Workday (`kit scan-boards`). The companies it checks live in `job_search/watchlist.json`.
   The list grows on every run: whenever web search turns up a company on one of these platforms, it's added
   (`kit watch add <careers-url>`).
2. **Job boards** via web search: LinkedIn Jobs, Indeed, Naukri, Glassdoor, foundit, Internshala, Unstop, iimjobs,
   Instahyre, Wellfound, Cutshort, hiring.cafe, and Google Jobs.
3. **LinkedIn hiring posts** ("we're hiring, DM me / mail your CV") found with `site:linkedin.com/posts` searches.
   The poster and how to apply go in the tracker.
4. **Your logged-in Chrome** when you start Claude Code with `claude --chrome`. This is the deepest option: it uses
   LinkedIn's own post search, hiring.cafe, Indeed, and Naukri, which block plain web fetching. It browses at a human
   pace, reads only, and stops on CAPTCHAs or warnings. Heavy automation can get a LinkedIn account restricted.

Every posting is opened and checked before it's added. Duplicates are removed across sources and across runs,
and each job gets a match % against your resume. Results go to `applications/job_tracker.xlsx`, sheet **Jobs**,
with columns for Type, Stipend/Salary, Deadline, Apply Via, Poster/Contact, Status, and more.

## Setup
```bash
python3 -m pip install -r requirements.txt
```
Open Claude Code in this repository (`claude`, or `claude --chrome` for browser mode).

## Layout
```
.claude/skills/tailor/      /tailor workflow, ATS writing rules, JSON shapes
.claude/skills/find-jobs/   /find-jobs workflow
jobkit/kit.py               helper CLI (python3 jobkit/kit.py --help): score, audit, render, add-jobs,
                            scan-boards, watch, detect-ats, search-urls, fetch-job, extract-text
job_search/                 watchlist.json, saved_searches.json, runs/<date>_<query>/ raw results
resume/
  base_resume.docx          your original resume
  base_resume.json          the facts every tailored version is built from
applications/               one folder per job + job_tracker.xlsx
tests/                      python3 -m pytest -q
```

## Changing your base resume
Edit `resume/base_resume.json` directly, or give Claude a new file and say "update my base resume". It extracts the
text, rebuilds the JSON, and asks you to confirm before replacing anything.

## About the ATS score
`kit score` is a transparent heuristic, not any vendor's real algorithm. It scores keyword match (50), title
alignment (10), sections (10), bullet quality (15), length (5), and parse safety (10). Use it to compare drafts,
and don't chase 100 at the cost of honesty or readability.
