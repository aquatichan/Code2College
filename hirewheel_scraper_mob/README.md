# Hirewatch
> By a Code2College student—for Code2College students.

The [desktop watcher](../hirewheel_scraper_web) works, but it puts "something new
appeared on Hirewheel" in a Tkinter window on a Mac that has to be awake and
looked at. That is the wrong place for a time-sensitive alert. Hirewatch moves
the whole thing onto an iPhone: it signs in, scans, diffs, keeps a browsable
history, and notifies you, **all on the phone**. No server, nothing to host,
nothing to pay for.

```
hirewheel_scraper_mob/
  ios/        the app (native SwiftUI), does everything — see ios/README.md
  server/     the earlier server-based version (Python, FastAPI); optional, see below
  DEPLOY.md   getting it onto your phone, and onto friends' phones
```

## How it runs on a phone

The first version ran the scanner on a server, on the assumption that scanning
needed a real browser (Playwright). It doesn't: Hirewheel's pages are
server-rendered, so a plain HTTPS request with the session cookie returns
everything the extractors read. That made the server optional:

* **Sign-in** happens on Hirewheel's own login page, in a web view inside the
  app. Only the session cookies are kept, in the iPhone Keychain.
* **Scanning** fetches the pages in parallel and runs the same extractors, ported
  to Swift on top of the HTML parser built into iOS.
* **History and diffs** are stored in the app's own storage.
* **Notifications** are local. The phone ran the scan, so it already knows what
  changed.

The trade-off is timing. A server can scan every 3 hours on the dot; iOS only
lets an app run in the background when it chooses, typically every few hours
and more often for apps you open regularly. Hirewatch also scans whenever you
open it (if the last scan is over 30 minutes old), and on pull-to-refresh.

## What's new compared with the desktop version

1. **History.** The desktop overwrote its one snapshot per page every cycle, so
   there was never a past to look at. Hirewatch saves a copy of a page each time
   it changes, so you can step back through every state it has been in and see
   the page as it looked.
2. **Notifications instead of a window.** One grouped alert per scan
   ("Hirewheel — 3 updates · Marketplace, Notifications, Special Events"), never
   one per item, with per-page mutes.
3. **Recoverable sign-in.** When a session expires the desktop showed a banner
   telling you to quit and run a CLI command. Here it notifies you once and opens
   the login page.

## Things this does *not* do

* **It does not diff page archives or screenshots.** It diffs structured items by
  stable id (`data-notif-id` and friends) and a hash of the meaningful fields,
  carried over unchanged from the desktop version. That means no false alarms
  from reordering or "2 minutes ago" timestamps. Saved pages are for *viewing*.
* **It is not a general crawler.** It scans 17 configured pages: the 11
  top-level ones plus the Program Hub and Marketplace tabs, which are separate
  `?tab=` URLs. Detail pages are followed only from the Newsfeed and Special
  Events, capped at 12 each. Learning Modules is deliberately **not** followed:
  it links to ~190 module pages.

## Status

**App: builds clean** for the simulator and for real iPhones, Debug and Release,
under Swift 6 strict concurrency, with no third-party code.

**Extractors: matched against the originals.** Every HTML sample in the server's
tests, plus hand-written ones for the pages whose tests keep their HTML inline,
was run through both the Python and Swift extractors: 25 of 25 outputs
identical, down to the content hashes. The diff was checked against the real
notifications page: a first scan records silently, an added notification is one
addition, an edited one is one change.

**Checked against live Hirewheel:** the login page loads and fits the phone, and
a request with no session is correctly recognised as signed out. **Not yet done:**
a full scan with a real signed-in account on a phone. The server version ran
full scans against a live account (23 pages, 250+ items) with these same
extractors.

## The server version

`server/` is the earlier design: a Python service that scans on a fixed
schedule with a real browser and pushes to phones. The app no longer uses it.
It is kept because it is the reference the Swift extractors were ported from
(and checked against), and because a machine that never sleeps can scan on a
stricter schedule than iOS allows. [server/README.md](server/README.md) covers
running it.

## Legal

[Terms of Service](TERMS.md) · [Privacy Policy](PRIVACY.md)

Unofficial and not affiliated with Code2College. Code2College publishes a
[Privacy Policy](https://www.hirewheel.ai/privacy) and a
[Security page](https://www.hirewheel.ai/security), but no public Terms of
Service, which means there is no published permission for automated access
either. See section 2 of the Terms.

## A note on other people's accounts

Because everything stays on each person's own phone, sharing the app no longer
means holding anyone else's session. A friend who installs it signs in on their
phone, and their data never reaches you. Automated access to Hirewheel is still
a question for Code2College, though, so **ask them before handing it out widely.**

## Getting started

```bash
open ios/Hirewatch.xcodeproj
```

Hit Run for the simulator. For your own iPhone and for friends' phones, see
**[DEPLOY.md](DEPLOY.md)**.
