# Privacy Policy — Hirewatch

**Last updated: 23 September 2026**

Hirewatch is an unofficial tool that watches your own HireWheel account for
new opportunities and tells you when something changes. It is **not affiliated
with, endorsed by, or operated by Code2College**.

This policy describes the app and its companion server. **Whoever runs the
server you connect to holds your data.** The TestFlight build connects to a server
the app's author runs, so for that server it is the author. If you point the app
at a different server ("Use a different server"), its operator holds your data
instead.

## What is stored

| Data | Why | Where |
|---|---|---|
| **HireWheel session state** (cookies) | So the server can load your pages while your phone is asleep | Server database, encrypted |
| **Your HireWheel login email** | Shown in Settings so you know which account is connected | Server database |
| **Screenshots of your HireWheel pages** | The history timeline — seeing a page as it was at an earlier scan | Server disk, one image per page per scan |
| **Extracted page contents** | Detecting what changed between scans | Server database |
| **Device token** | Identifies your phone to your server | iOS Keychain + server database |
| **APNs push token** | Delivering notifications, when remote push is configured | Server database |

Your **HireWheel password is never seen, transmitted, or stored by this app**.
Sign-in happens inside HireWheel's own login page, rendered by a browser the
server controls; only the resulting session is kept.

The HireWheel account page also displays a **parent/guardian email address**. The
extractor is deliberately anchored to the "Current login email" label so that the
guardian address is never read or stored — it belongs to someone who never agreed
to use this tool.

## What is not stored

No analytics, no advertising identifiers, no crash reporting, no location, no
contacts. Nothing is sold, and nothing is shared with any third party for
marketing.

Two outside services are involved, only to keep the app running:

* **Fly.io** hosts the author's server, so the database and screenshots above sit
  on its infrastructure (in the United States).
* **Apple's push notification service** delivers the notification text (for
  example "Hirewheel — 3 updates · Marketplace"), not the page contents.

TestFlight itself is run by Apple. If you choose to share crash reports or
feedback through it, Apple's terms cover that, not this policy.

## Encryption, stated honestly

Session state is encrypted at rest with a key held in the server's environment
rather than its database. This protects against a leaked database file alone.

**It is not end-to-end encryption.** The server must decrypt your session in
order to load your pages, so anyone holding both the database and the encryption
key can read it. Do not connect to a server you do not trust.

## Your account

Your account is identified by your HireWheel login email. Signing out of the app
removes that phone's access but keeps your history, so signing back in with the
same HireWheel account — on the same phone or a new one — brings your previous
scans back. Someone else signing in on your phone gets their own separate
account and never sees yours.

## Retention and deletion

Scans that found no changes are deleted after 3 days, along with their
screenshots. Scans that recorded changes are kept, because they are the history
the app exists to provide.

**Settings → Delete my account and all data** removes everything immediately:
your stored session, every scan, every screenshot, your email and device
records. It cannot be undone.

## Students under 18

HireWheel is an educational platform and much of what this app copies is student
educational data. Code2College's own
[Privacy Policy](https://www.hirewheel.ai/privacy) describes FERPA alignment,
school coordinator oversight for minors, and audit logging of data access.

Running this server for anyone other than yourself means holding another
student's session and a copy of their educational records **outside the controls
Code2College maintains**. If you do that for a minor, obtain their guardian's
informed consent first, and read the Authorization section of the
[Terms of Service](TERMS.md) before inviting anyone.

## Contact

For the author's server, contact the person who sent you the invite code:
they run it and can answer questions or delete your data by hand. For any other
server, contact whoever runs it. For the software itself, open an issue on the
repository.
