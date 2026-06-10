import logging
from datetime import datetime
from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.billing import (
    BillingInvoiceActionRequest,
    BillingPosInvoiceRequestDetail,
    BillingPosInvoiceRequestListResponse,
)
from app.services.billing import (
    discard_billing_invoice_request,
    get_billing_pos_invoice_request_detail,
    list_billing_pos_invoice_requests,
    mark_billing_invoice_request_review,
    observe_billing_invoice_request,
    prepare_billing_invoice_request,
    validate_billing_queue_access,
)


router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)
T = TypeVar("T")


def get_billing_context(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    validate_billing_queue_access(context)
    return context


def run_billing_write(db: Session, action: str, operation: Callable[[], T]) -> T:
    try:
        result = operation()
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Conflicto de integridad en billing durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo completar la operación fiscal.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error de base de datos en billing durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo completar la operación fiscal.",
        ) from exc


def validate_date_range(fecha_desde: datetime | None, fecha_hasta: datetime | None) -> None:
    if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_hasta no puede ser menor que fecha_desde.",
        )


@router.get("/pos/invoice-requests", response_model=BillingPosInvoiceRequestListResponse)
def get_billing_pos_requests(
    estado: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    rfc: str | None = None,
    folio: str | None = None,
    cliente: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_billing_context),
    db: Session = Depends(get_db),
) -> BillingPosInvoiceRequestListResponse:
    validate_date_range(fecha_desde, fecha_hasta)
    total, items, kpis = list_billing_pos_invoice_requests(
        db,
        context.empresa.id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        rfc=rfc,
        folio=folio,
        cliente=cliente,
        limit=limit,
        offset=offset,
    )
    return BillingPosInvoiceRequestListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        kpis=kpis,
    )


@router.get("/pos/invoice-requests/{sale_id}", response_model=BillingPosInvoiceRequestDetail)
def get_billing_pos_request_detail(
    sale_id: str,
    context: TenantContext = Depends(get_billing_context),
    db: Session = Depends(get_db),
) -> BillingPosInvoiceRequestDetail:
    return get_billing_pos_invoice_request_detail(db, context.empresa.id, sale_id)


@router.post("/pos/invoice-requests/{sale_id}/review", response_model=BillingPosInvoiceRequestDetail)
def review_billing_pos_request(
    sale_id: str,
    payload: BillingInvoiceActionRequest,
    request: Request,
    context: TenantContext = Depends(get_billing_context),
    db: Session = Depends(get_db),
) -> BillingPosInvoiceRequestDetail:
    return run_billing_write(
        db,
        "review_billing_pos_request",
        lambda: mark_billing_invoice_request_review(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            nota=payload.nota,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/pos/invoice-requests/{sale_id}/observe", response_model=BillingPosInvoiceRequestDetail)
def observe_billing_pos_request(
    sale_id: str,
    payload: BillingInvoiceActionRequest,
    request: Request,
    context: TenantContext = Depends(get_billing_context),
    db: Session = Depends(get_db),
) -> BillingPosInvoiceRequestDetail:
    return run_billing_write(
        db,
        "observe_billing_pos_request",
        lambda: observe_billing_invoice_request(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            nota=payload.nota,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/pos/invoice-requests/{sale_id}/prepare", response_model=BillingPosInvoiceRequestDetail)
def prepare_billing_pos_request(
    sale_id: str,
    request: Request,
    context: TenantContext = Depends(get_billing_context),
    db: Session = Depends(get_db),
) -> BillingPosInvoiceRequestDetail:
    return run_billing_write(
        db,
        "prepare_billing_pos_request",
        lambda: prepare_billing_invoice_request(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/pos/invoice-requests/{sale_id}/discard", response_model=BillingPosInvoiceRequestDetail)
def discard_billing_pos_request(
    sale_id: str,
    payload: BillingInvoiceActionRequest,
    request: Request,
    context: TenantContext = Depends(get_billing_context),
    db: Session = Depends(get_db),
) -> BillingPosInvoiceRequestDetail:
    return run_billing_write(
        db,
        "discard_billing_pos_request",
        lambda: discard_billing_invoice_request(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            nota=payload.nota,
            ip_address=request.client.host if request.client else None,
        ),
    )
