"""
Create a business and its first administrator from the command line.

    python -m app.create_owner

Use this when setting up a live system (sign-up is closed there), or to add
another business later. It asks for everything, including the password, so
nothing is left in your shell history.
"""

import getpass
import sys

from pydantic import ValidationError

from app.api.auth import create_business_with_owner
from app.database import SessionLocal
from app.schemas.auth import RegisterRequest
from fastapi import HTTPException


def main() -> int:
    print("Create a business and its main administrator\n")
    business = input("Business name: ").strip()
    full_name = input("Administrator's full name: ").strip()
    email = input("Administrator's email: ").strip()
    password = getpass.getpass("Password (at least 8 characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("The passwords do not match.", file=sys.stderr)
        return 1

    try:
        data = RegisterRequest(
            business_name=business,
            full_name=full_name,
            email=email,
            password=password,
        )
    except ValidationError as exc:
        for err in exc.errors():
            print(f"- {err['loc'][-1]}: {err['msg']}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        create_business_with_owner(data, db)
    except HTTPException as exc:
        print(f"Could not create it: {exc.detail}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"\nDone. {full_name} can now sign in as {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
