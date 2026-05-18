from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, aliased

from app.models import AuditLog, Empresa, Usuario, Venta, VentaDetalle
from app.models.inventory import Almacen, Existencia, Material
from app.schemas.pos import (
    PosCatalogItem,
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
    normalize_query_text,
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


def normalize_sale_folio(value: str | None) -> str:
    if value is None:
        return generate_sale_folio()
    cleaned = value.strip()
    if not cleaned:
        return generate_sale_folio()
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


def serialize_sale_detail(detail: VentaDetalle) -> SaleDetailItem:
    return SaleDetailItem(
        id=detail.id,
        venta_id=detail.venta_id,
        material_id=detail.material_id,
        sku_snapshot=detail.sku_snapshot,
        nombre_snapshot=detail.nombre_snapshot,
        cantidad=detail.cantidad,
        precio_unitario=detail.precio_unitario,
        descuento_unitario=detail.descuento_unitario,
        subtotal_linea=detail.subtotal_linea,
        total_linea=detail.total_linea,
        movimiento_inventario_id=detail.movimiento_inventario_id,
    )


def build_sale_item(sale: Venta, almacen_nombre: str, vendedor_nombre: str, items_count: int) -> SaleItem:
    return SaleItem(
        id=sale.id,
        empresa_id=sale.empresa_id,
        folio=sale.folio,
        almacen_id=sale.almacen_id,
        almacen_nombre=almacen_nombre,
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
    summary = build_sale_item(sale, sale.almacen.nombre, sale.usuario.full_name, len(details))
    return SaleResponse(**summary.model_dump(), details=[serialize_sale_detail(detail) for detail in details])


def get_sale_ticket(db: Session, sale: Venta) -> PosTicketResponse:
    details = db.scalars(
        select(VentaDetalle)
        .where(VentaDetalle.venta_id == sale.id)
        .order_by(VentaDetalle.nombre_snapshot.asc(), VentaDetalle.sku_snapshot.asc(), VentaDetalle.id.asc())
    ).all()
    return PosTicketResponse(
        id=sale.id,
        folio=sale.folio,
        fecha=sale.created_at,
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
    id_query = select(Venta.id).where(Venta.empresa_id == empresa_id)
    id_query = apply_text_search(id_query, q, Venta.folio, Venta.cliente_nombre, Venta.cliente_email, Venta.notas)

    if estatus:
        id_query = id_query.where(Venta.estatus == estatus)
    if almacen_id:
        id_query = id_query.where(Venta.almacen_id == almacen_id)
    if metodo_pago:
        id_query = id_query.where(Venta.metodo_pago == metodo_pago)
    if fecha_desde:
        id_query = id_query.where(Venta.created_at >= fecha_desde)
    if fecha_hasta:
        id_query = id_query.where(Venta.created_at <= fecha_hasta)

    total = count_rows(db, id_query)
    page_ids = db.scalars(
        id_query.order_by(desc(Venta.created_at), desc(Venta.id)).offset(offset).limit(limit)
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
            func.coalesce(detail_count_subquery.c.detail_count, 0).label("detail_count"),
        )
        .join(Almacen, Venta.almacen_id == Almacen.id)
        .join(Usuario, Venta.usuario_id == Usuario.id)
        .outerjoin(detail_count_subquery, detail_count_subquery.c.venta_id == Venta.id)
        .where(Venta.id.in_(page_ids))
        .order_by(desc(Venta.created_at), desc(Venta.id))
    ).all()

    items = [
        build_sale_item(sale, almacen_nombre, vendedor_nombre, int(detail_count))
        for sale, almacen_nombre, vendedor_nombre, detail_count in rows
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
    query = apply_text_search(query, q, Material.sku, Material.nombre, Material.descripcion, Material.categoria)

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
            precio=material.precio_venta,
            existencia=cantidad,
            stock_minimo=material.stock_minimo,
            stock_bajo=Decimal(cantidad) <= Decimal(material.stock_minimo),
        )
        for material, cantidad in rows
    ]
    return total, items


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

    if metodo_pago in PENDING_PAYMENT_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pagos mixtos quedan pendientes en esta fase.",
        )

    warehouse = get_active_sale_warehouse(db, empresa.id, almacen_id)

    resolved_lines: list[dict] = []
    required_stock: dict[str, Decimal] = {}
    subtotal = ZERO
    descuento_total = ZERO

    for item in items:
        material = get_active_sale_material(db, empresa.id, item.material_id)
        quantity = Decimal(item.cantidad)
        if quantity <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad debe ser mayor a 0.",
            )

        price = Decimal(material.precio_venta)
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

    for material_id, quantity in required_stock.items():
        stock = get_or_create_stock(db, empresa.id, warehouse.id, material_id)
        if Decimal(stock.cantidad) < quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stock insuficiente.")

    impuesto_total = ZERO
    total = subtotal - descuento_total + impuesto_total
    if total < ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El total de la venta no puede ser negativo.",
        )

    received_amount = Decimal(monto_recibido) if monto_recibido is not None else None
    change_amount: Decimal | None = None
    if metodo_pago == "efectivo":
        if received_amount is None or received_amount < total:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El monto recibido debe cubrir el total para pago en efectivo.",
            )
        change_amount = received_amount - total

    folio = normalize_sale_folio(None)
    ensure_unique_sale_folio(db, empresa.id, folio)

    sale = Venta(
        empresa_id=empresa.id,
        folio=folio,
        almacen_id=warehouse.id,
        usuario_id=user.id,
        cliente_nombre=normalize_optional_text(cliente_nombre),
        cliente_email=normalize_customer_email(cliente_email),
        subtotal=subtotal,
        descuento_total=descuento_total,
        impuesto_total=impuesto_total,
        total=total,
        metodo_pago=metodo_pago,
        monto_recibido=received_amount,
        cambio=change_amount,
        estatus="pagada",
        notas=normalize_optional_text(notas),
    )
    db.add(sale)
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

        movement = apply_inventory_movement(
            db,
            user=user,
            empresa=empresa,
            almacen_id=warehouse.id,
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
            detail="La venta ya fue cancelada.",
        )
    if sale.estatus != "pagada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden cancelar ventas pagadas.",
        )

    cancel_reason = normalize_required_text(reason, "Razon")
    detail_rows = db.scalars(
        select(VentaDetalle).where(VentaDetalle.venta_id == sale.id).order_by(VentaDetalle.id.asc())
    ).all()

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
        },
    )
    db.flush()
    db.refresh(sale)
    return serialize_sale_response(db, sale)
