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
    PosCatalogResponse,
    PosShiftCloseRequest,
    PosShiftManualMovementRequest,
    PosShiftOpenRequest,
    PosShiftResponse,
    PosTicketResponse,
    SaleCancelRequest,
    SaleCreateRequest,
    SaleListResponse,
    SaleResponse,
)
from app.services.inventory import get_warehouse_for_company
from app.services.pos import (
    add_shift_manual_movement,
    cancel_sale,
    close_shift,
    create_sale,
    get_active_shift_response,
    get_pos_catalog,
    get_sale_for_company,
    get_sale_ticket,
    list_sales,
    open_shift,
    serialize_sale_response,
    validate_pos_access,
)


router = APIRouter(prefix="/pos", tags=["pos"])
logger = logging.getLogger(__name__)
T = TypeVar("T")


def get_pos_context(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    validate_pos_access(context.user, context.empresa)
    return context


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


@router.get("/sales", response_model=SaleListResponse)
def get_sales(
    q: str | None = None,
    estatus: Literal["pagada", "cancelada"] | None = None,
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
            notas=payload.notas,
            items=payload.items,
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
