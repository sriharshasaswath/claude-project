# Rules for a tailored resume

## Honesty (never break these)
- Every claim must trace to `resume/base_resume.json` or to something the user said in this chat.
- Never add a skill, tool, certification, employer, title, date, degree, grade, or metric that isn't supported by those.
  If the job needs something the resume doesn't show, list it as a **gap** and ask the user about it.
- Keep every metric exactly as written (for example 1300+, 195%, 130+, 12). Don't round, inflate, or estimate.
- Keep employer names, job titles, dates, scores, and contact details unchanged. If the email or phone looks
  like a typo, ask the user instead of correcting it.

## What you may change
- **Headline:** a one-line target title that mirrors the job title where it's accurate. For example, use
  "MBA Candidate (IIT Kanpur) | Supply Chain & Operations Analytics", not a title the candidate never held.
- **Summary:** 2 to 3 lines that lead with the job's top 3 or 4 required keywords that the candidate genuinely
  has, and with their most relevant experience.
- **Skills:** regroup and reorder so the job's terms come first, using the job's exact spelling when it's the same
  thing (for example "Power BI", "SAP ERP", "CI/CD"). Only include skills shown elsewhere in the resume or confirmed by the user.
- **Bullets:** reword toward the job's vocabulary when it describes the same work, lead with the most relevant
  bullets, and cut or shorten bullets that don't matter for this role.
- **Section order:** put the most relevant section first, after the summary and skills.
  Use `kit render --order summary,skills,experience,projects,education,certifications,leadership,additional`
  (or a different order). For campus or fresher-style roles, education can come right after the summary.
- **Leaving content out:** you may drop low-relevance items (for example a hobby, or Class X/XII results for
  experienced hires) to stay at one page.

## ATS formatting (the renderer already does this, so don't fight it)
- Single column. No tables, text boxes, images, icons, or headers and footers holding content.
- Standard section headings: Summary, Skills, Experience, Projects, Education, Certifications.
- Plain characters only. No emoji and no ▪ or ★ symbols.
- Dates written the same way throughout ("May 2022 – Nov 2024").

## Bullet style
- Start every bullet with a strong past-tense verb (Led, Built, Optimized, Analysed, Reduced...), or present tense for a current role.
- Use 8 to 35 words, one or two lines.
- Structure it as action, then what or how (tools), then result. Add a result only if it is real.
- Use 3 to 5 bullets for the most relevant role and 1 to 3 for the others.

## Keyword placement
- Put each important required keyword in the Skills section **and** in at least one bullet that shows it in use.
- Write out the acronym and the full form once where both are common: "Sales & Operations Planning (S&OP)".
- Don't repeat a keyword unnaturally and don't use hidden or white text.

## Length
- One page, about 450 to 750 words, for candidates with under 8 years of experience.
