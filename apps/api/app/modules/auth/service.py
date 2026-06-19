from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.db import get_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hash_: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hash_.encode("utf-8"))


def create_token(user_id: str, username: str, is_admin: bool = False) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        return None


def create_user(username: str, password: str, display_name: str) -> dict:
    db = get_db()
    user_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(password)

    db.execute(
        """INSERT INTO users (id, username, password_hash, display_name, created_at, is_admin)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, username, pw_hash, display_name, now, 0),
    )
    db.commit()

    return {"id": user_id, "username": username, "display_name": display_name, "created_at": now, "is_admin": False}


def authenticate(username: str, password: str) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT id, username, password_hash, display_name, created_at, is_admin FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None

    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"], "created_at": row["created_at"], "is_admin": bool(row["is_admin"])}


def get_user_by_id(user_id: str) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT id, username, display_name, created_at, is_admin FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"], "created_at": row["created_at"], "is_admin": bool(row["is_admin"])}
