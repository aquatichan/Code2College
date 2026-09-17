"""One-time login: `python -m hwscraper.login`.

Opens a real browser window using the persistent profile. You sign in to
Hirewheel yourself (including any MFA). Once you're in, the session is saved to
``.pw_profile/`` and every future scrape reuses it — no need to log in again
until the session naturally expires.
"""

from __future__ import annotations

from .session import Session


def main() -> int:
    print("Opening a browser window. Please sign in to Hirewheel as a student…")
    with Session(headless=False) as sess:
        if sess.is_authenticated():
            print("Already signed in — nothing to do. You're set.")
            return 0
        ok = sess.wait_for_login(timeout_s=300)
        if ok:
            print("Signed in. Session saved — you can close this and run the app.")
            return 0
        print("Timed out waiting for login. Re-run this command to try again.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
