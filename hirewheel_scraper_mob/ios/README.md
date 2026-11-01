# Hirewatch — iOS app

Native SwiftUI, and self-contained: the app signs in to Hirewheel, scans your
pages, works out what changed, stores the history and notifies you, all on the
phone. No server, no invite code, no Mac once it's installed.

## Running it

```bash
open ios/Hirewatch.xcodeproj
```

Pick an iPhone simulator and hit **Run** (⌘R). No setup step, and no packages to
download: the only outside code is what ships with iOS.

To build from the command line instead:

```bash
cd ios
xcodebuild -project Hirewatch.xcodeproj -scheme Hirewatch \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
```

### On your own iPhone (free Apple ID)

1. Plug the phone in, unlock it, and tap **Trust This Computer**.
2. **Signing & Capabilities → Team**: your personal Apple ID (add it under
   Xcode → Settings → Accounts if it isn't listed).
3. Pick the phone as the run destination and hit ⌘R.
4. First launch only: on the phone, **Settings → General → VPN & Device
   Management** → your Apple ID → **Trust**.

After the first install, Window → Devices and Simulators → **Connect via
network** lets Xcode install over Wi-Fi with no cable.

Free-account builds stop opening after **7 days**. Run from Xcode again to renew;
the app's data is kept. A paid account (or TestFlight) removes the limit. See
[DEPLOY.md](../DEPLOY.md).

### How the project is wired

The project uses an Xcode 16+ **file-system synchronized group**, so every
`.swift` file under `Hirewatch/` is compiled automatically.

- Deployment target **iOS 18.0**; Swift 6 with `SWIFT_STRICT_CONCURRENCY = complete`
- Bundle id `com.aaronqin.hirewatch`, display name **Hirewatch**
- Background mode: *fetch*
- `Info.plist` carries `BGTaskSchedulerPermittedIdentifiers` — **without this iOS
  silently refuses to run the background scan**, and it is the single easiest
  thing to get wrong here
- No entitlements, so a free personal team can sign it

## How a scan works

| File | What it does |
|---|---|
| `Scraper/Hirewheel.swift` | The 17 watched pages, the Keychain cookie store, and the fetcher. Pages are server-rendered, so a plain HTTPS request returns everything the extractors read. No browser needed to scan. |
| `Scraper/HTML.swift` | A small DOM and CSS-selector engine on top of libxml2 (part of iOS). |
| `Scraper/Extractors.swift` | Line-for-line port of the server's `hwcore/extractors`. When Hirewheel's markup moves, fix it here. |
| `Scraper/Scanner.swift` | One scan: fetch all pages in parallel, extract, diff, store. Also follows Newsfeed and Special Events into their detail pages (capped at 12 each). |
| `Scraper/LocalStore.swift` | Everything on disk, plus the diff. |

Fetching in parallel is what makes a full scan (about 40 requests) fit in the
roughly 30 seconds iOS grants a background refresh.

### When scans happen

- When you open the app, if the last scan is more than 30 minutes old.
- When you pull down on the feed or tap ↻.
- When iOS grants background time (`BackgroundRefresh`). iOS decides how often
  based on how much the app is used. Expect every few hours, not on a schedule.

A scan with changes on pages you haven't muted raises one grouped local
notification. When the session expires, you get one "signed out" notification
that opens sign-in.

### Extractor parity

The Swift extractors were checked against the Python ones by running every HTML
sample in the server's tests (plus hand-written samples for the Program Hub
tabs, Marketplace Examples and detail pages) through both and comparing the
output field by field: 25 of 25 identical, content hashes included.

## Screens

| File | What it does |
|---|---|
| `FeedView` | Every scan, newest first. Pull down to scan. A red banner appears when the session has expired. |
| `SignInView` | Hirewheel's own login page in a web view (`HirewheelLoginView`). Done once the site serves a protected page instead of the login form. |
| `ScanDetailView` | One scan in full: added / changed / removed per page, with old → new field values, plus any pages that couldn't be read. |
| `PageHistoryView` | Every distinct state a page has been in. **Page** shows the saved copy as it looked then (`SnapshotPageView`); **Items** lists what was extracted. |
| `SettingsView` | Account, appearance, per-page notification mutes, sign out, delete everything. |

## Where things live

- **Hirewheel session cookies:** Keychain, `kSecAttrAccessibleAfterFirstUnlock`
  so background scans can read them while the phone is locked. Rewritten after
  every scan, because Hirewheel rotates its session cookie.
- **Scans, baselines and settings:** `Application Support/Hirewatch/index.json`.
- **Saved pages:** `Application Support/Hirewatch/snapshots/`, one HTML copy and
  one item list per page, written **only when that page changed**. Unchanged
  and failed scans are pruned after 3 days; at most 60 saved copies per page.

Your password is typed into Hirewheel's own page and goes straight to
Hirewheel. The app never reads it.

## Debug launch options

Set with `--setenv` on `xcrun simctl launch`, or in the scheme's environment:

- `HW_DEV_SIGNIN=browser` opens straight onto Hirewheel's login page.
- `HW_DEV_ROUTE=settings` or `HW_DEV_ROUTE=history:<page key>` opens a screen.
- `HW_DEV_BG_REFRESH=1` runs the background scan path once at launch.
