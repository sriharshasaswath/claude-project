# Running the skills on a computer or on a phone

Both `/tailor` and `/find-jobs` follow this file at the start and end of every run.

## Start of run

1. Run `python3 jobkit/kit.py env`. It reports:
   - `mode`: **local** (Claude Code on the user's computer) or **cloud** (the Claude app on a phone, claude.ai/code
     on the web, or any other remote session). A cloud session starts as a fresh clone and is deleted when it ends.
   - `browser_mode`: whether the Claude in Chrome tools can be available. They never are in cloud sessions, and
     the Chrome extension doesn't exist on phones.
   - `save_branch` and `auto_save`: the user's saved preferences (`job_search/config.json`).
   - `deps_installed`: if false, run `python3 -m venv .venv && .venv/bin/python3 -m pip install -r requirements.txt`.
     `kit` uses the project `.venv` automatically. Don't install packages system-wide; Homebrew and some Linux Pythons block that.
2. **Cloud mode only: get the latest tracker and resumes.** Other sessions may have pushed new results since this
   clone was made. If the current branch is not `save_branch`, run `git fetch origin <save_branch>` and then
   `git merge --no-edit origin/<save_branch>`. A fresh session has no local changes, so this merge is clean.
   If it reports a conflict, stop and tell the user. Don't guess.

## Phone-friendly behaviour (cloud mode)

- The user is probably reading on a small screen. Keep chat output scannable: short headings, short tables, and
  links. Put long content (full job lists, raw research) in files, not chat.
- Browser mode isn't available. To make up for it in `/find-jobs`, run more web-search variants for LinkedIn
  posts and job boards (more synonyms, city names, hashtags, and date words like "this week" or the current
  month). Then tell the user which sources only a local `claude --chrome` run can reach.
- When files are ready, send them to the user if a tool for that is available: the final DOCX after `/tailor`,
  and the tracker plus `applications/JOBS.md` after `/find-jobs`. Otherwise give the repo paths.
- After changing the tracker, run `python3 jobkit/kit.py export-md` to refresh `applications/JOBS.md`. That's a
  Markdown view of the tracker that renders in the GitHub mobile app, where Excel files don't.

## End of run: save

The files to save are everything the run changed under `applications/`, `job_search/`, and `resume/`.

1. Run `git add applications/ job_search/ resume/` and commit with a short message, for example
   `Tailor resume: Acme – Supply Chain Analyst` or `find-jobs: supply chain internships (23 new)`.
2. Push:
   - If `auto_save` is **true**: run `git push origin HEAD:<save_branch>`. If the push is rejected because the
     remote moved on, run `git fetch origin <save_branch>`, then `git merge --no-edit origin/<save_branch>`, and push
     again. Retry once. If it still fails, tell the user. If the current branch differs from `save_branch`, also
     push the current branch (`git push -u origin HEAD`) so nothing is lost.
   - If `auto_save` is **null** (never asked): in **cloud mode**, ask the user once: *"Cloud sessions are deleted
     when they end. Should I always commit and push results to `<save_branch>` so they're saved to GitHub and the
     tracker keeps growing between sessions?"* Record the answer with `python3 jobkit/kit.py config auto_save true`
     or `false`, and use `config save_branch <name>` if they choose a different branch. In **local mode**, ask
     whether to commit and push this time.
   - If `auto_save` is **false**: don't push. In cloud mode, warn the user that the results disappear when the
     session ends unless they're pushed.
3. Tell the user in one line what was saved and where.
