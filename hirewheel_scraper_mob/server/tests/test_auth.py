"""Auth detection.

This is the check that decides whether a Hirewheel session is alive, and getting
it wrong is silent and total: a too-strict check makes sign-in never complete,
which is exactly what an inherited `a[href="/logout"]` selector did — that element
does not exist on the real site, and being ANDed with the URL check it forced
every session to read as signed out.

These tests pin the behaviour so that can't come back.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hwserver.browser import UserBrowser, _looks_like_login  # noqa: E402

SIGNED_IN_URL = "https://www.hirewheel.ai/intern/notifications"
LOGIN_URL = "https://www.hirewheel.ai/login?next=%2Fintern%2Fnotifications"


class _StubLocator:
    def __init__(self, count: int):
        self._count = count

    def count(self) -> int:
        return self._count


class _StubPage:
    """Stands in for a Playwright page: records the selector it was asked about."""

    def __init__(self, url: str, password_fields: int = 0):
        self.url = url
        self.password_fields = password_fields
        self.selectors: list[str] = []

    def locator(self, selector: str) -> _StubLocator:
        self.selectors.append(selector)
        return _StubLocator(self.password_fields)


def _browser_with(page: _StubPage) -> UserBrowser:
    browser = UserBrowser(None)
    browser._page = page  # type: ignore[assignment]
    return browser


def test_login_url_markers():
    assert _looks_like_login(LOGIN_URL)
    assert _looks_like_login("https://www.hirewheel.ai/accounts/login")
    assert not _looks_like_login(SIGNED_IN_URL)


def test_redirect_to_login_means_signed_out():
    browser = _browser_with(_StubPage(LOGIN_URL, password_fields=1))
    assert browser._page_is_authed(LOGIN_URL) is False


def test_protected_page_without_password_field_means_signed_in():
    page = _StubPage(SIGNED_IN_URL, password_fields=0)
    assert _browser_with(page)._page_is_authed(SIGNED_IN_URL) is True


def test_does_not_require_a_logout_link():
    """The regression. A signed-in page with no logout anchor must still count."""
    page = _StubPage(SIGNED_IN_URL, password_fields=0)
    assert _browser_with(page)._page_is_authed(SIGNED_IN_URL) is True
    assert not any("logout" in sel for sel in page.selectors), (
        f"auth check is looking for a logout element again: {page.selectors}"
    )


def test_password_form_on_a_protected_page_is_still_signed_in():
    """/account carries a change-password form while fully authenticated.

    An earlier version treated any password field as proof of a login form, which
    made that page read as signed out and would have aborted a scan cycle. Only
    the redirect decides.
    """
    account = "https://www.hirewheel.ai/account"
    page = _StubPage(account, password_fields=1)
    assert _browser_with(page)._page_is_authed(account) is True


def test_auth_check_does_not_inspect_the_dom_at_all():
    """The decision comes from the URL, so no selector can silently break it."""
    page = _StubPage(SIGNED_IN_URL, password_fields=3)
    assert _browser_with(page)._page_is_authed(SIGNED_IN_URL) is True
    assert page.selectors == [], f"unexpected DOM lookups: {page.selectors}"


def _run_all():
    for fn in (
        test_login_url_markers,
        test_redirect_to_login_means_signed_out,
        test_protected_page_without_password_field_means_signed_in,
        test_does_not_require_a_logout_link,
        test_password_form_on_a_protected_page_is_still_signed_in,
        test_auth_check_does_not_inspect_the_dom_at_all,
    ):
        fn()
        print(f"  ok  {fn.__name__}")
    print("\n6 tests passed.")


if __name__ == "__main__":
    _run_all()
