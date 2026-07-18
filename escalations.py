"""
Simple escalation logging using SQLite.
For a production setup, swap this for Slack/email notifications or a real
ticketing system (Zendesk, Freshdesk, etc.) -- the log_escalation() function
is the only place that would need to change.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "escalations.db"


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            customer_email TEXT,
            reason TEXT NOT NULL,
            summary TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
        )
        """
    )
    conn.commit()
    conn.close()


def log_escalation(reason: str, summary: str, customer_email: str = "") -> dict:
    conn = _get_conn()
    created_at = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO escalations (created_at, customer_email, reason, summary, status) "
        "VALUES (?, ?, ?, ?, 'open')",
        (created_at, customer_email, reason, summary),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return {"id": row_id, "created_at": created_at}


def list_escalations(status: str | None = None) -> list[dict]:
    conn = _get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM escalations WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM escalations ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_escalation(escalation_id: int) -> None:
    conn = _get_conn()
    conn.execute("UPDATE escalations SET status = 'resolved' WHERE id = ?", (escalation_id,))
    conn.commit()
    conn.close()


init_db()
