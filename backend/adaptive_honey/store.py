from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class EventStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state_json TEXT NOT NULL, profile_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS techniques (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, data_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS indicators (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, data_json TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, sequence);
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def save_session(self, session_id: str, state: dict, profile: dict, created_at: str):
        with self.lock, self._connect() as db:
            db.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?,?)", (session_id, json.dumps(state), json.dumps(profile), created_at))

    def add_event(self, session_id: str, event: dict, techniques: list[dict], indicators: list[dict]):
        with self.lock, self._connect() as db:
            db.execute("INSERT INTO events VALUES (?,?,?,?,?)", (event["id"], session_id, event["sequence"], json.dumps(event), event["timestamp"]))
            for technique in techniques:
                db.execute("INSERT INTO techniques VALUES (?,?,?)", (technique["id"], session_id, json.dumps(technique)))
            for indicator in indicators:
                db.execute("INSERT INTO indicators(session_id,data_json) VALUES (?,?)", (session_id, json.dumps(indicator)))

    def all_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT state_json,profile_json FROM sessions ORDER BY created_at DESC").fetchall()
        return [{"state": json.loads(s), "profile": json.loads(p)} for s, p in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT state_json,profile_json FROM sessions WHERE id=?", (session_id,)).fetchone()
        return {"state": json.loads(row[0]), "profile": json.loads(row[1])} if row else None

    def events(self, session_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT event_json FROM events WHERE session_id=? ORDER BY sequence", (session_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def techniques(self, session_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT data_json FROM techniques WHERE session_id=?", (session_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def indicators(self, session_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT data_json FROM indicators WHERE session_id=?", (session_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def counts(self) -> dict[str, int]:
        with self._connect() as db:
            return {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("sessions", "events", "techniques", "indicators")}

