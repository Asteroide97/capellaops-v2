from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AuditLog,
    Empresa,
    PosTicketDelivery,
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
    PosTicketDeliveryItem,
    PosTicketDeliveryResponse,
    PosShiftMovementResponse,
    PosShiftResponse,
    PosTicketResponse,
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
from app.services.phone import validate_phone_e164


PAYMENT_METHODS = {"efectivo", "tarjeta", "transferencia", "otro"}
LEGACY_MIXED_PAYMENT_METHODS = {"mixto"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"
TWILIO_MESSAGES_API_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"


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


def calculate_sale_paid_amount(sale: Venta) -> Decimal | None:
    if sale.monto_recibido is not None:
        return Decimal(sale.monto_recibido or ZERO)
    if sale.estatus == "suspendida":
        return None
    return Decimal(sale.total or ZERO)


def normalize_payment_reference(value: str | None) -> str | None:
    return normalize_optional_text(value)


def normalize_ticket_email(value: str) -> str:
    normalized = normalize_optional_text(value)
    if not normalized or not EMAIL_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingresa un email válido.",
        )
    return normalized.lower()


def normalize_ticket_phone(value: str) -> str:
    normalized = normalize_optional_text(value)
    if not normalized or not validate_phone_e164(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingresa un teléfono válido.",
        )
    return normalized


def format_ticket_currency(value: Decimal | int | float | None) -> str:
    amount = Decimal(value or ZERO).quantize(Decimal("0.01"))
    return f"${amount:,.2f}"


def format_ticket_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def validate_sale_ticket_available(sale: Venta) -> None:
    if sale.estatus == "suspendida":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo las ventas pagadas o canceladas generan ticket.",
        )


def serialize_ticket_delivery(delivery: PosTicketDelivery) -> PosTicketDeliveryItem:
    return PosTicketDeliveryItem(
        id=delivery.id,
        canal=delivery.canal,
        destino=delivery.destino,
        estatus=delivery.estatus,
        proveedor=delivery.proveedor,
        error_message=delivery.error_message,
        sent_by_user_id=delivery.sent_by_user_id,
        sent_by_user_nombre=delivery.sent_by_user.full_name if delivery.sent_by_user else None,
        created_at=delivery.created_at,
    )


def load_ticket_deliveries(db: Session, sale_id: str) -> list[PosTicketDelivery]:
    return db.scalars(
        select(PosTicketDelivery)
        .where(PosTicketDelivery.venta_id == sale_id)
        .order_by(PosTicketDelivery.created_at.desc(), PosTicketDelivery.id.desc())
    ).all()


def get_serialized_ticket_deliveries(db: Session, sale: Venta) -> list[PosTicketDeliveryItem]:
    return [serialize_ticket_delivery(delivery) for delivery in load_ticket_deliveries(db, sale.id)]


def record_ticket_delivery(
    db: Session,
    *,
    sale: Venta,
    user: Usuario,
    channel: str,
    destination: str,
    status_value: str,
    provider: str | None,
    error_message: str | None = None,
) -> PosTicketDelivery:
    delivery = PosTicketDelivery(
        empresa_id=sale.empresa_id,
        venta_id=sale.id,
        canal=channel,
        destino=destination,
        estatus=status_value,
        proveedor=provider,
        error_message=error_message,
        sent_by_user_id=user.id,
    )
    delivery.sent_by_user = user
    db.add(delivery)
    db.flush()
    return delivery


def build_ticket_email_html(ticket: PosTicketResponse, recipient_name: str | None = None) -> str:
    greeting = f"<p>Hola {escape(recipient_name)},</p>" if recipient_name else ""
    product_rows = "".join(
        (
            "<tr>"
            f"<td style='padding:6px 0'>{escape(item.nombre)}</td>"
            f"<td style='padding:6px 0; text-align:center'>{escape(str(item.cantidad))}</td>"
            f"<td style='padding:6px 0; text-align:right'>{escape(format_ticket_currency(item.precio_unitario))}</td>"
            f"<td style='padding:6px 0; text-align:right'>{escape(format_ticket_currency(item.descuento_unitario))}</td>"
            f"<td style='padding:6px 0; text-align:right'>{escape(format_ticket_currency(item.total_linea))}</td>"
            "</tr>"
        )
        for item in ticket.productos
    )
    payment_rows = "".join(
        (
            "<tr>"
            f"<td style='padding:6px 0'>{escape(payment.metodo.capitalize())}</td>"
            f"<td style='padding:6px 0'>{escape(payment.referencia or 'Sin referencia')}</td>"
            f"<td style='padding:6px 0; text-align:right'>{escape(format_ticket_currency(payment.monto))}</td>"
            "</tr>"
        )
        for payment in ticket.pagos
    )
    cancelled_block = (
        "<p style='margin:0 0 16px; padding:10px 12px; border-radius:10px; background:#fff5f5; color:#b42318; font-weight:700'>"
        "VENTA CANCELADA"
        "</p>"
        if ticket.estatus == "cancelada"
        else ""
    )
    note_block = f"<p style='margin:16px 0 0'>{escape(ticket.notas)}</p>" if ticket.notas else ""
    return (
        "<div style='font-family:Arial,sans-serif; color:#101828; max-width:720px; margin:0 auto; padding:24px'>"
        "<p style='margin:0 0 8px; font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:#475467'>Comprobante de venta</p>"
        f"<h1 style='margin:0 0 16px; font-size:24px'>{escape(ticket.empresa)}</h1>"
        f"{greeting}"
        f"{cancelled_block}"
        f"<p style='margin:0 0 16px'>Adjuntamos el resumen de tu compra <strong>{escape(ticket.folio)}</strong>.</p>"
        "<table style='width:100%; border-collapse:collapse; margin-bottom:20px'>"
        f"<tr><td><strong>Almacen</strong></td><td>{escape(ticket.almacen)}</td></tr>"
        f"<tr><td><strong>Fecha</strong></td><td>{escape(format_ticket_datetime(ticket.fecha))}</td></tr>"
        f"<tr><td><strong>Cajero</strong></td><td>{escape(ticket.vendedor)}</td></tr>"
        f"<tr><td><strong>Cliente</strong></td><td>{escape(ticket.cliente_nombre or 'Mostrador')}</td></tr>"
        "</table>"
        "<table style='width:100%; border-collapse:collapse; margin-bottom:20px'>"
        "<thead><tr>"
        "<th style='text-align:left; padding:8px 0; border-bottom:1px solid #d0d5dd'>Producto</th>"
        "<th style='text-align:center; padding:8px 0; border-bottom:1px solid #d0d5dd'>Cant.</th>"
        "<th style='text-align:right; padding:8px 0; border-bottom:1px solid #d0d5dd'>Precio</th>"
        "<th style='text-align:right; padding:8px 0; border-bottom:1px solid #d0d5dd'>Desc.</th>"
        "<th style='text-align:right; padding:8px 0; border-bottom:1px solid #d0d5dd'>Total</th>"
        "</tr></thead>"
        f"<tbody>{product_rows}</tbody>"
        "</table>"
        "<table style='width:100%; border-collapse:collapse; margin-bottom:20px'>"
        f"<tr><td>Subtotal bruto</td><td style='text-align:right'>{escape(format_ticket_currency(ticket.subtotal))}</td></tr>"
        f"<tr><td>Descuentos de linea</td><td style='text-align:right'>-{escape(format_ticket_currency(ticket.descuento_lineas_total))}</td></tr>"
        f"<tr><td>Descuento global</td><td style='text-align:right'>-{escape(format_ticket_currency(ticket.descuento_global))}</td></tr>"
        f"<tr><td><strong>Total</strong></td><td style='text-align:right'><strong>{escape(format_ticket_currency(ticket.total))}</strong></td></tr>"
        f"<tr><td>Pagado</td><td style='text-align:right'>{escape(format_ticket_currency(ticket.monto_pagado))}</td></tr>"
        f"<tr><td>Cambio</td><td style='text-align:right'>{escape(format_ticket_currency(ticket.cambio))}</td></tr>"
        "</table>"
        "<h2 style='margin:0 0 10px; font-size:16px'>Pagos</h2>"
        "<table style='width:100%; border-collapse:collapse; margin-bottom:20px'>"
        "<thead><tr>"
        "<th style='text-align:left; padding:8px 0; border-bottom:1px solid #d0d5dd'>Metodo</th>"
        "<th style='text-align:left; padding:8px 0; border-bottom:1px solid #d0d5dd'>Referencia</th>"
        "<th style='text-align:right; padding:8px 0; border-bottom:1px solid #d0d5dd'>Monto</th>"
        "</tr></thead>"
        f"<tbody>{payment_rows}</tbody>"
        "</table>"
        f"{note_block}"
        "<p style='margin:20px 0 0; font-weight:700'>Gracias por su compra</p>"
        "<p style='margin:8px 0 0; color:#475467'>No es comprobante fiscal.</p>"
        "</div>"
    )


def build_ticket_sms_message(ticket: PosTicketResponse) -> str:
    return (
        f"Ticket {ticket.folio}. Total {format_ticket_currency(ticket.total)}. "
        "Gracias por su compra. No es comprobante fiscal."
    )


def post_json_request(url: str, *, payload: dict, headers: dict[str, str]) -> tuple[int, dict | None]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8").strip()
            return response.status, json.loads(body) if body else None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore").strip()
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed
    except URLError:
        return 0, None


def post_form_request(url: str, *, payload: dict[str, str], headers: dict[str, str]) -> tuple[int, dict | None]:
    request = Request(
        url,
        data=urlencode(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8").strip()
            return response.status, json.loads(body) if body else None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore").strip()
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed
    except URLError:
        return 0, None


def dispatch_ticket_email(ticket: PosTicketResponse, *, email: str, recipient_name: str | None = None) -> tuple[bool, str, str]:
    settings = get_settings()
    if not settings.sendgrid_api_key or not settings.email_from:
        return False, "El envío de email no está configurado.", "sendgrid"

    status_code, payload = post_json_request(
        SENDGRID_API_URL,
        payload={
            "personalizations": [
                {
                    "to": [{"email": email, "name": recipient_name} if recipient_name else {"email": email}],
                }
            ],
            "from": {"email": settings.email_from},
            "subject": f"Comprobante de venta {ticket.folio}",
            "content": [
                {
                    "type": "text/html",
                    "value": build_ticket_email_html(ticket, recipient_name=recipient_name),
                }
            ],
        },
        headers={
            "Authorization": f"Bearer {settings.sendgrid_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    if status_code == 202:
        return True, "Ticket enviado por email.", "sendgrid"
    if status_code == 0:
        return False, "No se pudo enviar el ticket por email.", "sendgrid"
    return False, "No se pudo enviar el ticket por email.", "sendgrid"


def dispatch_ticket_sms(ticket: PosTicketResponse, *, phone: str) -> tuple[bool, str, str]:
    settings = get_settings()
    if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.twilio_sms_from:
        return False, "El envío de SMS no está configurado.", "twilio"

    credentials = f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode("utf-8")
    auth_token = base64.b64encode(credentials).decode("utf-8")
    status_code, payload = post_form_request(
        TWILIO_MESSAGES_API_TEMPLATE.format(account_sid=settings.twilio_account_sid),
        payload={
            "From": settings.twilio_sms_from,
            "To": phone,
            "Body": build_ticket_sms_message(ticket),
        },
        headers={
            "Authorization": f"Basic {auth_token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    if status_code in {200, 201} and payload and payload.get("sid"):
        return True, "Ticket enviado por SMS.", "twilio"
    if status_code == 0:
        return False, "No se pudo enviar el ticket por SMS.", "twilio"
    return False, "No se pudo enviar el ticket por SMS.", "twilio"

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
        payments=payments,
        details=[
            serialize_sale_detail(detail, stock_actual=stock_map.get(detail.material_id, ZERO))
            for detail in details
        ],
    )


def get_sale_ticket(db: Session, sale: Venta) -> PosTicketResponse:
    validate_sale_ticket_available(sale)
    details = db.scalars(
        select(VentaDetalle)
        .where(VentaDetalle.venta_id == sale.id)
        .order_by(VentaDetalle.nombre_snapshot.asc(), VentaDetalle.sku_snapshot.asc(), VentaDetalle.id.asc())
    ).all()
    serialized_payments = get_serialized_sale_payments(db, sale)
    serialized_deliveries = get_serialized_ticket_deliveries(db, sale)
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
        deliveries=serialized_deliveries,
    )


def send_sale_ticket_email(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    email: str,
    recipient_name: str | None = None,
) -> PosTicketDeliveryResponse:
    sale = get_sale_for_company(db, empresa.id, sale_id)
    validate_sale_ticket_available(sale)
    normalized_email = normalize_ticket_email(email)
    ticket = get_sale_ticket(db, sale)
    sent, message, provider = dispatch_ticket_email(ticket, email=normalized_email, recipient_name=recipient_name)
    delivery = record_ticket_delivery(
        db,
        sale=sale,
        user=user,
        channel="email",
        destination=normalized_email,
        status_value="enviado" if sent else "fallido",
        provider=provider,
        error_message=None if sent else message,
    )
    return PosTicketDeliveryResponse(
        sent=sent,
        message=message,
        delivery=serialize_ticket_delivery(delivery),
    )


def send_sale_ticket_sms(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    phone: str,
) -> PosTicketDeliveryResponse:
    sale = get_sale_for_company(db, empresa.id, sale_id)
    validate_sale_ticket_available(sale)
    normalized_phone = normalize_ticket_phone(phone)
    ticket = get_sale_ticket(db, sale)
    sent, message, provider = dispatch_ticket_sms(ticket, phone=normalized_phone)
    delivery = record_ticket_delivery(
        db,
        sale=sale,
        user=user,
        channel="sms",
        destination=normalized_phone,
        status_value="enviado" if sent else "fallido",
        provider=provider,
        error_message=None if sent else message,
    )
    return PosTicketDeliveryResponse(
        sent=sent,
        message=message,
        delivery=serialize_ticket_delivery(delivery),
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
) -> tuple[Almacen, list[dict], Decimal, Decimal]:
    warehouse = get_active_sale_warehouse(db, empresa_id, warehouse_id)
    resolved_lines: list[dict] = []
    required_stock: dict[str, Decimal] = {}
    subtotal_bruto = ZERO
    descuento_lineas_total = ZERO

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

        subtotal_bruto += line_subtotal
        descuento_lineas_total += line_discount_total
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

    subtotal_despues_descuentos = subtotal_bruto - descuento_lineas_total
    if subtotal_despues_descuentos < ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El total de la venta no puede ser negativo.",
        )

    return warehouse, resolved_lines, subtotal_bruto, descuento_lineas_total


def resolve_sale_totals(
    *,
    subtotal_bruto: Decimal,
    descuento_lineas_total: Decimal,
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
    total = subtotal_despues_descuentos_linea - normalized_global_discount
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
    payments = load_sale_payments(db, sale.id)
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
    metodo_pago: str | None,
    monto_recibido: Decimal | None,
    descuento_global: Decimal | None,
    notas: str | None,
    items: list,
    payments: list | None,
    ip_address: str | None,
) -> SaleResponse:
    validate_pos_access(user, empresa)
    warehouse, resolved_lines, subtotal_bruto, descuento_lineas_total = resolve_sale_lines(
        db,
        empresa_id=empresa.id,
        warehouse_id=almacen_id,
        items=items,
        validate_stock=True,
    )
    subtotal_neto_lineas, normalized_global_discount, descuento_total, total = resolve_sale_totals(
        subtotal_bruto=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
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
        impuesto_total=ZERO,
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
    warehouse, resolved_lines, subtotal_bruto, descuento_lineas_total = resolve_sale_lines(
        db,
        empresa_id=empresa.id,
        warehouse_id=almacen_id,
        items=items,
        validate_stock=False,
    )
    _, normalized_global_discount, descuento_total, total = resolve_sale_totals(
        subtotal_bruto=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
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
        impuesto_total=ZERO,
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

    warehouse, resolved_lines, subtotal_bruto, descuento_lineas_total = resolve_sale_lines(
        db,
        empresa_id=empresa.id,
        warehouse_id=almacen_id,
        items=items,
        validate_stock=True,
    )
    _, normalized_global_discount, descuento_total, total = resolve_sale_totals(
        subtotal_bruto=subtotal_bruto,
        descuento_lineas_total=descuento_lineas_total,
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
    sale.impuesto_total = ZERO
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
