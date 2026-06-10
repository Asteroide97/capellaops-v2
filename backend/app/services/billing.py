from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import TenantContext
from app.models import Empresa, Usuario, Venta
from app.schemas.billing import (
    BillingInvoiceValidationResult,
    BillingPosInvoiceRequestDetail,
    BillingPosInvoiceRequestItem,
    BillingPosInvoiceRequestKpis,
)
from app.services.inventory import apply_text_search, count_rows, normalize_optional_text
from app.services.pos import (
    EMAIL_PATTERN,
    RFC_PATTERN,
    create_audit_log,
    get_sale_for_company,
    serialize_sale_response,
)


REVIEWABLE_STATUSES = {
    "pendiente_datos",
    "lista_para_facturar",
    "en_revision",
    "observada",
    "preparada",
    "descartada",
}


def validate_billing_queue_access(context: TenantContext) -> None:
    role = str(context.membership.role or "").lower()
    if context.user.is_superadmin or role in {"owner", "admin"}:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permisos para revisar solicitudes fiscales.",
    )


def resolve_review_status(sale: Venta) -> str:
    if sale.factura_revision_estado in REVIEWABLE_STATUSES:
        return str(sale.factura_revision_estado)
    if sale.factura_estado in REVIEWABLE_STATUSES:
        return str(sale.factura_estado)
    return "pendiente_datos"


def parse_stored_invoice_errors(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [line.strip() for line in str(raw_value).splitlines() if line.strip()]


def validate_basic_invoice_request(sale: Venta) -> BillingInvoiceValidationResult:
    errors: list[str] = []

    if sale.estatus == "cancelada":
        errors.append("No puedes preparar una venta cancelada.")
    elif sale.estatus != "pagada":
        errors.append("Solo puedes preparar solicitudes de ventas pagadas.")

    if not sale.factura_rfc:
        errors.append("Falta el RFC.")
    elif not RFC_PATTERN.fullmatch(str(sale.factura_rfc).strip().upper().replace(" ", "")):
        errors.append("Ingresa un RFC válido.")

    if not normalize_optional_text(sale.factura_razon_social):
        errors.append("Falta la razón social.")

    email = normalize_optional_text(sale.factura_email)
    if not email:
        errors.append("Falta el email fiscal.")
    elif not EMAIL_PATTERN.fullmatch(email.lower()):
        errors.append("Ingresa un email válido.")

    if not normalize_optional_text(sale.factura_uso_cfdi):
        errors.append("Falta el uso CFDI.")

    if not normalize_optional_text(sale.factura_regimen_fiscal):
        errors.append("Falta el régimen fiscal.")

    codigo_postal = normalize_optional_text(sale.factura_codigo_postal)
    if not codigo_postal:
        errors.append("Falta el código postal.")
    elif not codigo_postal.isdigit() or len(codigo_postal) != 5:
        errors.append("Ingresa un código postal válido.")

    return BillingInvoiceValidationResult(is_valid=len(errors) == 0, errors=errors)


def build_billing_queue_item(sale: Venta) -> BillingPosInvoiceRequestItem:
    validation = validate_basic_invoice_request(sale)
    stored_errors = parse_stored_invoice_errors(sale.factura_error_datos)
    return BillingPosInvoiceRequestItem(
        venta_id=sale.id,
        folio=sale.folio,
        fecha_venta=sale.factura_solicitada_at or sale.paid_at or sale.created_at,
        total=sale.total,
        estado_solicitud=sale.factura_estado or "no_solicitada",
        estado_revision=resolve_review_status(sale),
        cliente=sale.factura_cliente_nombre or sale.cliente_nombre,
        rfc=sale.factura_rfc,
        razon_social=sale.factura_razon_social,
        email=sale.factura_email,
        uso_cfdi=sale.factura_uso_cfdi,
        regimen_fiscal=sale.factura_regimen_fiscal,
        codigo_postal=sale.factura_codigo_postal,
        notas=sale.factura_notas,
        errores_datos=stored_errors or ([] if validation.is_valid else validation.errors),
        venta_cancelada=sale.estatus == "cancelada",
    )


def get_billing_queue_sale(
    db: Session,
    empresa_id: str,
    sale_id: str,
    *,
    for_update: bool = False,
) -> Venta:
    query = (
        select(Venta)
        .options(
            selectinload(Venta.almacen),
            selectinload(Venta.usuario),
            selectinload(Venta.turno),
            selectinload(Venta.factura_revisada_por_user),
        )
        .where(Venta.id == sale_id, Venta.empresa_id == empresa_id)
    )
    if for_update:
        query = query.with_for_update()
    sale = db.scalar(query)
    if not sale or sale.factura_estado == "no_solicitada":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud fiscal no encontrada.",
        )
    return sale


def build_billing_queue_detail(db: Session, sale: Venta) -> BillingPosInvoiceRequestDetail:
    sale_response = serialize_sale_response(db, sale)
    queue_item = build_billing_queue_item(sale)
    validation = validate_basic_invoice_request(sale)
    return BillingPosInvoiceRequestDetail(
        **queue_item.model_dump(),
        venta_estatus=sale.estatus,
        factura_solicitada_at=sale.factura_solicitada_at,
        factura_revisada_at=sale.factura_revisada_at,
        factura_preparada_at=sale.factura_preparada_at,
        factura_descartada_at=sale.factura_descartada_at,
        factura_revision_notas=sale.factura_revision_notas,
        revisada_por_user_id=sale.factura_revisada_por_user_id,
        revisada_por_nombre=sale.factura_revisada_por_user.full_name if sale.factura_revisada_por_user else None,
        productos=sale_response.details,
        pagos=sale_response.payments,
        validation=validation,
    )


def build_billing_kpis(states: Iterable[str]) -> BillingPosInvoiceRequestKpis:
    kpis = BillingPosInvoiceRequestKpis()
    for state in states:
        normalized = str(state or "").lower()
        if normalized == "pendiente_datos":
            kpis.pendientes_datos += 1
        elif normalized == "lista_para_facturar":
            kpis.listas_para_facturar += 1
        elif normalized == "en_revision":
            kpis.en_revision += 1
        elif normalized == "observada":
            kpis.observadas += 1
        elif normalized == "preparada":
            kpis.preparadas += 1
    return kpis


def list_billing_pos_invoice_requests(
    db: Session,
    empresa_id: str,
    *,
    estado: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    rfc: str | None = None,
    folio: str | None = None,
    cliente: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[BillingPosInvoiceRequestItem], BillingPosInvoiceRequestKpis]:
    review_status_expr = func.coalesce(Venta.factura_revision_estado, Venta.factura_estado)
    request_timestamp = func.coalesce(Venta.factura_solicitada_at, Venta.paid_at, Venta.created_at)

    id_query = select(Venta.id).where(
        Venta.empresa_id == empresa_id,
        Venta.factura_estado != "no_solicitada",
    )
    kpi_state_query = select(review_status_expr).where(
        Venta.empresa_id == empresa_id,
        Venta.factura_estado != "no_solicitada",
    )

    if estado:
        id_query = id_query.where(review_status_expr == estado)
        kpi_state_query = kpi_state_query.where(review_status_expr == estado)
    if fecha_desde:
        id_query = id_query.where(request_timestamp >= fecha_desde)
        kpi_state_query = kpi_state_query.where(request_timestamp >= fecha_desde)
    if fecha_hasta:
        id_query = id_query.where(request_timestamp <= fecha_hasta)
        kpi_state_query = kpi_state_query.where(request_timestamp <= fecha_hasta)
    if rfc:
        id_query = apply_text_search(id_query, rfc, Venta.factura_rfc)
        kpi_state_query = apply_text_search(kpi_state_query, rfc, Venta.factura_rfc)
    if folio:
        id_query = apply_text_search(id_query, folio, Venta.folio)
        kpi_state_query = apply_text_search(kpi_state_query, folio, Venta.folio)
    if cliente:
        id_query = apply_text_search(
            id_query,
            cliente,
            Venta.factura_cliente_nombre,
            Venta.factura_razon_social,
            Venta.cliente_nombre,
        )
        kpi_state_query = apply_text_search(
            kpi_state_query,
            cliente,
            Venta.factura_cliente_nombre,
            Venta.factura_razon_social,
            Venta.cliente_nombre,
        )

    total = count_rows(db, id_query)
    kpi_states = db.scalars(kpi_state_query).all()
    page_ids = db.scalars(
        id_query.order_by(desc(request_timestamp), desc(Venta.id)).offset(offset).limit(limit)
    ).all()
    if not page_ids:
        return total, [], build_billing_kpis(kpi_states)

    sales = db.scalars(
        select(Venta)
        .options(
            selectinload(Venta.almacen),
            selectinload(Venta.usuario),
            selectinload(Venta.turno),
            selectinload(Venta.factura_revisada_por_user),
        )
        .where(Venta.id.in_(page_ids))
        .order_by(desc(func.coalesce(Venta.factura_solicitada_at, Venta.paid_at, Venta.created_at)), desc(Venta.id))
    ).all()
    return total, [build_billing_queue_item(sale) for sale in sales], build_billing_kpis(kpi_states)


def get_billing_pos_invoice_request_detail(
    db: Session,
    empresa_id: str,
    sale_id: str,
) -> BillingPosInvoiceRequestDetail:
    sale = get_billing_queue_sale(db, empresa_id, sale_id)
    return build_billing_queue_detail(db, sale)


def mark_billing_invoice_request_review(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    nota: str | None,
    ip_address: str | None,
) -> BillingPosInvoiceRequestDetail:
    sale = get_billing_queue_sale(db, empresa.id, sale_id, for_update=True)
    sale.factura_revision_estado = "en_revision"
    sale.factura_revision_notas = normalize_optional_text(nota)
    sale.factura_revisada_por_user_id = user.id
    sale.factura_revisada_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="billing.pos.invoice_request.review",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "estado_revision": sale.factura_revision_estado,
        },
    )
    db.flush()
    db.refresh(sale)
    return build_billing_queue_detail(db, sale)


def observe_billing_invoice_request(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    nota: str | None,
    ip_address: str | None,
) -> BillingPosInvoiceRequestDetail:
    observation_note = normalize_optional_text(nota)
    if not observation_note:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agrega una nota para observar la solicitud.",
        )

    sale = get_billing_queue_sale(db, empresa.id, sale_id, for_update=True)
    validation = validate_basic_invoice_request(sale)
    sale.factura_revision_estado = "observada"
    sale.factura_revision_notas = observation_note
    sale.factura_error_datos = "\n".join(validation.errors) if validation.errors else observation_note
    sale.factura_revisada_por_user_id = user.id
    sale.factura_revisada_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="billing.pos.invoice_request.observe",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "estado_revision": sale.factura_revision_estado,
            "errores": validation.errors,
        },
    )
    db.flush()
    db.refresh(sale)
    return build_billing_queue_detail(db, sale)


def prepare_billing_invoice_request(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    ip_address: str | None,
) -> BillingPosInvoiceRequestDetail:
    sale = get_billing_queue_sale(db, empresa.id, sale_id, for_update=True)

    if sale.estatus == "cancelada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes preparar una venta cancelada.",
        )
    if sale.estatus != "pagada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo puedes preparar solicitudes de ventas pagadas.",
        )

    validation = validate_basic_invoice_request(sale)
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Faltan datos fiscales.",
        )

    sale.factura_revision_estado = "preparada"
    sale.factura_error_datos = None
    sale.factura_revisada_por_user_id = user.id
    sale.factura_revisada_at = datetime.now(timezone.utc)
    sale.factura_preparada_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="billing.pos.invoice_request.prepare",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "estado_revision": sale.factura_revision_estado,
        },
    )
    db.flush()
    db.refresh(sale)
    return build_billing_queue_detail(db, sale)


def discard_billing_invoice_request(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    sale_id: str,
    nota: str | None,
    ip_address: str | None,
) -> BillingPosInvoiceRequestDetail:
    discard_note = normalize_optional_text(nota)
    if not discard_note:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agrega un motivo para descartar la solicitud.",
        )

    sale = get_billing_queue_sale(db, empresa.id, sale_id, for_update=True)
    sale.factura_revision_estado = "descartada"
    sale.factura_revision_notas = discard_note
    sale.factura_descartada_at = datetime.now(timezone.utc)
    sale.factura_revisada_por_user_id = user.id
    sale.factura_revisada_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="billing.pos.invoice_request.discard",
        entity_name="venta",
        entity_id=sale.id,
        ip_address=ip_address,
        metadata_json={
            "folio": sale.folio,
            "estado_revision": sale.factura_revision_estado,
        },
    )
    db.flush()
    db.refresh(sale)
    return build_billing_queue_detail(db, sale)
