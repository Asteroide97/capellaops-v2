import logging
from typing import Callable, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.crm import (
    CRMActivityCreateRequest,
    CRMActivityItem,
    CRMActivityListResponse,
    CRMActivityUpdateRequest,
    CRMClientCreateRequest,
    CRMClientItem,
    CRMClientListResponse,
    CRMClientUpdateRequest,
    CRMContactCreateRequest,
    CRMContactItem,
    CRMContactListResponse,
    CRMContactUpdateRequest,
    CRMOpportunityCloseLostRequest,
    CRMOpportunityCloseWonRequest,
    CRMOpportunityCreateRequest,
    CRMOpportunityItem,
    CRMOpportunityListResponse,
    CRMOpportunityUpdateRequest,
    CRMSummaryResponse,
)
from app.services.crm import (
    build_crm_summary,
    close_opportunity_lost,
    close_opportunity_won,
    complete_activity,
    create_activity,
    create_client,
    create_contact,
    create_opportunity,
    deactivate_activity,
    deactivate_contact,
    get_client_for_company,
    get_opportunity_for_company,
    list_activities,
    list_client_contacts,
    list_clients,
    list_opportunities,
    serialize_activity,
    serialize_client,
    serialize_contact,
    serialize_opportunity,
    update_activity,
    update_client,
    update_contact,
    update_opportunity,
    validate_crm_access,
    set_client_status,
)


router = APIRouter(prefix="/crm", tags=["crm"])
logger = logging.getLogger(__name__)
T = TypeVar("T")


def get_crm_context(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    validate_crm_access(context.user, context.empresa)
    return context


def run_crm_write(db: Session, action: str, operation: Callable[[], T]) -> T:
    try:
        result = operation()
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Conflicto de integridad en CRM durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo completar la operacion de CRM.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error de base de datos en CRM durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo completar la operacion de CRM.",
        ) from exc


@router.get("/summary", response_model=CRMSummaryResponse)
def crm_summary(
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMSummaryResponse:
    return build_crm_summary(db, context.empresa.id)


@router.get("/clients", response_model=CRMClientListResponse)
def crm_clients(
    q: str | None = None,
    tipo: Literal["prospecto", "cliente", "otro"] | None = None,
    estatus: Literal["activo", "inactivo"] | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMClientListResponse:
    total, items = list_clients(
        db,
        context.empresa.id,
        q=q,
        tipo=tipo,
        estatus=estatus,
        limit=limit,
        offset=offset,
    )
    return CRMClientListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/clients", response_model=CRMClientItem, status_code=status.HTTP_201_CREATED)
def crm_create_client(
    payload: CRMClientCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMClientItem:
    return run_crm_write(
        db,
        "create_client",
        lambda: create_client(
            db,
            empresa=context.empresa,
            user=context.user,
            nombre_comercial=payload.nombre_comercial,
            razon_social=payload.razon_social,
            rfc=payload.rfc,
            tipo=payload.tipo,
            email=payload.email,
            telefono=payload.telefono,
            sitio_web=payload.sitio_web,
            direccion=payload.direccion,
            ciudad=payload.ciudad,
            estado=payload.estado,
            pais=payload.pais,
            codigo_postal=payload.codigo_postal,
            origen=payload.origen,
            industria=payload.industria,
            notas=payload.notas,
            estatus=payload.estatus,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/clients/{client_id}", response_model=CRMClientItem)
def crm_client_detail(
    client_id: str,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMClientItem:
    return serialize_client(get_client_for_company(db, context.empresa.id, client_id))


@router.put("/clients/{client_id}", response_model=CRMClientItem)
def crm_update_client(
    client_id: str,
    payload: CRMClientUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMClientItem:
    return run_crm_write(
        db,
        "update_client",
        lambda: update_client(
            db,
            empresa=context.empresa,
            user=context.user,
            client_id=client_id,
            nombre_comercial=payload.nombre_comercial,
            razon_social=payload.razon_social,
            rfc=payload.rfc,
            tipo=payload.tipo,
            email=payload.email,
            telefono=payload.telefono,
            sitio_web=payload.sitio_web,
            direccion=payload.direccion,
            ciudad=payload.ciudad,
            estado=payload.estado,
            pais=payload.pais,
            codigo_postal=payload.codigo_postal,
            origen=payload.origen,
            industria=payload.industria,
            notas=payload.notas,
            estatus=payload.estatus,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/clients/{client_id}/deactivate", response_model=CRMClientItem)
def crm_deactivate_client(
    client_id: str,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMClientItem:
    return run_crm_write(
        db,
        "deactivate_client",
        lambda: set_client_status(
            db,
            empresa=context.empresa,
            user=context.user,
            client_id=client_id,
            status_value="inactivo",
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/clients/{client_id}/reactivate", response_model=CRMClientItem)
def crm_reactivate_client(
    client_id: str,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMClientItem:
    return run_crm_write(
        db,
        "reactivate_client",
        lambda: set_client_status(
            db,
            empresa=context.empresa,
            user=context.user,
            client_id=client_id,
            status_value="activo",
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/clients/{client_id}/contacts", response_model=CRMContactListResponse)
def crm_list_contacts(
    client_id: str,
    q: str | None = None,
    activo: bool | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMContactListResponse:
    total, items = list_client_contacts(
        db,
        context.empresa.id,
        client_id,
        q=q,
        activo=activo,
        limit=limit,
        offset=offset,
    )
    return CRMContactListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/clients/{client_id}/contacts", response_model=CRMContactItem, status_code=status.HTTP_201_CREATED)
def crm_create_contact(
    client_id: str,
    payload: CRMContactCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMContactItem:
    return run_crm_write(
        db,
        "create_contact",
        lambda: create_contact(
            db,
            empresa=context.empresa,
            user=context.user,
            client_id=client_id,
            nombre=payload.nombre,
            puesto=payload.puesto,
            email=payload.email,
            telefono=payload.telefono,
            whatsapp=payload.whatsapp,
            principal=payload.principal,
            notas=payload.notas,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/contacts/{contact_id}", response_model=CRMContactItem)
def crm_update_contact(
    contact_id: str,
    payload: CRMContactUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMContactItem:
    return run_crm_write(
        db,
        "update_contact",
        lambda: update_contact(
            db,
            empresa=context.empresa,
            user=context.user,
            contact_id=contact_id,
            nombre=payload.nombre,
            puesto=payload.puesto,
            email=payload.email,
            telefono=payload.telefono,
            whatsapp=payload.whatsapp,
            principal=payload.principal,
            notas=payload.notas,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/contacts/{contact_id}/deactivate", response_model=CRMContactItem)
def crm_deactivate_contact(
    contact_id: str,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMContactItem:
    return run_crm_write(
        db,
        "deactivate_contact",
        lambda: deactivate_contact(
            db,
            empresa=context.empresa,
            user=context.user,
            contact_id=contact_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/opportunities", response_model=CRMOpportunityListResponse)
def crm_opportunities(
    q: str | None = None,
    etapa: Literal["nueva", "contactado", "propuesta", "negociacion", "ganada", "perdida"] | None = None,
    activa: bool | None = None,
    client_id: str | None = None,
    responsable_user_id: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMOpportunityListResponse:
    total, items = list_opportunities(
        db,
        context.empresa.id,
        q=q,
        etapa=etapa,
        activa=activa,
        client_id=client_id,
        responsible_user_id=responsable_user_id,
        limit=limit,
        offset=offset,
    )
    return CRMOpportunityListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/opportunities", response_model=CRMOpportunityItem, status_code=status.HTTP_201_CREATED)
def crm_create_opportunity(
    payload: CRMOpportunityCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMOpportunityItem:
    return run_crm_write(
        db,
        "create_opportunity",
        lambda: create_opportunity(
            db,
            empresa=context.empresa,
            user=context.user,
            client_id=payload.cliente_id,
            contacto_id=payload.contacto_id,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            etapa=payload.etapa,
            monto_estimado=payload.monto_estimado,
            probabilidad=payload.probabilidad,
            fecha_estimada_cierre=payload.fecha_estimada_cierre,
            responsable_user_id=payload.responsable_user_id,
            origen=payload.origen,
            motivo_perdida=payload.motivo_perdida,
            notas=payload.notas,
            activa=payload.activa,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/opportunities/{opportunity_id}", response_model=CRMOpportunityItem)
def crm_opportunity_detail(
    opportunity_id: str,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMOpportunityItem:
    return serialize_opportunity(get_opportunity_for_company(db, context.empresa.id, opportunity_id))


@router.put("/opportunities/{opportunity_id}", response_model=CRMOpportunityItem)
def crm_update_opportunity(
    opportunity_id: str,
    payload: CRMOpportunityUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMOpportunityItem:
    return run_crm_write(
        db,
        "update_opportunity",
        lambda: update_opportunity(
            db,
            empresa=context.empresa,
            user=context.user,
            opportunity_id=opportunity_id,
            client_id=payload.cliente_id,
            contacto_id=payload.contacto_id,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            etapa=payload.etapa,
            monto_estimado=payload.monto_estimado,
            probabilidad=payload.probabilidad,
            fecha_estimada_cierre=payload.fecha_estimada_cierre,
            responsable_user_id=payload.responsable_user_id,
            origen=payload.origen,
            motivo_perdida=payload.motivo_perdida,
            notas=payload.notas,
            activa=payload.activa,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/opportunities/{opportunity_id}/close-won", response_model=CRMOpportunityItem)
def crm_close_won(
    opportunity_id: str,
    request: Request,
    payload: CRMOpportunityCloseWonRequest | None = None,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMOpportunityItem:
    return run_crm_write(
        db,
        "close_opportunity_won",
        lambda: close_opportunity_won(
            db,
            empresa=context.empresa,
            user=context.user,
            opportunity_id=opportunity_id,
            notas=payload.notas if payload else None,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/opportunities/{opportunity_id}/close-lost", response_model=CRMOpportunityItem)
def crm_close_lost(
    opportunity_id: str,
    payload: CRMOpportunityCloseLostRequest,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMOpportunityItem:
    return run_crm_write(
        db,
        "close_opportunity_lost",
        lambda: close_opportunity_lost(
            db,
            empresa=context.empresa,
            user=context.user,
            opportunity_id=opportunity_id,
            motivo_perdida=payload.motivo_perdida,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/activities", response_model=CRMActivityListResponse)
def crm_activities(
    q: str | None = None,
    tipo: Literal["llamada", "email", "reunion", "tarea", "nota", "whatsapp", "otro"] | None = None,
    completada: bool | None = None,
    activo: bool | None = None,
    client_id: str | None = None,
    opportunity_id: str | None = None,
    vencidas: bool = False,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMActivityListResponse:
    total, items = list_activities(
        db,
        context.empresa.id,
        q=q,
        tipo=tipo,
        completada=completada,
        activo=activo,
        client_id=client_id,
        opportunity_id=opportunity_id,
        overdue_only=vencidas,
        limit=limit,
        offset=offset,
    )
    return CRMActivityListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/activities", response_model=CRMActivityItem, status_code=status.HTTP_201_CREATED)
def crm_create_activity(
    payload: CRMActivityCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMActivityItem:
    return run_crm_write(
        db,
        "create_activity",
        lambda: create_activity(
            db,
            empresa=context.empresa,
            user=context.user,
            cliente_id=payload.cliente_id,
            oportunidad_id=payload.oportunidad_id,
            contacto_id=payload.contacto_id,
            tipo=payload.tipo,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            fecha_actividad=payload.fecha_actividad,
            fecha_vencimiento=payload.fecha_vencimiento,
            completada=payload.completada,
            usuario_id=payload.usuario_id,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/activities/{activity_id}", response_model=CRMActivityItem)
def crm_update_activity(
    activity_id: str,
    payload: CRMActivityUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMActivityItem:
    return run_crm_write(
        db,
        "update_activity",
        lambda: update_activity(
            db,
            empresa=context.empresa,
            user=context.user,
            activity_id=activity_id,
            cliente_id=payload.cliente_id,
            oportunidad_id=payload.oportunidad_id,
            contacto_id=payload.contacto_id,
            tipo=payload.tipo,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            fecha_actividad=payload.fecha_actividad,
            fecha_vencimiento=payload.fecha_vencimiento,
            completada=payload.completada,
            usuario_id=payload.usuario_id,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/activities/{activity_id}/complete", response_model=CRMActivityItem)
def crm_complete_activity(
    activity_id: str,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMActivityItem:
    return run_crm_write(
        db,
        "complete_activity",
        lambda: complete_activity(
            db,
            empresa=context.empresa,
            user=context.user,
            activity_id=activity_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/activities/{activity_id}/deactivate", response_model=CRMActivityItem)
def crm_deactivate_activity(
    activity_id: str,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMActivityItem:
    return run_crm_write(
        db,
        "deactivate_activity",
        lambda: deactivate_activity(
            db,
            empresa=context.empresa,
            user=context.user,
            activity_id=activity_id,
            ip_address=request.client.host if request.client else None,
        ),
    )
