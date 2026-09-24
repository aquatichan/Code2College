# Deploying Hirewatch for friends

Hirewatch runs in two lanes that don't interfere with each other:

| | **Sandbox** (you, testing) | **Production** (friends) |
|---|---|---|
| App build | Debug, run from Xcode | Release, installed through TestFlight |
| Server | `server/run-dev.sh` on your Mac | Fly.io, `https://hirewatch.fly.dev` |
| Server data | `server/data/` | a Fly volume |
| Hirewheel sign-in | a browser window opens on your Mac | streamed into the app (noVNC) |
| Push gateway | APNs sandbox | APNs production |

The build picks its server automatically (`HW_DEFAULT_SERVER`, set per
configuration in the Xcode project), and each phone tells the server which push
gateway its token belongs to. So a Debug build can point at the production server
("Use a different server" on the connect screen) and push still reaches it.

The two servers have separate databases and separate `HW_SECRET_KEY`s. An
account on one does not exist on the other.

---

## 1. Put the server on Fly.io (~$6/month)

A 1 GB machine is needed for Chromium; it must stay on around the clock because
the scanner runs inside it.

```bash
brew install flyctl
fly auth signup                       # or: fly auth login

cd hirewheel_scraper_mob/server
fly apps create hirewatch             # name taken? pick another — see note below
fly volumes create hirewatch_data --region dfw --size 3

fly secrets set \
  HW_SECRET_KEY="$(python3 -m hwserver.keygen)" \
  HW_INVITE_CODE="pick-something-to-text-your-friends"

fly deploy
curl https://hirewatch.fly.dev/healthz        # → {"ok":true}
```

**Save the `HW_SECRET_KEY`** somewhere safe, like a password manager (`fly secrets`
won't show it again). If it's lost, everyone has to sign in to Hirewheel again.

If you used a different app name, change it in three places: `app` and
`HW_PUBLIC_URL` in `fly.toml`, and `HW_DEFAULT_SERVER` (Release) in
`ios/Hirewatch.xcodeproj` (Build Settings → search "HW_DEFAULT_SERVER").

With `HW_ENV=production` (set in `fly.toml`) the server **refuses to start** if
the secret key or invite code is missing, the URL isn't HTTPS, or sign-in isn't
set to the streamed mode. If a deploy won't come up, run `fly logs`, which lists
exactly what's wrong.

**Sign in yourself first.** The streamed sign-in has been tested piece by piece
(the relay has an automated test), but it has not yet run on a real Fly machine.
Be the first to sign in, then invite friends.

## 2. Turn on real push (needs the paid Apple account)

One key covers both sandbox and production.

1. [developer.apple.com](https://developer.apple.com/account/resources/authkeys/list)
   → Keys → **+** → tick *Apple Push Notifications service (APNs)* → download
   `AuthKey_XXXXXXXXXX.p8`. You can only download it once. Note the **Key ID**
   and the account's **Team ID** (top right of the page).
2. Give it to the server, then keep the file out of git (`*.p8` is already
   ignored):
   ```bash
   fly secrets set \
     HW_APNS_KEY="$(cat ~/Downloads/AuthKey_XXXXXXXXXX.p8)" \
     HW_APNS_KEY_ID=XXXXXXXXXX \
     HW_APNS_TEAM_ID=YYYYYYYYYY
   ```
3. In `fly.toml` set `HW_PUSH_BACKEND = "apns"`, then `fly deploy`.

The app notices `remote_push` flip to true and stops using its
background-refresh fallback, so nobody gets notified twice.

## 3. Ship the app through TestFlight

In Xcode, open `ios/Hirewatch.xcodeproj`:

1. **Signing & Capabilities → Team:** the paid account. Push is already declared
   in `Hirewatch.entitlements`.
2. **Product → Archive**, then **Distribute App → TestFlight & App Store**. Xcode
   registers `com.aaronqin.hirewatch`, switches push to production, and uploads.
   The first upload asks you to create the app record in App Store Connect.
3. In [App Store Connect](https://appstoreconnect.apple.com) → your app →
   **TestFlight**:
   - **External Testing** → create a group → add the build → turn on the
     **public link**. The first build goes through Beta App Review, usually
     within a day. Later builds are mostly automatic.
   - Internal testing skips review, but every tester must be added to the Apple
     team, which is overkill for friends.

Before each new upload, bump **Build** (`CURRENT_PROJECT_VERSION`), or App Store
Connect rejects the upload as a duplicate.

## 4. What a friend does

1. Install **TestFlight** from the App Store, then open your public link.
2. Open Hirewatch and enter the invite code. The server is already filled in.
3. **Sign in to Hirewheel.** Hirewheel's real login page appears inside the app,
   and they type their password there. The server keeps only the session.
4. Allow notifications. The first scan runs immediately and quietly records
   what's there; after that they get one notification per scan whenever
   something changes (every 3 hours).

---

## Day-to-day

```bash
fly logs                  # what the scanner is doing
fly ssh console           # shell on the machine (data is in /data)
fly deploy                # ship server changes
```

Server changes: test them locally with `./run-dev.sh` and a Debug build, then
`fly deploy`. App changes: test them in Debug, then archive and upload.

## Before you invite anyone

This server will hold live Hirewheel sessions for other students, most of whom
are minors. Read "A note on other people's accounts" in the
[README](README.md). [PRIVACY.md](PRIVACY.md) tells friends to contact whoever
sent the invite code. That's you, so be ready to delete someone's data by hand
if they ask (Settings → Delete does it too). External TestFlight will also ask
for a contact email and a short beta description.
