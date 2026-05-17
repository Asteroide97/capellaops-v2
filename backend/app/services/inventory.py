from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import desc, select
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


def validate_inventory_access(user: Usuario, empresa: Empresa) -> None:
    if not can_access_module(user, empresa, "inventory"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La empresa no tiene acceso al modulo Inventario.",
        )


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


def get_warehouse_for_company(db: Session, empresa_id: str, warehouse_id: str) -> Almacen:
    warehouse = db.scalar(
        select(Almacen).where(
            Almacen.id == warehouse_id,
            Almacen.empresa_id == empresa_id,
        )
    )
    if not warehouse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Almacen no encontrado.")
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
                detail="Stock insuficiente para registrar la salida.",
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de movimiento invalido.")

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


def list_stock(
    db: Session,
    empresa_id: str,
    almacen_id: str | None = None,
    material_id: str | None = None,
) -> list[StockItem]:
    query = (
        select(Existencia, Almacen, Material)
        .join(Almacen, Existencia.almacen_id == Almacen.id)
        .join(Material, Existencia.material_id == Material.id)
        .where(Existencia.empresa_id == empresa_id)
        .order_by(Almacen.nombre.asc(), Material.nombre.asc())
    )

    if almacen_id:
        query = query.where(Existencia.almacen_id == almacen_id)
    if material_id:
        query = query.where(Existencia.material_id == material_id)

    rows = db.execute(query).all()
    return [
        StockItem(
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
        for stock, warehouse, material in rows
    ]


def list_recent_movements(
    db: Session,
    empresa_id: str,
    *,
    limit: int = 25,
) -> list[MovementItem]:
    query = (
        select(MovimientoInventario, Almacen, Material)
        .join(Almacen, MovimientoInventario.almacen_id == Almacen.id)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .where(MovimientoInventario.empresa_id == empresa_id)
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
        .limit(limit)
    )
    rows = db.execute(query).all()
    return [build_movement_item(movement, warehouse, material) for movement, warehouse, material in rows]


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
