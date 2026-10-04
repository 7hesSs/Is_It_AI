"""
Auth logic - deliberately dependency-free:
  - Password hashing via hashlib.pbkdf2_hmac (stdlib) instead of bcrypt/argon2.
    100,000 iterations is a reasonable modern floor for PBKDF2-SHA256.
  - Sessions are opaque random tokens (secrets.token_urlsafe) stored in SQLite
    with an expiry, rather than JWTs - simpler to reason about and revoke
    (logout just deletes the row), at the cost of a DB lookup per request.
    Fine at this scale; a JWT would avoid the DB hit if this ever needs to
    scale to heavy traffic.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from app.db import get_connection

SESSION_TTL_HOURS = 24 * 7  # sessions last a week
PASSWORD_RESET_TTL_MINUTES = 30
PBKDF2_ITERATIONS = 100_000


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    ).hex()


def create_user(email: str, password: str) -> int:
    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (email.lower().strip(), password_hash, salt.hex(), now),
        )
        conn.commit()
        return cursor.lastrowid


def get_user_by_email(email: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None


def verify_password(email: str, password: str) -> dict | None:
    user = get_user_by_email(email)
    if not user:
        return None

    salt = bytes.fromhex(user["salt"])
    expected = _hash_password(password, salt)

    # Constant-time comparison - avoids leaking timing information about
    # how much of the hash matched.
    if hmac.compare_digest(expected, user["password_hash"]):
        return user
    return None


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=SESSION_TTL_HOURS)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now.isoformat(), expires.isoformat()),
        )
        conn.commit()
    return token


def get_user_by_token(token: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ? AND sessions.expires_at > ?
            """,
            (token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
        return dict(row) if row else None


def delete_session(token: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def create_password_reset(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO password_resets (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now.isoformat(), expires.isoformat()),
        )
        conn.commit()
    return token


def get_user_id_by_reset_token(token: str) -> int | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id FROM password_resets WHERE token = ? AND expires_at > ?",
            (token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
        return row["user_id"] if row else None


def consume_reset_token(token: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM password_resets WHERE token = ?", (token,))
        conn.commit()


def update_password(user_id: int, new_password: str) -> None:
    salt = secrets.token_bytes(16)
    password_hash = _hash_password(new_password, salt)

    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (password_hash, salt.hex(), user_id),
        )
        # Changing the password invalidates all existing sessions - standard
        # practice, and matters here specifically since a reset usually means
        # someone else might have had access to the old password/session.
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
