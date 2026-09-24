from app.database import SessionLocal
from app.services.permission_seed import sync_permission_system


def main() -> None:
    db = SessionLocal()

    try:
        result = sync_permission_system(db)

        print("Permission system synchronized successfully.")
        print(f"Permissions created: {result['permissions_created']}")
        print(
            f"Role permissions created: "
            f"{result['role_permissions_created']}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
