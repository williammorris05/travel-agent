"""Atomic lifetime attempt allowances. Stores counts only, never travel data or keys."""
import sqlite3
from contextlib import closing
from pathlib import Path


class UsageLedger:
    def __init__(self, path: Path):
        self.path = path

    def reserve(self, bucket: str, limit: int) -> bool:
        if bucket not in ('model', 'hotels') or limit <= 0:
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('CREATE TABLE IF NOT EXISTS usage (bucket TEXT PRIMARY KEY, attempts INTEGER NOT NULL CHECK(attempts >= 0))')
                db.execute('INSERT OR IGNORE INTO usage VALUES (?, 0)', (bucket,))
                cursor = db.execute('UPDATE usage SET attempts = attempts + 1 WHERE bucket = ? AND attempts < ?', (bucket, limit))
                return cursor.rowcount == 1
        except (OSError, sqlite3.Error):
            return False  # Fail closed; an unavailable ledger never enables calls.

    def used(self, bucket: str) -> int | None:
        try:
            if not self.path.exists():
                return 0
            with closing(sqlite3.connect(self.path, timeout=5)) as db:
                row = db.execute('SELECT attempts FROM usage WHERE bucket = ?', (bucket,)).fetchone()
                return row[0] if row else 0
        except (OSError, sqlite3.Error):
            return None
