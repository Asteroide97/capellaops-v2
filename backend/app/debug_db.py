from sqlalchemy import inspect

from app.core.config import get_settings
from app.db.session import engine


def main() -> None:
    settings = get_settings()
    summary = settings.database_summary()

    print(f"database_engine={summary['engine']}")
    print(f"database_host={summary['host'] or '(local)'}")
    print(f"database_name={summary['database'] or '(local)'}")

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = sorted(inspector.get_table_names())
            print(f"default_schema={getattr(inspector, 'default_schema_name', 'n/a')}")
            print(f"tables={tables}")
            print(f"usuarios_exists={'usuarios' in tables}")
            print(f"empresas_exists={'empresas' in tables}")
            print(f"planes_exists={'planes' in tables}")
    except Exception as exc:
        print(f"connection_error={exc.__class__.__name__}: {exc}")
        raise


if __name__ == "__main__":
    main()
