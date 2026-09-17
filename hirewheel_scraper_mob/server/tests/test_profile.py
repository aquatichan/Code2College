"""Reading the account holder's email — and only theirs.

The Hirewheel account page shows two addresses: the student's login email and a
parent/guardian address. The guardian never agreed to use this tool, so picking
the wrong one would mean storing a third party's personal data. These tests pin
which one is taken.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hwserver.profile import parse_login_email  # noqa: E402

# Shaped after the real /account markup.
ACCOUNT_HTML = """
<main>
  <div class="card">
    <h2>Login</h2>
    <p>Current login email: <strong>student@example.com</strong></p>
    <form><input type="password" name="new_password"></form>
  </div>
  <div class="card">
    <h2>Parent / Guardian Email</h2>
    <p>Currently on file: <strong>guardian@example.com</strong></p>
    <p>Your parent/guardian will receive a one-time verification link.</p>
  </div>
</main>
"""

GUARDIAN_FIRST_HTML = """
<main>
  <div class="card">
    <h2>Parent / Guardian Email</h2>
    <p>Currently on file: <strong>guardian@example.com</strong></p>
  </div>
  <div class="card">
    <p>Current login email: <strong>student@example.com</strong></p>
  </div>
</main>
"""


def test_picks_the_login_email():
    assert parse_login_email(ACCOUNT_HTML) == "student@example.com"


def test_never_returns_the_guardian_address():
    for html in (ACCOUNT_HTML, GUARDIAN_FIRST_HTML):
        assert parse_login_email(html) != "guardian@example.com"


def test_order_on_the_page_does_not_matter():
    assert parse_login_email(GUARDIAN_FIRST_HTML) == "student@example.com"


def test_missing_email_is_not_an_error():
    assert parse_login_email("<main><p>Nothing here.</p></main>") is None


def test_ignores_versioned_library_strings():
    """Asset URLs like bootstrap@5.2.3 look email-ish to a naive regex."""
    html = '<main><script src="https://cdn.example/bootstrap@5.2.3/x.js"></script></main>'
    assert parse_login_email(html) is None


def _run_all():
    for fn in (
        test_picks_the_login_email,
        test_never_returns_the_guardian_address,
        test_order_on_the_page_does_not_matter,
        test_missing_email_is_not_an_error,
        test_ignores_versioned_library_strings,
    ):
        fn()
        print(f"  ok  {fn.__name__}")
    print("\n5 tests passed.")


if __name__ == "__main__":
    _run_all()
