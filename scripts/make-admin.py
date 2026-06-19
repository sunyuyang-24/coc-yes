"""Promote a user to administrator.

Usage: python scripts/make-admin.py <username> [--data-dir DATA_DIR]

The script updates the user's is_admin flag in the SQLite database.
Requires the API server to be stopped (or at least not holding a write lock).
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Promote a user to admin")
    parser.add_argument("username", help="Username to promote")
    parser.add_argument(
        "--data-dir",
        default="data/runtime",
        help="Data directory containing rooms.db (default: data/runtime)",
    )
    args = parser.parse_args()

    db_path = Path(args.data_dir) / "rooms.db"
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT id, username, is_admin FROM users WHERE username = ?", (args.username,))
        row = cur.fetchone()
        if row is None:
            print(f"Error: User '{args.username}' not found", file=sys.stderr)
            sys.exit(1)

        if row["is_admin"]:
            print(f"User '{args.username}' is already an admin.")
            return

        conn.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (args.username,))
        conn.commit()
        print(f"User '{args.username}' (id={row['id']}) is now an admin.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
