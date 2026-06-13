from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock

from app.core.time_utils import now_iso


_conn: sqlite3.Connection | None = None
_conn_lock = Lock()


def get_db() -> sqlite3.Connection:
    """返回线程级 SQLite 连接 (WAL 模式)。"""
    global _conn
    if _conn is not None:
        return _conn
    raise RuntimeError("Database not initialized — call init_db() first")


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'preparing',
    invite_code TEXT UNIQUE NOT NULL,
    password TEXT,
    room_theme TEXT DEFAULT 'black',
    module_intro TEXT,
    summary TEXT,
    created_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS room_members (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    user_id TEXT REFERENCES users(id),
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    online INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_members_room ON room_members(room_id);
CREATE INDEX IF NOT EXISTS idx_members_user ON room_members(user_id);

CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    owner_id TEXT,
    owner_name TEXT,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_characters_room ON characters(room_id);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    type TEXT NOT NULL,
    sender_id TEXT,
    sender_name TEXT NOT NULL,
    sender_role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    data_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id);

CREATE TABLE IF NOT EXISTS dice_rolls (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    roller_id TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rolls_room ON dice_rolls(room_id);
"""


def init_db(data_dir: Path) -> None:
    """初始化 SQLite 数据库：创建连接、建表、从 rooms.json 迁移数据。"""
    global _conn
    with _conn_lock:
        db_path = data_dir / "rooms.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(db_path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _conn.commit()

        # 检查是否需要从 rooms.json 迁移
        json_path = data_dir / "rooms.json"
        _migrate_from_json(json_path)

    print(f"[db] SQLite initialized at {db_path}")


def _migrate_from_json(json_path: Path) -> None:
    if not json_path.exists():
        return

    # 检查 rooms 表是否已有数据
    cur = _conn.execute("SELECT COUNT(*) FROM rooms")
    if cur.fetchone()[0] > 0:
        return

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    rooms = data.get("rooms", {})
    if not rooms:
        return

    migrated = 0
    for room_id, room in rooms.items():
        try:
            _conn.execute(
                """INSERT OR IGNORE INTO rooms
                   (id, name, status, invite_code, password, room_theme,
                    module_intro, summary, created_at, ended_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    room.get("id", room_id),
                    room.get("name", ""),
                    room.get("status", "preparing"),
                    room.get("inviteCode", ""),
                    room.get("password"),
                    room.get("roomTheme", "black"),
                    room.get("moduleIntro"),
                    json.dumps(room.get("summary")) if room.get("summary") else None,
                    room.get("createdAt", now_iso()),
                    room.get("endedAt"),
                ),
            )

            for member in room.get("members", []):
                _conn.execute(
                    """INSERT OR IGNORE INTO room_members
                       (id, room_id, user_id, display_name, role, online, joined_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        member.get("id", ""),
                        room.get("id", room_id),
                        None,  # 旧数据无 user_id
                        member.get("displayName", ""),
                        member.get("role", "player"),
                        0,  # 迁移时全部离线
                        member.get("joinedAt", now_iso()),
                    ),
                )

            for char in room.get("characters", []):
                _conn.execute(
                    """INSERT OR IGNORE INTO characters
                       (id, room_id, owner_id, owner_name, data_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        char.get("id", ""),
                        room.get("id", room_id),
                        char.get("ownerId"),
                        char.get("ownerName", ""),
                        json.dumps(char, ensure_ascii=False),
                        char.get("createdAt", now_iso()),
                        char.get("updatedAt", now_iso()),
                    ),
                )

            for msg in room.get("messages", []):
                extra = {}
                for key in ("roll", "replyTo", "attachment", "privateTo", "whisperTo", "mentionIds"):
                    if msg.get(key):
                        extra[key] = msg[key]
                _conn.execute(
                    """INSERT OR IGNORE INTO messages
                       (id, room_id, type, sender_id, sender_name, sender_role,
                        content, data_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        msg.get("id", ""),
                        room.get("id", room_id),
                        msg.get("type", "text"),
                        msg.get("senderId"),
                        msg.get("senderName", ""),
                        msg.get("senderRole", "player"),
                        msg.get("content", ""),
                        json.dumps(extra, ensure_ascii=False) if extra else None,
                        msg.get("createdAt", now_iso()),
                    ),
                )

            for roll in room.get("rolls", []):
                _conn.execute(
                    """INSERT OR IGNORE INTO dice_rolls
                       (id, room_id, roller_id, data_json, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        roll.get("id", ""),
                        room.get("id", room_id),
                        roll.get("rollerId", ""),
                        json.dumps(roll, ensure_ascii=False),
                        roll.get("createdAt", now_iso()),
                    ),
                )

            migrated += 1
        except Exception:
            _conn.rollback()
            raise

    _conn.commit()

    # 迁移成功后备份
    backup = json_path.with_suffix(".json.migrated")
    json_path.rename(backup)
    print(f"[db] migrated {migrated} rooms from {json_path.name} → {backup.name}")


def close_db() -> None:
    global _conn
    with _conn_lock:
        if _conn is not None:
            _conn.close()
            _conn = None

