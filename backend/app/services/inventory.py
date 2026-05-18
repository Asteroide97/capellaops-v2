from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Empresa, Usuario
from app.models.inventory import Almacen, Existencia, Material, MovimientoInventario
from app.schemas.inventory import (
    KardexResponse,
    KardexStockItem,
    MaterialItem,
    MovementItem,
    StockItem,
    WarehouseItem,
)
from app.services.access import can_access_module


ZERO = Decimal("0")


def normalize_required_text(value: str, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} obligatorio.")
    return cleaned


def normalize_code(value: str, field_name: str) -> str:
    cleaned = normalize_required_text(value, field_name)
    return cleaned.upper().replace(" ", "-")


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_query_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def validate_inventory_access(user: Usuario, empresa: Empresa) -> None:
    if not can_access_module(user, empresa, "inventory"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La empresa no tiene acceso al módulo Inventario.",
        )


def apply_text_search(query, q: str | None, *columns):
    normalized = normalize_query_text(q)
    if not normalized:
        return query

    pattern = f"%{normalized}%"
    filters = [func.lower(func.coalesce(column, "")).like(pattern) for column in columns]
    return query.where(or_(*filters))


def count_rows(db: Session, query) -> int:
    return db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0


def count_active_warehouses(db: Session, empresa_id: str) -> int:
    return db.scalar(
        select(func.count(Almacen.id)).where(
            Almacen.empresa_id == empresa_id,
            Almacen.activo == True,
        )
    ) or 0


def serialize_material(material: Material) -> MaterialItem:
    return MaterialItem(
        id=material.id,
        empresa_id=material.empresa_id,
        sku=material.sku,
        nombre=material.nombre,
        descripcion=material.descripcion,
        categoria=material.categoria,
        unidad=material.unidad,
        costo_unitario=material.costo_unitario,
        precio_venta=material.precio_venta,
        stock_minimo=material.stock_minimo,
        activo=material.activo,
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


def serialize_warehouse(warehouse: Almacen) -> WarehouseItem:
    return WarehouseItem(
        id=warehouse.id,
        empresa_id=warehouse.empresa_id,
        nombre=warehouse.nombre,
        codigo=warehouse.codigo,
        descripcion=warehouse.descripcion,
        activo=warehouse.activo,
        created_at=warehouse.created_at,
        updated_at=warehouse.updated_at,
    )


def serialize_stock_item(stock: Existencia, warehouse: Almacen, material: Material) -> StockItem:
    return StockItem(
        id=stock.id,
        empresa_id=stock.empresa_id,
        almacen_id=warehouse.id,
        almacen_nombre=warehouse.nombre,
        almacen_codigo=warehouse.codigo,
        material_id=material.id,
        material_sku=material.sku,
        material_nombre=material.nombre,
        material_unidad=material.unidad,
        stock_minimo=material.stock_minimo,
        cantidad=stock.cantidad,
        low_stock=Decimal(stock.cantidad) <= Decimal(material.stock_minimo),
        updated_at=stock.updated_at,
    )


def create_warehouse_record(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    nombre: str,
    codigo: str,
    descripcion: str | None,
    activo: bool,
    ip_address: str | None,
    audit_action: str = "inventory.warehouse.create",
    fail_if_active_exists: bool = False,
) -> Almacen:
    normalized_name = normalize_required_text(nombre, "Nombre")
    normalized_code = normalize_code(codigo, "Código")

    if fail_if_active_exists and count_active_warehouses(db, empresa.id) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La empresa ya tiene un almacén configurado.",
        )

    existing = db.scalar(
        select(Almacen.id).where(
            Almacen.empresa_id == empresa.id,
            Almacen.codigo == normalized_code,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Código de almacén ya existe en esta empresa.",
        )

    warehouse = Almacen(
        empresa_id=empresa.id,
        nombre=normalized_name,
        codigo=normalized_code,
        descripcion=normalize_optional_text(descripcion),
        activo=activo,
    )
    db.add(warehouse)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=empresa.id,
            usuario_id=user.id,
            action=audit_action,
            entity_name="almacen",
            entity_id=warehouse.id,
            ip_address=ip_address,
            metadata_json={"codigo": warehouse.codigo, "nombre": warehouse.nombre, "activo": warehouse.activo},
        )
    )
    return warehouse


def get_warehouse_for_company(db: Session, empresa_id: str, warehouse_id: str) -> Almacen:
    warehouse = db.scalar(
        select(Almacen).where(
            Almacen.id == warehouse_id,
            Almacen.empresa_id == empresa_id,
        )
    )
    if not warehouse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Almacén no encontrado.")
    return warehouse


def get_material_for_company(db: Session, empresa_id: str, material_id: str) -> Material:
    material = db.scalar(
        select(Material).where(
            Material.id == material_id,
            Material.empresa_id == empresa_id,
        )
    )
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material no encontrado.")
    return material


def get_or_create_stock(
    db: Session,
    empresa_id: str,
    almacen_id: str,
    material_id: str,
) -> Existencia:
    stock = db.scalar(
        select(Existencia)
        .where(
            Existencia.empresa_id == empresa_id,
            Existencia.almacen_id == almacen_id,
            Existencia.material_id == material_id,
        )
        .with_for_update()
    )
    if stock:
        return stock

    stock = Existencia(
        empresa_id=empresa_id,
        almacen_id=almacen_id,
        material_id=material_id,
        cantidad=ZERO,
    )
    db.add(stock)
    db.flush()
    return stock


def build_movement_item(movement: MovimientoInventario, warehouse: Almacen, material: Material) -> MovementItem:
    return MovementItem(
        id=movement.id,
        empresa_id=movement.empresa_id,
        almacen_id=movement.almacen_id,
        almacen_nombre=warehouse.nombre,
        material_id=movement.material_id,
        material_sku=material.sku,
        material_nombre=material.nombre,
        tipo=movement.tipo,
        cantidad=movement.cantidad,
        cantidad_anterior=movement.cantidad_anterior,
        cantidad_nueva=movement.cantidad_nueva,
        referencia_tipo=movement.referencia_tipo,
        referencia_id=movement.referencia_id,
        notas=movement.notas,
        created_by=movement.created_by,
        created_at=movement.created_at,
    )


def apply_inventory_movement(
    db: Session,
    *,
    user: Usuario,
    empresa: Empresa,
    almacen_id: str,
    material_id: str,
    tipo: str,
    cantidad: Decimal | None,
    cantidad_nueva: Decimal | None,
    referencia_tipo: str | None,
    referencia_id: str | None,
    notas: str | None,
    ip_address: str | None,
) -> MovementItem:
    validate_inventory_access(user, empresa)
    warehouse = get_warehouse_for_company(db, empresa.id, almacen_id)
    material = get_material_for_company(db, empresa.id, material_id)
    stock = get_or_create_stock(db, empresa.id, almacen_id, material_id)

    previous_quantity = Decimal(stock.cantidad)

    if tipo == "entrada":
        if cantidad is None or cantidad <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad debe ser mayor a 0 para una entrada.",
            )
        movement_quantity = Decimal(cantidad)
        next_quantity = previous_quantity + movement_quantity
    elif tipo == "salida":
        if cantidad is None or cantidad <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad debe ser mayor a 0 para una salida.",
            )
        movement_quantity = Decimal(cantidad)
        if previous_quantity < movement_quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Stock insuficiente.",
            )
        next_quantity = previous_quantity - movement_quantity
    elif tipo == "ajuste":
        if cantidad_nueva is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cantidad_nueva es obligatoria para un ajuste.",
            )
        if cantidad_nueva < ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad nueva no puede ser negativa.",
            )
        next_quantity = Decimal(cantidad_nueva)
        movement_quantity = next_quantity - previous_quantity
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de movimiento inválido.")

    if next_quantity < ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La existencia no puede quedar en negativo.",
        )

    stock.cantidad = next_quantity
    movement = MovimientoInventario(
        empresa_id=empresa.id,
        almacen_id=warehouse.id,
        material_id=material.id,
        tipo=tipo,
        cantidad=movement_quantity,
        cantidad_anterior=previous_quantity,
        cantidad_nueva=next_quantity,
        referencia_tipo=normalize_optional_text(referencia_tipo) or "manual",
        referencia_id=normalize_optional_text(referencia_id),
        notas=normalize_optional_text(notas),
        created_by=user.id,
    )
    db.add(movement)
    db.flush()

    db.add(
        AuditLog(
            empresa_id=empresa.id,
            usuario_id=user.id,
            action=f"inventory.movement.{tipo}",
            entity_name="movimiento_inventario",
            entity_id=movement.id,
            ip_address=ip_address,
            metadata_json={
                "almacen_id": warehouse.id,
                "material_id": material.id,
                "cantidad": str(movement.cantidad),
                "cantidad_anterior": str(previous_quantity),
                "cantidad_nueva": str(next_quantity),
                "referencia_tipo": movement.referencia_tipo,
            },
        )
    )

    return build_movement_item(movement, warehouse, material)


def list_warehouses(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    activo: bool | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[WarehouseItem]]:
    query = select(Almacen).where(Almacen.empresa_id == empresa_id)
    query = apply_text_search(query, q, Almacen.nombre, Almacen.codigo, Almacen.descripcion)

    if activo is not None:
        query = query.where(Almacen.activo == activo)

    total = count_rows(db, query)
    rows = db.scalars(
        query.order_by(Almacen.nombre.asc(), Almacen.codigo.asc()).offset(offset).limit(limit)
    ).all()
    return total, [serialize_warehouse(warehouse) for warehouse in rows]


def list_materials(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    categoria: str | None = None,
    activo: bool | None = None,
    stock_bajo: bool | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[MaterialItem]]:
    query = select(Material).where(Material.empresa_id == empresa_id)
    query = apply_text_search(query, q, Material.sku, Material.nombre, Material.descripcion, Material.categoria)

    normalized_category = normalize_query_text(categoria)
    if normalized_category:
        query = query.where(func.lower(func.coalesce(Material.categoria, "")) == normalized_category)
    if activo is not None:
        query = query.where(Material.activo == activo)

    if stock_bajo is not None:
        stock_totals = (
            select(
                Existencia.material_id.label("material_id"),
                func.coalesce(func.sum(Existencia.cantidad), 0).label("total_stock"),
            )
            .where(Existencia.empresa_id == empresa_id)
            .group_by(Existencia.material_id)
            .subquery()
        )
        total_stock = func.coalesce(stock_totals.c.total_stock, 0)
        query = query.outerjoin(stock_totals, stock_totals.c.material_id == Material.id)
        query = query.where(total_stock <= Material.stock_minimo if stock_bajo else total_stock > Material.stock_minimo)

    total = count_rows(db, query)
    rows = db.scalars(query.order_by(Material.nombre.asc(), Material.sku.asc()).offset(offset).limit(limit)).all()
    return total, [serialize_material(material) for material in rows]


def list_stock(
    db: Session,
    empresa_id: str,
    *,
    almacen_id: str | None = None,
    material_id: str | None = None,
    q: str | None = None,
    stock_bajo: bool | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[StockItem]]:
    query = (
        select(Existencia, Almacen, Material)
        .join(Almacen, Existencia.almacen_id == Almacen.id)
        .join(Material, Existencia.material_id == Material.id)
        .where(Existencia.empresa_id == empresa_id)
    )
    query = apply_text_search(query, q, Almacen.nombre, Almacen.codigo, Material.sku, Material.nombre, Material.categoria)

    if almacen_id:
        query = query.where(Existencia.almacen_id == almacen_id)
    if material_id:
        query = query.where(Existencia.material_id == material_id)
    if stock_bajo is not None:
        query = query.where(Existencia.cantidad <= Material.stock_minimo if stock_bajo else Existencia.cantidad > Material.stock_minimo)

    total = count_rows(db, query)
    rows = db.execute(
        query.order_by(Almacen.nombre.asc(), Material.nombre.asc(), Material.sku.asc()).offset(offset).limit(limit)
    ).all()
    return total, [serialize_stock_item(stock, warehouse, material) for stock, warehouse, material in rows]


def list_recent_movements(
    db: Session,
    empresa_id: str,
    *,
    almacen_id: str | None = None,
    material_id: str | None = None,
    tipo: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[MovementItem]]:
    query = (
        select(MovimientoInventario, Almacen, Material)
        .join(Almacen, MovimientoInventario.almacen_id == Almacen.id)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .where(MovimientoInventario.empresa_id == empresa_id)
    )

    if almacen_id:
        query = query.where(MovimientoInventario.almacen_id == almacen_id)
    if material_id:
        query = query.where(MovimientoInventario.material_id == material_id)
    if tipo:
        query = query.where(MovimientoInventario.tipo == tipo)
    if fecha_desde:
        query = query.where(MovimientoInventario.created_at >= fecha_desde)
    if fecha_hasta:
        query = query.where(MovimientoInventario.created_at <= fecha_hasta)

    total = count_rows(db, query)
    rows = db.execute(
        query.order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id)).offset(offset).limit(limit)
    ).all()
    return total, [build_movement_item(movement, warehouse, material) for movement, warehouse, material in rows]


def get_kardex(
    db: Session,
    empresa_id: str,
    material_id: str,
    almacen_id: str | None = None,
) -> KardexResponse:
    material = get_material_for_company(db, empresa_id, material_id)
    if almacen_id:
        get_warehouse_for_company(db, empresa_id, almacen_id)

    stock_query = (
        select(Existencia, Almacen)
        .join(Almacen, Existencia.almacen_id == Almacen.id)
        .where(
            Existencia.empresa_id == empresa_id,
            Existencia.material_id == material_id,
        )
        .order_by(Almacen.nombre.asc())
    )
    if almacen_id:
        stock_query = stock_query.where(Existencia.almacen_id == almacen_id)

    movement_query = (
        select(MovimientoInventario, Almacen, Material)
        .join(Almacen, MovimientoInventario.almacen_id == Almacen.id)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.material_id == material_id,
        )
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
    )
    if almacen_id:
        movement_query = movement_query.where(MovimientoInventario.almacen_id == almacen_id)

    stock_rows = db.execute(stock_query).all()
    movement_rows = db.execute(movement_query).all()

    stock_items = [
        KardexStockItem(
            almacen_id=warehouse.id,
            almacen_nombre=warehouse.nombre,
            almacen_codigo=warehouse.codigo,
            cantidad=stock.cantidad,
        )
        for stock, warehouse in stock_rows
    ]
    total_stock = sum((Decimal(item.cantidad) for item in stock_items), ZERO)

    return KardexResponse(
        material=serialize_material(material),
        existencia_total=total_stock,
        stock_por_almacen=stock_items,
        movements=[build_movement_item(movement, warehouse, material_row) for movement, warehouse, material_row in movement_rows],
    )
