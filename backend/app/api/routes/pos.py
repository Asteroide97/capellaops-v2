import logging
from datetime import datetime
from typing import Callable, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.pos import (
    PosActiveShiftResponse,
    PosSaleAdjustmentListResponse,
    SaleApprovalDecisionRequest,
    PosSaleApprovalItem,
    PosSaleApprovalListResponse,
    PosSaleApprovalRequestResponse,
    PosCatalogResponse,
    PosInvoiceRequestListResponse,
    PosInvoiceRequestResponse,
    PosInvoiceRequestUpsertRequest,
    PosReportSummaryResponse,
    SaleEditableSummaryResponse,
    SaleApprovalRequest,
    SaleLineAddRequest,
    PosShiftCloseRequest,
    PosShiftListResponse,
    PosShiftManualMovementRequest,
    PosShiftOpenRequest,
    PosShiftReportResponse,
    PosShiftResponse,
    PosTicketResponse,
    SaleCancelRequest,
    SaleCreateRequest,
    SaleCrmLinkRequest,
    SaleLineDeleteRequest,
    SaleListResponse,
    SaleLineUpdateRequest,
    SaleRecalculateRequest,
    SaleResponse,
)
from app.services.inventory import get_warehouse_for_company
from app.services.pos import (
    add_shift_manual_movement,
    approve_sale_approval,
    cancel_sale,
    close_shift,
    create_suspended_sale,
    create_sale,
    delete_sale_line,
    get_active_shift_response,
    get_pos_catalog,
    get_pos_report_summary,
    get_sale_editable_summary,
    get_sale_for_company,
    get_sale_invoice_request,
    get_sale_ticket,
    get_shift_detail_response,
    get_shift_report,
    list_invoice_requests,
    list_pending_sale_approvals,
    list_sale_adjustments,
    list_sale_approvals,
    list_sales,
    list_shifts,
    link_sale_to_crm,
    open_shift,
    pay_suspended_sale,
    recalculate_sale_adjustments,
    reject_sale_approval,
    request_sale_approval,
    resume_suspended_sale,
    serialize_sale_response,
    add_sale_line,
    unlink_sale_from_crm,
    update_sale_line,
    upsert_sale_invoice_request,
    validate_pos_access,
)


router = APIRouter(prefix="/pos", tags=["pos"])
logger = logging.getLogger(__name__)
T = TypeVar("T")


def get_pos_context(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    validate_pos_access(context.user, context.empresa)
    return context


def can_manage_pos_approvals(context: TenantContext) -> bool:
    return bool(getattr(context.user, "is_superadmin", False) or context.membership.role in {"owner", "admin"})


def ensure_pos_approval_manager(context: TenantContext, detail: str) -> None:
    if not can_manage_pos_approvals(context):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def run_pos_write(db: Session, action: str, operation: Callable[[], T]) -> T:
    try:
        result = operation()
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Conflicto de integridad en POS durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo completar la operacion de POS.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error de base de datos en POS durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo completar la operacion de POS.",
        ) from exc


def validate_date_range(fecha_desde: datetime | None, fecha_hasta: datetime | None) -> None:
    if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_hasta no puede ser menor que fecha_desde.",
        )


@router.get("/shift/active", response_model=PosActiveShiftResponse)
def get_active_shift(
    warehouse_id: str,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosActiveShiftResponse:
    return get_active_shift_response(db, context.empresa.id, warehouse_id)


@router.post("/shift/open", response_model=PosShiftResponse, status_code=status.HTTP_201_CREATED)
def open_shift_endpoint(
    payload: PosShiftOpenRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosShiftResponse:
    return run_pos_write(
        db,
        "open_shift",
        lambda: open_shift(
            db,
            empresa=context.empresa,
            user=context.user,
            warehouse_id=payload.warehouse_id,
            fondo_inicial=payload.fondo_inicial,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/shift/close", response_model=PosShiftResponse)
def close_shift_endpoint(
    payload: PosShiftCloseRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosShiftResponse:
    return run_pos_write(
        db,
        "close_shift",
        lambda: close_shift(
            db,
            empresa=context.empresa,
            user=context.user,
            warehouse_id=payload.warehouse_id,
            efectivo_contado=payload.efectivo_contado,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/shift/manual-income", response_model=PosShiftResponse)
def manual_income_endpoint(
    payload: PosShiftManualMovementRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosShiftResponse:
    return run_pos_write(
        db,
        "manual_income",
        lambda: add_shift_manual_movement(
            db,
            empresa=context.empresa,
            user=context.user,
            warehouse_id=payload.warehouse_id,
            movement_type="ingreso",
            amount=payload.monto,
            reason=payload.motivo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/shift/manual-withdrawal", response_model=PosShiftResponse)
def manual_withdrawal_endpoint(
    payload: PosShiftManualMovementRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosShiftResponse:
    return run_pos_write(
        db,
        "manual_withdrawal",
        lambda: add_shift_manual_movement(
            db,
            empresa=context.empresa,
            user=context.user,
            warehouse_id=payload.warehouse_id,
            movement_type="retiro",
            amount=payload.monto,
            reason=payload.motivo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/shifts", response_model=PosShiftListResponse)
def get_shifts(
    almacen_id: str | None = None,
    estatus: Literal["abierta", "cerrada", "cancelada"] | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    usuario_id: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosShiftListResponse:
    validate_date_range(fecha_desde, fecha_hasta)
    if almacen_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_id)

    total, items = list_shifts(
        db,
        context.empresa.id,
        almacen_id=almacen_id,
        estatus=estatus,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        usuario_id=usuario_id,
        limit=limit,
        offset=offset,
    )
    return PosShiftListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/shifts/{shift_id}", response_model=PosShiftResponse)
def get_shift_detail(
    shift_id: str,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosShiftResponse:
    return get_shift_detail_response(db, context.empresa.id, shift_id)


@router.get("/shifts/{shift_id}/report", response_model=PosShiftReportResponse)
def get_shift_report_endpoint(
    shift_id: str,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosShiftReportResponse:
    return get_shift_report(db, context.empresa.id, shift_id)


@router.get("/catalog", response_model=PosCatalogResponse)
def get_catalog(
    almacen_id: str,
    q: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosCatalogResponse:
    total, items = get_pos_catalog(
        db,
        context.empresa.id,
        almacen_id=almacen_id,
        q=q,
        limit=limit,
        offset=offset,
    )
    return PosCatalogResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/reports/summary", response_model=PosReportSummaryResponse)
def get_report_summary(
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    almacen_id: str | None = None,
    usuario_id: str | None = None,
    estatus: Literal["pagada", "cancelada", "suspendida"] | None = None,
    agrupacion: Literal["day", "week", "month"] = "day",
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosReportSummaryResponse:
    validate_date_range(fecha_desde, fecha_hasta)
    if almacen_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_id)

    return get_pos_report_summary(
        db,
        context.empresa.id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        almacen_id=almacen_id,
        usuario_id=usuario_id,
        estatus=estatus,
        agrupacion=agrupacion,
    )


@router.get("/sales", response_model=SaleListResponse)
def get_sales(
    q: str | None = None,
    estatus: Literal["pagada", "cancelada", "suspendida"] | None = None,
    almacen_id: str | None = None,
    metodo_pago: Literal["efectivo", "tarjeta", "transferencia", "mixto", "otro"] | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleListResponse:
    validate_date_range(fecha_desde, fecha_hasta)
    if almacen_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_id)

    total, items = list_sales(
        db,
        context.empresa.id,
        q=q,
        estatus=estatus,
        almacen_id=almacen_id,
        metodo_pago=metodo_pago,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset,
    )
    return SaleListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/sales/{sale_id}", response_model=SaleResponse)
def sale_detail(
    sale_id: str,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleResponse:
    sale = get_sale_for_company(db, context.empresa.id, sale_id)
    return serialize_sale_response(db, sale)


@router.get("/sales/{sale_id}/editable-summary", response_model=SaleEditableSummaryResponse)
def sale_editable_summary(
    sale_id: str,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleEditableSummaryResponse:
    return get_sale_editable_summary(db, empresa_id=context.empresa.id, sale_id=sale_id)


@router.post("/sales/{sale_id}/lines", response_model=SaleEditableSummaryResponse, status_code=status.HTTP_201_CREATED)
def add_sale_line_endpoint(
    sale_id: str,
    payload: SaleLineAddRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleEditableSummaryResponse:
    return run_pos_write(
        db,
        "add_sale_line",
        lambda: add_sale_line(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            item=payload,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/sales/{sale_id}/lines/{line_id}", response_model=SaleEditableSummaryResponse)
def update_sale_line_endpoint(
    sale_id: str,
    line_id: str,
    payload: SaleLineUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleEditableSummaryResponse:
    return run_pos_write(
        db,
        "update_sale_line",
        lambda: update_sale_line(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            line_id=line_id,
            payload=payload,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.delete("/sales/{sale_id}/lines/{line_id}", response_model=SaleEditableSummaryResponse)
def delete_sale_line_endpoint(
    sale_id: str,
    line_id: str,
    request: Request,
    payload: SaleLineDeleteRequest | None = None,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleEditableSummaryResponse:
    return run_pos_write(
        db,
        "delete_sale_line",
        lambda: delete_sale_line(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            line_id=line_id,
            motivo=payload.motivo if payload else None,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/sales/{sale_id}/recalculate", response_model=SaleEditableSummaryResponse)
def recalculate_sale_endpoint(
    sale_id: str,
    request: Request,
    payload: SaleRecalculateRequest | None = None,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleEditableSummaryResponse:
    return run_pos_write(
        db,
        "recalculate_sale",
        lambda: recalculate_sale_adjustments(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            descuento_global=payload.descuento_global if payload else None,
            motivo=payload.motivo if payload else None,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/sales/{sale_id}/approval-request", response_model=PosSaleApprovalRequestResponse)
def request_sale_approval_endpoint(
    sale_id: str,
    payload: SaleApprovalRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosSaleApprovalRequestResponse:
    return run_pos_write(
        db,
        "request_sale_approval",
        lambda: request_sale_approval(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            reason=payload.reason,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/sales/{sale_id}/approvals", response_model=PosSaleApprovalListResponse)
def get_sale_approvals_endpoint(
    sale_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosSaleApprovalListResponse:
    return list_sale_approvals(
        db,
        empresa_id=context.empresa.id,
        sale_id=sale_id,
        limit=limit,
        offset=offset,
    )


@router.post("/sales/{sale_id}/approvals/{approval_id}/approve", response_model=PosSaleApprovalItem)
def approve_sale_approval_endpoint(
    sale_id: str,
    approval_id: str,
    payload: SaleApprovalDecisionRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosSaleApprovalItem:
    ensure_pos_approval_manager(context, "No tienes permiso para autorizar ventas POS.")
    return run_pos_write(
        db,
        "approve_sale_approval",
        lambda: approve_sale_approval(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            approval_id=approval_id,
            note=payload.note,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/sales/{sale_id}/approvals/{approval_id}/reject", response_model=PosSaleApprovalItem)
def reject_sale_approval_endpoint(
    sale_id: str,
    approval_id: str,
    payload: SaleApprovalDecisionRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosSaleApprovalItem:
    ensure_pos_approval_manager(context, "No tienes permiso para rechazar ventas POS.")
    return run_pos_write(
        db,
        "reject_sale_approval",
        lambda: reject_sale_approval(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            approval_id=approval_id,
            note=payload.note,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/approvals/pending", response_model=PosSaleApprovalListResponse)
def get_pending_sale_approvals_endpoint(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosSaleApprovalListResponse:
    ensure_pos_approval_manager(context, "No tienes permiso para revisar autorizaciones pendientes de POS.")
    return list_pending_sale_approvals(
        db,
        empresa_id=context.empresa.id,
        limit=limit,
        offset=offset,
    )


@router.get("/sales/{sale_id}/adjustments", response_model=PosSaleAdjustmentListResponse)
def get_sale_adjustments_endpoint(
    sale_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosSaleAdjustmentListResponse:
    return list_sale_adjustments(
        db,
        empresa_id=context.empresa.id,
        sale_id=sale_id,
        limit=limit,
        offset=offset,
    )


@router.put("/sales/{sale_id}/crm-link", response_model=SaleResponse)
def link_sale_to_crm_endpoint(
    sale_id: str,
    payload: SaleCrmLinkRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleResponse:
    return run_pos_write(
        db,
        "link_sale_to_crm",
        lambda: link_sale_to_crm(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            cliente_id=payload.cliente_id,
            contacto_id=payload.contacto_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.delete("/sales/{sale_id}/crm-link", response_model=SaleResponse)
def unlink_sale_from_crm_endpoint(
    sale_id: str,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleResponse:
    return run_pos_write(
        db,
        "unlink_sale_from_crm",
        lambda: unlink_sale_from_crm(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/sales/{sale_id}/request-invoice", response_model=PosInvoiceRequestResponse)
def request_sale_invoice(
    sale_id: str,
    payload: PosInvoiceRequestUpsertRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosInvoiceRequestResponse:
    return run_pos_write(
        db,
        "request_sale_invoice",
        lambda: upsert_sale_invoice_request(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            cliente_nombre=payload.cliente_nombre,
            rfc=payload.rfc,
            razon_social=payload.razon_social,
            email=payload.email,
            uso_cfdi=payload.uso_cfdi,
            regimen_fiscal=payload.regimen_fiscal,
            codigo_postal=payload.codigo_postal,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
            audit_action="pos.sale.invoice_request.create",
        ),
    )


@router.get("/sales/{sale_id}/invoice-request", response_model=PosInvoiceRequestResponse)
def get_sale_invoice_request_endpoint(
    sale_id: str,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosInvoiceRequestResponse:
    return get_sale_invoice_request(db, context.empresa.id, sale_id)


@router.put("/sales/{sale_id}/invoice-request", response_model=PosInvoiceRequestResponse)
def update_sale_invoice_request(
    sale_id: str,
    payload: PosInvoiceRequestUpsertRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosInvoiceRequestResponse:
    return run_pos_write(
        db,
        "update_sale_invoice_request",
        lambda: upsert_sale_invoice_request(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            cliente_nombre=payload.cliente_nombre,
            rfc=payload.rfc,
            razon_social=payload.razon_social,
            email=payload.email,
            uso_cfdi=payload.uso_cfdi,
            regimen_fiscal=payload.regimen_fiscal,
            codigo_postal=payload.codigo_postal,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
            audit_action="pos.sale.invoice_request.update",
        ),
    )


@router.get("/invoice-requests", response_model=PosInvoiceRequestListResponse)
def get_invoice_requests(
    estado: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    rfc: str | None = None,
    folio: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosInvoiceRequestListResponse:
    validate_date_range(fecha_desde, fecha_hasta)
    total, items = list_invoice_requests(
        db,
        context.empresa.id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        rfc=rfc,
        folio=folio,
        limit=limit,
        offset=offset,
    )
    return PosInvoiceRequestListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/sales", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale_endpoint(
    payload: SaleCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleResponse:
    return run_pos_write(
        db,
        "create_sale",
        lambda: create_sale(
            db,
            empresa=context.empresa,
            user=context.user,
            almacen_id=payload.almacen_id,
            cliente_nombre=payload.cliente_nombre,
            cliente_email=payload.cliente_email,
            metodo_pago=payload.metodo_pago,
            monto_recibido=payload.monto_recibido,
            descuento_global=payload.descuento_global,
            notas=payload.notas,
            items=payload.items,
            payments=payload.payments,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/sales/suspend", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def suspend_sale_endpoint(
    payload: SaleCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleResponse:
    return run_pos_write(
        db,
        "suspend_sale",
        lambda: create_suspended_sale(
            db,
            empresa=context.empresa,
            user=context.user,
            almacen_id=payload.almacen_id,
            cliente_nombre=payload.cliente_nombre,
            cliente_email=payload.cliente_email,
            metodo_pago=payload.metodo_pago,
            descuento_global=payload.descuento_global,
            notas=payload.notas,
            items=payload.items,
            payments=payload.payments,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/sales/{sale_id}/resume", response_model=SaleResponse)
def resume_sale_endpoint(
    sale_id: str,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleResponse:
    return resume_suspended_sale(
        db,
        empresa=context.empresa,
        user=context.user,
        sale_id=sale_id,
    )


@router.post("/sales/{sale_id}/pay", response_model=SaleResponse)
def pay_suspended_sale_endpoint(
    sale_id: str,
    payload: SaleCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleResponse:
    return run_pos_write(
        db,
        "pay_suspended_sale",
        lambda: pay_suspended_sale(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            almacen_id=payload.almacen_id,
            cliente_nombre=payload.cliente_nombre,
            cliente_email=payload.cliente_email,
            metodo_pago=payload.metodo_pago,
            monto_recibido=payload.monto_recibido,
            descuento_global=payload.descuento_global,
            notas=payload.notas,
            items=payload.items,
            payments=payload.payments,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/sales/{sale_id}/cancel", response_model=SaleResponse)
def cancel_sale_endpoint(
    sale_id: str,
    payload: SaleCancelRequest,
    request: Request,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> SaleResponse:
    return run_pos_write(
        db,
        "cancel_sale",
        lambda: cancel_sale(
            db,
            empresa=context.empresa,
            user=context.user,
            sale_id=sale_id,
            reason=payload.reason,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/ticket/{sale_id}", response_model=PosTicketResponse)
def sale_ticket(
    sale_id: str,
    context: TenantContext = Depends(get_pos_context),
    db: Session = Depends(get_db),
) -> PosTicketResponse:
    sale = get_sale_for_company(db, context.empresa.id, sale_id)
    return get_sale_ticket(db, sale)
