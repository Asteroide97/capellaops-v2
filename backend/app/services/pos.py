from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Empresa, PosTurnoCaja, PosTurnoCajaMovimiento, Usuario, Venta, VentaDetalle
from app.models.inventory import Almacen, Existencia, Material
from app.schemas.pos import (
    PosActiveShiftResponse,
    PosCatalogItem,
    PosShiftMovementResponse,
    PosShiftResponse,
    PosTicketResponse,
    SaleDetailItem,
    SaleItem,
    SaleResponse,
    TicketLineItem,
)
from app.services.access import can_access_module
from app.services.inventory import (
    ZERO,
    apply_inventory_movement,
    apply_text_search,
    count_rows,
    get_material_for_company,
    get_or_create_stock,
    get_warehouse_for_company,
    normalize_code,
    normalize_optional_text,
    normalize_required_text,
)


PENDING_PAYMENT_METHODS = {"mixto"}


def validate_pos_access(user: Usuario, empresa: Empresa) -> None:
    if not can_access_module(user, empresa, "pos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La empresa no tiene acceso al modulo POS.",
        )


def generate_sale_folio() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = str(uuid4())[:6].upper()
    return f"VTA-{timestamp}-{suffix}"


def generate_shift_folio() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = str(uuid4())[:6].upper()
    return f"CAJA-{timestamp}-{suffix}"


def normalize_sale_folio(value: str | None) -> str:
    if value is None:
        return generate_sale_folio()
    cleaned = value.strip()
    if not cleaned:
        return generate_sale_folio()
    return normalize_code(cleaned, "Folio")


def normalize_shift_folio(value: str | None) -> str:
    if value is None:
        return generate_shift_folio()
    cleaned = value.strip()
    if not cleaned:
        return generate_shift_folio()
    return normalize_code(cleaned, "Folio")


def normalize_customer_email(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    return normalized.lower()


def ensure_unique_sale_folio(db: Session, empresa_id: str, folio: str, sale_id: str | None = None) -> None:
    query = select(Venta.id).where(Venta.empresa_id == empresa_id, Venta.folio == folio)
    if sale_id:
        query = query.where(Venta.id != sale_id)
    existing = db.scalar(query)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El folio de venta ya existe en esta empresa.",
        )


def ensure_unique_shift_folio(db: Session, empresa_id: str, folio: str, shift_id: str | None = None) -> None:
    query = select(PosTurnoCaja.id).where(PosTurnoCaja.empresa_id == empresa_id, PosTurnoCaja.folio == folio)
    if shift_id:
        query = query.where(PosTurnoCaja.id != shift_id)
    existing = db.scalar(query)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El folio del turno ya existe en esta empresa.",
        )


def get_sale_for_company(
    db: Session,
    empresa_id: str,
    sale_id: str,
    *,
    for_update: bool = False,
) -> Venta:
    query = select(Venta).where(Venta.id == sale_id, Venta.empresa_id == empresa_id)
    if for_update:
        query = query.with_for_update()
    sale = db.scalar(query)
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")
    return sale


def get_shift_for_company(
    db: Session,
    empresa_id: str,
    shift_id: str,
    *,
    for_update: bool = False,
) -> PosTurnoCaja:
    query = select(PosTurnoCaja).where(PosTurnoCaja.id == shift_id, PosTurnoCaja.empresa_id == empresa_id)
    if for_update:
        query = query.with_for_update()
    shift = db.scalar(query)
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno de caja no encontrado.")
    return shift


def get_active_shift_for_company(
    db: Session,
    empresa_id: str,
    warehouse_id: str,
    *,
    for_update: bool = False,
) -> PosTurnoCaja | None:
    query = select(PosTurnoCaja).where(
        PosTurnoCaja.empresa_id == empresa_id,
        PosTurnoCaja.almacen_id == warehouse_id,
        PosTurnoCaja.estatus == "abierta",
    )
    if for_update:
        query = query.with_for_update()
    return db.scalar(query.order_by(desc(PosTurnoCaja.opened_at), desc(PosTurnoCaja.id)))


def get_active_sale_warehouse(db: Session, empresa_id: str, warehouse_id: str) -> Almacen:
    warehouse = get_warehouse_for_company(db, empresa_id, warehouse_id)
    if not warehouse.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede vender desde un almacen inactivo.",
        )
    return warehouse


def get_active_sale_material(db: Session, empresa_id: str, material_id: str) -> Material:
    material = get_material_for_company(db, empresa_id, material_id)
    if not material.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede vender un material inactivo.",
        )
    return material


def create_audit_log(
    db: Session,
    *,
    empresa_id: str,
    usuario_id: str,
    action: str,
    entity_name: str,
    entity_id: str,
    ip_address: str | None,
    metadata_json: dict | None,
) -> None:
    db.add(
        AuditLog(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            action=action,
            entity_name=entity_name,
            entity_id=entity_id,
            ip_address=ip_address,
            metadata_json=metadata_json,
        )
    )


def build_sale_stock_map(
    db: Session,
    *,
    empresa_id: str,
    almacen_id: str,
    material_ids: list[str],
) -> dict[str, Decimal]:
    if not material_ids:
        return {}

    rows = db.execute(
        select(Existencia.material_id, func.coalesce(Existencia.cantidad, 0)).where(
            Existencia.empresa_id == empresa_id,
            Existencia.almacen_id == almacen_id,
            Existencia.material_id.in_(material_ids),
        )
    ).all()
    return {material_id: Decimal(quantity or ZERO) for material_id, quantity in rows}


def serialize_sale_detail(detail: VentaDetalle, *, stock_actual: Decimal | None = None) -> SaleDetailItem:
    return SaleDetailItem(
        id=detail.id,
        venta_id=detail.venta_id,
        material_id=detail.material_id,
        sku_snapshot=detail.sku_snapshot,
        nombre_snapshot=detail.nombre_snapshot,
        unidad=detail.material.unidad if detail.material else None,
        cantidad=detail.cantidad,
        precio_unitario=detail.precio_unitario,
        descuento_unitario=detail.descuento_unitario,
        subtotal_linea=detail.subtotal_linea,
        total_linea=detail.total_linea,
        movimiento_inventario_id=detail.movimiento_inventario_id,
        stock_actual=stock_actual,
    )


def build_sale_item(
    sale: Venta,
    almacen_nombre: str,
    vendedor_nombre: str,
    items_count: int,
    *,
    turno_folio: str | None = None,
) -> SaleItem:
    return SaleItem(
        id=sale.id,
        empresa_id=sale.empresa_id,
        folio=sale.folio,
        almacen_id=sale.almacen_id,
        almacen_nombre=almacen_nombre,
        turno_id=sale.turno_id,
        turno_folio=turno_folio,
        usuario_id=sale.usuario_id,
        vendedor_nombre=vendedor_nombre,
        cliente_nombre=sale.cliente_nombre,
        cliente_email=sale.cliente_email,
        subtotal=sale.subtotal,
        descuento_total=sale.descuento_total,
        impuesto_total=sale.impuesto_total,
        total=sale.total,
        metodo_pago=sale.metodo_pago,
        monto_recibido=sale.monto_recibido,
        cambio=sale.cambio,
        estatus=sale.estatus,
        notas=sale.notas,
        created_at=sale.created_at,
        paid_at=sale.paid_at,
        cancelled_at=sale.cancelled_at,
        cancelled_by_user_id=sale.cancelled_by_user_id,
        cancel_reason=sale.cancel_reason,
        items_count=items_count,
    )


def serialize_sale_response(db: Session, sale: Venta) -> SaleResponse:
    details = db.scalars(
        select(VentaDetalle)
        .where(VentaDetalle.venta_id == sale.id)
        .order_by(VentaDetalle.nombre_snapshot.asc(), VentaDetalle.sku_snapshot.asc(), VentaDetalle.id.asc())
    ).all()
    stock_map = build_sale_stock_map(
        db,
        empresa_id=sale.empresa_id,
        almacen_id=sale.almacen_id,
        material_ids=[detail.material_id for detail in details],
    )
    summary = build_sale_item(
        sale,
        sale.almacen.nombre,
        sale.usuario.full_name,
        len(details),
        turno_folio=sale.turno.folio if sale.turno else None,
    )
    return SaleResponse(
        **summary.model_dump(),
        details=[
            serialize_sale_detail(detail, stock_actual=stock_map.get(detail.material_id, ZERO))
            for detail in details
        ],
    )


def get_sale_ticket(db: Session, sale: Venta) -> PosTicketResponse:
    if sale.estatus == "suspendida":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo las ventas pagadas o canceladas generan ticket.",
        )
    details = db.scalars(
        select(VentaDetalle)
        .where(VentaDetalle.venta_id == sale.id)
        .order_by(VentaDetalle.nombre_snapshot.asc(), VentaDetalle.sku_snapshot.asc(), VentaDetalle.id.asc())
    ).all()
    return PosTicketResponse(
        id=sale.id,
        folio=sale.folio,
        turno_folio=sale.turno.folio if sale.turno else None,
        fecha=sale.paid_at or sale.created_at,
        paid_at=sale.paid_at,
        empresa=sale.empresa.name,
        almacen=sale.almacen.nombre,
        vendedor=sale.usuario.full_name,
        cliente_nombre=sale.cliente_nombre,
        cliente_email=sale.cliente_email,
        productos=[
            TicketLineItem(
                sku=detail.sku_snapshot,
                nombre=detail.nombre_snapshot,
                cantidad=detail.cantidad,
                precio_unitario=detail.precio_unitario,
                descuento_unitario=detail.descuento_unitario,
                subtotal_linea=detail.subtotal_linea,
                total_linea=detail.total_linea,
            )
            for detail in details
        ],
        subtotal=sale.subtotal,
        descuento_total=sale.descuento_total,
        impuesto_total=sale.impuesto_total,
        total=sale.total,
        metodo_pago=sale.metodo_pago,
        monto_recibido=sale.monto_recibido,
        cambio=sale.cambio,
        estatus=sale.estatus,
        notas=sale.notas,
        cancel_reason=sale.cancel_reason,
        cancelled_at=sale.cancelled_at,
    )


def list_sales(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    estatus: str | None = None,
    almacen_id: str | None = None,
    metodo_pago: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[SaleItem]]:
    sort_timestamp = func.coalesce(Venta.paid_at, Venta.created_at)
    id_query = select(Venta.id).where(Venta.empresa_id == empresa_id)
    id_query = apply_text_search(id_query, q, Venta.folio, Venta.cliente_nombre, Venta.cliente_email, Venta.notas)

    if estatus:
        id_query = id_query.where(Venta.estatus == estatus)
    if almacen_id:
        id_query = id_query.where(Venta.almacen_id == almacen_id)
    if metodo_pago:
        id_query = id_query.where(Venta.metodo_pago == metodo_pago)
    if fecha_desde:
        id_query = id_query.where(sort_timestamp >= fecha_desde)
    if fecha_hasta:
        id_query = id_query.where(sort_timestamp <= fecha_hasta)

    total = count_rows(db, id_query)
    page_ids = db.scalars(
        id_query.order_by(desc(sort_timestamp), desc(Venta.id)).offset(offset).limit(limit)
    ).all()
    if not page_ids:
        return total, []

    detail_count_subquery = (
        select(
            VentaDetalle.venta_id.label("venta_id"),
            func.count(VentaDetalle.id).label("detail_count"),
        )
        .where(VentaDetalle.venta_id.in_(page_ids))
        .group_by(VentaDetalle.venta_id)
        .subquery()
    )

    rows = db.execute(
        select(
            Venta,
            Almacen.nombre.label("almacen_nombre"),
            Usuario.full_name.label("vendedor_nombre"),
            PosTurnoCaja.folio.label("turno_folio"),
            func.coalesce(detail_count_subquery.c.detail_count, 0).label("detail_count"),
        )
        .join(Almacen, Venta.almacen_id == Almacen.id)
        .join(Usuario, Venta.usuario_id == Usuario.id)
        .outerjoin(PosTurnoCaja, Venta.turno_id == PosTurnoCaja.id)
        .outerjoin(detail_count_subquery, detail_count_subquery.c.venta_id == Venta.id)
        .where(Venta.id.in_(page_ids))
        .order_by(desc(func.coalesce(Venta.paid_at, Venta.created_at)), desc(Venta.id))
    ).all()

    items = [
        build_sale_item(sale, almacen_nombre, vendedor_nombre, int(detail_count), turno_folio=turno_folio)
        for sale, almacen_nombre, vendedor_nombre, turno_folio, detail_count in rows
    ]
    return total, items


def get_pos_catalog(
    db: Session,
    empresa_id: str,
    *,
    almacen_id: str,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[PosCatalogItem]]:
    get_active_sale_warehouse(db, empresa_id, almacen_id)

    stock_subquery = (
        select(
            Existencia.material_id.label("material_id"),
            func.coalesce(Existencia.cantidad, 0).label("cantidad"),
        )
        .where(
            Existencia.empresa_id == empresa_id,
            Existencia.almacen_id == almacen_id,
        )
        .subquery()
    )

    query = (
        select(
            Material,
            func.coalesce(stock_subquery.c.cantidad, 0).label("cantidad"),
        )
        .outerjoin(stock_subquery, stock_subquery.c.material_id == Material.id)
        .where(
            Material.empresa_id == empresa_id,
            Material.activo == True,
        )
    )
    query = apply_text_search(
        query,
        q,
        Material.sku,
        Material.codigo_barras,
        Material.nombre,
        Material.descripcion,
        Material.categoria,
    )

    total = count_rows(db, query)
    rows = db.execute(
        query.order_by(Material.nombre.asc(), Material.sku.asc()).offset(offset).limit(limit)
    ).all()
    items = [
        PosCatalogItem(
            material_id=material.id,
            sku=material.sku,
            nombre=material.nombre,
            unidad=material.unidad,
            precio=material.precio_venta or ZERO,
            existencia=cantidad,
            stock_minimo=material.stock_minimo,
            stock_bajo=Decimal(cantidad) <= Decimal(material.stock_minimo),
        )
        for material, cantidad in rows
    ]
    return total, items


def calculate_expected_cash(shift: PosTurnoCaja) -> Decimal:
    return (
        Decimal(shift.fondo_inicial or ZERO)
        + Decimal(shift.total_efectivo or ZERO)
        + Decimal(shift.ingresos_manuales or ZERO)
        - Decimal(shift.retiros_manuales or ZERO)
    )


def get_shift_sales_count(db: Session, shift_id: str) -> int:
    return int(
        db.scalar(
            select(func.count(Venta.id)).where(
                Venta.turno_id == shift_id,
                Venta.estatus == "pagada",
            )
        )
        or 0
    )


def get_shift_cancelled_summary(db: Session, shift_id: str) -> tuple[int, Decimal]:
    count_value, total_value = db.execute(
        select(
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.total), 0),
        ).where(
            Venta.turno_id == shift_id,
            Venta.estatus == "cancelada",
        )
    ).one()
    return int(count_value or 0), Decimal(total_value or ZERO)


def serialize_shift_movement(movement: PosTurnoCajaMovimiento) -> PosShiftMovementResponse:
    return PosShiftMovementResponse(
        id=movement.id,
        tipo=movement.tipo,
        monto=movement.monto,
        motivo=movement.motivo,
        usuario_id=movement.usuario_id,
        usuario_nombre=movement.usuario.full_name,
        created_at=movement.created_at,
    )


def serialize_shift_response(db: Session, shift: PosTurnoCaja) -> PosShiftResponse:
    movements = db.scalars(
        select(PosTurnoCajaMovimiento)
        .where(PosTurnoCajaMovimiento.turno_id == shift.id)
        .order_by(desc(PosTurnoCajaMovimiento.created_at), desc(PosTurnoCajaMovimiento.id))
    ).all()
    cancelled_count, cancelled_total = get_shift_cancelled_summary(db, shift.id)
    return PosShiftResponse(
        id=shift.id,
        empresa_id=shift.empresa_id,
        almacen_id=shift.almacen_id,
        almacen_nombre=shift.almacen.nombre,
        folio=shift.folio,
        estatus=shift.estatus,
        usuario_apertura_id=shift.usuario_apertura_id,
        usuario_apertura_nombre=shift.usuario_apertura.full_name,
        usuario_cierre_id=shift.usuario_cierre_id,
        usuario_cierre_nombre=shift.usuario_cierre.full_name if shift.usuario_cierre else None,
        fondo_inicial=shift.fondo_inicial,
        total_ventas=shift.total_ventas,
        total_efectivo=shift.total_efectivo,
        total_tarjeta=shift.total_tarjeta,
        total_transferencia=shift.total_transferencia,
        total_otro=shift.total_otro,
        ingresos_manuales=shift.ingresos_manuales,
        retiros_manuales=shift.retiros_manuales,
        efectivo_esperado=calculate_expected_cash(shift),
        efectivo_contado=shift.efectivo_contado,
        diferencia=shift.diferencia,
        notas_apertura=shift.notas_apertura,
        notas_cierre=shift.notas_cierre,
        opened_at=shift.opened_at,
        closed_at=shift.closed_at,
        ventas_count=get_shift_sales_count(db, shift.id),
        ventas_canceladas_count=cancelled_count,
        ventas_canceladas_total=cancelled_total,
        total_neto=Decimal(shift.total_ventas or ZERO),
        movimientos=[serialize_shift_movement(movement) for movement in movements],
    )


def get_active_shift_response(db: Session, empresa_id: str, warehouse_id: str) -> PosActiveShiftResponse:
    get_warehouse_for_company(db, empresa_id, warehouse_id)
    shift = get_active_shift_for_company(db, empresa_id, warehouse_id)
    return PosActiveShiftResponse(active_shift=serialize_shift_response(db, shift) if shift else None)


def adjust_shift_totals_for_sale(
    shift: PosTurnoCaja,
    *,
    sale_total: Decimal,
    payment_method: str,
    reverse: bool = False,
) -> None:
    multiplier = Decimal("-1") if reverse else Decimal("1")
    amount = Decimal(sale_total) * multiplier
    next_total_ventas = Decimal(shift.total_ventas or ZERO) + amount
    if next_total_ventas < ZERO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo ajustar el turno para esta venta.",
        )
    shift.total_ventas = next_total_ventas
    if payment_method == "efectivo":
        next_value = Decimal(shift.total_efectivo or ZERO) + amount
        if next_value < ZERO:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pudo ajustar el turno para esta venta.")
        shift.total_efectivo = next_value
    elif payment_method == "tarjeta":
        next_value = Decimal(shift.total_tarjeta or ZERO) + amount
        if next_value < ZERO:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pudo ajustar el turno para esta venta.")
        shift.total_tarjeta = next_value
    elif payment_method == "transferencia":
        next_value = Decimal(shift.total_transferencia or ZERO) + amount
        if next_value < ZERO:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pudo ajustar el turno para esta venta.")
        shift.total_transferencia = next_value
    else:
        next_value = Decimal(shift.total_otro or ZERO) + amount
        if next_value < ZERO:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pudo ajustar el turno para esta venta.")
        shift.total_otro = next_value


def refresh_closed_shift_difference(shift: PosTurnoCaja) -> None:
    if shift.efectivo_contado is None:
        shift.diferencia = None
        return
    shift.diferencia = Decimal(shift.efectivo_contado) - calculate_expected_cash(shift)


def open_shift(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    warehouse_id: str,
    fondo_inicial: Decimal,
    notas: str | None,
    ip_address: str | None,
) -> PosShiftResponse:
    validate_pos_access(user, empresa)
    warehouse = get_active_sale_warehouse(db, empresa.id, warehouse_id)

    existing_shift = get_active_shift_for_company(db, empresa.id, warehouse.id, for_update=True)
    if existing_shift:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un turno abierto para este almacen.",
        )

    folio = normalize_shift_folio(None)
    ensure_unique_shift_folio(db, empresa.id, folio)
    opened_at = datetime.now(timezone.utc)
    shift = PosTurnoCaja(
        empresa_id=empresa.id,
        almacen_id=warehouse.id,
        folio=folio,
        usuario_apertura_id=user.id,
        estatus="abierta",
        fondo_inicial=Decimal(fondo_inicial or ZERO),
        notas_apertura=normalize_optional_text(notas),
        opened_at=opened_at,
    )
    db.add(shift)
    db.flush()

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.shift.open",
        entity_name="pos_turno_caja",
        entity_id=shift.id,
        ip_address=ip_address,
        metadata_json={
            "folio": shift.folio,
            "almacen_id": shift.almacen_id,
            "fondo_inicial": str(shift.fondo_inicial),
        },
    )
    db.refresh(shift)
    return serialize_shift_response(db, shift)


def close_shift(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    warehouse_id: str,
    efectivo_contado: Decimal,
    notas: str | None,
    ip_address: str | None,
) -> PosShiftResponse:
    validate_pos_access(user, empresa)
    get_warehouse_for_company(db, empresa.id, warehouse_id)
    shift = get_active_shift_for_company(db, empresa.id, warehouse_id, for_update=True)
    if not shift:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay turno activo para este almacen.",
        )

    shift.efectivo_contado = Decimal(efectivo_contado or ZERO)
    shift.notas_cierre = normalize_optional_text(notas)
    shift.usuario_cierre_id = user.id
    shift.closed_at = datetime.now(timezone.utc)
    shift.estatus = "cerrada"
    refresh_closed_shift_difference(shift)
    db.flush()

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.shift.close",
        entity_name="pos_turno_caja",
        entity_id=shift.id,
        ip_address=ip_address,
        metadata_json={
            "folio": shift.folio,
            "efectivo_contado": str(shift.efectivo_contado),
            "diferencia": str(shift.diferencia or ZERO),
        },
    )
    db.refresh(shift)
    return serialize_shift_response(db, shift)


def add_shift_manual_movement(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    warehouse_id: str,
    movement_type: str,
    amount: Decimal,
    reason: str,
    ip_address: str | None,
) -> PosShiftResponse:
    validate_pos_access(user, empresa)
    get_warehouse_for_company(db, empresa.id, warehouse_id)
    shift = get_active_shift_for_company(db, empresa.id, warehouse_id, for_update=True)
    if not shift:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay turno activo para este almacen.",
        )

    normalized_reason = normalize_required_text(reason, "Motivo")
    movement = PosTurnoCajaMovimiento(
        empresa_id=empresa.id,
        turno_id=shift.id,
        tipo=movement_type,
        monto=Decimal(amount),
        motivo=normalized_reason,
        usuario_id=user.id,
    )
    db.add(movement)

    if movement_type == "ingreso":
        shift.ingresos_manuales = Decimal(shift.ingresos_manuales or ZERO) + Decimal(amount)
    else:
        shift.retiros_manuales = Decimal(shift.retiros_manuales or ZERO) + Decimal(amount)
    refresh_closed_shift_difference(shift)
    db.flush()

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action=f"pos.shift.{movement_type}",
        entity_name="pos_turno_caja",
        entity_id=shift.id,
        ip_address=ip_address,
        metadata_json={
            "folio": shift.folio,
            "monto": str(amount),
            "motivo": normalized_reason,
        },
    )
    db.refresh(shift)
    return serialize_shift_response(db, shift)


def resolve_sale_lines(
    db: Session,
    *,
    empresa_id: str,
    warehouse_id: str,
    items: list,
    validate_stock: bool,
) -> tuple[Almacen, list[dict], Decimal, Decimal, Decimal]:
    warehouse = get_active_sale_warehouse(db, empresa_id, warehouse_id)
    resolved_lines: list[dict] = []
    required_stock: dict[str, Decimal] = {}
    subtotal = ZERO
    descuento_total = ZERO

    for item in items:
        material = get_active_sale_material(db, empresa_id, item.material_id)
        quantity = Decimal(item.cantidad)
        if quantity <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad debe ser mayor a cero.",
            )

        price_override = getattr(item, "precio_unitario", None)
        price = Decimal(price_override) if price_override is not None else Decimal(material.precio_venta or ZERO)
        if price < ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El precio unitario no puede ser negativo.",
            )

        discount = Decimal(item.descuento_unitario or ZERO)
        if discount > price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El descuento unitario no puede exceder el precio unitario.",
            )

        line_subtotal = price * quantity
        line_discount_total = discount * quantity
        line_total = line_subtotal - line_discount_total

        subtotal += line_subtotal
        descuento_total += line_discount_total
        required_stock[material.id] = required_stock.get(material.id, ZERO) + quantity
        resolved_lines.append(
            {
                "material": material,
                "cantidad": quantity,
                "precio_unitario": price,
                "descuento_unitario": discount,
                "subtotal_linea": line_subtotal,
                "total_linea": line_total,
            }
        )

    if validate_stock:
        for material_id, quantity in required_stock.items():
            stock = get_or_create_stock(db, empresa_id, warehouse.id, material_id)
            if Decimal(stock.cantidad) < quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No hay stock suficiente.",
                )

    impuesto_total = ZERO
    total = subtotal - descuento_total + impuesto_total
    if total < ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El total de la venta no puede ser negativo.",
        )

    return warehouse, resolved_lines, subtotal, descuento_total, total


def resolve_sale_payment(
    *,
    metodo_pago: str,
    monto_recibido: Decimal | None,
    total: Decimal,
    require_payment_validation: bool,
) -> tuple[Decimal | None, Decimal | None]:
    if metodo_pago in PENDING_PAYMENT_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pagos mixtos quedan pendientes en esta fase.",
        )

    if not require_payment_validation:
        return None, None

    received_amount = Decimal(monto_recibido) if monto_recibido is not None else None
    change_amount: Decimal | None = None
    if metodo_pago == "efectivo":
        if received_amount is None or received_amount < total:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El monto recibido debe cubrir el total para pago en efectivo.",
            )
        change_amount = received_amount - total
    return received_amount, change_amount


def replace_sale_details(
    db: Session,
    *,
    sale: Venta,
    resolved_lines: list[dict],
    empresa: Empresa,
    user: Usuario,
    warehouse_id: str,
    create_inventory_movements: bool,
    ip_address: str | None,
) -> None:
    existing_details = db.scalars(
        select(VentaDetalle).where(VentaDetalle.venta_id == sale.id).order_by(VentaDetalle.id.asc())
    ).all()
    for detail in existing_details:
        db.delete(detail)
    db.flush()

    for line in resolved_lines:
        material = line["material"]
        detail = VentaDetalle(
            venta_id=sale.id,
            material_id=material.id,
            sku_snapshot=material.sku,
            nombre_snapshot=material.nombre,
            cantidad=line["cantidad"],
            precio_unitario=line["precio_unitario"],
            descuento_unitario=line["descuento_unitario"],
            subtotal_linea=line["subtotal_linea"],
            total_linea=line["total_linea"],
        )
        db.add(detail)
        db.flush()

        if create_inventory_movements:
            movement = apply_inventory_movement(
                db,
                user=user,
                empresa=empresa,
                almacen_id=warehouse_id,
                material_id=material.id,
                tipo="salida",
                cantidad=line["cantidad"],
                cantidad_nueva=None,
                referencia_tipo="pos_sale",
                referencia_id=sale.id,
                notas=f"Venta {sale.folio}",
                ip_address=ip_address,
            )
            detail.movimiento_inventario_id = movement.id


def create_sale(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    almacen_id: str,
    cliente_nombre: str | None,
    cliente_email: str | None,
    metodo_pago: str,
    monto_recibido: Decimal | None,
    notas: str | None,
    items: list,
    ip_address: str | None,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    warehouse, resolved_lines, subtotal, descuento_total, total = resolve_sale_lines(
        db,
        empresa_id=empresa.id,
        warehouse_id=almacen_id,
        items=items,
        validate_stock=True,
    )
    shift = get_active_shift_for_company(db, empresa.id, warehouse.id, for_update=True)
    if not shift:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Abre caja para poder cobrar ventas.",
        )

    received_amount, change_amount = resolve_sale_payment(
        metodo_pago=metodo_pago,
        monto_recibido=monto_recibido,
        total=total,
        require_payment_validation=True,
    )

    paid_at = datetime.now(timezone.utc)
    folio = normalize_sale_folio(None)
    ensure_unique_sale_folio(db, empresa.id, folio)
    sale = Venta(
        empresa_id=empresa.id,
        folio=folio,
        almacen_id=warehouse.id,
        turno_id=shift.id,
        usuario_id=user.id,
        cliente_nombre=normalize_optional_text(cliente_nombre),
        cliente_email=normalize_customer_email(cliente_email),
        subtotal=subtotal,
        descuento_total=descuento_total,
        impuesto_total=ZERO,
        total=total,
        metodo_pago=metodo_pago,
        monto_recibido=received_amount,
        cambio=change_amount,
        estatus="pagada",
        notas=normalize_optional_text(notas),
        paid_at=paid_at,
    )
    db.add(sale)
    db.flush()

    replace_sale_details(
        db,
        sale=sale,
        resolved_lines=resolved_lines,
        empresa=empresa,
        user=user,
        warehouse_id=warehouse.id,
        create_inventory_movements=True,
        ip_address=ip_address,
    )

    adjust_shift_totals_for_sale(shift, sale_total=sale.total, payment_method=sale.metodo_pago, reverse=False)
    refresh_closed_shift_difference(shift)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.create",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "almacen_id": sale.almacen_id,
            "turno_id": sale.turno_id,
            "metodo_pago": sale.metodo_pago,
            "subtotal": str(sale.subtotal),
            "descuento_total": str(sale.descuento_total),
            "total": str(sale.total),
            "items_count": len(resolved_lines),
        },
    )
    db.flush()
    db.refresh(sale)
    return serialize_sale_response(db, sale)


def create_suspended_sale(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    almacen_id: str,
    cliente_nombre: str | None,
    cliente_email: str | None,
    metodo_pago: str,
    notas: str | None,
    items: list,
    ip_address: str | None,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    warehouse, resolved_lines, subtotal, descuento_total, total = resolve_sale_lines(
        db,
        empresa_id=empresa.id,
        warehouse_id=almacen_id,
        items=items,
        validate_stock=False,
    )
    if metodo_pago in PENDING_PAYMENT_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pagos mixtos quedan pendientes en esta fase.",
        )

    folio = normalize_sale_folio(None)
    ensure_unique_sale_folio(db, empresa.id, folio)
    sale = Venta(
        empresa_id=empresa.id,
        folio=folio,
        almacen_id=warehouse.id,
        turno_id=None,
        usuario_id=user.id,
        cliente_nombre=normalize_optional_text(cliente_nombre),
        cliente_email=normalize_customer_email(cliente_email),
        subtotal=subtotal,
        descuento_total=descuento_total,
        impuesto_total=ZERO,
        total=total,
        metodo_pago=metodo_pago,
        monto_recibido=None,
        cambio=None,
        estatus="suspendida",
        notas=normalize_optional_text(notas),
        paid_at=None,
    )
    db.add(sale)
    db.flush()

    replace_sale_details(
        db,
        sale=sale,
        resolved_lines=resolved_lines,
        empresa=empresa,
        user=user,
        warehouse_id=warehouse.id,
        create_inventory_movements=False,
        ip_address=ip_address,
    )

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.suspend",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "almacen_id": sale.almacen_id,
            "estatus": sale.estatus,
            "total": str(sale.total),
            "items_count": len(resolved_lines),
        },
    )
    db.flush()
    db.refresh(sale)
    return serialize_sale_response(db, sale)


def resume_suspended_sale(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    sale = get_sale_for_company(db, empresa.id, sale_id)
    if sale.estatus != "suspendida":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden reanudar ventas suspendidas.",
        )
    return serialize_sale_response(db, sale)


def pay_suspended_sale(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    almacen_id: str,
    cliente_nombre: str | None,
    cliente_email: str | None,
    metodo_pago: str,
    monto_recibido: Decimal | None,
    notas: str | None,
    items: list,
    ip_address: str | None,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    sale = get_sale_for_company(db, empresa.id, sale_id, for_update=True)
    if sale.estatus == "cancelada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede cobrar una venta cancelada.",
        )
    if sale.estatus != "suspendida":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden cobrar ventas suspendidas.",
        )

    warehouse, resolved_lines, subtotal, descuento_total, total = resolve_sale_lines(
        db,
        empresa_id=empresa.id,
        warehouse_id=almacen_id,
        items=items,
        validate_stock=True,
    )
    shift = get_active_shift_for_company(db, empresa.id, warehouse.id, for_update=True)
    if not shift:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Abre caja para cobrar esta venta.",
        )

    received_amount, change_amount = resolve_sale_payment(
        metodo_pago=metodo_pago,
        monto_recibido=monto_recibido,
        total=total,
        require_payment_validation=True,
    )

    sale.almacen_id = warehouse.id
    sale.turno_id = shift.id
    sale.usuario_id = user.id
    sale.cliente_nombre = normalize_optional_text(cliente_nombre)
    sale.cliente_email = normalize_customer_email(cliente_email)
    sale.subtotal = subtotal
    sale.descuento_total = descuento_total
    sale.impuesto_total = ZERO
    sale.total = total
    sale.metodo_pago = metodo_pago
    sale.monto_recibido = received_amount
    sale.cambio = change_amount
    sale.estatus = "pagada"
    sale.notas = normalize_optional_text(notas)
    sale.paid_at = datetime.now(timezone.utc)
    sale.cancelled_at = None
    sale.cancelled_by_user_id = None
    sale.cancel_reason = None
    db.flush()

    replace_sale_details(
        db,
        sale=sale,
        resolved_lines=resolved_lines,
        empresa=empresa,
        user=user,
        warehouse_id=warehouse.id,
        create_inventory_movements=True,
        ip_address=ip_address,
    )

    adjust_shift_totals_for_sale(shift, sale_total=sale.total, payment_method=sale.metodo_pago, reverse=False)
    refresh_closed_shift_difference(shift)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.pay_suspended",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "almacen_id": sale.almacen_id,
            "turno_id": sale.turno_id,
            "metodo_pago": sale.metodo_pago,
            "total": str(sale.total),
            "items_count": len(resolved_lines),
        },
    )
    db.flush()
    db.refresh(sale)
    return serialize_sale_response(db, sale)


def cancel_sale(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    reason: str,
    ip_address: str | None,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    sale = get_sale_for_company(db, empresa.id, sale_id, for_update=True)

    if sale.estatus == "cancelada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede cancelar una venta ya cancelada.",
        )

    cancel_reason = normalize_required_text(reason, "Razon")

    if sale.estatus == "pagada":
        detail_rows = db.scalars(
            select(VentaDetalle).where(VentaDetalle.venta_id == sale.id).order_by(VentaDetalle.id.asc())
        ).all()

        if sale.turno_id:
            shift = get_shift_for_company(db, empresa.id, sale.turno_id, for_update=True)
            if shift.estatus != "abierta":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No se puede cancelar una venta de un turno cerrado en esta fase.",
                )
            adjust_shift_totals_for_sale(shift, sale_total=sale.total, payment_method=sale.metodo_pago, reverse=True)
            refresh_closed_shift_difference(shift)

        for detail in detail_rows:
            apply_inventory_movement(
                db,
                user=user,
                empresa=empresa,
                almacen_id=sale.almacen_id,
                material_id=detail.material_id,
                tipo="entrada",
                cantidad=detail.cantidad,
                cantidad_nueva=None,
                referencia_tipo="pos_sale_cancel",
                referencia_id=sale.id,
                notas=f"Cancelacion de venta {sale.folio}",
                ip_address=ip_address,
            )
    elif sale.estatus != "suspendida":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden cancelar ventas pagadas o suspendidas.",
        )

    sale.estatus = "cancelada"
    sale.cancelled_at = datetime.now(timezone.utc)
    sale.cancelled_by_user_id = user.id
    sale.cancel_reason = cancel_reason

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.cancel",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "reason": cancel_reason,
            "previous_status": "pagada" if sale.paid_at else "suspendida",
        },
    )
    db.flush()
    db.refresh(sale)
    return serialize_sale_response(db, sale)
