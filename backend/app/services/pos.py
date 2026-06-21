from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AuditLog,
    CRMCliente,
    CRMContacto,
    Empresa,
    PosSaleAdjustment,
    PosTurnoCaja,
    PosTurnoCajaMovimiento,
    Usuario,
    Venta,
    VentaDetalle,
    VentaPago,
)
from app.models.inventory import Almacen, Existencia, Material
from app.schemas.pos import (
    PosActiveShiftResponse,
    PosCatalogItem,
    PosInvoiceRequestItem,
    PosInvoiceRequestListResponse,
    PosInvoiceRequestResponse,
    PosReportCancellationItem,
    PosReportDiscountSummary,
    PosReportKpis,
    PosReportPaymentMethodItem,
    PosReportSalesByCashierItem,
    PosReportSalesByWarehouseItem,
    PosReportSalesTimelineItem,
    PosReportSummaryResponse,
    PosReportTopProductItem,
    PosShiftCancellationReportItem,
    PosShiftMovementResponse,
    PosShiftReportResponse,
    PosShiftResponse,
    PosShiftSaleReportItem,
    PosTicketResponse,
    SaleEditableLineItem,
    SaleEditableSummaryResponse,
    SaleEditableTotals,
    SaleDetailItem,
    SaleItem,
    SalePaymentItem,
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


PAYMENT_METHODS = {"efectivo", "tarjeta", "transferencia", "otro"}
LEGACY_MIXED_PAYMENT_METHODS = {"mixto"}
SALE_LINE_TYPES = {"material", "manual", "servicio"}
NON_INVENTORY_LINE_TYPES = {"manual", "servicio"}
NON_EDITABLE_SALE_STATUSES = {"pagada", "cancelada"}
BLOCKING_INVOICE_EDIT_STATUSES = {"lista_para_facturar", "facturada", "preparada"}
INVOICE_READY_REQUIRED_FIELDS = (
    "factura_rfc",
    "factura_razon_social",
    "factura_email",
    "factura_uso_cfdi",
    "factura_regimen_fiscal",
    "factura_codigo_postal",
)
INVOICE_ALLOWED_STATUSES = {"no_solicitada", "solicitada", "pendiente_datos", "lista_para_facturar", "facturada", "cancelada"}
INVOICE_REVIEW_STATUSES = {"pendiente_datos", "lista_para_facturar", "en_revision", "observada", "preparada", "descartada"}
RFC_PATTERN = re.compile(r"^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


def normalize_invoice_email(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    normalized = normalized.lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingresa un email válido.",
        )
    return normalized


def normalize_invoice_rfc(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    normalized = normalized.upper().replace(" ", "")
    if not RFC_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingresa un RFC válido.",
        )
    return normalized


def normalize_invoice_catalog_value(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    return normalized.upper()


def resolve_invoice_request_status(sale: Venta) -> str:
    if sale.factura_estado not in INVOICE_ALLOWED_STATUSES:
        return "no_solicitada"
    has_minimum_data = all(getattr(sale, field) for field in INVOICE_READY_REQUIRED_FIELDS)
    return "lista_para_facturar" if has_minimum_data else "pendiente_datos"


def resolve_invoice_display_status(sale: Venta) -> str:
    if sale.factura_revision_estado in INVOICE_REVIEW_STATUSES:
        return str(sale.factura_revision_estado)
    if sale.factura_estado in INVOICE_ALLOWED_STATUSES:
        return str(sale.factura_estado)
    return "no_solicitada"


def validate_sale_invoice_request_allowed(sale: Venta) -> None:
    if sale.estatus == "cancelada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes solicitar factura de una venta cancelada.",
        )
    if sale.estatus != "pagada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo puedes solicitar factura de una venta pagada.",
        )


def normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_sale_report_timestamp(sale: Venta) -> datetime:
    base_value = sale.cancelled_at or sale.paid_at or sale.created_at
    return normalize_utc_datetime(base_value)


def normalize_sale_line_type(value: str | None) -> str:
    normalized = (normalize_optional_text(value) or "material").lower()
    if normalized not in SALE_LINE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selecciona un tipo de linea valido.",
        )
    return normalized


def quantize_decimal(value: Decimal | int | float | None) -> Decimal:
    return Decimal(str(value if value is not None else 0)).quantize(Decimal("0.0001"))


def resolve_sale_line_description(*, detail: VentaDetalle | None = None, line: dict | None = None) -> str:
    if detail is not None:
        return (
            normalize_optional_text(detail.descripcion_manual)
            or normalize_optional_text(detail.nombre_snapshot)
            or "Concepto manual"
        )
    if line is not None:
        return (
            normalize_optional_text(line.get("descripcion_manual"))
            or normalize_optional_text(line.get("nombre_snapshot"))
            or "Concepto manual"
        )
    return "Concepto manual"


def resolve_sale_line_sku(*, detail: VentaDetalle | None = None, line_type: str | None = None) -> str:
    resolved_type = line_type or (detail.tipo_linea if detail is not None else "manual")
    return "SERVICIO" if resolved_type == "servicio" else "MANUAL"


def format_report_bucket(value: datetime, grouping: str) -> str:
    normalized = normalize_utc_datetime(value)
    if grouping == "month":
        return f"{normalized.year:04d}-{normalized.month:02d}"
    if grouping == "week":
        week_start = (normalized - timedelta(days=normalized.weekday())).date()
        return week_start.isoformat()
    return normalized.date().isoformat()


def resolve_sale_detail_estimated_cost(detail: VentaDetalle) -> Decimal:
    movement = detail.movimiento_inventario
    material = detail.material

    if detail.costo_unitario_manual is not None and Decimal(detail.costo_unitario_manual) > ZERO:
        return Decimal(detail.costo_unitario_manual)
    if movement and movement.costo_unitario_snapshot is not None and Decimal(movement.costo_unitario_snapshot) > ZERO:
        return Decimal(movement.costo_unitario_snapshot)
    if movement and movement.costo_promedio_snapshot is not None and Decimal(movement.costo_promedio_snapshot) > ZERO:
        return Decimal(movement.costo_promedio_snapshot)
    if material and material.costo_promedio_actual is not None and Decimal(material.costo_promedio_actual) > ZERO:
        return Decimal(material.costo_promedio_actual)
    if material and material.costo_unitario is not None and Decimal(material.costo_unitario) > ZERO:
        return Decimal(material.costo_unitario)
    return ZERO


def get_sale_editable_reason(sale: Venta) -> str | None:
    if sale.estatus in NON_EDITABLE_SALE_STATUSES:
        if sale.estatus == "pagada":
            return "No se puede editar una venta pagada."
        if sale.estatus == "cancelada":
            return "No se puede editar una venta cancelada."
    invoice_status = resolve_invoice_display_status(sale)
    if invoice_status in BLOCKING_INVOICE_EDIT_STATUSES:
        return "No se puede editar una venta con solicitud de factura lista o facturada."
    if sale.estatus != "suspendida":
        return "La venta no permite edición en su estatus actual."
    return None


def ensure_sale_editable(sale: Venta) -> None:
    reason = get_sale_editable_reason(sale)
    if reason:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)


def serialize_sale_line_adjustment_snapshot(detail: VentaDetalle | dict | None) -> dict | None:
    if detail is None:
        return None
    if isinstance(detail, dict):
        line_type = normalize_sale_line_type(detail.get("tipo_linea"))
        material = detail.get("material")
        return {
            "line_id": detail.get("id"),
            "tipo_linea": line_type,
            "material_id": material.id if material is not None else detail.get("material_id"),
            "descripcion_manual": detail.get("descripcion_manual"),
            "sku": material.sku if material is not None else detail.get("sku_snapshot"),
            "nombre": material.nombre if material is not None else detail.get("nombre_snapshot"),
            "cantidad": str(detail.get("cantidad") or ZERO),
            "precio_unitario": str(detail.get("precio_unitario") or ZERO),
            "descuento_unitario": str(detail.get("descuento_unitario") or ZERO),
            "impuesto_tasa": str(detail.get("impuesto_tasa") or ZERO),
            "impuesto_linea": str(detail.get("impuesto_linea") or ZERO),
            "subtotal_linea": str(detail.get("subtotal_linea") or ZERO),
            "total_linea": str(detail.get("total_linea") or ZERO),
            "es_inventariable": bool(detail.get("es_inventariable", line_type == "material")),
            "costo_unitario_manual": (
                str(detail.get("costo_unitario_manual")) if detail.get("costo_unitario_manual") is not None else None
            ),
        }
    return {
        "line_id": detail.id,
        "tipo_linea": detail.tipo_linea,
        "material_id": detail.material_id,
        "descripcion_manual": detail.descripcion_manual,
        "sku": detail.sku_snapshot,
        "nombre": detail.nombre_snapshot,
        "cantidad": str(detail.cantidad or ZERO),
        "precio_unitario": str(detail.precio_unitario or ZERO),
        "descuento_unitario": str(detail.descuento_unitario or ZERO),
        "impuesto_tasa": str(detail.impuesto_tasa or ZERO),
        "impuesto_linea": str(detail.impuesto_linea or ZERO),
        "subtotal_linea": str(detail.subtotal_linea or ZERO),
        "total_linea": str(detail.total_linea or ZERO),
        "es_inventariable": bool(detail.es_inventariable),
        "costo_unitario_manual": str(detail.costo_unitario_manual) if detail.costo_unitario_manual is not None else None,
    }


def create_sale_adjustment(
    db: Session,
    *,
    empresa_id: str,
    sale_id: str,
    line_id: str | None,
    usuario_id: str,
    adjustment_type: str,
    before_json: dict | None,
    after_json: dict | None,
    motivo: str | None,
) -> None:
    db.add(
        PosSaleAdjustment(
            empresa_id=empresa_id,
            sale_id=sale_id,
            line_id=line_id,
            usuario_id=usuario_id,
            tipo=adjustment_type,
            before_json=before_json,
            after_json=after_json,
            motivo=normalize_optional_text(motivo),
        )
    )


def serialize_sale_totals_adjustment_snapshot(sale: Venta) -> dict:
    return {
        "sale_id": sale.id,
        "estatus": sale.estatus,
        "subtotal": str(sale.subtotal or ZERO),
        "descuento_lineas_total": str(sale.descuento_lineas_total or ZERO),
        "descuento_global": str(sale.descuento_global or ZERO),
        "descuento_total": str(sale.descuento_total or ZERO),
        "impuesto_total": str(sale.impuesto_total or ZERO),
        "total": str(sale.total or ZERO),
    }


def calculate_sale_paid_amount(sale: Venta) -> Decimal | None:
    if sale.monto_recibido is not None:
        return Decimal(sale.monto_recibido or ZERO)
    if sale.estatus == "suspendida":
        return None
    return Decimal(sale.total or ZERO)


def normalize_payment_reference(value: str | None) -> str | None:
    return normalize_optional_text(value)


def validate_sale_ticket_available(sale: Venta) -> None:
    if sale.estatus == "suspendida":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo las ventas pagadas o canceladas generan ticket.",
        )

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
    query = (
        select(Venta)
        .options(
            selectinload(Venta.empresa),
            selectinload(Venta.almacen),
            selectinload(Venta.turno),
            selectinload(Venta.usuario),
            selectinload(Venta.crm_cliente),
            selectinload(Venta.crm_contacto),
        )
        .where(Venta.id == sale_id, Venta.empresa_id == empresa_id)
    )
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


def get_crm_client_for_company(db: Session, empresa_id: str, client_id: str) -> CRMCliente:
    client = db.scalar(
        select(CRMCliente).where(
            CRMCliente.id == client_id,
            CRMCliente.empresa_id == empresa_id,
        )
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente CRM no encontrado.")
    return client


def get_crm_contact_for_company(db: Session, empresa_id: str, contact_id: str) -> CRMContacto:
    contact = db.scalar(
        select(CRMContacto)
        .options(selectinload(CRMContacto.cliente))
        .where(
            CRMContacto.id == contact_id,
            CRMContacto.empresa_id == empresa_id,
        )
    )
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto CRM no encontrado.")
    return contact


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


def coalesce_text(*values: str | None) -> str | None:
    for value in values:
        normalized = normalize_optional_text(value)
        if normalized is not None:
            return normalized
    return None


def build_sale_invoice_crm_defaults(sale: Venta) -> dict[str, str | None]:
    crm_client = sale.crm_cliente
    crm_contact = sale.crm_contacto
    return {
        "cliente_nombre": crm_client.nombre_comercial if crm_client else None,
        "rfc": crm_client.rfc if crm_client else None,
        "razon_social": crm_client.razon_social if crm_client else None,
        "email": (crm_contact.email if crm_contact else None) or (crm_client.email if crm_client else None),
        "codigo_postal": crm_client.codigo_postal if crm_client else None,
    }


def resolve_sale_crm_link(
    db: Session,
    *,
    empresa_id: str,
    cliente_id: str,
    contacto_id: str | None,
) -> tuple[CRMCliente, CRMContacto | None]:
    client = get_crm_client_for_company(db, empresa_id, cliente_id)
    contact = get_crm_contact_for_company(db, empresa_id, contacto_id) if contacto_id else None
    if contact and contact.cliente_id != client.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contacto CRM no pertenece al cliente indicado.",
        )
    return client, contact


def serialize_sale_detail(detail: VentaDetalle, *, stock_actual: Decimal | None = None) -> SaleDetailItem:
    return SaleDetailItem(
        id=detail.id,
        venta_id=detail.venta_id,
        tipo_linea=detail.tipo_linea,
        material_id=detail.material_id,
        material_nombre=detail.material.nombre if detail.material else None,
        descripcion=resolve_sale_line_description(detail=detail),
        descripcion_manual=detail.descripcion_manual,
        es_inventariable=bool(detail.es_inventariable),
        sku_snapshot=detail.sku_snapshot,
        nombre_snapshot=detail.nombre_snapshot,
        unidad=detail.material.unidad if detail.material else None,
        cantidad=detail.cantidad,
        precio_unitario=detail.precio_unitario,
        descuento_unitario=detail.descuento_unitario,
        descuento=Decimal(detail.descuento_unitario or ZERO) * Decimal(detail.cantidad or ZERO),
        impuesto_tasa=detail.impuesto_tasa,
        impuesto=detail.impuesto_linea,
        impuesto_linea=detail.impuesto_linea,
        subtotal_linea=detail.subtotal_linea,
        total_linea=detail.total_linea,
        movimiento_inventario_id=detail.movimiento_inventario_id,
        stock_actual=stock_actual,
    )


def serialize_sale_payment(payment: VentaPago) -> SalePaymentItem:
    return SalePaymentItem(
        id=payment.id,
        metodo=payment.metodo,
        monto=payment.monto,
        referencia=payment.referencia,
        notas=payment.notas,
        created_at=payment.created_at,
    )


def build_legacy_sale_payment(sale: Venta) -> list[SalePaymentItem]:
    if sale.estatus == "suspendida":
        return []
    amount = Decimal(sale.monto_recibido or sale.total or ZERO)
    if amount <= ZERO:
        return []
    return [
        SalePaymentItem(
            id=f"legacy-{sale.id}",
            metodo=sale.metodo_pago,
            monto=amount,
            referencia=None,
            notas=None,
            created_at=sale.paid_at or sale.created_at,
        )
    ]


def load_sale_payments(db: Session, sale_id: str) -> list[VentaPago]:
    return db.scalars(
        select(VentaPago)
        .where(VentaPago.venta_id == sale_id)
        .order_by(VentaPago.created_at.asc(), VentaPago.id.asc())
    ).all()


def get_serialized_sale_payments(db: Session, sale: Venta) -> list[SalePaymentItem]:
    payments = load_sale_payments(db, sale.id)
    if payments:
        return [serialize_sale_payment(payment) for payment in payments]
    return build_legacy_sale_payment(sale)


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
        crm_cliente_id=sale.crm_cliente_id,
        crm_cliente_nombre=sale.crm_cliente.nombre_comercial if sale.crm_cliente else None,
        crm_contacto_id=sale.crm_contacto_id,
        crm_contacto_nombre=sale.crm_contacto.nombre if sale.crm_contacto else None,
        subtotal=sale.subtotal,
        descuento_lineas_total=sale.descuento_lineas_total,
        descuento_global=sale.descuento_global,
        descuento_total=sale.descuento_total,
        impuesto_total=sale.impuesto_total,
        total=sale.total,
        metodo_pago=sale.metodo_pago,
        monto_recibido=sale.monto_recibido,
        monto_pagado=calculate_sale_paid_amount(sale),
        cambio=sale.cambio,
        estatus=sale.estatus,
        factura_estado=resolve_invoice_display_status(sale),
        factura_solicitada_at=sale.factura_solicitada_at,
        factura_cliente_nombre=sale.factura_cliente_nombre,
        factura_rfc=sale.factura_rfc,
        factura_razon_social=sale.factura_razon_social,
        factura_email=sale.factura_email,
        factura_uso_cfdi=sale.factura_uso_cfdi,
        factura_regimen_fiscal=sale.factura_regimen_fiscal,
        factura_codigo_postal=sale.factura_codigo_postal,
        factura_notas=sale.factura_notas,
        factura_requiere_factura_global=bool(sale.factura_requiere_factura_global),
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
    payments = get_serialized_sale_payments(db, sale)
    stock_map = build_sale_stock_map(
        db,
        empresa_id=sale.empresa_id,
        almacen_id=sale.almacen_id,
        material_ids=[detail.material_id for detail in details if detail.material_id],
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
        payments=payments,
        details=[
            serialize_sale_detail(
                detail,
                stock_actual=stock_map.get(detail.material_id, ZERO) if detail.material_id else None,
            )
            for detail in details
        ],
    )


def load_sale_details(
    db: Session,
    *,
    sale_id: str,
    for_update: bool = False,
) -> list[VentaDetalle]:
    query = (
        select(VentaDetalle)
        .options(
            selectinload(VentaDetalle.material),
            selectinload(VentaDetalle.movimiento_inventario),
        )
        .where(VentaDetalle.venta_id == sale_id)
        .order_by(VentaDetalle.id.asc())
    )
    if for_update:
        query = query.with_for_update()
    return db.scalars(query).all()


def get_sale_detail_for_company(
    db: Session,
    *,
    empresa_id: str,
    sale_id: str,
    line_id: str,
    for_update: bool = False,
) -> VentaDetalle:
    query = (
        select(VentaDetalle)
        .options(
            selectinload(VentaDetalle.material),
            selectinload(VentaDetalle.movimiento_inventario),
            selectinload(VentaDetalle.venta),
        )
        .join(Venta, Venta.id == VentaDetalle.venta_id)
        .where(
            VentaDetalle.id == line_id,
            VentaDetalle.venta_id == sale_id,
            Venta.empresa_id == empresa_id,
        )
    )
    if for_update:
        query = query.with_for_update()
    detail = db.scalar(query)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea de venta no encontrada.")
    return detail


def recalculate_sale_detail_models(
    db: Session,
    *,
    empresa_id: str,
    warehouse_id: str,
    details: list[VentaDetalle],
    validate_stock: bool,
) -> tuple[Almacen, list[dict], Decimal, Decimal, Decimal]:
    warehouse = get_active_sale_warehouse(db, empresa_id, warehouse_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La venta debe conservar al menos una linea.",
        )

    resolved_lines: list[dict] = []
    required_stock: dict[str, Decimal] = {}
    subtotal_bruto = ZERO
    descuento_lineas_total = ZERO
    impuesto_total = ZERO

    for detail in details:
        line_type = normalize_sale_line_type(detail.tipo_linea)
        quantity = quantize_decimal(detail.cantidad)
        if quantity <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad debe ser mayor a cero.",
            )

        material = None
        descripcion_manual = None
        nombre_snapshot = None
        sku_snapshot = None
        es_inventariable = line_type == "material"
        costo_unitario_manual = quantize_decimal(detail.costo_unitario_manual) if detail.costo_unitario_manual is not None else None

        if line_type == "material":
            if not detail.material_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selecciona un material valido.",
                )
            material = get_active_sale_material(db, empresa_id, detail.material_id)
            nombre_snapshot = material.nombre
            sku_snapshot = material.sku
            descripcion_manual = None
            es_inventariable = True
            costo_unitario_manual = None
        else:
            descripcion_manual = normalize_optional_text(detail.descripcion_manual or detail.nombre_snapshot)
            if descripcion_manual is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ingresa una descripcion para la linea manual.",
                )
            nombre_snapshot = descripcion_manual
            sku_snapshot = resolve_sale_line_sku(line_type=line_type)
            material = None
            detail.material_id = None
            es_inventariable = False

        price = quantize_decimal(detail.precio_unitario)
        if price < ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El precio unitario no puede ser negativo.",
            )

        discount = quantize_decimal(detail.descuento_unitario)
        line_subtotal = quantize_decimal(price * quantity)
        line_discount_total = quantize_decimal(discount * quantity)
        if line_discount_total > line_subtotal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El descuento no puede superar el subtotal.",
            )

        tax_rate = quantize_decimal(detail.impuesto_tasa)
        if tax_rate < ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El impuesto no puede ser negativo.",
            )

        line_subtotal_neto = quantize_decimal(line_subtotal - line_discount_total)
        line_tax_total = quantize_decimal(line_subtotal_neto * tax_rate)
        line_total = quantize_decimal(line_subtotal_neto + line_tax_total)

        detail.tipo_linea = line_type
        detail.descripcion_manual = descripcion_manual
        detail.es_inventariable = es_inventariable
        detail.costo_unitario_manual = costo_unitario_manual
        detail.sku_snapshot = sku_snapshot
        detail.nombre_snapshot = nombre_snapshot
        detail.cantidad = quantity
        detail.precio_unitario = price
        detail.descuento_unitario = discount
        detail.impuesto_tasa = tax_rate
        detail.impuesto_linea = line_tax_total
        detail.subtotal_linea = line_subtotal
        detail.total_linea = line_total

        subtotal_bruto = quantize_decimal(subtotal_bruto + line_subtotal)
        descuento_lineas_total = quantize_decimal(descuento_lineas_total + line_discount_total)
        impuesto_total = quantize_decimal(impuesto_total + line_tax_total)
        if material is not None:
            required_stock[material.id] = quantize_decimal(required_stock.get(material.id, ZERO) + quantity)

        resolved_lines.append(
            {
                "id": detail.id,
                "tipo_linea": line_type,
                "material": material,
                "material_id": material.id if material is not None else None,
                "descripcion_manual": descripcion_manual,
                "nombre_snapshot": nombre_snapshot,
                "sku_snapshot": sku_snapshot,
                "es_inventariable": es_inventariable,
                "costo_unitario_manual": costo_unitario_manual,
                "cantidad": quantity,
                "precio_unitario": price,
                "descuento_unitario": discount,
                "impuesto_tasa": tax_rate,
                "impuesto_linea": line_tax_total,
                "subtotal_linea": line_subtotal,
                "total_linea": line_total,
            }
        )

    if validate_stock:
        for material_id, quantity in required_stock.items():
            stock = get_or_create_stock(db, empresa_id, warehouse.id, material_id)
            if quantize_decimal(stock.cantidad) < quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No hay stock suficiente.",
                )

    return warehouse, resolved_lines, subtotal_bruto, descuento_lineas_total, impuesto_total


def apply_sale_totals(
    sale: Venta,
    *,
    subtotal_bruto: Decimal,
    descuento_lineas_total: Decimal,
    impuesto_total: Decimal,
    descuento_global: Decimal | None = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    subtotal_neto_lineas, normalized_global_discount, descuento_total, total = resolve_sale_totals(
        subtotal_bruto=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
        impuesto_total=impuesto_total,
        descuento_global=sale.descuento_global if descuento_global is None else descuento_global,
    )
    sale.subtotal = quantize_decimal(subtotal_bruto)
    sale.descuento_lineas_total = quantize_decimal(descuento_lineas_total)
    sale.descuento_global = quantize_decimal(normalized_global_discount)
    sale.descuento_total = quantize_decimal(descuento_total)
    sale.impuesto_total = quantize_decimal(impuesto_total)
    sale.total = quantize_decimal(total)
    return subtotal_neto_lineas, normalized_global_discount, descuento_total, total


def recalculate_editable_sale_models(
    db: Session,
    *,
    sale: Venta,
    validate_stock: bool = True,
    descuento_global: Decimal | None = None,
) -> tuple[list[VentaDetalle], list[dict], Decimal, Decimal, Decimal]:
    details = load_sale_details(db, sale_id=sale.id, for_update=False)
    _, resolved_lines, subtotal_bruto, descuento_lineas_total, impuesto_total = recalculate_sale_detail_models(
        db,
        empresa_id=sale.empresa_id,
        warehouse_id=sale.almacen_id,
        details=details,
        validate_stock=validate_stock,
    )
    apply_sale_totals(
        sale,
        subtotal_bruto=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
        impuesto_total=impuesto_total,
        descuento_global=descuento_global,
    )
    db.flush()
    return details, resolved_lines, subtotal_bruto, descuento_lineas_total, impuesto_total


def build_sale_editable_summary_response(
    db: Session,
    sale: Venta,
    *,
    details: list[VentaDetalle] | None = None,
) -> SaleEditableSummaryResponse:
    sale_details = details if details is not None else load_sale_details(db, sale_id=sale.id, for_update=False)
    stock_map = build_sale_stock_map(
        db,
        empresa_id=sale.empresa_id,
        almacen_id=sale.almacen_id,
        material_ids=[detail.material_id for detail in sale_details if detail.material_id],
    )
    summary = build_sale_item(
        sale,
        sale.almacen.nombre,
        sale.usuario.full_name,
        len(sale_details),
        turno_folio=sale.turno.folio if sale.turno else None,
    )
    editable_reason = get_sale_editable_reason(sale)
    editable = editable_reason is None
    line_discount_base_total = quantize_decimal(
        sum(
            (
                quantize_decimal(Decimal(detail.subtotal_linea or ZERO) - (Decimal(detail.descuento_unitario or ZERO) * Decimal(detail.cantidad or ZERO)))
                for detail in sale_details
            ),
            ZERO,
        )
    )
    remaining_global_discount = quantize_decimal(sale.descuento_global or ZERO)
    net_sale_before_tax = quantize_decimal(Decimal(sale.subtotal or ZERO) - Decimal(sale.descuento_total or ZERO))
    line_items: list[SaleEditableLineItem] = []
    total_cost = ZERO
    margin_complete = True
    collected_warnings: list[str] = []

    for index, detail in enumerate(sale_details):
        line_discount_total = quantize_decimal(Decimal(detail.descuento_unitario or ZERO) * Decimal(detail.cantidad or ZERO))
        line_subtotal_bruto = quantize_decimal(detail.subtotal_linea)
        line_subtotal_before_global = quantize_decimal(line_subtotal_bruto - line_discount_total)
        if remaining_global_discount > ZERO and line_discount_base_total > ZERO:
            if index == len(sale_details) - 1:
                allocated_global_discount = remaining_global_discount
            else:
                allocated_global_discount = quantize_decimal(
                    (Decimal(sale.descuento_global or ZERO) * line_subtotal_before_global) / line_discount_base_total
                )
                if allocated_global_discount > remaining_global_discount:
                    allocated_global_discount = remaining_global_discount
            remaining_global_discount = quantize_decimal(remaining_global_discount - allocated_global_discount)
        else:
            allocated_global_discount = ZERO
        line_subtotal_neto = quantize_decimal(line_subtotal_before_global - allocated_global_discount)

        warnings: list[str] = []
        estimated_unit_cost: Decimal | None = None
        if detail.material_id and bool(detail.es_inventariable):
            resolved_cost = quantize_decimal(resolve_sale_detail_estimated_cost(detail))
            if resolved_cost > ZERO:
                estimated_unit_cost = resolved_cost
            else:
                warnings.append("Material sin costo.")
        else:
            if detail.costo_unitario_manual is not None and quantize_decimal(detail.costo_unitario_manual) > ZERO:
                estimated_unit_cost = quantize_decimal(detail.costo_unitario_manual)
            else:
                warnings.append("Linea manual sin costo estimado.")

        cost_total: Decimal | None = None
        margin: Decimal | None = None
        margin_percentage: Decimal | None = None
        if estimated_unit_cost is not None:
            cost_total = quantize_decimal(estimated_unit_cost * Decimal(detail.cantidad or ZERO))
            margin = quantize_decimal(line_subtotal_neto - cost_total)
            if line_subtotal_neto > ZERO:
                margin_percentage = quantize_decimal((margin / line_subtotal_neto) * Decimal("100"))
            if quantize_decimal(detail.precio_unitario) < estimated_unit_cost:
                warnings.append("Precio debajo de costo.")
            if margin < ZERO:
                warnings.append("Margen negativo.")
            total_cost = quantize_decimal(total_cost + cost_total)
        else:
            margin_complete = False

        description = resolve_sale_line_description(detail=detail)
        for warning in warnings:
            collected_warnings.append(f"{description}: {warning}")

        line_items.append(
            SaleEditableLineItem(
                **serialize_sale_detail(
                    detail,
                    stock_actual=stock_map.get(detail.material_id, ZERO) if detail.material_id else None,
                ).model_dump(),
                subtotal_bruto=line_subtotal_bruto,
                descuento_total=line_discount_total,
                descuento_global_asignado=allocated_global_discount,
                subtotal_neto=line_subtotal_neto,
                costo_unitario_estimado=estimated_unit_cost,
                costo_total_estimado=cost_total,
                margen_estimado=margin,
                margen_porcentaje=margin_percentage,
                warnings=warnings,
            )
        )

    totals = SaleEditableTotals(
        subtotal_bruto=quantize_decimal(sale.subtotal),
        descuento_lineas_total=quantize_decimal(sale.descuento_lineas_total),
        descuento_global=quantize_decimal(sale.descuento_global),
        descuento_total=quantize_decimal(sale.descuento_total),
        subtotal_neto=net_sale_before_tax,
        impuesto_total=quantize_decimal(sale.impuesto_total),
        total=quantize_decimal(sale.total),
        costo_total_estimado=total_cost if margin_complete else None,
        margen_estimado=quantize_decimal(net_sale_before_tax - total_cost) if margin_complete else None,
        margen_completo=margin_complete,
        warnings=collected_warnings,
    )
    return SaleEditableSummaryResponse(
        sale=summary,
        lines=line_items,
        editable=editable,
        reason=editable_reason,
        totals=totals,
    )


def get_sale_editable_summary(
    db: Session,
    *,
    empresa_id: str,
    sale_id: str,
) -> SaleEditableSummaryResponse:
    sale = get_sale_for_company(db, empresa_id, sale_id)
    return build_sale_editable_summary_response(db, sale)


def add_sale_line(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    item,
    ip_address: str | None,
) -> SaleEditableSummaryResponse:
    validate_pos_access(user, empresa)
    sale = get_sale_for_company(db, empresa.id, sale_id, for_update=True)
    ensure_sale_editable(sale)

    line_type = normalize_sale_line_type(getattr(item, "tipo_linea", None))
    quantity = quantize_decimal(getattr(item, "cantidad", ZERO))
    if quantity <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad debe ser mayor a cero.")

    material = None
    description_manual = None
    sku_snapshot = None
    nombre_snapshot = None
    price_override = getattr(item, "precio_unitario", None)
    price = quantize_decimal(price_override) if price_override is not None else ZERO
    discount = quantize_decimal(getattr(item, "descuento_unitario", ZERO) or ZERO)
    tax_rate = quantize_decimal(getattr(item, "impuesto_tasa", ZERO) or ZERO)
    manual_cost = getattr(item, "costo_unitario_manual", None)
    costo_unitario_manual = quantize_decimal(manual_cost) if manual_cost is not None else None

    if line_type == "material":
        material_id = getattr(item, "material_id", None)
        if not material_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selecciona un material valido.")
        material = get_active_sale_material(db, empresa.id, material_id)
        if price_override is None:
            price = quantize_decimal(material.precio_venta or ZERO)
        nombre_snapshot = material.nombre
        sku_snapshot = material.sku
        description_manual = None
        costo_unitario_manual = None
    else:
        description_manual = normalize_optional_text(getattr(item, "descripcion", None))
        if description_manual is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ingresa una descripcion para la linea manual.",
            )
        nombre_snapshot = description_manual
        sku_snapshot = resolve_sale_line_sku(line_type=line_type)

    if price < ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El precio unitario no puede ser negativo.")
    if discount < ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El descuento no puede ser negativo.")
    if tax_rate < ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El impuesto no puede ser negativo.")

    new_detail = VentaDetalle(
        venta_id=sale.id,
        material_id=material.id if material is not None else None,
        tipo_linea=line_type,
        descripcion_manual=description_manual,
        es_inventariable=line_type == "material",
        costo_unitario_manual=costo_unitario_manual if line_type in NON_INVENTORY_LINE_TYPES else None,
        sku_snapshot=sku_snapshot,
        nombre_snapshot=nombre_snapshot,
        cantidad=quantity,
        precio_unitario=price,
        descuento_unitario=discount,
        impuesto_tasa=tax_rate,
        impuesto_linea=ZERO,
        subtotal_linea=ZERO,
        total_linea=ZERO,
    )
    db.add(new_detail)
    db.flush()

    details, _, _, _, _ = recalculate_editable_sale_models(db, sale=sale, validate_stock=True)
    create_sale_adjustment(
        db,
        empresa_id=empresa.id,
        sale_id=sale.id,
        line_id=new_detail.id,
        usuario_id=user.id,
        adjustment_type="add_line",
        before_json=None,
        after_json=serialize_sale_line_adjustment_snapshot(new_detail),
        motivo=getattr(item, "motivo", None),
    )
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.line.add",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={"folio": sale.folio, "line_id": new_detail.id, "tipo_linea": line_type},
    )
    db.flush()
    db.refresh(sale)
    return build_sale_editable_summary_response(db, sale, details=details)


def update_sale_line(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    line_id: str,
    payload,
    ip_address: str | None,
) -> SaleEditableSummaryResponse:
    validate_pos_access(user, empresa)
    sale = get_sale_for_company(db, empresa.id, sale_id, for_update=True)
    ensure_sale_editable(sale)
    detail = get_sale_detail_for_company(db, empresa_id=empresa.id, sale_id=sale_id, line_id=line_id, for_update=True)
    before_snapshot = serialize_sale_line_adjustment_snapshot(detail)

    provided_fields = set(getattr(payload, "model_fields_set", set())) - {"motivo"}
    if not provided_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay cambios para actualizar en la linea.",
        )

    if "cantidad" in provided_fields:
        detail.cantidad = quantize_decimal(payload.cantidad)
    if "precio_unitario" in provided_fields:
        detail.precio_unitario = quantize_decimal(payload.precio_unitario)
    if "descuento_unitario" in provided_fields:
        detail.descuento_unitario = quantize_decimal(payload.descuento_unitario)
    if "impuesto_tasa" in provided_fields:
        detail.impuesto_tasa = quantize_decimal(payload.impuesto_tasa)
    if "descripcion_manual" in provided_fields:
        if detail.tipo_linea not in NON_INVENTORY_LINE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La descripcion manual solo aplica a lineas manuales o de servicio.",
            )
        detail.descripcion_manual = normalize_required_text(payload.descripcion_manual, "Descripcion")
    if "costo_unitario_manual" in provided_fields:
        if detail.tipo_linea not in NON_INVENTORY_LINE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El costo manual solo aplica a lineas manuales o de servicio.",
            )
        detail.costo_unitario_manual = quantize_decimal(payload.costo_unitario_manual) if payload.costo_unitario_manual is not None else None

    details, _, _, _, _ = recalculate_editable_sale_models(db, sale=sale, validate_stock=True)
    create_sale_adjustment(
        db,
        empresa_id=empresa.id,
        sale_id=sale.id,
        line_id=detail.id,
        usuario_id=user.id,
        adjustment_type="update_line",
        before_json=before_snapshot,
        after_json=serialize_sale_line_adjustment_snapshot(detail),
        motivo=getattr(payload, "motivo", None),
    )
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.line.update",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={"folio": sale.folio, "line_id": detail.id},
    )
    db.flush()
    db.refresh(sale)
    return build_sale_editable_summary_response(db, sale, details=details)


def delete_sale_line(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    line_id: str,
    motivo: str | None,
    ip_address: str | None,
) -> SaleEditableSummaryResponse:
    validate_pos_access(user, empresa)
    sale = get_sale_for_company(db, empresa.id, sale_id, for_update=True)
    ensure_sale_editable(sale)
    details = load_sale_details(db, sale_id=sale.id, for_update=True)
    if len(details) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La venta debe conservar al menos una linea.",
        )
    detail = next((item for item in details if item.id == line_id), None)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea de venta no encontrada.")

    before_snapshot = serialize_sale_line_adjustment_snapshot(detail)
    db.delete(detail)
    db.flush()

    remaining_details, _, _, _, _ = recalculate_editable_sale_models(db, sale=sale, validate_stock=True)
    create_sale_adjustment(
        db,
        empresa_id=empresa.id,
        sale_id=sale.id,
        line_id=line_id,
        usuario_id=user.id,
        adjustment_type="delete_line",
        before_json=before_snapshot,
        after_json=None,
        motivo=motivo,
    )
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.line.delete",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={"folio": sale.folio, "line_id": line_id},
    )
    db.flush()
    db.refresh(sale)
    return build_sale_editable_summary_response(db, sale, details=remaining_details)


def recalculate_sale_adjustments(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    descuento_global: Decimal | None,
    motivo: str | None,
    ip_address: str | None,
) -> SaleEditableSummaryResponse:
    validate_pos_access(user, empresa)
    sale = get_sale_for_company(db, empresa.id, sale_id, for_update=True)
    ensure_sale_editable(sale)
    before_snapshot = serialize_sale_totals_adjustment_snapshot(sale)
    details, _, _, _, _ = recalculate_editable_sale_models(
        db,
        sale=sale,
        validate_stock=True,
        descuento_global=descuento_global,
    )
    after_snapshot = serialize_sale_totals_adjustment_snapshot(sale)
    create_sale_adjustment(
        db,
        empresa_id=empresa.id,
        sale_id=sale.id,
        line_id=None,
        usuario_id=user.id,
        adjustment_type="recalculate",
        before_json=before_snapshot,
        after_json=after_snapshot,
        motivo=motivo,
    )
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.recalculate",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={"folio": sale.folio},
    )
    db.flush()
    db.refresh(sale)
    return build_sale_editable_summary_response(db, sale, details=details)


def serialize_invoice_request_item(sale: Venta) -> PosInvoiceRequestItem:
    return PosInvoiceRequestItem(
        venta_id=sale.id,
        folio=sale.folio,
        fecha=sale.factura_solicitada_at or sale.paid_at or sale.created_at,
        total=sale.total,
        venta_estatus=sale.estatus,
        factura_estado=resolve_invoice_display_status(sale),
        cliente_nombre=sale.factura_cliente_nombre or sale.cliente_nombre,
        rfc=sale.factura_rfc,
        email=sale.factura_email or sale.cliente_email,
        uso_cfdi=sale.factura_uso_cfdi,
        fecha_solicitud=sale.factura_solicitada_at,
    )


def serialize_invoice_request_response(sale: Venta) -> PosInvoiceRequestResponse:
    return PosInvoiceRequestResponse(
        **serialize_invoice_request_item(sale).model_dump(),
        almacen_id=sale.almacen_id,
        almacen_nombre=sale.almacen.nombre,
        usuario_id=sale.usuario_id,
        vendedor_nombre=sale.usuario.full_name,
        cliente_email=sale.cliente_email,
        razon_social=sale.factura_razon_social,
        regimen_fiscal=sale.factura_regimen_fiscal,
        codigo_postal=sale.factura_codigo_postal,
        notas=sale.factura_notas,
        factura_crm_cliente_id=sale.factura_crm_cliente_id,
        factura_crm_cliente_nombre=sale.factura_crm_cliente.nombre_comercial if sale.factura_crm_cliente else None,
        factura_crm_contacto_id=sale.factura_crm_contacto_id,
        factura_crm_contacto_nombre=sale.factura_crm_contacto.nombre if sale.factura_crm_contacto else None,
        factura_requiere_factura_global=bool(sale.factura_requiere_factura_global),
    )


def get_sale_ticket(db: Session, sale: Venta) -> PosTicketResponse:
    validate_sale_ticket_available(sale)
    details = db.scalars(
        select(VentaDetalle)
        .where(VentaDetalle.venta_id == sale.id)
        .order_by(VentaDetalle.nombre_snapshot.asc(), VentaDetalle.sku_snapshot.asc(), VentaDetalle.id.asc())
    ).all()
    serialized_payments = get_serialized_sale_payments(db, sale)
    return PosTicketResponse(
        id=sale.id,
        folio=sale.folio,
        turno_folio=sale.turno.folio if sale.turno else None,
        fecha=sale.paid_at or sale.created_at,
        paid_at=sale.paid_at,
        empresa=sale.empresa.nombre_comercial or sale.empresa.razon_social or sale.empresa.name,
        almacen=sale.almacen.nombre,
        vendedor=sale.usuario.full_name,
        cliente_nombre=sale.cliente_nombre,
        cliente_email=sale.cliente_email,
        productos=[
            TicketLineItem(
                tipo_linea=detail.tipo_linea,
                sku=detail.sku_snapshot,
                nombre=resolve_sale_line_description(detail=detail),
                cantidad=detail.cantidad,
                precio_unitario=detail.precio_unitario,
                descuento_unitario=detail.descuento_unitario,
                descuento=Decimal(detail.descuento_unitario or ZERO) * Decimal(detail.cantidad or ZERO),
                impuesto_tasa=detail.impuesto_tasa,
                impuesto=detail.impuesto_linea,
                impuesto_linea=detail.impuesto_linea,
                subtotal_linea=detail.subtotal_linea,
                total_linea=detail.total_linea,
            )
            for detail in details
        ],
        subtotal=sale.subtotal,
        descuento_lineas_total=sale.descuento_lineas_total,
        descuento_global=sale.descuento_global,
        descuento_total=sale.descuento_total,
        impuesto_total=sale.impuesto_total,
        total=sale.total,
        metodo_pago=sale.metodo_pago,
        monto_recibido=sale.monto_recibido,
        monto_pagado=calculate_sale_paid_amount(sale),
        cambio=sale.cambio,
        estatus=sale.estatus,
        notas=sale.notas,
        cancel_reason=sale.cancel_reason,
        cancelled_at=sale.cancelled_at,
        pagos=serialized_payments,
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
        .options(
            selectinload(Venta.crm_cliente),
            selectinload(Venta.crm_contacto),
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


def get_sale_invoice_request(
    db: Session,
    empresa_id: str,
    sale_id: str,
) -> PosInvoiceRequestResponse:
    sale = db.scalar(
        select(Venta)
        .options(
            selectinload(Venta.almacen),
            selectinload(Venta.usuario),
            selectinload(Venta.crm_cliente),
            selectinload(Venta.crm_contacto),
            selectinload(Venta.factura_crm_cliente),
            selectinload(Venta.factura_crm_contacto),
        )
        .where(Venta.id == sale_id, Venta.empresa_id == empresa_id)
    )
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")
    return serialize_invoice_request_response(sale)


def upsert_sale_invoice_request(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    cliente_nombre: str | None,
    rfc: str | None,
    razon_social: str | None,
    email: str | None,
    uso_cfdi: str | None,
    regimen_fiscal: str | None,
    codigo_postal: str | None,
    notas: str | None,
    ip_address: str | None,
    audit_action: str,
) -> PosInvoiceRequestResponse:
    validate_pos_access(user, empresa)
    sale = db.scalar(
        select(Venta)
        .options(
            selectinload(Venta.almacen),
            selectinload(Venta.usuario),
            selectinload(Venta.crm_cliente),
            selectinload(Venta.crm_contacto),
            selectinload(Venta.factura_crm_cliente),
            selectinload(Venta.factura_crm_contacto),
        )
        .where(Venta.id == sale_id, Venta.empresa_id == empresa.id)
        .with_for_update()
    )
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")

    validate_sale_invoice_request_allowed(sale)
    crm_defaults = build_sale_invoice_crm_defaults(sale)

    sale.factura_cliente_nombre = coalesce_text(
        cliente_nombre,
        sale.factura_cliente_nombre,
        crm_defaults["cliente_nombre"],
        sale.cliente_nombre,
    )
    sale.factura_rfc = normalize_invoice_rfc(coalesce_text(rfc, sale.factura_rfc, crm_defaults["rfc"]))
    sale.factura_razon_social = coalesce_text(
        razon_social,
        sale.factura_razon_social,
        crm_defaults["razon_social"],
        crm_defaults["cliente_nombre"],
    )
    sale.factura_email = normalize_invoice_email(
        coalesce_text(email, sale.factura_email, crm_defaults["email"], sale.cliente_email)
    )
    sale.factura_crm_cliente_id = sale.crm_cliente_id or sale.factura_crm_cliente_id
    sale.factura_crm_contacto_id = sale.crm_contacto_id or sale.factura_crm_contacto_id
    sale.factura_uso_cfdi = normalize_invoice_catalog_value(coalesce_text(uso_cfdi, sale.factura_uso_cfdi))
    sale.factura_regimen_fiscal = normalize_invoice_catalog_value(
        coalesce_text(regimen_fiscal, sale.factura_regimen_fiscal)
    )
    sale.factura_codigo_postal = coalesce_text(
        codigo_postal,
        sale.factura_codigo_postal,
        crm_defaults["codigo_postal"],
    )
    sale.factura_notas = coalesce_text(notas, sale.factura_notas)
    sale.factura_requiere_factura_global = False

    if not sale.factura_solicitada_at:
        sale.factura_solicitada_at = datetime.now(timezone.utc)
    sale.factura_estado = resolve_invoice_request_status(sale)
    sale.factura_revision_estado = sale.factura_estado
    sale.factura_revision_notas = None
    sale.factura_revisada_por_user_id = None
    sale.factura_revisada_at = None
    sale.factura_preparada_at = None
    sale.factura_descartada_at = None
    sale.factura_error_datos = None

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action=audit_action,
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "factura_estado": sale.factura_estado,
            "factura_rfc": sale.factura_rfc,
            "factura_email": sale.factura_email,
            "factura_uso_cfdi": sale.factura_uso_cfdi,
        },
    )
    db.flush()
    db.refresh(sale)
    return serialize_invoice_request_response(sale)


def link_sale_to_crm(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    cliente_id: str,
    contacto_id: str | None,
    ip_address: str | None,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    sale = get_sale_for_company(db, empresa.id, sale_id, for_update=True)
    client, contact = resolve_sale_crm_link(
        db,
        empresa_id=empresa.id,
        cliente_id=cliente_id,
        contacto_id=contacto_id,
    )
    sale.crm_cliente_id = client.id
    sale.crm_contacto_id = contact.id if contact else None
    sale.crm_cliente = client
    sale.crm_contacto = contact
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.crm_link",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "crm_cliente_id": sale.crm_cliente_id,
            "crm_contacto_id": sale.crm_contacto_id,
        },
    )
    db.refresh(sale)
    return serialize_sale_response(db, sale)


def unlink_sale_from_crm(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    ip_address: str | None,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    sale = get_sale_for_company(db, empresa.id, sale_id, for_update=True)
    sale.crm_cliente_id = None
    sale.crm_contacto_id = None
    sale.crm_cliente = None
    sale.crm_contacto = None
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="pos.sale.crm_unlink",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={"folio": sale.folio},
    )
    db.refresh(sale)
    return serialize_sale_response(db, sale)


def list_invoice_requests(
    db: Session,
    empresa_id: str,
    *,
    estado: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    rfc: str | None = None,
    folio: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[PosInvoiceRequestItem]]:
    request_timestamp = func.coalesce(Venta.factura_solicitada_at, Venta.paid_at, Venta.created_at)
    display_status = func.coalesce(Venta.factura_revision_estado, Venta.factura_estado)
    id_query = select(Venta.id).where(
        Venta.empresa_id == empresa_id,
        Venta.estatus == "pagada",
        Venta.factura_estado != "no_solicitada",
    )

    if estado:
        id_query = id_query.where(display_status == estado)
    if fecha_desde:
        id_query = id_query.where(request_timestamp >= fecha_desde)
    if fecha_hasta:
        id_query = id_query.where(request_timestamp <= fecha_hasta)
    if rfc:
        id_query = apply_text_search(id_query, rfc, Venta.factura_rfc)
    if folio:
        id_query = apply_text_search(id_query, folio, Venta.folio)

    total = count_rows(db, id_query)
    page_ids = db.scalars(
        id_query.order_by(desc(request_timestamp), desc(Venta.id)).offset(offset).limit(limit)
    ).all()
    if not page_ids:
        return total, []

    sales = db.scalars(
        select(Venta)
        .options(selectinload(Venta.almacen), selectinload(Venta.usuario))
        .where(Venta.id.in_(page_ids))
        .order_by(desc(func.coalesce(Venta.factura_solicitada_at, Venta.paid_at, Venta.created_at)), desc(Venta.id))
    ).all()
    return total, [serialize_invoice_request_item(sale) for sale in sales]


def get_pos_report_summary(
    db: Session,
    empresa_id: str,
    *,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    almacen_id: str | None = None,
    usuario_id: str | None = None,
    estatus: str | None = None,
    agrupacion: str = "day",
) -> PosReportSummaryResponse:
    report_timestamp = func.coalesce(Venta.cancelled_at, Venta.paid_at, Venta.created_at)
    query = (
        select(Venta)
        .options(
            selectinload(Venta.almacen),
            selectinload(Venta.usuario),
            selectinload(Venta.turno),
            selectinload(Venta.cancelled_by_user),
            selectinload(Venta.pagos),
            selectinload(Venta.detalles).selectinload(VentaDetalle.material),
            selectinload(Venta.detalles).selectinload(VentaDetalle.movimiento_inventario),
        )
        .where(Venta.empresa_id == empresa_id)
    )

    if fecha_desde:
        query = query.where(report_timestamp >= fecha_desde)
    if fecha_hasta:
        query = query.where(report_timestamp <= fecha_hasta)
    if almacen_id:
        query = query.where(Venta.almacen_id == almacen_id)
    if usuario_id:
        query = query.where(Venta.usuario_id == usuario_id)
    if estatus:
        query = query.where(Venta.estatus == estatus)

    sales = db.scalars(query.order_by(desc(report_timestamp), desc(Venta.id))).all()

    method_totals: dict[str, dict[str, Decimal | int]] = {
        "efectivo": {"total": ZERO, "ventas_count": 0},
        "tarjeta": {"total": ZERO, "ventas_count": 0},
        "transferencia": {"total": ZERO, "ventas_count": 0},
        "otro": {"total": ZERO, "ventas_count": 0},
    }
    timeline: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"ventas_count": 0, "total_neto": ZERO, "cancelado": ZERO}
    )
    cashier_totals: dict[str, dict[str, str | int | Decimal | None]] = {}
    warehouse_totals: dict[str, dict[str, str | int | Decimal | None]] = {}
    product_totals: dict[str, dict[str, Decimal | str]] = {}

    ventas_pagadas_count = 0
    ventas_canceladas_count = 0
    ventas_suspendidas_count = 0
    total_bruto = ZERO
    total_descuentos = ZERO
    total_cancelado = ZERO
    total_pagado = ZERO
    utilidad_estimada = ZERO
    descuento_lineas_total = ZERO
    descuento_global_total = ZERO
    cancelaciones: list[PosReportCancellationItem] = []

    for sale in sales:
        sale_timestamp = get_sale_report_timestamp(sale)
        bucket_label = format_report_bucket(sale_timestamp, agrupacion)
        sale_sign = ZERO

        if sale.estatus == "pagada":
            ventas_pagadas_count += 1
            total_pagado += Decimal(sale.total or ZERO)
            total_bruto += Decimal(sale.subtotal or ZERO)
            total_descuentos += Decimal(sale.descuento_total or ZERO)
            descuento_lineas_total += Decimal(sale.descuento_lineas_total or ZERO)
            descuento_global_total += Decimal(sale.descuento_global or ZERO)
            timeline[bucket_label]["ventas_count"] += 1
            timeline[bucket_label]["total_neto"] += Decimal(sale.total or ZERO)
            sale_sign = Decimal("1")
        elif sale.estatus == "cancelada":
            ventas_canceladas_count += 1
            total_bruto += Decimal(sale.subtotal or ZERO)
            total_descuentos += Decimal(sale.descuento_total or ZERO)
            total_cancelado += Decimal(sale.total or ZERO)
            descuento_lineas_total += Decimal(sale.descuento_lineas_total or ZERO)
            descuento_global_total += Decimal(sale.descuento_global or ZERO)
            timeline[bucket_label]["cancelado"] += Decimal(sale.total or ZERO)
            sale_sign = Decimal("-1")
            cancelaciones.append(
                PosReportCancellationItem(
                    venta_id=sale.id,
                    folio=sale.folio,
                    fecha=sale.cancelled_at or sale_timestamp,
                    total=Decimal(sale.total or ZERO),
                    motivo=sale.cancel_reason,
                    usuario=sale.cancelled_by_user.full_name if sale.cancelled_by_user else None,
                )
            )
        else:
            ventas_suspendidas_count += 1

        if sale.estatus in {"pagada", "cancelada"}:
            payments = get_sale_payment_breakdown(db, sale=sale)
            counted_methods: set[str] = set()
            for payment in payments:
                method = str(payment["metodo"] or "").strip().lower()
                if method not in method_totals:
                    method_totals[method] = {"total": ZERO, "ventas_count": 0}
                method_totals[method]["total"] += Decimal(payment["monto"] or ZERO) * sale_sign
                if sale.estatus == "pagada" and method not in counted_methods:
                    method_totals[method]["ventas_count"] += 1
                    counted_methods.add(method)

        if sale.estatus in {"pagada", "cancelada"}:
            cashier_key = sale.usuario_id
            if cashier_key not in cashier_totals:
                cashier_totals[cashier_key] = {
                    "usuario_id": sale.usuario_id,
                    "nombre": sale.usuario.full_name,
                    "ventas_count": 0,
                    "total_neto": ZERO,
                }
            warehouse_key = sale.almacen_id
            if warehouse_key not in warehouse_totals:
                warehouse_totals[warehouse_key] = {
                    "almacen_id": sale.almacen_id,
                    "nombre": sale.almacen.nombre,
                    "ventas_count": 0,
                    "total_neto": ZERO,
                }

            if sale.estatus == "pagada":
                cashier_totals[cashier_key]["ventas_count"] += 1
                warehouse_totals[warehouse_key]["ventas_count"] += 1

            cashier_totals[cashier_key]["total_neto"] += Decimal(sale.total or ZERO) * sale_sign
            warehouse_totals[warehouse_key]["total_neto"] += Decimal(sale.total or ZERO) * sale_sign

        if sale.estatus in {"pagada", "cancelada"}:
            for detail in sale.detalles:
                unit_cost = resolve_sale_detail_estimated_cost(detail)
                quantity = Decimal(detail.cantidad or ZERO)
                signed_quantity = quantity * sale_sign
                signed_total = Decimal(detail.total_linea or ZERO) * sale_sign
                signed_cost = unit_cost * quantity * sale_sign
                utilidad_estimada += signed_total - signed_cost

                if not detail.material_id:
                    continue

                product_entry = product_totals.get(detail.material_id)
                if not product_entry:
                    product_entry = {
                        "material_id": detail.material_id,
                        "sku": detail.sku_snapshot,
                        "nombre": detail.nombre_snapshot,
                        "cantidad": ZERO,
                        "total_venta": ZERO,
                        "costo_estimado": ZERO,
                        "utilidad_estimada": ZERO,
                    }
                    product_totals[detail.material_id] = product_entry

                product_entry["cantidad"] += signed_quantity
                product_entry["total_venta"] += signed_total
                product_entry["costo_estimado"] += signed_cost
                product_entry["utilidad_estimada"] += signed_total - signed_cost

    total_neto = total_pagado - total_cancelado
    ticket_promedio = total_neto / Decimal(ventas_pagadas_count) if ventas_pagadas_count else ZERO
    descuentos = PosReportDiscountSummary(
        descuento_lineas_total=descuento_lineas_total,
        descuento_global_total=descuento_global_total,
        descuento_total=descuento_lineas_total + descuento_global_total,
    )

    timeline_items = [
        PosReportSalesTimelineItem(
            fecha=fecha,
            ventas_count=int(data["ventas_count"] or 0),
            total_neto=Decimal(data["total_neto"] or ZERO),
            cancelado=Decimal(data["cancelado"] or ZERO),
        )
        for fecha, data in sorted(timeline.items(), key=lambda item: item[0])
    ]

    payment_items = [
        PosReportPaymentMethodItem(
            metodo=method,
            total=Decimal(data["total"] or ZERO),
            ventas_count=int(data["ventas_count"] or 0),
        )
        for method, data in method_totals.items()
        if Decimal(data["total"] or ZERO) != ZERO or int(data["ventas_count"] or 0) > 0 or method in PAYMENT_METHODS
    ]

    cashier_items = sorted(
        [
            PosReportSalesByCashierItem(
                usuario_id=str(data["usuario_id"]) if data["usuario_id"] else None,
                nombre=str(data["nombre"] or "No registrado"),
                ventas_count=int(data["ventas_count"] or 0),
                total_neto=Decimal(data["total_neto"] or ZERO),
            )
            for data in cashier_totals.values()
        ],
        key=lambda item: (-item.total_neto, item.nombre.lower()),
    )

    warehouse_items = sorted(
        [
            PosReportSalesByWarehouseItem(
                almacen_id=str(data["almacen_id"]) if data["almacen_id"] else None,
                nombre=str(data["nombre"] or "No registrado"),
                ventas_count=int(data["ventas_count"] or 0),
                total_neto=Decimal(data["total_neto"] or ZERO),
            )
            for data in warehouse_totals.values()
        ],
        key=lambda item: (-item.total_neto, item.nombre.lower()),
    )

    product_items = sorted(
        [
            PosReportTopProductItem(
                material_id=str(data["material_id"]),
                sku=str(data["sku"]),
                nombre=str(data["nombre"]),
                cantidad=Decimal(data["cantidad"] or ZERO),
                total_venta=Decimal(data["total_venta"] or ZERO),
                costo_estimado=Decimal(data["costo_estimado"] or ZERO),
                utilidad_estimada=Decimal(data["utilidad_estimada"] or ZERO),
            )
            for data in product_totals.values()
            if Decimal(data["cantidad"] or ZERO) > ZERO or Decimal(data["total_venta"] or ZERO) > ZERO
        ],
        key=lambda item: (-item.cantidad, -item.total_venta, item.nombre.lower()),
    )

    cancelaciones.sort(key=lambda item: item.fecha, reverse=True)

    return PosReportSummaryResponse(
        agrupacion=agrupacion,
        kpis=PosReportKpis(
            ventas_count=len(sales),
            ventas_pagadas_count=ventas_pagadas_count,
            ventas_canceladas_count=ventas_canceladas_count,
            ventas_suspendidas_count=ventas_suspendidas_count,
            total_bruto=total_bruto,
            total_descuentos=total_descuentos,
            total_cancelado=total_cancelado,
            total_neto=total_neto,
            ticket_promedio=ticket_promedio,
            utilidad_estimada=utilidad_estimada,
        ),
        metodos_pago=payment_items,
        ventas_por_dia=timeline_items,
        ventas_por_cajero=cashier_items,
        ventas_por_almacen=warehouse_items,
        productos_mas_vendidos=product_items,
        descuentos=descuentos,
        cancelaciones=cancelaciones,
    )


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
    total_neto = Decimal(shift.total_ventas or ZERO)
    total_bruto = total_neto + cancelled_total
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
        total_bruto=total_bruto,
        ventas_canceladas_total=cancelled_total,
        total_neto=total_neto,
        movimientos=[serialize_shift_movement(movement) for movement in movements],
    )


def get_active_shift_response(db: Session, empresa_id: str, warehouse_id: str) -> PosActiveShiftResponse:
    get_warehouse_for_company(db, empresa_id, warehouse_id)
    shift = get_active_shift_for_company(db, empresa_id, warehouse_id)
    return PosActiveShiftResponse(active_shift=serialize_shift_response(db, shift) if shift else None)


def serialize_shift_sale_report_item(sale: Venta) -> PosShiftSaleReportItem:
    return PosShiftSaleReportItem(
        id=sale.id,
        folio=sale.folio,
        fecha=sale.paid_at or sale.created_at,
        estatus=sale.estatus,
        total=sale.total,
        subtotal=sale.subtotal,
        descuento_lineas_total=sale.descuento_lineas_total,
        descuento_global=sale.descuento_global,
        descuento_total=sale.descuento_total,
        metodo_pago=sale.metodo_pago,
        cliente_nombre=sale.cliente_nombre,
        cliente_email=sale.cliente_email,
        vendedor_nombre=sale.usuario.full_name,
        turno_folio=sale.turno.folio if sale.turno else None,
        monto_pagado=calculate_sale_paid_amount(sale),
        cambio=sale.cambio,
    )


def serialize_shift_cancellation_report_item(sale: Venta) -> PosShiftCancellationReportItem:
    return PosShiftCancellationReportItem(
        id=sale.id,
        folio=sale.folio,
        fecha=sale.cancelled_at or sale.paid_at or sale.created_at,
        total=sale.total,
        metodo_pago=sale.metodo_pago,
        cliente_nombre=sale.cliente_nombre,
        motivo=sale.cancel_reason,
        usuario_id=sale.cancelled_by_user_id,
        usuario_nombre=sale.cancelled_by_user.full_name if sale.cancelled_by_user else None,
    )


def list_shifts(
    db: Session,
    empresa_id: str,
    *,
    almacen_id: str | None = None,
    estatus: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    usuario_id: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[PosShiftResponse]]:
    id_query = select(PosTurnoCaja.id).where(PosTurnoCaja.empresa_id == empresa_id)

    if almacen_id:
        id_query = id_query.where(PosTurnoCaja.almacen_id == almacen_id)
    if estatus:
        id_query = id_query.where(PosTurnoCaja.estatus == estatus)
    if fecha_desde:
        id_query = id_query.where(PosTurnoCaja.opened_at >= fecha_desde)
    if fecha_hasta:
        id_query = id_query.where(PosTurnoCaja.opened_at <= fecha_hasta)
    if usuario_id:
        id_query = id_query.where(
            or_(
                PosTurnoCaja.usuario_apertura_id == usuario_id,
                PosTurnoCaja.usuario_cierre_id == usuario_id,
            )
        )

    total = count_rows(db, id_query)
    page_ids = db.scalars(
        id_query.order_by(desc(PosTurnoCaja.opened_at), desc(PosTurnoCaja.id)).offset(offset).limit(limit)
    ).all()
    if not page_ids:
        return total, []

    shifts = db.scalars(
        select(PosTurnoCaja)
        .where(PosTurnoCaja.id.in_(page_ids))
        .order_by(desc(PosTurnoCaja.opened_at), desc(PosTurnoCaja.id))
    ).all()
    return total, [serialize_shift_response(db, shift) for shift in shifts]


def get_shift_detail_response(db: Session, empresa_id: str, shift_id: str) -> PosShiftResponse:
    shift = get_shift_for_company(db, empresa_id, shift_id)
    return serialize_shift_response(db, shift)


def get_shift_report(db: Session, empresa_id: str, shift_id: str) -> PosShiftReportResponse:
    shift = get_shift_for_company(db, empresa_id, shift_id)
    shift_response = serialize_shift_response(db, shift)
    sales = db.scalars(
        select(Venta)
        .where(Venta.empresa_id == empresa_id, Venta.turno_id == shift.id)
        .order_by(desc(func.coalesce(Venta.paid_at, Venta.created_at)), desc(Venta.id))
    ).all()
    cancelled_sales = [sale for sale in sales if sale.estatus == "cancelada"]
    opened_at = normalize_utc_datetime(shift.opened_at)
    duration_end = normalize_utc_datetime(shift.closed_at) if shift.closed_at else datetime.now(timezone.utc)
    duration_seconds = max(0, int((duration_end - opened_at).total_seconds()))
    descuento_lineas_total = sum((Decimal(sale.descuento_lineas_total or ZERO) for sale in sales), ZERO)
    descuento_global_total = sum((Decimal(sale.descuento_global or ZERO) for sale in sales), ZERO)
    descuentos_totales = sum((Decimal(sale.descuento_total or ZERO) for sale in sales), ZERO)

    return PosShiftReportResponse(
        shift=shift_response,
        generated_at=datetime.now(timezone.utc),
        duracion_segundos=duration_seconds,
        descuento_lineas_total=descuento_lineas_total,
        descuento_global_total=descuento_global_total,
        descuentos_totales=descuentos_totales,
        movimientos_manuales=shift_response.movimientos,
        ventas=[serialize_shift_sale_report_item(sale) for sale in sales],
        cancelaciones=[serialize_shift_cancellation_report_item(sale) for sale in cancelled_sales],
    )


def adjust_shift_totals_for_sale(
    shift: PosTurnoCaja,
    *,
    sale_total: Decimal,
    payment_method: str,
    monto_recibido: Decimal | None = None,
    change_amount: Decimal | None = None,
    reverse: bool = False,
) -> None:
    if payment_method == "efectivo":
        payment_amount = Decimal(monto_recibido or sale_total or ZERO)
    else:
        payment_amount = Decimal(sale_total or ZERO)
    payments = [{"metodo": payment_method, "monto": payment_amount}]
    adjust_shift_totals_for_payments(
        shift,
        sale_total=sale_total,
        payments=payments,
        change_amount=change_amount,
        reverse=reverse,
    )


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
    subtotal_bruto = ZERO
    descuento_lineas_total = ZERO
    impuesto_total = ZERO

    for item in items:
        line_type = normalize_sale_line_type(getattr(item, "tipo_linea", None))
        quantity = Decimal(item.cantidad)
        if quantity <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad debe ser mayor a cero.",
            )

        material = None
        descripcion_manual = None
        nombre_snapshot = None
        sku_snapshot = None
        es_inventariable = line_type == "material"
        costo_unitario_manual = None

        if line_type == "material":
            material_id = getattr(item, "material_id", None)
            if not material_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selecciona un material valido.",
                )
            material = get_active_sale_material(db, empresa_id, material_id)
            price_override = getattr(item, "precio_unitario", None)
            price = Decimal(price_override) if price_override is not None else Decimal(material.precio_venta or ZERO)
            nombre_snapshot = material.nombre
            sku_snapshot = material.sku
        else:
            descripcion_manual = normalize_optional_text(getattr(item, "descripcion", None))
            if descripcion_manual is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ingresa una descripcion para la linea manual.",
                )
            price_override = getattr(item, "precio_unitario", None)
            price = Decimal(price_override or ZERO)
            nombre_snapshot = descripcion_manual
            sku_snapshot = resolve_sale_line_sku(line_type=line_type)

        if price < ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El precio unitario no puede ser negativo.",
            )

        discount = Decimal(getattr(item, "descuento_unitario", ZERO) or ZERO)
        line_subtotal = price * quantity
        line_discount_total = discount * quantity
        if line_discount_total > line_subtotal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El descuento no puede superar el subtotal.",
            )

        tax_rate = Decimal(getattr(item, "impuesto_tasa", ZERO) or ZERO)
        if tax_rate < ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El impuesto no puede ser negativo.",
            )

        line_subtotal_neto = line_subtotal - line_discount_total
        line_tax_total = line_subtotal_neto * tax_rate
        line_total = line_subtotal_neto + line_tax_total

        subtotal_bruto += line_subtotal
        descuento_lineas_total += line_discount_total
        impuesto_total += line_tax_total
        if material is not None:
            required_stock[material.id] = required_stock.get(material.id, ZERO) + quantity
        resolved_lines.append(
            {
                "tipo_linea": line_type,
                "material": material,
                "descripcion_manual": descripcion_manual,
                "nombre_snapshot": nombre_snapshot,
                "sku_snapshot": sku_snapshot,
                "es_inventariable": es_inventariable,
                "costo_unitario_manual": costo_unitario_manual,
                "cantidad": quantity,
                "precio_unitario": price,
                "descuento_unitario": discount,
                "impuesto_tasa": tax_rate,
                "impuesto_linea": line_tax_total,
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

    subtotal_despues_descuentos = subtotal_bruto - descuento_lineas_total
    if subtotal_despues_descuentos < ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El total de la venta no puede ser negativo.",
        )

    return warehouse, resolved_lines, subtotal_bruto, descuento_lineas_total, impuesto_total


def resolve_sale_totals(
    *,
    subtotal_bruto: Decimal,
    descuento_lineas_total: Decimal,
    impuesto_total: Decimal,
    descuento_global: Decimal | None,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    normalized_global_discount = Decimal(descuento_global or ZERO)
    if normalized_global_discount < ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El descuento global no puede ser negativo.",
        )

    subtotal_despues_descuentos_linea = subtotal_bruto - descuento_lineas_total
    if normalized_global_discount > subtotal_despues_descuentos_linea:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El descuento no puede superar el subtotal.",
        )

    descuento_total = descuento_lineas_total + normalized_global_discount
    normalized_tax_total = Decimal(impuesto_total or ZERO)
    if normalized_tax_total < ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El impuesto no puede ser negativo.",
        )

    total = subtotal_despues_descuentos_linea - normalized_global_discount + normalized_tax_total
    if total < ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El total de la venta no puede ser negativo.",
        )

    return subtotal_despues_descuentos_linea, normalized_global_discount, descuento_total, total


def resolve_sale_payments(
    *,
    metodo_pago: str | None,
    monto_recibido: Decimal | None,
    payments: list | None,
    total: Decimal,
    require_payment_validation: bool,
) -> tuple[list[dict], str, Decimal | None, Decimal | None]:
    raw_payments = [payment for payment in (payments or []) if payment is not None]

    if not raw_payments and metodo_pago in LEGACY_MIXED_PAYMENT_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agrega los pagos para completar un cobro mixto.",
        )

    resolved_payments: list[dict] = []
    if raw_payments:
        for payment in raw_payments:
            method = str(payment.metodo or "").strip().lower()
            if method not in PAYMENT_METHODS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selecciona un metodo de pago valido.",
                )
            amount = Decimal(payment.monto or ZERO)
            if amount <= ZERO:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El monto del pago debe ser mayor a cero.",
                )
            resolved_payments.append(
                {
                    "metodo": method,
                    "monto": amount,
                    "referencia": normalize_payment_reference(getattr(payment, "referencia", None)),
                    "notas": normalize_optional_text(getattr(payment, "notas", None)),
                }
            )
    else:
        method = str(metodo_pago or "").strip().lower()
        if method in LEGACY_MIXED_PAYMENT_METHODS or method not in PAYMENT_METHODS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selecciona un metodo de pago valido.",
            )
        if method == "efectivo":
            tendered_amount = Decimal(monto_recibido or ZERO)
            if require_payment_validation and tendered_amount < total:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El total pagado no cubre el total de la venta.",
                )
        else:
            tendered_amount = Decimal(monto_recibido or total or ZERO)
            if tendered_amount <= ZERO:
                tendered_amount = Decimal(total or ZERO)
        if tendered_amount <= ZERO and require_payment_validation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El monto del pago debe ser mayor a cero.",
            )
        resolved_payments.append(
            {
                "metodo": method,
                "monto": tendered_amount,
                "referencia": None,
                "notas": None,
            }
        )

    if not require_payment_validation:
        principal_method = resolved_payments[0]["metodo"] if len(resolved_payments) == 1 else "mixto"
        paid_amount = sum((Decimal(payment["monto"]) for payment in resolved_payments), ZERO)
        return resolved_payments, principal_method, paid_amount or None, None

    total_paid = sum((Decimal(payment["monto"]) for payment in resolved_payments), ZERO)
    if total_paid < total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El total pagado no cubre el total de la venta.",
        )

    cash_total = sum(
        (Decimal(payment["monto"]) for payment in resolved_payments if payment["metodo"] == "efectivo"),
        ZERO,
    )
    change_amount = total_paid - total
    if change_amount > ZERO and change_amount > cash_total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cambio solo puede generarse con efectivo.",
        )

    principal_method = resolved_payments[0]["metodo"] if len(resolved_payments) == 1 else "mixto"
    return resolved_payments, principal_method, total_paid, change_amount if change_amount > ZERO else ZERO


def replace_sale_payments(
    db: Session,
    *,
    sale: Venta,
    payments: list[dict],
    turno_id: str | None,
) -> None:
    existing_payments = db.scalars(
        select(VentaPago).where(VentaPago.venta_id == sale.id).order_by(VentaPago.created_at.asc(), VentaPago.id.asc())
    ).all()
    for payment in existing_payments:
        db.delete(payment)
    db.flush()

    for payment in payments:
        db.add(
            VentaPago(
                empresa_id=sale.empresa_id,
                venta_id=sale.id,
                turno_id=turno_id,
                metodo=payment["metodo"],
                monto=payment["monto"],
                referencia=payment.get("referencia"),
                notas=payment.get("notas"),
            )
        )
    db.flush()


def get_sale_payment_breakdown(
    db: Session,
    *,
    sale: Venta,
) -> list[dict]:
    payments = list(sale.pagos) if getattr(sale, "pagos", None) else load_sale_payments(db, sale.id)
    if payments:
        return [
            {
                "metodo": payment.metodo,
                "monto": Decimal(payment.monto or ZERO),
                "referencia": payment.referencia,
                "notas": payment.notas,
            }
            for payment in payments
        ]

    fallback_amount = Decimal(sale.monto_recibido or sale.total or ZERO)
    if fallback_amount <= ZERO or sale.estatus == "suspendida":
        return []

    return [
        {
            "metodo": sale.metodo_pago,
            "monto": fallback_amount,
            "referencia": None,
            "notas": None,
        }
    ]


def calculate_shift_payment_totals(
    payments: list[dict],
    *,
    change_amount: Decimal | None = None,
) -> dict[str, Decimal]:
    totals = {method: ZERO for method in PAYMENT_METHODS}
    for payment in payments:
        method = payment["metodo"]
        if method not in totals:
            continue
        totals[method] += Decimal(payment["monto"] or ZERO)

    if change_amount and change_amount > ZERO:
        totals["efectivo"] -= Decimal(change_amount)
        if totals["efectivo"] < ZERO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se pudo ajustar el turno para esta venta.",
            )
    return totals


def adjust_shift_totals_for_payments(
    shift: PosTurnoCaja,
    *,
    sale_total: Decimal,
    payments: list[dict],
    change_amount: Decimal | None = None,
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

    payment_totals = calculate_shift_payment_totals(payments, change_amount=change_amount)
    for method, method_total in payment_totals.items():
        next_value = getattr(shift, f"total_{method}") + (method_total * multiplier)
        if next_value < ZERO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se pudo ajustar el turno para esta venta.",
            )
        setattr(shift, f"total_{method}", next_value)


def resolve_sale_payment(
    *,
    metodo_pago: str | None,
    monto_recibido: Decimal | None,
    payments: list | None,
    total: Decimal,
    require_payment_validation: bool,
) -> tuple[list[dict], str, Decimal | None, Decimal | None]:
    return resolve_sale_payments(
        metodo_pago=metodo_pago,
        monto_recibido=monto_recibido,
        payments=payments,
        total=total,
        require_payment_validation=require_payment_validation,
    )


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
            material_id=material.id if material else None,
            tipo_linea=line["tipo_linea"],
            descripcion_manual=line["descripcion_manual"],
            es_inventariable=bool(line["es_inventariable"]),
            costo_unitario_manual=line["costo_unitario_manual"],
            sku_snapshot=material.sku if material else line["sku_snapshot"],
            nombre_snapshot=material.nombre if material else line["nombre_snapshot"],
            cantidad=line["cantidad"],
            precio_unitario=line["precio_unitario"],
            descuento_unitario=line["descuento_unitario"],
            impuesto_tasa=line["impuesto_tasa"],
            impuesto_linea=line["impuesto_linea"],
            subtotal_linea=line["subtotal_linea"],
            total_linea=line["total_linea"],
        )
        db.add(detail)
        db.flush()

        if create_inventory_movements and material is not None and bool(line["es_inventariable"]):
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
    metodo_pago: str | None,
    monto_recibido: Decimal | None,
    descuento_global: Decimal | None,
    notas: str | None,
    items: list,
    payments: list | None,
    ip_address: str | None,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    warehouse, resolved_lines, subtotal_bruto, descuento_lineas_total, impuesto_total = resolve_sale_lines(
        db,
        empresa_id=empresa.id,
        warehouse_id=almacen_id,
        items=items,
        validate_stock=True,
    )
    subtotal_neto_lineas, normalized_global_discount, descuento_total, total = resolve_sale_totals(
        subtotal_bruto=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
        impuesto_total=impuesto_total,
        descuento_global=descuento_global,
    )
    shift = get_active_shift_for_company(db, empresa.id, warehouse.id, for_update=True)
    if not shift:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Abre caja para poder cobrar ventas.",
        )

    resolved_payments, resolved_payment_method, received_amount, change_amount = resolve_sale_payment(
        metodo_pago=metodo_pago,
        monto_recibido=monto_recibido,
        payments=payments,
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
        subtotal=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
        descuento_global=normalized_global_discount,
        descuento_total=descuento_total,
        impuesto_total=impuesto_total,
        total=total,
        metodo_pago=resolved_payment_method,
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

    replace_sale_payments(db, sale=sale, payments=resolved_payments, turno_id=shift.id)
    adjust_shift_totals_for_payments(
        shift,
        sale_total=sale.total,
        payments=resolved_payments,
        change_amount=change_amount,
        reverse=False,
    )
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
            "subtotal": str(subtotal_neto_lineas),
            "subtotal_bruto": str(sale.subtotal),
            "descuento_lineas_total": str(sale.descuento_lineas_total),
            "descuento_global": str(sale.descuento_global),
            "descuento_total": str(sale.descuento_total),
            "total": str(sale.total),
            "payments_count": len(resolved_payments),
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
    metodo_pago: str | None,
    descuento_global: Decimal | None,
    notas: str | None,
    items: list,
    payments: list | None,
    ip_address: str | None,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    warehouse, resolved_lines, subtotal_bruto, descuento_lineas_total, impuesto_total = resolve_sale_lines(
        db,
        empresa_id=empresa.id,
        warehouse_id=almacen_id,
        items=items,
        validate_stock=False,
    )
    _, normalized_global_discount, descuento_total, total = resolve_sale_totals(
        subtotal_bruto=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
        impuesto_total=impuesto_total,
        descuento_global=descuento_global,
    )
    suspended_payment_method = "efectivo"
    if payments:
        suspended_payment_method = "mixto" if len(payments) > 1 else str(payments[0].metodo or "efectivo").lower()
    elif metodo_pago:
        candidate_method = str(metodo_pago).strip().lower()
        if candidate_method in PAYMENT_METHODS or candidate_method in LEGACY_MIXED_PAYMENT_METHODS:
            suspended_payment_method = candidate_method

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
        subtotal=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
        descuento_global=normalized_global_discount,
        descuento_total=descuento_total,
        impuesto_total=impuesto_total,
        total=total,
        metodo_pago=suspended_payment_method,
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
    metodo_pago: str | None,
    monto_recibido: Decimal | None,
    descuento_global: Decimal | None,
    notas: str | None,
    items: list,
    payments: list | None,
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

    warehouse, resolved_lines, subtotal_bruto, descuento_lineas_total, impuesto_total = resolve_sale_lines(
        db,
        empresa_id=empresa.id,
        warehouse_id=almacen_id,
        items=items,
        validate_stock=True,
    )
    _, normalized_global_discount, descuento_total, total = resolve_sale_totals(
        subtotal_bruto=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
        impuesto_total=impuesto_total,
        descuento_global=descuento_global,
    )
    shift = get_active_shift_for_company(db, empresa.id, warehouse.id, for_update=True)
    if not shift:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Abre caja para cobrar esta venta.",
        )

    resolved_payments, resolved_payment_method, received_amount, change_amount = resolve_sale_payment(
        metodo_pago=metodo_pago,
        monto_recibido=monto_recibido,
        payments=payments,
        total=total,
        require_payment_validation=True,
    )

    sale.almacen_id = warehouse.id
    sale.turno_id = shift.id
    sale.usuario_id = user.id
    sale.cliente_nombre = normalize_optional_text(cliente_nombre)
    sale.cliente_email = normalize_customer_email(cliente_email)
    sale.subtotal = subtotal_bruto
    sale.descuento_lineas_total = descuento_lineas_total
    sale.descuento_global = normalized_global_discount
    sale.descuento_total = descuento_total
    sale.impuesto_total = impuesto_total
    sale.total = total
    sale.metodo_pago = resolved_payment_method
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

    replace_sale_payments(db, sale=sale, payments=resolved_payments, turno_id=shift.id)
    adjust_shift_totals_for_payments(
        shift,
        sale_total=sale.total,
        payments=resolved_payments,
        change_amount=change_amount,
        reverse=False,
    )
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
            "payments_count": len(resolved_payments),
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
        payment_breakdown = get_sale_payment_breakdown(db, sale=sale)
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
            adjust_shift_totals_for_payments(
                shift,
                sale_total=sale.total,
                payments=payment_breakdown,
                change_amount=sale.cambio,
                reverse=True,
            )
            refresh_closed_shift_difference(shift)

        for detail in detail_rows:
            if not detail.material_id or not bool(detail.es_inventariable):
                continue
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
