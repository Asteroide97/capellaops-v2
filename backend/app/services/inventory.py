from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Empresa, Usuario
from app.models.inventory import Almacen, Existencia, Material, MovimientoInventario
from app.models.procurement import OrdenCompra, Proveedor, Requisicion
from app.schemas.inventory import (
    InventoryBulkMovementLineCreateRequest,
    InventoryBulkMovementResponse,
    InventorySummaryAlertItem,
    InventorySummaryCoreProductItem,
    InventorySummaryIndicators,
    InventorySummaryKpis,
    InventorySummaryLowRotationItem,
    InventorySummaryLowStockItem,
    InventorySummaryResponse,
    KardexResponse,
    KardexStockItem,
    MaterialItem,
    MovementItem,
    StockItem,
    WarehouseItem,
)
from app.services.access import can_access_module


ZERO = Decimal("0")


def ensure_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def days_since(value: datetime | None, *, fallback: datetime | None, now: datetime) -> int:
    reference = ensure_utc_datetime(value) or ensure_utc_datetime(fallback) or now
    delta = now - reference
    return max(delta.days, 0)


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


def normalize_optional_upper_text(value: str | None) -> str | None:
    cleaned = normalize_optional_text(value)
    return cleaned.upper() if cleaned else None


def normalize_query_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def normalize_barcode(value: str | None) -> str | None:
    cleaned = normalize_optional_upper_text(value)
    return cleaned.replace(" ", "") if cleaned else None


def normalize_image_urls(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = normalize_optional_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def dump_image_urls(values: list[str] | None) -> str | None:
    normalized = normalize_image_urls(values)
    if not normalized:
        return None
    return json.dumps(normalized, ensure_ascii=False)


def load_image_urls(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def decimal_or_zero(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(value or ZERO)


def cost_basis_for_material(material: Material) -> Decimal:
    return decimal_or_zero(material.costo_promedio_actual) or decimal_or_zero(material.costo_unitario)


def is_low_stock_value(stock_total: Decimal, stock_minimo: Decimal) -> bool:
    return stock_total <= stock_minimo if stock_minimo > ZERO else stock_total <= ZERO


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


def build_inventory_summary(db: Session, empresa_id: str) -> InventorySummaryResponse:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month_start = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )
    low_rotation_cutoff = now - timedelta(days=30)

    stock_totals = (
        select(
            Existencia.material_id.label("material_id"),
            func.coalesce(func.sum(Existencia.cantidad), 0).label("stock_total"),
        )
        .where(Existencia.empresa_id == empresa_id)
        .group_by(Existencia.material_id)
        .subquery()
    )
    last_movements = (
        select(
            MovimientoInventario.material_id.label("material_id"),
            func.max(MovimientoInventario.created_at).label("last_movement_at"),
        )
        .where(MovimientoInventario.empresa_id == empresa_id)
        .group_by(MovimientoInventario.material_id)
        .subquery()
    )

    material_rows = db.execute(
        select(
            Material,
            func.coalesce(stock_totals.c.stock_total, 0).label("stock_total"),
            last_movements.c.last_movement_at.label("last_movement_at"),
        )
        .outerjoin(stock_totals, stock_totals.c.material_id == Material.id)
        .outerjoin(last_movements, last_movements.c.material_id == Material.id)
        .where(
            Material.empresa_id == empresa_id,
            Material.activo == True,
        )
        .order_by(Material.nombre.asc(), Material.sku.asc())
    ).all()

    total_materiales = len(material_rows)
    ordenes_compra_pendientes = db.scalar(
        select(func.count(OrdenCompra.id)).where(
            OrdenCompra.empresa_id == empresa_id,
            OrdenCompra.estatus.in_(["borrador", "emitida", "recibida_parcial"]),
        )
    ) or 0
    requisiciones_pendientes = db.scalar(
        select(func.count(Requisicion.id)).where(
            Requisicion.empresa_id == empresa_id,
            Requisicion.estatus.in_(["enviada", "aprobada"]),
        )
    ) or 0
    ajustes_mes = db.scalar(
        select(func.count(MovimientoInventario.id)).where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.tipo == "ajuste",
            MovimientoInventario.created_at >= month_start,
            MovimientoInventario.created_at < next_month_start,
        )
    ) or 0

    valor_inventario = ZERO
    costo_reposicion = ZERO
    materiales_bajo_stock: list[InventorySummaryLowStockItem] = []
    productos_core_candidates: list[tuple[Decimal, Decimal, str, InventorySummaryCoreProductItem]] = []
    baja_rotacion_candidates: list[tuple[Decimal, int, str, InventorySummaryLowRotationItem]] = []
    alertas: list[InventorySummaryAlertItem] = []

    for material, stock_total_raw, last_movement_at in material_rows:
        stock_total = decimal_or_zero(stock_total_raw)
        stock_minimo = decimal_or_zero(material.stock_minimo)
        cost_basis = cost_basis_for_material(material)
        valor_total = stock_total * cost_basis
        dias_sin_movimiento = days_since(last_movement_at, fallback=material.created_at, now=now)

        valor_inventario += valor_total
        is_low_stock = is_low_stock_value(stock_total, stock_minimo)
        faltante = max(stock_minimo - stock_total, ZERO)

        if is_low_stock:
            costo_reposicion += faltante * cost_basis
            estado = "Agotado" if stock_total <= ZERO else "Bajo mínimo"
            materiales_bajo_stock.append(
                InventorySummaryLowStockItem(
                    material_id=material.id,
                    sku=material.sku,
                    nombre=material.nombre,
                    categoria=material.categoria,
                    stock_total=stock_total,
                    stock_minimo=stock_minimo,
                    faltante=faltante,
                    estado=estado,
                )
            )
            alertas.append(
                InventorySummaryAlertItem(
                    nivel="critical" if stock_total <= ZERO else "warning",
                    tipo="stock",
                    titulo=f"{material.sku} en alerta de stock",
                    mensaje=(
                        f"{material.nombre} está agotado."
                        if stock_total <= ZERO
                        else f"{material.nombre} está por debajo de su stock mínimo."
                    ),
                    route="/inventario/materiales",
                    material_id=material.id,
                )
            )

        if stock_total > ZERO or valor_total > ZERO:
            productos_core_candidates.append(
                (
                    valor_total,
                    stock_total,
                    material.nombre.lower(),
                    InventorySummaryCoreProductItem(
                        material_id=material.id,
                        sku=material.sku,
                        nombre=material.nombre,
                        categoria=material.categoria,
                        stock_total=stock_total,
                        valor_total=valor_total,
                        dias_sin_movimiento=dias_sin_movimiento,
                    ),
                )
            )

        if stock_total > ZERO and (
            last_movement_at is None or ensure_utc_datetime(last_movement_at) < low_rotation_cutoff
        ):
            baja_rotacion_candidates.append(
                (
                    valor_total,
                    dias_sin_movimiento,
                    material.nombre.lower(),
                    InventorySummaryLowRotationItem(
                        material_id=material.id,
                        sku=material.sku,
                        nombre=material.nombre,
                        categoria=material.categoria,
                        stock_total=stock_total,
                        valor_retenido=valor_total,
                        dias_sin_movimiento=dias_sin_movimiento,
                    ),
                )
            )

    if ordenes_compra_pendientes:
        alertas.append(
            InventorySummaryAlertItem(
                nivel="warning",
                tipo="compras",
                titulo="Órdenes de compra pendientes",
                mensaje=f"Hay {ordenes_compra_pendientes} órdenes de compra abiertas por recibir.",
                route="/inventario/ordenes-compra",
            )
        )

    if requisiciones_pendientes:
        alertas.append(
            InventorySummaryAlertItem(
                nivel="info",
                tipo="requisiciones",
                titulo="Requisiciones pendientes",
                mensaje=f"Hay {requisiciones_pendientes} requisiciones enviadas o aprobadas pendientes de atención.",
                route="/inventario/requisiciones",
            )
        )

    materiales_bajo_stock.sort(
        key=lambda item: (-decimal_or_zero(item.faltante), decimal_or_zero(item.stock_total), item.nombre.lower())
    )
    productos_core_candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    baja_rotacion_candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))

    return InventorySummaryResponse(
        kpis=InventorySummaryKpis(
            materiales_bajo_stock=len(materiales_bajo_stock),
            ordenes_compra_pendientes=ordenes_compra_pendientes,
            requisiciones_pendientes=requisiciones_pendientes,
            total_materiales=total_materiales,
        ),
        indicadores=InventorySummaryIndicators(
            valor_inventario=valor_inventario,
            costo_reposicion=costo_reposicion,
            ajustes_mes=ajustes_mes,
            merma_mes=ZERO,
        ),
        productos_core=[item[3] for item in productos_core_candidates[:5]],
        baja_rotacion=[item[3] for item in baja_rotacion_candidates[:5]],
        materiales_bajo_stock=materiales_bajo_stock[:10],
        alertas=alertas[:12],
    )


def serialize_material(
    material: Material,
    *,
    stock_total: Decimal | int | float | str | None = None,
    proveedor_principal_nombre: str | None = None,
    proveedor_principal_rfc: str | None = None,
) -> MaterialItem:
    total_stock = decimal_or_zero(stock_total)
    stock_minimo = decimal_or_zero(material.stock_minimo)
    cost_basis = cost_basis_for_material(material)
    return MaterialItem(
        id=material.id,
        empresa_id=material.empresa_id,
        sku=material.sku,
        nombre=material.nombre,
        descripcion=material.descripcion,
        categoria=material.categoria,
        subcategoria=material.subcategoria,
        unidad=material.unidad,
        imagen_url=material.imagen_url,
        imagenes_extra=load_image_urls(material.imagenes_extra_json),
        codigo_barras=material.codigo_barras,
        costo_unitario=material.costo_unitario,
        costo_promedio_actual=material.costo_promedio_actual,
        precio_venta=material.precio_venta,
        stock_minimo=material.stock_minimo,
        stock_maximo=material.stock_maximo,
        stock_total=total_stock,
        valor_inventario=total_stock * cost_basis,
        ubicacion_texto=material.ubicacion_texto,
        proveedor_principal_id=material.proveedor_principal_id,
        proveedor_principal_nombre=proveedor_principal_nombre,
        proveedor_principal_rfc=proveedor_principal_rfc,
        lead_time_dias=material.lead_time_dias,
        stock_bajo=is_low_stock_value(total_stock, stock_minimo),
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
    quantity = decimal_or_zero(stock.cantidad)
    minimum = decimal_or_zero(material.stock_minimo)
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
        low_stock=is_low_stock_value(quantity, minimum),
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


def get_material_item_for_company(db: Session, empresa_id: str, material_id: str) -> MaterialItem:
    stock_totals = (
        select(
            Existencia.material_id.label("material_id"),
            func.coalesce(func.sum(Existencia.cantidad), 0).label("stock_total"),
        )
        .where(Existencia.empresa_id == empresa_id)
        .group_by(Existencia.material_id)
        .subquery()
    )
    row = db.execute(
        select(
            Material,
            func.coalesce(stock_totals.c.stock_total, 0).label("stock_total"),
            Proveedor.nombre.label("proveedor_principal_nombre"),
            Proveedor.rfc.label("proveedor_principal_rfc"),
        )
        .outerjoin(stock_totals, stock_totals.c.material_id == Material.id)
        .outerjoin(Proveedor, Proveedor.id == Material.proveedor_principal_id)
        .where(
            Material.id == material_id,
            Material.empresa_id == empresa_id,
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material no encontrado.")
    material, stock_total, proveedor_nombre, proveedor_rfc = row
    return serialize_material(
        material,
        stock_total=stock_total,
        proveedor_principal_nombre=proveedor_nombre,
        proveedor_principal_rfc=proveedor_rfc,
    )


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


def build_movement_item(
    movement: MovimientoInventario,
    warehouse: Almacen,
    material: Material,
    user: Usuario | None = None,
) -> MovementItem:
    cost_basis = decimal_or_zero(movement.costo_promedio_snapshot or movement.costo_unitario_snapshot)
    return MovementItem(
        id=movement.id,
        empresa_id=movement.empresa_id,
        almacen_id=movement.almacen_id,
        almacen_nombre=warehouse.nombre,
        material_id=movement.material_id,
        material_sku=material.sku,
        material_nombre=material.nombre,
        tipo=movement.tipo,
        estatus=movement.estatus,
        cantidad=movement.cantidad,
        cantidad_anterior=movement.cantidad_anterior,
        cantidad_nueva=movement.cantidad_nueva,
        referencia_tipo=movement.referencia_tipo,
        referencia_id=movement.referencia_id,
        grupo_referencia=movement.grupo_referencia,
        motivo=movement.motivo,
        entregado_por=movement.entregado_por,
        recibido_por=movement.recibido_por,
        documento_referencia=movement.documento_referencia,
        evidencia_url=movement.evidencia_url,
        es_proyecto=movement.es_proyecto,
        proyecto_id=movement.proyecto_id,
        proyecto_nombre_snapshot=movement.proyecto_nombre_snapshot,
        costo_unitario_snapshot=movement.costo_unitario_snapshot,
        costo_promedio_snapshot=movement.costo_promedio_snapshot,
        valor_inventario=decimal_or_zero(movement.cantidad_nueva) * cost_basis if cost_basis else ZERO,
        notas=movement.notas,
        created_by=movement.created_by,
        created_by_nombre=user.full_name if user else None,
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
    grupo_referencia: str | None = None,
    motivo: str | None = None,
    entregado_por: str | None = None,
    recibido_por: str | None = None,
    documento_referencia: str | None = None,
    evidencia_url: str | None = None,
    es_proyecto: bool = False,
    proyecto_id: str | None = None,
    proyecto_nombre_snapshot: str | None = None,
    costo_unitario: Decimal | None = None,
) -> MovementItem:
    validate_inventory_access(user, empresa)
    warehouse = get_warehouse_for_company(db, empresa.id, almacen_id)
    material = get_material_for_company(db, empresa.id, material_id)
    stock = get_or_create_stock(db, empresa.id, almacen_id, material_id)

    previous_quantity = decimal_or_zero(stock.cantidad)

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
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stock insuficiente.")
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

    override_cost = decimal_or_zero(costo_unitario) if costo_unitario is not None else None
    if override_cost is not None and tipo in {"entrada", "ajuste"}:
        material.costo_unitario = override_cost
        material.costo_promedio_actual = override_cost

    stock.cantidad = next_quantity
    cost_basis = cost_basis_for_material(material)
    movement = MovimientoInventario(
        empresa_id=empresa.id,
        almacen_id=warehouse.id,
        material_id=material.id,
        tipo=tipo,
        estatus="confirmado",
        cantidad=movement_quantity,
        cantidad_anterior=previous_quantity,
        cantidad_nueva=next_quantity,
        referencia_tipo=normalize_optional_text(referencia_tipo) or "manual",
        referencia_id=normalize_optional_text(referencia_id),
        grupo_referencia=normalize_optional_text(grupo_referencia),
        motivo=normalize_optional_text(motivo),
        entregado_por=normalize_optional_text(entregado_por),
        recibido_por=normalize_optional_text(recibido_por),
        documento_referencia=normalize_optional_text(documento_referencia),
        evidencia_url=normalize_optional_text(evidencia_url),
        es_proyecto=bool(es_proyecto),
        proyecto_id=normalize_optional_text(proyecto_id),
        proyecto_nombre_snapshot=normalize_optional_text(proyecto_nombre_snapshot),
        costo_unitario_snapshot=override_cost if override_cost is not None else decimal_or_zero(material.costo_unitario),
        costo_promedio_snapshot=cost_basis,
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
                "grupo_referencia": movement.grupo_referencia,
                "es_proyecto": movement.es_proyecto,
            },
        )
    )

    return build_movement_item(movement, warehouse, material, user)


def apply_bulk_inventory_movement(
    db: Session,
    *,
    user: Usuario,
    empresa: Empresa,
    almacen_id: str,
    tipo: str,
    items: list[InventoryBulkMovementLineCreateRequest],
    referencia_tipo: str | None,
    referencia_id: str | None,
    motivo: str | None,
    entregado_por: str | None,
    recibido_por: str | None,
    documento_referencia: str | None,
    evidencia_url: str | None,
    es_proyecto: bool,
    proyecto_id: str | None,
    proyecto_nombre_snapshot: str | None,
    notas: str | None,
    ip_address: str | None,
) -> InventoryBulkMovementResponse:
    validate_inventory_access(user, empresa)
    warehouse = get_warehouse_for_company(db, empresa.id, almacen_id)
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes agregar al menos un material.")

    group_reference = str(uuid4())
    movements: list[MovementItem] = []
    for item in items:
        line_notes = "\n".join(part for part in [normalize_optional_text(notas), normalize_optional_text(item.notas)] if part)
        movement = apply_inventory_movement(
            db,
            user=user,
            empresa=empresa,
            almacen_id=warehouse.id,
            material_id=item.material_id,
            tipo=tipo,
            cantidad=item.cantidad,
            cantidad_nueva=item.cantidad_nueva,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            notas=line_notes or None,
            ip_address=ip_address,
            grupo_referencia=group_reference,
            motivo=motivo,
            entregado_por=entregado_por,
            recibido_por=recibido_por,
            documento_referencia=documento_referencia,
            evidencia_url=evidencia_url,
            es_proyecto=es_proyecto,
            proyecto_id=proyecto_id,
            proyecto_nombre_snapshot=proyecto_nombre_snapshot,
            costo_unitario=item.costo_unitario,
        )
        movements.append(movement)

    return InventoryBulkMovementResponse(
        group_reference=group_reference,
        tipo=tipo,
        almacen_id=warehouse.id,
        movement_count=len(movements),
        items=movements,
    )


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
    proveedor_principal_id: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[MaterialItem]]:
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
    low_stock_condition = or_(
        and_(Material.stock_minimo > 0, total_stock <= Material.stock_minimo),
        and_(Material.stock_minimo <= 0, total_stock <= 0),
    )

    query = (
        select(
            Material,
            total_stock.label("stock_total"),
            Proveedor.nombre.label("proveedor_principal_nombre"),
            Proveedor.rfc.label("proveedor_principal_rfc"),
        )
        .outerjoin(stock_totals, stock_totals.c.material_id == Material.id)
        .outerjoin(Proveedor, Proveedor.id == Material.proveedor_principal_id)
        .where(Material.empresa_id == empresa_id)
    )
    query = apply_text_search(
        query,
        q,
        Material.sku,
        Material.nombre,
        Material.descripcion,
        Material.categoria,
        Material.subcategoria,
        Material.codigo_barras,
        Proveedor.nombre,
        Proveedor.rfc,
    )

    normalized_category = normalize_query_text(categoria)
    if normalized_category:
        query = query.where(func.lower(func.coalesce(Material.categoria, "")) == normalized_category)
    if proveedor_principal_id:
        query = query.where(Material.proveedor_principal_id == proveedor_principal_id)
    if activo is not None:
        query = query.where(Material.activo == activo)
    if stock_bajo is not None:
        query = query.where(low_stock_condition if stock_bajo else ~low_stock_condition)

    total = count_rows(db, query)
    rows = db.execute(query.order_by(Material.nombre.asc(), Material.sku.asc()).offset(offset).limit(limit)).all()
    return total, [
        serialize_material(
            material,
            stock_total=stock_total_value,
            proveedor_principal_nombre=proveedor_principal_nombre,
            proveedor_principal_rfc=proveedor_principal_rfc,
        )
        for material, stock_total_value, proveedor_principal_nombre, proveedor_principal_rfc in rows
    ]


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
    query = apply_text_search(
        query,
        q,
        Almacen.nombre,
        Almacen.codigo,
        Material.sku,
        Material.nombre,
        Material.categoria,
        Material.codigo_barras,
    )

    if almacen_id:
        query = query.where(Existencia.almacen_id == almacen_id)
    if material_id:
        query = query.where(Existencia.material_id == material_id)
    if stock_bajo is not None:
        low_condition = or_(
            and_(Material.stock_minimo > 0, Existencia.cantidad <= Material.stock_minimo),
            and_(Material.stock_minimo <= 0, Existencia.cantidad <= 0),
        )
        query = query.where(low_condition if stock_bajo else ~low_condition)

    total = count_rows(db, query)
    rows = db.execute(
        query.order_by(Almacen.nombre.asc(), Material.nombre.asc(), Material.sku.asc()).offset(offset).limit(limit)
    ).all()
    return total, [serialize_stock_item(stock, warehouse, material) for stock, warehouse, material in rows]


def list_recent_movements(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    almacen_id: str | None = None,
    material_id: str | None = None,
    tipo: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[MovementItem]]:
    query = (
        select(MovimientoInventario, Almacen, Material, Usuario)
        .join(Almacen, MovimientoInventario.almacen_id == Almacen.id)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .join(Usuario, MovimientoInventario.created_by == Usuario.id)
        .where(MovimientoInventario.empresa_id == empresa_id)
    )
    query = apply_text_search(
        query,
        q,
        Material.sku,
        Material.nombre,
        Material.codigo_barras,
        MovimientoInventario.motivo,
        MovimientoInventario.documento_referencia,
        MovimientoInventario.referencia_id,
        MovimientoInventario.notas,
        MovimientoInventario.entregado_por,
        MovimientoInventario.recibido_por,
        MovimientoInventario.proyecto_nombre_snapshot,
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
    return total, [build_movement_item(movement, warehouse, material, created_by) for movement, warehouse, material, created_by in rows]


def get_kardex(
    db: Session,
    empresa_id: str,
    material_id: str,
    almacen_id: str | None = None,
) -> KardexResponse:
    material_item = get_material_item_for_company(db, empresa_id, material_id)
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
        select(MovimientoInventario, Almacen, Material, Usuario)
        .join(Almacen, MovimientoInventario.almacen_id == Almacen.id)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .join(Usuario, MovimientoInventario.created_by == Usuario.id)
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
    total_stock = sum((decimal_or_zero(item.cantidad) for item in stock_items), ZERO)

    return KardexResponse(
        material=material_item,
        existencia_total=total_stock,
        stock_por_almacen=stock_items,
        movements=[
            build_movement_item(movement, warehouse, material_row, created_by)
            for movement, warehouse, material_row, created_by in movement_rows
        ],
    )
