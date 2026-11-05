# Resume Tailor: a Claude Code skill

Tailor your resume to any job posting with one command:

```
/tailor https://link-to-the-job-posting
```

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

## Setup
```bash
python3 -m pip install -r requirements.txt
```
Open Claude Code in this repository. The skill lives in `.claude/skills/tailor/`.

## Layout
```
.claude/skills/tailor/
  SKILL.md                  step-by-step workflow Claude follows
  reference/ats-rules.md    writing and honesty rules
  reference/schemas.md      JSON shapes
  scripts/resume_kit.py     helper CLI: score, audit, render, tracker, fetch-job, extract-text
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
