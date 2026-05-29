from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Empresa,
    OrdenCompra,
    OrdenCompraDetalle,
    Proveedor,
    Requisicion,
    RequisicionDetalle,
    Usuario,
)
from app.models.inventory import Existencia, Material, MovimientoInventario
from app.schemas.procurement import (
    PurchaseOrderDetailItem,
    PurchaseOrderItem,
    PurchaseOrderMovementTraceItem,
    PurchaseOrderResponse,
    RequisitionDetailItem,
    RequisitionItem,
    RequisitionResponse,
    SupplierItem,
)
from app.services.inventory import (
    ZERO,
    apply_inventory_movement,
    apply_text_search,
    count_rows,
    get_material_for_company,
    get_warehouse_for_company,
    normalize_code,
    normalize_optional_text,
    normalize_required_text,
)


def generate_procurement_folio(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = str(uuid4())[:6].upper()
    return f"{prefix}-{timestamp}-{suffix}"


def normalize_optional_folio(value: str | None, prefix: str) -> str:
    if value is None:
        return generate_procurement_folio(prefix)
    cleaned = value.strip()
    if not cleaned:
        return generate_procurement_folio(prefix)
    return normalize_code(cleaned, "Folio")


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
        razon_social=supplier.razon_social,
        rfc=supplier.rfc,
        contacto_nombre=supplier.contacto_nombre,
        correo=supplier.correo,
        telefono=supplier.telefono,
        direccion=supplier.direccion,
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
    )
    if activo is not None:
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
    razon_social: str | None,
    rfc: str | None,
    contacto_nombre: str | None,
    correo: str | None,
    telefono: str | None,
    direccion: str | None,
    notas: str | None,
    activo: bool,
    ip_address: str | None,
) -> SupplierItem:
    supplier = Proveedor(
        empresa_id=empresa.id,
        nombre=normalize_required_text(nombre, "Nombre"),
        razon_social=normalize_optional_text(razon_social),
        rfc=normalize_optional_text(rfc.upper() if rfc else None),
        contacto_nombre=normalize_optional_text(contacto_nombre),
        correo=normalize_optional_text(correo),
        telefono=normalize_optional_text(telefono),
        direccion=normalize_optional_text(direccion),
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
        metadata_json={"nombre": supplier.nombre, "rfc": supplier.rfc, "activo": supplier.activo},
    )
    return serialize_supplier(supplier)


def update_supplier(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    supplier_id: str,
    nombre: str | None,
    razon_social: str | None,
    rfc: str | None,
    contacto_nombre: str | None,
    correo: str | None,
    telefono: str | None,
    direccion: str | None,
    notas: str | None,
    activo: bool | None,
    ip_address: str | None,
) -> SupplierItem:
    supplier = get_supplier_for_company(db, empresa.id, supplier_id)
    if nombre is not None:
        supplier.nombre = normalize_required_text(nombre, "Nombre")
    if razon_social is not None:
        supplier.razon_social = normalize_optional_text(razon_social)
    if rfc is not None:
        supplier.rfc = normalize_optional_text(rfc.upper())
    if contacto_nombre is not None:
        supplier.contacto_nombre = normalize_optional_text(contacto_nombre)
    if correo is not None:
        supplier.correo = normalize_optional_text(correo)
    if telefono is not None:
        supplier.telefono = normalize_optional_text(telefono)
    if direccion is not None:
        supplier.direccion = normalize_optional_text(direccion)
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
        metadata_json={"nombre": supplier.nombre, "rfc": supplier.rfc, "activo": supplier.activo},
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


def serialize_requisition_detail(detail: RequisicionDetalle) -> RequisitionDetailItem:
    return RequisitionDetailItem(
        id=detail.id,
        requisicion_id=detail.requisicion_id,
        material_id=detail.material_id,
        material_sku=detail.material.sku,
        material_nombre=detail.material.nombre,
        material_unidad=detail.material.unidad,
        cantidad=detail.cantidad,
        notas=detail.notas,
    )


def build_requisition_item(
    requisition: Requisicion,
    details_count: int,
    *,
    proveedor_sugerido_nombre: str | None = None,
    orden_compra_folio: str | None = None,
) -> RequisitionItem:
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
        estatus=requisition.estatus,
        notas=requisition.notas,
        created_at=requisition.created_at,
        updated_at=requisition.updated_at,
        details_count=details_count,
    )


def serialize_requisition_response(db: Session, requisition: Requisicion) -> RequisitionResponse:
    details = db.scalars(
        select(RequisicionDetalle)
        .where(RequisicionDetalle.requisicion_id == requisition.id)
        .order_by(RequisicionDetalle.id.asc())
    ).all()
    summary = build_requisition_item(
        requisition,
        len(details),
        proveedor_sugerido_nombre=requisition.proveedor_sugerido.nombre if requisition.proveedor_sugerido else None,
        orden_compra_folio=requisition.orden_compra.folio if requisition.orden_compra else None,
    )
    return RequisitionResponse(
        **summary.model_dump(),
        details=[serialize_requisition_detail(item) for item in details],
    )


def list_requisitions(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    estatus: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[RequisitionItem]]:
    id_query = select(Requisicion.id).where(Requisicion.empresa_id == empresa_id)
    id_query = apply_text_search(id_query, q, Requisicion.folio, Requisicion.notas)
    if estatus:
        id_query = id_query.where(Requisicion.estatus == estatus)

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
            proveedor_sugerido_nombre=proveedor_sugerido_nombre,
            orden_compra_folio=orden_compra_folio,
        )
        for item, proveedor_sugerido_nombre, orden_compra_folio, detail_count in rows
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
            Requisicion.estatus.in_(["borrador", "enviada", "aprobada"]),
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
        return max(stock_minimo - stock_total, Decimal("1"))
    if stock_total <= ZERO:
        return Decimal("1")
    return Decimal("1")


def create_requisition(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    folio: str | None,
    notas: str | None,
    proveedor_sugerido_id: str | None = None,
    ip_address: str | None,
) -> RequisitionResponse:
    next_folio = normalize_optional_folio(folio, "REQ")
    ensure_unique_requisition_folio(db, empresa.id, next_folio)

    requisition = Requisicion(
        empresa_id=empresa.id,
        folio=next_folio,
        solicitante_user_id=user.id,
        proveedor_sugerido_id=proveedor_sugerido_id,
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
        metadata_json={"folio": requisition.folio},
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

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.requisition.update",
        entity_name="requisicion",
        entity_id=requisition.id,
        ip_address=ip_address,
        metadata_json={"folio": requisition.folio},
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
    material: Material,
    user: Usuario | None,
) -> PurchaseOrderMovementTraceItem:
    return PurchaseOrderMovementTraceItem(
        id=movement.id,
        created_at=movement.created_at,
        tipo=movement.tipo,
        material_id=movement.material_id,
        material_sku=material.sku,
        material_nombre=material.nombre,
        cantidad=movement.cantidad,
        documento_referencia=movement.documento_referencia,
        notas=movement.notas,
        recibido_por=movement.recibido_por,
        created_by_nombre=user.full_name if user else None,
    )


def list_purchase_order_movements(db: Session, empresa_id: str, order_id: str) -> list[PurchaseOrderMovementTraceItem]:
    rows = db.execute(
        select(MovimientoInventario, Material, Usuario)
        .join(Material, MovimientoInventario.material_id == Material.id)
        .join(Usuario, MovimientoInventario.created_by == Usuario.id)
        .where(
            MovimientoInventario.empresa_id == empresa_id,
            MovimientoInventario.referencia_tipo == "purchase_order_receive",
            MovimientoInventario.referencia_id == order_id,
        )
        .order_by(desc(MovimientoInventario.created_at), desc(MovimientoInventario.id))
    ).all()
    return [build_purchase_order_movement_trace_item(movement, material, user) for movement, material, user in rows]


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
    )


def build_purchase_order_item(
    order: OrdenCompra,
    details_count: int,
    *,
    cantidad_total_ordenada: Decimal = ZERO,
    cantidad_total_recibida: Decimal = ZERO,
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
        notas=order.notas,
        created_at=order.created_at,
        updated_at=order.updated_at,
        details_count=details_count,
        cantidad_renglones=details_count,
        cantidad_total_ordenada=Decimal(cantidad_total_ordenada),
        cantidad_total_recibida=Decimal(cantidad_total_recibida),
        cantidad_total_pendiente=cantidad_total_pendiente,
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
    requisition = get_linked_purchase_requisition(order)
    summary = build_purchase_order_item(
        order,
        len(details),
        cantidad_total_ordenada=total_ordenada,
        cantidad_total_recibida=total_recibida,
        requisicion_id=requisition.id if requisition else None,
        requisicion_folio=requisition.folio if requisition else None,
    )
    return PurchaseOrderResponse(
        **summary.model_dump(),
        details=[serialize_purchase_order_detail(item) for item in details],
        movements=list_purchase_order_movements(db, order.empresa_id, order.id),
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
    id_query = select(OrdenCompra.id).where(OrdenCompra.empresa_id == empresa_id)
    id_query = apply_text_search(id_query, q, OrdenCompra.folio, OrdenCompra.notas)
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
        )
        .where(OrdenCompraDetalle.orden_compra_id.in_(page_ids))
        .group_by(OrdenCompraDetalle.orden_compra_id)
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
            requisition_subquery.c.requisicion_id,
            requisition_subquery.c.requisicion_folio,
        )
        .outerjoin(details_count_subquery, details_count_subquery.c.orden_compra_id == OrdenCompra.id)
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
            requisicion_id=requisicion_id,
            requisicion_folio=requisicion_folio,
        )
        for item, detail_count, ordered_quantity, received_quantity, requisicion_id, requisicion_folio in rows
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
    if requisition.estatus != "aprobada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo las requisiciones aprobadas pueden convertirse en orden de compra.",
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

    for detail in details:
        material = get_material_for_company(db, empresa.id, detail.material_id)
        unit_cost = Decimal(material.costo_unitario or ZERO)
        line_subtotal = Decimal(detail.cantidad) * unit_cost
        db.add(
            OrdenCompraDetalle(
                orden_compra_id=order.id,
                material_id=detail.material_id,
                cantidad=detail.cantidad,
                cantidad_recibida=ZERO,
                costo_unitario=unit_cost,
                subtotal_linea=line_subtotal,
                total_linea=line_subtotal,
            )
        )

    db.flush()
    recompute_purchase_order_totals(db, order)
    requisition.orden_compra_id = order.id

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
        order.proveedor_id = ensure_active_supplier(db, empresa.id, proveedor_id).id
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

    ensure_active_supplier(db, empresa.id, order.proveedor_id)
    ensure_active_destination_warehouse(db, empresa.id, order.almacen_destino_id)
    order.estatus = "emitida"
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


def receive_purchase_order(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    order_id: str,
    items: list,
    documento_referencia: str | None,
    notas_recepcion: str | None,
    ip_address: str | None,
) -> PurchaseOrderResponse:
    order = get_purchase_order_for_company(db, empresa.id, order_id, for_update=True)
    if order.estatus not in {"emitida", "recibida_parcial"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La orden de compra no puede recibirse en su estatus actual.",
        )

    warehouse = ensure_active_destination_warehouse(db, empresa.id, order.almacen_destino_id)
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

    applied_any = False
    for item in items:
        detail = detail_map.get(item.detail_id)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Detalle de orden de compra no encontrado.",
            )

        receive_quantity = Decimal(item.cantidad)
        remaining = Decimal(detail.cantidad) - Decimal(detail.cantidad_recibida)
        if receive_quantity > remaining:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La cantidad recibida excede lo pendiente por recibir.",
            )
        if receive_quantity <= ZERO:
            continue

        movement_notes = "\n".join(
            part
            for part in [
                f"Recepcion de orden {order.folio}",
                normalize_optional_text(notas_recepcion),
            ]
            if part
        )
        apply_inventory_movement(
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
            motivo="Recepcion de compra",
            recibido_por=user.full_name,
            documento_referencia=documento_referencia,
            costo_unitario=detail.costo_unitario,
        )
        detail.cantidad_recibida = Decimal(detail.cantidad_recibida) + receive_quantity
        applied_any = True

    if not applied_any:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se recibio ninguna cantidad valida.",
        )

    details = list(detail_map.values())
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
        metadata_json={"estatus": order.estatus},
    )
    db.flush()
    db.refresh(order)
    return serialize_purchase_order_response(db, order)
