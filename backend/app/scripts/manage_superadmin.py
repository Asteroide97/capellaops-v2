from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal
from app.models import AuditLog, Usuario


PROMOTE = "promote"
DEMOTE = "demote"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promueve o retira privilegios superadmin a un usuario existente por email.",
    )
    parser.add_argument(
        "command",
        choices=[PROMOTE, DEMOTE],
        help="Accion a ejecutar sobre el usuario.",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Correo del usuario a administrar.",
    )
    parser.add_argument(
        "--reason",
        required=True,
        help="Razon operativa obligatoria para auditar el cambio.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirma la escritura real en base de datos. Sin este flag solo se muestra lo que ocurriria.",
    )
    return parser


def get_user_by_email(email: str) -> Usuario | None:
    db = SessionLocal()
    try:
        normalized_email = normalize_email(email)
        return db.scalar(
            select(Usuario).where(func.lower(Usuario.email) == normalized_email)
        )
    finally:
        db.close()


def write_audit_log(db, action: str, user: Usuario, reason: str) -> None:
    db.add(
        AuditLog(
            empresa_id=None,
            usuario_id=None,
            action=action,
            entity_name="usuario",
            entity_id=user.id,
            metadata_json={
                "target_user_id": user.id,
                "target_email": user.email,
                "reason": reason,
                "managed_by": "app.scripts.manage_superadmin",
            },
        )
    )


def execute_change(command: str, email: str, reason: str, confirm: bool) -> int:
    normalized_email = normalize_email(email)
    normalized_reason = reason.strip()
    if not normalized_reason:
        print("Error: --reason es obligatorio y no puede ir vacio.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        user = db.scalar(
            select(Usuario).where(func.lower(Usuario.email) == normalized_email)
        )
        if user is None:
            print(
                f'Error: no existe un usuario con email "{normalized_email}".',
                file=sys.stderr,
            )
            return 1

        desired_superadmin = command == PROMOTE
        action = "superadmin_promote" if desired_superadmin else "superadmin_demote"
        verb = "promover" if desired_superadmin else "retirar"

        if desired_superadmin and not user.is_active:
            print(
                f'Error: el usuario "{user.email}" esta inactivo y no puede promoverse a superadmin.',
                file=sys.stderr,
            )
            return 1

        if user.is_superadmin == desired_superadmin:
            state_label = "ya es superadmin" if desired_superadmin else "ya no es superadmin"
            print(f'Sin cambios: el usuario "{user.email}" {state_label}.')
            return 0

        if not confirm:
            print(
                f'Dry-run: se va a {verb} privilegios superadmin para "{user.email}" '
                f'(usuario_id={user.id}).'
            )
            print(f"Reason: {normalized_reason}")
            print("No se escribieron cambios. Repite el comando con --confirm para aplicar.")
            return 0

        user.is_superadmin = desired_superadmin
        write_audit_log(db, action, user, normalized_reason)
        db.commit()

        status_label = "ahora es superadmin" if desired_superadmin else "ya no es superadmin"
        print(f'OK: el usuario "{user.email}" {status_label}.')
        return 0
    except SQLAlchemyError as exc:
        db.rollback()
        print(
            f"Error: no se pudo completar la operacion de superadmin ({exc.__class__.__name__}).",
            file=sys.stderr,
        )
        return 1
    finally:
        db.close()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return execute_change(
        command=args.command,
        email=args.email,
        reason=args.reason,
        confirm=args.confirm,
    )


if __name__ == "__main__":
    raise SystemExit(main())
