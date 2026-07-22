import sqlite3
import time
import random

DB_PATH = "problems.db"

# Categories stored in the `problems` table's `category` column.
CATEGORY_ALGEBRA = "ALGEBRA"
CATEGORY_GEOMETRY = "GEOMETRY"
CATEGORY_COMBINATORICS = "COMBINATORICS"
CATEGORY_NUMBERTHEORY = "NUMBERTHEORY"
CATEGORY_ADVANCED = "ADVANCED"

CATEGORIES = (CATEGORY_ALGEBRA, CATEGORY_GEOMETRY, CATEGORY_COMBINATORICS, CATEGORY_NUMBERTHEORY, CATEGORY_ADVANCED,)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            prompt TEXT NOT NULL,
            answer TEXT,
            difficulty INTEGER,
            latex INTEGER NOT NULL DEFAULT 0,
            image_url TEXT,
            submitted_by_id INTEGER,
            submitted_by_name TEXT,
            approved INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        )
        """
    )
    # Lightweight migration so existing databases pick up new columns without being dropped.
    _add_column_if_missing(conn, "difficulty", "INTEGER")
    _add_column_if_missing(conn, "latex", "INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()


def _add_column_if_missing(conn, name, decl):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(problems)").fetchall()}
    if name not in existing:
        conn.execute(f"ALTER TABLE problems ADD COLUMN {name} {decl}")


def submit_problem(category, prompt, answer, difficulty, latex, image_url,
                   submitted_by_id, submitted_by_name):
    """Inserts a problem in a pending (unapproved) state. Returns the new row id."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        """
        INSERT INTO problems
            (category, prompt, answer, difficulty, latex, image_url,
             submitted_by_id, submitted_by_name, approved, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (category, prompt, answer, difficulty, int(bool(latex)), image_url,
         submitted_by_id, submitted_by_name, time.time()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_random_problem(category):
    """Returns one random *approved* row for the given category, or None if none exist."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, prompt, answer, difficulty, latex, image_url, submitted_by_name "
        "FROM problems WHERE category = ? AND approved = 1",
        (category,),
    ).fetchall()
    conn.close()
    if not rows:
        return None
    return random.choice(rows)


def get_duel_problems(count, category=None, min_difficulty=None, max_difficulty=None):
    """Returns up to `count` random *approved* problems for a duel.

    Optionally filters by category and an inclusive difficulty range. Problems
    without a difficulty are only included when no difficulty range is requested.
    Returns a list of rows: (id, category, prompt, answer, difficulty, latex, image_url).
    """
    clauses = ["approved = 1"]
    params = []
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    if min_difficulty is not None:
        clauses.append("difficulty >= ?")
        params.append(min_difficulty)
    if max_difficulty is not None:
        clauses.append("difficulty <= ?")
        params.append(max_difficulty)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, category, prompt, answer, difficulty, latex, image_url "
        "FROM problems WHERE " + " AND ".join(clauses),
        params,
    ).fetchall()
    conn.close()

    random.shuffle(rows)
    return rows[:count]


def get_pending_submissions(limit=25):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, category, prompt, answer, difficulty, latex, image_url, "
        "submitted_by_name, created_at "
        "FROM problems WHERE approved = 0 ORDER BY created_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


# Full column tuple used by single-problem and browse lookups.
_FULL_COLUMNS = ("id, category, prompt, answer, difficulty, latex, image_url, "
                 "submitted_by_name, approved, created_at")


def get_problem(problem_id):
    """Returns one problem row by id regardless of approval state, or None.

    Row shape: (id, category, prompt, answer, difficulty, latex, image_url,
                submitted_by_name, approved, created_at).
    """
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        f"SELECT {_FULL_COLUMNS} FROM problems WHERE id = ?",
        (problem_id,),
    ).fetchone()
    conn.close()
    return row


def get_all_problems(category=None, approved=None):
    """Returns every problem (newest first) for moderator browsing.

    Optionally filters by category and/or approval state (True/False).
    Same row shape as get_problem.
    """
    clauses = []
    params = []
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    if approved is not None:
        clauses.append("approved = ?")
        params.append(1 if approved else 0)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        f"SELECT {_FULL_COLUMNS} FROM problems{where} ORDER BY id DESC",
        params,
    ).fetchall()
    conn.close()
    return rows


def delete_problem(problem_id):
    """Hard-deletes any problem (approved or not) by id. Returns True if a row was removed."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("DELETE FROM problems WHERE id = ?", (problem_id,))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0


def get_stats():
    """Returns aggregate stats for the /stats command.

    {
      "total_approved": int, "total_pending": int,
      "by_category": {category_code: approved_count, ...},
      "avg_difficulty": float | None,
    }
    """
    conn = sqlite3.connect(DB_PATH)
    total_approved = conn.execute(
        "SELECT COUNT(*) FROM problems WHERE approved = 1"
    ).fetchone()[0]
    total_pending = conn.execute(
        "SELECT COUNT(*) FROM problems WHERE approved = 0"
    ).fetchone()[0]
    by_category = dict(conn.execute(
        "SELECT category, COUNT(*) FROM problems WHERE approved = 1 GROUP BY category"
    ).fetchall())
    avg_difficulty = conn.execute(
        "SELECT AVG(difficulty) FROM problems WHERE approved = 1 AND difficulty IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    return {
        "total_approved": total_approved,
        "total_pending": total_pending,
        "by_category": by_category,
        "avg_difficulty": avg_difficulty,
    }


def approve_submission(problem_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "UPDATE problems SET approved = 1 WHERE id = ?",
        (problem_id,),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0


def reject_submission(problem_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "DELETE FROM problems WHERE id = ? AND approved = 0",
        (problem_id,),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0


# Fields a moderator is allowed to edit via /reviewproblem and /editproblem.
_EDITABLE_FIELDS = ("category", "prompt", "answer", "difficulty", "latex", "image_url")


def update_problem(problem_id, **fields):
    """Updates the given editable fields on a problem. Returns True if a row changed."""
    updates = {k: v for k, v in fields.items() if k in _EDITABLE_FIELDS and v is not None}
    if not updates:
        return False
    columns = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [problem_id]
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(f"UPDATE problems SET {columns} WHERE id = ?", values)
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0
