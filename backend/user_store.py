import os
import sqlite3
from pathlib import Path

import requests

from .settings import BASE_DIR


DEFAULT_SQLITE_PATH = BASE_DIR / "users.db"


class SQLiteUserStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("DATABASE_PATH") or DEFAULT_SQLITE_PATH)
        self._ensure_schema()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    active INTEGER NOT NULL DEFAULT 1
                )
                """
            )

    def get_user(self, username):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT username, password_hash, role, active FROM app_users WHERE username = ?",
                (username,),
            ).fetchone()
        return dict(row) if row else None

    def list_users(self):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT username, role, active FROM app_users ORDER BY username"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_user(self, username, password_hash, role, active=True):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_users (username, password_hash, role, active) VALUES (?, ?, ?, ?)",
                (username, password_hash, role, int(active)),
            )

    def set_active(self, username, active):
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE app_users SET active = ? WHERE username = ?",
                (int(active), username),
            )
        return cursor.rowcount > 0


class SupabaseUserStore:
    def __init__(self, url, service_role_key, table="app_users"):
        self.url = url.rstrip("/")
        self.table = table
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    def _endpoint(self):
        return f"{self.url}/rest/v1/{self.table}"

    def get_user(self, username):
        response = requests.get(
            self._endpoint(),
            headers=self.headers,
            params={"username": f"eq.{username}", "select": "username,password_hash,role,active"},
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if rows else None

    def list_users(self):
        response = requests.get(
            self._endpoint(),
            headers=self.headers,
            params={"select": "username,role,active", "order": "username.asc"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def create_user(self, username, password_hash, role, active=True):
        response = requests.post(
            self._endpoint(),
            headers=self.headers,
            json={
                "username": username,
                "password_hash": password_hash,
                "role": role,
                "active": bool(active),
            },
            timeout=20,
        )
        response.raise_for_status()

    def set_active(self, username, active):
        response = requests.patch(
            self._endpoint(),
            headers=self.headers,
            params={"username": f"eq.{username}"},
            json={"active": bool(active)},
            timeout=20,
        )
        response.raise_for_status()
        return True


def get_user_store():
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if supabase_url and supabase_key:
        return SupabaseUserStore(
            supabase_url,
            supabase_key,
            os.getenv("SUPABASE_USERS_TABLE", "app_users"),
        )
    return SQLiteUserStore()
