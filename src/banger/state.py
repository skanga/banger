"""Durable project-local state, stored outside model conversation text."""

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path


class StateStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS messages (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                session TEXT NOT NULL REFERENCES sessions(id), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts (
                kind TEXT, key TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind, key));
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL,
                before BLOB, after BLOB, status TEXT NOT NULL DEFAULT 'applied');
        """)
        if "batch" not in {row[1] for row in self.db.execute("PRAGMA table_info(snapshots)")}:
            with self.db:
                self.db.execute("ALTER TABLE snapshots ADD COLUMN batch TEXT")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        with self._lock:
            self.db.close()

    def new_session(self, title: str) -> str:
        session = uuid.uuid4().hex
        with self._lock, self.db:
            self.db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (session, title, time.time()))
        return session

    def sessions(self) -> list[dict]:
        with self._lock:
            return [
                dict(r) for r in self.db.execute("SELECT * FROM sessions ORDER BY updated DESC")
            ]

    def append(self, session: str, message: dict):
        with self._lock, self.db:
            if not self.db.execute("SELECT 1 FROM sessions WHERE id=?", (session,)).fetchone():
                raise KeyError(session)
            self.db.execute(
                "INSERT INTO messages(session,payload) VALUES (?,?)", (session, json.dumps(message))
            )
            self.db.execute("UPDATE sessions SET updated=? WHERE id=?", (time.time(), session))

    def messages(self, session: str) -> list[dict]:
        with self._lock:
            return [
                json.loads(r[0])
                for r in self.db.execute(
                    "SELECT payload FROM messages WHERE session=? ORDER BY seq", (session,)
                )
            ]

    def set_memory(self, key: str, value: str):
        with self._lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO memory VALUES (?,?)", (key, value))

    def memories(self) -> dict[str, str]:
        with self._lock:
            return dict(self.db.execute("SELECT key,value FROM memory"))

    def forget_memory(self, key: str) -> bool:
        with self._lock, self.db:
            return self.db.execute("DELETE FROM memory WHERE key=?", (key,)).rowcount > 0

    def put_artifact(self, kind: str, key: str, value):
        with self._lock, self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO artifacts VALUES (?,?,?)", (kind, key, json.dumps(value))
            )

    def artifact(self, kind: str, key: str):
        with self._lock:
            row = self.db.execute(
                "SELECT payload FROM artifacts WHERE kind=? AND key=?", (kind, key)
            ).fetchone()
            return json.loads(row[0]) if row else None

    def snapshot(
        self, path: str, before: bytes | None, after: bytes | None, status: str = "applied"
    ) -> int:
        with self._lock, self.db:
            return self.db.execute(
                "INSERT INTO snapshots(path,before,after,status) VALUES (?,?,?,?)",
                (path, before, after, status),
            ).lastrowid

    def latest_snapshot(self) -> dict | None:
        with self._lock:
            row = self.db.execute(
                "SELECT * FROM snapshots WHERE status IN ('applied', 'incomplete') ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def finish_snapshot(self, snapshot: int, status: str):
        with self._lock, self.db:
            self.db.execute("UPDATE snapshots SET status=? WHERE id=?", (status, snapshot))

    def pending_snapshots(self) -> list[dict]:
        with self._lock:
            return [
                dict(row)
                for row in self.db.execute(
                    "SELECT * FROM snapshots WHERE status IN ('pending', 'pending-rollback') ORDER BY id"
                )
            ]

    def snapshot_many(self, changes):
        batch = uuid.uuid4().hex
        with self._lock, self.db:
            for path, before, after in changes:
                self.db.execute(
                    "INSERT INTO snapshots(path,before,after,status,batch) VALUES (?,?,?,'pending',?)",
                    (path, before, after, batch),
                )
        return self.snapshot_group(batch)

    def snapshot_group(self, batch):
        with self._lock:
            return [
                dict(row)
                for row in self.db.execute(
                    "SELECT * FROM snapshots WHERE batch=? ORDER BY id", (batch,)
                )
            ]

    def finish_group(self, batch, status):
        with self._lock, self.db:
            self.db.execute("UPDATE snapshots SET status=? WHERE batch=?", (status, batch))
