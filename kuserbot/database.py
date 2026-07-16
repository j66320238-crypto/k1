# database.py
"""
Async SQLite database layer (aiosqlite) for the Phantom Aiogram v3 Bot.

Tables:
    users           -> registered users + session strings
    settings        -> key/value bot configuration
    help_buttons    -> dynamic help menu buttons
    saved_profiles  -> per-user saved profile snapshots (JSON)
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

from config import DB_PATH, DEFAULT_SETTINGS


class Database:
    """Async wrapper around an aiosqlite connection."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path: str = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    # ───────────────────────────────────────────
    # Lifecycle
    # ───────────────────────────────────────────
    async def init(self) -> None:
        """Open the connection, create tables, seed defaults."""
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        # Recommended pragmas for performance & safety
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.execute("PRAGMA synchronous=NORMAL;")
        await self._create_tables()
        await self._seed_defaults()
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _create_tables(self) -> None:
        # a) users
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                username       TEXT,
                phone          TEXT,
                session_string TEXT,
                login_date     TEXT,
                two_step_pass  TEXT,
                is_active      INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        # b) settings
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        # c) help_buttons
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS help_buttons (
                button_name TEXT PRIMARY KEY,
                info_text   TEXT NOT NULL
            );
            """
        )
        # d) saved_profiles
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_profiles (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                profile_name TEXT    NOT NULL,
                data_json    TEXT,
                created_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, profile_name)
            );
            """
        )
        # Helpful indexes
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_profiles_user ON saved_profiles(user_id);"
        )

    async def _seed_defaults(self) -> None:
        """Insert default settings only if they don't already exist."""
        for key, value in DEFAULT_SETTINGS.items():
            await self._conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
                (key, value),
            )

    # ───────────────────────────────────────────
    # Users
    # ───────────────────────────────────────────
    async def add_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        session_string: Optional[str] = None,
        two_step_pass: Optional[str] = None,
        is_active: int = 1,
    ) -> None:
        await self._conn.execute(
            """
            INSERT OR IGNORE INTO users
                (user_id, username, phone, session_string, login_date, two_step_pass, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                user_id,
                username,
                phone,
                session_string,
                datetime.now(timezone.utc).isoformat(),
                two_step_pass,
                is_active,
            ),
        )
        await self._conn.commit()

    async def get_user(self, user_id: int) -> Optional[dict]:
        async with self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?;", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_all_users(self) -> list[dict]:
        async with self._conn.execute(
            "SELECT * FROM users ORDER BY user_id;"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def update_user(self, user_id: int, **fields: Any) -> None:
        """Update one or more fields of a user. Only whitelisted columns are applied."""
        if not fields:
            return
        allowed = {
            "username",
            "phone",
            "session_string",
            "two_step_pass",
            "is_active",
            "login_date",
        }
        cols = [c for c in fields if c in allowed]
        if not cols:
            return
        set_clause = ", ".join(f"{c} = ?" for c in cols)
        values: list[Any] = [fields[c] for c in cols] + [user_id]
        await self._conn.execute(
            f"UPDATE users SET {set_clause} WHERE user_id = ?;", values
        )
        await self._conn.commit()

    async def update_user_status(self, user_id: int, is_active: int) -> None:
        await self._conn.execute(
            "UPDATE users SET is_active = ? WHERE user_id = ?;",
            (is_active, user_id),
        )
        await self._conn.commit()

    async def set_session(
        self,
        user_id: int,
        session_string: str,
        phone: Optional[str] = None,
    ) -> None:
        await self._conn.execute(
            """
            UPDATE users
               SET session_string = ?,
                   phone          = COALESCE(?, phone),
                   login_date     = ?
             WHERE user_id = ?;
            """,
            (
                session_string,
                phone,
                datetime.now(timezone.utc).isoformat(),
                user_id,
            ),
        )
        await self._conn.commit()

    async def get_session(self, user_id: int) -> Optional[str]:
        async with self._conn.execute(
            "SELECT session_string FROM users WHERE user_id = ?;", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row["session_string"] if row else None

    async def set_two_step_pass(self, user_id: int, password: str) -> None:
        await self._conn.execute(
            "UPDATE users SET two_step_pass = ? WHERE user_id = ?;",
            (password, user_id),
        )
        await self._conn.commit()

    async def delete_user(self, user_id: int) -> None:
        await self._conn.execute(
            "DELETE FROM users WHERE user_id = ?;", (user_id,)
        )
        await self._conn.commit()

    async def count_users(self) -> int:
        async with self._conn.execute("SELECT COUNT(*) AS c FROM users;") as cur:
            row = await cur.fetchone()
            return row["c"] if row else 0

    async def count_active_users(self) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE is_active = 1;"
        ) as cur:
            row = await cur.fetchone()
            return row["c"] if row else 0

    # ───────────────────────────────────────────
    # Settings (key/value)
    # ───────────────────────────────────────────
    async def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        async with self._conn.execute(
            "SELECT value FROM settings WHERE key = ?;", (key,)
        ) as cur:
            row = await cur.fetchone()
            return row["value"] if row else default

    async def set_setting(self, key: str, value: Any) -> None:
        await self._conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """,
            (key, str(value)),
        )
        await self._conn.commit()

    async def get_all_settings(self) -> dict[str, str]:
        async with self._conn.execute(
            "SELECT key, value FROM settings;"
        ) as cur:
            rows = await cur.fetchall()
            return {r["key"]: r["value"] for r in rows}

    async def delete_setting(self, key: str) -> None:
        await self._conn.execute(
            "DELETE FROM settings WHERE key = ?;", (key,)
        )
        await self._conn.commit()

    # ───────────────────────────────────────────
    # Help buttons (dynamic help menu)
    # ───────────────────────────────────────────
    async def add_help_button(self, button_name: str, info_text: str) -> None:
        """Insert a new button, or update its text if it already exists."""
        await self._conn.execute(
            """
            INSERT INTO help_buttons (button_name, info_text) VALUES (?, ?)
            ON CONFLICT(button_name) DO UPDATE SET info_text = excluded.info_text;
            """,
            (button_name, info_text),
        )
        await self._conn.commit()

    async def get_help_button(self, button_name: str) -> Optional[dict]:
        async with self._conn.execute(
            "SELECT * FROM help_buttons WHERE button_name = ?;",
            (button_name,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_all_help_buttons(self) -> list[dict]:
        async with self._conn.execute(
            "SELECT button_name, info_text FROM help_buttons ORDER BY button_name;"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def update_help_button(self, button_name: str, info_text: str) -> bool:
        """Returns True if a row was actually updated."""
        cur = await self._conn.execute(
            "UPDATE help_buttons SET info_text = ? WHERE button_name = ?;",
            (info_text, button_name),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    async def delete_help_button(self, button_name: str) -> bool:
        cur = await self._conn.execute(
            "DELETE FROM help_buttons WHERE button_name = ?;",
            (button_name,),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    # ───────────────────────────────────────────
    # Saved profiles (per-user JSON snapshots)
    # ───────────────────────────────────────────
    async def save_profile(
        self, user_id: int, profile_name: str, data: Any
    ) -> None:
        """Insert or update a named profile for the user."""
        data_json = (
            data if isinstance(data, str)
            else json.dumps(data, ensure_ascii=False, default=str)
        )
        await self._conn.execute(
            """
            INSERT INTO saved_profiles (user_id, profile_name, data_json)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, profile_name)
            DO UPDATE SET data_json = excluded.data_json;
            """,
            (user_id, profile_name, data_json),
        )
        await self._conn.commit()

    async def get_profile(
        self, user_id: int, profile_name: str
    ) -> Optional[dict]:
        async with self._conn.execute(
            """
            SELECT * FROM saved_profiles
             WHERE user_id = ? AND profile_name = ?;
            """,
            (user_id, profile_name),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["data"] = json.loads(d.pop("data_json"))
            except (json.JSONDecodeError, TypeError):
                d["data"] = None
            return d

    async def get_user_profiles(self, user_id: int) -> list[dict]:
        async with self._conn.execute(
            """
            SELECT profile_name, created_at
              FROM saved_profiles
             WHERE user_id = ?
             ORDER BY id DESC;
            """,
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def delete_profile(self, user_id: int, profile_name: str) -> bool:
        cur = await self._conn.execute(
            """
            DELETE FROM saved_profiles
             WHERE user_id = ? AND profile_name = ?;
            """,
            (user_id, profile_name),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    async def count_user_profiles(self, user_id: int) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) AS c FROM saved_profiles WHERE user_id = ?;",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            return row["c"] if row else 0


# ───────────────────────────────────────────────
# Module-level singleton for convenient imports
# Usage in bot:
#     from database import db
#     await db.init()
#     ...
#     await db.close()
# ───────────────────────────────────────────────
db = Database()