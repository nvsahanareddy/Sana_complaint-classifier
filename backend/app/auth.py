"""Authentication, password hashing, sessions and role-based access."""

import hashlib
import hmac
import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException

from app import db

SESSION_DAYS = 7


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
        check = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
        ).hex()
        return hmac.compare_digest(check, digest)
    except (ValueError, AttributeError):
        return False


def prune_expired_sessions(conn) -> int:
    cur = conn.execute(
        "DELETE FROM sessions WHERE created_at <= datetime('now', ?)",
        (f"-{SESSION_DAYS} days",),
    )
    return cur.rowcount


def create_session(conn, user_id: int) -> str:
    prune_expired_sessions(conn)
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    return token


def current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """Return the authenticated user's details and role."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please log in first.")

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.name, u.email, u.role
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.created_at > datetime('now', ?)
            """,
            (token, f"-{SESSION_DAYS} days"),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    return {**dict(row), "token": token}


def is_admin(user: dict) -> bool:
    return user.get("role") == "admin"


def is_technician(user: dict) -> bool:
    return user.get("role") in ("technician", "technision")


def require_admin(user: dict = Depends(current_user)) -> dict:
    """Allow access only to administrator accounts."""
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return user


def require_technician(user: dict = Depends(current_user)) -> dict:
    """Allow access only to technician accounts."""
    if not is_technician(user):
        raise HTTPException(status_code=403, detail="Technician access required.")
    return user


def require_technician_or_admin(user: dict = Depends(current_user)) -> dict:
    """Allow access to technicians and administrators."""
    if not (is_admin(user) or is_technician(user)):
        raise HTTPException(status_code=403, detail="Staff access required (Technician or Administrator).")
    return user


def require_user(user: dict = Depends(current_user)) -> dict:
    """Allow access to authenticated users (citizens, technicians, admins)."""
    return user