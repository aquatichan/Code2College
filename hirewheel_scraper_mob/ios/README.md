# Hirewheel Watch — iOS app

Native SwiftUI. Talks to [`hwserver`](../server/README.md); it does no scraping of
its own.

## Running it

The Xcode project is already here, so:

```bash
open ios/HirewheelWatch.xcodeproj
```

Pick an iPhone simulator and hit **Run** (⌘R). That's it — no setup step.

This has been verified end to end: it builds clean, installs, launches, and
renders. Confirmed working on an iPhone 17 Pro simulator (iOS 26.5 SDK).

To build from the command line instead:

```bash
cd ios
xcodebuild -project HirewheelWatch.xcodeproj -scheme HirewheelWatch \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
```

### How the project is wired

The project uses an Xcode 16+ **file-system synchronized group**, so every
`.swift` file under `HirewheelWatch/` is compiled automatically. Add a file to the
folder and it is in the build — there is no per-file list in the project to
maintain or to get out of sync.

Already configured, so you don't have to:

- Deployment target **iOS 18.0**; Swift 6 with `SWIFT_STRICT_CONCURRENCY = complete`
- Bundle id `com.aaronqin.HirewheelWatch`
- Background modes: *fetch* and *remote-notification*
- `Info.plist` carries `BGTaskSchedulerPermittedIdentifiers` — **without this iOS
  silently refuses to run the background task**, and it is the single easiest
  thing to get wrong here
- `NSAllowsLocalNetworking`, so a server at plain `http://` on your LAN works

### Running on a physical device

Two extra steps:

1. **Signing & Capabilities → Team**: pick your Apple ID. Xcode will offer to
   register the bundle id; a free account is enough to run on your own device.
2. In the app's sign-in screen, replace `http://localhost:8000` with your Mac's
   LAN address — the phone can't reach your Mac's localhost. Find it with
   `ipconfig getifaddr en0`.

The simulator needs neither: it shares your Mac's network, so the prefilled
`localhost:8000` works as-is.

If you change the bundle id, change it in two other places or push will silently
never arrive: `BackgroundRefresh.taskIdentifier`, and `HW_APNS_BUNDLE_ID` on the
server.

## Screens

| File | What it does |
|---|---|
| `FeedView` | Every scan, newest first. Pull down to trigger a scan. A red banner appears when the session has expired. |
| `SignInView` | Two stages: connect to your server with an invite code, then sign in to Hirewheel through the server's streamed browser. |
| `ScanDetailView` | One cycle in full — added / changed / removed per page, with the screenshot and the old → new field deltas. |
| `PageHistoryView` | **The history timeline.** A scrubber of every stored scan for one page; tap any tick to see that moment's screenshot and item list. |
| `SettingsView` | Scan interval, per-page notification mutes, sign out, delete everything. |

The palette in `Theme.swift` is lifted from the desktop watcher's Tkinter UI so
the two front ends read as one product.

## How notifications work right now

Two paths, and the server tells the app which is live via `remote_push` on `/me`:

- **Today, with no Apple Developer account** — `BackgroundRefresh` asks iOS for
  periodic wake-ups, checks `/scans`, and raises a **local** notification if
  something is new. Works on a free provisioning profile. The catch is real: iOS
  decides when (and whether) to wake the app, so an alert can lag well behind the
  scan. The feed's status bar shows "background" so this isn't a mystery.
- **Once you have the account** — add the Push Notifications capability, put the
  `.p8` key on the server, set `HW_PUSH_BACKEND=apns` plus the key/team/bundle
  env vars, and remote push takes over. The app already registers for APNs and
  ships its device token to `/devices/push`; `BackgroundRefresh` notices
  `remote_push == true` and stops posting local notifications so you never get
  double-buzzed.

No code change is needed to flip between them.

## In-app purchases

Faster scan intervals are **non-consumable** StoreKit purchases — one-time, no
subscription. 24 hours is free; 12h is $0.99, 6h $1.99, 3h $3.99, 1h $5.99.

Each interval is bought **independently**: owning the 6-hour product unlocks the
6-hour interval and nothing else, in either direction. The server therefore
stores a set of unlocked intervals rather than a threshold.

Apple keeps the record: `Transaction.currentEntitlements` returns what the Apple
ID owns, across devices and reinstalls, and "Restore purchases" re-downloads it
for free.

**The device is not trusted.** StoreKit verifies a transaction locally, but that
proves nothing to the server, so the app forwards each entitlement's
`jwsRepresentation` and the server re-verifies the certificate chain up to Apple's
root before granting anything. `PATCH /me/interval` refuses an interval that has
not been paid for, regardless of what the app displays.

### Testing without an Apple Developer account

`Products.storekit` drives a local StoreKit environment, wired into the shared
scheme — so **Run from Xcode** and purchases work in the simulator with fake
money, no account needed. Manage or reset them in Xcode's Debug → StoreKit menu.

**If products still show "Unavailable" after selecting the file in Edit Scheme**,
Xcode can hold a stale internal association with its local test daemon
(`storekitd`'s "Octane" config store) that a normal re-save of the scheme does
not clear — the scheme XML looks correct, but no configuration ever actually
reaches the daemon before the app's product request fires, so it silently falls
through to the real network App Store instead (visible in the simulator's system
log as `Requesting products from Media API...`, with `accountMissing` errors
since there's no sandbox account). The fix: in Edit Scheme → Run → Options, set
StoreKit Configuration to **None**, close, reopen, and set it back to
`Products.storekit` — that round trip forces Xcode to push a fresh
configuration rather than trusting whatever it cached.

Two caveats:

* Prices only appear when launched **through Xcode** (⌘R). `simctl launch` does
  not apply the StoreKit configuration, so the price fields read "Unavailable"
  and tapping a locked interval explains why instead of doing nothing.
* Xcode signs local test transactions with its own certificate, not Apple's, so
  the server needs `HW_ALLOW_UNVERIFIED_PURCHASES=1` to accept them. That flag
  disables the security property that makes purchases meaningful — it is for a
  development machine only. In production set `HW_APPSTORE_ROOT_CA` instead.

Shipping this for real also needs a paid Apple Developer account, products
configured in App Store Connect, and — the part worth thinking about first — the
app passing App Review.

## Where the credentials live

The app stores exactly one secret: the device token from enrollment, in the
**Keychain** (`kSecAttrAccessibleAfterFirstUnlock`, so background refresh can read
it while the phone is locked). The server address sits in `UserDefaults`.

Your Hirewheel password is typed into Hirewheel's own login page, rendered by the
server's browser. It never reaches the phone, and the resulting session stays on
the server.
