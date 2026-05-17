from app.db.session import SessionLocal
from app.services.seed import seed_default_plans


def main() -> None:
    db = SessionLocal()
    try:
        seed_default_plans(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()

