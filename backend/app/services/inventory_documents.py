from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, aliased

from app.models import AuditLog, Empresa, Usuario
from app.models.inventory import (
    Almacen,
    ConteoInventario,
    ConteoInventarioDetalle,
    Existencia,
    Material,
    TransferenciaInventario,
    TransferenciaInventarioDetalle,
)
from app.schemas.inventory import (
    CountDetailItem,
    CountItem,
    CountResponse,
    TransferDetailItem,
    TransferItem,
    TransferResponse,
)
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
)


def generate_inventory_folio(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = str(uuid4())[:6].upper()
    return f"{prefix}-{timestamp}-{suffix}"


def normalize_optional_folio(value: str | None, prefix: str) -> str:
    if value is None:
        return generate_inventory_folio(prefix)
    cleaned = value.strip()
    if not cleaned:
        return generate_inventory_folio(prefix)
    return normalize_code(cleaned, "Folio")


def get_transfer_for_company(
    db: Session,
    empresa_id: str,
    transfer_id: str,
    *,
    for_update: bool = False,
) -> TransferenciaInventario:
    query = select(TransferenciaInventario).where(
        TransferenciaInventario.id == transfer_id,
        TransferenciaInventario.empresa_id == empresa_id,
    )
    if for_update:
        query = query.with_for_update()
    transfer = db.scalar(query)
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transferencia no encontrada.")
    return transfer


def get_count_for_company(
    db: Session,
    empresa_id: str,
    count_id: str,
    *,
    for_update: bool = False,
) -> ConteoInventario:
    query = select(ConteoInventario).where(
        ConteoInventario.id == count_id,
        ConteoInventario.empresa_id == empresa_id,
    )
    if for_update:
        query = query.with_for_update()
    count = db.scalar(query)
    if not count:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conteo no encontrado.")
    return count


def ensure_transfer_is_draft(transfer: TransferenciaInventario) -> None:
    if transfer.estatus != "borrador":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden modificar transferencias en borrador.",
        )


def ensure_count_is_draft(count: ConteoInventario) -> None:
    if count.estatus != "borrador":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden modificar conteos en borrador.",
        )


def get_transfer_detail(
    db: Session,
    transfer_id: str,
    detail_id: str,
) -> TransferenciaInventarioDetalle:
    detail = db.scalar(
        select(TransferenciaInventarioDetalle).where(
            TransferenciaInventarioDetalle.id == detail_id,
            TransferenciaInventarioDetalle.transferencia_id == transfer_id,
        )
    )
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detalle de transferencia no encontrado.")
    return detail


def get_count_detail(
    db: Session,
    count_id: str,
    detail_id: str,
) -> ConteoInventarioDetalle:
    detail = db.scalar(
        select(ConteoInventarioDetalle).where(
            ConteoInventarioDetalle.id == detail_id,
            ConteoInventarioDetalle.conteo_id == count_id,
        )
    )
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detalle de conteo no encontrado.")
    return detail


def get_current_stock_snapshot(db: Session, empresa_id: str, almacen_id: str, material_id: str) -> Decimal:
    quantity = db.scalar(
        select(Existencia.cantidad).where(
            Existencia.empresa_id == empresa_id,
            Existencia.almacen_id == almacen_id,
            Existencia.material_id == material_id,
        )
    )
    return Decimal(quantity or ZERO)


def create_audit_log(
    db: Session,
    *,
    empresa_id: str,
    usuario_id: str,
    action: str,
    entity_name: str,
    entity_id: str | None,
    ip_address: str | None,
    metadata_json: dict | None = None,
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


def validate_transfer_header(
    db: Session,
    empresa_id: str,
    *,
    almacen_origen_id: str,
    almacen_destino_id: str,
) -> tuple:
    if almacen_origen_id == almacen_destino_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El almacén origen y destino deben ser distintos.",
        )
    origin = get_warehouse_for_company(db, empresa_id, almacen_origen_id)
    destination = get_warehouse_for_company(db, empresa_id, almacen_destino_id)
    return origin, destination


def ensure_unique_transfer_folio(
    db: Session,
    empresa_id: str,
    folio: str,
    *,
    exclude_id: str | None = None,
) -> None:
    query = select(TransferenciaInventario.id).where(
        TransferenciaInventario.empresa_id == empresa_id,
        TransferenciaInventario.folio == folio,
    )
    if exclude_id:
        query = query.where(TransferenciaInventario.id != exclude_id)
    if db.scalar(query):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El folio de transferencia ya existe en esta empresa.",
        )


def ensure_unique_count_folio(
    db: Session,
    empresa_id: str,
    folio: str,
    *,
    exclude_id: str | None = None,
) -> None:
    query = select(ConteoInventario.id).where(
        ConteoInventario.empresa_id == empresa_id,
        ConteoInventario.folio == folio,
    )
    if exclude_id:
        query = query.where(ConteoInventario.id != exclude_id)
    if db.scalar(query):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El folio de conteo ya existe en esta empresa.",
        )


def serialize_transfer_detail(detail: TransferenciaInventarioDetalle, material: Material) -> TransferDetailItem:
    return TransferDetailItem(
        id=detail.id,
        transferencia_id=detail.transferencia_id,
        material_id=material.id,
        material_sku=material.sku,
        material_nombre=material.nombre,
        material_unidad=material.unidad,
        cantidad=detail.cantidad,
        costo_unitario_snapshot=detail.costo_unitario_snapshot,
    )


def serialize_count_detail(detail: ConteoInventarioDetalle, material: Material) -> CountDetailItem:
    return CountDetailItem(
        id=detail.id,
        conteo_id=detail.conteo_id,
        material_id=material.id,
        material_sku=material.sku,
        material_nombre=material.nombre,
        material_unidad=material.unidad,
        cantidad_sistema_snapshot=detail.cantidad_sistema_snapshot,
        cantidad_fisica=detail.cantidad_fisica,
        diferencia=detail.diferencia,
        ajuste_movimiento_id=detail.ajuste_movimiento_id,
    )


def build_transfer_item(
    transfer: TransferenciaInventario,
    origin_name: str,
    destination_name: str,
    details_count: int,
) -> TransferItem:
    return TransferItem(
        id=transfer.id,
        empresa_id=transfer.empresa_id,
        folio=transfer.folio,
        almacen_origen_id=transfer.almacen_origen_id,
        almacen_origen_nombre=origin_name,
        almacen_destino_id=transfer.almacen_destino_id,
        almacen_destino_nombre=destination_name,
        estatus=transfer.estatus,
        notas=transfer.notas,
        created_by_user_id=transfer.created_by_user_id,
        confirmed_by_user_id=transfer.confirmed_by_user_id,
        cancelled_by_user_id=transfer.cancelled_by_user_id,
        created_at=transfer.created_at,
        confirmed_at=transfer.confirmed_at,
        cancelled_at=transfer.cancelled_at,
        detalles_count=details_count,
    )


def build_count_item(count: ConteoInventario, warehouse_name: str, details_count: int) -> CountItem:
    return CountItem(
        id=count.id,
        empresa_id=count.empresa_id,
        almacen_id=count.almacen_id,
        almacen_nombre=warehouse_name,
        folio=count.folio,
        estatus=count.estatus,
        notas=count.notas,
        created_by_user_id=count.created_by_user_id,
        applied_by_user_id=count.applied_by_user_id,
        cancelled_by_user_id=count.cancelled_by_user_id,
        created_at=count.created_at,
        applied_at=count.applied_at,
        cancelled_at=count.cancelled_at,
        detalles_count=details_count,
    )


def serialize_transfer_response(db: Session, transfer: TransferenciaInventario) -> TransferResponse:
    detail_rows = db.execute(
        select(TransferenciaInventarioDetalle, Material)
        .join(Material, TransferenciaInventarioDetalle.material_id == Material.id)
        .where(TransferenciaInventarioDetalle.transferencia_id == transfer.id)
        .order_by(Material.sku.asc(), Material.nombre.asc())
    ).all()
    details = [serialize_transfer_detail(detail, material) for detail, material in detail_rows]
    summary = build_transfer_item(
        transfer,
        transfer.almacen_origen.nombre,
        transfer.almacen_destino.nombre,
        len(details),
    )
    return TransferResponse(**summary.model_dump(), details=details)


def serialize_count_response(db: Session, count: ConteoInventario) -> CountResponse:
    detail_rows = db.execute(
        select(ConteoInventarioDetalle, Material)
        .join(Material, ConteoInventarioDetalle.material_id == Material.id)
        .where(ConteoInventarioDetalle.conteo_id == count.id)
        .order_by(Material.sku.asc(), Material.nombre.asc())
    ).all()
    details = [serialize_count_detail(detail, material) for detail, material in detail_rows]
    summary = build_count_item(count, count.almacen.nombre, len(details))
    return CountResponse(**summary.model_dump(), details=details)


def list_transfers(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    almacen_origen_id: str | None = None,
    almacen_destino_id: str | None = None,
    estatus: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[TransferItem]]:
    id_query = select(TransferenciaInventario.id).where(TransferenciaInventario.empresa_id == empresa_id)
    id_query = apply_text_search(id_query, q, TransferenciaInventario.folio, TransferenciaInventario.notas)

    if almacen_origen_id:
        id_query = id_query.where(TransferenciaInventario.almacen_origen_id == almacen_origen_id)
    if almacen_destino_id:
        id_query = id_query.where(TransferenciaInventario.almacen_destino_id == almacen_destino_id)
    if estatus:
        id_query = id_query.where(TransferenciaInventario.estatus == estatus)
    if fecha_desde:
        id_query = id_query.where(TransferenciaInventario.created_at >= fecha_desde)
    if fecha_hasta:
        id_query = id_query.where(TransferenciaInventario.created_at <= fecha_hasta)

    total = count_rows(db, id_query)
    page_ids = db.scalars(
        id_query.order_by(desc(TransferenciaInventario.created_at), desc(TransferenciaInventario.id))
        .offset(offset)
        .limit(limit)
    ).all()
    if not page_ids:
        return total, []

    origin_warehouse = aliased(Almacen)
    destination_warehouse = aliased(Almacen)
    detail_count_subquery = (
        select(
            TransferenciaInventarioDetalle.transferencia_id.label("transferencia_id"),
            func.count(TransferenciaInventarioDetalle.id).label("detail_count"),
        )
        .where(TransferenciaInventarioDetalle.transferencia_id.in_(page_ids))
        .group_by(TransferenciaInventarioDetalle.transferencia_id)
        .subquery()
    )
    rows = db.execute(
        select(
            TransferenciaInventario,
            origin_warehouse,
            destination_warehouse,
            func.coalesce(detail_count_subquery.c.detail_count, 0).label("detail_count"),
        )
        .join(origin_warehouse, TransferenciaInventario.almacen_origen_id == origin_warehouse.id)
        .join(destination_warehouse, TransferenciaInventario.almacen_destino_id == destination_warehouse.id)
        .outerjoin(
            detail_count_subquery,
            detail_count_subquery.c.transferencia_id == TransferenciaInventario.id,
        )
        .where(TransferenciaInventario.id.in_(page_ids))
    ).all()
    items_by_id = {
        transfer.id: build_transfer_item(transfer, origin_row.nombre, destination_row.nombre, int(details_count or 0))
        for transfer, origin_row, destination_row, details_count in rows
    }
    items = [
        items_by_id[transfer_id]
        for transfer_id in page_ids
        if transfer_id in items_by_id
    ]
    return total, items


def list_counts(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    almacen_id: str | None = None,
    estatus: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[CountItem]]:
    id_query = select(ConteoInventario.id).where(ConteoInventario.empresa_id == empresa_id)
    id_query = apply_text_search(id_query, q, ConteoInventario.folio, ConteoInventario.notas)

    if almacen_id:
        id_query = id_query.where(ConteoInventario.almacen_id == almacen_id)
    if estatus:
        id_query = id_query.where(ConteoInventario.estatus == estatus)
    if fecha_desde:
        id_query = id_query.where(ConteoInventario.created_at >= fecha_desde)
    if fecha_hasta:
        id_query = id_query.where(ConteoInventario.created_at <= fecha_hasta)

    total = count_rows(db, id_query)
    page_ids = db.scalars(
        id_query.order_by(desc(ConteoInventario.created_at), desc(ConteoInventario.id))
        .offset(offset)
        .limit(limit)
    ).all()
    if not page_ids:
        return total, []

    detail_count_subquery = (
        select(
            ConteoInventarioDetalle.conteo_id.label("conteo_id"),
            func.count(ConteoInventarioDetalle.id).label("detail_count"),
        )
        .where(ConteoInventarioDetalle.conteo_id.in_(page_ids))
        .group_by(ConteoInventarioDetalle.conteo_id)
        .subquery()
    )

    rows = db.execute(
        select(
            ConteoInventario,
            Almacen,
            func.coalesce(detail_count_subquery.c.detail_count, 0).label("detail_count"),
        )
        .join(Almacen, ConteoInventario.almacen_id == Almacen.id)
        .outerjoin(detail_count_subquery, detail_count_subquery.c.conteo_id == ConteoInventario.id)
        .where(ConteoInventario.id.in_(page_ids))
    ).all()
    items_by_id = {
        count.id: build_count_item(count, warehouse.nombre, int(details_count or 0))
        for count, warehouse, details_count in rows
    }
    items = [
        items_by_id[count_id]
        for count_id in page_ids
        if count_id in items_by_id
    ]
    return total, items


def create_transfer(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    folio: str | None,
    almacen_origen_id: str,
    almacen_destino_id: str,
    notas: str | None,
    ip_address: str | None,
) -> TransferResponse:
    origin, destination = validate_transfer_header(
        db,
        empresa.id,
        almacen_origen_id=almacen_origen_id,
        almacen_destino_id=almacen_destino_id,
    )
    transfer_folio = normalize_optional_folio(folio, "TR")
    ensure_unique_transfer_folio(db, empresa.id, transfer_folio)

    transfer = TransferenciaInventario(
        empresa_id=empresa.id,
        folio=transfer_folio,
        almacen_origen_id=origin.id,
        almacen_destino_id=destination.id,
        notas=normalize_optional_text(notas),
        created_by_user_id=user.id,
    )
    db.add(transfer)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.transfer.create",
        entity_name="transferencia_inventario",
        entity_id=transfer.id,
        ip_address=ip_address,
        metadata_json={"folio": transfer.folio, "estatus": transfer.estatus},
    )
    return serialize_transfer_response(db, transfer)


def update_transfer(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    transfer_id: str,
    folio: str | None,
    almacen_origen_id: str | None,
    almacen_destino_id: str | None,
    notas: str | None,
    ip_address: str | None,
) -> TransferResponse:
    transfer = get_transfer_for_company(db, empresa.id, transfer_id, for_update=True)
    ensure_transfer_is_draft(transfer)

    next_origin_id = almacen_origen_id or transfer.almacen_origen_id
    next_destination_id = almacen_destino_id or transfer.almacen_destino_id
    origin, destination = validate_transfer_header(
        db,
        empresa.id,
        almacen_origen_id=next_origin_id,
        almacen_destino_id=next_destination_id,
    )
    transfer.almacen_origen_id = origin.id
    transfer.almacen_destino_id = destination.id

    if folio is not None:
        normalized_folio = normalize_optional_folio(folio, "TR")
        ensure_unique_transfer_folio(db, empresa.id, normalized_folio, exclude_id=transfer.id)
        transfer.folio = normalized_folio
    if notas is not None:
        transfer.notas = normalize_optional_text(notas)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.transfer.update",
        entity_name="transferencia_inventario",
        entity_id=transfer.id,
        ip_address=ip_address,
        metadata_json={"folio": transfer.folio, "estatus": transfer.estatus},
    )
    db.flush()
    return serialize_transfer_response(db, transfer)


def add_transfer_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    transfer_id: str,
    material_id: str,
    cantidad: Decimal,
    costo_unitario_snapshot: Decimal | None,
    ip_address: str | None,
) -> TransferResponse:
    transfer = get_transfer_for_company(db, empresa.id, transfer_id, for_update=True)
    ensure_transfer_is_draft(transfer)
    material = get_material_for_company(db, empresa.id, material_id)

    existing = db.scalar(
        select(TransferenciaInventarioDetalle.id).where(
            TransferenciaInventarioDetalle.transferencia_id == transfer.id,
            TransferenciaInventarioDetalle.material_id == material.id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El material ya existe en esta transferencia.",
        )

    detail = TransferenciaInventarioDetalle(
        transferencia_id=transfer.id,
        material_id=material.id,
        cantidad=Decimal(cantidad),
        costo_unitario_snapshot=Decimal(costo_unitario_snapshot) if costo_unitario_snapshot is not None else material.costo_unitario,
    )
    db.add(detail)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.transfer.detail.add",
        entity_name="transferencia_inventario_detalle",
        entity_id=detail.id,
        ip_address=ip_address,
        metadata_json={"transferencia_id": transfer.id, "material_id": material.id, "cantidad": str(detail.cantidad)},
    )
    return serialize_transfer_response(db, transfer)


def update_transfer_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    transfer_id: str,
    detail_id: str,
    material_id: str | None,
    cantidad: Decimal | None,
    costo_unitario_snapshot: Decimal | None,
    ip_address: str | None,
) -> TransferResponse:
    transfer = get_transfer_for_company(db, empresa.id, transfer_id, for_update=True)
    ensure_transfer_is_draft(transfer)
    detail = get_transfer_detail(db, transfer.id, detail_id)

    if material_id is not None:
        material = get_material_for_company(db, empresa.id, material_id)
        existing = db.scalar(
            select(TransferenciaInventarioDetalle.id).where(
                TransferenciaInventarioDetalle.transferencia_id == transfer.id,
                TransferenciaInventarioDetalle.material_id == material.id,
                TransferenciaInventarioDetalle.id != detail.id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El material ya existe en esta transferencia.",
            )
        detail.material_id = material.id
        if costo_unitario_snapshot is None:
            detail.costo_unitario_snapshot = material.costo_unitario

    if cantidad is not None:
        detail.cantidad = Decimal(cantidad)
    if costo_unitario_snapshot is not None:
        detail.costo_unitario_snapshot = Decimal(costo_unitario_snapshot)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.transfer.detail.update",
        entity_name="transferencia_inventario_detalle",
        entity_id=detail.id,
        ip_address=ip_address,
        metadata_json={"transferencia_id": transfer.id, "material_id": detail.material_id, "cantidad": str(detail.cantidad)},
    )
    db.flush()
    return serialize_transfer_response(db, transfer)


def delete_transfer_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    transfer_id: str,
    detail_id: str,
    ip_address: str | None,
) -> TransferResponse:
    transfer = get_transfer_for_company(db, empresa.id, transfer_id, for_update=True)
    ensure_transfer_is_draft(transfer)
    detail = get_transfer_detail(db, transfer.id, detail_id)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.transfer.detail.delete",
        entity_name="transferencia_inventario_detalle",
        entity_id=detail.id,
        ip_address=ip_address,
        metadata_json={"transferencia_id": transfer.id, "material_id": detail.material_id},
    )
    db.delete(detail)
    db.flush()
    return serialize_transfer_response(db, transfer)


def confirm_transfer(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    transfer_id: str,
    ip_address: str | None,
) -> TransferResponse:
    transfer = get_transfer_for_company(db, empresa.id, transfer_id, for_update=True)
    ensure_transfer_is_draft(transfer)

    detail_rows = db.execute(
        select(TransferenciaInventarioDetalle, Material)
        .join(Material, TransferenciaInventarioDetalle.material_id == Material.id)
        .where(TransferenciaInventarioDetalle.transferencia_id == transfer.id)
        .order_by(Material.sku.asc())
    ).all()
    if not detail_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La transferencia debe tener al menos un material.",
        )

    validate_transfer_header(
        db,
        empresa.id,
        almacen_origen_id=transfer.almacen_origen_id,
        almacen_destino_id=transfer.almacen_destino_id,
    )

    for detail, material in detail_rows:
        stock = get_or_create_stock(db, empresa.id, transfer.almacen_origen_id, material.id)
        if Decimal(stock.cantidad) < Decimal(detail.cantidad):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stock insuficiente.")

    for detail, material in detail_rows:
        transfer_note = f"Transferencia {transfer.folio}"
        if transfer.notas:
            transfer_note = f"{transfer_note}: {transfer.notas}"
        apply_inventory_movement(
            db,
            user=user,
            empresa=empresa,
            almacen_id=transfer.almacen_origen_id,
            material_id=material.id,
            tipo="salida",
            cantidad=detail.cantidad,
            cantidad_nueva=None,
            referencia_tipo="transferencia_salida",
            referencia_id=transfer.id,
            notas=transfer_note,
            ip_address=ip_address,
            costo_unitario=detail.costo_unitario_snapshot,
        )
        apply_inventory_movement(
            db,
            user=user,
            empresa=empresa,
            almacen_id=transfer.almacen_destino_id,
            material_id=material.id,
            tipo="entrada",
            cantidad=detail.cantidad,
            cantidad_nueva=None,
            referencia_tipo="transferencia_entrada",
            referencia_id=transfer.id,
            notas=transfer_note,
            ip_address=ip_address,
            costo_unitario=detail.costo_unitario_snapshot,
        )

    transfer.estatus = "confirmada"
    transfer.confirmed_by_user_id = user.id
    transfer.confirmed_at = datetime.now(timezone.utc)
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.transfer.confirm",
        entity_name="transferencia_inventario",
        entity_id=transfer.id,
        ip_address=ip_address,
        metadata_json={"folio": transfer.folio, "estatus": transfer.estatus},
    )
    db.flush()
    return serialize_transfer_response(db, transfer)


def cancel_transfer(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    transfer_id: str,
    ip_address: str | None,
) -> TransferResponse:
    transfer = get_transfer_for_company(db, empresa.id, transfer_id, for_update=True)
    ensure_transfer_is_draft(transfer)

    transfer.estatus = "cancelada"
    transfer.cancelled_by_user_id = user.id
    transfer.cancelled_at = datetime.now(timezone.utc)
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.transfer.cancel",
        entity_name="transferencia_inventario",
        entity_id=transfer.id,
        ip_address=ip_address,
        metadata_json={"folio": transfer.folio, "estatus": transfer.estatus, "reversa_pendiente": True},
    )
    db.flush()
    return serialize_transfer_response(db, transfer)


def create_count(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    folio: str | None,
    almacen_id: str,
    notas: str | None,
    ip_address: str | None,
) -> CountResponse:
    warehouse = get_warehouse_for_company(db, empresa.id, almacen_id)
    count_folio = normalize_optional_folio(folio, "CI")
    ensure_unique_count_folio(db, empresa.id, count_folio)

    count = ConteoInventario(
        empresa_id=empresa.id,
        almacen_id=warehouse.id,
        folio=count_folio,
        notas=normalize_optional_text(notas),
        created_by_user_id=user.id,
    )
    db.add(count)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.count.create",
        entity_name="conteo_inventario",
        entity_id=count.id,
        ip_address=ip_address,
        metadata_json={"folio": count.folio, "estatus": count.estatus},
    )
    return serialize_count_response(db, count)


def update_count(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    count_id: str,
    folio: str | None,
    almacen_id: str | None,
    notas: str | None,
    ip_address: str | None,
) -> CountResponse:
    count = get_count_for_company(db, empresa.id, count_id, for_update=True)
    ensure_count_is_draft(count)

    if almacen_id is not None and almacen_id != count.almacen_id:
        get_warehouse_for_company(db, empresa.id, almacen_id)
        existing_details = db.scalar(
            select(func.count(ConteoInventarioDetalle.id)).where(ConteoInventarioDetalle.conteo_id == count.id)
        ) or 0
        if existing_details > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No puedes cambiar el almacén de un conteo que ya tiene detalles.",
            )
        count.almacen_id = almacen_id

    if folio is not None:
        normalized_folio = normalize_optional_folio(folio, "CI")
        ensure_unique_count_folio(db, empresa.id, normalized_folio, exclude_id=count.id)
        count.folio = normalized_folio
    if notas is not None:
        count.notas = normalize_optional_text(notas)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.count.update",
        entity_name="conteo_inventario",
        entity_id=count.id,
        ip_address=ip_address,
        metadata_json={"folio": count.folio, "estatus": count.estatus},
    )
    db.flush()
    return serialize_count_response(db, count)


def add_count_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    count_id: str,
    material_id: str,
    cantidad_fisica: Decimal,
    ip_address: str | None,
) -> CountResponse:
    count = get_count_for_company(db, empresa.id, count_id, for_update=True)
    ensure_count_is_draft(count)
    material = get_material_for_company(db, empresa.id, material_id)

    existing = db.scalar(
        select(ConteoInventarioDetalle.id).where(
            ConteoInventarioDetalle.conteo_id == count.id,
            ConteoInventarioDetalle.material_id == material.id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El material ya existe en este conteo.",
        )

    snapshot = get_current_stock_snapshot(db, empresa.id, count.almacen_id, material.id)
    physical = Decimal(cantidad_fisica)
    detail = ConteoInventarioDetalle(
        conteo_id=count.id,
        material_id=material.id,
        cantidad_sistema_snapshot=snapshot,
        cantidad_fisica=physical,
        diferencia=physical - snapshot,
    )
    db.add(detail)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.count.detail.add",
        entity_name="conteo_inventario_detalle",
        entity_id=detail.id,
        ip_address=ip_address,
        metadata_json={"conteo_id": count.id, "material_id": material.id, "cantidad_fisica": str(detail.cantidad_fisica)},
    )
    return serialize_count_response(db, count)


def update_count_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    count_id: str,
    detail_id: str,
    material_id: str | None,
    cantidad_fisica: Decimal | None,
    ip_address: str | None,
) -> CountResponse:
    count = get_count_for_company(db, empresa.id, count_id, for_update=True)
    ensure_count_is_draft(count)
    detail = get_count_detail(db, count.id, detail_id)

    if material_id is not None:
        material = get_material_for_company(db, empresa.id, material_id)
        existing = db.scalar(
            select(ConteoInventarioDetalle.id).where(
                ConteoInventarioDetalle.conteo_id == count.id,
                ConteoInventarioDetalle.material_id == material.id,
                ConteoInventarioDetalle.id != detail.id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El material ya existe en este conteo.",
            )
        detail.material_id = material.id
        detail.cantidad_sistema_snapshot = get_current_stock_snapshot(db, empresa.id, count.almacen_id, material.id)

    if cantidad_fisica is not None:
        detail.cantidad_fisica = Decimal(cantidad_fisica)

    detail.diferencia = Decimal(detail.cantidad_fisica) - Decimal(detail.cantidad_sistema_snapshot)
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.count.detail.update",
        entity_name="conteo_inventario_detalle",
        entity_id=detail.id,
        ip_address=ip_address,
        metadata_json={"conteo_id": count.id, "material_id": detail.material_id, "cantidad_fisica": str(detail.cantidad_fisica)},
    )
    db.flush()
    return serialize_count_response(db, count)


def delete_count_detail(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    count_id: str,
    detail_id: str,
    ip_address: str | None,
) -> CountResponse:
    count = get_count_for_company(db, empresa.id, count_id, for_update=True)
    ensure_count_is_draft(count)
    detail = get_count_detail(db, count.id, detail_id)

    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.count.detail.delete",
        entity_name="conteo_inventario_detalle",
        entity_id=detail.id,
        ip_address=ip_address,
        metadata_json={"conteo_id": count.id, "material_id": detail.material_id},
    )
    db.delete(detail)
    db.flush()
    return serialize_count_response(db, count)


def apply_count(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    count_id: str,
    ip_address: str | None,
) -> CountResponse:
    count = get_count_for_company(db, empresa.id, count_id, for_update=True)
    ensure_count_is_draft(count)
    get_warehouse_for_company(db, empresa.id, count.almacen_id)

    detail_rows = db.execute(
        select(ConteoInventarioDetalle, Material)
        .join(Material, ConteoInventarioDetalle.material_id == Material.id)
        .where(ConteoInventarioDetalle.conteo_id == count.id)
        .order_by(Material.sku.asc())
    ).all()
    if not detail_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El conteo debe tener al menos un material.",
        )

    for detail, material in detail_rows:
        difference = Decimal(detail.cantidad_fisica) - Decimal(detail.cantidad_sistema_snapshot)
        detail.diferencia = difference
        if difference == ZERO:
            detail.ajuste_movimiento_id = None
            continue

        note = f"Conteo fisico {count.folio}"
        if count.notas:
            note = f"{note}: {count.notas}"
        movement = apply_inventory_movement(
            db,
            user=user,
            empresa=empresa,
            almacen_id=count.almacen_id,
            material_id=material.id,
            tipo="ajuste",
            cantidad=None,
            cantidad_nueva=detail.cantidad_fisica,
            referencia_tipo="conteo_fisico",
            referencia_id=count.id,
            notas=note,
            ip_address=ip_address,
        )
        detail.ajuste_movimiento_id = movement.id

    count.estatus = "aplicado"
    count.applied_by_user_id = user.id
    count.applied_at = datetime.now(timezone.utc)
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.count.apply",
        entity_name="conteo_inventario",
        entity_id=count.id,
        ip_address=ip_address,
        metadata_json={"folio": count.folio, "estatus": count.estatus, "reversa_pendiente": True},
    )
    db.flush()
    return serialize_count_response(db, count)


def cancel_count(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    count_id: str,
    ip_address: str | None,
) -> CountResponse:
    count = get_count_for_company(db, empresa.id, count_id, for_update=True)
    ensure_count_is_draft(count)

    count.estatus = "cancelado"
    count.cancelled_by_user_id = user.id
    count.cancelled_at = datetime.now(timezone.utc)
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="inventory.count.cancel",
        entity_name="conteo_inventario",
        entity_id=count.id,
        ip_address=ip_address,
        metadata_json={"folio": count.folio, "estatus": count.estatus, "reversa_pendiente": True},
    )
    db.flush()
    return serialize_count_response(db, count)
