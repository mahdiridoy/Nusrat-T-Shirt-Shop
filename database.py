"""
Storage layer for ad-view counts.

Design note on the "reset at 00:00" requirement:
Instead of running a cron job to zero out counters (which can drift or fail
silently), each row is keyed by (user_id, date_key). date_key is the
calendar date in the configured timezone (e.g. "2026-07-08"). Once the
clock rolls past midnight, today_str() in bot.py naturally returns a new
date_key, so every user starts back at 0/1000 automatically -- no
scheduled job required, and no risk of a missed reset.
"""

import sqlite3
import threading

DB_PATH = "ads.db"
_lock = threading.Lock()


def init_db():
    with _lock, sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ad_views (
                user_id INTEGER NOT NULL,
                date_key TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, date_key)
            )
            """
        )
        conn.commit()


def get_count(user_id: int, date_key: str) -> int:
    with _lock, sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT count FROM ad_views WHERE user_id=? AND date_key=?",
            (user_id, date_key),
        ).fetchone()
        return row[0] if row else 0


def increment(user_id: int, date_key: str) -> int:
    """Atomically increments today's count for a user and returns the new value."""
    with _lock, sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO ad_views (user_id, date_key, count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, date_key)
            DO UPDATE SET count = count + 1
            """,
            (user_id, date_key),
        )
        conn.commit()
        row = conn.execute(
            "SELECT count FROM ad_views WHERE user_id=? AND date_key=?",
            (user_id, date_key),
        ).fetchone()
        return row[0]
