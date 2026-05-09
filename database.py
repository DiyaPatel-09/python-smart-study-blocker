"""
database.py - SQLite database handler for Smart Study Distraction Blocker
"""

import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "study_data.db")


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        """Create required tables if they don't exist."""
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS blocked_apps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                completed INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    # ── Blocked Apps ──────────────────────────────────────────────────────────

    def add_blocked_app(self, app_name: str) -> bool:
        """Add an app to the blocked list. Returns False if already exists."""
        try:
            self.conn.execute(
                "INSERT INTO blocked_apps (app_name) VALUES (?)",
                (app_name.lower().strip(),)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_blocked_app(self, app_name: str):
        """Remove an app from the blocked list."""
        self.conn.execute(
            "DELETE FROM blocked_apps WHERE app_name = ?",
            (app_name.lower().strip(),)
        )
        self.conn.commit()

    def get_blocked_apps(self) -> list[str]:
        """Return all blocked app names."""
        cursor = self.conn.execute("SELECT app_name FROM blocked_apps ORDER BY app_name")
        return [row[0] for row in cursor.fetchall()]

    # ── Sessions ──────────────────────────────────────────────────────────────

    def log_session(self, duration_minutes: int, completed: bool = True) -> int:
        """Insert a session record and return its id."""
        cursor = self.conn.execute(
            "INSERT INTO sessions (date, duration_minutes, completed) VALUES (?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d"), duration_minutes, int(completed))
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_sessions(self) -> list[dict]:
        """Return all session records as dicts."""
        cursor = self.conn.execute(
            "SELECT id, date, duration_minutes, completed FROM sessions ORDER BY id DESC"
        )
        cols = ["id", "date", "duration_minutes", "completed"]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_daily_totals(self) -> list[tuple]:
        """Return (date, total_minutes) grouped by date for the last 30 days."""
        cursor = self.conn.execute("""
            SELECT date, SUM(duration_minutes)
            FROM sessions
            WHERE completed = 1
            GROUP BY date
            ORDER BY date DESC
            LIMIT 30
        """)
        return cursor.fetchall()

    def get_weekly_totals(self) -> list[tuple]:
        """Return (week_label, total_minutes) for the last 8 weeks."""
        cursor = self.conn.execute("""
            SELECT strftime('%Y-W%W', date) AS week, SUM(duration_minutes)
            FROM sessions
            WHERE completed = 1
            GROUP BY week
            ORDER BY week DESC
            LIMIT 8
        """)
        return cursor.fetchall()

    def get_total_study_time(self) -> int:
        """Return total completed study minutes."""
        cursor = self.conn.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM sessions WHERE completed = 1"
        )
        return cursor.fetchone()[0]

    def close(self):
        self.conn.close()
