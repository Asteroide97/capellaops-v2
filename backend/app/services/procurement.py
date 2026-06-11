from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Almacen,
    AuditLog,
    Empresa,
    OrdenCompra,
    OrdenCompraDetalle,
    OrdenCompraRecepcion,
    OrdenCompraRecepcionDetalle,
    PMProyecto,
    PMProyectoMaterialConsumo,
    Proveedor,
    Requisicion,
    RequisicionDetalle,
    Usuario,
)
from app.models.pm import PMPresupuestoPartida, PMTarea
from app.models.inventory import Existencia, Material, MovimientoInventario
from app.schemas.procurement import (
    PurchaseOrderDetailItem,
    PurchaseOrderItem,
    PurchaseOrderMovementTraceItem,
    PurchaseOrderPendingQuantityItem,
    PurchaseOrderPendingReportKpis,
    PurchaseOrderPendingReportMaterialItem,
    PurchaseOrderPendingReportOrderItem,
    PurchaseOrderPendingReportResponse,
    PurchaseOrderPendingReportSupplierItem,
    PurchaseOrderReceiptDetailItem,
    PurchaseOrderReceiptItem,
    PurchaseOrderReceiveResponse,
    PurchaseOrderResponse,
    RequisitionDetailItem,
    RequisitionDetailStockItem,
    RequisitionItem,
    RequisitionMovementTraceItem,
    RequisitionResponse,
    SupplierMaterialItem,
    SupplierItem,
    SupplierSummaryResponse,
)
from app.services.inventory import (
    ZERO,
    apply_inventory_movement,
    apply_text_search,
    count_rows,
    decimal_or_zero,
    get_material_for_company,
    get_warehouse_for_company,
    normalize_code,
    normalize_optional_text,
    normalize_required_text,
    resolve_inventory_unit_cost,
)


def generate_procurement_folio(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = str(uuid4())[:6].upper()
    return f"{prefix}-{timestamp}-{suffix}"


ALLOWED_REQUISITION_PRIORITY = {"baja", "normal", "alta", "urgente"}
BASIC_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BASIC_RFC_RE = re.compile(r"^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$")
BASIC_POSTAL_CODE_RE = re.compile(r"^\d{5}$")


def normalize_optional_folio(value: str | None, prefix: str) -> str:
    if value is None:
        return generate_procurement_folio(prefix)
    cleaned = value.strip()
    if not cleaned:
        return generate_procurement_folio(prefix)
    return normalize_code(cleaned, "Folio")


def normalize_requisition_priority(value: str | None) -> str:
    normalized = normalize_optional_text(value) or "normal"
    normalized = normalized.lower()
    if normalized not in ALLOWED_REQUISITION_PRIORITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prioridad inválida. Usa baja, normal, alta o urgente.",
        )
    return normalized


def normalize_supplier_name(nombre: str | None, nombre_comercial: str | None, *, required: bool) -> str | None:
    raw_value = normalize_optional_text(nombre_comercial) or normalize_optional_text(nombre)
    if required:
        return normalize_required_text(raw_value, "Nombre")
    if raw_value is None:
        return None
    return normalize_required_text(raw_value, "Nombre")


def normalize_supplier_contact_name(contacto_nombre: str | None, contacto_principal: str | None) -> str | None:
    return normalize_optional_text(contacto_principal) or normalize_optional_text(contacto_nombre)


def normalize_supplier_email(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if not BASIC_EMAIL_RE.match(lowered):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ingresa un email valido.")
    return lowered


def normalize_supplier_rfc(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    upper = normalized.upper()
    if not BASIC_RFC_RE.match(upper):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ingresa un RFC valido.")
    return upper


def normalize_supplier_postal_code(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    if not BASIC_POSTAL_CODE_RE.match(normalized):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ingresa un codigo postal valido.")
    return normalized


def normalize_nonnegative_int(value: int | None, detail: str, *, default: int = 0) -> int:
    if value is None:
        return default
    if value < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    return int(value)


def resolve_supplier_snapshot_email(supplier: Proveedor) -> str | None:
    return normalize_optional_text(supplier.email_contacto) or normalize_optional_text(supplier.correo)


def resolve_supplier_snapshot_phone(supplier: Proveedor) -> str | None:
    return normalize_optional_text(supplier.telefono_contacto) or normalize_optional_text(supplier.telefono)


def apply_supplier_snapshot(order: OrdenCompra, supplier: Proveedor) -> None:
    order.proveedor_contacto_snapshot = normalize_optional_text(supplier.contacto_nombre)
    order.proveedor_email_snapshot = resolve_supplier_snapshot_email(supplier)
    order.proveedor_telefono_snapshot = resolve_supplier_snapshot_phone(supplier)
    order.condiciones_pago_snapshot = normalize_optional_text(supplier.condiciones_pago)
    order.moneda_snapshot = normalize_optional_text(supplier.moneda_preferida)


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


def serialize_supplier(supplier: Proveedor) -> SupplierItem:
    return SupplierItem(
        id=supplier.id,
        empresa_id=supplier.empresa_id,
        nombre=supplier.nombre,
        nombre_comercial=supplier.nombre,
        razon_social=supplier.razon_social,
        rfc=supplier.rfc,
        contacto_nombre=supplier.contacto_nombre,
        contacto_principal=supplier.contacto_nombre,
        correo=supplier.correo,
        email=supplier.correo,
        telefono=supplier.telefono,
        sitio_web=supplier.sitio_web,
        direccion=supplier.direccion,
        ciudad=supplier.ciudad,
        estado=supplier.estado,
        pais=supplier.pais,
        codigo_postal=supplier.codigo_postal,
        telefono_contacto=supplier.telefono_contacto,
        email_contacto=supplier.email_contacto,
        moneda_preferida=supplier.moneda_preferida,
        condiciones_pago=supplier.condiciones_pago,
        dias_credito=int(supplier.dias_credito or 0),
        lead_time_dias=int(supplier.lead_time_dias or 0),
        metodo_pago_preferido=supplier.metodo_pago_preferido,
        banco=supplier.banco,
        cuenta_bancaria=supplier.cuenta_bancaria,
        clabe=supplier.clabe,
        notas=supplier.notas,
        activo=supplier.activo,
        created_at=supplier.created_at,
        updated_at=supplier.updated_at,
    )


def get_supplier_for_company(db: Session, empresa_id: str, supplier_id: str) -> Proveedor:
    supplier = db.scalar(
        select(Proveedor).where(
            Proveedor.id == supplier_id,
            Proveedor.empresa_id == empresa_id,
        )
    )
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")
    return supplier


def list_suppliers(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    activo: bool | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[SupplierItem]]:
    query = select(Proveedor).where(Proveedor.empresa_id == empresa_id)
    query = apply_text_search(
        query,
        q,
        Proveedor.nombre,
        Proveedor.razon_social,
        Proveedor.rfc,
        Proveedor.contacto_nombre,
        Proveedor.correo,
        Proveedor.telefono,
        Proveedor.sitio_web,
        Proveedor.ciudad,
        Proveedor.estado,
        Proveedor.pais,
        Proveedor.codigo_postal,
        Proveedor.email_contacto,
        Proveedor.telefono_contacto,
        Proveedor.moneda_preferida,
        Proveedor.metodo_pago_preferido,
    )
    if activo is None:
        query = query.where(Proveedor.activo == True)
    else:
        query = query.where(Proveedor.activo == activo)

    total = count_rows(db, query)
    rows = db.scalars(query.order_by(Proveedor.nombre.asc(), Proveedor.id.asc()).offset(offset).limit(limit)).all()
    return total, [serialize_supplier(item) for item in rows]


def create_supplier(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    nombre: str,
    nombre_comercial: str | None,
    razon_social: str | None,
    rfc: str | None,
    contacto_nombre: str | None,
    contacto_principal: str | None,
    correo: str | None,
    email: str | None,
    telefono: str | None,
    sitio_web: str | None,
    direccion: str | None,
    ciudad: str | None,
    estado: str | None,
    pais: str | None,
    codigo_postal: str | None,
    telefono_contacto: str | None,
    email_contacto: str | None,
    moneda_preferida: str | None,
    condiciones_pago: str | None,
    dias_credito: int,
    lead_time_dias: int,
    metodo_pago_preferido: str | None,
    banco: str | None,
    cuenta_bancaria: str | None,
    clabe: str | None,
    notas: str | None,
    activo: bool,
    ip_address: str | None,
) -> SupplierItem:
    supplier = Proveedor(
        empresa_id=empresa.id,
        nombre=normalize_supplier_name(nombre, nombre_comercial, required=True),
        razon_social=normalize_optional_text(razon_social),
        rfc=normalize_supplier_rfc(rfc),
        contacto_nombre=normalize_supplier_contact_name(contacto_nombre, contacto_principal),
        correo=normalize_supplier_email(email or correo),
        telefono=normalize_optional_text(telefono),
        sitio_web=normalize_optional_text(sitio_web),
        direccion=normalize_optional_text(direccion),
        ciudad=normalize_optional_text(ciudad),
        estado=normalize_optional_text(estado),
        pais=normalize_optional_text(pais),
        codigo_postal=normalize_supplier_postal_code(codigo_postal),
        telefono_contacto=normalize_optional_text(telefono_contacto),
        email_contacto=normalize_supplier_email(email_contacto),
        moneda_preferida=normalize_optional_text(moneda_preferida.upper() if moneda_preferida else None),
        condiciones_pago=normalize_optional_text(condiciones_pago),
        dias_credito=normalize_nonnegative_int(dias_credito, "Los dias de credito no pueden ser negativos."),
        lead_time_dias=normalize_nonnegative_int(lead_time_dias, "El lead time no puede ser negativo."),
        metodo_pago_preferido=normalize_optional_text(metodo_pago_preferido),
        banco=normalize_optional_text(banco),
        cuenta_bancaria=normalize_optional_text(cuenta_bancaria),
        clabe=normalize_optional_text(clabe),
        notas=normalize_optional_text(notas),
        activo=activo,
    )
    db.add(supplier)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.supplier.create",
        entity_name="proveedor",
        entity_id=supplier.id,
        ip_address=ip_address,
        metadata_json={
            "nombre": supplier.nombre,
            "rfc": supplier.rfc,
            "activo": supplier.activo,
            "moneda_preferida": supplier.moneda_preferida,
        },
    )
    return serialize_supplier(supplier)


def update_supplier(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    supplier_id: str,
    nombre: str | None,
    nombre_comercial: str | None,
    razon_social: str | None,
    rfc: str | None,
    contacto_nombre: str | None,
    contacto_principal: str | None,
    correo: str | None,
    email: str | None,
    telefono: str | None,
    sitio_web: str | None,
    direccion: str | None,
    ciudad: str | None,
    estado: str | None,
    pais: str | None,
    codigo_postal: str | None,
    telefono_contacto: str | None,
    email_contacto: str | None,
    moneda_preferida: str | None,
    condiciones_pago: str | None,
    dias_credito: int | None,
    lead_time_dias: int | None,
    metodo_pago_preferido: str | None,
    banco: str | None,
    cuenta_bancaria: str | None,
    clabe: str | None,
    notas: str | None,
    activo: bool | None,
    ip_address: str | None,
) -> SupplierItem:
    supplier = get_supplier_for_company(db, empresa.id, supplier_id)
    if nombre is not None or nombre_comercial is not None:
        supplier.nombre = normalize_supplier_name(
            nombre if nombre is not None else supplier.nombre,
            nombre_comercial,
            required=True,
        )
    if razon_social is not None:
        supplier.razon_social = normalize_optional_text(razon_social)
    if rfc is not None:
        supplier.rfc = normalize_supplier_rfc(rfc)
    if contacto_nombre is not None or contacto_principal is not None:
        supplier.contacto_nombre = normalize_supplier_contact_name(contacto_nombre, contacto_principal)
    if correo is not None or email is not None:
        supplier.correo = normalize_supplier_email(email if email is not None else correo)
    if telefono is not None:
        supplier.telefono = normalize_optional_text(telefono)
    if sitio_web is not None:
        supplier.sitio_web = normalize_optional_text(sitio_web)
    if direccion is not None:
        supplier.direccion = normalize_optional_text(direccion)
    if ciudad is not None:
        supplier.ciudad = normalize_optional_text(ciudad)
    if estado is not None:
        supplier.estado = normalize_optional_text(estado)
    if pais is not None:
        supplier.pais = normalize_optional_text(pais)
    if codigo_postal is not None:
        supplier.codigo_postal = normalize_supplier_postal_code(codigo_postal)
    if telefono_contacto is not None:
        supplier.telefono_contacto = normalize_optional_text(telefono_contacto)
    if email_contacto is not None:
        supplier.email_contacto = normalize_supplier_email(email_contacto)
    if moneda_preferida is not None:
        supplier.moneda_preferida = normalize_optional_text(moneda_preferida.upper())
    if condiciones_pago is not None:
        supplier.condiciones_pago = normalize_optional_text(condiciones_pago)
    if dias_credito is not None:
        supplier.dias_credito = normalize_nonnegative_int(
            dias_credito,
            "Los dias de credito no pueden ser negativos.",
            default=int(supplier.dias_credito or 0),
        )
    if lead_time_dias is not None:
        supplier.lead_time_dias = normalize_nonnegative_int(
            lead_time_dias,
            "El lead time no puede ser negativo.",
            default=int(supplier.lead_time_dias or 0),
        )
    if metodo_pago_preferido is not None:
        supplier.metodo_pago_preferido = normalize_optional_text(metodo_pago_preferido)
    if banco is not None:
        supplier.banco = normalize_optional_text(banco)
    if cuenta_bancaria is not None:
        supplier.cuenta_bancaria = normalize_optional_text(cuenta_bancaria)
    if clabe is not None:
        supplier.clabe = normalize_optional_text(clabe)
    if notas is not None:
        supplier.notas = normalize_optional_text(notas)
    if activo is not None:
        supplier.activo = activo

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.supplier.update",
        entity_name="proveedor",
        entity_id=supplier.id,
        ip_address=ip_address,
        metadata_json={
            "nombre": supplier.nombre,
            "rfc": supplier.rfc,
            "activo": supplier.activo,
            "moneda_preferida": supplier.moneda_preferida,
        },
    )
    db.flush()
    db.refresh(supplier)
    return serialize_supplier(supplier)


def ensure_requisition_is_draft(requisition: Requisicion) -> None:
    if requisition.estatus != "borrador":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden modificar requisiciones en borrador.",
        )


def get_requisition_for_company(
    db: Session,
    empresa_id: str,
    requisition_id: str,
    *,
    for_update: bool = False,
) -> Requisicion:
    query = select(Requisicion).where(
        Requisicion.id == requisition_id,
        Requisicion.empresa_id == empresa_id,
    )
    if for_update:
        query = query.with_for_update()
    requisition = db.scalar(query)
    if not requisition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requisicion no encontrada.")
    return requisition


def get_requisition_detail(db: Session, requisition_id: str, detail_id: str) -> RequisicionDetalle:
    detail = db.scalar(
        select(RequisicionDetalle).where(
            RequisicionDetalle.id == detail_id,
            RequisicionDetalle.requisicion_id == requisition_id,
        )
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detalle de requisicion no encontrado.",
        )
    return detail


def get_requisition_detail_approved_quantity(detail: RequisicionDetalle) -> Decimal:
    approved = decimal_or_zero(detail.cantidad_aprobada)
    if approved > ZERO:
        return approved
    return decimal_or_zero(detail.cantidad)


def get_requisition_detail_pending_quantity(detail: RequisicionDetalle) -> Decimal:
    requested = get_requisition_detail_approved_quantity(detail)
    fulfilled = decimal_or_zero(detail.cantidad_surtida)
    pending = requested - fulfilled
    return pending if pending > ZERO else ZERO


def get_requisition_line_state(detail: RequisicionDetalle) -> str:
    fulfilled = decimal_or_zero(detail.cantidad_surtida)
    pending = get_requisition_detail_pending_quantity(detail)
    if pending <= ZERO:
        return "surtido"
    if fulfilled > ZERO:
        return "parcial"
    return "pendiente"


def get_requisition_stock_rows(
    db: Session,
    empresa_id: str,
    material_id: str,
) -> list[tuple[str, str, Decimal]]:
    return [
        (almacen_id, almacen_nombre, decimal_or_zero(stock_actual))
        for almacen_id, almacen_nombre, stock_actual in db.execute(
            select(
                Existencia.almacen_id.label("almacen_id"),
                Almacen.nombre.label("almacen_nombre"),
                func.coalesce(Existencia.cantidad, 0).label("stock_actual"),
            )
            .join(Almacen, Almacen.id == Existencia.almacen_id)
            .where(
                Existencia.empresa_id == empresa_id,
                Existencia.material_id == material_id,
            )
            .order_by(Almacen.nombre.asc(), Almacen.codigo.asc())
        ).all()
    ]


def serialize_requisition_detail(db: Session, empresa_id: str, detail: RequisicionDetalle) -> RequisitionDetailItem:
    stock_rows = get_requisition_stock_rows(db, empresa_id, detail.material_id)
    stock_total = sum((stock_actual for _, _, stock_actual in stock_rows), ZERO)
    return RequisitionDetailItem(
        id=detail.id,
        requisicion_id=detail.requisicion_id,
        material_id=detail.material_id,
        material_sku=detail.material.sku,
        material_nombre=detail.material.nombre,
        material_unidad=detail.material.unidad,
        cantidad=detail.cantidad,
        cantidad_aprobada=get_requisition_detail_approved_quantity(detail),
        cantidad_surtida=decimal_or_zero(detail.cantidad_surtida),
        cantidad_pendiente=get_requisition_detail_pending_quantity(detail),
        estado_linea=get_requisition_line_state(detail),
        stock_total=stock_total,
        proveedor_sugerido_id=detail.material.proveedor_principal_id,
        proveedor_sugerido_nombre=(
            detail.material.proveedor_principal.nombre
            if detail.material.proveedor_principal is not None
            else None
        ),
        stock_por_almacen=[
            RequisitionDetailStockItem(
                almacen_id=almacen_id,
                almacen_nombre=almacen_nombre,
                stock_actual=stock_actual,
            )
            for almacen_id, almacen_nombre, stock_actual in stock_rows
        ],
        notas=detail.notas,
    )


def build_requisition_item(
    requisition: Requisicion,
    details_count: int,
    *,
    cantidad_total_solicitada: Decimal = ZERO,
    cantidad_total_aprobada: Decimal = ZERO,
    cantidad_total_surtida: Decimal = ZERO,
    proveedor_sugerido_nombre: str | None = None,
    orden_compra_folio: str | None = None,
) -> RequisitionItem:
    approved_total = decimal_or_zero(cantidad_total_aprobada) or decimal_or_zero(cantidad_total_solicitada)
    cantidad_pendiente = approved_total - cantidad_total_surtida
    if cantidad_pendiente < ZERO:
        cantidad_pendiente = ZERO
    return RequisitionItem(
        id=requisition.id,
        empresa_id=requisition.empresa_id,
        folio=requisition.folio,
        solicitante_user_id=requisition.solicitante_user_id,
        solicitante_nombre=requisition.solicitante_user.full_name,
        proveedor_sugerido_id=requisition.proveedor_sugerido_id,
        proveedor_sugerido_nombre=(
            proveedor_sugerido_nombre
            if proveedor_sugerido_nombre is not None
            else requisition.proveedor_sugerido.nombre if requisition.proveedor_sugerido else None
        ),
        orden_compra_id=requisition.orden_compra_id,
        orden_compra_folio=(
            orden_compra_folio if orden_compra_folio is not None else requisition.orden_compra.folio if requisition.orden_compra else None
        ),
        es_proyecto=bool(requisition.es_proyecto),
        proyecto_id=requisition.proyecto_id,
        proyecto_nombre_snapshot=requisition.proyecto_nombre_snapshot,
        prioridad=requisition.prioridad or "normal",
        tarea_id=requisition.tarea_id,
        tarea_nombre_snapshot=requisition.tarea_nombre_snapshot,
        partida_id=requisition.partida_id,
        partida_nombre_snapshot=requisition.partida_nombre_snapshot,
        aprobador_user_id=requisition.aprobador_user_id,
        estatus=requisition.estatus,
        total_renglones=details_count,
        cantidad_total_solicitada=decimal_or_zero(cantidad_total_solicitada),
        cantidad_total_aprobada=approved_total,
        cantidad_total_surtida=decimal_or_zero(cantidad_total_surtida),
        cantidad_total_pendiente=decimal_or_zero(cantidad_pendiente),
        notas=requisition.notas,
        motivo_rechazo=requisition.motivo_rechazo,
        submitted_at=requisition.submitted_at,
        approved_at=requisition.approved_at,
        rejected_at=requisition.rejected_at,
        fulfilled_at=requisition.fulfilled_at,
        cancelled_at=requisition.cancelled_at,
        created_at=requisition.created_at,
        updated_at=requisition.updated_at,
        details_count=details_count,
    )


def build_requisition_movement_trace_item(
    movement: MovimientoInventario,
    warehouse: Almacen,
    material: Material,
    created_by: Usuario | None,
) -> RequisitionMovementTraceItem:
    return RequisitionMovementTraceItem(
        id=movement.id,
        created_at=movement.created_at,
        almacen_id=warehouse.id,
        almacen_nombre=warehouse.nombre,
        tipo=movement.tipo,
        material_id=material.id,
        material_sku=material.sku,
        material_nombre=material.nombre,
        cantidad=decimal_or_zero(movement.cantidad),
        documento_referencia=movement.documento_referencia,
        notas=movement.notas,
        proyecto_id=movement.proyecto_id,
        proyecto_nombre_snapshot=movement.proyecto_nombre_snapshot,
        tarea_nombre_snapshot=movement.pm_tarea_nombre_snapshot,
        partida_nombre_snapshot=movement.pm_partida_nombre_snapshot,
        created_by_nombre=created_by.full_name if created_by else None,
    )


def list_requisition_movements(
    db: Session,
    empresa_id: str,
    requisition_id: str,
) -> list[RequisitionMovementTraceItem]:
    rows = db.execute(
        select(MovimientoInventario, Almacen, Material, Usuario)
        .join(Almacen, Almacen.id == MovimientoInventario.almacen_id)
        .join(Material, Material.id == MovimientoInventario.material_id)
        .join(Usuario, Usuario.id == MovimientoInventario.created_by)
        .outerjoin(
            PMProyectoMaterialConsumo,
            and_(
                PMProyectoMaterialConsumo.movimiento_id == MovimientoInventario.id,
                PMProyectoMaterialConsumo.empresa_id == empresa_id,
            ),
        )
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            or_(
                and_(
                    MovimientoInventario.referencia_tipo == "requisition_fulfill",
                    MovimientoInventario.referencia_id == requisition_id,
                ),
                PMProyectoMaterialConsumo.requisicion_id == requisition_id,
            ),
        )
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
    ).all()
    return [
        build_requisition_movement_trace_item(movement, warehouse, material, created_by)
        for movement, warehouse, material, created_by in rows
    ]


def serialize_requisition_response(db: Session, requisition: Requisicion) -> RequisitionResponse:
    details = db.scalars(
        select(RequisicionDetalle)
        .where(RequisicionDetalle.requisicion_id == requisition.id)
        .order_by(RequisicionDetalle.id.asc())
    ).all()
    summary = build_requisition_item(
        requisition,
        len(details),
        cantidad_total_solicitada=sum((decimal_or_zero(item.cantidad) for item in details), ZERO),
        cantidad_total_aprobada=sum((get_requisition_detail_approved_quantity(item) for item in details), ZERO),
        cantidad_total_surtida=sum((decimal_or_zero(item.cantidad_surtida) for item in details), ZERO),
        proveedor_sugerido_nombre=requisition.proveedor_sugerido.nombre if requisition.proveedor_sugerido else None,
        orden_compra_folio=requisition.orden_compra.folio if requisition.orden_compra else None,
    )
    return RequisitionResponse(
        **summary.model_dump(),
        details=[serialize_requisition_detail(db, requisition.empresa_id, item) for item in details],
        movements=list_requisition_movements(db, requisition.empresa_id, requisition.id),
    )


def list_requisitions(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    estatus: str | None = None,
    proveedor_sugerido_id: str | None = None,
    proyecto: str | None = None,
    proyecto_id: str | None = None,
    material_id: str | None = None,
    es_proyecto: bool | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[RequisitionItem]]:
    id_query = select(Requisicion.id).where(Requisicion.empresa_id == empresa_id)
    needs_detail_join = bool(material_id or q)
    if needs_detail_join:
        id_query = id_query.join(RequisicionDetalle, RequisicionDetalle.requisicion_id == Requisicion.id)
        id_query = id_query.join(Material, Material.id == RequisicionDetalle.material_id)
    if q:
        id_query = apply_text_search(
            id_query,
            q,
            Requisicion.folio,
            Requisicion.notas,
            Requisicion.proyecto_nombre_snapshot,
            Material.nombre if needs_detail_join else Requisicion.folio,
            Material.sku if needs_detail_join else Requisicion.folio,
        )
    if estatus:
        id_query = id_query.where(Requisicion.estatus == estatus)
    if proveedor_sugerido_id:
        id_query = id_query.where(Requisicion.proveedor_sugerido_id == proveedor_sugerido_id)
    if proyecto:
        id_query = apply_text_search(id_query, proyecto, Requisicion.proyecto_nombre_snapshot, Requisicion.proyecto_id)
    if proyecto_id:
        id_query = id_query.where(Requisicion.proyecto_id == proyecto_id)
    if material_id:
        id_query = id_query.where(RequisicionDetalle.material_id == material_id)
    if es_proyecto is not None:
        id_query = id_query.where(Requisicion.es_proyecto == es_proyecto)
    if fecha_desde:
        id_query = id_query.where(Requisicion.created_at >= to_start_of_day(fecha_desde))
    if fecha_hasta:
        id_query = id_query.where(Requisicion.created_at <= to_end_of_day(fecha_hasta))

    id_query = id_query.distinct()

    total = count_rows(db, id_query)
    page_ids = db.scalars(
        id_query.order_by(desc(Requisicion.created_at), desc(Requisicion.id)).offset(offset).limit(limit)
    ).all()
    if not page_ids:
        return total, []

    details_count_subquery = (
        select(
            RequisicionDetalle.requisicion_id.label("requisicion_id"),
            func.count(RequisicionDetalle.id).label("detail_count"),
            func.coalesce(func.sum(RequisicionDetalle.cantidad), 0).label("requested_quantity"),
            func.coalesce(func.sum(func.coalesce(RequisicionDetalle.cantidad_aprobada, RequisicionDetalle.cantidad)), 0).label("approved_quantity"),
            func.coalesce(func.sum(RequisicionDetalle.cantidad_surtida), 0).label("fulfilled_quantity"),
        )
        .where(RequisicionDetalle.requisicion_id.in_(page_ids))
        .group_by(RequisicionDetalle.requisicion_id)
        .subquery()
    )

    rows = db.execute(
        select(
            Requisicion,
            Proveedor.nombre.label("proveedor_sugerido_nombre"),
            OrdenCompra.folio.label("orden_compra_folio"),
            func.coalesce(details_count_subquery.c.detail_count, 0).label("detail_count"),
            func.coalesce(details_count_subquery.c.requested_quantity, 0).label("requested_quantity"),
            func.coalesce(details_count_subquery.c.approved_quantity, 0).label("approved_quantity"),
            func.coalesce(details_count_subquery.c.fulfilled_quantity, 0).label("fulfilled_quantity"),
        )
        .outerjoin(Proveedor, Proveedor.id == Requisicion.proveedor_sugerido_id)
        .outerjoin(OrdenCompra, OrdenCompra.id == Requisicion.orden_compra_id)
        .outerjoin(details_count_subquery, details_count_subquery.c.requisicion_id == Requisicion.id)
        .where(Requisicion.id.in_(page_ids))
        .order_by(desc(Requisicion.created_at), desc(Requisicion.id))
    ).all()
    return total, [
        build_requisition_item(
            item,
            int(detail_count),
            cantidad_total_solicitada=Decimal(requested_quantity or ZERO),
            cantidad_total_aprobada=Decimal(approved_quantity or ZERO),
            cantidad_total_surtida=Decimal(fulfilled_quantity or ZERO),
            proveedor_sugerido_nombre=proveedor_sugerido_nombre,
            orden_compra_folio=orden_compra_folio,
        )
        for item, proveedor_sugerido_nombre, orden_compra_folio, detail_count, requested_quantity, approved_quantity, fulfilled_quantity in rows
    ]


def ensure_unique_requisition_folio(db: Session, empresa_id: str, folio: str, requisition_id: str | None = None) -> None:
    query = select(Requisicion.id).where(Requisicion.empresa_id == empresa_id, Requisicion.folio == folio)
    if requisition_id:
        query = query.where(Requisicion.id != requisition_id)
    existing = db.scalar(query)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El folio de requisicion ya existe en esta empresa.",
        )


def get_material_stock_total(db: Session, empresa_id: str, material_id: str) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Existencia.cantidad), 0)).where(
            Existencia.empresa_id == empresa_id,
            Existencia.material_id == material_id,
        )
    )
    return Decimal(total or ZERO)


def get_pending_requisition_for_material(db: Session, empresa_id: str, material_id: str) -> Requisicion | None:
    return db.scalar(
        select(Requisicion)
        .join(RequisicionDetalle, RequisicionDetalle.requisicion_id == Requisicion.id)
        .where(
            Requisicion.empresa_id == empresa_id,
            RequisicionDetalle.material_id == material_id,
            Requisicion.estatus.in_(["borrador", "enviada", "aprobada", "parcial", "convertida_a_oc"]),
        )
        .order_by(desc(Requisicion.created_at), desc(Requisicion.id))
        .limit(1)
    )


def calculate_suggested_requisition_quantity(material, stock_total: Decimal) -> Decimal:
    stock_minimo = Decimal(material.stock_minimo or ZERO)
    stock_maximo = Decimal(material.stock_maximo or ZERO)

    if stock_maximo > ZERO:
        return max(stock_maximo - stock_total, stock_minimo - stock_total, Decimal("1"))
    if stock_minimo > ZERO:
        return max((stock_minimo * Decimal("2")) - stock_total, stock_minimo - stock_total, Decimal("1"))
    if stock_total <= ZERO:
        return Decimal("1")
    return Decimal("1")


def resolve_requisition_project_context(
    db: Session,
    empresa_id: str,
    *,
    es_proyecto: bool,
    proyecto_id: str | None,
    proyecto_nombre_snapshot: str | None,
) -> tuple[bool, str | None, str | None]:
    normalized_project_id = normalize_optional_text(proyecto_id)
    normalized_project_name = normalize_optional_text(proyecto_nombre_snapshot)
    project_enabled = bool(es_proyecto or normalized_project_id or normalized_project_name)
    if not project_enabled:
        return False, None, None

    if normalized_project_id:
        project = db.scalar(
            select(PMProyecto).where(
                PMProyecto.id == normalized_project_id,
                PMProyecto.empresa_id == empresa_id,
            )
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado para esta empresa.",
            )
        return True, project.id, normalized_project_name or project.nombre

    return True, None, normalized_project_name


def resolve_requisition_task_context(
    db: Session,
    empresa_id: str,
    *,
    project_id: str | None,
    task_id: str | None,
) -> tuple[str | None, str | None]:
    normalized_task_id = normalize_optional_text(task_id)
    if not normalized_task_id:
        return None, None
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La requisición necesita un proyecto para asociar una tarea.",
        )
    task = db.scalar(
        select(PMTarea).where(
            PMTarea.id == normalized_task_id,
            PMTarea.empresa_id == empresa_id,
            PMTarea.proyecto_id == project_id,
            PMTarea.activo == True,
        )
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La tarea no pertenece a este proyecto.",
        )
    return task.id, task.titulo


def resolve_requisition_budget_item_context(
    db: Session,
    empresa_id: str,
    *,
    project_id: str | None,
    partida_id: str | None,
) -> tuple[str | None, str | None]:
    normalized_partida_id = normalize_optional_text(partida_id)
    if not normalized_partida_id:
        return None, None
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La requisición necesita un proyecto para asociar una partida.",
        )
    item = db.scalar(
        select(PMPresupuestoPartida).where(
            PMPresupuestoPartida.id == normalized_partida_id,
            PMPresupuestoPartida.empresa_id == empresa_id,
            PMPresupuestoPartida.proyecto_id == project_id,
            PMPresupuestoPartida.activo == True,
        )
    )
    if not item or str(item.tipo or "").lower() != "partida":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La partida no pertenece a este proyecto.",
        )
    return item.id, item.nombre


def create_requisition(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    folio: str | None,
    notas: str | None,
    proveedor_sugerido_id: str | None = None,
    es_proyecto: bool = False,
    proyecto_id: str | None = None,
    proyecto_nombre_snapshot: str | None = None,
    prioridad: str | None = None,
    tarea_id: str | None = None,
    partida_id: str | None = None,
    ip_address: str | None,
) -> RequisitionResponse:
    next_folio = normalize_optional_folio(folio, "REQ")
    ensure_unique_requisition_folio(db, empresa.id, next_folio)
    proveedor_sugerido = (
        ensure_active_supplier(db, empresa.id, proveedor_sugerido_id).id
        if normalize_optional_text(proveedor_sugerido_id)
        else None
    )
    next_es_proyecto, next_proyecto_id, next_proyecto_nombre = resolve_requisition_project_context(
        db,
        empresa.id,
        es_proyecto=es_proyecto,
        proyecto_id=proyecto_id,
        proyecto_nombre_snapshot=proyecto_nombre_snapshot,
    )
    next_tarea_id, next_tarea_nombre = resolve_requisition_task_context(
        db,
        empresa.id,
        project_id=next_proyecto_id,
        task_id=tarea_id,
    )
    next_partida_id, next_partida_nombre = resolve_requisition_budget_item_context(
        db,
        empresa.id,
        project_id=next_proyecto_id,
        partida_id=partida_id,
    )

    requisition = Requisicion(
        empresa_id=empresa.id,
        folio=next_folio,
        solicitante_user_id=user.id,
        proveedor_sugerido_id=proveedor_sugerido,
        es_proyecto=next_es_proyecto,
        proyecto_id=next_proyecto_id,
        proyecto_nombre_snapshot=next_proyecto_nombre,
        prioridad=normalize_requisition_priority(prioridad),
        tarea_id=next_tarea_id,
        tarea_nombre_snapshot=next_tarea_nombre,
        partida_id=next_partida_id,
        partida_nombre_snapshot=next_partida_nombre,
        estatus="borrador",
        notas=normalize_optional_text(notas),
    )
    db.add(requisition)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.create",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={
            "folio": requisition.folio,
            "es_proyecto": requisition.es_proyecto,
            "proveedor_sugerido_id": requisition.proveedor_sugerido_id,
            "prioridad": requisition.prioridad,
        },
    )
    return serialize_requisition_response(db, requisition)


def create_requisition_from_material(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    material_id: str,
    ip_address: str | None,
) -> RequisitionResponse:
    material = get_material_for_company(db, empresa.id, material_id)
    if not material.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede crear una requisicion para un material inactivo.",
        )

    existing = get_pending_requisition_for_material(db, empresa.id, material.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una requisicion pendiente para este material.",
        )

    suggested_quantity = calculate_suggested_requisition_quantity(
        material,
        get_material_stock_total(db, empresa.id, material.id),
    )
    requisition_response = create_requisition(
        db,
        empresa=empresa,
        user=user,
        folio=None,
        notas=f"Requisicion sugerida por bajo stock para {material.sku}",
        proveedor_sugerido_id=material.proveedor_principal_id,
        es_proyecto=False,
        proyecto_id=None,
        proyecto_nombre_snapshot=None,
        ip_address=ip_address,
    )
    requisition = get_requisition_for_company(db, empresa.id, requisition_response.id, for_update=True)
    detail = RequisicionDetalle(
        requisicion_id=requisition.id,
        material_id=material.id,
        cantidad=suggested_quantity,
        notas="Generada automaticamente desde alerta de bajo stock.",
    )
    db.add(detail)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.create_from_low_stock",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={
            "material_id": material.id,
            "cantidad_sugerida": str(suggested_quantity),
            "proveedor_sugerido_id": material.proveedor_principal_id,
        },
    )
    db.refresh(requisition)
    return serialize_requisition_response(db, requisition)


def update_requisition(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    folio: str | None,
    notas: str | None,
    proveedor_sugerido_id: str | None,
    es_proyecto: bool | None,
    proyecto_id: str | None,
    proyecto_nombre_snapshot: str | None,
    prioridad: str | None,
    tarea_id: str | None,
    partida_id: str | None,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    ensure_requisition_is_draft(requisition)

    if folio is not None:
        next_folio = normalize_optional_folio(folio, "REQ")
        ensure_unique_requisition_folio(db, empresa.id, next_folio, requisition.id)
        requisition.folio = next_folio
    if notas is not None:
        requisition.notas = normalize_optional_text(notas)
    if proveedor_sugerido_id is not None:
        requisition.proveedor_sugerido_id = (
            ensure_active_supplier(db, empresa.id, proveedor_sugerido_id).id
            if normalize_optional_text(proveedor_sugerido_id)
            else None
        )
    if prioridad is not None:
        requisition.prioridad = normalize_requisition_priority(prioridad)
    if es_proyecto is not None or proyecto_id is not None or proyecto_nombre_snapshot is not None:
        next_es_proyecto, next_proyecto_id, next_proyecto_nombre = resolve_requisition_project_context(
            db,
            empresa.id,
            es_proyecto=bool(es_proyecto),
            proyecto_id=proyecto_id,
            proyecto_nombre_snapshot=proyecto_nombre_snapshot,
        )
        requisition.es_proyecto = next_es_proyecto
        requisition.proyecto_id = next_proyecto_id
        requisition.proyecto_nombre_snapshot = next_proyecto_nombre
    target_project_id = requisition.proyecto_id if requisition.es_proyecto else None
    if tarea_id is not None:
        requisition.tarea_id, requisition.tarea_nombre_snapshot = resolve_requisition_task_context(
            db,
            empresa.id,
            project_id=target_project_id,
            task_id=tarea_id,
        )
    if partida_id is not None:
        requisition.partida_id, requisition.partida_nombre_snapshot = resolve_requisition_budget_item_context(
            db,
            empresa.id,
            project_id=target_project_id,
            partida_id=partida_id,
        )
    if not requisition.es_proyecto:
        requisition.tarea_id = None
        requisition.tarea_nombre_snapshot = None
        requisition.partida_id = None
        requisition.partida_nombre_snapshot = None

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.update",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={
            "folio": requisition.folio,
            "es_proyecto": requisition.es_proyecto,
            "proveedor_sugerido_id": requisition.proveedor_sugerido_id,
            "prioridad": requisition.prioridad,
        },
    )
    db.flush()
    db.refresh(requisition)
    return serialize_requisition_response(db, requisition)


def add_requisition_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    material_id: str,
    cantidad: Decimal,
    notas: str | None,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    ensure_requisition_is_draft(requisition)
    material = get_material_for_company(db, empresa.id, material_id)

    detail = RequisicionDetalle(
        requisicion_id=requisition.id,
        material_id=material.id,
        cantidad=Decimal(cantidad),
        cantidad_surtida=ZERO,
        notas=normalize_optional_text(notas),
    )
    db.add(detail)
    db.flush()

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.detail.create",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={"material_id": material.id, "cantidad": str(detail.cantidad)},
    )
    return serialize_requisition_response(db, requisition)


def update_requisition_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    detail_id: str,
    material_id: str | None,
    cantidad: Decimal | None,
    notas: str | None,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    ensure_requisition_is_draft(requisition)
    detail = get_requisition_detail(db, requisition.id, detail_id)

    if material_id is not None:
        material = get_material_for_company(db, empresa.id, material_id)
        detail.material_id = material.id
    if cantidad is not None:
        detail.cantidad = Decimal(cantidad)
    if notas is not None:
        detail.notas = normalize_optional_text(notas)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.detail.update",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={"detail_id": detail.id},
    )
    db.flush()
    return serialize_requisition_response(db, requisition)


def delete_requisition_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    detail_id: str,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    ensure_requisition_is_draft(requisition)
    detail = get_requisition_detail(db, requisition.id, detail_id)
    db.delete(detail)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.detail.delete",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={"detail_id": detail_id},
    )
    db.flush()
    return serialize_requisition_response(db, requisition)


def change_requisition_status(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    next_status: str,
    allowed_current_statuses: set[str],
    action: str,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    if requisition.estatus not in allowed_current_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisicion no puede cambiar a ese estatus.",
        )
    if next_status == "cancelada" and requisition.orden_compra_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisicion ya esta vinculada a una orden de compra.",
        )
    if next_status == "cancelada":
        fulfilled_lines = db.scalar(
            select(func.count(RequisicionDetalle.id)).where(
                RequisicionDetalle.requisicion_id == requisition.id,
                RequisicionDetalle.cantidad_surtida > ZERO,
            )
        ) or 0
        if fulfilled_lines > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede cancelar una requisicion que ya tiene surtidos aplicados.",
            )

    details_count = db.scalar(
        select(func.count(RequisicionDetalle.id)).where(RequisicionDetalle.requisicion_id == requisition.id)
    ) or 0
    if next_status in {"enviada", "aprobada"} and details_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisicion necesita al menos un detalle.",
        )

    requisition.estatus = next_status
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action=action,
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={"estatus": next_status},
    )
    db.flush()
    db.refresh(requisition)
    return serialize_requisition_response(db, requisition)


def submit_requisition(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    if requisition.estatus != "borrador":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo las requisiciones en borrador pueden enviarse.",
        )
    details = db.scalars(
        select(RequisicionDetalle).where(RequisicionDetalle.requisicion_id == requisition.id)
    ).all()
    if not details:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisición necesita al menos un material.",
        )
    requisition.estatus = "enviada"
    requisition.submitted_at = datetime.now(timezone.utc)
    requisition.motivo_rechazo = None
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.submit",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={"estatus": requisition.estatus},
    )
    db.flush()
    db.refresh(requisition)
    return serialize_requisition_response(db, requisition)


def approve_requisition(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    items: list,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    if requisition.estatus != "enviada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo las requisiciones enviadas pueden aprobarse.",
        )
    details = db.scalars(
        select(RequisicionDetalle)
        .where(RequisicionDetalle.requisicion_id == requisition.id)
        .with_for_update()
    ).all()
    if not details:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisición necesita al menos un material.",
        )
    approved_map = {item.detail_id: Decimal(item.cantidad_aprobada) for item in items or []}
    for detail in details:
        next_approved = approved_map.get(detail.id, Decimal(detail.cantidad))
        if next_approved <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad aprobada debe ser mayor a cero.",
            )
        if next_approved > Decimal(detail.cantidad):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La cantidad aprobada no puede exceder la cantidad solicitada.",
            )
        detail.cantidad_aprobada = next_approved
    requisition.estatus = "aprobada"
    requisition.approved_at = datetime.now(timezone.utc)
    requisition.aprobador_user_id = user.id
    requisition.motivo_rechazo = None
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.approve",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={"estatus": requisition.estatus},
    )
    db.flush()
    db.refresh(requisition)
    return serialize_requisition_response(db, requisition)


def reject_requisition(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    motivo_rechazo: str,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    if requisition.estatus not in {"enviada", "aprobada"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo las requisiciones enviadas o aprobadas pueden rechazarse.",
        )
    fulfilled_lines = db.scalar(
        select(func.count(RequisicionDetalle.id)).where(
            RequisicionDetalle.requisicion_id == requisition.id,
            RequisicionDetalle.cantidad_surtida > ZERO,
        )
    ) or 0
    if fulfilled_lines > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes rechazar una requisición que ya tiene surtidos registrados.",
        )
    requisition.estatus = "rechazada"
    requisition.rejected_at = datetime.now(timezone.utc)
    requisition.aprobador_user_id = user.id
    requisition.motivo_rechazo = normalize_required_text(motivo_rechazo, "Motivo de rechazo")
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.reject",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={"estatus": requisition.estatus},
    )
    db.flush()
    db.refresh(requisition)
    return serialize_requisition_response(db, requisition)


def cancel_requisition(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    if requisition.estatus not in {"borrador", "enviada", "aprobada"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisición no puede cancelarse en su estatus actual.",
        )
    if requisition.orden_compra_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisición ya está vinculada a una orden de compra.",
        )
    fulfilled_lines = db.scalar(
        select(func.count(RequisicionDetalle.id)).where(
            RequisicionDetalle.requisicion_id == requisition.id,
            RequisicionDetalle.cantidad_surtida > ZERO,
        )
    ) or 0
    if fulfilled_lines > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede cancelar una requisición que ya tiene surtidos aplicados.",
        )
    requisition.estatus = "cancelada"
    requisition.cancelled_at = datetime.now(timezone.utc)
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.cancel",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={"estatus": requisition.estatus},
    )
    db.flush()
    db.refresh(requisition)
    return serialize_requisition_response(db, requisition)


def fulfill_requisition(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    almacen_id: str,
    items: list,
    documento_referencia: str | None,
    notas: str | None,
    proyecto_id: str | None,
    proyecto_nombre_snapshot: str | None,
    ip_address: str | None,
) -> RequisitionResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    if requisition.estatus not in {"aprobada", "parcial"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisicion solo puede surtirse si esta aprobada o parcial.",
        )
    if requisition.orden_compra_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisicion ya esta vinculada a una orden de compra. Revisa la recepcion de la OC para completar el flujo.",
        )

    warehouse = get_warehouse_for_company(db, empresa.id, almacen_id)
    detail_map = {
        detail.id: detail
        for detail in db.scalars(
            select(RequisicionDetalle)
            .where(RequisicionDetalle.requisicion_id == requisition.id)
            .with_for_update()
        ).all()
    }
    if not detail_map:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisicion necesita al menos un detalle para surtirse.",
        )

    movement_is_project, movement_project_id, movement_project_name = resolve_requisition_project_context(
        db,
        empresa.id,
        es_proyecto=bool(requisition.es_proyecto),
        proyecto_id=proyecto_id if proyecto_id is not None else requisition.proyecto_id,
        proyecto_nombre_snapshot=(
            proyecto_nombre_snapshot
            if proyecto_nombre_snapshot is not None
            else requisition.proyecto_nombre_snapshot
        ),
    )
    from app.services.inventory import consume_material_for_project

    applied_any = False
    seen_detail_ids: set[str] = set()
    for item in items:
        if item.detail_id in seen_detail_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede repetir el mismo detalle en una sola recepcion.",
            )
        seen_detail_ids.add(item.detail_id)

        detail = detail_map.get(item.detail_id)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Detalle de requisicion no encontrado.",
            )

        fulfill_quantity = Decimal(item.cantidad_surtir)
        pending_quantity = get_requisition_detail_pending_quantity(detail)
        if fulfill_quantity > pending_quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La cantidad a surtir excede lo pendiente por surtir.",
            )
        if fulfill_quantity <= ZERO:
            continue
        available_stock = decimal_or_zero(
            db.scalar(
                select(Existencia.cantidad).where(
                    Existencia.empresa_id == empresa.id,
                    Existencia.almacen_id == warehouse.id,
                    Existencia.material_id == detail.material_id,
                )
            )
        )
        if fulfill_quantity > available_stock:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No hay stock suficiente para surtir esta cantidad.",
            )

        movement_notes = "\n".join(
            part
            for part in [
                f"Surtido de requisicion {requisition.folio}",
                normalize_optional_text(notas),
            ]
            if part
        )
        if movement_project_id:
            movement = consume_material_for_project(
                db,
                empresa_id=empresa.id,
                proyecto_id=movement_project_id,
                material_id=detail.material_id,
                almacen_id=warehouse.id,
                cantidad=fulfill_quantity,
                tarea_id=requisition.tarea_id,
                partida_id=requisition.partida_id,
                notas=movement_notes or None,
                usuario_id=user.id,
                user=user,
                empresa=empresa,
                ip_address=ip_address,
                documento_referencia=documento_referencia,
                requisition_id=requisition.id,
                requisition_detail_id=detail.id,
                origin="requisicion_surtida",
            )
        else:
            movement = apply_inventory_movement(
                db,
                user=user,
                empresa=empresa,
                almacen_id=warehouse.id,
                material_id=detail.material_id,
                tipo="salida",
                cantidad=fulfill_quantity,
                cantidad_nueva=None,
                referencia_tipo="requisition_fulfill",
                referencia_id=requisition.id,
                notas=movement_notes or None,
                ip_address=ip_address,
                motivo="Surtido de requisicion",
                entregado_por=user.full_name,
                documento_referencia=documento_referencia,
                es_proyecto=movement_is_project,
                proyecto_id=movement_project_id,
                proyecto_nombre_snapshot=movement_project_name,
            )
            from app.services.pm import create_project_material_consumption_from_movement

            create_project_material_consumption_from_movement(
                db,
                empresa_id=empresa.id,
                movement_id=movement.id,
                project_id=movement_project_id,
                requisition_id=requisition.id,
                requisition_detail_id=detail.id,
                origen="requisicion_surtida",
            )
        detail.cantidad_surtida = decimal_or_zero(detail.cantidad_surtida) + fulfill_quantity
        applied_any = True

    if not applied_any:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se registro ninguna cantidad valida para surtir.",
        )

    if movement_is_project:
        requisition.es_proyecto = True
        requisition.proyecto_id = movement_project_id
        requisition.proyecto_nombre_snapshot = movement_project_name

    details = list(detail_map.values())
    if all(get_requisition_detail_pending_quantity(detail) <= ZERO for detail in details):
        requisition.estatus = "surtida"
        requisition.fulfilled_at = datetime.now(timezone.utc)
    else:
        requisition.estatus = "parcial"

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.fulfill",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={
            "almacen_id": warehouse.id,
            "estatus": requisition.estatus,
            "es_proyecto": requisition.es_proyecto,
        },
    )
    db.flush()
    db.refresh(requisition)
    return serialize_requisition_response(db, requisition)


def ensure_purchase_order_is_draft(order: OrdenCompra) -> None:
    if order.estatus != "borrador":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden modificar ordenes de compra en borrador.",
        )


def get_purchase_order_for_company(
    db: Session,
    empresa_id: str,
    order_id: str,
    *,
    for_update: bool = False,
) -> OrdenCompra:
    query = select(OrdenCompra).where(
        OrdenCompra.id == order_id,
        OrdenCompra.empresa_id == empresa_id,
    )
    if for_update:
        query = query.with_for_update()
    order = db.scalar(query)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de compra no encontrada.")
    return order


def get_purchase_order_detail(db: Session, order_id: str, detail_id: str) -> OrdenCompraDetalle:
    detail = db.scalar(
        select(OrdenCompraDetalle).where(
            OrdenCompraDetalle.id == detail_id,
            OrdenCompraDetalle.orden_compra_id == order_id,
        )
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detalle de orden de compra no encontrado.",
        )
    return detail


def ensure_active_supplier(db: Session, empresa_id: str, supplier_id: str) -> Proveedor:
    supplier = get_supplier_for_company(db, empresa_id, supplier_id)
    if not supplier.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede usar un proveedor inactivo.",
        )
    return supplier


def ensure_active_destination_warehouse(db: Session, empresa_id: str, warehouse_id: str):
    warehouse = get_warehouse_for_company(db, empresa_id, warehouse_id)
    if not warehouse.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede recibir en un almacen inactivo.",
        )
    return warehouse


def to_start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def to_end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def get_linked_purchase_requisition(order: OrdenCompra) -> Requisicion | None:
    if not order.requisiciones:
        return None
    return sorted(order.requisiciones, key=lambda item: (item.created_at, item.id))[0]


def get_purchase_order_line_state(detail: OrdenCompraDetalle) -> str:
    ordered = Decimal(detail.cantidad or ZERO)
    received = Decimal(detail.cantidad_recibida or ZERO)
    if received <= ZERO:
        return "pendiente"
    if received >= ordered:
        return "completa"
    return "parcial"


def build_purchase_order_movement_trace_item(
    movement: MovimientoInventario,
    warehouse: Almacen,
    material: Material,
    user: Usuario | None,
) -> PurchaseOrderMovementTraceItem:
    return PurchaseOrderMovementTraceItem(
        id=movement.id,
        created_at=movement.created_at,
        almacen_id=warehouse.id,
        almacen_nombre=warehouse.nombre,
        tipo=movement.tipo,
        material_id=movement.material_id,
        material_sku=material.sku,
        material_nombre=material.nombre,
        cantidad=movement.cantidad,
        documento_referencia=movement.documento_referencia,
        notas=movement.notas,
        recibido_por=movement.recibido_por,
        created_by_nombre=user.full_name if user else None,
        grupo_referencia=movement.grupo_referencia,
    )


def list_purchase_order_movements(db: Session, empresa_id: str, order_id: str) -> list[PurchaseOrderMovementTraceItem]:
    rows = db.execute(
        select(MovimientoInventario, Almacen, Material, Usuario)
        .join(Almacen, MovimientoInventario.almacen_id == Almacen.id)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .join(Usuario, MovimientoInventario.created_by == Usuario.id)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.referencia_tipo == "purchase_order_receive",
            MovimientoInventario.referencia_id == order_id,
        )
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
    ).all()
    return [build_purchase_order_movement_trace_item(movement, warehouse, material, user) for movement, warehouse, material, user in rows]


def build_purchase_order_receipts_from_models(
    db: Session,
    receipts: list[OrdenCompraRecepcion],
) -> list[PurchaseOrderReceiptItem]:
    if not receipts:
        return []

    receipt_ids = [item.id for item in receipts]
    receipt_empresa_id = receipts[0].empresa_id
    detail_rows = db.execute(
        select(OrdenCompraRecepcionDetalle, Material)
        .join(Material, OrdenCompraRecepcionDetalle.material_id == Material.id)
        .where(OrdenCompraRecepcionDetalle.recepcion_id.in_(receipt_ids))
        .order_by(OrdenCompraRecepcionDetalle.id.asc())
    ).all()
    receipt_detail_map: dict[str, list[PurchaseOrderReceiptDetailItem]] = {receipt_id: [] for receipt_id in receipt_ids}
    for detail, material in detail_rows:
        receipt_detail_map.setdefault(detail.recepcion_id, []).append(
            PurchaseOrderReceiptDetailItem(
                id=detail.id,
                recepcion_id=detail.recepcion_id,
                orden_compra_detalle_id=detail.orden_compra_detalle_id,
                material_id=detail.material_id,
                material_sku=material.sku,
                material_nombre=material.nombre,
                material_unidad=material.unidad,
                cantidad_recibida=detail.cantidad_recibida,
                costo_unitario_snapshot=detail.costo_unitario_snapshot,
                movimiento_inventario_id=detail.movimiento_inventario_id,
            )
        )

    movement_rows = db.execute(
        select(MovimientoInventario, Almacen, Material, Usuario)
        .join(Almacen, MovimientoInventario.almacen_id == Almacen.id)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .join(Usuario, MovimientoInventario.created_by == Usuario.id)
        .where(
            MovimientoInventario.empresa_id == receipt_empresa_id,
            MovimientoInventario.grupo_referencia.in_(receipt_ids),
        )
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
    ).all()
    receipt_movement_map: dict[str, list[PurchaseOrderMovementTraceItem]] = {receipt_id: [] for receipt_id in receipt_ids}
    for movement, warehouse, material, user in movement_rows:
        group_reference = normalize_optional_text(movement.grupo_referencia)
        if not group_reference:
            continue
        receipt_movement_map.setdefault(group_reference, []).append(
            build_purchase_order_movement_trace_item(movement, warehouse, material, user)
        )

    return [
        PurchaseOrderReceiptItem(
            id=receipt.id,
            empresa_id=receipt.empresa_id,
            orden_compra_id=receipt.orden_compra_id,
            almacen_id=receipt.almacen_id,
            almacen_nombre=receipt.almacen.nombre,
            documento_referencia=receipt.documento_referencia,
            notas=receipt.notas,
            recibido_por_user_id=receipt.recibido_por_user_id,
            recibido_por_nombre=receipt.recibido_por_user.full_name,
            created_at=receipt.created_at,
            updated_at=receipt.updated_at,
            items=receipt_detail_map.get(receipt.id, []),
            movements=receipt_movement_map.get(receipt.id, []),
        )
        for receipt in receipts
    ]


def list_purchase_order_receipts(db: Session, empresa_id: str, order_id: str) -> list[PurchaseOrderReceiptItem]:
    receipts = db.scalars(
        select(OrdenCompraRecepcion)
        .where(
            OrdenCompraRecepcion.empresa_id == empresa_id,
            OrdenCompraRecepcion.orden_compra_id == order_id,
        )
        .order_by(desc(OrdenCompraRecepcion.created_at), desc(OrdenCompraRecepcion.id))
    ).all()
    return build_purchase_order_receipts_from_models(db, receipts)


def list_supplier_receipts(
    db: Session,
    empresa_id: str,
    supplier_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[PurchaseOrderReceiptItem]]:
    get_supplier_for_company(db, empresa_id, supplier_id)
    id_query = (
        select(OrdenCompraRecepcion.id)
        .join(OrdenCompra, OrdenCompraRecepcion.orden_compra_id == OrdenCompra.id)
        .where(
            OrdenCompraRecepcion.empresa_id == empresa_id,
            OrdenCompra.proveedor_id == supplier_id,
        )
    )
    total = count_rows(db, id_query)
    receipts = db.scalars(
        select(OrdenCompraRecepcion)
        .join(OrdenCompra, OrdenCompraRecepcion.orden_compra_id == OrdenCompra.id)
        .where(
            OrdenCompraRecepcion.empresa_id == empresa_id,
            OrdenCompra.proveedor_id == supplier_id,
        )
        .order_by(desc(OrdenCompraRecepcion.created_at), desc(OrdenCompraRecepcion.id))
        .offset(offset)
        .limit(limit)
    ).all()
    return total, build_purchase_order_receipts_from_models(db, receipts)


def list_supplier_materials(
    db: Session,
    empresa_id: str,
    supplier_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[SupplierMaterialItem]]:
    supplier = get_supplier_for_company(db, empresa_id, supplier_id)
    ordered_rows = db.execute(
        select(
            Material,
            func.count(func.distinct(OrdenCompra.id)).label("orders_count"),
            func.coalesce(func.sum(OrdenCompraDetalle.cantidad), 0).label("total_ordenado"),
            func.coalesce(func.sum(OrdenCompraDetalle.cantidad_recibida), 0).label("total_recibido"),
            func.coalesce(func.sum(OrdenCompraDetalle.total_linea), 0).label("monto_total"),
            func.max(OrdenCompra.created_at).label("ultima_orden_at"),
        )
        .join(OrdenCompraDetalle, OrdenCompraDetalle.material_id == Material.id)
        .join(OrdenCompra, OrdenCompra.id == OrdenCompraDetalle.orden_compra_id)
        .where(
            Material.empresa_id == empresa_id,
            OrdenCompra.empresa_id == empresa_id,
            OrdenCompra.proveedor_id == supplier.id,
        )
        .group_by(Material.id)
    ).all()

    material_map: dict[str, SupplierMaterialItem] = {}
    for material, orders_count, total_ordenado, total_recibido, monto_total, ultima_orden_at in ordered_rows:
        material_map[material.id] = SupplierMaterialItem(
            material_id=material.id,
            sku=material.sku,
            nombre=material.nombre,
            unidad=material.unidad,
            activo=material.activo,
            es_proveedor_principal=material.proveedor_principal_id == supplier.id,
            ordenes_count=int(orders_count or 0),
            total_ordenado=Decimal(total_ordenado or ZERO),
            total_recibido=Decimal(total_recibido or ZERO),
            monto_total_comprado=Decimal(monto_total or ZERO),
            ultima_orden_at=ultima_orden_at,
        )

    principal_materials = db.scalars(
        select(Material)
        .where(
            Material.empresa_id == empresa_id,
            Material.proveedor_principal_id == supplier.id,
        )
        .order_by(Material.nombre.asc(), Material.sku.asc())
    ).all()
    for material in principal_materials:
        existing = material_map.get(material.id)
        if existing is None:
            material_map[material.id] = SupplierMaterialItem(
                material_id=material.id,
                sku=material.sku,
                nombre=material.nombre,
                unidad=material.unidad,
                activo=material.activo,
                es_proveedor_principal=True,
            )
        else:
            existing.es_proveedor_principal = True

    min_datetime = datetime.min.replace(tzinfo=timezone.utc)
    items = sorted(
        material_map.values(),
        key=lambda item: (
            item.ultima_orden_at or min_datetime,
            Decimal(item.monto_total_comprado or ZERO),
            item.nombre.lower(),
        ),
        reverse=True,
    )
    total = len(items)
    return total, items[offset : offset + limit]


def get_supplier_summary(db: Session, empresa_id: str, supplier_id: str) -> SupplierSummaryResponse:
    supplier = get_supplier_for_company(db, empresa_id, supplier_id)
    open_statuses = {"emitida", "recibida_parcial"}
    ordenes_totales = db.scalar(
        select(func.count(OrdenCompra.id)).where(
            OrdenCompra.empresa_id == empresa_id,
            OrdenCompra.proveedor_id == supplier.id,
        )
    ) or 0
    ordenes_abiertas = db.scalar(
        select(func.count(OrdenCompra.id)).where(
            OrdenCompra.empresa_id == empresa_id,
            OrdenCompra.proveedor_id == supplier.id,
            OrdenCompra.estatus.in_(open_statuses),
        )
    ) or 0
    ordenes_recibidas = db.scalar(
        select(func.count(OrdenCompra.id)).where(
            OrdenCompra.empresa_id == empresa_id,
            OrdenCompra.proveedor_id == supplier.id,
            OrdenCompra.estatus == "recibida",
        )
    ) or 0
    monto_total_comprado = db.scalar(
        select(func.coalesce(func.sum(OrdenCompra.total), 0)).where(
            OrdenCompra.empresa_id == empresa_id,
            OrdenCompra.proveedor_id == supplier.id,
            OrdenCompra.estatus != "cancelada",
        )
    ) or ZERO
    monto_pendiente_por_recibir = db.scalar(
        select(
            func.coalesce(
                func.sum((OrdenCompraDetalle.cantidad - OrdenCompraDetalle.cantidad_recibida) * OrdenCompraDetalle.costo_unitario),
                0,
            )
        )
        .join(OrdenCompra, OrdenCompra.id == OrdenCompraDetalle.orden_compra_id)
        .where(
            OrdenCompra.empresa_id == empresa_id,
            OrdenCompra.proveedor_id == supplier.id,
            OrdenCompra.estatus.in_(open_statuses),
        )
    ) or ZERO
    recepciones_totales = db.scalar(
        select(func.count(OrdenCompraRecepcion.id))
        .join(OrdenCompra, OrdenCompraRecepcion.orden_compra_id == OrdenCompra.id)
        .where(
            OrdenCompraRecepcion.empresa_id == empresa_id,
            OrdenCompra.proveedor_id == supplier.id,
        )
    ) or 0
    _, ordenes_recientes = list_purchase_orders(
        db,
        empresa_id,
        proveedor_id=supplier.id,
        limit=5,
        offset=0,
    )
    _, recepciones_recientes = list_supplier_receipts(
        db,
        empresa_id,
        supplier.id,
        limit=5,
        offset=0,
    )
    materiales_asociados, materiales_relacionados = list_supplier_materials(
        db,
        empresa_id,
        supplier.id,
        limit=5,
        offset=0,
    )
    return SupplierSummaryResponse(
        proveedor=serialize_supplier(supplier),
        ordenes_totales=int(ordenes_totales),
        ordenes_abiertas=int(ordenes_abiertas),
        ordenes_recibidas=int(ordenes_recibidas),
        monto_total_comprado=Decimal(monto_total_comprado or ZERO),
        monto_pendiente_por_recibir=Decimal(monto_pendiente_por_recibir or ZERO),
        recepciones_totales=int(recepciones_totales),
        materiales_asociados=int(materiales_asociados),
        ordenes_recientes=ordenes_recientes,
        recepciones_recientes=recepciones_recientes,
        materiales_relacionados=materiales_relacionados,
    )


def serialize_purchase_order_detail(detail: OrdenCompraDetalle) -> PurchaseOrderDetailItem:
    cantidad = Decimal(detail.cantidad or ZERO)
    cantidad_recibida = Decimal(detail.cantidad_recibida or ZERO)
    return PurchaseOrderDetailItem(
        id=detail.id,
        orden_compra_id=detail.orden_compra_id,
        material_id=detail.material_id,
        material_sku=detail.material.sku,
        material_nombre=detail.material.nombre,
        material_unidad=detail.material.unidad,
        cantidad=cantidad,
        cantidad_recibida=cantidad_recibida,
        cantidad_pendiente=max(cantidad - cantidad_recibida, ZERO),
        costo_unitario=detail.costo_unitario,
        subtotal_linea=detail.subtotal_linea,
        total_linea=detail.total_linea,
        estado_linea=get_purchase_order_line_state(detail),
        ultima_recepcion_at=detail.ultima_recepcion_at,
    )


def build_purchase_order_item(
    order: OrdenCompra,
    details_count: int,
    *,
    cantidad_total_ordenada: Decimal = ZERO,
    cantidad_total_recibida: Decimal = ZERO,
    valor_total_recibido: Decimal = ZERO,
    valor_total_pendiente: Decimal = ZERO,
    recepciones_count: int = 0,
    requisicion_id: str | None = None,
    requisicion_folio: str | None = None,
) -> PurchaseOrderItem:
    cantidad_total_pendiente = max(Decimal(cantidad_total_ordenada) - Decimal(cantidad_total_recibida), ZERO)
    return PurchaseOrderItem(
        id=order.id,
        empresa_id=order.empresa_id,
        folio=order.folio,
        proveedor_id=order.proveedor_id,
        proveedor_nombre=order.proveedor.nombre,
        almacen_destino_id=order.almacen_destino_id,
        almacen_destino_nombre=order.almacen_destino.nombre,
        created_by_user_id=order.created_by_user_id,
        created_by_nombre=order.created_by_user.full_name,
        estatus=order.estatus,
        subtotal=order.subtotal,
        descuento_total=order.descuento_total,
        impuesto_total=order.impuesto_total,
        total=order.total,
        fecha_emitida=order.fecha_emitida,
        fecha_esperada=order.fecha_esperada,
        fecha_ultima_recepcion=order.fecha_ultima_recepcion,
        documento_referencia=order.documento_referencia,
        notas_recepcion=order.notas_recepcion,
        recibido_por_user_id=order.recibido_por_user_id,
        recibido_por_nombre=order.recibido_por_user.full_name if order.recibido_por_user else None,
        proveedor_contacto_snapshot=order.proveedor_contacto_snapshot,
        proveedor_email_snapshot=order.proveedor_email_snapshot,
        proveedor_telefono_snapshot=order.proveedor_telefono_snapshot,
        condiciones_pago_snapshot=order.condiciones_pago_snapshot,
        moneda_snapshot=order.moneda_snapshot,
        notas=order.notas,
        created_at=order.created_at,
        updated_at=order.updated_at,
        details_count=details_count,
        cantidad_renglones=details_count,
        cantidad_total_ordenada=Decimal(cantidad_total_ordenada),
        cantidad_total_recibida=Decimal(cantidad_total_recibida),
        cantidad_total_pendiente=cantidad_total_pendiente,
        valor_total_recibido=Decimal(valor_total_recibido),
        valor_total_pendiente=Decimal(valor_total_pendiente),
        recepciones_count=recepciones_count,
        requisicion_id=requisicion_id,
        requisicion_folio=requisicion_folio,
    )


def serialize_purchase_order_response(db: Session, order: OrdenCompra) -> PurchaseOrderResponse:
    details = db.scalars(
        select(OrdenCompraDetalle)
        .where(OrdenCompraDetalle.orden_compra_id == order.id)
        .order_by(OrdenCompraDetalle.id.asc())
    ).all()
    total_ordenada = sum((Decimal(item.cantidad or ZERO) for item in details), start=ZERO)
    total_recibida = sum((Decimal(item.cantidad_recibida or ZERO) for item in details), start=ZERO)
    valor_total_recibido = sum(
        (Decimal(item.cantidad_recibida or ZERO) * Decimal(item.costo_unitario or ZERO) for item in details),
        start=ZERO,
    )
    valor_total_pendiente = sum(
        ((Decimal(item.cantidad or ZERO) - Decimal(item.cantidad_recibida or ZERO)) * Decimal(item.costo_unitario or ZERO) for item in details),
        start=ZERO,
    )
    requisition = get_linked_purchase_requisition(order)
    receipts = list_purchase_order_receipts(db, order.empresa_id, order.id)
    summary = build_purchase_order_item(
        order,
        len(details),
        cantidad_total_ordenada=total_ordenada,
        cantidad_total_recibida=total_recibida,
        valor_total_recibido=valor_total_recibido,
        valor_total_pendiente=max(valor_total_pendiente, ZERO),
        recepciones_count=len(receipts),
        requisicion_id=requisition.id if requisition else None,
        requisicion_folio=requisition.folio if requisition else None,
    )
    return PurchaseOrderResponse(
        **summary.model_dump(),
        details=[serialize_purchase_order_detail(item) for item in details],
        movements=list_purchase_order_movements(db, order.empresa_id, order.id),
        receipts=receipts,
    )


def recompute_purchase_order_totals(db: Session, order: OrdenCompra) -> None:
    subtotal = db.scalar(
        select(func.coalesce(func.sum(OrdenCompraDetalle.subtotal_linea), 0)).where(
            OrdenCompraDetalle.orden_compra_id == order.id
        )
    ) or ZERO
    order.subtotal = subtotal
    order.descuento_total = ZERO
    order.impuesto_total = ZERO
    order.total = subtotal


def list_purchase_orders(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    estatus: str | None = None,
    proveedor_id: str | None = None,
    almacen_destino_id: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[PurchaseOrderItem]]:
    id_query = (
        select(OrdenCompra.id)
        .select_from(OrdenCompra)
        .join(Proveedor, OrdenCompra.proveedor_id == Proveedor.id)
        .where(OrdenCompra.empresa_id == empresa_id)
    )
    id_query = apply_text_search(id_query, q, OrdenCompra.folio, OrdenCompra.notas, Proveedor.nombre, Proveedor.razon_social)
    if estatus:
        id_query = id_query.where(OrdenCompra.estatus == estatus)
    if proveedor_id:
        id_query = id_query.where(OrdenCompra.proveedor_id == proveedor_id)
    if almacen_destino_id:
        id_query = id_query.where(OrdenCompra.almacen_destino_id == almacen_destino_id)
    if fecha_desde:
        id_query = id_query.where(OrdenCompra.created_at >= to_start_of_day(fecha_desde))
    if fecha_hasta:
        id_query = id_query.where(OrdenCompra.created_at <= to_end_of_day(fecha_hasta))

    total = count_rows(db, id_query)
    page_ids = db.scalars(
        id_query.order_by(desc(OrdenCompra.created_at), desc(OrdenCompra.id)).offset(offset).limit(limit)
    ).all()
    if not page_ids:
        return total, []

    details_count_subquery = (
        select(
            OrdenCompraDetalle.orden_compra_id.label("orden_compra_id"),
            func.count(OrdenCompraDetalle.id).label("detail_count"),
            func.coalesce(func.sum(OrdenCompraDetalle.cantidad), 0).label("ordered_quantity"),
            func.coalesce(func.sum(OrdenCompraDetalle.cantidad_recibida), 0).label("received_quantity"),
            func.coalesce(
                func.sum(OrdenCompraDetalle.cantidad_recibida * OrdenCompraDetalle.costo_unitario),
                0,
            ).label("received_value"),
            func.coalesce(
                func.sum((OrdenCompraDetalle.cantidad - OrdenCompraDetalle.cantidad_recibida) * OrdenCompraDetalle.costo_unitario),
                0,
            ).label("pending_value"),
        )
        .where(OrdenCompraDetalle.orden_compra_id.in_(page_ids))
        .group_by(OrdenCompraDetalle.orden_compra_id)
        .subquery()
    )

    receipts_count_subquery = (
        select(
            OrdenCompraRecepcion.orden_compra_id.label("orden_compra_id"),
            func.count(OrdenCompraRecepcion.id).label("receipts_count"),
        )
        .where(
            OrdenCompraRecepcion.empresa_id == empresa_id,
            OrdenCompraRecepcion.orden_compra_id.in_(page_ids),
        )
        .group_by(OrdenCompraRecepcion.orden_compra_id)
        .subquery()
    )

    requisition_subquery = (
        select(
            Requisicion.orden_compra_id.label("orden_compra_id"),
            func.min(Requisicion.id).label("requisicion_id"),
            func.min(Requisicion.folio).label("requisicion_folio"),
        )
        .where(
            Requisicion.empresa_id == empresa_id,
            Requisicion.orden_compra_id.in_(page_ids),
        )
        .group_by(Requisicion.orden_compra_id)
        .subquery()
    )

    rows = db.execute(
        select(
            OrdenCompra,
            func.coalesce(details_count_subquery.c.detail_count, 0).label("detail_count"),
            func.coalesce(details_count_subquery.c.ordered_quantity, 0).label("ordered_quantity"),
            func.coalesce(details_count_subquery.c.received_quantity, 0).label("received_quantity"),
            func.coalesce(details_count_subquery.c.received_value, 0).label("received_value"),
            func.coalesce(details_count_subquery.c.pending_value, 0).label("pending_value"),
            func.coalesce(receipts_count_subquery.c.receipts_count, 0).label("receipts_count"),
            requisition_subquery.c.requisicion_id,
            requisition_subquery.c.requisicion_folio,
        )
        .outerjoin(details_count_subquery, details_count_subquery.c.orden_compra_id == OrdenCompra.id)
        .outerjoin(receipts_count_subquery, receipts_count_subquery.c.orden_compra_id == OrdenCompra.id)
        .outerjoin(requisition_subquery, requisition_subquery.c.orden_compra_id == OrdenCompra.id)
        .where(OrdenCompra.id.in_(page_ids))
        .order_by(desc(OrdenCompra.created_at), desc(OrdenCompra.id))
    ).all()
    return total, [
        build_purchase_order_item(
            item,
            int(detail_count),
            cantidad_total_ordenada=Decimal(ordered_quantity or ZERO),
            cantidad_total_recibida=Decimal(received_quantity or ZERO),
            valor_total_recibido=Decimal(received_value or ZERO),
            valor_total_pendiente=max(Decimal(pending_value or ZERO), ZERO),
            recepciones_count=int(receipts_count or 0),
            requisicion_id=requisicion_id,
            requisicion_folio=requisicion_folio,
        )
        for item, detail_count, ordered_quantity, received_quantity, received_value, pending_value, receipts_count, requisicion_id, requisicion_folio in rows
    ]


def ensure_unique_purchase_order_folio(db: Session, empresa_id: str, folio: str, order_id: str | None = None) -> None:
    query = select(OrdenCompra.id).where(OrdenCompra.empresa_id == empresa_id, OrdenCompra.folio == folio)
    if order_id:
        query = query.where(OrdenCompra.id != order_id)
    existing = db.scalar(query)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El folio de orden de compra ya existe en esta empresa.",
        )


def create_purchase_order_record(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    folio: str | None,
    proveedor_id: str,
    almacen_destino_id: str,
    notas: str | None,
) -> OrdenCompra:
    next_folio = normalize_optional_folio(folio, "OC")
    ensure_unique_purchase_order_folio(db, empresa.id, next_folio)
    supplier = ensure_active_supplier(db, empresa.id, proveedor_id)
    warehouse = ensure_active_destination_warehouse(db, empresa.id, almacen_destino_id)

    order = OrdenCompra(
        empresa_id=empresa.id,
        folio=next_folio,
        proveedor_id=supplier.id,
        almacen_destino_id=warehouse.id,
        created_by_user_id=user.id,
        estatus="borrador",
        subtotal=ZERO,
        descuento_total=ZERO,
        impuesto_total=ZERO,
        total=ZERO,
        notas=normalize_optional_text(notas),
    )
    apply_supplier_snapshot(order, supplier)
    db.add(order)
    db.flush()
    return order


def create_purchase_order(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    folio: str | None,
    proveedor_id: str,
    almacen_destino_id: str,
    notas: str | None,
    ip_address: str | None,
) -> PurchaseOrderResponse:
    order = create_purchase_order_record(
        db,
        empresa=empresa,
        user=user,
        folio=folio,
        proveedor_id=proveedor_id,
        almacen_destino_id=almacen_destino_id,
        notas=notas,
    )
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.purchase_order.create",
        entity_name="orden_compra",
        entity_id=order.id,
        ip_address=ip_address,
        metadata_json={"folio": order.folio},
    )
    return serialize_purchase_order_response(db, order)


def create_purchase_order_from_requisition(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    requisition_id: str,
    proveedor_id: str,
    almacen_destino_id: str,
    folio: str | None,
    ip_address: str | None,
) -> PurchaseOrderResponse:
    requisition = get_requisition_for_company(db, empresa.id, requisition_id, for_update=True)
    if requisition.estatus not in {"aprobada", "parcial"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo las requisiciones aprobadas o parciales pueden convertirse en orden de compra.",
        )
    if requisition.orden_compra_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisicion ya tiene una orden de compra creada.",
        )

    details = db.scalars(
        select(RequisicionDetalle)
        .where(RequisicionDetalle.requisicion_id == requisition.id)
        .order_by(RequisicionDetalle.id.asc())
    ).all()
    if not details:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisicion necesita al menos un detalle para crear la orden de compra.",
        )

    pending_details = [
        (detail, get_requisition_detail_pending_quantity(detail))
        for detail in details
        if get_requisition_detail_pending_quantity(detail) > ZERO
    ]
    if not pending_details:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La requisicion ya no tiene cantidades pendientes por comprar.",
        )

    order_notes = requisition.notas or None
    order = create_purchase_order_record(
        db,
        empresa=empresa,
        user=user,
        folio=folio,
        proveedor_id=proveedor_id,
        almacen_destino_id=almacen_destino_id,
        notas=order_notes,
    )

    for detail, pending_quantity in pending_details:
        material = get_material_for_company(db, empresa.id, detail.material_id)
        unit_cost = Decimal(material.costo_unitario or ZERO)
        line_subtotal = pending_quantity * unit_cost
        db.add(
            OrdenCompraDetalle(
                orden_compra_id=order.id,
                material_id=detail.material_id,
                cantidad=pending_quantity,
                cantidad_recibida=ZERO,
                costo_unitario=unit_cost,
                subtotal_linea=line_subtotal,
                total_linea=line_subtotal,
            )
        )

    db.flush()
    recompute_purchase_order_totals(db, order)
    requisition.orden_compra_id = order.id
    requisition.estatus = "convertida_a_oc"

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.create_purchase_order",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={
            "orden_compra_id": order.id,
            "orden_compra_folio": order.folio,
            "proveedor_id": proveedor_id,
            "almacen_destino_id": almacen_destino_id,
            "estatus_requisicion": requisition.estatus,
        },
    )
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.purchase_order.create_from_requisition",
        entity_name="orden_compra",
        entity_id=order.id,
        ip_address=ip_address,
        metadata_json={"requisicion_id": requisition.id, "requisicion_folio": requisition.folio},
    )
    db.flush()
    db.refresh(requisition)
    db.refresh(order)
    return serialize_purchase_order_response(db, order)


def update_purchase_order(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    order_id: str,
    folio: str | None,
    proveedor_id: str | None,
    almacen_destino_id: str | None,
    notas: str | None,
    ip_address: str | None,
) -> PurchaseOrderResponse:
    order = get_purchase_order_for_company(db, empresa.id, order_id, for_update=True)
    ensure_purchase_order_is_draft(order)

    if folio is not None:
        next_folio = normalize_optional_folio(folio, "OC")
        ensure_unique_purchase_order_folio(db, empresa.id, next_folio, order.id)
        order.folio = next_folio
    if proveedor_id is not None:
        supplier = ensure_active_supplier(db, empresa.id, proveedor_id)
        order.proveedor_id = supplier.id
        apply_supplier_snapshot(order, supplier)
    if almacen_destino_id is not None:
        order.almacen_destino_id = ensure_active_destination_warehouse(db, empresa.id, almacen_destino_id).id
    if notas is not None:
        order.notas = normalize_optional_text(notas)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.purchase_order.update",
        entity_name="orden_compra",
        entity_id=order.id,
        ip_address=ip_address,
        metadata_json={"folio": order.folio},
    )
    db.flush()
    db.refresh(order)
    return serialize_purchase_order_response(db, order)


def add_purchase_order_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    order_id: str,
    material_id: str,
    cantidad: Decimal,
    costo_unitario: Decimal,
    ip_address: str | None,
) -> PurchaseOrderResponse:
    order = get_purchase_order_for_company(db, empresa.id, order_id, for_update=True)
    ensure_purchase_order_is_draft(order)
    material = get_material_for_company(db, empresa.id, material_id)

    quantity = Decimal(cantidad)
    unit_cost = Decimal(costo_unitario)
    subtotal_line = quantity * unit_cost

    detail = OrdenCompraDetalle(
        orden_compra_id=order.id,
        material_id=material.id,
        cantidad=quantity,
        cantidad_recibida=ZERO,
        costo_unitario=unit_cost,
        subtotal_linea=subtotal_line,
        total_linea=subtotal_line,
    )
    db.add(detail)
    db.flush()
    recompute_purchase_order_totals(db, order)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.purchase_order.detail.create",
        entity_name="orden_compra",
        entity_id=order.id,
        ip_address=ip_address,
        metadata_json={"material_id": material.id, "cantidad": str(quantity)},
    )
    db.flush()
    return serialize_purchase_order_response(db, order)


def update_purchase_order_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    order_id: str,
    detail_id: str,
    material_id: str | None,
    cantidad: Decimal | None,
    costo_unitario: Decimal | None,
    ip_address: str | None,
) -> PurchaseOrderResponse:
    order = get_purchase_order_for_company(db, empresa.id, order_id, for_update=True)
    ensure_purchase_order_is_draft(order)
    detail = get_purchase_order_detail(db, order.id, detail_id)

    if material_id is not None:
        detail.material_id = get_material_for_company(db, empresa.id, material_id).id
    if cantidad is not None:
        detail.cantidad = Decimal(cantidad)
    if costo_unitario is not None:
        detail.costo_unitario = Decimal(costo_unitario)
    detail.subtotal_linea = Decimal(detail.cantidad) * Decimal(detail.costo_unitario)
    detail.total_linea = detail.subtotal_linea

    db.flush()
    recompute_purchase_order_totals(db, order)
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.purchase_order.detail.update",
        entity_name="orden_compra",
        entity_id=order.id,
        ip_address=ip_address,
        metadata_json={"detail_id": detail.id},
    )
    db.flush()
    return serialize_purchase_order_response(db, order)


def delete_purchase_order_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    order_id: str,
    detail_id: str,
    ip_address: str | None,
) -> PurchaseOrderResponse:
    order = get_purchase_order_for_company(db, empresa.id, order_id, for_update=True)
    ensure_purchase_order_is_draft(order)
    detail = get_purchase_order_detail(db, order.id, detail_id)
    db.delete(detail)
    db.flush()
    recompute_purchase_order_totals(db, order)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.purchase_order.detail.delete",
        entity_name="orden_compra",
        entity_id=order.id,
        ip_address=ip_address,
        metadata_json={"detail_id": detail_id},
    )
    db.flush()
    return serialize_purchase_order_response(db, order)


def issue_purchase_order(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    order_id: str,
    ip_address: str | None,
) -> PurchaseOrderResponse:
    order = get_purchase_order_for_company(db, empresa.id, order_id, for_update=True)
    ensure_purchase_order_is_draft(order)

    details_count = db.scalar(
        select(func.count(OrdenCompraDetalle.id)).where(OrdenCompraDetalle.orden_compra_id == order.id)
    ) or 0
    if details_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La orden de compra necesita al menos un detalle.",
        )

    supplier = ensure_active_supplier(db, empresa.id, order.proveedor_id)
    ensure_active_destination_warehouse(db, empresa.id, order.almacen_destino_id)
    apply_supplier_snapshot(order, supplier)
    order.estatus = "emitida"
    if order.fecha_emitida is None:
        order.fecha_emitida = datetime.now(timezone.utc)
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.purchase_order.issue",
        entity_name="orden_compra",
        entity_id=order.id,
        ip_address=ip_address,
        metadata_json={"estatus": order.estatus},
    )
    db.flush()
    db.refresh(order)
    return serialize_purchase_order_response(db, order)


def cancel_purchase_order(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    order_id: str,
    ip_address: str | None,
) -> PurchaseOrderResponse:
    order = get_purchase_order_for_company(db, empresa.id, order_id, for_update=True)
    if order.estatus == "cancelada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La orden de compra ya esta cancelada.",
        )
    if order.estatus not in {"borrador", "emitida"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden cancelar ordenes en borrador o emitidas sin recepcion.",
        )

    received_lines = db.scalar(
        select(func.count(OrdenCompraDetalle.id)).where(
            OrdenCompraDetalle.orden_compra_id == order.id,
            OrdenCompraDetalle.cantidad_recibida > ZERO,
        )
    ) or 0
    if received_lines > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede cancelar una orden que ya tiene recepciones aplicadas.",
        )

    order.estatus = "cancelada"
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.purchase_order.cancel",
        entity_name="orden_compra",
        entity_id=order.id,
        ip_address=ip_address,
        metadata_json={"estatus": order.estatus},
    )
    db.flush()
    db.refresh(order)
    return serialize_purchase_order_response(db, order)


def build_purchase_order_pending_items(details: list[OrdenCompraDetalle]) -> list[PurchaseOrderPendingQuantityItem]:
    return [
        PurchaseOrderPendingQuantityItem(
            detail_id=detail.id,
            material_id=detail.material_id,
            material_sku=detail.material.sku,
            material_nombre=detail.material.nombre,
            cantidad_ordenada=Decimal(detail.cantidad or ZERO),
            cantidad_recibida=Decimal(detail.cantidad_recibida or ZERO),
            cantidad_pendiente=max(Decimal(detail.cantidad or ZERO) - Decimal(detail.cantidad_recibida or ZERO), ZERO),
            estado_linea=get_purchase_order_line_state(detail),
        )
        for detail in details
    ]


def receive_purchase_order(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    order_id: str,
    items: list,
    almacen_id: str,
    documento_referencia: str | None,
    notas_recepcion: str | None,
    ip_address: str | None,
) -> PurchaseOrderReceiveResponse:
    order = get_purchase_order_for_company(db, empresa.id, order_id, for_update=True)
    if order.estatus not in {"emitida", "recibida_parcial"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La orden de compra no permite recepcion.",
        )

    warehouse = ensure_active_destination_warehouse(db, empresa.id, almacen_id)
    if warehouse.id != order.almacen_destino_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La recepcion debe registrarse en el almacen destino de la orden.",
        )
    detail_map = {
        detail.id: detail
        for detail in db.scalars(
            select(OrdenCompraDetalle).where(OrdenCompraDetalle.orden_compra_id == order.id).with_for_update()
        ).all()
    }
    if not detail_map:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La orden de compra necesita al menos un detalle.",
        )

    receipt = OrdenCompraRecepcion(
        empresa_id=empresa.id,
        orden_compra_id=order.id,
        almacen_id=warehouse.id,
        documento_referencia=normalize_optional_text(documento_referencia),
        notas=normalize_optional_text(notas_recepcion),
        recibido_por_user_id=user.id,
    )
    db.add(receipt)
    db.flush()

    received_at = datetime.now(timezone.utc)
    applied_any = False
    received_lines_count = 0
    for item in items:
        detail = detail_map.get(item.detail_id)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Detalle de orden de compra no encontrado.",
            )

        receive_quantity = Decimal(item.resolved_cantidad)
        if receive_quantity <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad recibida debe ser mayor a cero.",
            )
        remaining = Decimal(detail.cantidad) - Decimal(detail.cantidad_recibida)
        if receive_quantity > remaining:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La cantidad recibida supera la cantidad pendiente.",
            )

        movement_notes = "\n".join(
            part
            for part in [
                f"Recepcion de orden {order.folio}",
                normalize_optional_text(notas_recepcion),
            ]
            if part
        )
        movement = apply_inventory_movement(
            db,
            user=user,
            empresa=empresa,
            almacen_id=warehouse.id,
            material_id=detail.material_id,
            tipo="entrada",
            cantidad=receive_quantity,
            cantidad_nueva=None,
            referencia_tipo="purchase_order_receive",
            referencia_id=order.id,
            notas=movement_notes or None,
            ip_address=ip_address,
            grupo_referencia=receipt.id,
            motivo="Recepcion de compra",
            recibido_por=user.full_name,
            documento_referencia=documento_referencia,
            costo_unitario=detail.costo_unitario,
        )
        detail.cantidad_recibida = Decimal(detail.cantidad_recibida) + receive_quantity
        detail.ultima_recepcion_at = received_at
        db.add(
            OrdenCompraRecepcionDetalle(
                recepcion_id=receipt.id,
                orden_compra_detalle_id=detail.id,
                material_id=detail.material_id,
                cantidad_recibida=receive_quantity,
                costo_unitario_snapshot=detail.costo_unitario,
                movimiento_inventario_id=movement.id,
            )
        )
        applied_any = True
        received_lines_count += 1

    if not applied_any:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cantidad recibida debe ser mayor a cero.",
        )

    details = list(detail_map.values())
    order.fecha_ultima_recepcion = received_at
    order.documento_referencia = normalize_optional_text(documento_referencia)
    order.notas_recepcion = normalize_optional_text(notas_recepcion)
    order.recibido_por_user_id = user.id
    if all(Decimal(item.cantidad_recibida) >= Decimal(item.cantidad) for item in details):
        order.estatus = "recibida"
    else:
        order.estatus = "recibida_parcial"

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.purchase_order.receive",
        entity_name="orden_compra",
        entity_id=order.id,
        ip_address=ip_address,
        metadata_json={
            "estatus": order.estatus,
            "recepcion_id": receipt.id,
            "documento_referencia": receipt.documento_referencia,
            "lineas_recibidas": received_lines_count,
        },
    )
    db.flush()
    db.refresh(order)
    receipts = list_purchase_order_receipts(db, empresa.id, order.id)
    current_receipt = next((item for item in receipts if item.id == receipt.id), None)
    order_response = serialize_purchase_order_response(db, order)
    pending_items = build_purchase_order_pending_items(details)
    return PurchaseOrderReceiveResponse(
        order=order_response,
        receipt=current_receipt
        or PurchaseOrderReceiptItem(
            id=receipt.id,
            empresa_id=receipt.empresa_id,
            orden_compra_id=receipt.orden_compra_id,
            almacen_id=receipt.almacen_id,
            almacen_nombre=warehouse.nombre,
            documento_referencia=receipt.documento_referencia,
            notas=receipt.notas,
            recibido_por_user_id=receipt.recibido_por_user_id,
            recibido_por_nombre=user.full_name,
            created_at=receipt.created_at,
            updated_at=receipt.updated_at,
            items=[],
            movements=[],
        ),
        movements=current_receipt.movements if current_receipt else [],
        pending_items=pending_items,
        cantidad_total_recibida=order_response.cantidad_total_recibida,
        cantidad_total_pendiente=order_response.cantidad_total_pendiente,
    )


def get_purchase_order_receipts_response(db: Session, empresa_id: str, order_id: str) -> list[PurchaseOrderReceiptItem]:
    get_purchase_order_for_company(db, empresa_id, order_id)
    return list_purchase_order_receipts(db, empresa_id, order_id)


def get_purchase_report_pending(db: Session, empresa_id: str) -> PurchaseOrderPendingReportResponse:
    open_statuses = {"emitida", "recibida_parcial"}
    orders = db.scalars(
        select(OrdenCompra)
        .where(
            OrdenCompra.empresa_id == empresa_id,
            OrdenCompra.estatus.in_(open_statuses),
        )
        .order_by(desc(OrdenCompra.fecha_emitida), desc(OrdenCompra.created_at), desc(OrdenCompra.id))
    ).all()
    if not orders:
        return PurchaseOrderPendingReportResponse(
            kpis=PurchaseOrderPendingReportKpis(
                ordenes_pendientes=0,
                ordenes_parciales=0,
                materiales_pendientes=0,
                monto_pendiente=ZERO,
            ),
            ordenes=[],
            materiales=[],
            proveedores=[],
        )

    order_ids = [order.id for order in orders]
    details = db.scalars(
        select(OrdenCompraDetalle)
        .where(OrdenCompraDetalle.orden_compra_id.in_(order_ids))
        .order_by(OrdenCompraDetalle.orden_compra_id.asc(), OrdenCompraDetalle.id.asc())
    ).all()
    details_by_order: dict[str, list[OrdenCompraDetalle]] = {order_id: [] for order_id in order_ids}
    for detail in details:
        details_by_order.setdefault(detail.orden_compra_id, []).append(detail)

    material_rows: list[PurchaseOrderPendingReportMaterialItem] = []
    supplier_map: dict[str, PurchaseOrderPendingReportSupplierItem] = {}
    order_rows: list[PurchaseOrderPendingReportOrderItem] = []
    total_pending_amount = ZERO
    pending_material_lines = 0
    partial_orders = 0
    pending_orders = 0

    for order in orders:
        if order.estatus == "emitida":
            pending_orders += 1
        if order.estatus == "recibida_parcial":
            partial_orders += 1

        pending_quantity_total = ZERO
        pending_amount_total = ZERO
        for detail in details_by_order.get(order.id, []):
            pending_quantity = max(Decimal(detail.cantidad or ZERO) - Decimal(detail.cantidad_recibida or ZERO), ZERO)
            if pending_quantity <= ZERO:
                continue
            pending_material_lines += 1
            pending_amount = pending_quantity * Decimal(detail.costo_unitario or ZERO)
            pending_quantity_total += pending_quantity
            pending_amount_total += pending_amount
            material_rows.append(
                PurchaseOrderPendingReportMaterialItem(
                    material_id=detail.material_id,
                    material=detail.material.nombre,
                    sku=detail.material.sku,
                    cantidad_pendiente=pending_quantity,
                    proveedor=order.proveedor.nombre,
                    ordenes_abiertas=1,
                )
            )

        total_pending_amount += pending_amount_total
        order_rows.append(
            PurchaseOrderPendingReportOrderItem(
                id=order.id,
                folio=order.folio,
                proveedor=order.proveedor.nombre,
                estatus=order.estatus,
                fecha_emitida=order.fecha_emitida,
                fecha_esperada=order.fecha_esperada,
                total=order.total,
                pendiente=pending_amount_total,
                cantidad_pendiente=pending_quantity_total,
            )
        )
        supplier_item = supplier_map.get(order.proveedor_id)
        if supplier_item is None:
            supplier_map[order.proveedor_id] = PurchaseOrderPendingReportSupplierItem(
                proveedor_id=order.proveedor_id,
                proveedor=order.proveedor.nombre,
                ordenes_abiertas=1,
                monto_pendiente=pending_amount_total,
            )
        else:
            supplier_item.ordenes_abiertas += 1
            supplier_item.monto_pendiente += pending_amount_total

    material_aggregate: dict[tuple[str, str], PurchaseOrderPendingReportMaterialItem] = {}
    for item in material_rows:
        key = (item.material_id, item.proveedor)
        existing = material_aggregate.get(key)
        if existing is None:
            material_aggregate[key] = item
        else:
            existing.cantidad_pendiente += item.cantidad_pendiente
            existing.ordenes_abiertas += item.ordenes_abiertas

    return PurchaseOrderPendingReportResponse(
        kpis=PurchaseOrderPendingReportKpis(
            ordenes_pendientes=pending_orders,
            ordenes_parciales=partial_orders,
            materiales_pendientes=pending_material_lines,
            monto_pendiente=total_pending_amount,
        ),
        ordenes=order_rows,
        materiales=sorted(
            material_aggregate.values(),
            key=lambda item: (Decimal(item.cantidad_pendiente), item.material.lower()),
            reverse=True,
        ),
        proveedores=sorted(
            supplier_map.values(),
            key=lambda item: (Decimal(item.monto_pendiente), item.proveedor.lower()),
            reverse=True,
        ),
    )
