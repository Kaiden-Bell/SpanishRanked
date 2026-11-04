"""Maintenance commands, run inside the container (the owner can't recover a lost password any other way):

    docker compose exec -w /app/backend languageai python -m app.manage reset-owner-password
"""

import argparse
import secrets
import sqlite3
import sys

from . import db
from .config import Settings
from .routes_auth import OWNER_USERNAME
from .security import hash_password


def reset_owner_password(conn: sqlite3.Connection) -> str | None:
    """Give the owner a new random one-time password and sign out every device.

    Returns the password, or None if there is no owner account yet.
    """
    password = secrets.token_urlsafe(16)
    with conn:
        updated = conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE username = ?",
            (hash_password(password), OWNER_USERNAME),
        ).rowcount
        if not updated:
            return None
        conn.execute(
            "DELETE FROM auth_sessions WHERE user_id = (SELECT id FROM users WHERE username = ?)",
            (OWNER_USERNAME,),
        )
    return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    parser.add_subparsers(dest="command", required=True).add_parser(
        "reset-owner-password", help="issue a new one-time password for the owner"
    )
    parser.parse_args(argv)

    settings = Settings.from_env()
    if not settings.db_path.exists():
        print(f"No database at {settings.db_path}; start the app once first.", file=sys.stderr)
        return 1
    conn = db.connect(settings.db_path)
    try:
        password = reset_owner_password(conn)
    finally:
        conn.close()
    if password is None:
        print("No owner account exists yet; start the app to create one.", file=sys.stderr)
        return 1
    print(f"Sign in as '{OWNER_USERNAME}' with one-time password: {password}")
    print("You will be asked to change it immediately. All existing sign-ins were ended.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
