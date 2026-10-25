"""Create a platform (Saccharum) administrator.

    python -m app.create_platform_admin
"""

import getpass
import sys

from app.database import SessionLocal
from app.models.platform_admin import PlatformAdmin
from app.security import hash_password


def main(prompt=input, secret=getpass.getpass) -> int:
    email = prompt("Email: ").strip().lower()
    name = prompt("Full name: ").strip()
    password = secret("Password (12+ characters): ")
    if "@" not in email or not name or len(password) < 12:
        print("Email, name and a password of at least 12 characters are required.")
        return 1
    db = SessionLocal()
    try:
        if db.query(PlatformAdmin).filter(PlatformAdmin.email == email).first():
            print("That platform administrator already exists.")
            return 1
        db.add(PlatformAdmin(
            email=email, full_name=name, password_hash=hash_password(password)
        ))
        db.commit()
    finally:
        db.close()
    print(f"Platform administrator {email} created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
