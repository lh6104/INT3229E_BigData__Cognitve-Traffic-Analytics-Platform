"""SQLite transactions serialize duplicate webhook deliveries; keep database on persistent disk."""
import sqlite3
from pathlib import Path


class IncidentStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY, fingerprint TEXT, started_at TEXT, received_at REAL,
                state TEXT, diagnosis TEXT, requested_at REAL, resolved_at REAL, verification TEXT)''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def rows(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM incidents ORDER BY received_at')]
