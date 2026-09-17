# Hirewheel Scraper — Mobile
> By a Code2College student—for Code2College students.

The [desktop watcher](../hirewheel_scraper_web) works, but it puts "something new
appeared on Hirewheel" in a Tkinter window on a Mac that has to be awake and
looked at. That is the wrong place for a time-sensitive alert. This version moves
the engine to a server and puts the alert on an iPhone — and, because the storage
layer had to be rebuilt anyway, adds something the desktop version never had:
**a browsable history of every scan**.

```
hirewheel_scraper_mob/
  server/   the scanning service (Python, FastAPI) — see server/README.md
  ios/      the phone app (native SwiftUI)        — see ios/README.md
```

## Why the scraper can't just run on the phone

The engine drives a real Chromium through Playwright. No mobile OS permits the
arbitrary code execution that needs, and there is no CDP-drivable browser inside
an app sandbox — this is a platform limit, not a language one, so Swift doesn't
change it. The split is:

* **the server** logs in, scans, diffs, screenshots, stores, and notifies
* **the phone** receives notifications and browses what the server found

## What's actually new here

Beyond the port, three things the desktop version could not do:

1. **History.** The desktop stored one screenshot per page and one snapshot per
   page, overwriting both every cycle — there was never a past to look at. Every
   scan is now appended, so you can scrub back through what Marketplace looked
   like at any previous scan.
2. **Notifications instead of a window.** One grouped alert per cycle ("Hirewheel —
   3 updates · Marketplace, Notifications, Special Events"), never one per item.
3. **Recoverable sign-in.** When a session expires the desktop showed a banner
   telling you to quit and run a CLI command. Here it notifies you and deep-links
   straight into the login flow.

## Things this does *not* do

Worth stating plainly, because the original sketch for this project assumed
otherwise:

* **It does not diff MHTML or page archives.** It diffs structured items by stable
  server id (`data-notif-id` and friends) and a content hash of the meaningful
  fields — carried over unchanged from the desktop version. That produces no false
  alarms from reordering or "2 minutes ago" timestamps, which archive diffing
  cannot avoid. Screenshots are stored for *viewing*, not for change detection.
* **It is not a general crawler.** It scans 17 configured pages — the 11
  top-level ones plus the Program Hub and Marketplace tabs, which turned out to
  be separate server-rendered `?tab=` URLs rather than client-side panes.
  Content hidden *within* a page (inactive tab panes, collapsed accordions) is
  expanded before capture.

  Detail pages are followed only from listings that explicitly opt in — currently
  the Newsfeed and Special Events, which is where the actual announcement text
  lives, adding ~6 pages. Learning Modules is deliberately **not** followed: it
  links to 188 module pages, which would turn a 50-second scan into minutes for
  very little signal. The cap is enforced in `hwserver/children.py`.

## Status

**Server: built and tested.** 26 passing tests, and it has been booted and
exercised over HTTP end to end.

**iOS app: builds and runs.** All 16 Swift files compile clean under Swift 6
strict concurrency. `open ios/HirewheelWatch.xcodeproj` and hit Run.

**Verified against live Hirewheel.** Hosted sign-in completes, and full scan
cycles run end to end: 283 items extracted across 23 pages (17 configured + 6 discovered
detail pages), one screenshot each per scan, and the history timeline accumulating across scans. Three pages report
zero items because they are genuinely empty for this account — Marketplace
currently says "No open projects right now", and My Projects / My Interviews have
no data yet.

Not yet done: the noVNC login path is implemented but only exercised through the
`local` mode fallback, and real APNs is wired but untestable without a paid Apple
account. No change has yet been *observed* between two scans, since Hirewheel
hasn't changed during testing — the diff engine is covered by tests but has not
fired on live data.

## Notifications today vs. later

Remote push needs a paid Apple Developer account, so the app ships with both
paths and the server tells it which is live:

* **Now** — iOS wakes the app periodically, it checks the server, and raises a
  *local* notification. Free, works on a free provisioning profile. iOS controls
  the timing, so alerts can lag.
* **Later** — drop the `.p8` key on the server, set `HW_PUSH_BACKEND=apns`, add
  the Push Notifications capability. Instant delivery, app closed. No code change;
  the app detects the switch and stops posting local notifications so you never
  get notified twice.

## Legal

[Terms of Service](TERMS.md) · [Privacy Policy](PRIVACY.md)

Unofficial and not affiliated with Code2College. Code2College publishes a
[Privacy Policy](https://www.hirewheel.ai/privacy) and a
[Security page](https://www.hirewheel.ai/security), but no public Terms of
Service — which means there is no published permission for automated access
either. See section 2 of the Terms before running this for anyone but yourself.

## A note on other people's accounts

Running this for anyone but yourself means your server holds live Hirewheel
sessions for other students, most of whom are minors. The design keeps passwords
out of it entirely — sign-in happens in Hirewheel's own form, and only the
resulting session is stored, encrypted — but that is still a real custodial
responsibility, not a technicality.

Enrollment is invite-gated (`HW_INVITE_CODE`) and there is a one-tap "delete
everything" in Settings. **Before inviting anyone, ask Code2College.** Until then,
run it for your own account.

## Getting started

```bash
# server
cd server
pip install -r requirements.txt
python -m playwright install chromium
export HW_SECRET_KEY="$(python -m hwserver.keygen)"
export HW_INVITE_CODE="pick-something"
python -m hwserver

# app: follow ios/README.md to create the Xcode project once, then run it
```
