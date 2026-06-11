from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import SuperadminContext, get_superadmin_context
from app.core.catalog import ALLOWED_ACCESS_STATUSES, ALLOWED_PLAN_CODES
from app.core.security import build_token_expiration, create_access_token
from app.db.session import get_db
from app.models import AuditLog, Empresa, EmpresaModulo, EmpresaUsuario, Plan, Usuario
from app.models.inventory import Almacen, Existencia, Material, MovimientoInventario
from app.schemas.superadmin import (
    ImpersonateRequest,
    ImpersonateResponse,
    SuperadminAuditLogItem,
    SuperadminAuditLogListResponse,
    SuperadminCompanyDetailResponse,
    SuperadminCompanyListItem,
    SuperadminCompanyListResponse,
    SuperadminCompanyModuleItem,
    SuperadminCompanyUserItem,
    SuperadminInventoryCounts,
    SuperadminOverviewResponse,
    SuperadminPlanCounts,
    SuperadminUserCompanyItem,
    SuperadminUserDetailResponse,
    SuperadminUserListItem,
    SuperadminUserListResponse,
    UpdateCompanyAccessRequest,
)
from app.schemas.common import CompanyLimitsSummary
from app.services.phone import mask_phone
from app.services.company import get_company_plan_limits
from app.services.seed import sync_company_modules


router = APIRouter(prefix="/superadmin", tags=["superadmin"])


def normalize_reason(reason: str) -> str:
    normalized = reason.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes indicar una razon para este cambio.",
        )
    return normalized


def serialize_audit_log(log: AuditLog, company_name: str | None, user_name: str | None) -> SuperadminAuditLogItem:
    return SuperadminAuditLogItem(
        id=log.id,
        empresa_id=log.empresa_id,
        empresa_nombre=company_name,
        usuario_id=log.usuario_id,
        usuario_nombre=user_name,
        action=log.action,
        entity_name=log.entity_name,
        entity_id=log.entity_id,
        created_at=log.created_at,
        metadata_json=log.metadata_json,
    )


def list_recent_audit_logs(
    db: Session,
    *,
    limit: int = 25,
    offset: int = 0,
    empresa_id: str | None = None,
    usuario_id: str | None = None,
    action: str | None = None,
    q: str | None = None,
) -> tuple[int, list[SuperadminAuditLogItem]]:
    filters = []
    if empresa_id:
        filters.append(AuditLog.empresa_id == empresa_id)
    if usuario_id:
        filters.append(AuditLog.usuario_id == usuario_id)
    if action:
        filters.append(AuditLog.action == action.strip())
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                AuditLog.action.ilike(pattern),
                AuditLog.entity_name.ilike(pattern),
            )
        )

    total = db.scalar(
        select(func.count(AuditLog.id)).where(*filters)
    ) or 0

    rows = db.execute(
        select(AuditLog, Empresa.name, Usuario.full_name)
        .outerjoin(Empresa, AuditLog.empresa_id == Empresa.id)
        .outerjoin(Usuario, AuditLog.usuario_id == Usuario.id)
        .where(*filters)
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .offset(offset)
        .limit(limit)
    ).all()

    return total, [serialize_audit_log(log, company_name, user_name) for log, company_name, user_name in rows]


def build_company_user_item(membership: EmpresaUsuario) -> SuperadminCompanyUserItem:
    user = membership.usuario
    return SuperadminCompanyUserItem(
        membership_id=membership.id,
        usuario_id=user.id,
        nombre_completo=user.full_name,
        email=user.email,
        phone_e164_masked=mask_phone(user.phone_e164 or "", user.country_code) if user.phone_e164 else None,
        role=membership.role,
        activo=bool(membership.is_active and user.is_active),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def build_user_company_item(membership: EmpresaUsuario) -> SuperadminUserCompanyItem:
    company = membership.empresa
    return SuperadminUserCompanyItem(
        empresa_id=company.id,
        empresa_nombre=company.name,
        role=membership.role,
        is_active=membership.is_active,
        plan_code=company.plan_code,
        access_status=company.access_status,
    )


def build_company_detail(db: Session, empresa_id: str) -> SuperadminCompanyDetailResponse:
    company = db.scalar(
        select(Empresa)
        .options(
            selectinload(Empresa.modules),
            selectinload(Empresa.users).selectinload(EmpresaUsuario.usuario),
        )
        .where(Empresa.id == empresa_id)
    )
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada.")

    inventory_counts = SuperadminInventoryCounts(
        almacenes=db.scalar(
            select(func.count(Almacen.id)).where(Almacen.empresa_id == company.id, Almacen.activo == True)
        ) or 0,
        materiales=db.scalar(select(func.count(Material.id)).where(Material.empresa_id == company.id)) or 0,
        existencias=db.scalar(select(func.count(Existencia.id)).where(Existencia.empresa_id == company.id)) or 0,
        movimientos=db.scalar(
            select(func.count(MovimientoInventario.id)).where(MovimientoInventario.empresa_id == company.id)
        ) or 0,
    )
    limits = get_company_plan_limits(db, company)
    _, audit_items = list_recent_audit_logs(db, empresa_id=company.id, limit=25)

    sorted_memberships = sorted(
        [membership for membership in company.users if membership.usuario is not None],
        key=lambda membership: (membership.role != "owner", membership.usuario.full_name.lower()),
    )
    modules = sorted(company.modules, key=lambda module: module.module_name)

    return SuperadminCompanyDetailResponse(
        id=company.id,
        nombre=company.name,
        slug=company.slug,
        razon_social=company.razon_social,
        rfc=company.rfc,
        giro=company.giro,
        telefono=company.telefono,
        email_contacto=company.email_contacto,
        pais=company.pais,
        estado=company.estado,
        ciudad=company.ciudad,
        direccion=company.direccion,
        plan_code=company.plan_code,
        access_status=company.access_status,
        trial_ends_at=company.trial_ends_at,
        created_at=company.created_at,
        is_trial=company.access_status == "trial",
        estado_pago=None,
        limits=CompanyLimitsSummary(
            max_usuarios=limits.max_usuarios,
            usuarios_actuales=limits.usuarios_actuales,
            max_almacenes=limits.max_almacenes,
            almacenes_actuales=limits.almacenes_actuales,
            max_facturas_mensuales=limits.max_facturas_mensuales,
            productos_ilimitados=limits.productos_ilimitados,
            ventas_ilimitadas=limits.ventas_ilimitadas,
        ),
        users=[build_company_user_item(membership) for membership in sorted_memberships],
        modules=[
            SuperadminCompanyModuleItem(
                module_name=module.module_name,
                is_enabled=module.is_enabled,
                notes=module.notes,
            )
            for module in modules
        ],
        inventory_counts=inventory_counts,
        recent_audit_logs=audit_items,
    )


def build_user_detail(db: Session, user_id: str) -> SuperadminUserDetailResponse:
    user = db.scalar(
        select(Usuario)
        .options(selectinload(Usuario.memberships).selectinload(EmpresaUsuario.empresa))
        .where(Usuario.id == user_id)
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    memberships = sorted(
        [membership for membership in user.memberships if membership.empresa is not None],
        key=lambda membership: (membership.role != "owner", membership.empresa.name.lower()),
    )
    _, audit_items = list_recent_audit_logs(db, usuario_id=user.id, limit=25)

    return SuperadminUserDetailResponse(
        id=user.id,
        nombre_completo=user.full_name,
        email=user.email,
        phone_e164_masked=mask_phone(user.phone_e164 or "", user.country_code) if user.phone_e164 else None,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        activo=user.is_active,
        is_superadmin=user.is_superadmin,
        empresas=[build_user_company_item(membership) for membership in memberships],
        recent_audit_logs=audit_items,
    )


@router.get("/overview", response_model=SuperadminOverviewResponse)
def overview(
    _: SuperadminContext = Depends(get_superadmin_context),
    db: Session = Depends(get_db),
) -> SuperadminOverviewResponse:
    now = datetime.now(timezone.utc)
    next_week = now + timedelta(days=7)

    return SuperadminOverviewResponse(
        total_empresas=db.scalar(select(func.count(Empresa.id))) or 0,
        total_usuarios=db.scalar(select(func.count(Usuario.id))) or 0,
        empresas_en_trial=db.scalar(
            select(func.count(Empresa.id)).where(Empresa.access_status == "trial")
        ) or 0,
        empresas_activas=db.scalar(
            select(func.count(Empresa.id)).where(Empresa.access_status == "active")
        ) or 0,
        empresas_suspendidas=db.scalar(
            select(func.count(Empresa.id)).where(Empresa.access_status == "suspended")
        ) or 0,
        trials_por_vencer_7_dias=db.scalar(
            select(func.count(Empresa.id)).where(
                Empresa.access_status == "trial",
                Empresa.trial_ends_at >= now,
                Empresa.trial_ends_at <= next_week,
            )
        ) or 0,
        plan_counts=SuperadminPlanCounts(
            basico=db.scalar(select(func.count(Empresa.id)).where(Empresa.plan_code == "basico")) or 0,
            pro=db.scalar(select(func.count(Empresa.id)).where(Empresa.plan_code == "pro")) or 0,
            total=db.scalar(select(func.count(Empresa.id)).where(Empresa.plan_code == "total")) or 0,
        ),
    )


@router.get("/companies", response_model=SuperadminCompanyListResponse)
def companies(
    q: str | None = None,
    plan_code: str | None = None,
    access_status: str | None = None,
    trial_status: str | None = Query(default=None, pattern="^(active|expired|ending_soon)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: SuperadminContext = Depends(get_superadmin_context),
    db: Session = Depends(get_db),
) -> SuperadminCompanyListResponse:
    now = datetime.now(timezone.utc)
    next_week = now + timedelta(days=7)

    user_counts_sq = (
        select(EmpresaUsuario.empresa_id.label("empresa_id"), func.count(EmpresaUsuario.id).label("usuarios_count"))
        .where(EmpresaUsuario.is_active == True)
        .group_by(EmpresaUsuario.empresa_id)
        .subquery()
    )
    warehouse_counts_sq = (
        select(Almacen.empresa_id.label("empresa_id"), func.count(Almacen.id).label("almacenes_count"))
        .where(Almacen.activo == True)
        .group_by(Almacen.empresa_id)
        .subquery()
    )
    material_counts_sq = (
        select(Material.empresa_id.label("empresa_id"), func.count(Material.id).label("materiales_count"))
        .group_by(Material.empresa_id)
        .subquery()
    )
    last_login_sq = (
        select(EmpresaUsuario.empresa_id.label("empresa_id"), func.max(Usuario.last_login_at).label("ultimo_login_at"))
        .join(Usuario, EmpresaUsuario.usuario_id == Usuario.id)
        .group_by(EmpresaUsuario.empresa_id)
        .subquery()
    )

    filters = []
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(Empresa.name.ilike(pattern), Empresa.slug.ilike(pattern)))
    if plan_code:
        filters.append(Empresa.plan_code == plan_code.strip().lower())
    if access_status:
        filters.append(Empresa.access_status == access_status.strip().lower())
    if trial_status == "active":
        filters.extend([Empresa.access_status == "trial", Empresa.trial_ends_at >= now])
    elif trial_status == "expired":
        filters.append(Empresa.trial_ends_at < now)
    elif trial_status == "ending_soon":
        filters.extend(
            [
                Empresa.access_status == "trial",
                Empresa.trial_ends_at >= now,
                Empresa.trial_ends_at <= next_week,
            ]
        )

    total = db.scalar(select(func.count(Empresa.id)).where(*filters)) or 0

    rows = db.execute(
        select(
            Empresa,
            func.coalesce(user_counts_sq.c.usuarios_count, 0),
            func.coalesce(warehouse_counts_sq.c.almacenes_count, 0),
            func.coalesce(material_counts_sq.c.materiales_count, 0),
            last_login_sq.c.ultimo_login_at,
            Plan.max_usuarios,
            Plan.max_almacenes,
        )
        .outerjoin(user_counts_sq, user_counts_sq.c.empresa_id == Empresa.id)
        .outerjoin(warehouse_counts_sq, warehouse_counts_sq.c.empresa_id == Empresa.id)
        .outerjoin(material_counts_sq, material_counts_sq.c.empresa_id == Empresa.id)
        .outerjoin(last_login_sq, last_login_sq.c.empresa_id == Empresa.id)
        .outerjoin(Plan, Plan.code == Empresa.plan_code)
        .where(*filters)
        .order_by(desc(Empresa.created_at), Empresa.name.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    return SuperadminCompanyListResponse(
        total=total,
        items=[
            SuperadminCompanyListItem(
                id=company.id,
                nombre=company.name,
                razon_social=company.razon_social,
                rfc=company.rfc,
                plan_code=company.plan_code,
                access_status=company.access_status,
                trial_ends_at=company.trial_ends_at,
                created_at=company.created_at,
                usuarios_count=usuarios_count,
                almacenes_count=almacenes_count,
                materiales_count=materiales_count,
                max_usuarios=max_usuarios,
                max_almacenes=max_almacenes,
                ultimo_login_at=ultimo_login_at,
                estado_pago=None,
            )
            for company, usuarios_count, almacenes_count, materiales_count, ultimo_login_at, max_usuarios, max_almacenes in rows
        ],
    )


@router.get("/companies/{empresa_id}", response_model=SuperadminCompanyDetailResponse)
def company_detail(
    empresa_id: str,
    _: SuperadminContext = Depends(get_superadmin_context),
    db: Session = Depends(get_db),
) -> SuperadminCompanyDetailResponse:
    return build_company_detail(db, empresa_id)


@router.get("/users", response_model=SuperadminUserListResponse)
def users(
    q: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: SuperadminContext = Depends(get_superadmin_context),
    db: Session = Depends(get_db),
) -> SuperadminUserListResponse:
    filters = []
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(Usuario.full_name.ilike(pattern), Usuario.email.ilike(pattern)))

    total = db.scalar(select(func.count(Usuario.id)).where(*filters)) or 0
    users_list = db.scalars(
        select(Usuario)
        .options(selectinload(Usuario.memberships).selectinload(EmpresaUsuario.empresa))
        .where(*filters)
        .order_by(desc(Usuario.created_at), Usuario.full_name.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    return SuperadminUserListResponse(
        total=total,
        items=[
            SuperadminUserListItem(
                id=user.id,
                nombre_completo=user.full_name,
                email=user.email,
                phone_e164_masked=mask_phone(user.phone_e164 or "", user.country_code) if user.phone_e164 else None,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
                activo=user.is_active,
                empresas=[
                    build_user_company_item(membership)
                    for membership in sorted(
                        [membership for membership in user.memberships if membership.empresa is not None],
                        key=lambda membership: (membership.role != "owner", membership.empresa.name.lower()),
                    )
                ],
            )
            for user in users_list
        ],
    )


@router.get("/users/{usuario_id}", response_model=SuperadminUserDetailResponse)
def user_detail(
    usuario_id: str,
    _: SuperadminContext = Depends(get_superadmin_context),
    db: Session = Depends(get_db),
) -> SuperadminUserDetailResponse:
    return build_user_detail(db, usuario_id)


@router.patch("/companies/{empresa_id}/access", response_model=SuperadminCompanyDetailResponse)
def update_company_access(
    empresa_id: str,
    payload: UpdateCompanyAccessRequest,
    context: SuperadminContext = Depends(get_superadmin_context),
    db: Session = Depends(get_db),
) -> SuperadminCompanyDetailResponse:
    normalized_reason = normalize_reason(payload.reason)
    normalized_plan_code = payload.plan_code.strip().lower()
    normalized_access_status = payload.access_status.strip().lower()

    if normalized_plan_code not in ALLOWED_PLAN_CODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="plan_code invalido.")
    if normalized_access_status not in ALLOWED_ACCESS_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="access_status invalido.")

    company = db.scalar(
        select(Empresa).options(selectinload(Empresa.modules)).where(Empresa.id == empresa_id)
    )
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada.")

    previous_state = {
        "plan_code": company.plan_code,
        "access_status": company.access_status,
        "trial_ends_at": company.trial_ends_at.isoformat(),
    }

    company.plan_code = normalized_plan_code
    company.access_status = normalized_access_status
    if payload.trial_ends_at is not None:
        company.trial_ends_at = payload.trial_ends_at
    sync_company_modules(company, normalized_plan_code)

    db.add(
        AuditLog(
            empresa_id=company.id,
            usuario_id=context.user.id,
            action="superadmin.company.access.update",
            entity_name="empresa",
            entity_id=company.id,
            metadata_json={
                "before": previous_state,
                "after": {
                    "plan_code": company.plan_code,
                    "access_status": company.access_status,
                    "trial_ends_at": company.trial_ends_at.isoformat(),
                },
                "reason": normalized_reason,
            },
        )
    )
    db.commit()
    return build_company_detail(db, company.id)


@router.post("/impersonate", response_model=ImpersonateResponse)
def impersonate(
    payload: ImpersonateRequest,
    context: SuperadminContext = Depends(get_superadmin_context),
    db: Session = Depends(get_db),
) -> ImpersonateResponse:
    normalized_reason = normalize_reason(payload.reason)
    user = db.get(Usuario, payload.usuario_id)
    company = db.get(Empresa, payload.empresa_id)
    if not user or not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario o empresa no encontrados.",
        )

    membership = db.scalar(
        select(EmpresaUsuario)
        .where(
            EmpresaUsuario.empresa_id == company.id,
            EmpresaUsuario.usuario_id == user.id,
            EmpresaUsuario.is_active == True,
        )
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario no pertenece a la empresa indicada.",
        )

    expires_at = build_token_expiration(15)
    access_token = create_access_token(
        subject=user.id,
        empresa_id=company.id,
        expires_minutes=15,
        extra_claims={
            "email": user.email,
            "role": membership.role,
            "impersonated_by": context.user.id,
            "impersonation": True,
            "impersonation_ends_at": expires_at.isoformat(),
        },
    )

    db.add(
        AuditLog(
            empresa_id=company.id,
            usuario_id=context.user.id,
            action="superadmin.impersonate",
            entity_name="usuario",
            entity_id=user.id,
            metadata_json={
                "impersonated_user_id": user.id,
                "impersonated_user_email": user.email,
                "empresa_id": company.id,
                "reason": normalized_reason,
                "expires_at": expires_at.isoformat(),
            },
        )
    )
    db.commit()

    return ImpersonateResponse(
        access_token=access_token,
        token_type="bearer",
        expires_at=expires_at,
        empresa_id=company.id,
        empresa_nombre=company.name,
        usuario_id=user.id,
        usuario_nombre=user.full_name,
    )


@router.get("/audit-logs", response_model=SuperadminAuditLogListResponse)
def audit_logs(
    action: str | None = None,
    q: str | None = None,
    empresa_id: str | None = None,
    usuario_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: SuperadminContext = Depends(get_superadmin_context),
    db: Session = Depends(get_db),
) -> SuperadminAuditLogListResponse:
    total, items = list_recent_audit_logs(
        db,
        limit=limit,
        offset=offset,
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        action=action,
        q=q,
    )
    return SuperadminAuditLogListResponse(total=total, items=items)

