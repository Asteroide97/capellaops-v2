import logging

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
    list_recent_movements,
    list_stock,
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
            detail="No se pudo crear el almacén inicial porque el codigo ya existe.",
        ) from exc

    db.refresh(warehouse)
    return serialize_warehouse(warehouse)


@router.get("/warehouses", response_model=WarehouseListResponse)
def list_warehouses(
    include_inactive: bool = True,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> WarehouseListResponse:
    query = select(Almacen).where(Almacen.empresa_id == context.empresa.id).order_by(Almacen.nombre.asc())
    if not include_inactive:
        query = query.where(Almacen.activo == True)

    warehouses = db.scalars(query).all()
    return WarehouseListResponse(items=[serialize_warehouse(warehouse) for warehouse in warehouses])


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
            detail="No se pudo crear el almacen porque el codigo ya existe.",
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
    warehouse = db.scalar(
        select(Almacen).where(
            Almacen.id == warehouse_id,
            Almacen.empresa_id == context.empresa.id,
        )
    )
    if not warehouse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Almacen no encontrado.")

    if payload.nombre is not None:
        warehouse.nombre = payload.nombre.strip()
        if not warehouse.nombre:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre obligatorio.")
    if payload.codigo is not None:
        next_code = payload.codigo.strip().upper().replace(" ", "-")
        if not next_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Codigo obligatorio.")
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
                detail="Ya existe un almacen con ese codigo.",
            )
        warehouse.codigo = next_code
    if payload.descripcion is not None:
        warehouse.descripcion = payload.descripcion.strip() or None
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
            detail="No se pudo actualizar el almacen porque el codigo ya existe.",
        ) from exc

    db.refresh(warehouse)
    return serialize_warehouse(warehouse)


@router.get("/materials", response_model=MaterialListResponse)
def list_materials(
    include_inactive: bool = True,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MaterialListResponse:
    query = select(Material).where(Material.empresa_id == context.empresa.id).order_by(Material.nombre.asc())
    if not include_inactive:
        query = query.where(Material.activo == True)

    materials = db.scalars(query).all()
    return MaterialListResponse(items=[serialize_material(material) for material in materials])


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
            detail="Ya existe un material con ese SKU.",
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
            detail="No se pudo crear el material porque el SKU ya existe.",
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
    return get_kardex(db, context.empresa.id, material_id, almacen_id)


@router.put("/materials/{material_id}", response_model=MaterialItem)
def update_material(
    material_id: str,
    payload: MaterialUpdateRequest,
    request: Request,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MaterialItem:
    material = db.scalar(
        select(Material).where(
            Material.id == material_id,
            Material.empresa_id == context.empresa.id,
        )
    )
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material no encontrado.")

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
                detail="Ya existe un material con ese SKU.",
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
            detail="No se pudo actualizar el material porque el SKU ya existe.",
        ) from exc

    db.refresh(material)
    return serialize_material(material)


@router.get("/stock", response_model=StockListResponse)
def stock(
    almacen_id: str | None = None,
    material_id: str | None = None,
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> StockListResponse:
    return StockListResponse(items=list_stock(db, context.empresa.id, almacen_id, material_id))


@router.get("/movements", response_model=MovementListResponse)
def movements(
    limit: int = Query(default=25, ge=1, le=100),
    context: TenantContext = Depends(get_inventory_context),
    db: Session = Depends(get_db),
) -> MovementListResponse:
    return MovementListResponse(items=list_recent_movements(db, context.empresa.id, limit=limit))


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
