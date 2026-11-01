# Hirewheel Scraper
> By a Code2College student—for Code2College students.

<img width="1442" height="1440" alt="Screenshot 2026-07-20 at 6 13 56 PM" src="https://github.com/user-attachments/assets/2d16eb5b-5e0c-4ff0-8f11-3695ab1c83dc" />

> NOTICE: these changes were not actually observed in real time and were instead hardcoded for the purpose of the above demo preview.
> This app will be more rigorously tested and updated after the start of the Fall 2026 Term. 

Watches Hirewheel student pages and pops up **anything new** — fresh notifications, 
newly opened marketplace projects, new surveys, events, newsfeed posts — so 
opportunities don't slip past you. Every 3 hours it quietly scans your pages, 
diffs them against the last scan, and shows only what changed in a desktop window 
(with a screenshot of each changed page).

## How it works

1. **Log in once.** A real browser window opens; you sign in to Hirewheel
   yourself (MFA and all). Your session is saved to a local browser profile —
   no passwords are ever stored by this tool.
2. **It watches in the background.** A headless browser reuses that session,
   scans all your pages every 3 hours, and compares each page to last time.
3. **You see only the diffs.** New / changed / removed items show up in the
   "Hirewheel Watch" window, grouped by page, with each changed page's
   screenshot rendered inline in its card.

Because Hirewheel serves plain server-rendered HTML with stable item IDs
(`data-notif-id`, etc.), the diffs are precise — no false alarms from
reordering or timestamps.

## Setup

```bash
cd hirewheel_scraper
pip install -r requirements.txt
python -m playwright install chromium   # one-time browser download
```

## Run

```bash
# 1) Sign in once (opens a browser window):
python -m hwscraper.login

# 2) Start the watcher (opens the desktop window; runs a scan immediately,
#    then every 3 hours):
python -m hwscraper
```

If your session ever expires, the window shows a banner telling you to quit and
re-run `python -m hwscraper.login`.

## Watched pages

Learning Modules · Internship Prep · College Pathways · Marketplace ·
My Projects · My Interviews · Surveys · Program Hub · Special Events ·
Notifications · Newsfeed

## Layout

```
hwscraper/
  config.py        page list, 3-hour interval, paths
  session.py       Playwright persistent profile + login detection
  login.py         one-time interactive sign-in
  models.py        the Item shape + stable-id / content-hash logic
  store.py         per-page JSON snapshots
  diff.py          added / changed / removed between runs
  extractors/      one module per page (HTML → Items)
  pipeline.py      one full scan cycle
  scheduler.py     background thread, runs now + every 3h
  ui.py            Tkinter "Hirewheel Watch" window
  app.py           entry point (python -m hwscraper)
tests/             extractor + pipeline tests (run: python -m tests.test_pipeline)
```

## Tests

```bash
python -m tests.test_notifications
python -m tests.test_pipeline
```

## Status

Fully working engine + UI, with **all 11 page extractors** built from each
page's real markup and covered by tests (`tests/test_extractors.py`).

Two pages (**My Projects**, **My Interviews**) had no data at build time, so
their card selectors are best-effort with a whole-page "changed" safety net —
they'll be refined the first time real data appears. Program Hub currently
watches the **Deliverables** tab only (the other tabs load client-side).
