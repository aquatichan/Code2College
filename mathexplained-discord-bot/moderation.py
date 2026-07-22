import sqlite3
import time
from collections import defaultdict, deque

DB_PATH = "moderation.db"

# Spam thresholds: N messages within WINDOW_SECONDS (across any channels) triggers a kick.
SPAM_MESSAGE_COUNT = 5
SPAM_WINDOW_SECONDS = 7


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS offenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            guild_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def log_offense(user_id, user_name, guild_id, reason, action):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO offenses (user_id, user_name, guild_id, reason, action, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, user_name, guild_id, reason, action, time.time()),
    )
    conn.commit()
    conn.close()


def get_offenses(user_id, guild_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT reason, action, created_at FROM offenses "
        "WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC",
        (user_id, guild_id),
    ).fetchall()
    conn.close()
    return rows


class SpamTracker:
    """Tracks recent message timestamps per user (across all channels) to detect flooding."""

    def __init__(self, message_count=SPAM_MESSAGE_COUNT, window_seconds=SPAM_WINDOW_SECONDS):
        self.message_count = message_count
        self.window_seconds = window_seconds
        self._history = defaultdict(deque)

    def record_and_check(self, user_id) -> bool:
        """Records a message for the user; returns True if they've tripped the spam threshold."""
        now = time.time()
        history = self._history[user_id]
        history.append(now)

        while history and now - history[0] > self.window_seconds:
            history.popleft()

        if len(history) >= self.message_count:
            history.clear()
            return True
        return False
