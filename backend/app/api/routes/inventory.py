import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.models import AuditLog
from app.models.inventory import Almacen, Material
from app.schemas.inventory import (
    InventoryMovementCreateRequest,
    InventoryOnboardingStatusResponse,
    KardexResponse,
    MaterialCreateRequest,
    MaterialItem,
    MaterialListResponse,
    MaterialUpdateRequest,
    MovementItem,
    MovementListResponse,
    StockListResponse,
    WarehouseCreateRequest,
    WarehouseItem,
    WarehouseListResponse,
    WarehouseUpdateRequest,
)
from app.services.inventory import (
    apply_inventory_movement,
    count_active_warehouses,
    create_warehouse_record,
    get_kardex,
    get_material_for_company,
    get_warehouse_for_company,
    list_materials,
    list_recent_movements,
    list_stock,
    list_warehouses,
    normalize_code,
    normalize_optional_text,
    normalize_required_text,
    serialize_material,
    serialize_warehouse,
    validate_inventory_access,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])
logger = logging.getLogger(__name__)


def get_inventory_context(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    validate_inventory_access(context.user, context.empresa)
    return context


@router.get("/onboarding-status", response_model=InventoryOnboardingStatusResponse)
def onboarding_status(
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> InventoryOnboardingStatusResponse:
    try:
        warehouses_count = count_active_warehouses(db, context.empresa.id)
        requires_first_warehouse = warehouses_count == 0
        return InventoryOnboardingStatusResponse(
            requires_first_warehouse=requires_first_warehouse,
            warehouses_count=warehouses_count,
            message="Crea tu primer almacén para comenzar.",
        )
    except SQLAlchemyError as exc:
        logger.exception(
            "No se pudo consultar el estado de onboarding de inventario para empresa_id=%s.",
            context.empresa.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo consultar el estado de onboarding.",
        ) from exc


@router.post("/first-warehouse", response_model=WarehouseItem, status_code=status.HTTP_201_CREATED)
def create_first_warehouse(
    payload: WarehouseCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> WarehouseItem:
    try:
        warehouse = create_warehouse_record(
            db,
            empresa=context.empresa,
            user=context.user,
            nombre=payload.nombre,
            codigo=payload.codigo,
            descripcion=payload.descripcion,
            activo=True,
            ip_address=request.client.host if request.client else None,
            audit_action="inventory.onboarding.first_warehouse.create",
            fail_if_active_exists=True,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Código de almacén ya existe en esta empresa.",
        ) from exc

    db.refresh(warehouse)
    return serialize_warehouse(warehouse)


@router.get("/warehouses", response_model=WarehouseListResponse)
def get_warehouses(
    q: str | None = None,
    activo: bool | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> WarehouseListResponse:
    total, items = list_warehouses(
        db,
        context.empresa.id,
        q=q,
        activo=activo,
        limit=limit,
        offset=offset,
    )
    return WarehouseListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseItem)
def warehouse_detail(
    warehouse_id: str,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> WarehouseItem:
    warehouse = get_warehouse_for_company(db, context.empresa.id, warehouse_id)
    return serialize_warehouse(warehouse)


@router.post("/warehouses", response_model=WarehouseItem, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    payload: WarehouseCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> WarehouseItem:
    try:
        warehouse = create_warehouse_record(
            db,
            empresa=context.empresa,
            user=context.user,
            nombre=payload.nombre,
            codigo=payload.codigo,
            descripcion=payload.descripcion,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Código de almacén ya existe en esta empresa.",
        ) from exc

    db.refresh(warehouse)
    return serialize_warehouse(warehouse)


@router.put("/warehouses/{warehouse_id}", response_model=WarehouseItem)
def update_warehouse(
    warehouse_id: str,
    payload: WarehouseUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> WarehouseItem:
    warehouse = get_warehouse_for_company(db, context.empresa.id, warehouse_id)

    if payload.nombre is not None:
        warehouse.nombre = normalize_required_text(payload.nombre, "Nombre")
    if payload.codigo is not None:
        next_code = normalize_code(payload.codigo, "Código")
        existing = db.scalar(
            select(Almacen.id).where(
                Almacen.empresa_id == context.empresa.id,
                Almacen.codigo == next_code,
                Almacen.id != warehouse.id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Código de almacén ya existe en esta empresa.",
            )
        warehouse.codigo = next_code
    if payload.descripcion is not None:
        warehouse.descripcion = normalize_optional_text(payload.descripcion)
    if payload.activo is not None:
        warehouse.activo = payload.activo

    db.add(
        AuditLog(
            empresa_id=context.empresa.id,
            usuario_id=context.user.id,
            action="inventory.warehouse.update",
            entity_name="almacen",
            entity_id=warehouse.id,
            ip_address=request.client.host if request.client else None,
            metadata_json={"codigo": warehouse.codigo, "nombre": warehouse.nombre, "activo": warehouse.activo},
        )
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Código de almacén ya existe en esta empresa.",
        ) from exc

    db.refresh(warehouse)
    return serialize_warehouse(warehouse)


@router.get("/materials", response_model=MaterialListResponse)
def get_materials(
    q: str | None = None,
    categoria: str | None = None,
    activo: bool | None = None,
    stock_bajo: bool | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MaterialListResponse:
    total, items = list_materials(
        db,
        context.empresa.id,
        q=q,
        categoria=categoria,
        activo=activo,
        stock_bajo=stock_bajo,
        limit=limit,
        offset=offset,
    )
    return MaterialListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/materials/{material_id}", response_model=MaterialItem)
def material_detail(
    material_id: str,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MaterialItem:
    material = get_material_for_company(db, context.empresa.id, material_id)
    return serialize_material(material)


@router.post("/materials", response_model=MaterialItem, status_code=status.HTTP_201_CREATED)
def create_material(
    payload: MaterialCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MaterialItem:
    sku = normalize_code(payload.sku, "SKU")
    nombre = normalize_required_text(payload.nombre, "Nombre")
    unidad = normalize_required_text(payload.unidad, "Unidad")

    existing = db.scalar(
        select(Material.id).where(
            Material.empresa_id == context.empresa.id,
            Material.sku == sku,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SKU ya existe en esta empresa.",
        )

    material = Material(
        empresa_id=context.empresa.id,
        sku=sku,
        nombre=nombre,
        descripcion=normalize_optional_text(payload.descripcion),
        categoria=normalize_optional_text(payload.categoria),
        unidad=unidad,
        costo_unitario=payload.costo_unitario,
        precio_venta=payload.precio_venta,
        stock_minimo=payload.stock_minimo,
        activo=payload.activo,
    )
    db.add(material)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=context.empresa.id,
            usuario_id=context.user.id,
            action="inventory.material.create",
            entity_name="material",
            entity_id=material.id,
            ip_address=request.client.host if request.client else None,
            metadata_json={"sku": material.sku, "nombre": material.nombre},
        )
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SKU ya existe en esta empresa.",
        ) from exc

    db.refresh(material)
    return serialize_material(material)


@router.get("/materials/{material_id}/kardex", response_model=KardexResponse)
def material_kardex(
    material_id: str,
    almacen_id: str | None = None,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> KardexResponse:
    if almacen_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_id)
    return get_kardex(db, context.empresa.id, material_id, almacen_id)


@router.put("/materials/{material_id}", response_model=MaterialItem)
def update_material(
    material_id: str,
    payload: MaterialUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MaterialItem:
    material = get_material_for_company(db, context.empresa.id, material_id)

    if payload.sku is not None:
        next_sku = normalize_code(payload.sku, "SKU")
        existing = db.scalar(
            select(Material.id).where(
                Material.empresa_id == context.empresa.id,
                Material.sku == next_sku,
                Material.id != material.id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="SKU ya existe en esta empresa.",
            )
        material.sku = next_sku
    if payload.nombre is not None:
        material.nombre = normalize_required_text(payload.nombre, "Nombre")
    if payload.descripcion is not None:
        material.descripcion = normalize_optional_text(payload.descripcion)
    if payload.categoria is not None:
        material.categoria = normalize_optional_text(payload.categoria)
    if payload.unidad is not None:
        material.unidad = normalize_required_text(payload.unidad, "Unidad")
    if payload.costo_unitario is not None:
        material.costo_unitario = payload.costo_unitario
    if payload.precio_venta is not None:
        material.precio_venta = payload.precio_venta
    if payload.stock_minimo is not None:
        material.stock_minimo = payload.stock_minimo
    if payload.activo is not None:
        material.activo = payload.activo

    db.add(
        AuditLog(
            empresa_id=context.empresa.id,
            usuario_id=context.user.id,
            action="inventory.material.update",
            entity_name="material",
            entity_id=material.id,
            ip_address=request.client.host if request.client else None,
            metadata_json={"sku": material.sku, "nombre": material.nombre, "activo": material.activo},
        )
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SKU ya existe en esta empresa.",
        ) from exc

    db.refresh(material)
    return serialize_material(material)


@router.get("/stock", response_model=StockListResponse)
def get_stock(
    almacen_id: str | None = None,
    material_id: str | None = None,
    q: str | None = None,
    stock_bajo: bool | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> StockListResponse:
    if almacen_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_id)
    if material_id:
        get_material_for_company(db, context.empresa.id, material_id)

    total, items = list_stock(
        db,
        context.empresa.id,
        almacen_id=almacen_id,
        material_id=material_id,
        q=q,
        stock_bajo=stock_bajo,
        limit=limit,
        offset=offset,
    )
    return StockListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/movements", response_model=MovementListResponse)
def get_movements(
    almacen_id: str | None = None,
    material_id: str | None = None,
    tipo: Literal["entrada", "salida", "ajuste"] | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MovementListResponse:
    if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_hasta no puede ser menor que fecha_desde.",
        )
    if almacen_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_id)
    if material_id:
        get_material_for_company(db, context.empresa.id, material_id)

    total, items = list_recent_movements(
        db,
        context.empresa.id,
        almacen_id=almacen_id,
        material_id=material_id,
        tipo=tipo,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset,
    )
    return MovementListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/movements", response_model=MovementItem, status_code=status.HTTP_201_CREATED)
def create_inventory_movement(
    payload: InventoryMovementCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MovementItem:
    movement = apply_inventory_movement(
        db,
        user=context.user,
        empresa=context.empresa,
        almacen_id=payload.almacen_id,
        material_id=payload.material_id,
        tipo=payload.tipo,
        cantidad=payload.cantidad,
        cantidad_nueva=payload.cantidad_nueva,
        referencia_tipo=payload.referencia_tipo,
        referencia_id=payload.referencia_id,
        notas=payload.notas,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return movement
