"""
SessionStore — SQLite (stdlib sqlite3, WAL mode) theo đúng schema PLAN.md 4.4.

Vì sao 1 connection + 1 Lock thay vì connection pool: quy mô vài user, mọi
truy vấn đều < 1ms — lock toàn cục đơn giản và đúng, pool là over-engineering.
check_same_thread=False vì store được gọi từ cả event loop (async side) lẫn
agent thread (runner).
"""

from __future__ import annotations
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    invite_token TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL UNIQUE REFERENCES users(id),
    device_token TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    last_seen    TEXT,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id                      TEXT PRIMARY KEY,
    session_id              TEXT NOT NULL,
    status                  TEXT NOT NULL,
    total_prompt_tokens     INTEGER DEFAULT 0,
    total_completion_tokens INTEGER DEFAULT 0,
    created_at              TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def _execute(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    # --- users ---

    def create_user(self, name: str) -> dict:
        user = {
            "id": str(uuid.uuid4()),
            "name": name,
            "invite_token": secrets.token_urlsafe(24),
            "created_at": _now(),
        }
        self._execute(
            "INSERT INTO users (id, name, invite_token, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], user["name"], user["invite_token"], user["created_at"]),
        )
        return user

    def list_users(self) -> list[dict]:
        return self._query("SELECT * FROM users ORDER BY created_at")

    def get_user_by_invite(self, token: str) -> dict | None:
        rows = self._query("SELECT * FROM users WHERE invite_token = ?", (token,))
        return rows[0] if rows else None

    def delete_user(self, user_id: str) -> None:
        """Thu hồi user: xóa sạch user + device + sessions/messages/runs.
        Invite link và device token lập tức vô hiệu ở lần auth kế tiếp."""
        self._execute(
            "DELETE FROM runs WHERE session_id IN (SELECT id FROM sessions WHERE user_id = ?)",
            (user_id,),
        )
        self._execute(
            "DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE user_id = ?)",
            (user_id,),
        )
        self._execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        self._execute("DELETE FROM devices WHERE user_id = ?", (user_id,))
        self._execute("DELETE FROM users WHERE id = ?", (user_id,))

    # --- devices (1 user 1 device — pair mới GHI ĐÈ device cũ, token cũ vô hiệu) ---

    def upsert_device(self, user_id: str, name: str) -> str:
        device_token = secrets.token_urlsafe(24)
        self._execute("DELETE FROM devices WHERE user_id = ?", (user_id,))
        self._execute(
            "INSERT INTO devices (id, user_id, device_token, name, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, device_token, name, _now()),
        )
        return device_token

    def get_device(self, user_id: str) -> dict | None:
        rows = self._query("SELECT * FROM devices WHERE user_id = ?", (user_id,))
        return rows[0] if rows else None

    def get_user_by_device_token(self, token: str) -> dict | None:
        rows = self._query(
            "SELECT u.*, d.name AS device_name FROM devices d JOIN users u ON u.id = d.user_id "
            "WHERE d.device_token = ?",
            (token,),
        )
        return rows[0] if rows else None

    def touch_device(self, user_id: str) -> None:
        self._execute("UPDATE devices SET last_seen = ? WHERE user_id = ?", (_now(), user_id))

    # --- sessions / messages ---

    def create_session(self, user_id: str, title: str) -> dict:
        session = {"id": str(uuid.uuid4()), "user_id": user_id, "title": title[:60], "created_at": _now()}
        self._execute(
            "INSERT INTO sessions (id, user_id, title, created_at) VALUES (?, ?, ?, ?)",
            (session["id"], session["user_id"], session["title"], session["created_at"]),
        )
        return session

    def list_sessions(self, user_id: str) -> list[dict]:
        return self._query(
            "SELECT id, title, created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )

    def get_session(self, session_id: str) -> dict | None:
        rows = self._query("SELECT * FROM sessions WHERE id = ?", (session_id,))
        return rows[0] if rows else None

    def delete_session(self, session_id: str) -> None:
        self._execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        self._execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def get_messages(self, session_id: str) -> list[dict]:
        return self._query(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        )

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self._execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )

    # --- runs ---

    def record_run(
        self, run_id: str, session_id: str, status: str, prompt_tokens: int, completion_tokens: int
    ) -> None:
        self._execute(
            "INSERT INTO runs (id, session_id, status, total_prompt_tokens, total_completion_tokens, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, session_id, status, prompt_tokens, completion_tokens, _now()),
        )
