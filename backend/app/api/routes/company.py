from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.models import AuditLog, EmpresaUsuario, Usuario
from app.models.user import EmpresaUsuarioInvitacion
from app.schemas.common import CompanyLimitsSummary
from app.schemas.company import (
    CompanyUserDeactivateResponse,
    CompanyUserInviteRequest,
    CompanyUserInviteResponse,
    CompanyUserItem,
    CompanyUsersListResponse,
    CompanyUserUpdateRequest,
)
from app.services.company import (
    ensure_membership_can_manage_users,
    ensure_within_company_user_limit,
    get_company_plan_limits,
    get_pending_invitation_for_company_email,
    normalize_company_role,
)


router = APIRouter(prefix="/company", tags=["company"])


def normalize_email(email: str) -> str:
    return email.strip().lower()


def build_limits_summary(db: Session, empresa) -> CompanyLimitsSummary:
    limits = get_company_plan_limits(db, empresa)
    return CompanyLimitsSummary(
        max_usuarios=limits.max_usuarios,
        usuarios_actuales=limits.usuarios_actuales,
        max_almacenes=limits.max_almacenes,
        almacenes_actuales=limits.almacenes_actuales,
        max_facturas_mensuales=limits.max_facturas_mensuales,
        productos_ilimitados=limits.productos_ilimitados,
        ventas_ilimitadas=limits.ventas_ilimitadas,
    )


def build_membership_item(membership: EmpresaUsuario) -> CompanyUserItem:
    user = membership.usuario
    return CompanyUserItem(
        id=membership.id,
        kind="member",
        usuario_id=user.id if user else None,
        email=user.email if user else "",
        full_name=user.full_name if user else None,
        role=membership.role,
        status="active" if membership.is_active and user and user.is_active else "inactive",
        is_active=bool(membership.is_active and user and user.is_active),
        last_login_at=user.last_login_at if user else None,
        created_at=membership.created_at,
    )


def build_invitation_item(invitation: EmpresaUsuarioInvitacion) -> CompanyUserItem:
    return CompanyUserItem(
        id=invitation.id,
        kind="invitation",
        usuario_id=invitation.linked_user_id,
        email=invitation.email,
        full_name=invitation.full_name,
        role=invitation.role,
        status=invitation.status,
        is_active=False,
        last_login_at=invitation.linked_user.last_login_at if invitation.linked_user else None,
        invited_by_user_id=invitation.invited_by_user_id,
        created_at=invitation.created_at,
    )


def get_company_user_membership(
    db: Session,
    *,
    empresa_id: str,
    membership_id: str,
) -> EmpresaUsuario:
    membership = db.scalar(
        select(EmpresaUsuario)
        .options(selectinload(EmpresaUsuario.usuario))
        .where(
            EmpresaUsuario.id == membership_id,
            EmpresaUsuario.empresa_id == empresa_id,
        )
    )
    if not membership or membership.usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario de empresa no encontrado.")
    return membership


@router.get("/users", response_model=CompanyUsersListResponse)
def list_company_users(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> CompanyUsersListResponse:
    ensure_membership_can_manage_users(context.membership)
    memberships = db.scalars(
        select(EmpresaUsuario)
        .options(selectinload(EmpresaUsuario.usuario))
        .where(EmpresaUsuario.empresa_id == context.empresa.id)
    ).all()
    invitations = db.scalars(
        select(EmpresaUsuarioInvitacion)
        .options(selectinload(EmpresaUsuarioInvitacion.linked_user))
        .where(
            EmpresaUsuarioInvitacion.empresa_id == context.empresa.id,
            EmpresaUsuarioInvitacion.status == "pending",
        )
    ).all()

    items = [build_membership_item(item) for item in memberships if item.usuario is not None]
    items.extend(build_invitation_item(item) for item in invitations)
    items.sort(key=lambda item: (item.kind != "member", item.role != "owner", item.email.lower()))

    return CompanyUsersListResponse(
        empresa_id=context.empresa.id,
        empresa_nombre=context.empresa.name,
        plan_code=context.empresa.plan_code,
        limits=build_limits_summary(db, context.empresa),
        items=items,
    )


@router.post("/users/invite", response_model=CompanyUserInviteResponse)
def invite_company_user(
    payload: CompanyUserInviteRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> CompanyUserInviteResponse:
    ensure_membership_can_manage_users(context.membership)
    email = normalize_email(payload.email)
    role = normalize_company_role(payload.role)
    full_name = payload.full_name.strip() if payload.full_name else None

    existing_membership = db.scalar(
        select(EmpresaUsuario)
        .join(Usuario, EmpresaUsuario.usuario_id == Usuario.id)
        .options(selectinload(EmpresaUsuario.usuario))
        .where(
            EmpresaUsuario.empresa_id == context.empresa.id,
            Usuario.email == email,
        )
    )
    if existing_membership and existing_membership.usuario is not None and existing_membership.is_active:
        return CompanyUserInviteResponse(
            status="already_member",
            message="Ese correo ya pertenece a esta empresa.",
            item=build_membership_item(existing_membership),
            limits=build_limits_summary(db, context.empresa),
        )

    pending_invitation = get_pending_invitation_for_company_email(db, context.empresa.id, email)
    if pending_invitation:
        return CompanyUserInviteResponse(
            status="invited",
            message="Ya existe una invitacion pendiente para este correo.",
            item=build_invitation_item(pending_invitation),
            limits=build_limits_summary(db, context.empresa),
        )

    ensure_within_company_user_limit(db, context.empresa)
    existing_user = db.scalar(select(Usuario).where(Usuario.email == email))

    if existing_membership and existing_membership.usuario is not None and not existing_membership.is_active:
        existing_membership.is_active = True
        existing_membership.role = role
        db.add(
            AuditLog(
                empresa_id=context.empresa.id,
                usuario_id=context.user.id,
                action="company.user.reactivate",
                entity_name="empresa_usuario",
                entity_id=existing_membership.id,
                ip_address=request.client.host if request.client else None,
                metadata_json={"email": email, "role": role},
            )
        )
        db.commit()
        db.refresh(existing_membership)
        return CompanyUserInviteResponse(
            status="linked_existing_user",
            message="El usuario existente fue reactivado y vinculado a la empresa.",
            item=build_membership_item(existing_membership),
            limits=build_limits_summary(db, context.empresa),
        )

    if existing_user:
        membership = EmpresaUsuario(
            empresa_id=context.empresa.id,
            usuario_id=existing_user.id,
            role=role,
            is_active=True,
        )
        db.add(membership)
        db.flush()
        db.add(
            AuditLog(
                empresa_id=context.empresa.id,
                usuario_id=context.user.id,
                action="company.user.link_existing",
                entity_name="empresa_usuario",
                entity_id=membership.id,
                ip_address=request.client.host if request.client else None,
                metadata_json={"email": email, "role": role},
            )
        )
        db.commit()
        db.refresh(membership)
        db.refresh(existing_user)
        membership.usuario = existing_user
        return CompanyUserInviteResponse(
            status="linked_existing_user",
            message="El usuario existente fue vinculado a la empresa.",
            item=build_membership_item(membership),
            limits=build_limits_summary(db, context.empresa),
        )

    invitation = EmpresaUsuarioInvitacion(
        empresa_id=context.empresa.id,
        email=email,
        full_name=full_name,
        role=role,
        status="pending",
        invited_by_user_id=context.user.id,
    )
    db.add(invitation)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=context.empresa.id,
            usuario_id=context.user.id,
            action="company.user.invite",
            entity_name="empresa_usuario_invitacion",
            entity_id=invitation.id,
            ip_address=request.client.host if request.client else None,
            metadata_json={"email": email, "role": role},
        )
    )
    db.commit()
    db.refresh(invitation)
    return CompanyUserInviteResponse(
        status="invited",
        message="Invitacion registrada. El envio de email queda pendiente.",
        item=build_invitation_item(invitation),
        limits=build_limits_summary(db, context.empresa),
    )


@router.patch("/users/{membership_id}", response_model=CompanyUserDeactivateResponse)
def update_company_user(
    membership_id: str,
    payload: CompanyUserUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> CompanyUserDeactivateResponse:
    ensure_membership_can_manage_users(context.membership)
    membership = get_company_user_membership(db, empresa_id=context.empresa.id, membership_id=membership_id)

    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario owner no se puede modificar desde esta operacion.",
        )

    if payload.role is not None:
        membership.role = normalize_company_role(payload.role)

    if payload.is_active is not None:
        if payload.is_active and not membership.is_active:
            ensure_within_company_user_limit(db, context.empresa)
        membership.is_active = payload.is_active

    db.add(
        AuditLog(
            empresa_id=context.empresa.id,
            usuario_id=context.user.id,
            action="company.user.update",
            entity_name="empresa_usuario",
            entity_id=membership.id,
            ip_address=request.client.host if request.client else None,
            metadata_json={"role": membership.role, "is_active": membership.is_active},
        )
    )
    db.commit()
    db.refresh(membership)

    return CompanyUserDeactivateResponse(
        ok=True,
        message="Usuario de empresa actualizado.",
        item=build_membership_item(membership),
        limits=build_limits_summary(db, context.empresa),
    )


@router.post("/users/{membership_id}/deactivate", response_model=CompanyUserDeactivateResponse)
def deactivate_company_user(
    membership_id: str,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> CompanyUserDeactivateResponse:
    ensure_membership_can_manage_users(context.membership)
    membership = get_company_user_membership(db, empresa_id=context.empresa.id, membership_id=membership_id)

    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes desactivar al owner de la empresa.",
        )

    if not membership.is_active:
        return CompanyUserDeactivateResponse(
            ok=True,
            message="El usuario ya estaba desactivado.",
            item=build_membership_item(membership),
            limits=build_limits_summary(db, context.empresa),
        )

    membership.is_active = False
    db.add(
        AuditLog(
            empresa_id=context.empresa.id,
            usuario_id=context.user.id,
            action="company.user.deactivate",
            entity_name="empresa_usuario",
            entity_id=membership.id,
            ip_address=request.client.host if request.client else None,
            metadata_json={"role": membership.role, "email": membership.usuario.email},
        )
    )
    db.commit()
    db.refresh(membership)

    return CompanyUserDeactivateResponse(
        ok=True,
        message="Usuario desactivado correctamente.",
        item=build_membership_item(membership),
        limits=build_limits_summary(db, context.empresa),
    )
