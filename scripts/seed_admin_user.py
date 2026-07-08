"""Seeds/resets an admin user for RBAC login (spec section 18).

There is no registration or password-reset endpoint -- this script is the
only way to create or reset a user for now. Safe to re-run: if the username
already exists, its password is reset and role forced to admin rather than
creating a duplicate.

Run from services/api's venv (needs app.db.* + DATABASE_URL):
    cd services/api
    ./.venv/Scripts/python.exe ../../scripts/seed_admin_user.py <username> <password>
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[1] / "services" / "api"
sys.path.insert(0, str(_API_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.models import AppUser  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python seed_admin_user.py <username> <password>")
        raise SystemExit(1)
    username, password = sys.argv[1], sys.argv[2]
    if len(password) < 8:
        print("Refusing a password shorter than 8 characters.")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        user = db.scalar(select(AppUser).where(AppUser.username == username))
        if user is None:
            user = AppUser(username=username, password_hash=hash_password(password), role="admin", is_active=True)
            db.add(user)
            db.commit()
            print(f"Created admin user '{username}'.")
        else:
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.is_active = True
            db.commit()
            print(f"Reset existing user '{username}' to admin with the new password.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
