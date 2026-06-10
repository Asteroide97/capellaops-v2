from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Empresa, Usuario
from app.models.inventory import Almacen, Existencia, Material, MovimientoInventario
from app.models.pos import Venta, VentaDetalle
from app.models.pm import PMPresupuestoPartida, PMProyecto, PMTarea
from app.models.procurement import OrdenCompra, OrdenCompraDetalle, Proveedor, Requisicion, RequisicionDetalle
from app.schemas.inventory import (
    InventoryBulkMovementLineCreateRequest,
    InventoryBulkMovementResponse,
    InventoryProjectListResponse,
    InventoryProjectMaterialItem,
    InventoryProjectMaterialsResponse,
    InventoryProjectSummaryItem,
    MaterialLookupItem,
    MaterialLookupResponse,
    MaterialLookupWarehouseStockItem,
    InventorySummaryAlertItem,
    InventorySummaryCoreProductItem,
    InventorySummaryIndicators,
    InventorySummaryKpis,
    InventorySummaryMaterialIssueItem,
    InventorySummaryLowRotationItem,
    InventorySummaryLowStockItem,
    InventorySummaryRecentMovementItem,
    InventorySummaryResponse,
    InventorySummaryTopMovementItem,
    KardexResponse,
    KardexStockItem,
    MaterialItem,
    MovementItem,
    MovementListResponse,
    StockItem,
    WarehouseItem,
)
from app.services.access import can_access_module
from app.services.company import ensure_within_company_warehouse_limit


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


def resolve_inventory_unit_cost(
    db: Session,
    *,
    empresa_id: str,
    material: Material,
    almacen_id: str | None = None,
) -> Decimal:
    average_cost = decimal_or_zero(material.costo_promedio_actual)
    if average_cost > ZERO:
        return average_cost

    latest_entry_query = (
        select(MovimientoInventario)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.material_id == material.id,
            MovimientoInventario.tipo == "entrada",
            MovimientoInventario.estatus == "confirmado",
        )
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
    )
    if almacen_id:
        latest_entry_query = latest_entry_query.where(MovimientoInventario.almacen_id == almacen_id)
    latest_entry = db.scalars(latest_entry_query.limit(1)).first()
    if latest_entry:
        latest_entry_cost = decimal_or_zero(latest_entry.costo_unitario_snapshot) or decimal_or_zero(
            latest_entry.costo_promedio_snapshot
        )
        if latest_entry_cost > ZERO:
            return latest_entry_cost

    reference_cost = decimal_or_zero(material.costo_unitario)
    if reference_cost > ZERO:
        return reference_cost
    return ZERO


def resolve_project_return_unit_cost(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    material_id: str,
    almacen_id: str | None = None,
    task_id: str | None = None,
    partida_id: str | None = None,
) -> Decimal:
    movement_query = (
        select(MovimientoInventario)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.proyecto_id == project_id,
            MovimientoInventario.material_id == material_id,
            MovimientoInventario.tipo == "salida",
            MovimientoInventario.estatus == "confirmado",
            MovimientoInventario.referencia_tipo == "CONSUMO_PROYECTO",
        )
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
    )
    if almacen_id:
        movement_query = movement_query.where(MovimientoInventario.almacen_id == almacen_id)
    if task_id:
        movement_query = movement_query.where(MovimientoInventario.pm_tarea_id == task_id)
    if partida_id:
        movement_query = movement_query.where(MovimientoInventario.pm_partida_id == partida_id)

    movement = db.scalars(movement_query.limit(1)).first()
    if not movement:
        return ZERO

    unit_cost = decimal_or_zero(movement.costo_unitario_snapshot) or decimal_or_zero(movement.costo_promedio_snapshot)
    return unit_cost if unit_cost > ZERO else ZERO


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


def calculate_operational_requisition_quantity(material: Material, stock_total: Decimal) -> Decimal:
    stock_minimo = decimal_or_zero(material.stock_minimo)
    stock_maximo = decimal_or_zero(material.stock_maximo)

    if stock_maximo > ZERO:
        return max(stock_maximo - stock_total, stock_minimo - stock_total, Decimal("1"))
    if stock_minimo > ZERO:
        return max((stock_minimo * Decimal("2")) - stock_total, stock_minimo - stock_total, Decimal("1"))
    if stock_total <= ZERO:
        return Decimal("1")
    return Decimal("1")


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


def build_inventory_summary(
    db: Session,
    empresa_id: str,
    *,
    almacen_id: str | None = None,
    periodo_dias: int = 60,
    categoria: str | None = None,
) -> InventorySummaryResponse:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month_start = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )
    periodo_efectivo = max(int(periodo_dias or 60), 1)
    periodo_corte = now - timedelta(days=periodo_efectivo)
    categoria_normalizada = normalize_query_text(categoria)

    stock_totals_query = (
        select(
            Existencia.material_id.label("material_id"),
            func.coalesce(func.sum(Existencia.cantidad), 0).label("stock_total"),
        )
        .where(Existencia.empresa_id == empresa_id)
    )
    if almacen_id:
        stock_totals_query = stock_totals_query.where(Existencia.almacen_id == almacen_id)
    stock_totals = stock_totals_query.group_by(Existencia.material_id).subquery()

    last_output_query = (
        select(
            MovimientoInventario.material_id.label("material_id"),
            func.max(MovimientoInventario.created_at).label("last_output_at"),
        )
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.tipo == "salida",
            MovimientoInventario.estatus == "confirmado",
        )
    )
    if almacen_id:
        last_output_query = last_output_query.where(MovimientoInventario.almacen_id == almacen_id)
    last_output_movements = last_output_query.group_by(MovimientoInventario.material_id).subquery()

    material_query = (
        select(
            Material,
            func.coalesce(stock_totals.c.stock_total, 0).label("stock_total"),
            last_output_movements.c.last_output_at.label("last_output_at"),
        )
        .outerjoin(stock_totals, stock_totals.c.material_id == Material.id)
        .outerjoin(last_output_movements, last_output_movements.c.material_id == Material.id)
        .where(
            Material.empresa_id == empresa_id,
            Material.activo == True,
        )
        .order_by(Material.nombre.asc(), Material.sku.asc())
    )
    if categoria_normalizada:
        material_query = material_query.where(func.lower(func.coalesce(Material.categoria, "")) == categoria_normalizada)

    material_rows = db.execute(material_query).all()
    material_ids = [material.id for material, _stock_total, _last_output_at in material_rows]
    total_materiales = len(material_rows)

    pending_requisition_map: dict[str, tuple[str, str]] = {}
    if material_ids:
        pending_requisition_rows = db.execute(
            select(
                RequisicionDetalle.material_id,
                Requisicion.id,
                Requisicion.folio,
            )
            .join(Requisicion, Requisicion.id == RequisicionDetalle.requisicion_id)
            .where(
                Requisicion.empresa_id == empresa_id,
                RequisicionDetalle.material_id.in_(material_ids),
                Requisicion.estatus.in_(["borrador", "enviada", "aprobada", "parcial", "convertida_a_oc"]),
            )
            .order_by(
                RequisicionDetalle.material_id.asc(),
                desc(Requisicion.created_at),
                desc(Requisicion.id),
            )
        ).all()
        for material_id, requisition_id, requisition_folio in pending_requisition_rows:
            if material_id not in pending_requisition_map:
                pending_requisition_map[material_id] = (requisition_id, requisition_folio)

    requisiciones_query = select(func.count(Requisicion.id)).where(
        Requisicion.empresa_id == empresa_id,
        Requisicion.estatus.in_(["enviada", "aprobada", "parcial"]),
    )
    ordenes_query = select(func.count(OrdenCompra.id)).where(
        OrdenCompra.empresa_id == empresa_id,
        OrdenCompra.estatus.in_(["borrador", "emitida", "recibida_parcial"]),
    )
    if categoria_normalizada:
        requisiciones_query = (
            select(func.count(func.distinct(Requisicion.id)))
            .select_from(Requisicion)
            .join(RequisicionDetalle, RequisicionDetalle.requisicion_id == Requisicion.id)
            .join(Material, Material.id == RequisicionDetalle.material_id)
            .where(
                Requisicion.empresa_id == empresa_id,
                Requisicion.estatus.in_(["enviada", "aprobada", "parcial"]),
                func.lower(func.coalesce(Material.categoria, "")) == categoria_normalizada,
            )
        )
        ordenes_query = (
            select(func.count(func.distinct(OrdenCompra.id)))
            .select_from(OrdenCompra)
            .join(OrdenCompraDetalle, OrdenCompraDetalle.orden_compra_id == OrdenCompra.id)
            .join(Material, Material.id == OrdenCompraDetalle.material_id)
            .where(
                OrdenCompra.empresa_id == empresa_id,
                OrdenCompra.estatus.in_(["borrador", "emitida", "recibida_parcial"]),
                func.lower(func.coalesce(Material.categoria, "")) == categoria_normalizada,
            )
        )

    requisiciones_pendientes = db.scalar(requisiciones_query) or 0
    ordenes_compra_pendientes = db.scalar(ordenes_query) or 0

    movement_month_query = (
        select(func.count(MovimientoInventario.id))
        .join(Material, Material.id == MovimientoInventario.material_id)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.estatus == "confirmado",
            MovimientoInventario.created_at >= month_start,
            MovimientoInventario.created_at < next_month_start,
        )
    )
    ajustes_month_query = (
        select(func.count(MovimientoInventario.id))
        .join(Material, Material.id == MovimientoInventario.material_id)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.tipo == "ajuste",
            MovimientoInventario.estatus == "confirmado",
            MovimientoInventario.created_at >= month_start,
            MovimientoInventario.created_at < next_month_start,
        )
    )
    if almacen_id:
        movement_month_query = movement_month_query.where(MovimientoInventario.almacen_id == almacen_id)
        ajustes_month_query = ajustes_month_query.where(MovimientoInventario.almacen_id == almacen_id)
    if categoria_normalizada:
        movement_month_query = movement_month_query.where(func.lower(func.coalesce(Material.categoria, "")) == categoria_normalizada)
        ajustes_month_query = ajustes_month_query.where(func.lower(func.coalesce(Material.categoria, "")) == categoria_normalizada)

    movimientos_mes = db.scalar(movement_month_query) or 0
    ajustes_mes = db.scalar(ajustes_month_query) or 0

    valor_inventario = ZERO
    costo_reposicion = ZERO
    materiales_sin_stock = 0
    materiales_bajo_stock: list[InventorySummaryLowStockItem] = []
    materiales_sin_precio_venta: list[InventorySummaryMaterialIssueItem] = []
    materiales_sin_costo: list[InventorySummaryMaterialIssueItem] = []
    productos_core_candidates: list[tuple[Decimal, Decimal, str, InventorySummaryCoreProductItem]] = []
    baja_rotacion_candidates: list[tuple[Decimal, int, str, InventorySummaryLowRotationItem]] = []
    alertas: list[InventorySummaryAlertItem] = []

    for material, stock_total_raw, last_output_at in material_rows:
        stock_total = decimal_or_zero(stock_total_raw)
        stock_minimo = decimal_or_zero(material.stock_minimo)
        stock_maximo = decimal_or_zero(material.stock_maximo)
        cost_basis = cost_basis_for_material(material)
        valor_total = stock_total * cost_basis
        dias_sin_movimiento = days_since(last_output_at, fallback=material.created_at, now=now)
        sin_precio_venta = decimal_or_zero(material.precio_venta) <= ZERO
        sin_costo = decimal_or_zero(material.costo_unitario) <= ZERO and decimal_or_zero(material.costo_promedio_actual) <= ZERO

        valor_inventario += valor_total

        if stock_total <= ZERO:
            materiales_sin_stock += 1

        if is_low_stock_value(stock_total, stock_minimo):
            requisicion_pendiente = pending_requisition_map.get(material.id)
            cantidad_sugerida = calculate_operational_requisition_quantity(material, stock_total)
            costo_reposicion += cantidad_sugerida * cost_basis if cost_basis > ZERO else ZERO
            materiales_bajo_stock.append(
                InventorySummaryLowStockItem(
                    material_id=material.id,
                    sku=material.sku,
                    nombre=material.nombre,
                    categoria=material.categoria,
                    stock_total=stock_total,
                    stock_minimo=stock_minimo,
                    stock_maximo=stock_maximo,
                    faltante=max(stock_minimo - stock_total, ZERO),
                    cantidad_sugerida=cantidad_sugerida,
                    estado="Agotado" if stock_total <= ZERO else "Bajo minimo",
                    requisicion_pendiente=bool(requisicion_pendiente),
                    requisicion_id=requisicion_pendiente[0] if requisicion_pendiente else None,
                    requisicion_folio=requisicion_pendiente[1] if requisicion_pendiente else None,
                )
            )

        if sin_precio_venta:
            materiales_sin_precio_venta.append(
                InventorySummaryMaterialIssueItem(
                    material_id=material.id,
                    sku=material.sku,
                    nombre=material.nombre,
                    categoria=material.categoria,
                    stock_total=stock_total,
                    precio_venta=material.precio_venta,
                    costo_unitario=material.costo_unitario,
                    costo_promedio_actual=material.costo_promedio_actual,
                    valor_inventario=valor_total,
                )
            )

        if sin_costo:
            materiales_sin_costo.append(
                InventorySummaryMaterialIssueItem(
                    material_id=material.id,
                    sku=material.sku,
                    nombre=material.nombre,
                    categoria=material.categoria,
                    stock_total=stock_total,
                    precio_venta=material.precio_venta,
                    costo_unitario=material.costo_unitario,
                    costo_promedio_actual=material.costo_promedio_actual,
                    valor_inventario=valor_total,
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

        if stock_total > ZERO and (last_output_at is None or ensure_utc_datetime(last_output_at) < periodo_corte):
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

    top_movement_query = (
        select(
            Material.id,
            Material.sku,
            Material.nombre,
            Material.categoria,
            func.coalesce(
                func.sum(case((MovimientoInventario.tipo == "entrada", MovimientoInventario.cantidad), else_=ZERO)),
                0,
            ),
            func.coalesce(
                func.sum(case((MovimientoInventario.tipo == "salida", MovimientoInventario.cantidad), else_=ZERO)),
                0,
            ),
            func.count(MovimientoInventario.id),
        )
        .join(Material, Material.id == MovimientoInventario.material_id)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.estatus == "confirmado",
            MovimientoInventario.created_at >= periodo_corte,
        )
        .group_by(Material.id, Material.sku, Material.nombre, Material.categoria)
    )
    if almacen_id:
        top_movement_query = top_movement_query.where(MovimientoInventario.almacen_id == almacen_id)
    if categoria_normalizada:
        top_movement_query = top_movement_query.where(func.lower(func.coalesce(Material.categoria, "")) == categoria_normalizada)
    productos_mas_movidos = [
        InventorySummaryTopMovementItem(
            material_id=material_id,
            sku=sku,
            nombre=nombre,
            categoria=material_categoria,
            cantidad_entrada=decimal_or_zero(cantidad_entrada),
            cantidad_salida=decimal_or_zero(cantidad_salida),
            movimientos_count=int(movimientos_count or 0),
        )
        for material_id, sku, nombre, material_categoria, cantidad_entrada, cantidad_salida, movimientos_count in db.execute(
            top_movement_query
        ).all()
    ]
    productos_mas_movidos.sort(
        key=lambda item: (
            -(decimal_or_zero(item.cantidad_salida) + decimal_or_zero(item.cantidad_entrada)),
            -item.movimientos_count,
            item.nombre.lower(),
        )
    )

    recent_movements_query = (
        select(MovimientoInventario, Almacen, Material, Usuario)
        .join(Almacen, MovimientoInventario.almacen_id == Almacen.id)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .join(Usuario, MovimientoInventario.created_by == Usuario.id)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.estatus == "confirmado",
        )
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
    )
    if almacen_id:
        recent_movements_query = recent_movements_query.where(MovimientoInventario.almacen_id == almacen_id)
    if categoria_normalizada:
        recent_movements_query = recent_movements_query.where(func.lower(func.coalesce(Material.categoria, "")) == categoria_normalizada)
    ultimos_movimientos = [
        InventorySummaryRecentMovementItem(
            id=movement.id,
            fecha=movement.created_at,
            tipo=movement.tipo,
            material_id=material.id,
            material_sku=material.sku,
            material_nombre=material.nombre,
            almacen_id=warehouse.id,
            almacen_nombre=warehouse.nombre,
            cantidad=movement.cantidad,
            referencia=movement.documento_referencia or movement.referencia_id or movement.motivo,
            usuario=user.full_name if user else None,
        )
        for movement, warehouse, material, user in db.execute(recent_movements_query.limit(10)).all()
    ]

    no_margin_totals: dict[str, dict[str, Decimal | str | int]] = {}
    no_margin_query = (
        select(VentaDetalle, Venta, Material, MovimientoInventario)
        .join(Venta, Venta.id == VentaDetalle.venta_id)
        .join(Material, Material.id == VentaDetalle.material_id)
        .outerjoin(MovimientoInventario, MovimientoInventario.id == VentaDetalle.movimiento_inventario_id)
        .where(
            Venta.empresa_id == empresa_id,
            Venta.estatus == "pagada",
            or_(
                Venta.paid_at >= periodo_corte,
                and_(Venta.paid_at.is_(None), Venta.created_at >= periodo_corte),
            ),
        )
    )
    if almacen_id:
        no_margin_query = no_margin_query.where(Venta.almacen_id == almacen_id)
    if categoria_normalizada:
        no_margin_query = no_margin_query.where(func.lower(func.coalesce(Material.categoria, "")) == categoria_normalizada)
    for detail, _sale, material, movement in db.execute(no_margin_query).all():
        unit_cost = decimal_or_zero(movement.costo_unitario_snapshot if movement else None)
        if unit_cost <= ZERO:
            unit_cost = decimal_or_zero(movement.costo_promedio_snapshot if movement else None)
        if unit_cost <= ZERO:
            unit_cost = decimal_or_zero(material.costo_promedio_actual)
        if unit_cost <= ZERO:
            unit_cost = decimal_or_zero(material.costo_unitario)
        line_margin = decimal_or_zero(detail.total_linea) - (decimal_or_zero(detail.cantidad) * unit_cost)
        if line_margin > ZERO:
            continue
        entry = no_margin_totals.setdefault(
            material.id,
            {"sku": material.sku, "nombre": material.nombre, "margen": ZERO, "lineas": 0},
        )
        entry["margen"] = decimal_or_zero(entry["margen"]) + line_margin
        entry["lineas"] = int(entry["lineas"] or 0) + 1

    if ordenes_compra_pendientes:
        descripcion = f"Hay {ordenes_compra_pendientes} ordenes de compra abiertas por recibir."
        alertas.append(
            InventorySummaryAlertItem(
                tipo="orden_compra_pendiente",
                severidad="warning",
                titulo="Ordenes de compra pendientes",
                descripcion=descripcion,
                accion_label="Ver ordenes",
                accion_url="/inventario/ordenes-compra",
                action="open_purchase_orders",
                nivel="warning",
                mensaje=descripcion,
                route="/inventario/ordenes-compra",
            )
        )

    if requisiciones_pendientes:
        descripcion = f"Hay {requisiciones_pendientes} requisiciones enviadas o aprobadas pendientes de atencion."
        alertas.append(
            InventorySummaryAlertItem(
                tipo="requisicion_pendiente",
                severidad="info",
                titulo="Requisiciones pendientes",
                descripcion=descripcion,
                accion_label="Ver requisiciones",
                accion_url="/inventario/requisiciones",
                action="open_requisitions",
                nivel="info",
                mensaje=descripcion,
                route="/inventario/requisiciones",
            )
        )

    for item in materiales_bajo_stock[:6]:
        is_critical = decimal_or_zero(item.stock_total) <= ZERO
        descripcion = (
            f"{item.nombre} no tiene existencias. Cantidad sugerida: {item.cantidad_sugerida}."
            if is_critical
            else f"{item.nombre} esta por debajo del minimo. Cantidad sugerida: {item.cantidad_sugerida}."
        )
        if item.requisicion_pendiente and item.requisicion_folio:
            descripcion = f"{descripcion} Ya existe la requisicion {item.requisicion_folio}."
        alertas.append(
            InventorySummaryAlertItem(
                tipo="sin_stock" if is_critical else "bajo_stock",
                severidad="critical" if is_critical else "warning",
                titulo=f"{item.sku} {'sin stock' if is_critical else 'bajo stock'}",
                descripcion=descripcion,
                accion_label="Ver requisicion pendiente" if item.requisicion_pendiente else "Crear requisicion",
                accion_url="/inventario/requisiciones" if item.requisicion_pendiente else "/inventario/resumen",
                action="open_requisitions" if item.requisicion_pendiente else "create_requisition",
                material_id=item.material_id,
                requisicion_id=item.requisicion_id,
                nivel="critical" if is_critical else "warning",
                mensaje=descripcion,
                route="/inventario/requisiciones" if item.requisicion_pendiente else "/inventario/resumen",
            )
        )

    for item in materiales_sin_precio_venta[:6]:
        descripcion = f"{item.nombre} no tiene precio de venta configurado para POS."
        alertas.append(
            InventorySummaryAlertItem(
                tipo="sin_precio_venta",
                severidad="warning",
                titulo=f"{item.sku} sin precio de venta",
                descripcion=descripcion,
                accion_label="Editar precio",
                accion_url="/inventario/materiales?sin_precio_venta=true",
                action="open_materials_missing_price",
                material_id=item.material_id,
                nivel="warning",
                mensaje=descripcion,
                route="/inventario/materiales?sin_precio_venta=true",
            )
        )

    for item in materiales_sin_costo[:6]:
        descripcion = f"{item.nombre} no tiene costo de referencia ni costo promedio."
        alertas.append(
            InventorySummaryAlertItem(
                tipo="sin_costo",
                severidad="warning",
                titulo=f"{item.sku} sin costo",
                descripcion=descripcion,
                accion_label="Actualizar costo",
                accion_url="/inventario/materiales?sin_costo=true",
                action="open_materials_missing_cost",
                material_id=item.material_id,
                nivel="warning",
                mensaje=descripcion,
                route="/inventario/materiales?sin_costo=true",
            )
        )

    for material_id, payload in sorted(
        no_margin_totals.items(),
        key=lambda entry: (decimal_or_zero(entry[1]["margen"]), str(entry[1]["nombre"]).lower()),
    )[:5]:
        descripcion = f"{payload['nombre']} tuvo {payload['lineas']} venta(s) sin margen positivo en el periodo."
        alertas.append(
            InventorySummaryAlertItem(
                tipo="venta_sin_margen",
                severidad="critical",
                titulo=f"{payload['sku']} vendido sin margen",
                descripcion=descripcion,
                accion_label="Revisar material",
                accion_url=f"/inventario/materiales?q={payload['sku']}",
                action="open_material",
                material_id=material_id,
                nivel="critical",
                mensaje=descripcion,
                route=f"/inventario/materiales?q={payload['sku']}",
            )
        )

    materiales_bajo_stock.sort(
        key=lambda item: (
            0 if decimal_or_zero(item.stock_total) <= ZERO else 1,
            -decimal_or_zero(item.cantidad_sugerida),
            decimal_or_zero(item.stock_total),
            item.nombre.lower(),
        )
    )
    productos_core_candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    baja_rotacion_candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    materiales_sin_precio_venta.sort(
        key=lambda item: (-decimal_or_zero(item.stock_total), item.nombre.lower(), item.sku.lower())
    )
    materiales_sin_costo.sort(
        key=lambda item: (-decimal_or_zero(item.stock_total), item.nombre.lower(), item.sku.lower())
    )
    alertas.sort(key=lambda item: ({"critical": 0, "warning": 1, "info": 2}.get(item.severidad, 9), item.titulo.lower()))

    return InventorySummaryResponse(
        kpis=InventorySummaryKpis(
            valor_total_inventario=valor_inventario,
            materiales_bajo_stock=len(materiales_bajo_stock),
            materiales_sin_stock=materiales_sin_stock,
            materiales_sin_precio_venta=len(materiales_sin_precio_venta),
            materiales_sin_costo=len(materiales_sin_costo),
            ordenes_compra_pendientes=ordenes_compra_pendientes,
            requisiciones_pendientes=requisiciones_pendientes,
            movimientos_mes=movimientos_mes,
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
        bajo_stock=materiales_bajo_stock[:10],
        sin_precio_venta=materiales_sin_precio_venta[:10],
        sin_costo=materiales_sin_costo[:10],
        productos_mas_movidos=productos_mas_movidos[:10],
        ultimos_movimientos=ultimos_movimientos,
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

    if activo:
        ensure_within_company_warehouse_limit(db, empresa)

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


def get_project_for_company_inventory(db: Session, empresa_id: str, project_id: str) -> PMProyecto:
    project = db.scalar(
        select(PMProyecto).where(
            PMProyecto.id == project_id,
            PMProyecto.empresa_id == empresa_id,
        )
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    return project


def get_project_task_for_company_inventory(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    task_id: str | None,
) -> PMTarea | None:
    normalized_task_id = normalize_optional_text(task_id)
    if not normalized_task_id:
        return None
    task = db.scalar(
        select(PMTarea).where(
            PMTarea.id == normalized_task_id,
            PMTarea.empresa_id == empresa_id,
        )
    )
    if not task or task.proyecto_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La tarea indicada no pertenece al proyecto seleccionado.",
        )
    return task


def get_budget_item_for_company_inventory(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    item_id: str | None,
) -> PMPresupuestoPartida | None:
    normalized_item_id = normalize_optional_text(item_id)
    if not normalized_item_id:
        return None
    item = db.scalar(
        select(PMPresupuestoPartida).where(
            PMPresupuestoPartida.id == normalized_item_id,
            PMPresupuestoPartida.empresa_id == empresa_id,
        )
    )
    if not item or item.proyecto_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La partida indicada no pertenece al proyecto seleccionado.",
        )
    return item


def lookup_material_by_code(db: Session, empresa_id: str, code: str) -> MaterialLookupResponse:
    raw_code = normalize_optional_text(code)
    if not raw_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo obligatorio.",
        )

    normalized_sku = normalize_code(raw_code, "Codigo")
    normalized_barcode = normalize_barcode(raw_code)

    stock_totals = (
        select(
            Existencia.material_id.label("material_id"),
            func.coalesce(func.sum(Existencia.cantidad), 0).label("stock_total"),
        )
        .where(Existencia.empresa_id == empresa_id)
        .group_by(Existencia.material_id)
        .subquery()
    )

    base_query = (
        select(
            Material,
            func.coalesce(stock_totals.c.stock_total, 0).label("stock_total"),
            Proveedor.nombre.label("proveedor_principal_nombre"),
            Proveedor.rfc.label("proveedor_principal_rfc"),
        )
        .outerjoin(stock_totals, stock_totals.c.material_id == Material.id)
        .outerjoin(Proveedor, Proveedor.id == Material.proveedor_principal_id)
        .where(Material.empresa_id == empresa_id)
    )

    candidate_rows = []
    candidate_rows.append(
        db.execute(
            base_query.where(
                Material.activo == True,
                Material.sku == normalized_sku,
            )
        ).first()
    )
    if normalized_barcode:
        candidate_rows.append(
            db.execute(
                base_query.where(
                    Material.activo == True,
                    Material.codigo_barras == normalized_barcode,
                )
            ).first()
        )
    candidate_rows.append(
        db.execute(base_query.where(Material.sku == normalized_sku)).first()
    )
    if normalized_barcode:
        candidate_rows.append(
            db.execute(base_query.where(Material.codigo_barras == normalized_barcode)).first()
        )

    row = next((item for item in candidate_rows if item is not None), None)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontro ningun material con ese SKU o codigo de barras.",
        )

    material, stock_total, proveedor_nombre, proveedor_rfc = row
    stock_rows = db.execute(
        select(
            Existencia.almacen_id.label("almacen_id"),
            Almacen.nombre.label("almacen_nombre"),
            func.coalesce(Existencia.cantidad, 0).label("stock_actual"),
        )
        .join(Almacen, Almacen.id == Existencia.almacen_id)
        .where(
            Existencia.empresa_id == empresa_id,
            Existencia.material_id == material.id,
        )
        .order_by(Almacen.nombre.asc(), Almacen.codigo.asc())
    ).all()

    serialized = serialize_material(
        material,
        stock_total=stock_total,
        proveedor_principal_nombre=proveedor_nombre,
        proveedor_principal_rfc=proveedor_rfc,
    )

    return MaterialLookupResponse(
        material=MaterialLookupItem(
            **serialized.model_dump(),
            stock_por_almacen=[
                MaterialLookupWarehouseStockItem(
                    almacen_id=almacen_id,
                    almacen_nombre=almacen_nombre,
                    stock_actual=decimal_or_zero(stock_actual),
                )
                for almacen_id, almacen_nombre, stock_actual in stock_rows
            ],
        )
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
    movement_cost = decimal_or_zero(movement.cantidad) * decimal_or_zero(
        movement.costo_unitario_snapshot or movement.costo_promedio_snapshot
    )
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
        pm_tarea_id=movement.pm_tarea_id,
        pm_tarea_nombre_snapshot=movement.pm_tarea_nombre_snapshot,
        pm_partida_id=movement.pm_partida_id,
        pm_partida_nombre_snapshot=movement.pm_partida_nombre_snapshot,
        costo_unitario_snapshot=movement.costo_unitario_snapshot,
        costo_promedio_snapshot=movement.costo_promedio_snapshot,
        costo_total_snapshot=movement_cost,
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
    pm_tarea_id: str | None = None,
    pm_tarea_nombre_snapshot: str | None = None,
    pm_partida_id: str | None = None,
    pm_partida_nombre_snapshot: str | None = None,
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
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No hay stock suficiente en este almacén.")
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
    resolved_unit_cost = (
        override_cost
        if override_cost is not None
        else resolve_inventory_unit_cost(db, empresa_id=empresa.id, material=material, almacen_id=warehouse.id)
    )
    if tipo in {"entrada", "ajuste"}:
        if override_cost is not None:
            material.costo_unitario = override_cost
            material.costo_promedio_actual = override_cost
        elif resolved_unit_cost > ZERO:
            if decimal_or_zero(material.costo_unitario) <= ZERO:
                material.costo_unitario = resolved_unit_cost
            material.costo_promedio_actual = resolved_unit_cost

    stock.cantidad = next_quantity
    cost_basis = decimal_or_zero(material.costo_promedio_actual) or resolved_unit_cost
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
        pm_tarea_id=normalize_optional_text(pm_tarea_id),
        pm_tarea_nombre_snapshot=normalize_optional_text(pm_tarea_nombre_snapshot),
        pm_partida_id=normalize_optional_text(pm_partida_id),
        pm_partida_nombre_snapshot=normalize_optional_text(pm_partida_nombre_snapshot),
        costo_unitario_snapshot=resolved_unit_cost,
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
    pm_tarea_id: str | None,
    pm_tarea_nombre_snapshot: str | None,
    pm_partida_id: str | None,
    pm_partida_nombre_snapshot: str | None,
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
            pm_tarea_id=pm_tarea_id,
            pm_tarea_nombre_snapshot=pm_tarea_nombre_snapshot,
            pm_partida_id=pm_partida_id,
            pm_partida_nombre_snapshot=pm_partida_nombre_snapshot,
            costo_unitario=item.costo_unitario,
        )
        movements.append(movement)
        if tipo == "salida" and es_proyecto and normalize_optional_text(proyecto_id):
            from app.services.pm import create_project_material_consumption_from_movement

            create_project_material_consumption_from_movement(
                db,
                empresa_id=empresa.id,
                movement_id=movement.id,
                project_id=normalize_optional_text(proyecto_id),
                tarea_id=normalize_optional_text(pm_tarea_id),
                origen="movimiento_manual",
            )

    return InventoryBulkMovementResponse(
        group_reference=group_reference,
        tipo=tipo,
        almacen_id=warehouse.id,
        movement_count=len(movements),
        items=movements,
    )


def project_movement_cost_total(movement: MovimientoInventario) -> Decimal:
    unit_cost = decimal_or_zero(movement.costo_unitario_snapshot or movement.costo_promedio_snapshot)
    return decimal_or_zero(movement.cantidad) * unit_cost


def project_movement_sign(movement: MovimientoInventario) -> Decimal:
    if movement.tipo == "salida":
        return Decimal("1")
    if movement.tipo == "entrada" and normalize_optional_text(movement.referencia_tipo) == "DEVOLUCION_PROYECTO":
        return Decimal("-1")
    return ZERO


def list_project_inventory_movement_rows(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
) -> list[tuple[MovimientoInventario, Almacen, Material, Usuario]]:
    return db.execute(
        select(MovimientoInventario, Almacen, Material, Usuario)
        .join(Almacen, MovimientoInventario.almacen_id == Almacen.id)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .join(Usuario, MovimientoInventario.created_by == Usuario.id)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.es_proyecto == True,
            MovimientoInventario.proyecto_id == project_id,
            MovimientoInventario.estatus == "confirmado",
            or_(
                MovimientoInventario.tipo == "salida",
                and_(
                    MovimientoInventario.tipo == "entrada",
                    MovimientoInventario.referencia_tipo == "DEVOLUCION_PROYECTO",
                ),
            ),
        )
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
    ).all()


def get_project_material_net_quantity(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    material_id: str,
    task_id: str | None = None,
    partida_id: str | None = None,
) -> Decimal:
    rows = db.scalars(
        select(MovimientoInventario).where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.es_proyecto == True,
            MovimientoInventario.proyecto_id == project_id,
            MovimientoInventario.material_id == material_id,
            MovimientoInventario.estatus == "confirmado",
            or_(
                MovimientoInventario.tipo == "salida",
                and_(
                    MovimientoInventario.tipo == "entrada",
                    MovimientoInventario.referencia_tipo == "DEVOLUCION_PROYECTO",
                ),
            ),
        )
    ).all()
    total = ZERO
    normalized_task_id = normalize_optional_text(task_id)
    normalized_partida_id = normalize_optional_text(partida_id)
    for movement in rows:
        if normalized_task_id and movement.pm_tarea_id != normalized_task_id:
            continue
        if normalized_partida_id and movement.pm_partida_id != normalized_partida_id:
            continue
        total += project_movement_sign(movement) * decimal_or_zero(movement.cantidad)
    return total


def consume_material_for_project(
    db: Session,
    *,
    empresa_id: str,
    proyecto_id: str,
    material_id: str,
    almacen_id: str,
    cantidad: Decimal,
    tarea_id: str | None = None,
    partida_id: str | None = None,
    notas: str | None = None,
    usuario_id: str | None = None,
    user: Usuario,
    empresa: Empresa,
    ip_address: str | None,
    documento_referencia: str | None = None,
    requisition_id: str | None = None,
    requisition_detail_id: str | None = None,
    origin: str = "movimiento_manual",
) -> MovementItem:
    validate_inventory_access(user, empresa)
    if empresa.id != empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa inválida para el consumo.")
    quantity = decimal_or_zero(cantidad)
    if quantity <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad debe ser mayor a cero.")

    project = get_project_for_company_inventory(db, empresa_id, proyecto_id)
    if not project.activo or str(project.estatus or "").lower() != "activo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes consumir material de un proyecto inactivo.",
        )
    material = get_material_for_company(db, empresa_id, material_id)
    warehouse = get_warehouse_for_company(db, empresa_id, almacen_id)
    task = get_project_task_for_company_inventory(db, empresa_id=empresa_id, project_id=project.id, task_id=tarea_id)
    budget_item = get_budget_item_for_company_inventory(db, empresa_id=empresa_id, project_id=project.id, item_id=partida_id)

    movement = apply_inventory_movement(
        db,
        user=user,
        empresa=empresa,
        almacen_id=warehouse.id,
        material_id=material.id,
        tipo="salida",
        cantidad=quantity,
        cantidad_nueva=None,
        referencia_tipo="CONSUMO_PROYECTO",
        referencia_id=budget_item.id if budget_item else task.id if task else project.id,
        notas=notas,
        ip_address=ip_address,
        motivo="Consumo para proyecto",
        entregado_por=user.full_name,
        documento_referencia=documento_referencia,
        es_proyecto=True,
        proyecto_id=project.id,
        proyecto_nombre_snapshot=project.nombre,
        pm_tarea_id=task.id if task else None,
        pm_tarea_nombre_snapshot=task.titulo if task else None,
        pm_partida_id=budget_item.id if budget_item else None,
        pm_partida_nombre_snapshot=budget_item.nombre if budget_item else None,
        costo_unitario=None,
    )

    from app.services.pm import create_project_material_consumption_from_movement, refresh_project_material_costs

    create_project_material_consumption_from_movement(
        db,
        empresa_id=empresa_id,
        movement_id=movement.id,
        project_id=project.id,
        tarea_id=task.id if task else None,
        requisition_id=requisition_id,
        requisition_detail_id=requisition_detail_id,
        origen=origin,
    )
    refresh_project_material_costs(db, empresa_id=empresa_id, project_id=project.id)
    return movement


def return_material_from_project(
    db: Session,
    *,
    empresa_id: str,
    proyecto_id: str,
    material_id: str,
    almacen_id: str,
    cantidad: Decimal,
    tarea_id: str | None = None,
    partida_id: str | None = None,
    notas: str | None = None,
    usuario_id: str | None = None,
    user: Usuario,
    empresa: Empresa,
    ip_address: str | None,
) -> MovementItem:
    validate_inventory_access(user, empresa)
    if empresa.id != empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa inválida para la devolución.")
    quantity = decimal_or_zero(cantidad)
    if quantity <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad debe ser mayor a cero.")

    project = get_project_for_company_inventory(db, empresa_id, proyecto_id)
    if not project.activo or str(project.estatus or "").lower() != "activo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes devolver material de un proyecto inactivo.",
        )
    material = get_material_for_company(db, empresa_id, material_id)
    warehouse = get_warehouse_for_company(db, empresa_id, almacen_id)
    task = get_project_task_for_company_inventory(db, empresa_id=empresa_id, project_id=project.id, task_id=tarea_id)
    budget_item = get_budget_item_for_company_inventory(db, empresa_id=empresa_id, project_id=project.id, item_id=partida_id)
    net_quantity = get_project_material_net_quantity(
        db,
        empresa_id=empresa_id,
        project_id=project.id,
        material_id=material.id,
        task_id=task.id if task else None,
        partida_id=budget_item.id if budget_item else None,
    )
    if net_quantity < quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La devolución excede el material consumido para este proyecto.",
        )
    return_unit_cost = resolve_project_return_unit_cost(
        db,
        empresa_id=empresa_id,
        project_id=project.id,
        material_id=material.id,
        almacen_id=warehouse.id,
        task_id=task.id if task else None,
        partida_id=budget_item.id if budget_item else None,
    )
    if return_unit_cost <= ZERO:
        return_unit_cost = resolve_inventory_unit_cost(
            db,
            empresa_id=empresa_id,
            material=material,
            almacen_id=warehouse.id,
        )

    movement = apply_inventory_movement(
        db,
        user=user,
        empresa=empresa,
        almacen_id=warehouse.id,
        material_id=material.id,
        tipo="entrada",
        cantidad=quantity,
        cantidad_nueva=None,
        referencia_tipo="DEVOLUCION_PROYECTO",
        referencia_id=budget_item.id if budget_item else task.id if task else project.id,
        notas=notas,
        ip_address=ip_address,
        motivo="Devolución desde proyecto",
        recibido_por=user.full_name,
        es_proyecto=True,
        proyecto_id=project.id,
        proyecto_nombre_snapshot=project.nombre,
        pm_tarea_id=task.id if task else None,
        pm_tarea_nombre_snapshot=task.titulo if task else None,
        pm_partida_id=budget_item.id if budget_item else None,
        pm_partida_nombre_snapshot=budget_item.nombre if budget_item else None,
        costo_unitario=return_unit_cost if return_unit_cost > ZERO else None,
    )

    from app.services.pm import refresh_project_material_costs

    refresh_project_material_costs(db, empresa_id=empresa_id, project_id=project.id)
    return movement


def list_inventory_projects(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[InventoryProjectSummaryItem]]:
    projects = db.scalars(
        select(PMProyecto)
        .where(PMProyecto.empresa_id == empresa_id)
        .order_by(PMProyecto.nombre.asc(), PMProyecto.created_at.desc())
    ).all()
    normalized_query = normalize_query_text(q)
    items: list[InventoryProjectSummaryItem] = []
    for project in projects:
        if normalized_query and normalized_query not in f"{project.nombre} {project.codigo or ''}".lower():
            continue
        rows = list_project_inventory_movement_rows(db, empresa_id=empresa_id, project_id=project.id)
        if not rows:
            continue
        total_qty = ZERO
        total_cost = ZERO
        last_movement_at = None
        for movement, _warehouse, _material, _user in rows:
            sign = project_movement_sign(movement)
            total_qty += sign * decimal_or_zero(movement.cantidad)
            total_cost += sign * project_movement_cost_total(movement)
            if last_movement_at is None or movement.created_at > last_movement_at:
                last_movement_at = movement.created_at
        items.append(
            InventoryProjectSummaryItem(
                project_id=project.id,
                nombre=project.nombre,
                codigo=project.codigo,
                estatus=project.estatus,
                total_materiales_consumidos=total_qty,
                costo_materiales_real=total_cost,
                movimientos_count=len(rows),
                ultimo_movimiento_at=last_movement_at,
            )
        )
    total = len(items)
    return total, items[offset : offset + limit]


def get_inventory_project_materials(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
) -> InventoryProjectMaterialsResponse:
    get_project_for_company_inventory(db, empresa_id, project_id)
    rows = list_project_inventory_movement_rows(db, empresa_id=empresa_id, project_id=project_id)
    grouped: dict[str, dict[str, object]] = {}
    for movement, warehouse, material, _user in rows:
        bucket = grouped.setdefault(
            material.id,
            {
                "material_id": material.id,
                "material_sku": material.sku,
                "material_nombre": material.nombre,
                "unidad": material.unidad,
                "cantidad_consumida": ZERO,
                "costo_total": ZERO,
                "almacenes_involucrados": set(),
                "ultima_salida_at": None,
                "tarea_titulos": set(),
                "partida_titulos": set(),
            },
        )
        sign = project_movement_sign(movement)
        bucket["cantidad_consumida"] = decimal_or_zero(bucket["cantidad_consumida"]) + (sign * decimal_or_zero(movement.cantidad))
        bucket["costo_total"] = decimal_or_zero(bucket["costo_total"]) + (sign * project_movement_cost_total(movement))
        bucket["almacenes_involucrados"].add(warehouse.nombre)
        if movement.tipo == "salida":
            current_last = bucket["ultima_salida_at"]
            if current_last is None or movement.created_at > current_last:
                bucket["ultima_salida_at"] = movement.created_at
        if movement.pm_tarea_nombre_snapshot:
            bucket["tarea_titulos"].add(movement.pm_tarea_nombre_snapshot)
        if movement.pm_partida_nombre_snapshot:
            bucket["partida_titulos"].add(movement.pm_partida_nombre_snapshot)

    items = [
        InventoryProjectMaterialItem(
            material_id=str(bucket["material_id"]),
            material_sku=str(bucket["material_sku"]),
            material_nombre=str(bucket["material_nombre"]),
            unidad=str(bucket["unidad"]),
            cantidad_consumida=decimal_or_zero(bucket["cantidad_consumida"]),
            costo_total=decimal_or_zero(bucket["costo_total"]),
            almacenes_involucrados=sorted(str(name) for name in bucket["almacenes_involucrados"]),
            ultima_salida_at=bucket["ultima_salida_at"],
            tarea_titulos=sorted(str(name) for name in bucket["tarea_titulos"]),
            partida_titulos=sorted(str(name) for name in bucket["partida_titulos"]),
        )
        for bucket in grouped.values()
    ]
    items.sort(key=lambda item: (item.material_nombre.lower(), item.material_sku.lower()))
    return InventoryProjectMaterialsResponse(project_id=project_id, items=items)


def get_inventory_project_movements(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[MovementItem]]:
    get_project_for_company_inventory(db, empresa_id, project_id)
    rows = list_project_inventory_movement_rows(db, empresa_id=empresa_id, project_id=project_id)
    total = len(rows)
    sliced_rows = rows[offset : offset + limit]
    return total, [build_movement_item(movement, warehouse, material, user) for movement, warehouse, material, user in sliced_rows]


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
    sin_stock: bool | None = None,
    sin_precio_venta: bool | None = None,
    sin_costo: bool | None = None,
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
    no_stock_condition = total_stock <= 0
    no_sale_price_condition = func.coalesce(Material.precio_venta, 0) <= 0
    no_cost_condition = and_(
        func.coalesce(Material.costo_unitario, 0) <= 0,
        func.coalesce(Material.costo_promedio_actual, 0) <= 0,
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
    if sin_stock is not None:
        query = query.where(no_stock_condition if sin_stock else ~no_stock_condition)
    if sin_precio_venta is not None:
        query = query.where(no_sale_price_condition if sin_precio_venta else ~no_sale_price_condition)
    if sin_costo is not None:
        query = query.where(no_cost_condition if sin_costo else ~no_cost_condition)

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
