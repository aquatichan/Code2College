# Getting Hirewatch onto phones

Hirewatch runs entirely on the phone, so there is nothing to host. The only
question is how the app gets installed.

| | **Your own phone, free** | **Friends' phones** |
|---|---|---|
| How | Run from Xcode | TestFlight |
| Apple account | Free Apple ID | Paid Apple Developer Program ($99/year) |
| Mac needed | To install, and again every 7 days | Only to upload builds |
| Lasts | 7 days, then run from Xcode again | 90 days per build |

---

## 1. Your own iPhone (free)

1. Plug the phone into the Mac, unlock it, and tap **Trust This Computer**.
2. Open `ios/Hirewatch.xcodeproj`. Select the **Hirewatch** target →
   **Signing & Capabilities** → **Team** → your Apple ID (add it under Xcode →
   Settings → Accounts if it isn't listed).
3. Choose your iPhone as the run destination (top of the window) and press ⌘R.
4. The first time, iOS refuses to open it. On the phone: **Settings → General →
   VPN & Device Management** → your Apple ID → **Trust**.
5. Open Hirewatch, sign in to Hirewheel, and allow notifications.

**No cable after the first time:** Xcode → Window → Devices and Simulators →
select the phone → tick **Connect via network**. While phone and Mac share a
Wi-Fi network, ⌘R installs wirelessly.

**Every 7 days** a free-account build stops opening. Press ⌘R again to renew.
Your scans and sign-in survive it.

Also on the phone: **Settings → General → Background App Refresh** must be on,
or iOS never runs the background scan. Low Power Mode pauses it too.

## 2. Friends' phones (TestFlight)

This needs the paid Apple Developer Program. A free Apple ID can only install on
devices plugged into your own Mac.

1. In Xcode, set **Team** to the paid account.
2. **Product → Archive**, then **Distribute App → TestFlight & App Store**. The
   first upload asks you to create the app record in App Store Connect.
3. In [App Store Connect](https://appstoreconnect.apple.com) → your app →
   **TestFlight** → **External Testing** → create a group → add the build → turn
   on the **public link**. The first build goes through Beta App Review, usually
   within a day.

Before each new upload, bump **Build** (`CURRENT_PROJECT_VERSION`), or App Store
Connect rejects it as a duplicate.

A friend installs **TestFlight**, opens your link, installs Hirewatch, and signs
in to their own Hirewheel account. Their session and history stay on their
phone; you never hold them.

## Before you share it

Hirewheel has no published permission for automated access, and Code2College's
Security page says all data access is audit-logged. Read section 2 of the
[Terms](TERMS.md), and ask Code2College before handing it out widely.
