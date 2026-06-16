from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AuditLog,
    CRMActividad,
    CRMCliente,
    CRMContacto,
    CRMOportunidad,
    Empresa,
    EmpresaUsuario,
    PMProyecto,
    Usuario,
    Venta,
)
from app.schemas.crm import (
    CRMActivityItem,
    CRMClientItem,
    CRMClientCommercialSummaryResponse,
    CRMContactItem,
    CRMClientTimelineItem,
    CRMClientTimelineResponse,
    CRMOpportunityItem,
    CRMSummaryKpis,
    CRMSummaryPipelineStageItem,
    CRMSummaryResponse,
)
from app.services.access import can_access_module
from app.services.inventory import apply_text_search, count_rows, normalize_optional_text, normalize_required_text


ZERO = Decimal("0")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RFC_PATTERN = re.compile(r"^([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}|XAXX010101000)$")
POSTAL_CODE_PATTERN = re.compile(r"^\d{5}$")
CLIENT_TYPES = {"prospecto", "cliente", "otro"}
CLIENT_STATUSES = {"activo", "inactivo"}
OPPORTUNITY_STAGES = {"nueva", "contactado", "propuesta", "negociacion", "ganada", "perdida"}
ACTIVITY_TYPES = {"llamada", "email", "reunion", "tarea", "nota", "whatsapp", "otro"}


def validate_crm_access(user: Usuario, empresa: Empresa) -> None:
    if not can_access_module(user, empresa, "crm"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La empresa no tiene acceso al modulo CRM.",
        )


def ensure_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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


def normalize_email(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if not EMAIL_PATTERN.fullmatch(lowered):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ingresa un email valido.")
    return lowered


def normalize_rfc(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    upper = normalized.upper().replace(" ", "")
    if not RFC_PATTERN.fullmatch(upper):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ingresa un RFC valido.")
    return upper


def normalize_postal_code(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    if not POSTAL_CODE_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ingresa un codigo postal valido.")
    return normalized


def normalize_client_type(value: str | None, *, default: str = "prospecto") -> str:
    normalized = (normalize_optional_text(value) or default).lower()
    if normalized not in CLIENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de cliente invalido.")
    return normalized


def normalize_client_status(value: str | None, *, default: str = "activo") -> str:
    normalized = (normalize_optional_text(value) or default).lower()
    if normalized not in CLIENT_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estatus de cliente invalido.")
    return normalized


def normalize_opportunity_stage(value: str | None, *, default: str = "nueva") -> str:
    normalized = (normalize_optional_text(value) or default).lower()
    if normalized not in OPPORTUNITY_STAGES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Etapa de oportunidad invalida.")
    return normalized


def normalize_activity_type(value: str | None, *, default: str = "nota") -> str:
    normalized = (normalize_optional_text(value) or default).lower()
    if normalized not in ACTIVITY_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de actividad invalido.")
    return normalized


def nulls_last_rank(column):
    return case((column.is_(None), 1), else_=0)


def normalize_probability(value: int | None, *, default: int = 0) -> int:
    if value is None:
        return default
    probability = int(value)
    if probability < 0 or probability > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La probabilidad debe estar entre 0 y 100.")
    return probability


def normalize_nonnegative_amount(value: Decimal | int | float | None) -> Decimal:
    amount = Decimal(str(value if value is not None else 0))
    if amount < ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El monto estimado debe ser mayor o igual a cero.")
    return amount


def get_client_for_company(db: Session, empresa_id: str, client_id: str) -> CRMCliente:
    client = db.scalar(
        select(CRMCliente).where(
            CRMCliente.id == client_id,
            CRMCliente.empresa_id == empresa_id,
        )
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado.")
    return client


def get_contact_for_company(db: Session, empresa_id: str, contact_id: str) -> CRMContacto:
    contact = db.scalar(
        select(CRMContacto)
        .options(selectinload(CRMContacto.cliente))
        .where(
            CRMContacto.id == contact_id,
            CRMContacto.empresa_id == empresa_id,
        )
    )
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado.")
    return contact


def get_opportunity_for_company(db: Session, empresa_id: str, opportunity_id: str) -> CRMOportunidad:
    opportunity = db.scalar(
        select(CRMOportunidad)
        .options(
            selectinload(CRMOportunidad.cliente),
            selectinload(CRMOportunidad.contacto),
            selectinload(CRMOportunidad.responsable_user),
        )
        .where(
            CRMOportunidad.id == opportunity_id,
            CRMOportunidad.empresa_id == empresa_id,
        )
    )
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidad no encontrada.")
    return opportunity


def get_activity_for_company(db: Session, empresa_id: str, activity_id: str) -> CRMActividad:
    activity = db.scalar(
        select(CRMActividad)
        .options(
            selectinload(CRMActividad.cliente),
            selectinload(CRMActividad.contacto),
            selectinload(CRMActividad.oportunidad),
            selectinload(CRMActividad.usuario),
        )
        .where(
            CRMActividad.id == activity_id,
            CRMActividad.empresa_id == empresa_id,
        )
    )
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actividad no encontrada.")
    return activity


def resolve_invoice_request_display_status(sale: Venta) -> str:
    return normalize_optional_text(sale.factura_revision_estado) or normalize_optional_text(sale.factura_estado) or "no_solicitada"


def serialize_client(client: CRMCliente) -> CRMClientItem:
    return CRMClientItem(
        id=client.id,
        empresa_id=client.empresa_id,
        nombre_comercial=client.nombre_comercial,
        razon_social=client.razon_social,
        rfc=client.rfc,
        tipo=client.tipo,
        email=client.email,
        telefono=client.telefono,
        sitio_web=client.sitio_web,
        direccion=client.direccion,
        ciudad=client.ciudad,
        estado=client.estado,
        pais=client.pais,
        codigo_postal=client.codigo_postal,
        origen=client.origen,
        industria=client.industria,
        notas=client.notas,
        estatus=client.estatus,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


def serialize_contact(contact: CRMContacto) -> CRMContactItem:
    client_name = contact.cliente.nombre_comercial if contact.cliente else None
    return CRMContactItem(
        id=contact.id,
        empresa_id=contact.empresa_id,
        cliente_id=contact.cliente_id,
        cliente_nombre_comercial=client_name,
        nombre=contact.nombre,
        puesto=contact.puesto,
        email=contact.email,
        telefono=contact.telefono,
        whatsapp=contact.whatsapp,
        principal=contact.principal,
        notas=contact.notas,
        activo=contact.activo,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


def serialize_opportunity(opportunity: CRMOportunidad) -> CRMOpportunityItem:
    return CRMOpportunityItem(
        id=opportunity.id,
        empresa_id=opportunity.empresa_id,
        cliente_id=opportunity.cliente_id,
        cliente_nombre_comercial=opportunity.cliente.nombre_comercial if opportunity.cliente else None,
        contacto_id=opportunity.contacto_id,
        contacto_nombre=opportunity.contacto.nombre if opportunity.contacto else None,
        titulo=opportunity.titulo,
        descripcion=opportunity.descripcion,
        etapa=opportunity.etapa,
        monto_estimado=opportunity.monto_estimado,
        probabilidad=int(opportunity.probabilidad or 0),
        fecha_estimada_cierre=opportunity.fecha_estimada_cierre,
        responsable_user_id=opportunity.responsable_user_id,
        responsable_nombre=opportunity.responsable_user.full_name if opportunity.responsable_user else None,
        origen=opportunity.origen,
        motivo_perdida=opportunity.motivo_perdida,
        notas=opportunity.notas,
        activa=opportunity.activa,
        cerrada_at=opportunity.cerrada_at,
        created_at=opportunity.created_at,
        updated_at=opportunity.updated_at,
    )


def serialize_activity(activity: CRMActividad) -> CRMActivityItem:
    return CRMActivityItem(
        id=activity.id,
        empresa_id=activity.empresa_id,
        cliente_id=activity.cliente_id,
        cliente_nombre_comercial=activity.cliente.nombre_comercial if activity.cliente else None,
        oportunidad_id=activity.oportunidad_id,
        oportunidad_titulo=activity.oportunidad.titulo if activity.oportunidad else None,
        contacto_id=activity.contacto_id,
        contacto_nombre=activity.contacto.nombre if activity.contacto else None,
        tipo=activity.tipo,
        titulo=activity.titulo,
        descripcion=activity.descripcion,
        fecha_actividad=activity.fecha_actividad,
        fecha_vencimiento=activity.fecha_vencimiento,
        completada=activity.completada,
        completada_at=activity.completada_at,
        usuario_id=activity.usuario_id,
        usuario_nombre=activity.usuario.full_name if activity.usuario else None,
        activo=activity.activo,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


def ensure_responsible_user_in_company(db: Session, empresa_id: str, user_id: str | None) -> str | None:
    if not user_id:
        return None
    user = db.get(Usuario, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Responsable no encontrado.")
    membership_exists = db.scalar(
        select(func.count(EmpresaUsuario.id)).where(
            EmpresaUsuario.empresa_id == empresa_id,
            EmpresaUsuario.usuario_id == user_id,
            EmpresaUsuario.is_active == True,
        )
    )
    if not membership_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Responsable no pertenece a la empresa.")
    return user_id


def resolve_activity_relations(
    db: Session,
    empresa_id: str,
    *,
    cliente_id: str | None,
    oportunidad_id: str | None,
    contacto_id: str | None,
) -> tuple[CRMCliente | None, CRMOportunidad | None, CRMContacto | None]:
    client = get_client_for_company(db, empresa_id, cliente_id) if cliente_id else None
    opportunity = get_opportunity_for_company(db, empresa_id, oportunidad_id) if oportunidad_id else None
    contact = get_contact_for_company(db, empresa_id, contacto_id) if contacto_id else None

    if opportunity and client and opportunity.cliente_id != client.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La oportunidad no pertenece al cliente indicado.")
    if contact and client and contact.cliente_id != client.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El contacto no pertenece al cliente indicado.")
    if opportunity and contact and opportunity.cliente_id != contact.cliente_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El contacto no pertenece a la oportunidad indicada.")

    resolved_client = client or (opportunity.cliente if opportunity else None) or (contact.cliente if contact else None)
    return resolved_client, opportunity, contact


def list_clients(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    tipo: str | None = None,
    estatus: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[CRMClientItem]]:
    query = select(CRMCliente).where(CRMCliente.empresa_id == empresa_id)
    query = apply_text_search(
        query,
        q,
        CRMCliente.nombre_comercial,
        CRMCliente.razon_social,
        CRMCliente.rfc,
        CRMCliente.email,
        CRMCliente.telefono,
        CRMCliente.sitio_web,
        CRMCliente.ciudad,
        CRMCliente.estado,
        CRMCliente.pais,
        CRMCliente.codigo_postal,
        CRMCliente.origen,
        CRMCliente.industria,
        CRMCliente.notas,
    )
    if tipo:
        query = query.where(CRMCliente.tipo == normalize_client_type(tipo))
    if estatus:
        query = query.where(CRMCliente.estatus == normalize_client_status(estatus))
    total = count_rows(db, query)
    items = db.scalars(query.order_by(desc(CRMCliente.created_at), desc(CRMCliente.id)).offset(offset).limit(limit)).all()
    return total, [serialize_client(item) for item in items]


def create_client(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    nombre_comercial: str,
    razon_social: str | None,
    rfc: str | None,
    tipo: str | None,
    email: str | None,
    telefono: str | None,
    sitio_web: str | None,
    direccion: str | None,
    ciudad: str | None,
    estado: str | None,
    pais: str | None,
    codigo_postal: str | None,
    origen: str | None,
    industria: str | None,
    notas: str | None,
    estatus: str | None,
    ip_address: str | None,
) -> CRMClientItem:
    validate_crm_access(user, empresa)
    client = CRMCliente(
        empresa_id=empresa.id,
        nombre_comercial=normalize_required_text(nombre_comercial, "Nombre comercial"),
        razon_social=normalize_optional_text(razon_social),
        rfc=normalize_rfc(rfc),
        tipo=normalize_client_type(tipo),
        email=normalize_email(email),
        telefono=normalize_optional_text(telefono),
        sitio_web=normalize_optional_text(sitio_web),
        direccion=normalize_optional_text(direccion),
        ciudad=normalize_optional_text(ciudad),
        estado=normalize_optional_text(estado),
        pais=normalize_optional_text(pais),
        codigo_postal=normalize_postal_code(codigo_postal),
        origen=normalize_optional_text(origen),
        industria=normalize_optional_text(industria),
        notas=normalize_optional_text(notas),
        estatus=normalize_client_status(estatus),
    )
    db.add(client)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.client.create",
        entity_name="CRMCliente",
        entity_id=client.id,
        ip_address=ip_address,
        metadata_json={"nombre_comercial": client.nombre_comercial, "tipo": client.tipo},
    )
    return serialize_client(client)


def update_client(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    client_id: str,
    nombre_comercial: str | None = None,
    razon_social: str | None = None,
    rfc: str | None = None,
    tipo: str | None = None,
    email: str | None = None,
    telefono: str | None = None,
    sitio_web: str | None = None,
    direccion: str | None = None,
    ciudad: str | None = None,
    estado: str | None = None,
    pais: str | None = None,
    codigo_postal: str | None = None,
    origen: str | None = None,
    industria: str | None = None,
    notas: str | None = None,
    estatus: str | None = None,
    ip_address: str | None = None,
) -> CRMClientItem:
    validate_crm_access(user, empresa)
    client = get_client_for_company(db, empresa.id, client_id)
    if nombre_comercial is not None:
        client.nombre_comercial = normalize_required_text(nombre_comercial, "Nombre comercial")
    if razon_social is not None:
        client.razon_social = normalize_optional_text(razon_social)
    if rfc is not None:
        client.rfc = normalize_rfc(rfc)
    if tipo is not None:
        client.tipo = normalize_client_type(tipo)
    if email is not None:
        client.email = normalize_email(email)
    if telefono is not None:
        client.telefono = normalize_optional_text(telefono)
    if sitio_web is not None:
        client.sitio_web = normalize_optional_text(sitio_web)
    if direccion is not None:
        client.direccion = normalize_optional_text(direccion)
    if ciudad is not None:
        client.ciudad = normalize_optional_text(ciudad)
    if estado is not None:
        client.estado = normalize_optional_text(estado)
    if pais is not None:
        client.pais = normalize_optional_text(pais)
    if codigo_postal is not None:
        client.codigo_postal = normalize_postal_code(codigo_postal)
    if origen is not None:
        client.origen = normalize_optional_text(origen)
    if industria is not None:
        client.industria = normalize_optional_text(industria)
    if notas is not None:
        client.notas = normalize_optional_text(notas)
    if estatus is not None:
        client.estatus = normalize_client_status(estatus)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.client.update",
        entity_name="CRMCliente",
        entity_id=client.id,
        ip_address=ip_address,
        metadata_json={"estatus": client.estatus, "tipo": client.tipo},
    )
    return serialize_client(client)


def set_client_status(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    client_id: str,
    status_value: str,
    ip_address: str | None,
) -> CRMClientItem:
    validate_crm_access(user, empresa)
    client = get_client_for_company(db, empresa.id, client_id)
    client.estatus = normalize_client_status(status_value)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action=f"crm.client.{status_value}",
        entity_name="CRMCliente",
        entity_id=client.id,
        ip_address=ip_address,
        metadata_json={"estatus": client.estatus},
    )
    return serialize_client(client)


def list_client_contacts(
    db: Session,
    empresa_id: str,
    client_id: str,
    *,
    q: str | None = None,
    activo: bool | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[CRMContactItem]]:
    get_client_for_company(db, empresa_id, client_id)
    query = select(CRMContacto).options(selectinload(CRMContacto.cliente)).where(
        CRMContacto.empresa_id == empresa_id,
        CRMContacto.cliente_id == client_id,
    )
    query = apply_text_search(query, q, CRMContacto.nombre, CRMContacto.puesto, CRMContacto.email, CRMContacto.telefono, CRMContacto.whatsapp, CRMContacto.notas)
    if activo is not None:
        query = query.where(CRMContacto.activo == activo)
    total = count_rows(db, query)
    items = db.scalars(query.order_by(desc(CRMContacto.principal), desc(CRMContacto.created_at), desc(CRMContacto.id)).offset(offset).limit(limit)).all()
    return total, [serialize_contact(item) for item in items]


def ensure_single_primary_contact(db: Session, empresa_id: str, client_id: str, *, exclude_contact_id: str | None = None) -> None:
    query = select(CRMContacto).where(
        CRMContacto.empresa_id == empresa_id,
        CRMContacto.cliente_id == client_id,
        CRMContacto.principal == True,
    )
    if exclude_contact_id:
        query = query.where(CRMContacto.id != exclude_contact_id)
    for item in db.scalars(query).all():
        item.principal = False


def create_contact(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    client_id: str,
    nombre: str,
    puesto: str | None,
    email: str | None,
    telefono: str | None,
    whatsapp: str | None,
    principal: bool,
    notas: str | None,
    activo: bool,
    ip_address: str | None,
) -> CRMContactItem:
    validate_crm_access(user, empresa)
    client = get_client_for_company(db, empresa.id, client_id)
    if principal:
        ensure_single_primary_contact(db, empresa.id, client.id)
    contact = CRMContacto(
        empresa_id=empresa.id,
        cliente_id=client.id,
        nombre=normalize_required_text(nombre, "Nombre"),
        puesto=normalize_optional_text(puesto),
        email=normalize_email(email),
        telefono=normalize_optional_text(telefono),
        whatsapp=normalize_optional_text(whatsapp),
        principal=bool(principal),
        notas=normalize_optional_text(notas),
        activo=bool(activo),
    )
    db.add(contact)
    db.flush()
    db.refresh(contact)
    contact.cliente = client
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.contact.create",
        entity_name="CRMContacto",
        entity_id=contact.id,
        ip_address=ip_address,
        metadata_json={"cliente_id": client.id, "principal": contact.principal},
    )
    return serialize_contact(contact)


def update_contact(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    contact_id: str,
    nombre: str | None = None,
    puesto: str | None = None,
    email: str | None = None,
    telefono: str | None = None,
    whatsapp: str | None = None,
    principal: bool | None = None,
    notas: str | None = None,
    activo: bool | None = None,
    ip_address: str | None = None,
) -> CRMContactItem:
    validate_crm_access(user, empresa)
    contact = get_contact_for_company(db, empresa.id, contact_id)
    if nombre is not None:
        contact.nombre = normalize_required_text(nombre, "Nombre")
    if puesto is not None:
        contact.puesto = normalize_optional_text(puesto)
    if email is not None:
        contact.email = normalize_email(email)
    if telefono is not None:
        contact.telefono = normalize_optional_text(telefono)
    if whatsapp is not None:
        contact.whatsapp = normalize_optional_text(whatsapp)
    if principal is not None:
        if principal:
            ensure_single_primary_contact(db, empresa.id, contact.cliente_id, exclude_contact_id=contact.id)
        contact.principal = bool(principal)
    if notas is not None:
        contact.notas = normalize_optional_text(notas)
    if activo is not None:
        contact.activo = bool(activo)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.contact.update",
        entity_name="CRMContacto",
        entity_id=contact.id,
        ip_address=ip_address,
        metadata_json={"cliente_id": contact.cliente_id, "activo": contact.activo, "principal": contact.principal},
    )
    return serialize_contact(contact)


def deactivate_contact(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    contact_id: str,
    ip_address: str | None,
) -> CRMContactItem:
    return update_contact(
        db,
        empresa=empresa,
        user=user,
        contact_id=contact_id,
        activo=False,
        ip_address=ip_address,
    )


def list_opportunities(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    etapa: str | None = None,
    activa: bool | None = None,
    client_id: str | None = None,
    responsible_user_id: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[CRMOpportunityItem]]:
    query = (
        select(CRMOportunidad)
        .options(
            selectinload(CRMOportunidad.cliente),
            selectinload(CRMOportunidad.contacto),
            selectinload(CRMOportunidad.responsable_user),
        )
        .where(CRMOportunidad.empresa_id == empresa_id)
    )
    query = apply_text_search(
        query,
        q,
        CRMOportunidad.titulo,
        CRMOportunidad.descripcion,
        CRMOportunidad.origen,
        CRMOportunidad.motivo_perdida,
        CRMOportunidad.notas,
    )
    if etapa:
        query = query.where(CRMOportunidad.etapa == normalize_opportunity_stage(etapa))
    if activa is not None:
        query = query.where(CRMOportunidad.activa == activa)
    if client_id:
        query = query.where(CRMOportunidad.cliente_id == client_id)
    if responsible_user_id:
        query = query.where(CRMOportunidad.responsable_user_id == responsible_user_id)
    total = count_rows(db, query)
    items = db.scalars(query.order_by(desc(CRMOportunidad.updated_at), desc(CRMOportunidad.id)).offset(offset).limit(limit)).all()
    return total, [serialize_opportunity(item) for item in items]


def create_opportunity(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    client_id: str,
    contacto_id: str | None,
    titulo: str,
    descripcion: str | None,
    etapa: str | None,
    monto_estimado: Decimal | int | float | None,
    probabilidad: int | None,
    fecha_estimada_cierre,
    responsable_user_id: str | None,
    origen: str | None,
    motivo_perdida: str | None,
    notas: str | None,
    activa: bool,
    ip_address: str | None,
) -> CRMOpportunityItem:
    validate_crm_access(user, empresa)
    client = get_client_for_company(db, empresa.id, client_id)
    contact = get_contact_for_company(db, empresa.id, contacto_id) if contacto_id else None
    if contact and contact.cliente_id != client.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El contacto no pertenece al cliente indicado.")
    stage = normalize_opportunity_stage(etapa)
    loss_reason = normalize_optional_text(motivo_perdida)
    if stage == "perdida" and not loss_reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Close-lost requiere motivo_perdida.")
    responsible_id = ensure_responsible_user_in_company(db, empresa.id, responsable_user_id)
    is_closed = stage in {"ganada", "perdida"}
    opportunity = CRMOportunidad(
        empresa_id=empresa.id,
        cliente_id=client.id,
        contacto_id=contact.id if contact else None,
        titulo=normalize_required_text(titulo, "Titulo"),
        descripcion=normalize_optional_text(descripcion),
        etapa=stage,
        monto_estimado=normalize_nonnegative_amount(monto_estimado),
        probabilidad=normalize_probability(probabilidad),
        fecha_estimada_cierre=fecha_estimada_cierre,
        responsable_user_id=responsible_id,
        origen=normalize_optional_text(origen),
        motivo_perdida=loss_reason if stage == "perdida" else None,
        notas=normalize_optional_text(notas),
        activa=bool(activa and not is_closed),
        cerrada_at=datetime.now(timezone.utc) if is_closed else None,
    )
    if stage == "ganada":
        opportunity.activa = False
    db.add(opportunity)
    db.flush()
    opportunity.cliente = client
    opportunity.contacto = contact
    if responsible_id:
        opportunity.responsable_user = db.get(Usuario, responsible_id)
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.opportunity.create",
        entity_name="CRMOportunidad",
        entity_id=opportunity.id,
        ip_address=ip_address,
        metadata_json={"cliente_id": client.id, "etapa": opportunity.etapa},
    )
    return serialize_opportunity(opportunity)


def update_opportunity(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    opportunity_id: str,
    client_id: str | None = None,
    contacto_id: str | None = None,
    titulo: str | None = None,
    descripcion: str | None = None,
    etapa: str | None = None,
    monto_estimado: Decimal | int | float | None = None,
    probabilidad: int | None = None,
    fecha_estimada_cierre = None,
    responsable_user_id: str | None = None,
    origen: str | None = None,
    motivo_perdida: str | None = None,
    notas: str | None = None,
    activa: bool | None = None,
    ip_address: str | None = None,
) -> CRMOpportunityItem:
    validate_crm_access(user, empresa)
    opportunity = get_opportunity_for_company(db, empresa.id, opportunity_id)
    client = opportunity.cliente
    if client_id is not None and client_id != opportunity.cliente_id:
        client = get_client_for_company(db, empresa.id, client_id)
        opportunity.cliente_id = client.id
        opportunity.cliente = client

    if contacto_id is not None:
        if contacto_id == "":
            opportunity.contacto_id = None
            opportunity.contacto = None
        else:
            contact = get_contact_for_company(db, empresa.id, contacto_id)
            if contact.cliente_id != opportunity.cliente_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El contacto no pertenece al cliente indicado.")
            opportunity.contacto_id = contact.id
            opportunity.contacto = contact

    if titulo is not None:
        opportunity.titulo = normalize_required_text(titulo, "Titulo")
    if descripcion is not None:
        opportunity.descripcion = normalize_optional_text(descripcion)
    if monto_estimado is not None:
        opportunity.monto_estimado = normalize_nonnegative_amount(monto_estimado)
    if probabilidad is not None:
        opportunity.probabilidad = normalize_probability(probabilidad)
    if fecha_estimada_cierre is not None:
        opportunity.fecha_estimada_cierre = fecha_estimada_cierre
    if responsable_user_id is not None:
        opportunity.responsable_user_id = ensure_responsible_user_in_company(db, empresa.id, responsable_user_id)
        opportunity.responsable_user = db.get(Usuario, opportunity.responsable_user_id) if opportunity.responsable_user_id else None
    if origen is not None:
        opportunity.origen = normalize_optional_text(origen)
    if notas is not None:
        opportunity.notas = normalize_optional_text(notas)
    if motivo_perdida is not None:
        opportunity.motivo_perdida = normalize_optional_text(motivo_perdida)
    if etapa is not None:
        new_stage = normalize_opportunity_stage(etapa)
        if new_stage == "perdida" and not normalize_optional_text(opportunity.motivo_perdida):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Close-lost requiere motivo_perdida.")
        opportunity.etapa = new_stage
        if new_stage in {"ganada", "perdida"}:
            opportunity.activa = False if activa is None else bool(activa)
            opportunity.cerrada_at = datetime.now(timezone.utc)
            if new_stage == "ganada":
                opportunity.motivo_perdida = None
        else:
            opportunity.cerrada_at = None
            opportunity.activa = True if activa is None else bool(activa)
    elif activa is not None:
        opportunity.activa = bool(activa)
        if opportunity.activa:
            opportunity.cerrada_at = None
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.opportunity.update",
        entity_name="CRMOportunidad",
        entity_id=opportunity.id,
        ip_address=ip_address,
        metadata_json={"etapa": opportunity.etapa, "activa": opportunity.activa},
    )
    return serialize_opportunity(opportunity)


def close_opportunity_won(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    opportunity_id: str,
    notas: str | None,
    ip_address: str | None,
) -> CRMOpportunityItem:
    validate_crm_access(user, empresa)
    opportunity = get_opportunity_for_company(db, empresa.id, opportunity_id)
    opportunity.etapa = "ganada"
    opportunity.activa = False
    opportunity.cerrada_at = datetime.now(timezone.utc)
    opportunity.motivo_perdida = None
    if notas is not None:
        opportunity.notas = normalize_optional_text(notas)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.opportunity.close_won",
        entity_name="CRMOportunidad",
        entity_id=opportunity.id,
        ip_address=ip_address,
        metadata_json={"etapa": opportunity.etapa},
    )
    return serialize_opportunity(opportunity)


def close_opportunity_lost(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    opportunity_id: str,
    motivo_perdida: str,
    notas: str | None,
    ip_address: str | None,
) -> CRMOpportunityItem:
    validate_crm_access(user, empresa)
    loss_reason = normalize_optional_text(motivo_perdida)
    if not loss_reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Close-lost requiere motivo_perdida.")
    opportunity = get_opportunity_for_company(db, empresa.id, opportunity_id)
    opportunity.etapa = "perdida"
    opportunity.activa = False
    opportunity.cerrada_at = datetime.now(timezone.utc)
    opportunity.motivo_perdida = loss_reason
    if notas is not None:
        opportunity.notas = normalize_optional_text(notas)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.opportunity.close_lost",
        entity_name="CRMOportunidad",
        entity_id=opportunity.id,
        ip_address=ip_address,
        metadata_json={"motivo_perdida": opportunity.motivo_perdida},
    )
    return serialize_opportunity(opportunity)


def list_activities(
    db: Session,
    empresa_id: str,
    *,
    q: str | None = None,
    tipo: str | None = None,
    completada: bool | None = None,
    activo: bool | None = None,
    client_id: str | None = None,
    opportunity_id: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    overdue_only: bool = False,
    limit: int = 25,
    offset: int = 0,
) -> tuple[int, list[CRMActivityItem]]:
    now = datetime.now(timezone.utc)
    query = (
        select(CRMActividad)
        .options(
            selectinload(CRMActividad.cliente),
            selectinload(CRMActividad.oportunidad),
            selectinload(CRMActividad.contacto),
            selectinload(CRMActividad.usuario),
        )
        .where(CRMActividad.empresa_id == empresa_id)
    )
    query = apply_text_search(query, q, CRMActividad.titulo, CRMActividad.descripcion)
    if tipo:
        query = query.where(CRMActividad.tipo == normalize_activity_type(tipo))
    if completada is not None:
        query = query.where(CRMActividad.completada == completada)
    if activo is not None:
        query = query.where(CRMActividad.activo == activo)
    if client_id:
        query = query.where(CRMActividad.cliente_id == client_id)
    if opportunity_id:
        query = query.where(CRMActividad.oportunidad_id == opportunity_id)
    if fecha_desde is not None:
        query = query.where(CRMActividad.fecha_actividad >= ensure_utc_datetime(fecha_desde))
    if fecha_hasta is not None:
        query = query.where(CRMActividad.fecha_actividad <= ensure_utc_datetime(fecha_hasta))
    if overdue_only:
        query = query.where(
            CRMActividad.activo == True,
            CRMActividad.completada == False,
            CRMActividad.fecha_vencimiento.is_not(None),
            CRMActividad.fecha_vencimiento < now,
        )
    total = count_rows(db, query)
    items = db.scalars(
        query.order_by(
            CRMActividad.completada.asc(),
            nulls_last_rank(CRMActividad.fecha_vencimiento).asc(),
            CRMActividad.fecha_vencimiento.asc(),
            desc(CRMActividad.fecha_actividad),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return total, [serialize_activity(item) for item in items]


def create_activity(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    cliente_id: str | None,
    oportunidad_id: str | None,
    contacto_id: str | None,
    tipo: str | None,
    titulo: str,
    descripcion: str | None,
    fecha_actividad: datetime,
    fecha_vencimiento: datetime | None,
    completada: bool,
    usuario_id: str | None,
    activo: bool,
    ip_address: str | None,
) -> CRMActivityItem:
    validate_crm_access(user, empresa)
    resolved_client, opportunity, contact = resolve_activity_relations(
        db,
        empresa.id,
        cliente_id=cliente_id,
        oportunidad_id=oportunidad_id,
        contacto_id=contacto_id,
    )
    assigned_user_id = ensure_responsible_user_in_company(db, empresa.id, usuario_id) if usuario_id else user.id
    activity = CRMActividad(
        empresa_id=empresa.id,
        cliente_id=resolved_client.id if resolved_client else None,
        oportunidad_id=opportunity.id if opportunity else None,
        contacto_id=contact.id if contact else None,
        tipo=normalize_activity_type(tipo),
        titulo=normalize_required_text(titulo, "Titulo"),
        descripcion=normalize_optional_text(descripcion),
        fecha_actividad=ensure_utc_datetime(fecha_actividad),
        fecha_vencimiento=ensure_utc_datetime(fecha_vencimiento),
        completada=bool(completada),
        completada_at=datetime.now(timezone.utc) if completada else None,
        usuario_id=assigned_user_id,
        activo=bool(activo),
    )
    db.add(activity)
    db.flush()
    activity.cliente = resolved_client
    activity.oportunidad = opportunity
    activity.contacto = contact
    activity.usuario = db.get(Usuario, assigned_user_id) if assigned_user_id else None
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.activity.create",
        entity_name="CRMActividad",
        entity_id=activity.id,
        ip_address=ip_address,
        metadata_json={"tipo": activity.tipo, "cliente_id": activity.cliente_id, "oportunidad_id": activity.oportunidad_id},
    )
    return serialize_activity(activity)


def update_activity(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    activity_id: str,
    cliente_id: str | None = None,
    oportunidad_id: str | None = None,
    contacto_id: str | None = None,
    tipo: str | None = None,
    titulo: str | None = None,
    descripcion: str | None = None,
    fecha_actividad: datetime | None = None,
    fecha_vencimiento: datetime | None = None,
    completada: bool | None = None,
    usuario_id: str | None = None,
    activo: bool | None = None,
    ip_address: str | None = None,
) -> CRMActivityItem:
    validate_crm_access(user, empresa)
    activity = get_activity_for_company(db, empresa.id, activity_id)

    if any(value is not None for value in (cliente_id, oportunidad_id, contacto_id)):
        resolved_client, opportunity, contact = resolve_activity_relations(
            db,
            empresa.id,
            cliente_id=cliente_id if cliente_id is not None else activity.cliente_id,
            oportunidad_id=oportunidad_id if oportunidad_id is not None else activity.oportunidad_id,
            contacto_id=contacto_id if contacto_id is not None else activity.contacto_id,
        )
        activity.cliente_id = resolved_client.id if resolved_client else None
        activity.oportunidad_id = opportunity.id if opportunity else None
        activity.contacto_id = contact.id if contact else None
        activity.cliente = resolved_client
        activity.oportunidad = opportunity
        activity.contacto = contact

    if tipo is not None:
        activity.tipo = normalize_activity_type(tipo)
    if titulo is not None:
        activity.titulo = normalize_required_text(titulo, "Titulo")
    if descripcion is not None:
        activity.descripcion = normalize_optional_text(descripcion)
    if fecha_actividad is not None:
        activity.fecha_actividad = ensure_utc_datetime(fecha_actividad)
    if fecha_vencimiento is not None:
        activity.fecha_vencimiento = ensure_utc_datetime(fecha_vencimiento)
    if usuario_id is not None:
        activity.usuario_id = ensure_responsible_user_in_company(db, empresa.id, usuario_id) if usuario_id else None
        activity.usuario = db.get(Usuario, activity.usuario_id) if activity.usuario_id else None
    if completada is not None:
        activity.completada = bool(completada)
        activity.completada_at = datetime.now(timezone.utc) if activity.completada else None
    if activo is not None:
        activity.activo = bool(activo)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.activity.update",
        entity_name="CRMActividad",
        entity_id=activity.id,
        ip_address=ip_address,
        metadata_json={"tipo": activity.tipo, "completada": activity.completada, "activo": activity.activo},
    )
    return serialize_activity(activity)


def complete_activity(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    activity_id: str,
    ip_address: str | None,
) -> CRMActivityItem:
    validate_crm_access(user, empresa)
    activity = get_activity_for_company(db, empresa.id, activity_id)
    activity.completada = True
    activity.completada_at = datetime.now(timezone.utc)
    db.flush()
    create_audit_log(
        db,
        empresa_id=empresa.id,
        usuario_id=user.id,
        action="crm.activity.complete",
        entity_name="CRMActividad",
        entity_id=activity.id,
        ip_address=ip_address,
        metadata_json={"completada": True},
    )
    return serialize_activity(activity)


def deactivate_activity(
    db: Session,
    *,
    empresa: Empresa,
    user: Usuario,
    activity_id: str,
    ip_address: str | None,
) -> CRMActivityItem:
    return update_activity(
        db,
        empresa=empresa,
        user=user,
        activity_id=activity_id,
        activo=False,
        ip_address=ip_address,
    )


def build_crm_summary(db: Session, empresa_id: str) -> CRMSummaryResponse:
    now = datetime.now(timezone.utc)
    clientes_activos = db.scalar(
        select(func.count(CRMCliente.id)).where(
            CRMCliente.empresa_id == empresa_id,
            CRMCliente.estatus == "activo",
        )
    ) or 0
    prospectos = db.scalar(
        select(func.count(CRMCliente.id)).where(
            CRMCliente.empresa_id == empresa_id,
            CRMCliente.tipo == "prospecto",
            CRMCliente.estatus == "activo",
        )
    ) or 0
    oportunidades_abiertas = db.scalar(
        select(func.count(CRMOportunidad.id)).where(
            CRMOportunidad.empresa_id == empresa_id,
            CRMOportunidad.activa == True,
        )
    ) or 0
    oportunidades_ganadas = db.scalar(
        select(func.count(CRMOportunidad.id)).where(
            CRMOportunidad.empresa_id == empresa_id,
            CRMOportunidad.etapa == "ganada",
        )
    ) or 0
    oportunidades_perdidas = db.scalar(
        select(func.count(CRMOportunidad.id)).where(
            CRMOportunidad.empresa_id == empresa_id,
            CRMOportunidad.etapa == "perdida",
        )
    ) or 0
    monto_pipeline = db.scalar(
        select(func.coalesce(func.sum(CRMOportunidad.monto_estimado), 0)).where(
            CRMOportunidad.empresa_id == empresa_id,
            CRMOportunidad.activa == True,
        )
    ) or ZERO
    monto_ganado = db.scalar(
        select(func.coalesce(func.sum(CRMOportunidad.monto_estimado), 0)).where(
            CRMOportunidad.empresa_id == empresa_id,
            CRMOportunidad.etapa == "ganada",
        )
    ) or ZERO
    actividades_pendientes_count = db.scalar(
        select(func.count(CRMActividad.id)).where(
            CRMActividad.empresa_id == empresa_id,
            CRMActividad.activo == True,
            CRMActividad.completada == False,
        )
    ) or 0
    actividades_vencidas = db.scalar(
        select(func.count(CRMActividad.id)).where(
            CRMActividad.empresa_id == empresa_id,
            CRMActividad.activo == True,
            CRMActividad.completada == False,
            CRMActividad.fecha_vencimiento.is_not(None),
            CRMActividad.fecha_vencimiento < now,
        )
    ) or 0

    pipeline_rows = db.execute(
        select(
            CRMOportunidad.etapa,
            func.count(CRMOportunidad.id),
            func.coalesce(func.sum(CRMOportunidad.monto_estimado), 0),
        )
        .where(CRMOportunidad.empresa_id == empresa_id)
        .group_by(CRMOportunidad.etapa)
    ).all()
    stage_order = ["nueva", "contactado", "propuesta", "negociacion", "ganada", "perdida"]
    stage_map = {
        row[0]: CRMSummaryPipelineStageItem(
            etapa=row[0],
            oportunidades_count=int(row[1] or 0),
            monto_total=row[2] or ZERO,
        )
        for row in pipeline_rows
    }
    pipeline_por_etapa = [stage_map[stage] for stage in stage_order if stage in stage_map]

    recent_opportunities = db.scalars(
        select(CRMOportunidad)
        .options(
            selectinload(CRMOportunidad.cliente),
            selectinload(CRMOportunidad.contacto),
            selectinload(CRMOportunidad.responsable_user),
        )
        .where(CRMOportunidad.empresa_id == empresa_id)
        .order_by(desc(CRMOportunidad.created_at), desc(CRMOportunidad.id))
        .limit(5)
    ).all()
    pending_activities = db.scalars(
        select(CRMActividad)
        .options(
            selectinload(CRMActividad.cliente),
            selectinload(CRMActividad.oportunidad),
            selectinload(CRMActividad.contacto),
            selectinload(CRMActividad.usuario),
        )
        .where(
            CRMActividad.empresa_id == empresa_id,
            CRMActividad.activo == True,
            CRMActividad.completada == False,
        )
        .order_by(
            nulls_last_rank(CRMActividad.fecha_vencimiento).asc(),
            CRMActividad.fecha_vencimiento.asc(),
            desc(CRMActividad.fecha_actividad),
        )
        .limit(10)
    ).all()
    recent_clients = db.scalars(
        select(CRMCliente)
        .where(CRMCliente.empresa_id == empresa_id)
        .order_by(desc(CRMCliente.created_at), desc(CRMCliente.id))
        .limit(5)
    ).all()

    return CRMSummaryResponse(
        kpis=CRMSummaryKpis(
            clientes_activos=int(clientes_activos),
            prospectos=int(prospectos),
            oportunidades_abiertas=int(oportunidades_abiertas),
            oportunidades_ganadas=int(oportunidades_ganadas),
            oportunidades_perdidas=int(oportunidades_perdidas),
            monto_pipeline=monto_pipeline,
            monto_ganado=monto_ganado,
            actividades_pendientes=int(actividades_pendientes_count),
            actividades_vencidas=int(actividades_vencidas),
        ),
        pipeline_por_etapa=pipeline_por_etapa,
        oportunidades_recientes=[serialize_opportunity(item) for item in recent_opportunities],
        actividades_pendientes=[serialize_activity(item) for item in pending_activities],
        clientes_recientes=[serialize_client(item) for item in recent_clients],
    )


def get_client_timeline(
    db: Session,
    empresa_id: str,
    client_id: str,
) -> CRMClientTimelineResponse:
    get_client_for_company(db, empresa_id, client_id)

    sales = db.scalars(
        select(Venta)
        .where(
            Venta.empresa_id == empresa_id,
            Venta.crm_cliente_id == client_id,
        )
        .order_by(desc(func.coalesce(Venta.paid_at, Venta.created_at)), desc(Venta.id))
    ).all()
    projects = db.scalars(
        select(PMProyecto)
        .where(
            PMProyecto.empresa_id == empresa_id,
            PMProyecto.crm_cliente_id == client_id,
        )
        .order_by(desc(PMProyecto.updated_at), desc(PMProyecto.id))
    ).all()
    opportunities = db.scalars(
        select(CRMOportunidad)
        .options(selectinload(CRMOportunidad.contacto))
        .where(
            CRMOportunidad.empresa_id == empresa_id,
            CRMOportunidad.cliente_id == client_id,
        )
        .order_by(desc(CRMOportunidad.updated_at), desc(CRMOportunidad.id))
    ).all()
    activities = db.scalars(
        select(CRMActividad)
        .options(
            selectinload(CRMActividad.contacto),
            selectinload(CRMActividad.oportunidad),
        )
        .where(
            CRMActividad.empresa_id == empresa_id,
            CRMActividad.cliente_id == client_id,
            CRMActividad.activo == True,
        )
        .order_by(desc(CRMActividad.fecha_actividad), desc(CRMActividad.id))
    ).all()
    invoice_sales = db.scalars(
        select(Venta)
        .where(
            Venta.empresa_id == empresa_id,
            Venta.factura_estado != "no_solicitada",
            or_(
                Venta.factura_crm_cliente_id == client_id,
                and_(Venta.factura_crm_cliente_id.is_(None), Venta.crm_cliente_id == client_id),
            ),
        )
        .order_by(desc(func.coalesce(Venta.factura_solicitada_at, Venta.paid_at, Venta.created_at)), desc(Venta.id))
    ).all()

    items: list[CRMClientTimelineItem] = []

    for sale in sales:
        items.append(
            CRMClientTimelineItem(
                tipo="venta_pos",
                fecha=sale.paid_at or sale.created_at,
                titulo=f"Venta POS {sale.folio}",
                descripcion=sale.notas or sale.cliente_nombre,
                monto=Decimal(sale.total or ZERO),
                estatus=sale.estatus,
                referencia_id=sale.id,
            )
        )

    for project in projects:
        items.append(
            CRMClientTimelineItem(
                tipo="proyecto_pm",
                fecha=project.updated_at,
                titulo=f"Proyecto PM {project.nombre}",
                descripcion=project.codigo or project.descripcion,
                monto=Decimal(project.presupuesto_estimado or ZERO),
                estatus=project.estatus,
                referencia_id=project.id,
            )
        )

    for opportunity in opportunities:
        items.append(
            CRMClientTimelineItem(
                tipo="oportunidad",
                fecha=opportunity.updated_at,
                titulo=opportunity.titulo,
                descripcion=opportunity.descripcion or (opportunity.contacto.nombre if opportunity.contacto else None),
                monto=Decimal(opportunity.monto_estimado or ZERO),
                estatus=opportunity.etapa,
                referencia_id=opportunity.id,
            )
        )

    for activity in activities:
        items.append(
            CRMClientTimelineItem(
                tipo="actividad",
                fecha=activity.fecha_actividad,
                titulo=activity.titulo,
                descripcion=activity.descripcion or activity.tipo,
                monto=None,
                estatus="completada" if activity.completada else "pendiente",
                referencia_id=activity.id,
            )
        )

    for sale in invoice_sales:
        items.append(
            CRMClientTimelineItem(
                tipo="solicitud_factura_pos",
                fecha=sale.factura_solicitada_at or sale.paid_at or sale.created_at,
                titulo=f"Solicitud de factura {sale.folio}",
                descripcion=sale.factura_razon_social or sale.factura_rfc or sale.factura_email,
                monto=Decimal(sale.total or ZERO),
                estatus=resolve_invoice_request_display_status(sale),
                referencia_id=sale.id,
            )
        )

    items.sort(key=lambda item: (item.fecha, item.referencia_id), reverse=True)
    return CRMClientTimelineResponse(items=items)


def get_client_commercial_summary(
    db: Session,
    empresa_id: str,
    client_id: str,
) -> CRMClientCommercialSummaryResponse:
    get_client_for_company(db, empresa_id, client_id)

    total_ventas_pos = db.scalar(
        select(func.coalesce(func.sum(Venta.total), 0)).where(
            Venta.empresa_id == empresa_id,
            Venta.crm_cliente_id == client_id,
            Venta.estatus == "pagada",
        )
    ) or ZERO
    ventas_count = db.scalar(
        select(func.count(Venta.id)).where(
            Venta.empresa_id == empresa_id,
            Venta.crm_cliente_id == client_id,
            Venta.estatus == "pagada",
        )
    ) or 0
    proyectos_count = db.scalar(
        select(func.count(PMProyecto.id)).where(
            PMProyecto.empresa_id == empresa_id,
            PMProyecto.crm_cliente_id == client_id,
        )
    ) or 0
    proyectos_activos = db.scalar(
        select(func.count(PMProyecto.id)).where(
            PMProyecto.empresa_id == empresa_id,
            PMProyecto.crm_cliente_id == client_id,
            PMProyecto.activo == True,
            PMProyecto.estatus.not_in(["completado", "cancelado"]),
        )
    ) or 0
    oportunidades_abiertas = db.scalar(
        select(func.count(CRMOportunidad.id)).where(
            CRMOportunidad.empresa_id == empresa_id,
            CRMOportunidad.cliente_id == client_id,
            CRMOportunidad.activa == True,
        )
    ) or 0
    monto_pipeline = db.scalar(
        select(func.coalesce(func.sum(CRMOportunidad.monto_estimado), 0)).where(
            CRMOportunidad.empresa_id == empresa_id,
            CRMOportunidad.cliente_id == client_id,
            CRMOportunidad.activa == True,
        )
    ) or ZERO
    facturas_solicitadas = db.scalar(
        select(func.count(Venta.id)).where(
            Venta.empresa_id == empresa_id,
            Venta.factura_estado != "no_solicitada",
            or_(
                Venta.factura_crm_cliente_id == client_id,
                and_(Venta.factura_crm_cliente_id.is_(None), Venta.crm_cliente_id == client_id),
            ),
        )
    ) or 0
    actividades_pendientes = db.scalar(
        select(func.count(CRMActividad.id)).where(
            CRMActividad.empresa_id == empresa_id,
            CRMActividad.cliente_id == client_id,
            CRMActividad.activo == True,
            CRMActividad.completada == False,
        )
    ) or 0
    ultima_actividad_at = db.scalar(
        select(func.max(CRMActividad.fecha_actividad)).where(
            CRMActividad.empresa_id == empresa_id,
            CRMActividad.cliente_id == client_id,
            CRMActividad.activo == True,
        )
    )

    return CRMClientCommercialSummaryResponse(
        client_id=client_id,
        total_ventas_pos=Decimal(total_ventas_pos or ZERO),
        ventas_count=int(ventas_count),
        proyectos_count=int(proyectos_count),
        proyectos_activos=int(proyectos_activos),
        oportunidades_abiertas=int(oportunidades_abiertas),
        monto_pipeline=Decimal(monto_pipeline or ZERO),
        facturas_solicitadas=int(facturas_solicitadas),
        actividades_pendientes=int(actividades_pendientes),
        ultima_actividad_at=ultima_actividad_at,
    )
