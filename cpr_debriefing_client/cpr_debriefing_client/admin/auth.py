"""
admin/auth.py — Multi-Admin Authentication with Flask Sessions
==============================================================
Uses SQLite (built-in) for persistent user storage.
Uses werkzeug password hashing (bundled with Flask).
Uses Flask sessions for login state management.

Roles
-----
  super_admin  Can manage other admins + toggle all flags
  admin        Can toggle feature flags only

First-Run Setup
---------------
On first run, if no admins exist, a default super_admin is created:
  username: value of env var ADMIN_USERNAME  (default: "cpr_admin")
  password: value of env var ADMIN_PASSWORD  (default: auto-generated, printed once)

Session Configuration
---------------------
  SESSION_LIFETIME_HOURS  env var, default 4
  Flask SECRET_KEY        env var, required for session signing
"""

from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Optional

from flask import session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_DB_PATH = _HERE / "admins.db"

SESSION_LIFETIME_HOURS = int(os.getenv("SESSION_LIFETIME_HOURS", "4"))
_SESSION_KEY_ID       = "admin_id"
_SESSION_KEY_USERNAME = "admin_username"
_SESSION_KEY_ROLE     = "admin_role"
_SESSION_KEY_AT       = "logged_in_at"


# ──────────────────────────────────────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    """Create tables and seed the first super_admin if none exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    UNIQUE NOT NULL,
                password_hash TEXT  NOT NULL,
                role        TEXT    NOT NULL DEFAULT 'admin',
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_by  TEXT,
                created_at  TEXT    NOT NULL,
                last_login  TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token       TEXT PRIMARY KEY,
                admin_id    INTEGER NOT NULL,
                created_at  TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                FOREIGN KEY (admin_id) REFERENCES admins(id)
            )
        """)
        conn.commit()

    # Seed first super_admin
    with _get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
        if count == 0:
            username = os.getenv("ADMIN_USERNAME", "cpr_admin")
            password = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
            pw_hash  = generate_password_hash(password)
            now      = _now_iso()
            conn.execute(
                "INSERT INTO admins (username, password_hash, role, created_by, created_at) "
                "VALUES (?, ?, 'super_admin', 'system', ?)",
                (username, pw_hash, now),
            )
            conn.commit()
            if not os.getenv("ADMIN_PASSWORD"):
                print("=" * 60)
                print("  CPR DEBRIEFING -- ADMIN ACCOUNT CREATED")
                print(f"  Username : {username}")
                print(f"  Password : {password}")
                print("  [!] Save this password -- it will not be shown again.")
                print("=" * 60)
            logger.info(f"[AdminAuth] Default super_admin '{username}' created.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# AdminAuth
# ──────────────────────────────────────────────────────────────────────────────

class AdminAuth:
    """
    Multi-admin authentication manager.

    Usage
    -----
    auth = AdminAuth()

    # Login
    ok, msg, admin_info = auth.login("cpr_admin", "password")

    # Check current session
    admin = auth.current_admin()   # None if not logged in

    # Logout
    auth.logout()

    # User management (super_admin only)
    auth.create_admin("newuser", "pass", "admin", created_by="cpr_admin")
    auth.delete_admin(admin_id=2, by_username="cpr_admin")
    auth.list_admins()
    auth.change_password(admin_id, new_password, by_username)
    auth.set_active(admin_id, active, by_username)
    """

    def __init__(self):
        _init_db()

    # ── Login / Logout ────────────────────────────────────────────────────────

    def login(
        self, username: str, password: str
    ) -> tuple[bool, str, Optional[dict]]:
        """
        Verify credentials and start a Flask session.

        Returns:
            (success, message, admin_info_dict | None)
        """
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM admins WHERE username = ? AND is_active = 1",
                (username,),
            ).fetchone()

        if not row:
            logger.warning(f"[AdminAuth] Login failed: unknown user '{username}'")
            return False, "Invalid username or password.", None

        if not check_password_hash(row["password_hash"], password):
            logger.warning(f"[AdminAuth] Login failed: wrong password for '{username}'")
            return False, "Invalid username or password.", None

        # Update last_login
        now = _now_iso()
        with _get_conn() as conn:
            conn.execute(
                "UPDATE admins SET last_login = ? WHERE id = ?",
                (now, row["id"]),
            )
            conn.commit()

        # Write Flask session
        session.permanent = True
        session[_SESSION_KEY_ID]       = row["id"]
        session[_SESSION_KEY_USERNAME] = row["username"]
        session[_SESSION_KEY_ROLE]     = row["role"]
        session[_SESSION_KEY_AT]       = now

        admin_info = {
            "id":         row["id"],
            "username":   row["username"],
            "role":       row["role"],
            "last_login": row["last_login"],
        }
        logger.info(f"[AdminAuth] Login success: {username} ({row['role']})")
        return True, "Login successful.", admin_info

    def logout(self) -> None:
        """Clear the current admin session."""
        username = session.get(_SESSION_KEY_USERNAME, "unknown")
        session.clear()
        logger.info(f"[AdminAuth] Logged out: {username}")

    # ── Session check ─────────────────────────────────────────────────────────

    def current_admin(self) -> Optional[dict]:
        """
        Return current admin info from Flask session, or None if not logged in
        or session expired.
        """
        if _SESSION_KEY_ID not in session:
            return None

        logged_in_at = session.get(_SESSION_KEY_AT)
        if logged_in_at:
            try:
                login_time = datetime.fromisoformat(logged_in_at)
                if datetime.now(timezone.utc) - login_time > timedelta(hours=SESSION_LIFETIME_HOURS):
                    session.clear()
                    return None
            except Exception:
                session.clear()
                return None

        return {
            "id":       session[_SESSION_KEY_ID],
            "username": session[_SESSION_KEY_USERNAME],
            "role":     session[_SESSION_KEY_ROLE],
        }

    def is_super_admin(self) -> bool:
        admin = self.current_admin()
        return admin is not None and admin["role"] == "super_admin"

    # ── User management ───────────────────────────────────────────────────────

    def create_admin(
        self,
        username: str,
        password: str,
        role: str = "admin",
        created_by: str = "system",
    ) -> tuple[bool, str]:
        """Create a new admin. Role must be 'admin' or 'super_admin'."""
        if role not in ("admin", "super_admin"):
            return False, "Role must be 'admin' or 'super_admin'."
        if len(username) < 3:
            return False, "Username must be at least 3 characters."
        if len(password) < 8:
            return False, "Password must be at least 8 characters."
        try:
            with _get_conn() as conn:
                conn.execute(
                    "INSERT INTO admins (username, password_hash, role, created_by, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (username, generate_password_hash(password), role, created_by, _now_iso()),
                )
                conn.commit()
            logger.info(f"[AdminAuth] Admin '{username}' ({role}) created by {created_by}")
            return True, f"Admin '{username}' created successfully."
        except sqlite3.IntegrityError:
            return False, f"Username '{username}' already exists."

    def delete_admin(self, admin_id: int, by_username: str) -> tuple[bool, str]:
        """Soft-delete (deactivate) an admin. Cannot delete yourself."""
        current = self.current_admin()
        if current and current["id"] == admin_id:
            return False, "You cannot delete your own account."
        with _get_conn() as conn:
            row = conn.execute("SELECT username FROM admins WHERE id = ?", (admin_id,)).fetchone()
            if not row:
                return False, "Admin not found."
            conn.execute("UPDATE admins SET is_active = 0 WHERE id = ?", (admin_id,))
            conn.commit()
        logger.info(f"[AdminAuth] Admin #{admin_id} deactivated by {by_username}")
        return True, f"Admin '{row['username']}' deactivated."

    def change_password(
        self, admin_id: int, new_password: str, by_username: str
    ) -> tuple[bool, str]:
        if len(new_password) < 8:
            return False, "Password must be at least 8 characters."
        with _get_conn() as conn:
            row = conn.execute("SELECT username FROM admins WHERE id = ?", (admin_id,)).fetchone()
            if not row:
                return False, "Admin not found."
            conn.execute(
                "UPDATE admins SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_password), admin_id),
            )
            conn.commit()
        logger.info(f"[AdminAuth] Password changed for #{admin_id} by {by_username}")
        return True, f"Password updated for '{row['username']}'."

    def set_active(self, admin_id: int, active: bool, by_username: str) -> tuple[bool, str]:
        current = self.current_admin()
        if current and current["id"] == admin_id and not active:
            return False, "You cannot deactivate your own account."
        with _get_conn() as conn:
            conn.execute(
                "UPDATE admins SET is_active = ? WHERE id = ?",
                (1 if active else 0, admin_id),
            )
            conn.commit()
        status = "activated" if active else "deactivated"
        logger.info(f"[AdminAuth] Admin #{admin_id} {status} by {by_username}")
        return True, f"Admin #{admin_id} {status}."

    def list_admins(self) -> list[dict]:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT id, username, role, is_active, created_by, created_at, last_login "
                "FROM admins ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_admin_by_id(self, admin_id: int) -> Optional[dict]:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT id, username, role, is_active, created_by, created_at, last_login "
                "FROM admins WHERE id = ?",
                (admin_id,),
            ).fetchone()
        return dict(row) if row else None


# ──────────────────────────────────────────────────────────────────────────────
# Flask route decorators
# ──────────────────────────────────────────────────────────────────────────────

_auth_singleton: Optional[AdminAuth] = None


def _get_auth() -> AdminAuth:
    global _auth_singleton
    if _auth_singleton is None:
        _auth_singleton = AdminAuth()
    return _auth_singleton


def require_admin(f):
    """Route decorator: require any logged-in admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        admin = _get_auth().current_admin()
        if not admin:
            return jsonify({"error": "Admin login required."}), 401
        return f(*args, **kwargs)
    return decorated


def require_super_admin(f):
    """Route decorator: require super_admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        admin = _get_auth().current_admin()
        if not admin:
            return jsonify({"error": "Admin login required."}), 401
        if admin["role"] != "super_admin":
            return jsonify({"error": "Super-admin privileges required."}), 403
        return f(*args, **kwargs)
    return decorated
