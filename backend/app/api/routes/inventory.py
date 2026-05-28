import logging
from datetime import datetime
from typing import Callable, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.models import AuditLog
from app.models.inventory import Almacen, Material
from app.models.procurement import Proveedor
from app.schemas.inventory import (
    CountCreateRequest,
    CountDetailCreateRequest,
    CountDetailUpdateRequest,
    CountListResponse,
    CountResponse,
    InventoryBulkMovementCreateRequest,
    InventoryBulkMovementResponse,
    InventorySummaryResponse,
    CountUpdateRequest,
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
    TransferCreateRequest,
    TransferDetailCreateRequest,
    TransferDetailUpdateRequest,
    TransferListResponse,
    TransferResponse,
    TransferUpdateRequest,
    WarehouseCreateRequest,
    WarehouseItem,
    WarehouseListResponse,
    WarehouseUpdateRequest,
)
from app.services.inventory import (
    apply_inventory_movement,
    apply_bulk_inventory_movement,
    build_inventory_summary,
    count_active_warehouses,
    create_warehouse_record,
    dump_image_urls,
    get_kardex,
    get_material_for_company,
    get_material_item_for_company,
    get_warehouse_for_company,
    list_materials,
    list_recent_movements,
    list_stock,
    list_warehouses,
    normalize_barcode,
    normalize_code,
    normalize_optional_text,
    normalize_required_text,
    serialize_material,
    serialize_warehouse,
    validate_inventory_access,
)
from app.services.inventory_documents import (
    add_count_detail,
    add_transfer_detail,
    apply_count,
    cancel_count,
    cancel_transfer,
    confirm_transfer,
    create_count,
    create_transfer,
    delete_count_detail,
    delete_transfer_detail,
    get_count_for_company,
    get_transfer_for_company,
    list_counts,
    list_transfers,
    serialize_count_response,
    serialize_transfer_response,
    update_count,
    update_count_detail,
    update_transfer,
    update_transfer_detail,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])
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
        logger.exception("Conflicto de integridad en inventario durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo completar la operacion de inventario.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error de base de datos en inventario durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo completar la operacion de inventario.",
        ) from exc


def validate_date_range(fecha_desde: datetime | None, fecha_hasta: datetime | None) -> None:
    if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_hasta no puede ser menor que fecha_desde.",
        )


def get_supplier_for_company(db: Session, empresa_id: str, supplier_id: str) -> Proveedor:
    supplier = db.scalar(
        select(Proveedor).where(
            Proveedor.id == supplier_id,
            Proveedor.empresa_id == empresa_id,
        )
    )
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")
    return supplier


def ensure_material_supplier(
    db: Session,
    *,
    empresa_id: str,
    proveedor_principal_id: str | None,
) -> str | None:
    if proveedor_principal_id is None:
        return None
    supplier_id = normalize_optional_text(proveedor_principal_id)
    if not supplier_id:
        return None
    get_supplier_for_company(db, empresa_id, supplier_id)
    return supplier_id


def ensure_unique_barcode(
    db: Session,
    *,
    empresa_id: str,
    codigo_barras: str | None,
    material_id: str | None = None,
) -> str | None:
    barcode = normalize_barcode(codigo_barras)
    if not barcode:
        return None

    query = select(Material.id).where(
        Material.empresa_id == empresa_id,
        Material.codigo_barras == barcode,
    )
    if material_id:
        query = query.where(Material.id != material_id)

    existing = db.scalar(query)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Código de barras ya existe en esta empresa.",
        )
    return barcode


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
            message="Crea tu primer almacen para comenzar.",
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


@router.get("/summary", response_model=InventorySummaryResponse)
def inventory_summary(
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> InventorySummaryResponse:
    try:
        return build_inventory_summary(db, context.empresa.id)
    except SQLAlchemyError as exc:
        logger.exception(
            "No se pudo construir el resumen de inventario para empresa_id=%s.",
            context.empresa.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo cargar el resumen de inventario.",
        ) from exc


@router.post("/first-warehouse", response_model=WarehouseItem, status_code=status.HTTP_201_CREATED)
def create_first_warehouse(
    payload: WarehouseCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> WarehouseItem:
    def operation() -> WarehouseItem:
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
        db.flush()
        db.refresh(warehouse)
        return serialize_warehouse(warehouse)

    return run_inventory_write(db, "create_first_warehouse", operation)


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
    def operation() -> WarehouseItem:
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
        db.flush()
        db.refresh(warehouse)
        return serialize_warehouse(warehouse)

    return run_inventory_write(db, "create_warehouse", operation)


@router.put("/warehouses/{warehouse_id}", response_model=WarehouseItem)
def update_warehouse(
    warehouse_id: str,
    payload: WarehouseUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> WarehouseItem:
    def operation() -> WarehouseItem:
        warehouse = get_warehouse_for_company(db, context.empresa.id, warehouse_id)

        if payload.nombre is not None:
            warehouse.nombre = normalize_required_text(payload.nombre, "Nombre")
        if payload.codigo is not None:
            next_code = normalize_code(payload.codigo, "Codigo")
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
                    detail="Codigo de almacen ya existe en esta empresa.",
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
        db.flush()
        db.refresh(warehouse)
        return serialize_warehouse(warehouse)

    return run_inventory_write(db, "update_warehouse", operation)


@router.get("/materials", response_model=MaterialListResponse)
def get_materials(
    q: str | None = None,
    categoria: str | None = None,
    proveedor_principal_id: str | None = None,
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
        proveedor_principal_id=proveedor_principal_id,
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
    return get_material_item_for_company(db, context.empresa.id, material_id)


@router.post("/materials", response_model=MaterialItem, status_code=status.HTTP_201_CREATED)
def create_material(
    payload: MaterialCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MaterialItem:
    def operation() -> MaterialItem:
        sku = normalize_code(payload.sku, "SKU")
        nombre = normalize_required_text(payload.nombre, "Nombre")
        unidad = normalize_required_text(payload.unidad, "Unidad")
        proveedor_principal_id = ensure_material_supplier(
            db,
            empresa_id=context.empresa.id,
            proveedor_principal_id=payload.proveedor_principal_id,
        )
        codigo_barras = ensure_unique_barcode(
            db,
            empresa_id=context.empresa.id,
            codigo_barras=payload.codigo_barras,
        )

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
            categoria=normalize_required_text(payload.categoria, "Categoria"),
            subcategoria=normalize_optional_text(payload.subcategoria),
            unidad=unidad,
            imagen_url=normalize_optional_text(payload.imagen_url),
            imagenes_extra_json=dump_image_urls(payload.imagenes_extra),
            codigo_barras=codigo_barras,
            costo_unitario=payload.costo_unitario,
            costo_promedio_actual=payload.costo_promedio_actual or payload.costo_unitario,
            precio_venta=payload.precio_venta,
            stock_minimo=payload.stock_minimo,
            stock_maximo=payload.stock_maximo,
            ubicacion_texto=normalize_optional_text(payload.ubicacion_texto),
            proveedor_principal_id=proveedor_principal_id,
            lead_time_dias=payload.lead_time_dias,
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
                metadata_json={
                    "sku": material.sku,
                    "nombre": material.nombre,
                    "codigo_barras": material.codigo_barras,
                    "proveedor_principal_id": material.proveedor_principal_id,
                },
            )
        )
        db.refresh(material)
        return get_material_item_for_company(db, context.empresa.id, material.id)

    return run_inventory_write(db, "create_material", operation)


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
    def operation() -> MaterialItem:
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
        if payload.codigo_barras is not None:
            material.codigo_barras = ensure_unique_barcode(
                db,
                empresa_id=context.empresa.id,
                codigo_barras=payload.codigo_barras,
                material_id=material.id,
            )
        if payload.nombre is not None:
            material.nombre = normalize_required_text(payload.nombre, "Nombre")
        if payload.descripcion is not None:
            material.descripcion = normalize_optional_text(payload.descripcion)
        if payload.categoria is not None:
            material.categoria = normalize_required_text(payload.categoria, "Categoria")
        if payload.subcategoria is not None:
            material.subcategoria = normalize_optional_text(payload.subcategoria)
        if payload.unidad is not None:
            material.unidad = normalize_required_text(payload.unidad, "Unidad")
        if payload.imagen_url is not None:
            material.imagen_url = normalize_optional_text(payload.imagen_url)
        if payload.imagenes_extra is not None:
            material.imagenes_extra_json = dump_image_urls(payload.imagenes_extra)
        if payload.costo_unitario is not None:
            material.costo_unitario = payload.costo_unitario
            if payload.costo_promedio_actual is None and material.costo_promedio_actual in {None, 0}:
                material.costo_promedio_actual = payload.costo_unitario
        if payload.costo_promedio_actual is not None:
            material.costo_promedio_actual = payload.costo_promedio_actual
        if payload.precio_venta is not None:
            material.precio_venta = payload.precio_venta
        if payload.stock_minimo is not None:
            material.stock_minimo = payload.stock_minimo
        if payload.stock_maximo is not None:
            material.stock_maximo = payload.stock_maximo
        if payload.ubicacion_texto is not None:
            material.ubicacion_texto = normalize_optional_text(payload.ubicacion_texto)
        if payload.proveedor_principal_id is not None:
            material.proveedor_principal_id = ensure_material_supplier(
                db,
                empresa_id=context.empresa.id,
                proveedor_principal_id=payload.proveedor_principal_id,
            )
        if payload.lead_time_dias is not None:
            material.lead_time_dias = payload.lead_time_dias
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
                metadata_json={
                    "sku": material.sku,
                    "nombre": material.nombre,
                    "codigo_barras": material.codigo_barras,
                    "proveedor_principal_id": material.proveedor_principal_id,
                    "activo": material.activo,
                },
            )
        )
        db.flush()
        db.refresh(material)
        return get_material_item_for_company(db, context.empresa.id, material.id)

    return run_inventory_write(db, "update_material", operation)


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
    q: str | None = None,
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
    validate_date_range(fecha_desde, fecha_hasta)
    if almacen_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_id)
    if material_id:
        get_material_for_company(db, context.empresa.id, material_id)

    total, items = list_recent_movements(
        db,
        context.empresa.id,
        q=q,
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
    def operation() -> MovementItem:
        return apply_inventory_movement(
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
            motivo=payload.motivo,
            entregado_por=payload.entregado_por,
            recibido_por=payload.recibido_por,
            documento_referencia=payload.documento_referencia,
            evidencia_url=payload.evidencia_url,
            es_proyecto=payload.es_proyecto,
            proyecto_id=payload.proyecto_id,
            proyecto_nombre_snapshot=payload.proyecto_nombre_snapshot,
            costo_unitario=payload.costo_unitario,
        )

    return run_inventory_write(db, "create_inventory_movement", operation)


@router.post("/movements/bulk", response_model=InventoryBulkMovementResponse, status_code=status.HTTP_201_CREATED)
def create_inventory_movement_bulk(
    payload: InventoryBulkMovementCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> InventoryBulkMovementResponse:
    def operation() -> InventoryBulkMovementResponse:
        return apply_bulk_inventory_movement(
            db,
            user=context.user,
            empresa=context.empresa,
            almacen_id=payload.almacen_id,
            tipo=payload.tipo,
            items=payload.items,
            referencia_tipo=payload.referencia_tipo,
            referencia_id=payload.referencia_id,
            motivo=payload.motivo,
            entregado_por=payload.entregado_por,
            recibido_por=payload.recibido_por,
            documento_referencia=payload.documento_referencia,
            evidencia_url=payload.evidencia_url,
            es_proyecto=payload.es_proyecto,
            proyecto_id=payload.proyecto_id,
            proyecto_nombre_snapshot=payload.proyecto_nombre_snapshot,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        )

    return run_inventory_write(db, "create_inventory_movement_bulk", operation)


@router.get("/transfers", response_model=TransferListResponse)
def get_transfers(
    q: str | None = None,
    almacen_origen_id: str | None = None,
    almacen_destino_id: str | None = None,
    estatus: Literal["borrador", "confirmada", "cancelada"] | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> TransferListResponse:
    validate_date_range(fecha_desde, fecha_hasta)
    if almacen_origen_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_origen_id)
    if almacen_destino_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_destino_id)

    total, items = list_transfers(
        db,
        context.empresa.id,
        q=q,
        almacen_origen_id=almacen_origen_id,
        almacen_destino_id=almacen_destino_id,
        estatus=estatus,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset,
    )
    return TransferListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/transfers/{transfer_id}", response_model=TransferResponse)
def transfer_detail(
    transfer_id: str,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> TransferResponse:
    transfer = get_transfer_for_company(db, context.empresa.id, transfer_id)
    return serialize_transfer_response(db, transfer)


@router.post("/transfers", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer_endpoint(
    payload: TransferCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> TransferResponse:
    return run_inventory_write(
        db,
        "create_transfer",
        lambda: create_transfer(
            db,
            empresa=context.empresa,
            user=context.user,
            folio=payload.folio,
            almacen_origen_id=payload.almacen_origen_id,
            almacen_destino_id=payload.almacen_destino_id,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/transfers/{transfer_id}", response_model=TransferResponse)
def update_transfer_endpoint(
    transfer_id: str,
    payload: TransferUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> TransferResponse:
    return run_inventory_write(
        db,
        "update_transfer",
        lambda: update_transfer(
            db,
            empresa=context.empresa,
            user=context.user,
            transfer_id=transfer_id,
            folio=payload.folio,
            almacen_origen_id=payload.almacen_origen_id,
            almacen_destino_id=payload.almacen_destino_id,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/transfers/{transfer_id}/details", response_model=TransferResponse)
def add_transfer_detail_endpoint(
    transfer_id: str,
    payload: TransferDetailCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> TransferResponse:
    return run_inventory_write(
        db,
        "add_transfer_detail",
        lambda: add_transfer_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            transfer_id=transfer_id,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            costo_unitario_snapshot=payload.costo_unitario_snapshot,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/transfers/{transfer_id}/details/{detail_id}", response_model=TransferResponse)
def update_transfer_detail_endpoint(
    transfer_id: str,
    detail_id: str,
    payload: TransferDetailUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> TransferResponse:
    return run_inventory_write(
        db,
        "update_transfer_detail",
        lambda: update_transfer_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            transfer_id=transfer_id,
            detail_id=detail_id,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            costo_unitario_snapshot=payload.costo_unitario_snapshot,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.delete("/transfers/{transfer_id}/details/{detail_id}", response_model=TransferResponse)
def delete_transfer_detail_endpoint(
    transfer_id: str,
    detail_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> TransferResponse:
    return run_inventory_write(
        db,
        "delete_transfer_detail",
        lambda: delete_transfer_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            transfer_id=transfer_id,
            detail_id=detail_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/transfers/{transfer_id}/confirm", response_model=TransferResponse)
def confirm_transfer_endpoint(
    transfer_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> TransferResponse:
    return run_inventory_write(
        db,
        "confirm_transfer",
        lambda: confirm_transfer(
            db,
            empresa=context.empresa,
            user=context.user,
            transfer_id=transfer_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/transfers/{transfer_id}/cancel", response_model=TransferResponse)
def cancel_transfer_endpoint(
    transfer_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> TransferResponse:
    return run_inventory_write(
        db,
        "cancel_transfer",
        lambda: cancel_transfer(
            db,
            empresa=context.empresa,
            user=context.user,
            transfer_id=transfer_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/counts", response_model=CountListResponse)
def get_counts(
    q: str | None = None,
    almacen_id: str | None = None,
    estatus: Literal["borrador", "aplicado", "cancelado"] | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> CountListResponse:
    validate_date_range(fecha_desde, fecha_hasta)
    if almacen_id:
        get_warehouse_for_company(db, context.empresa.id, almacen_id)

    total, items = list_counts(
        db,
        context.empresa.id,
        q=q,
        almacen_id=almacen_id,
        estatus=estatus,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset,
    )
    return CountListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/counts/{count_id}", response_model=CountResponse)
def count_detail(
    count_id: str,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> CountResponse:
    count = get_count_for_company(db, context.empresa.id, count_id)
    return serialize_count_response(db, count)


@router.post("/counts", response_model=CountResponse, status_code=status.HTTP_201_CREATED)
def create_count_endpoint(
    payload: CountCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> CountResponse:
    return run_inventory_write(
        db,
        "create_count",
        lambda: create_count(
            db,
            empresa=context.empresa,
            user=context.user,
            folio=payload.folio,
            almacen_id=payload.almacen_id,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/counts/{count_id}", response_model=CountResponse)
def update_count_endpoint(
    count_id: str,
    payload: CountUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> CountResponse:
    return run_inventory_write(
        db,
        "update_count",
        lambda: update_count(
            db,
            empresa=context.empresa,
            user=context.user,
            count_id=count_id,
            folio=payload.folio,
            almacen_id=payload.almacen_id,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/counts/{count_id}/details", response_model=CountResponse)
def add_count_detail_endpoint(
    count_id: str,
    payload: CountDetailCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> CountResponse:
    return run_inventory_write(
        db,
        "add_count_detail",
        lambda: add_count_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            count_id=count_id,
            material_id=payload.material_id,
            cantidad_fisica=payload.cantidad_fisica,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/counts/{count_id}/details/{detail_id}", response_model=CountResponse)
def update_count_detail_endpoint(
    count_id: str,
    detail_id: str,
    payload: CountDetailUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> CountResponse:
    return run_inventory_write(
        db,
        "update_count_detail",
        lambda: update_count_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            count_id=count_id,
            detail_id=detail_id,
            material_id=payload.material_id,
            cantidad_fisica=payload.cantidad_fisica,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.delete("/counts/{count_id}/details/{detail_id}", response_model=CountResponse)
def delete_count_detail_endpoint(
    count_id: str,
    detail_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> CountResponse:
    return run_inventory_write(
        db,
        "delete_count_detail",
        lambda: delete_count_detail(
            db,
            empresa=context.empresa,
            user=context.user,
            count_id=count_id,
            detail_id=detail_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/counts/{count_id}/apply", response_model=CountResponse)
def apply_count_endpoint(
    count_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> CountResponse:
    return run_inventory_write(
        db,
        "apply_count",
        lambda: apply_count(
            db,
            empresa=context.empresa,
            user=context.user,
            count_id=count_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/counts/{count_id}/cancel", response_model=CountResponse)
def cancel_count_endpoint(
    count_id: str,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> CountResponse:
    return run_inventory_write(
        db,
        "cancel_count",
        lambda: cancel_count(
            db,
            empresa=context.empresa,
            user=context.user,
            count_id=count_id,
            ip_address=request.client.host if request.client else None,
        ),
    )
