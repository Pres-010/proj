from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

DATABASE_PATH = Path("database/data.db")

DEFAULT_SETTINGS = {
    "language": "English",
    "theme": "Light",
    "use_google": "No",
}


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'basic',
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            UNIQUE(user_id, key),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate_user(email: str, password: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    if hash_password(password) != row["password_hash"]:
        return None
    return dict(row)


def get_user_by_email(email: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def register_user(email: str, password: str, plan: str) -> dict:
    password_hash = hash_password(password)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (email, password_hash, plan, created_at) VALUES (?, ?, ?, ?)",
        (email.lower(), password_hash, plan, datetime.utcnow().isoformat()),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    for key, value in DEFAULT_SETTINGS.items():
        set_user_setting(user_id, key, value)

    return {
        "id": user_id,
        "email": email.lower(),
        "plan": plan,
        "created_at": datetime.utcnow().isoformat(),
    }


def get_user_settings(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    settings = {row["key"]: row["value"] for row in rows}
    for key, default_value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, default_value)
    return settings


def set_user_setting(user_id: int, key: str, value: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
        (user_id, key, value),
    )
    conn.commit()
    conn.close()


def append_history(user_id: int, role: str, message: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO history (user_id, role, message, created_at) VALUES (?, ?, ?, ?)",
        (user_id, role, message, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_history(user_id: int) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, role, message, created_at FROM history WHERE user_id = ? ORDER BY id",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_history_item(user_id: int, history_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM history WHERE user_id = ? AND id = ?", (user_id, history_id)
    )
    conn.commit()
    conn.close()


def clear_history(user_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def update_user_plan(user_id: int, plan: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
    conn.commit()
    conn.close()
