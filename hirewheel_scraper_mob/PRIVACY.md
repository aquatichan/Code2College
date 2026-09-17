# Privacy Policy — Hirewheel Watch

**Last updated: 15 September 2026**

Hirewheel Watch is an unofficial tool that watches your own HireWheel account for
new opportunities and tells you when something changes. It is **not affiliated
with, endorsed by, or operated by Code2College**.

This policy describes the app and its companion server. Because the server is
self-hosted, **whoever runs it is the data controller** — if a friend runs the
server you connect to, they hold your data, not the app's author.

## What is stored

| Data | Why | Where |
|---|---|---|
| **HireWheel session state** (cookies) | So the server can load your pages while your phone is asleep | Server database, encrypted |
| **Your HireWheel login email** | Shown in Settings so you know which account is connected | Server database |
| **Screenshots of your HireWheel pages** | The history timeline — seeing a page as it was at an earlier scan | Server disk, one image per page per scan |
| **Extracted page contents** | Detecting what changed between scans | Server database |
| **Device token** | Identifies your phone to your server | iOS Keychain + server database |
| **APNs push token** | Delivering notifications, when remote push is configured | Server database |
| **Purchase records** | Product id and Apple transaction id, to unlock faster scan intervals | Server database |

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
marketing. The only external services involved are Apple's (in-app purchases and,
if configured, push notifications).

## Encryption, stated honestly

Session state is encrypted at rest with a key held in the server's environment
rather than its database. This protects against a leaked database file alone.

**It is not end-to-end encryption.** The server must decrypt your session in
order to load your pages, so anyone holding both the database and the encryption
key can read it. Do not connect to a server you do not trust.

## Retention and deletion

Scans that found no changes are deleted after 30 days, along with their
screenshots. Scans that recorded changes are kept, because they are the history
the app exists to provide.

**Settings → Delete my account and all data** removes everything immediately:
your stored session, every scan, every screenshot, your email, device records and
purchase records. It cannot be undone. Apple retains its own record of any
purchase; that is outside this app's control and is what makes "Restore
purchases" work.

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

Data requests go to whoever operates the server you connected to. For the
software itself, open an issue on the repository.
