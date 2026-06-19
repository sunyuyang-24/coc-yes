"""User-scoped character cards (investigator profiles)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.core.db import get_db


def save_user_character(user_id: str, character: dict, source_filename: str) -> dict:
    """Save a character card to the user's account. Replaces if same name exists."""
    db = get_db()
    name = character.get("basic", {}).get("name") or source_filename
    now = datetime.now(timezone.utc).isoformat()

    existing = db.execute(
        "SELECT id FROM user_characters WHERE user_id = ? AND name = ?",
        (user_id, name),
    ).fetchone()

    if existing:
        char_id = existing["id"]
        db.execute(
            "UPDATE user_characters SET data_json = ?, source_filename = ?, updated_at = ? WHERE id = ?",
            (json.dumps(character, ensure_ascii=False), source_filename, now, char_id),
        )
    else:
        char_id = uuid4().hex
        db.execute(
            """INSERT INTO user_characters (id, user_id, name, data_json, source_filename, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (char_id, user_id, name, json.dumps(character, ensure_ascii=False), source_filename, now, now),
        )
    db.commit()
    return {"id": char_id, "name": name, "source_filename": source_filename, "created_at": now, "updated_at": now}


def get_user_characters(user_id: str) -> list[dict]:
    """Get all character cards for a user."""
    db = get_db()
    rows = db.execute(
        "SELECT id, name, source_filename, created_at, updated_at FROM user_characters WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    return [
        {"id": r["id"], "name": r["name"], "source_filename": r["source_filename"], "created_at": r["created_at"], "updated_at": r["updated_at"]}
        for r in rows
    ]


def get_user_character(user_id: str, char_id: str) -> dict | None:
    """Get a specific character card by ID (with full data)."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM user_characters WHERE id = ? AND user_id = ?",
        (char_id, user_id),
    ).fetchone()
    if row is None:
        return None
    data = json.loads(row["data_json"])
    data["id"] = row["id"]
    data["name"] = row["name"]
    data["sourceFileName"] = row["source_filename"]
    data["createdAt"] = row["created_at"]
    data["updatedAt"] = row["updated_at"]
    return data


def delete_user_character(user_id: str, char_id: str) -> bool:
    """Delete a user's character card."""
    db = get_db()
    cur = db.execute(
        "DELETE FROM user_characters WHERE id = ? AND user_id = ?",
        (char_id, user_id),
    )
    db.commit()
    return cur.rowcount > 0


def get_user_character_count(user_id: str) -> int:
    """Count how many character cards a user has."""
    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) AS cnt FROM user_characters WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return row["cnt"] if row else 0
