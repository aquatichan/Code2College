# Hirewatch — iOS app

Native SwiftUI. Talks to [`hwserver`](../server/README.md); it does no scraping of
its own.

## Running it

The Xcode project is already here, so:

```bash
open ios/Hirewatch.xcodeproj
```

Pick an iPhone simulator and hit **Run** (⌘R). That's it — no setup step.

This has been verified end to end: it builds clean, installs, launches, and
renders. Confirmed working on an iPhone 17 Pro simulator (iOS 26.5 SDK).

To build from the command line instead:

```bash
cd ios
xcodebuild -project Hirewatch.xcodeproj -scheme Hirewatch \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
```

### How the project is wired

The project uses an Xcode 16+ **file-system synchronized group**, so every
`.swift` file under `Hirewatch/` is compiled automatically. Add a file to the
folder and it is in the build — there is no per-file list in the project to
maintain or to get out of sync.

Already configured, so you don't have to:

- Deployment target **iOS 18.0**; Swift 6 with `SWIFT_STRICT_CONCURRENCY = complete`
- Bundle id `com.aaronqin.hirewatch`, display name **Hirewatch**
- Per-configuration server: Debug starts at `http://localhost:8000`, Release
  (TestFlight / App Store) at the hosted server. Both come from the
  `HW_DEFAULT_SERVER` build setting. Friends never see a server field;
  "Use a different server" reveals it
- Push entitlement (`Hirewatch.entitlements`). Debug builds register with APNs
  sandbox, archives with production, and the app tells the server which
- Background modes: *fetch* and *remote-notification*
- `Info.plist` carries `BGTaskSchedulerPermittedIdentifiers` — **without this iOS
  silently refuses to run the background task**, and it is the single easiest
  thing to get wrong here
- `NSAllowsLocalNetworking`, so a server at plain `http://` on your LAN works

### Running on a physical device

Two extra steps:

1. **Signing & Capabilities → Team**: pick the team. A **free** personal team
   can't sign the push entitlement, so with one, clear **Code Signing
   Entitlements** in Build Settings for your local run and don't commit that
   change. The app falls back to background refresh. A paid team needs
   nothing.
2. In the app's sign-in screen, replace `http://localhost:8000` with your Mac's
   LAN address — the phone can't reach your Mac's localhost. Find it with
   `ipconfig getifaddr en0`.

The simulator needs neither: it shares your Mac's network, so the prefilled
`localhost:8000` works as-is.

If you change the bundle id, also change `HW_APNS_BUNDLE_ID` on the server, or
push will silently never arrive. The background-refresh identifier follows the
bundle id automatically.

For TestFlight, see [DEPLOY.md](../DEPLOY.md).

## Screens

| File | What it does |
|---|---|
| `FeedView` | Every scan, newest first. Pull down to trigger a scan. A red banner appears when the session has expired. |
| `SignInView` | Two stages: enter the invite code, then sign in to Hirewheel through the server's streamed browser. |
| `ScanDetailView` | One cycle in full — added / changed / removed per page, with the screenshot and the old → new field deltas. |
| `PageHistoryView` | **The history timeline.** A scrubber of every stored scan for one page; tap any tick to see that moment's screenshot and item list. |
| `SettingsView` | Account, appearance, scan schedule, per-page notification mutes, sign out, delete everything. |

The palette in `Theme.swift` is lifted from the desktop watcher's Tkinter UI so
the two front ends read as one product.

## How notifications work right now

Two paths, and the server tells the app which is live via `remote_push` on `/me`:

- **Today, with no Apple Developer account** — `BackgroundRefresh` asks iOS for
  periodic wake-ups, checks `/scans`, and raises a **local** notification if
  something is new. Works on a free provisioning profile. The catch is real: iOS
  decides when (and whether) to wake the app, so an alert can lag well behind the
  scan. The feed's status bar shows "background" so this isn't a mystery.
- **Once you have the account** — put the `.p8` key on the server and set
  `HW_PUSH_BACKEND=apns` plus the key/team/bundle env vars, and remote push takes
  over. The entitlement is already in place. The app already registers for APNs and
  ships its device token to `/devices/push`; `BackgroundRefresh` notices
  `remote_push == true` and stops posting local notifications so you never get
  double-buzzed.

No code change is needed to flip between them.

## Accounts

The server identifies you by your HireWheel login email. Enrolling always makes a
fresh placeholder account; completing the HireWheel sign-in then links this phone
to any existing account with the same email, so **signing out and back in brings
your history back**. A different HireWheel account signing in on the same phone
gets its own account instead of inheriting the previous person's scans.

"Sign out of this device" forgets only this phone. "Delete my account and all
data" erases the account itself.

## Where the credentials live

The app stores exactly one secret: the device token from enrollment, in the
**Keychain** (`kSecAttrAccessibleAfterFirstUnlock`, so background refresh can read
it while the phone is locked). The server address sits in `UserDefaults`.

Your Hirewheel password is typed into Hirewheel's own login page, rendered by the
server's browser. It never reaches the phone, and the resulting session stays on
the server.
