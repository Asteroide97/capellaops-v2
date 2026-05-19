import logging
from typing import Callable, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.procurement import (
    PurchaseOrderCreateRequest,
    PurchaseOrderDetailCreateRequest,
    PurchaseOrderDetailUpdateRequest,
    PurchaseOrderListResponse,
    PurchaseOrderReceiveRequest,
    PurchaseOrderResponse,
    PurchaseOrderUpdateRequest,
    RequisitionCreateRequest,
    RequisitionDetailCreateRequest,
    RequisitionDetailUpdateRequest,
    RequisitionListResponse,
    RequisitionResponse,
    RequisitionUpdateRequest,
    SupplierCreateRequest,
    SupplierItem,
    SupplierListResponse,
    SupplierUpdateRequest,
)
from app.services.inventory import get_warehouse_for_company, validate_inventory_access
from app.services.procurement import (
    add_purchase_order_detail,
    add_requisition_detail,
    change_requisition_status,
    create_purchase_order,
    create_requisition,
    create_supplier,
    delete_purchase_order_detail,
    delete_requisition_detail,
    get_purchase_order_for_company,
    get_requisition_for_company,
    get_supplier_for_company,
    issue_purchase_order,
    list_purchase_orders,
    list_requisitions,
    list_suppliers,
    receive_purchase_order,
    serialize_purchase_order_response,
    serialize_requisition_response,
    serialize_supplier,
    update_purchase_order,
    update_purchase_order_detail,
    update_requisition,
    update_requisition_detail,
    update_supplier,
)


router = APIRouter(prefix="/inventory", tags=["inventory-procurement"])
logger = logging.getLogger(__name__)
T = TypeVar("T")


def get_inventory_context(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    validate_inventory_access(context.user, context.empresa)
    return context


def run_inventory_write(db: Session, action: str, operation: Callable[[], T]) -> T:
    try:
        result = operation()
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Conflicto de integridad en compras durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo completar la operacion de compras.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error de base de datos en compras durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo completar la operacion de compras.",
        ) from exc


@router.get("/suppliers", response_model=SupplierListResponse)
def get_suppliers(
    q: str | None = None,
    activo: bool | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> SupplierListResponse:
    total, items = list_suppliers(
        db,
        context.empresa.id,
        q=q,
        activo=activo,
        limit=limit,
        offset=offset,
    )
    return SupplierListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/suppliers", response_model=SupplierItem, status_code=status.HTTP_201_CREATED)
def create_supplier_endpoint(
    payload: SupplierCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> SupplierItem:
    return run_inventory_write(
        db,
        "create_supplier",
        lambda: create_supplier(
            db,
            empresa=context.empresa,
            user=context.user,
            nombre=payload.nombre,
            contacto_nombre=payload.contacto_nombre,
            correo=payload.correo,
            telefono=payload.telefono,
            direccion=payload.direccion,
            notas=payload.notas,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/suppliers/{supplier_id}", response_model=SupplierItem)
def supplier_detail(
    supplier_id: str,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> SupplierItem:
    supplier = get_supplier_for_company(db, context.empresa.id, supplier_id)
    return serialize_supplier(supplier)


@router.put("/suppliers/{supplier_id}", response_model=SupplierItem)
def update_supplier_endpoint(
    supplier_id: str,
    payload: SupplierUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> SupplierItem:
    return run_inventory_write(
        db,
        "update_supplier",
        lambda: update_supplier(
            db,
            empresa=context.empresa,
            user=context.user,
            supplier_id=supplier_id,
            nombre=payload.nombre,
            contacto_nombre=payload.contacto_nombre,
            correo=payload.correo,
            telefono=payload.telefono,
            direccion=payload.direccion,
            notas=payload.notas,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/requisitions", response_model=RequisitionListResponse)
def get_requisitions(
    q: str | None = None,
    estatus: Literal["borrador", "enviada", "aprobada", "rechazada", "surtida", "cancelada"] | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionListResponse:
    total, items = list_requisitions(
        db,
        context.empresa.id,
        q=q,
        estatus=estatus,
        limit=limit,
        offset=offset,
    )
    return RequisitionListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/requisitions", response_model=RequisitionResponse, status_code=status.HTTP_201_CREATED)
def create_requisition_endpoint(
    payload: RequisitionCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_inventory_write(
        db,
        "create_requisition",
        lambda: create_requisition(
            db,
            empresa=context.empresa,
            user=context.user,
            folio=payload.folio,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/requisitions/{requisition_id}", response_model=RequisitionResponse)
def requisition_detail(
    requisition_id: str,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, context.empresa.id, requisition_id)
    return serialize_requisition_response(db, requisition)


@router.put("/requisitions/{requisition_id}", response_model=RequisitionResponse)
def update_requisition_endpoint(
    requisition_id: str,
    payload: RequisitionUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_inventory_write(
        db,
        "update_requisition",
        lambda: update_requisition(
            db,
            empresa=context.empresa,
            user=context.user,
            requisition_id=requisition_id,
            folio=payload.folio,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/requisitions/{requisition_id}/details", response_model=RequisitionResponse)
def add_requisition_detail_endpoint(
    requisition_id: str,
    payload: RequisitionDetailCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_inventory_write(
        db,
        "add_requisition_detail",
        lambda: add_requisition_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            requisition_id=requisition_id,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/requisitions/{requisition_id}/details/{detail_id}", response_model=RequisitionResponse)
def update_requisition_detail_endpoint(
    requisition_id: str,
    detail_id: str,
    payload: RequisitionDetailUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_inventory_write(
        db,
        "update_requisition_detail",
        lambda: update_requisition_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            requisition_id=requisition_id,
            detail_id=detail_id,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.delete("/requisitions/{requisition_id}/details/{detail_id}", response_model=RequisitionResponse)
def delete_requisition_detail_endpoint(
    requisition_id: str,
    detail_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_inventory_write(
        db,
        "delete_requisition_detail",
        lambda: delete_requisition_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            requisition_id=requisition_id,
            detail_id=detail_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/requisitions/{requisition_id}/submit", response_model=RequisitionResponse)
def submit_requisition_endpoint(
    requisition_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_inventory_write(
        db,
        "submit_requisition",
        lambda: change_requisition_status(
            db,
            empresa=context.empresa,
            user=context.user,
            requisition_id=requisition_id,
            next_status="enviada",
            allowed_current_statuses={"borrador"},
            action="inventory.requisition.submit",
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/requisitions/{requisition_id}/approve", response_model=RequisitionResponse)
def approve_requisition_endpoint(
    requisition_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_inventory_write(
        db,
        "approve_requisition",
        lambda: change_requisition_status(
            db,
            empresa=context.empresa,
            user=context.user,
            requisition_id=requisition_id,
            next_status="aprobada",
            allowed_current_statuses={"enviada"},
            action="inventory.requisition.approve",
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/requisitions/{requisition_id}/reject", response_model=RequisitionResponse)
def reject_requisition_endpoint(
    requisition_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_inventory_write(
        db,
        "reject_requisition",
        lambda: change_requisition_status(
            db,
            empresa=context.empresa,
            user=context.user,
            requisition_id=requisition_id,
            next_status="rechazada",
            allowed_current_statuses={"enviada"},
            action="inventory.requisition.reject",
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/requisitions/{requisition_id}/cancel", response_model=RequisitionResponse)
def cancel_requisition_endpoint(
    requisition_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_inventory_write(
        db,
        "cancel_requisition",
        lambda: change_requisition_status(
            db,
            empresa=context.empresa,
            user=context.user,
            requisition_id=requisition_id,
            next_status="cancelada",
            allowed_current_statuses={"borrador", "enviada", "aprobada"},
            action="inventory.requisition.cancel",
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/purchase-orders", response_model=PurchaseOrderListResponse)
def get_purchase_orders(
    q: str | None = None,
    estatus: Literal["borrador", "emitida", "recibida_parcial", "recibida", "cancelada"] | None = None,
    proveedor_id: str | None = None,
    almacen_destino_id: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> PurchaseOrderListResponse:
    if proveedor_id:
        get_supplier_for_company(db, context.empresa.id, proveedor_id)
    if almacen_destino_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_destino_id)
    total, items = list_purchase_orders(
        db,
        context.empresa.id,
        q=q,
        estatus=estatus,
        proveedor_id=proveedor_id,
        almacen_destino_id=almacen_destino_id,
        limit=limit,
        offset=offset,
    )
    return PurchaseOrderListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/purchase-orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order_endpoint(
    payload: PurchaseOrderCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    return run_inventory_write(
        db,
        "create_purchase_order",
        lambda: create_purchase_order(
            db,
            empresa=context.empresa,
            user=context.user,
            folio=payload.folio,
            proveedor_id=payload.proveedor_id,
            almacen_destino_id=payload.almacen_destino_id,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/purchase-orders/{order_id}", response_model=PurchaseOrderResponse)
def purchase_order_detail(
    order_id: str,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    order = get_purchase_order_for_company(db, context.empresa.id, order_id)
    return serialize_purchase_order_response(db, order)


@router.put("/purchase-orders/{order_id}", response_model=PurchaseOrderResponse)
def update_purchase_order_endpoint(
    order_id: str,
    payload: PurchaseOrderUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    return run_inventory_write(
        db,
        "update_purchase_order",
        lambda: update_purchase_order(
            db,
            empresa=context.empresa,
            user=context.user,
            order_id=order_id,
            folio=payload.folio,
            proveedor_id=payload.proveedor_id,
            almacen_destino_id=payload.almacen_destino_id,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/purchase-orders/{order_id}/details", response_model=PurchaseOrderResponse)
def add_purchase_order_detail_endpoint(
    order_id: str,
    payload: PurchaseOrderDetailCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    return run_inventory_write(
        db,
        "add_purchase_order_detail",
        lambda: add_purchase_order_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            order_id=order_id,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            costo_unitario=payload.costo_unitario,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/purchase-orders/{order_id}/details/{detail_id}", response_model=PurchaseOrderResponse)
def update_purchase_order_detail_endpoint(
    order_id: str,
    detail_id: str,
    payload: PurchaseOrderDetailUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    return run_inventory_write(
        db,
        "update_purchase_order_detail",
        lambda: update_purchase_order_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            order_id=order_id,
            detail_id=detail_id,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            costo_unitario=payload.costo_unitario,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.delete("/purchase-orders/{order_id}/details/{detail_id}", response_model=PurchaseOrderResponse)
def delete_purchase_order_detail_endpoint(
    order_id: str,
    detail_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    return run_inventory_write(
        db,
        "delete_purchase_order_detail",
        lambda: delete_purchase_order_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            order_id=order_id,
            detail_id=detail_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/purchase-orders/{order_id}/issue", response_model=PurchaseOrderResponse)
def issue_purchase_order_endpoint(
    order_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    return run_inventory_write(
        db,
        "issue_purchase_order",
        lambda: issue_purchase_order(
            db,
            empresa=context.empresa,
            user=context.user,
            order_id=order_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/purchase-orders/{order_id}/receive", response_model=PurchaseOrderResponse)
def receive_purchase_order_endpoint(
    order_id: str,
    payload: PurchaseOrderReceiveRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    return run_inventory_write(
        db,
        "receive_purchase_order",
        lambda: receive_purchase_order(
            db,
            empresa=context.empresa,
            user=context.user,
            order_id=order_id,
            items=payload.items,
            ip_address=request.client.host if request.client else None,
        ),
    )
