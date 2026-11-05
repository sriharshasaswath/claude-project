# JSON shapes

Optional fields can be omitted. Missing keys are filled with empty values. `kit validate FILE` checks a resume.

## Resume (`resume/base_resume.json`, drafts, final)

```json
{
  "contact": {"name": "", "email": "", "phone": "", "location": "", "links": ["linkedin.com/in/..."]},
  "headline": "Target title line",
  "summary": "2-3 line summary",
  "skills": [{"category": "Analytics & Tools", "skills": ["Power BI", "SQL"]}],
  "education": [{"degree": "MBA", "school": "", "location": "", "start": "2026", "end": "2028", "score": "CGPA 10.00/10.00", "details": []}],
  "experience": [{"title": "", "company": "", "location": "", "start": "May 2022", "end": "Nov 2024", "bullets": [""]}],
  "projects": [{"name": "", "org": "", "dates": "2022–2023", "link": "", "bullets": [""]}],
  "certifications": [{"name": "", "issuer": "", "date": "2026", "details": "one line"}],
  "leadership": [{"title": "", "company": "", "location": "", "start": "", "end": "", "bullets": [""]}],
  "additional": [{"label": "Interests", "text": ""}]
}
```

## Job analysis (`applications/<Slug>/job_analysis.json`)

```json
{
  "url": "https://...",
  "title": "Supply Chain Analyst",
  "company": "Acme",
  "location": "Bengaluru, India",
  "seniority": "Entry | Mid | Senior | Manager",
  "required_skills": ["SQL", "Power BI", "Demand Forecasting"],
  "preferred_skills": ["SAP", "Python"],
  "keywords": ["S&OP", "inventory optimization", "KPI"],
  "responsibilities": ["..."],
  "search_queries": ["supply chain analyst Bengaluru Power BI SQL", "..."]
}
```

## Job record (`similar_jobs.json`, `job_search/runs/<run>/<group>.json`)

Either `{"jobs": [...]}` or a bare list. Only `title` and `url` are required. `kit add-jobs` accepts several files at once.

```json
{
  "jobs": [
    {
      "title": "Supply Chain Analyst Intern",
      "company": "Acme",
      "location": "Bengaluru",
      "work_mode": "Remote | Hybrid | Onsite",
      "type": "Internship | Full-time | Contract",
      "experience": "0-2 years",
      "salary": "₹25,000/month stipend",
      "duration": "6 months",
      "date_posted": "2026-11-01",
      "deadline": "2026-11-20",
      "source": "LinkedIn | LinkedIn post | Naukri | Internshala | Acme careers (Greenhouse) | ...",
      "found_via": "Career portal API | Job board | Social post | Browser | Web search",
      "apply_via": "https://apply-link or hr@acme.com or 'DM poster'",
      "contact": "Poster name – https://linkedin.com/in/...",
      "key_skills": ["SQL", "Power BI"],
      "why_relevant": "one sentence",
      "url": "https://... (the posting, or the LinkedIn post URL)"
    }
  ]
}
```

## Watchlist (`job_search/watchlist.json`)

Managed with `kit watch add <careers-url> --name <Company>`, `kit watch list`, and `kit watch remove <Company>`.

```json
[
  {"name": "Acme", "ats": "greenhouse", "slug": "acme"},
  {"name": "Big Co", "ats": "workday", "host": "bigco.wd5.myworkdayjobs.com", "tenant": "bigco", "site": "External"}
]
```
