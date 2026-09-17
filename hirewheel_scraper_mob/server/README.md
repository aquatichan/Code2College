# hwserver — the scanning service

The engine from [`hirewheel_scraper_web`](../../hirewheel_scraper_web), moved off
the desktop: it scans on a schedule, keeps every scan, and notifies a phone.

## What came across unchanged

`hwcore/` is a byte-for-byte copy of the desktop project's pure modules —
`models.py`, `diff.py`, and all 11 extractors. They are pure functions over HTML
with no dependency on Playwright, storage, or any UI, so they needed no edits.
Their tests pass here with only the import path changed (`hwscraper` → `hwcore`).

If a Hirewheel page changes its markup, fix the extractor in **both** projects.

## What was rewritten and why

| Desktop | Here | Reason |
|---|---|---|
| `session.py` | `browser.py` | The desktop used one persistent Chrome profile on disk — fine for one person on one Mac. Here each user's session is a Playwright *storage state* in the database, loaded into a fresh context per cycle. |
| `store.py` | `db.py` | The desktop kept one JSON file per page and overwrote it every cycle, so there was never more than one past state. Now every scan appends. **This is what makes history possible.** |
| `pipeline.py` | `pipeline.py` | Same loop, but writes to the database and screenshots *every* page every cycle rather than only changed ones — a timeline with holes is worse than none. |
| `scheduler.py` | `runner.py` | Same run/wait loop without the Tk event queue. A dead session is now skipped until re-login instead of re-probed forever. |
| `ui.py`, `login.py`, `app.py` | — | Replaced by the API and the iOS app. |

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium

export HW_SECRET_KEY="$(python -m hwserver.keygen)"
export HW_INVITE_CODE="something-only-you-know"
python -m hwserver
```

`HW_SECRET_KEY` encrypts stored Hirewheel sessions. **Losing it means every user
has to sign in again**; leaking it alongside the database means their sessions are
readable. It belongs in the environment, never in git.

See `.env.example` for the rest.

## Login modes

* `HW_LOGIN_MODE=local` (default) — the server opens a browser window on its own
  machine and you sign in there. Right for development and for running the watcher
  on your own laptop.
* `HW_LOGIN_MODE=novnc` — an ephemeral headful Chromium on a virtual display,
  streamed to the app over noVNC so you can sign in from the phone. Needs `Xvfb`,
  `x11vnc`, `websockify` and the noVNC assets, which is what the `Dockerfile`
  provides.

Either way the password is typed into Hirewheel's own login form. The server
watches only for the moment the session becomes valid — it never reads the form.

## Push

`HW_PUSH_BACKEND` decides how notifications are delivered:

* `none` (default) — device tokens are stored but nothing is sent. The iOS app
  falls back to background refresh plus a local notification, needing no Apple
  Developer account. `/me` reports `remote_push: false` so the app knows.
* `apns` — real remote push over HTTP/2, with an ES256 provider token signed from
  your `.p8` key. Set `HW_APNS_KEY_PATH`, `HW_APNS_KEY_ID`, `HW_APNS_TEAM_ID`,
  `HW_APNS_BUNDLE_ID`, and `HW_APNS_ENVIRONMENT`.

`apns.py` speaks the protocol directly — it is a signed JWT and one HTTP/2 POST,
so a push SDK would be more dependency than it is worth. The `.p8` is an
account-wide credential; `.gitignore` excludes `*.p8` for that reason.

## Tests

```bash
python -m tests.run_all
```

26 tests: the 15 carried over from the desktop project (extractors + diff), plus
new coverage for the storage layer, the pipeline against a fake browser, the APNs
provider token (verified cryptographically against its own key), and the API end
to end.

## Layout

```
hwcore/          copied verbatim — models, diff, 11 extractors
hwserver/
  config.py      the 17 watched pages, timing, env settings
  children.py    bounded detail-page discovery (opt-in per listing, capped)
  crypto.py      Fernet encryption for stored sessions
  db.py          append-only SQLite: scans, snapshots, diffs, devices
  browser.py     Playwright driven by a per-user storage state
  authflow.py    hosted interactive login (local window or streamed noVNC)
  media.py       screenshots → downscaled WebP, plus retention
  pipeline.py    one scan cycle
  runner.py      background scheduler
  apns.py        ES256 JWT + HTTP/2 APNs client
  push.py        notification dispatch (none | apns)
  api.py         FastAPI endpoints for the app
tests/           run with: python -m tests.run_all
```
