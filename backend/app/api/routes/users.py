from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.models import EmpresaUsuario
from app.schemas.common import EmpresaSummary, MeResponse, MembershipSummary, UserSummary


router = APIRouter(tags=["users"])


def parse_impersonation_ends_at(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


@router.get("/me", response_model=MeResponse)
def me(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> MeResponse:
    memberships = db.scalars(
        select(EmpresaUsuario)
        .options(selectinload(EmpresaUsuario.empresa))
        .where(EmpresaUsuario.usuario_id == context.user.id)
    ).all()

    return MeResponse(
        user=UserSummary(
            id=context.user.id,
            email=context.user.email,
            full_name=context.user.full_name,
            is_superadmin=context.user.is_superadmin,
        ),
        empresa=EmpresaSummary(
            id=context.empresa.id,
            name=context.empresa.name,
            slug=context.empresa.slug,
            plan_code=context.empresa.plan_code,
            access_status=context.empresa.access_status,
            trial_ends_at=context.empresa.trial_ends_at,
        ),
        membership=MembershipSummary(role=context.membership.role),
        empresas=[
            EmpresaSummary(
                id=membership.empresa.id,
                name=membership.empresa.name,
                slug=membership.empresa.slug,
                plan_code=membership.empresa.plan_code,
                access_status=membership.empresa.access_status,
                trial_ends_at=membership.empresa.trial_ends_at,
            )
            for membership in memberships
            if membership.empresa is not None
        ],
        impersonation=bool(context.token_payload.get("impersonation")),
        impersonated_by=context.token_payload.get("impersonated_by"),
        impersonation_ends_at=parse_impersonation_ends_at(context.token_payload.get("impersonation_ends_at")),
    )
