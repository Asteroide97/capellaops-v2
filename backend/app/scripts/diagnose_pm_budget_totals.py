"""Tenant-scoped SQLAlchemy diagnostics. Explicit DATABASE_URL via environment."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session


@contextmanager
def read_only_guard(engine, db):
    """Fail closed before non-SELECT application SQL, ORM flushes or commits."""
    def check_sql(conn, cursor, statement, parameters, context, executemany):
        if context.compiled is None or not getattr(context.compiled.statement, "is_select", False):
            raise ValueError("Dry-run solo permite SELECT compilados por SQLAlchemy.")

    def deny_flush(session, flush_context, instances):
        raise ValueError("Dry-run no permite flush.")

    def deny_commit(*args):
        raise ValueError("Dry-run no permite commit.")

    # Driver-owned dialect discovery happens before application queries.
    db.connection()
    event.listen(engine, "before_cursor_execute", check_sql)
    event.listen(engine, "commit", deny_commit)
    event.listen(db, "before_flush", deny_flush)
    event.listen(db, "before_commit", deny_commit)
    try:
        yield
    finally:
        db.rollback()
        event.remove(engine, "before_cursor_execute", check_sql)
        event.remove(engine, "commit", deny_commit)
        event.remove(db, "before_flush", deny_flush)
        event.remove(db, "before_commit", deny_commit)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Diagnostico PM SQLAlchemy, solo lectura por defecto.")
    parser.add_argument("--sqlite-path", help="Archivo SQLite local opcional en lugar de DATABASE_URL.")
    parser.add_argument("--empresa-id", required=True)
    parser.add_argument("--presupuesto-id", action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="Reparar solo IDs seleccionados; usar primero dry-run y copia de seguridad.")
    args = parser.parse_args(argv)
    empresa_id = args.empresa_id.strip()
    ids = {value.strip() for value in args.presupuesto_id}
    if not empresa_id or "" in ids:
        parser.error("Empresa e IDs deben ser explicitos y no vacios.")
    if args.apply and not ids:
        parser.error("--apply requiere al menos un --presupuesto-id revisado.")
    if args.sqlite_path:
        path = Path(args.sqlite_path).resolve()
        if str(path).startswith(("\\\\", "//")) or not path.is_file():
            parser.error("Se requiere un archivo SQLite local existente.")
        url = URL.create("sqlite+pysqlite", database=f"file:{path.as_posix()}",
                         query={"mode": "rw" if args.apply else "ro", "uri": "true"})
    else:
        supplied_url = os.environ.get("DATABASE_URL", "").strip()
        if not supplied_url:
            parser.error("Suministra DATABASE_URL explicitamente en el entorno; no hay fallback a .env.")
        try:
            from app.core.config import Settings
            url = make_url(Settings(_env_file=None, DATABASE_URL=supplied_url).sqlalchemy_database_url)
        except Exception:
            parser.error("La configuracion de conexion no es valida.")
    if url.get_backend_name() not in {"sqlite", "mssql"}:
        parser.error("Solo se admiten SQLite y SQL Server.")
    engine = None
    try:
        from app.services.pm_budget_diagnostics import diagnose_project_economics, repair_budget_headers
        engine = create_engine(url, echo=False, hide_parameters=True,
                               **({"isolation_level": "SERIALIZABLE"} if args.apply else {}))
        with Session(engine, autoflush=False) as db:
            if args.apply:
                with db.begin():
                    rows = repair_budget_headers(db, empresa_id=empresa_id, budget_ids=ids)
            else:
                with read_only_guard(engine, db):
                    rows = diagnose_project_economics(db, empresa_id=empresa_id, budget_ids=ids or None)
            print(json.dumps(rows, default=str, ensure_ascii=True, indent=2))
        return 0
    except Exception:
        print("No se pudo completar la revision. La transaccion no se confirmo.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
