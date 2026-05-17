from fastapi import APIRouter, Depends

from app.api.deps import TenantContext, get_tenant_context
from app.schemas.module import ModulesResponse
from app.services.access import build_module_payload


router = APIRouter(tags=["modules"])


@router.get("/modules", response_model=ModulesResponse)
def list_modules(context: TenantContext = Depends(get_tenant_context)) -> ModulesResponse:
    return ModulesResponse(
        empresa_id=context.empresa.id,
        modules=build_module_payload(context.user, context.empresa),
    )

