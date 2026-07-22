"""Per-user duel win/loss tracking for the /leaderboard command."""

import sqlite3

DB_PATH = "duelstats.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS duel_stats (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT NOT NULL,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            draws INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def _bump(conn, user_id, user_name, column):
    conn.execute(
        f"""
        INSERT INTO duel_stats (user_id, user_name, {column})
        VALUES (?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET
            {column} = {column} + 1,
            user_name = excluded.user_name
        """,
        (user_id, user_name),
    )


def record_result(user_id, user_name, result):
    """Records a single duel outcome for a human player. result in {'win','loss','draw'}."""
    column = {"win": "wins", "loss": "losses", "draw": "draws"}.get(result)
    if column is None:
        return
    conn = sqlite3.connect(DB_PATH)
    _bump(conn, user_id, user_name, column)
    conn.commit()
    conn.close()


def get_leaderboard(limit=10):
    """Returns top players ordered by wins (then win rate). Rows: (name, wins, losses, draws)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT user_name, wins, losses, draws FROM duel_stats "
        "ORDER BY wins DESC, (wins * 1.0 / (wins + losses + 1)) DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def get_user_stats(user_id):
    """Returns (wins, losses, draws) for a user, or (0, 0, 0) if they have no record."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT wins, losses, draws FROM duel_stats WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return row if row else (0, 0, 0)
