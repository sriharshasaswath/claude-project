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

## Similar jobs (`applications/<Slug>/similar_jobs.json`)

```json
{
  "jobs": [
    {
      "title": "", "company": "", "location": "", "work_mode": "Remote | Hybrid | Onsite",
      "experience": "0-2 years", "salary": "", "date_posted": "2026-11-01",
      "source": "LinkedIn | Naukri | company site | ...", "url": "https://...",
      "key_skills": ["SQL", "Power BI"], "why_similar": "one sentence"
    }
  ]
}
```
