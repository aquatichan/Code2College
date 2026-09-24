"""Account identity: the Hirewheel login email decides whose history you see.

Enrollment always creates a fresh placeholder account, because the server can't
know who you are until you sign in to Hirewheel. These tests pin down how that
placeholder is resolved — and in particular that a *different* person signing in
on the same phone never inherits the previous person's scans.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hwserver.crypto import generate_key  # noqa: E402

os.environ["HW_SECRET_KEY"] = generate_key()

from hwserver import config, db  # noqa: E402


def _fresh(td: str):
    config.DB_PATH = Path(td) / "test.db"
    return db.connect(config.DB_PATH)


def _account_with_history(conn, email: str) -> tuple[str, str]:
    """A signed-in user with one device and one finished scan."""
    user_id = db.create_user(conn, "student")
    db.set_email(conn, user_id, email)
    device_id, _ = db.register_device(conn, user_id)
    scan = db.start_scan(conn, user_id)
    db.finish_scan(conn, scan, status="ok", change_count=2)
    return user_id, device_id


def _placeholder(conn) -> tuple[str, str]:
    """What /enroll creates: an account nobody has signed into yet."""
    user_id = db.create_user(conn, "student")
    device_id, _ = db.register_device(conn, user_id)
    return user_id, device_id


def test_signing_back_in_recovers_previous_scans():
    with tempfile.TemporaryDirectory() as td:
        conn = _fresh(td)
        original, _ = _account_with_history(conn, "aaron@example.com")
        placeholder, new_device = _placeholder(conn)

        owner = db.claim_account(conn, placeholder, new_device, "aaron@example.com")

        assert owner == original
        assert db.get_user(conn, placeholder) is None, "empty placeholder should be discarded"
        moved = conn.execute("SELECT user_id FROM devices WHERE id = ?", (new_device,)).fetchone()
        assert moved["user_id"] == original
        assert len(db.list_scans(conn, original)) == 1, "history must survive"


def test_email_match_ignores_case():
    with tempfile.TemporaryDirectory() as td:
        conn = _fresh(td)
        original, _ = _account_with_history(conn, "Aaron@Example.com")
        placeholder, device = _placeholder(conn)
        assert db.claim_account(conn, placeholder, device, "aaron@example.com") == original


def test_first_ever_sign_in_claims_the_placeholder():
    with tempfile.TemporaryDirectory() as td:
        conn = _fresh(td)
        placeholder, device = _placeholder(conn)
        assert db.claim_account(conn, placeholder, device, "new@example.com") == placeholder
        assert db.get_user(conn, placeholder) is not None


def test_re_signing_in_after_session_expiry_keeps_the_same_account():
    with tempfile.TemporaryDirectory() as td:
        conn = _fresh(td)
        user_id, device = _account_with_history(conn, "aaron@example.com")
        assert db.claim_account(conn, user_id, device, "aaron@example.com") == user_id


def test_a_different_person_on_the_same_phone_gets_their_own_account():
    """The privacy-critical case: friend B signs in on A's phone."""
    with tempfile.TemporaryDirectory() as td:
        conn = _fresh(td)
        user_a, device = _account_with_history(conn, "a@example.com")

        owner = db.claim_account(conn, user_a, device, "b@example.com")

        assert owner != user_a, "B must not be merged into A's history"
        assert db.list_scans(conn, owner) == [], "B starts with nothing of A's"
        assert len(db.list_scans(conn, user_a)) == 1, "A's history is left intact"
        assert db.get_user(conn, user_a) is not None, "A's account is not deleted"
        moved = conn.execute("SELECT user_id FROM devices WHERE id = ?", (device,)).fetchone()
        assert moved["user_id"] == owner


def test_only_the_signing_in_device_moves():
    with tempfile.TemporaryDirectory() as td:
        conn = _fresh(td)
        original, _ = _account_with_history(conn, "aaron@example.com")
        other_user, other_device = _account_with_history(conn, "someone@example.com")
        placeholder, device = _placeholder(conn)

        db.claim_account(conn, placeholder, device, "aaron@example.com")

        untouched = conn.execute("SELECT user_id FROM devices WHERE id = ?", (other_device,)).fetchone()
        assert untouched["user_id"] == other_user


def test_login_session_follows_the_device():
    """The app polls its login session after the device has moved accounts."""
    with tempfile.TemporaryDirectory() as td:
        conn = _fresh(td)
        original, _ = _account_with_history(conn, "aaron@example.com")
        placeholder, device = _placeholder(conn)
        sid = db.create_login_session(conn, placeholder, "", 600, device_id=device)

        db.claim_account(conn, placeholder, device, "aaron@example.com")

        row = db.get_login_session(conn, sid)
        assert row is not None, "session vanished with the placeholder"
        assert row["user_id"] == original


def test_unreadable_email_leaves_the_account_alone():
    with tempfile.TemporaryDirectory() as td:
        conn = _fresh(td)
        placeholder, device = _placeholder(conn)
        assert db.claim_account(conn, placeholder, device, None) == placeholder


def _run_all():
    for fn in (
        test_signing_back_in_recovers_previous_scans,
        test_email_match_ignores_case,
        test_first_ever_sign_in_claims_the_placeholder,
        test_re_signing_in_after_session_expiry_keeps_the_same_account,
        test_a_different_person_on_the_same_phone_gets_their_own_account,
        test_only_the_signing_in_device_moves,
        test_login_session_follows_the_device,
        test_unreadable_email_leaves_the_account_alone,
    ):
        fn()
        print(f"  ok  {fn.__name__}")
    print("\n8 tests passed.")


if __name__ == "__main__":
    _run_all()
