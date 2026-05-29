from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Empresa, EmpresaUsuario, Plan
from app.models.inventory import Almacen
from app.models.user import EmpresaUsuarioInvitacion


ALLOWED_COMPANY_ROLES = {"owner", "admin", "user", "almacenista"}
MANAGE_COMPANY_USER_ROLES = {"owner", "admin"}


@dataclass
class CompanyPlanLimits:
    max_usuarios: int | None
    usuarios_actuales: int
    max_almacenes: int | None
    almacenes_actuales: int
    max_facturas_mensuales: int | None
    productos_ilimitados: bool
    ventas_ilimitadas: bool


def normalize_company_role(role: str, *, allow_owner: bool = False) -> str:
    normalized = (role or "").strip().lower()
    allowed = ALLOWED_COMPANY_ROLES if allow_owner else (ALLOWED_COMPANY_ROLES - {"owner"})
    if normalized not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rol inválido. Usa: {', '.join(sorted(allowed))}.",
        )
    return normalized


def ensure_membership_can_manage_users(membership: EmpresaUsuario) -> None:
    if not membership.is_active or membership.role not in MANAGE_COMPANY_USER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para administrar usuarios de la empresa.",
        )


def get_plan_or_raise(db: Session, plan_code: str) -> Plan:
    plan = db.get(Plan, plan_code)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El plan actual de la empresa no está configurado correctamente.",
        )
    return plan


def count_active_company_users(db: Session, empresa_id: str) -> int:
    return db.scalar(
        select(func.count(EmpresaUsuario.id)).where(
            EmpresaUsuario.empresa_id == empresa_id,
            EmpresaUsuario.is_active == True,
        )
    ) or 0


def count_active_company_warehouses(db: Session, empresa_id: str) -> int:
    return db.scalar(
        select(func.count(Almacen.id)).where(
            Almacen.empresa_id == empresa_id,
            Almacen.activo == True,
        )
    ) or 0


def get_company_plan_limits(db: Session, empresa: Empresa) -> CompanyPlanLimits:
    plan = get_plan_or_raise(db, empresa.plan_code)
    return CompanyPlanLimits(
        max_usuarios=plan.max_usuarios,
        usuarios_actuales=count_active_company_users(db, empresa.id),
        max_almacenes=plan.max_almacenes,
        almacenes_actuales=count_active_company_warehouses(db, empresa.id),
        max_facturas_mensuales=plan.max_facturas_mensuales,
        productos_ilimitados=bool(plan.productos_ilimitados),
        ventas_ilimitadas=bool(plan.ventas_ilimitadas),
    )


def ensure_within_company_user_limit(db: Session, empresa: Empresa) -> CompanyPlanLimits:
    limits = get_company_plan_limits(db, empresa)
    if limits.max_usuarios is not None and limits.usuarios_actuales >= limits.max_usuarios:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tu plan permite hasta {limits.max_usuarios} usuarios. Actualiza tu plan para invitar más usuarios.",
        )
    return limits


def ensure_within_company_warehouse_limit(db: Session, empresa: Empresa) -> CompanyPlanLimits:
    limits = get_company_plan_limits(db, empresa)
    if limits.max_almacenes is not None and limits.almacenes_actuales >= limits.max_almacenes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tu plan permite hasta {limits.max_almacenes} almacén(es). Actualiza tu plan para agregar más.",
        )
    return limits


def get_pending_invitation_for_company_email(db: Session, empresa_id: str, email: str) -> EmpresaUsuarioInvitacion | None:
    return db.scalar(
        select(EmpresaUsuarioInvitacion).where(
            EmpresaUsuarioInvitacion.empresa_id == empresa_id,
            EmpresaUsuarioInvitacion.email == email,
            EmpresaUsuarioInvitacion.status == "pending",
        )
    )
