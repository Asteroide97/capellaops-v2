from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.models import EmpresaUsuario
from app.schemas.common import CompanyLimitsSummary, EmpresaSummary, MeResponse, MembershipSummary, UserSummary
from app.services.access import build_module_payload
from app.services.company import get_company_plan_limits


router = APIRouter(tags=["users"])


def parse_impersonation_ends_at(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def build_company_summary(empresa) -> EmpresaSummary:
    return EmpresaSummary(
        id=empresa.id,
        name=empresa.name,
        slug=empresa.slug,
        razon_social=empresa.razon_social,
        rfc=empresa.rfc,
        giro=empresa.giro,
        telefono=empresa.telefono,
        email_contacto=empresa.email_contacto,
        sitio_web=empresa.sitio_web,
        pais=empresa.pais,
        estado=empresa.estado,
        ciudad=empresa.ciudad,
        codigo_postal=empresa.codigo_postal,
        direccion=empresa.direccion,
        plan_code=empresa.plan_code,
        access_status=empresa.access_status,
        trial_ends_at=empresa.trial_ends_at,
        is_trial=empresa.access_status == "trial",
    )


@router.get("/me", response_model=MeResponse)
def me(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> MeResponse:
    memberships = db.scalars(
        select(EmpresaUsuario)
        .options(selectinload(EmpresaUsuario.empresa))
        .where(
            EmpresaUsuario.usuario_id == context.user.id,
            EmpresaUsuario.is_active == True,
        )
    ).all()
    limits = get_company_plan_limits(db, context.empresa)

    return MeResponse(
        user=UserSummary(
            id=context.user.id,
            email=context.user.email,
            full_name=context.user.full_name,
            is_superadmin=context.user.is_superadmin,
            role=context.membership.role,
        ),
        empresa=build_company_summary(context.empresa),
        membership=MembershipSummary(role=context.membership.role, is_active=context.membership.is_active),
        empresas=[
            build_company_summary(membership.empresa)
            for membership in memberships
            if membership.empresa is not None
        ],
        limits=CompanyLimitsSummary(
            max_usuarios=limits.max_usuarios,
            usuarios_actuales=limits.usuarios_actuales,
            max_almacenes=limits.max_almacenes,
            almacenes_actuales=limits.almacenes_actuales,
            max_facturas_mensuales=limits.max_facturas_mensuales,
            productos_ilimitados=limits.productos_ilimitados,
            ventas_ilimitadas=limits.ventas_ilimitadas,
        ),
        modules=build_module_payload(context.user, context.empresa),
        impersonation=bool(context.token_payload.get("impersonation")),
        impersonated_by=context.token_payload.get("impersonated_by"),
        impersonation_ends_at=parse_impersonation_ends_at(context.token_payload.get("impersonation_ends_at")),
    )
