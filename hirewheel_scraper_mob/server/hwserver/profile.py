"""Reading the signed-in student's own account details.

Only the *login* email is taken. The account page also shows a parent/guardian
address — that belongs to someone who never agreed to use this tool, so it is
deliberately never parsed or stored.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from . import config

ACCOUNT_URL = f"{config.BASE_URL}/account"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")

# The page labels the account holder's address with this exact phrase, which is
# what separates it from the guardian address further down.
_LOGIN_LABEL = "current login email"


def parse_login_email(html: str) -> str | None:
    """Pull the account holder's login email out of /account markup."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup

    for node in root.find_all(string=_EMAIL):
        address = _EMAIL.search(str(node))
        if address is None:
            continue

        # Walk up until there's enough surrounding text to read the label.
        box = node.parent
        for _ in range(4):
            if box is None or box.parent is None:
                break
            context = " ".join(box.get_text(" ").split()).lower()
            if _LOGIN_LABEL in context:
                # Guard against a container so large it swallowed both addresses.
                if "parent" not in context.split(_LOGIN_LABEL)[0][-60:]:
                    return address.group(0)
            if len(context) > 30:
                break
            box = box.parent
    return None


def fetch_login_email(browser) -> str | None:
    """Load /account with the live session and return the login email, or None.

    Best-effort: a missing email is cosmetic, never a reason to fail a sign-in.
    """
    try:
        result = browser.fetch(ACCOUNT_URL)
    except Exception as exc:  # network/timeout
        print(f"[profile] could not load account page: {exc}")
        return None
    return parse_login_email(result.html)
