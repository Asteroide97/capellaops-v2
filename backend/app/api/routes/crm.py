import logging
from datetime import datetime
from typing import Callable, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
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
    CRMClientCommercialSummaryResponse,
    CRMClientItem,
    CRMClientListResponse,
    CRMClientTimelineResponse,
    CRMClientUpdateRequest,
    CRMContactCreateRequest,
    CRMContactItem,
    CRMContactListResponse,
    CRMContactUpdateRequest,
    CRMCotizacionConversionResponse,
    CRMCotizacionConvertToProjectRequest,
    CRMCotizacionConvertToSaleRequest,
    CRMCotizacionCreate,
    CRMCotizacionListResponse,
    CRMCotizacionResponse,
    CRMCotizacionStatusUpdate,
    CRMCotizacionUpdate,
    CRMOpportunityCloseLostRequest,
    CRMOpportunityCloseWonRequest,
    CRMOpportunityCreateRequest,
    CRMOpportunityItem,
    CRMOpportunityListResponse,
    CRMOpportunityUpdateRequest,
    CRMSummaryResponse,
)
from app.services.documents_pdf import build_crm_quote_pdf
from app.services.crm import (
    build_crm_summary,
    cancel_crm_quote,
    close_opportunity_lost,
    close_opportunity_won,
    complete_activity,
    convert_crm_quote_to_project,
    convert_crm_quote_to_sale,
    create_activity,
    create_client,
    create_contact,
    create_crm_quote,
    create_opportunity,
    deactivate_activity,
    deactivate_contact,
    get_crm_quote,
    get_client_commercial_summary,
    get_client_timeline,
    get_client_for_company,
    get_opportunity_for_company,
    list_crm_quotes,
    list_activities,
    list_client_contacts,
    list_clients,
    list_opportunities,
    mark_crm_quote_sent,
    accept_crm_quote,
    reject_crm_quote,
    serialize_activity,
    serialize_client,
    serialize_contact,
    serialize_opportunity,
    update_crm_quote,
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


def run_crm_read(action: str, operation: Callable[[], T]) -> T:
    try:
        return operation()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Error de consulta en CRM durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo consultar la informacion de CRM.",
        ) from exc


@router.get("/summary", response_model=CRMSummaryResponse)
def crm_summary(
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMSummaryResponse:
    return run_crm_read("summary", lambda: build_crm_summary(db, context.empresa.id))


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


@router.get("/clients/{client_id}/timeline", response_model=CRMClientTimelineResponse)
def crm_client_timeline(
    client_id: str,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMClientTimelineResponse:
    return run_crm_read("client_timeline", lambda: get_client_timeline(db, context.empresa.id, client_id))


@router.get("/clients/{client_id}/commercial-summary", response_model=CRMClientCommercialSummaryResponse)
def crm_client_commercial_summary(
    client_id: str,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMClientCommercialSummaryResponse:
    return run_crm_read(
        "client_commercial_summary",
        lambda: get_client_commercial_summary(db, context.empresa.id, client_id),
    )


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


@router.get("/quotes", response_model=CRMCotizacionListResponse)
def crm_quotes(
    cliente_id: str | None = None,
    oportunidad_id: str | None = None,
    estatus: Literal["borrador", "enviada", "aceptada", "rechazada", "cancelada", "vencida"] | None = None,
    search: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionListResponse:
    def operation() -> CRMCotizacionListResponse:
        total, items = list_crm_quotes(
            db,
            context.empresa.id,
            client_id=cliente_id,
            opportunity_id=oportunidad_id,
            status_value=estatus,
            search=search,
            limit=limit,
            offset=offset,
        )
        return CRMCotizacionListResponse(items=items, total=total, limit=limit, offset=offset)

    return run_crm_read("quotes", operation)


@router.post("/quotes", response_model=CRMCotizacionResponse, status_code=status.HTTP_201_CREATED)
def crm_create_quote(
    payload: CRMCotizacionCreate,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionResponse:
    return run_crm_write(
        db,
        "create_quote",
        lambda: create_crm_quote(
            db,
            empresa=context.empresa,
            user=context.user,
            data=payload.model_dump(),
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/quotes/{quote_id}", response_model=CRMCotizacionResponse)
def crm_quote_detail(
    quote_id: str,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionResponse:
    return run_crm_read("quote_detail", lambda: get_crm_quote(db, context.empresa.id, quote_id))


@router.get("/quotes/{quote_id}/pdf")
def crm_quote_pdf(
    quote_id: str,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> Response:
    quote = run_crm_read("quote_pdf", lambda: get_crm_quote(db, context.empresa.id, quote_id))
    pdf_bytes, filename = build_crm_quote_pdf(context.empresa, quote)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/quotes/{quote_id}", response_model=CRMCotizacionResponse)
def crm_update_quote(
    quote_id: str,
    payload: CRMCotizacionUpdate,
    request: Request,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionResponse:
    return run_crm_write(
        db,
        "update_quote",
        lambda: update_crm_quote(
            db,
            empresa=context.empresa,
            user=context.user,
            quote_id=quote_id,
            data=payload.model_dump(exclude_unset=True),
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/quotes/{quote_id}/send", response_model=CRMCotizacionResponse)
def crm_send_quote(
    quote_id: str,
    request: Request,
    payload: CRMCotizacionStatusUpdate | None = None,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionResponse:
    return run_crm_write(
        db,
        "send_quote",
        lambda: mark_crm_quote_sent(
            db,
            empresa=context.empresa,
            user=context.user,
            quote_id=quote_id,
            notas=payload.notas if payload else None,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/quotes/{quote_id}/accept", response_model=CRMCotizacionResponse)
def crm_accept_quote(
    quote_id: str,
    request: Request,
    payload: CRMCotizacionStatusUpdate | None = None,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionResponse:
    return run_crm_write(
        db,
        "accept_quote",
        lambda: accept_crm_quote(
            db,
            empresa=context.empresa,
            user=context.user,
            quote_id=quote_id,
            notas=payload.notas if payload else None,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/quotes/{quote_id}/reject", response_model=CRMCotizacionResponse)
def crm_reject_quote(
    quote_id: str,
    request: Request,
    payload: CRMCotizacionStatusUpdate | None = None,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionResponse:
    return run_crm_write(
        db,
        "reject_quote",
        lambda: reject_crm_quote(
            db,
            empresa=context.empresa,
            user=context.user,
            quote_id=quote_id,
            notas=payload.notas if payload else None,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/quotes/{quote_id}/cancel", response_model=CRMCotizacionResponse)
def crm_cancel_quote(
    quote_id: str,
    request: Request,
    payload: CRMCotizacionStatusUpdate | None = None,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionResponse:
    return run_crm_write(
        db,
        "cancel_quote",
        lambda: cancel_crm_quote(
            db,
            empresa=context.empresa,
            user=context.user,
            quote_id=quote_id,
            notas=payload.notas if payload else None,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/quotes/{quote_id}/convert-to-project", response_model=CRMCotizacionConversionResponse)
def crm_convert_quote_to_project(
    quote_id: str,
    request: Request,
    payload: CRMCotizacionConvertToProjectRequest | None = None,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionConversionResponse:
    return run_crm_write(
        db,
        "convert_quote_to_project",
        lambda: convert_crm_quote_to_project(
            db,
            empresa=context.empresa,
            user=context.user,
            membership_role=context.membership.role,
            quote_id=quote_id,
            nombre_proyecto=payload.nombre_proyecto if payload else None,
            fecha_inicio=payload.fecha_inicio if payload else None,
            fecha_fin_estimada=payload.fecha_fin_estimada if payload else None,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/quotes/{quote_id}/convert-to-sale", response_model=CRMCotizacionConversionResponse)
def crm_convert_quote_to_sale(
    quote_id: str,
    request: Request,
    payload: CRMCotizacionConvertToSaleRequest | None = None,
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMCotizacionConversionResponse:
    return run_crm_write(
        db,
        "convert_quote_to_sale",
        lambda: convert_crm_quote_to_sale(
            db,
            empresa=context.empresa,
            user=context.user,
            quote_id=quote_id,
            caja_id=payload.caja_id if payload else None,
            notas=payload.notas if payload else None,
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
    cliente_id: str | None = None,
    client_id: str | None = Query(default=None, include_in_schema=False),
    oportunidad_id: str | None = None,
    opportunity_id: str | None = Query(default=None, include_in_schema=False),
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    vencidas: bool = False,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_crm_context),
    db: Session = Depends(get_db),
) -> CRMActivityListResponse:
    resolved_client_id = cliente_id or client_id
    resolved_opportunity_id = oportunidad_id or opportunity_id

    def operation() -> CRMActivityListResponse:
        total, items = list_activities(
            db,
            context.empresa.id,
            q=q,
            tipo=tipo,
            completada=completada,
            activo=activo,
            client_id=resolved_client_id,
            opportunity_id=resolved_opportunity_id,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            overdue_only=vencidas,
            limit=limit,
            offset=offset,
        )
        return CRMActivityListResponse(items=items, total=total, limit=limit, offset=offset)

    return run_crm_read("activities", operation)


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
