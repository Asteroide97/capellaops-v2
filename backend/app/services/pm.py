from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.models import AuditLog, EmpresaUsuario, Usuario
from app.models.pm import (
    EmpresaPMConfig,
    PMChecklistItem,
    PMComentario,
    PMProyecto,
    PMProyectoMiembro,
    PMSubtarea,
    PMTarea,
)
from app.schemas.pm import (
    PMChecklistItemOut,
    PMCommentOut,
    PMConfigOut,
    PMDashboardDueItem,
    PMDashboardKpis,
    PMDashboardOut,
    PMProjectMembersListResponse,
    PMProyectoMiembroOut,
    PMProyectoOut,
    PMProyectoListResponse,
    PMStatusCount,
    PMSubtareaOut,
    PMTaskStats,
    PMTareaListItem,
    PMTareaListResponse,
    PMTareaOut,
)
from app.services.access import can_access_module


ALLOWED_PROJECT_STATUS = {"borrador", "activo", "en_pausa", "completado", "cancelado"}
ALLOWED_TASK_STATUS = {"pendiente", "en_progreso", "en_revision", "completada", "cancelada"}
ALLOWED_PRIORITY = {"baja", "media", "alta", "critica"}
ALLOWED_MEMBER_ROLE = {"lider", "colaborador", "observador"}
SUBTASK_STATUS = {"pendiente", "completada"}
ZERO = Decimal("0")


@dataclass
class PMContext:
    user: Usuario
    empresa_id: str
    membership_role: str
    config: EmpresaPMConfig


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def today_utc() -> date:
    return utcnow().date()


def decimal_or_zero(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(value or ZERO)


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_required_text(value: str, field_name: str) -> str:
    cleaned = normalize_optional_text(value)
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} obligatorio.")
    return cleaned


def normalize_email(value: str | None) -> str | None:
    cleaned = normalize_optional_text(value)
    return cleaned.lower() if cleaned else None


def normalize_code(value: str | None) -> str | None:
    cleaned = normalize_optional_text(value)
    return cleaned.upper().replace(" ", "-") if cleaned else None


def normalize_project_status(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Estatus").lower()
    if normalized not in ALLOWED_PROJECT_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estatus de proyecto invalido.")
    return normalized


def normalize_task_status(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Estatus").lower()
    if normalized not in ALLOWED_TASK_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estatus de tarea invalido.")
    return normalized


def normalize_priority(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Prioridad").lower()
    if normalized not in ALLOWED_PRIORITY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prioridad invalida.")
    return normalized


def normalize_member_role(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Rol").lower()
    if normalized not in ALLOWED_MEMBER_ROLE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol de proyecto invalido.")
    return normalized


def normalize_subtask_status(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Estatus").lower()
    if normalized not in SUBTASK_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estatus de subtarea invalido.")
    return normalized


def quantize_percentage(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_status_counts(rows: list[tuple[str, int]], allowed_values: set[str]) -> list[PMStatusCount]:
    totals = {status_name: count for status_name, count in rows}
    return [PMStatusCount(estatus=value, total=totals.get(value, 0)) for value in sorted(allowed_values)]


def get_or_create_pm_config(db: Session, empresa_id: str) -> tuple[EmpresaPMConfig, bool]:
    config = db.scalar(select(EmpresaPMConfig).where(EmpresaPMConfig.empresa_id == empresa_id))
    if config:
        return config, False

    config = EmpresaPMConfig(
        empresa_id=empresa_id,
        pm_enabled=True,
        pm_tareas_enabled=True,
        pm_materiales_enabled=False,
        pm_tiempo_enabled=False,
        pm_templates_enabled=False,
        pm_comercial_enabled=False,
        pm_portal_enabled=False,
    )
    db.add(config)
    db.flush()
    return config, True


def get_pm_context(db: Session, context: TenantContext) -> PMContext:
    if not can_access_module(context.user, context.empresa, "pm"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La empresa no tiene acceso al modulo PM.",
        )

    config, created = get_or_create_pm_config(db, context.empresa.id)
    if created:
        db.commit()
        db.refresh(config)

    if not config.pm_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PM esta deshabilitado para la empresa activa.",
        )

    return PMContext(
        user=context.user,
        empresa_id=context.empresa.id,
        membership_role=context.membership.role,
        config=config,
    )


def ensure_pm_tasks_enabled(pm_context: PMContext) -> None:
    if not pm_context.config.pm_tareas_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Las tareas de PM estan deshabilitadas para la empresa activa.",
        )


def get_company_member_by_user_id(db: Session, empresa_id: str, user_id: str | None) -> Usuario | None:
    if not user_id:
        return None
    row = db.execute(
        select(Usuario)
        .join(EmpresaUsuario, EmpresaUsuario.usuario_id == Usuario.id)
        .where(
            Usuario.id == user_id,
            EmpresaUsuario.empresa_id == empresa_id,
            EmpresaUsuario.is_active == True,
            Usuario.is_active == True,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario asignado no pertenece a la empresa activa.",
        )
    return row


def get_company_member_by_email(db: Session, empresa_id: str, email: str | None) -> Usuario | None:
    if not email:
        return None
    return db.execute(
        select(Usuario)
        .join(EmpresaUsuario, EmpresaUsuario.usuario_id == Usuario.id)
        .where(
            Usuario.email == email,
            EmpresaUsuario.empresa_id == empresa_id,
            EmpresaUsuario.is_active == True,
            Usuario.is_active == True,
        )
    ).scalar_one_or_none()


def get_project_for_company(db: Session, empresa_id: str, project_id: str) -> PMProyecto:
    project = db.scalar(
        select(PMProyecto).where(
            PMProyecto.id == project_id,
            PMProyecto.empresa_id == empresa_id,
        )
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    return project


def get_task_for_company(db: Session, empresa_id: str, task_id: str) -> PMTarea:
    task = db.scalar(
        select(PMTarea).where(
            PMTarea.id == task_id,
            PMTarea.empresa_id == empresa_id,
        )
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada.")
    return task


def get_project_member_for_company(db: Session, empresa_id: str, member_id: str) -> PMProyectoMiembro:
    member = db.scalar(
        select(PMProyectoMiembro).where(
            PMProyectoMiembro.id == member_id,
            PMProyectoMiembro.empresa_id == empresa_id,
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro de proyecto no encontrado.")
    return member


def get_subtask_for_company(db: Session, empresa_id: str, subtask_id: str) -> PMSubtarea:
    subtask = db.scalar(
        select(PMSubtarea).where(
            PMSubtarea.id == subtask_id,
            PMSubtarea.empresa_id == empresa_id,
        )
    )
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtarea no encontrada.")
    return subtask


def get_checklist_item_for_company(db: Session, empresa_id: str, item_id: str) -> PMChecklistItem:
    item = db.scalar(
        select(PMChecklistItem).where(
            PMChecklistItem.id == item_id,
            PMChecklistItem.empresa_id == empresa_id,
        )
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento de checklist no encontrado.")
    return item


def ensure_unique_project_code(db: Session, empresa_id: str, codigo: str | None, project_id: str | None = None) -> str | None:
    normalized = normalize_code(codigo)
    if not normalized:
        return None

    query = select(PMProyecto.id).where(
        PMProyecto.empresa_id == empresa_id,
        PMProyecto.codigo == normalized,
    )
    if project_id:
        query = query.where(PMProyecto.id != project_id)

    if db.scalar(query):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El codigo del proyecto ya existe en esta empresa.",
        )
    return normalized


def build_task_stats(db: Session, empresa_id: str, project_id: str) -> PMTaskStats:
    rows = db.execute(
        select(PMTarea.estatus, func.count(PMTarea.id))
        .where(
            PMTarea.empresa_id == empresa_id,
            PMTarea.proyecto_id == project_id,
            PMTarea.activo == True,
        )
        .group_by(PMTarea.estatus)
    ).all()
    counts = {status_name: count for status_name, count in rows}
    overdue = db.scalar(
        select(func.count(PMTarea.id)).where(
            PMTarea.empresa_id == empresa_id,
            PMTarea.proyecto_id == project_id,
            PMTarea.activo == True,
            PMTarea.estatus.in_(["pendiente", "en_progreso", "en_revision"]),
            PMTarea.fecha_vencimiento.is_not(None),
            PMTarea.fecha_vencimiento < today_utc(),
        )
    ) or 0
    total = sum(counts.values())
    return PMTaskStats(
        total=total,
        pendientes=counts.get("pendiente", 0),
        en_progreso=counts.get("en_progreso", 0),
        en_revision=counts.get("en_revision", 0),
        completadas=counts.get("completada", 0),
        canceladas=counts.get("cancelada", 0),
        vencidas=overdue,
    )


def recalculate_project_progress(db: Session, project: PMProyecto) -> Decimal:
    total_tasks = db.scalar(
        select(func.count(PMTarea.id)).where(
            PMTarea.empresa_id == project.empresa_id,
            PMTarea.proyecto_id == project.id,
            PMTarea.activo == True,
        )
    ) or 0
    completed_tasks = db.scalar(
        select(func.count(PMTarea.id)).where(
            PMTarea.empresa_id == project.empresa_id,
            PMTarea.proyecto_id == project.id,
            PMTarea.activo == True,
            PMTarea.estatus == "completada",
        )
    ) or 0
    if total_tasks > 0:
        progress = quantize_percentage((Decimal(completed_tasks) / Decimal(total_tasks)) * Decimal("100"))
        project.porcentaje_avance = progress
        return progress
    return decimal_or_zero(project.porcentaje_avance)


def serialize_comment(comment: PMComentario) -> PMCommentOut:
    return PMCommentOut(
        id=comment.id,
        empresa_id=comment.empresa_id,
        proyecto_id=comment.proyecto_id,
        tarea_id=comment.tarea_id,
        body=comment.body,
        created_by=comment.created_by,
        created_by_nombre_snapshot=comment.created_by_nombre_snapshot,
        activo=comment.activo,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def serialize_member(member: PMProyectoMiembro) -> PMProyectoMiembroOut:
    return PMProyectoMiembroOut(
        id=member.id,
        empresa_id=member.empresa_id,
        proyecto_id=member.proyecto_id,
        usuario_id=member.usuario_id,
        email=member.email,
        nombre_snapshot=member.nombre_snapshot,
        rol_en_proyecto=member.rol_en_proyecto,
        activo=member.activo,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def serialize_subtask(subtask: PMSubtarea) -> PMSubtareaOut:
    return PMSubtareaOut(
        id=subtask.id,
        empresa_id=subtask.empresa_id,
        tarea_id=subtask.tarea_id,
        titulo=subtask.titulo,
        estatus=subtask.estatus,
        orden=subtask.orden,
        asignado_user_id=subtask.asignado_user_id,
        activo=subtask.activo,
        created_at=subtask.created_at,
        updated_at=subtask.updated_at,
    )


def serialize_checklist_item(item: PMChecklistItem) -> PMChecklistItemOut:
    return PMChecklistItemOut(
        id=item.id,
        empresa_id=item.empresa_id,
        tarea_id=item.tarea_id,
        titulo=item.titulo,
        completado=item.completado,
        orden=item.orden,
        activo=item.activo,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def serialize_task_list_item(db: Session, task: PMTarea) -> PMTareaListItem:
    subtasks_count = db.scalar(
        select(func.count(PMSubtarea.id)).where(
            PMSubtarea.empresa_id == task.empresa_id,
            PMSubtarea.tarea_id == task.id,
            PMSubtarea.activo == True,
        )
    ) or 0
    checklist_total = db.scalar(
        select(func.count(PMChecklistItem.id)).where(
            PMChecklistItem.empresa_id == task.empresa_id,
            PMChecklistItem.tarea_id == task.id,
            PMChecklistItem.activo == True,
        )
    ) or 0
    checklist_done = db.scalar(
        select(func.count(PMChecklistItem.id)).where(
            PMChecklistItem.empresa_id == task.empresa_id,
            PMChecklistItem.tarea_id == task.id,
            PMChecklistItem.activo == True,
            PMChecklistItem.completado == True,
        )
    ) or 0

    return PMTareaListItem(
        id=task.id,
        empresa_id=task.empresa_id,
        proyecto_id=task.proyecto_id,
        titulo=task.titulo,
        descripcion=task.descripcion,
        estatus=task.estatus,
        prioridad=task.prioridad,
        asignado_user_id=task.asignado_user_id,
        asignado_nombre_snapshot=task.asignado_nombre_snapshot,
        fecha_inicio=task.fecha_inicio,
        fecha_vencimiento=task.fecha_vencimiento,
        fecha_completada=task.fecha_completada,
        estimacion_horas=task.estimacion_horas,
        porcentaje_avance=decimal_or_zero(task.porcentaje_avance),
        orden=task.orden,
        bloqueada=task.bloqueada,
        requiere_materiales=task.requiere_materiales,
        requiere_compra=task.requiere_compra,
        requiere_venta_pos=task.requiere_venta_pos,
        requiere_factura=task.requiere_factura,
        activo=task.activo,
        created_by=task.created_by,
        updated_by=task.updated_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
        subtareas_count=subtasks_count,
        checklist_total=checklist_total,
        checklist_completado=checklist_done,
    )


def serialize_task_detail(db: Session, task: PMTarea) -> PMTareaOut:
    subtasks = db.scalars(
        select(PMSubtarea)
        .where(
            PMSubtarea.empresa_id == task.empresa_id,
            PMSubtarea.tarea_id == task.id,
        )
        .order_by(PMSubtarea.orden.asc(), PMSubtarea.created_at.asc())
    ).all()
    checklist_items = db.scalars(
        select(PMChecklistItem)
        .where(
            PMChecklistItem.empresa_id == task.empresa_id,
            PMChecklistItem.tarea_id == task.id,
        )
        .order_by(PMChecklistItem.orden.asc(), PMChecklistItem.created_at.asc())
    ).all()
    comments = db.scalars(
        select(PMComentario)
        .where(
            PMComentario.empresa_id == task.empresa_id,
            PMComentario.tarea_id == task.id,
            PMComentario.activo == True,
        )
        .order_by(desc(PMComentario.created_at))
    ).all()
    return PMTareaOut(
        **serialize_task_list_item(db, task).model_dump(),
        subtasks=[serialize_subtask(item) for item in subtasks],
        checklist_items=[serialize_checklist_item(item) for item in checklist_items],
        comments=[serialize_comment(item) for item in comments],
    )


def serialize_project(db: Session, project: PMProyecto) -> PMProyectoOut:
    members_count = db.scalar(
        select(func.count(PMProyectoMiembro.id)).where(
            PMProyectoMiembro.empresa_id == project.empresa_id,
            PMProyectoMiembro.proyecto_id == project.id,
            PMProyectoMiembro.activo == True,
        )
    ) or 0
    comments = db.scalars(
        select(PMComentario)
        .where(
            PMComentario.empresa_id == project.empresa_id,
            PMComentario.proyecto_id == project.id,
            PMComentario.tarea_id.is_(None),
            PMComentario.activo == True,
        )
        .order_by(desc(PMComentario.created_at))
        .limit(20)
    ).all()
    return PMProyectoOut(
        id=project.id,
        empresa_id=project.empresa_id,
        nombre=project.nombre,
        codigo=project.codigo,
        descripcion=project.descripcion,
        tipo_proyecto=project.tipo_proyecto,
        estatus=project.estatus,
        prioridad=project.prioridad,
        fecha_inicio=project.fecha_inicio,
        fecha_fin_planificada=project.fecha_fin_planificada,
        fecha_fin_real=project.fecha_fin_real,
        porcentaje_avance=decimal_or_zero(project.porcentaje_avance),
        responsable_user_id=project.responsable_user_id,
        responsable_nombre_snapshot=project.responsable_nombre_snapshot,
        cliente_nombre_snapshot=project.cliente_nombre_snapshot,
        presupuesto_estimado=decimal_or_zero(project.presupuesto_estimado),
        activo=project.activo,
        created_by=project.created_by,
        updated_by=project.updated_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        miembros_activos=members_count,
        task_stats=build_task_stats(db, project.empresa_id, project.id),
        comments=[serialize_comment(item) for item in comments],
    )


def list_projects(
    db: Session,
    pm_context: PMContext,
    *,
    q: str | None = None,
    estatus: str | None = None,
    prioridad: str | None = None,
    activo: bool | None = True,
    limit: int = 25,
    offset: int = 0,
) -> PMProyectoListResponse:
    query = select(PMProyecto).where(PMProyecto.empresa_id == pm_context.empresa_id)
    if activo is not None:
        query = query.where(PMProyecto.activo == activo)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(func.coalesce(PMProyecto.nombre, "")).like(pattern),
                func.lower(func.coalesce(PMProyecto.codigo, "")).like(pattern),
                func.lower(func.coalesce(PMProyecto.descripcion, "")).like(pattern),
                func.lower(func.coalesce(PMProyecto.cliente_nombre_snapshot, "")).like(pattern),
            )
        )
    if estatus:
        query = query.where(PMProyecto.estatus == normalize_project_status(estatus))
    if prioridad:
        query = query.where(PMProyecto.prioridad == normalize_priority(prioridad))

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    projects = db.scalars(
        query.order_by(PMProyecto.fecha_fin_planificada.asc(), PMProyecto.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return PMProyectoListResponse(
        items=[serialize_project(db, project) for project in projects],
        total=total,
        limit=limit,
        offset=offset,
    )


def create_project(
    db: Session,
    pm_context: PMContext,
    *,
    nombre: str,
    codigo: str | None,
    descripcion: str | None,
    tipo_proyecto: str | None,
    estatus: str,
    prioridad: str,
    fecha_inicio: date | None,
    fecha_fin_planificada: date | None,
    fecha_fin_real: date | None,
    porcentaje_avance: Decimal,
    responsable_user_id: str | None,
    responsable_nombre_snapshot: str | None,
    cliente_nombre_snapshot: str | None,
    presupuesto_estimado: Decimal | None,
    activo: bool,
    ip_address: str | None,
) -> PMProyectoOut:
    responsable = get_company_member_by_user_id(db, pm_context.empresa_id, responsable_user_id)
    project = PMProyecto(
        empresa_id=pm_context.empresa_id,
        nombre=normalize_required_text(nombre, "Nombre"),
        codigo=ensure_unique_project_code(db, pm_context.empresa_id, codigo),
        descripcion=normalize_optional_text(descripcion),
        tipo_proyecto=normalize_optional_text(tipo_proyecto),
        estatus=normalize_project_status(estatus),
        prioridad=normalize_priority(prioridad),
        fecha_inicio=fecha_inicio,
        fecha_fin_planificada=fecha_fin_planificada,
        fecha_fin_real=fecha_fin_real,
        porcentaje_avance=quantize_percentage(decimal_or_zero(porcentaje_avance)),
        responsable_user_id=responsable.id if responsable else None,
        responsable_nombre_snapshot=responsable.full_name if responsable else normalize_optional_text(responsable_nombre_snapshot),
        cliente_nombre_snapshot=normalize_optional_text(cliente_nombre_snapshot),
        presupuesto_estimado=decimal_or_zero(presupuesto_estimado),
        activo=activo,
        created_by=pm_context.user.id,
        updated_by=pm_context.user.id,
    )
    db.add(project)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.create",
            entity_name="pm_proyecto",
            entity_id=project.id,
            ip_address=ip_address,
            metadata_json={"codigo": project.codigo, "estatus": project.estatus, "prioridad": project.prioridad},
        )
    )
    return serialize_project(db, project)


def update_project(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    nombre: str | None,
    codigo: str | None,
    descripcion: str | None,
    tipo_proyecto: str | None,
    estatus: str | None,
    prioridad: str | None,
    fecha_inicio: date | None,
    fecha_fin_planificada: date | None,
    fecha_fin_real: date | None,
    porcentaje_avance: Decimal | None,
    responsable_user_id: str | None,
    responsable_nombre_snapshot: str | None,
    cliente_nombre_snapshot: str | None,
    presupuesto_estimado: Decimal | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMProyectoOut:
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    if nombre is not None:
        project.nombre = normalize_required_text(nombre, "Nombre")
    if codigo is not None:
        project.codigo = ensure_unique_project_code(db, pm_context.empresa_id, codigo, project.id)
    if descripcion is not None:
        project.descripcion = normalize_optional_text(descripcion)
    if tipo_proyecto is not None:
        project.tipo_proyecto = normalize_optional_text(tipo_proyecto)
    if estatus is not None:
        project.estatus = normalize_project_status(estatus)
        if project.estatus == "completado" and not project.fecha_fin_real:
            project.fecha_fin_real = today_utc()
    if prioridad is not None:
        project.prioridad = normalize_priority(prioridad)
    if fecha_inicio is not None:
        project.fecha_inicio = fecha_inicio
    if fecha_fin_planificada is not None:
        project.fecha_fin_planificada = fecha_fin_planificada
    if fecha_fin_real is not None:
        project.fecha_fin_real = fecha_fin_real
    if porcentaje_avance is not None:
        project.porcentaje_avance = quantize_percentage(decimal_or_zero(porcentaje_avance))
    if responsable_user_id is not None:
        responsable = get_company_member_by_user_id(db, pm_context.empresa_id, responsable_user_id)
        project.responsable_user_id = responsable.id if responsable else None
        project.responsable_nombre_snapshot = (
            responsable.full_name if responsable else normalize_optional_text(responsable_nombre_snapshot)
        )
    elif responsable_nombre_snapshot is not None:
        project.responsable_nombre_snapshot = normalize_optional_text(responsable_nombre_snapshot)
    if cliente_nombre_snapshot is not None:
        project.cliente_nombre_snapshot = normalize_optional_text(cliente_nombre_snapshot)
    if presupuesto_estimado is not None:
        project.presupuesto_estimado = decimal_or_zero(presupuesto_estimado)
    if activo is not None:
        project.activo = activo
    project.updated_by = pm_context.user.id
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.update",
            entity_name="pm_proyecto",
            entity_id=project.id,
            ip_address=ip_address,
            metadata_json={"codigo": project.codigo, "estatus": project.estatus, "prioridad": project.prioridad},
        )
    )
    db.flush()
    return serialize_project(db, project)


def get_project(db: Session, pm_context: PMContext, project_id: str) -> PMProyectoOut:
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    return serialize_project(db, project)


def deactivate_project(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    ip_address: str | None,
) -> PMProyectoOut:
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    project.activo = False
    project.updated_by = pm_context.user.id
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.deactivate",
            entity_name="pm_proyecto",
            entity_id=project.id,
            ip_address=ip_address,
            metadata_json={"estatus": project.estatus},
        )
    )
    db.flush()
    return serialize_project(db, project)


def list_project_members(db: Session, pm_context: PMContext, project_id: str) -> PMProjectMembersListResponse:
    get_project_for_company(db, pm_context.empresa_id, project_id)
    members = db.scalars(
        select(PMProyectoMiembro)
        .where(
            PMProyectoMiembro.empresa_id == pm_context.empresa_id,
            PMProyectoMiembro.proyecto_id == project_id,
        )
        .order_by(PMProyectoMiembro.activo.desc(), PMProyectoMiembro.created_at.asc())
    ).all()
    return PMProjectMembersListResponse(items=[serialize_member(item) for item in members])


def add_project_member(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    usuario_id: str | None,
    email: str | None,
    nombre_snapshot: str | None,
    rol_en_proyecto: str,
    ip_address: str | None,
) -> PMProyectoMiembroOut:
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    normalized_email = normalize_email(email)
    linked_user = get_company_member_by_user_id(db, pm_context.empresa_id, usuario_id)
    if linked_user is None and normalized_email:
        linked_user = get_company_member_by_email(db, pm_context.empresa_id, normalized_email)

    if linked_user and normalized_email and linked_user.email != normalized_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario y el correo indicado no coinciden.",
        )

    if linked_user is None and normalized_email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes indicar un usuario de empresa o un correo.",
        )

    effective_email = linked_user.email if linked_user else normalized_email
    effective_name = linked_user.full_name if linked_user else normalize_optional_text(nombre_snapshot)
    normalized_role = normalize_member_role(rol_en_proyecto)

    existing = db.scalar(
        select(PMProyectoMiembro).where(
            PMProyectoMiembro.empresa_id == pm_context.empresa_id,
            PMProyectoMiembro.proyecto_id == project.id,
            or_(
                and_(linked_user is not None, PMProyectoMiembro.usuario_id == linked_user.id),
                and_(effective_email is not None, PMProyectoMiembro.email == effective_email),
            ),
        )
    )
    if existing:
        existing.usuario_id = linked_user.id if linked_user else existing.usuario_id
        existing.email = effective_email
        existing.nombre_snapshot = effective_name
        existing.rol_en_proyecto = normalized_role
        existing.activo = True
        member = existing
    else:
        member = PMProyectoMiembro(
            empresa_id=pm_context.empresa_id,
            proyecto_id=project.id,
            usuario_id=linked_user.id if linked_user else None,
            email=effective_email,
            nombre_snapshot=effective_name,
            rol_en_proyecto=normalized_role,
            activo=True,
        )
        db.add(member)

    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.member.upsert",
            entity_name="pm_proyecto_miembro",
            entity_id=member.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id, "email": member.email, "rol": member.rol_en_proyecto},
        )
    )
    return serialize_member(member)


def deactivate_project_member(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    member_id: str,
    ip_address: str | None,
) -> PMProyectoMiembroOut:
    get_project_for_company(db, pm_context.empresa_id, project_id)
    member = get_project_member_for_company(db, pm_context.empresa_id, member_id)
    if member.proyecto_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro de proyecto no encontrado.")
    member.activo = False
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.member.deactivate",
            entity_name="pm_proyecto_miembro",
            entity_id=member.id,
            ip_address=ip_address,
            metadata_json={"project_id": member.proyecto_id, "email": member.email},
        )
    )
    db.flush()
    return serialize_member(member)


def list_tasks(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    q: str | None = None,
    estatus: str | None = None,
    prioridad: str | None = None,
    activo: bool | None = True,
    limit: int = 25,
    offset: int = 0,
) -> PMTareaListResponse:
    ensure_pm_tasks_enabled(pm_context)
    get_project_for_company(db, pm_context.empresa_id, project_id)
    query = select(PMTarea).where(
        PMTarea.empresa_id == pm_context.empresa_id,
        PMTarea.proyecto_id == project_id,
    )
    if activo is not None:
        query = query.where(PMTarea.activo == activo)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(func.coalesce(PMTarea.titulo, "")).like(pattern),
                func.lower(func.coalesce(PMTarea.descripcion, "")).like(pattern),
                func.lower(func.coalesce(PMTarea.asignado_nombre_snapshot, "")).like(pattern),
            )
        )
    if estatus:
        query = query.where(PMTarea.estatus == normalize_task_status(estatus))
    if prioridad:
        query = query.where(PMTarea.prioridad == normalize_priority(prioridad))

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    tasks = db.scalars(
        query.order_by(PMTarea.orden.asc(), PMTarea.fecha_vencimiento.asc(), PMTarea.created_at.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PMTareaListResponse(
        items=[serialize_task_list_item(db, task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


def create_task(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    titulo: str,
    descripcion: str | None,
    estatus: str,
    prioridad: str,
    asignado_user_id: str | None,
    asignado_nombre_snapshot: str | None,
    fecha_inicio: date | None,
    fecha_vencimiento: date | None,
    fecha_completada: date | None,
    estimacion_horas: Decimal | None,
    porcentaje_avance: Decimal,
    orden: int,
    bloqueada: bool,
    requiere_materiales: bool,
    requiere_compra: bool,
    requiere_venta_pos: bool,
    requiere_factura: bool,
    activo: bool,
    ip_address: str | None,
) -> PMTareaOut:
    ensure_pm_tasks_enabled(pm_context)
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    assigned_user = get_company_member_by_user_id(db, pm_context.empresa_id, asignado_user_id)
    normalized_status = normalize_task_status(estatus)
    completed_date = fecha_completada
    if normalized_status == "completada" and completed_date is None:
        completed_date = today_utc()

    task = PMTarea(
        empresa_id=pm_context.empresa_id,
        proyecto_id=project.id,
        titulo=normalize_required_text(titulo, "Titulo"),
        descripcion=normalize_optional_text(descripcion),
        estatus=normalized_status,
        prioridad=normalize_priority(prioridad),
        asignado_user_id=assigned_user.id if assigned_user else None,
        asignado_nombre_snapshot=assigned_user.full_name if assigned_user else normalize_optional_text(asignado_nombre_snapshot),
        fecha_inicio=fecha_inicio,
        fecha_vencimiento=fecha_vencimiento,
        fecha_completada=completed_date,
        estimacion_horas=decimal_or_zero(estimacion_horas),
        porcentaje_avance=Decimal("100") if normalized_status == "completada" else quantize_percentage(decimal_or_zero(porcentaje_avance)),
        orden=orden,
        bloqueada=bloqueada,
        requiere_materiales=requiere_materiales,
        requiere_compra=requiere_compra,
        requiere_venta_pos=requiere_venta_pos,
        requiere_factura=requiere_factura,
        activo=activo,
        created_by=pm_context.user.id,
        updated_by=pm_context.user.id,
    )
    db.add(task)
    db.flush()
    recalculate_project_progress(db, project)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.task.create",
            entity_name="pm_tarea",
            entity_id=task.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id, "estatus": task.estatus, "prioridad": task.prioridad},
        )
    )
    return serialize_task_detail(db, task)


def update_task(
    db: Session,
    pm_context: PMContext,
    *,
    task_id: str,
    titulo: str | None,
    descripcion: str | None,
    estatus: str | None,
    prioridad: str | None,
    asignado_user_id: str | None,
    asignado_nombre_snapshot: str | None,
    fecha_inicio: date | None,
    fecha_vencimiento: date | None,
    fecha_completada: date | None,
    estimacion_horas: Decimal | None,
    porcentaje_avance: Decimal | None,
    orden: int | None,
    bloqueada: bool | None,
    requiere_materiales: bool | None,
    requiere_compra: bool | None,
    requiere_venta_pos: bool | None,
    requiere_factura: bool | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMTareaOut:
    ensure_pm_tasks_enabled(pm_context)
    task = get_task_for_company(db, pm_context.empresa_id, task_id)
    if titulo is not None:
        task.titulo = normalize_required_text(titulo, "Titulo")
    if descripcion is not None:
        task.descripcion = normalize_optional_text(descripcion)
    if estatus is not None:
        task.estatus = normalize_task_status(estatus)
        if task.estatus == "completada" and not task.fecha_completada:
            task.fecha_completada = today_utc()
            task.porcentaje_avance = Decimal("100")
        elif task.estatus != "completada":
            task.fecha_completada = fecha_completada
    if prioridad is not None:
        task.prioridad = normalize_priority(prioridad)
    if asignado_user_id is not None:
        assigned_user = get_company_member_by_user_id(db, pm_context.empresa_id, asignado_user_id)
        task.asignado_user_id = assigned_user.id if assigned_user else None
        task.asignado_nombre_snapshot = assigned_user.full_name if assigned_user else normalize_optional_text(asignado_nombre_snapshot)
    elif asignado_nombre_snapshot is not None:
        task.asignado_nombre_snapshot = normalize_optional_text(asignado_nombre_snapshot)
    if fecha_inicio is not None:
        task.fecha_inicio = fecha_inicio
    if fecha_vencimiento is not None:
        task.fecha_vencimiento = fecha_vencimiento
    if fecha_completada is not None and (estatus is None or task.estatus != "completada"):
        task.fecha_completada = fecha_completada
    if estimacion_horas is not None:
        task.estimacion_horas = decimal_or_zero(estimacion_horas)
    if porcentaje_avance is not None and task.estatus != "completada":
        task.porcentaje_avance = quantize_percentage(decimal_or_zero(porcentaje_avance))
    if orden is not None:
        task.orden = orden
    if bloqueada is not None:
        task.bloqueada = bloqueada
    if requiere_materiales is not None:
        task.requiere_materiales = requiere_materiales
    if requiere_compra is not None:
        task.requiere_compra = requiere_compra
    if requiere_venta_pos is not None:
        task.requiere_venta_pos = requiere_venta_pos
    if requiere_factura is not None:
        task.requiere_factura = requiere_factura
    if activo is not None:
        task.activo = activo
    task.updated_by = pm_context.user.id
    project = get_project_for_company(db, pm_context.empresa_id, task.proyecto_id)
    recalculate_project_progress(db, project)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.task.update",
            entity_name="pm_tarea",
            entity_id=task.id,
            ip_address=ip_address,
            metadata_json={"project_id": task.proyecto_id, "estatus": task.estatus, "prioridad": task.prioridad},
        )
    )
    db.flush()
    return serialize_task_detail(db, task)


def get_task(db: Session, pm_context: PMContext, task_id: str) -> PMTareaOut:
    ensure_pm_tasks_enabled(pm_context)
    task = get_task_for_company(db, pm_context.empresa_id, task_id)
    return serialize_task_detail(db, task)


def deactivate_task(
    db: Session,
    pm_context: PMContext,
    *,
    task_id: str,
    ip_address: str | None,
) -> PMTareaOut:
    ensure_pm_tasks_enabled(pm_context)
    task = get_task_for_company(db, pm_context.empresa_id, task_id)
    task.activo = False
    task.updated_by = pm_context.user.id
    project = get_project_for_company(db, pm_context.empresa_id, task.proyecto_id)
    recalculate_project_progress(db, project)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.task.deactivate",
            entity_name="pm_tarea",
            entity_id=task.id,
            ip_address=ip_address,
            metadata_json={"project_id": task.proyecto_id, "estatus": task.estatus},
        )
    )
    db.flush()
    return serialize_task_detail(db, task)


def create_subtask(
    db: Session,
    pm_context: PMContext,
    *,
    task_id: str,
    titulo: str,
    estatus: str,
    orden: int,
    asignado_user_id: str | None,
    ip_address: str | None,
) -> PMSubtareaOut:
    ensure_pm_tasks_enabled(pm_context)
    task = get_task_for_company(db, pm_context.empresa_id, task_id)
    assigned_user = get_company_member_by_user_id(db, pm_context.empresa_id, asignado_user_id)
    subtask = PMSubtarea(
        empresa_id=pm_context.empresa_id,
        tarea_id=task.id,
        titulo=normalize_required_text(titulo, "Titulo"),
        estatus=normalize_subtask_status(estatus),
        orden=orden,
        asignado_user_id=assigned_user.id if assigned_user else None,
        activo=True,
    )
    db.add(subtask)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.subtask.create",
            entity_name="pm_subtarea",
            entity_id=subtask.id,
            ip_address=ip_address,
            metadata_json={"task_id": task.id, "estatus": subtask.estatus},
        )
    )
    return serialize_subtask(subtask)


def update_subtask(
    db: Session,
    pm_context: PMContext,
    *,
    subtask_id: str,
    titulo: str | None,
    estatus: str | None,
    orden: int | None,
    asignado_user_id: str | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMSubtareaOut:
    ensure_pm_tasks_enabled(pm_context)
    subtask = get_subtask_for_company(db, pm_context.empresa_id, subtask_id)
    if titulo is not None:
        subtask.titulo = normalize_required_text(titulo, "Titulo")
    if estatus is not None:
        subtask.estatus = normalize_subtask_status(estatus)
    if orden is not None:
        subtask.orden = orden
    if asignado_user_id is not None:
        assigned_user = get_company_member_by_user_id(db, pm_context.empresa_id, asignado_user_id)
        subtask.asignado_user_id = assigned_user.id if assigned_user else None
    if activo is not None:
        subtask.activo = activo
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.subtask.update",
            entity_name="pm_subtarea",
            entity_id=subtask.id,
            ip_address=ip_address,
            metadata_json={"task_id": subtask.tarea_id, "estatus": subtask.estatus},
        )
    )
    db.flush()
    return serialize_subtask(subtask)


def create_checklist_item(
    db: Session,
    pm_context: PMContext,
    *,
    task_id: str,
    titulo: str,
    completado: bool,
    orden: int,
    ip_address: str | None,
) -> PMChecklistItemOut:
    ensure_pm_tasks_enabled(pm_context)
    task = get_task_for_company(db, pm_context.empresa_id, task_id)
    item = PMChecklistItem(
        empresa_id=pm_context.empresa_id,
        tarea_id=task.id,
        titulo=normalize_required_text(titulo, "Titulo"),
        completado=completado,
        orden=orden,
        activo=True,
    )
    db.add(item)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.checklist.create",
            entity_name="pm_checklist_item",
            entity_id=item.id,
            ip_address=ip_address,
            metadata_json={"task_id": task.id, "completado": item.completado},
        )
    )
    return serialize_checklist_item(item)


def update_checklist_item(
    db: Session,
    pm_context: PMContext,
    *,
    item_id: str,
    titulo: str | None,
    completado: bool | None,
    orden: int | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMChecklistItemOut:
    ensure_pm_tasks_enabled(pm_context)
    item = get_checklist_item_for_company(db, pm_context.empresa_id, item_id)
    if titulo is not None:
        item.titulo = normalize_required_text(titulo, "Titulo")
    if completado is not None:
        item.completado = completado
    if orden is not None:
        item.orden = orden
    if activo is not None:
        item.activo = activo
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.checklist.update",
            entity_name="pm_checklist_item",
            entity_id=item.id,
            ip_address=ip_address,
            metadata_json={"task_id": item.tarea_id, "completado": item.completado},
        )
    )
    db.flush()
    return serialize_checklist_item(item)


def create_project_comment(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    body: str,
    ip_address: str | None,
) -> PMCommentOut:
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    comment = PMComentario(
        empresa_id=pm_context.empresa_id,
        proyecto_id=project.id,
        tarea_id=None,
        body=normalize_required_text(body, "Comentario"),
        created_by=pm_context.user.id,
        created_by_nombre_snapshot=pm_context.user.full_name,
        activo=True,
    )
    db.add(comment)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.comment.create",
            entity_name="pm_comentario",
            entity_id=comment.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id},
        )
    )
    return serialize_comment(comment)


def create_task_comment(
    db: Session,
    pm_context: PMContext,
    *,
    task_id: str,
    body: str,
    ip_address: str | None,
) -> PMCommentOut:
    task = get_task_for_company(db, pm_context.empresa_id, task_id)
    comment = PMComentario(
        empresa_id=pm_context.empresa_id,
        proyecto_id=task.proyecto_id,
        tarea_id=task.id,
        body=normalize_required_text(body, "Comentario"),
        created_by=pm_context.user.id,
        created_by_nombre_snapshot=pm_context.user.full_name,
        activo=True,
    )
    db.add(comment)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.task.comment.create",
            entity_name="pm_comentario",
            entity_id=comment.id,
            ip_address=ip_address,
            metadata_json={"task_id": task.id, "project_id": task.proyecto_id},
        )
    )
    return serialize_comment(comment)


def get_pm_dashboard(db: Session, pm_context: PMContext) -> PMDashboardOut:
    ensure_pm_tasks_enabled(pm_context)
    today = today_utc()
    upcoming_limit = today + timedelta(days=14)

    active_projects = db.scalar(
        select(func.count(PMProyecto.id)).where(
            PMProyecto.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
            PMProyecto.estatus == "activo",
        )
    ) or 0
    delayed_projects = db.scalar(
        select(func.count(PMProyecto.id)).where(
            PMProyecto.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
            PMProyecto.estatus.in_(["borrador", "activo", "en_pausa"]),
            PMProyecto.fecha_fin_planificada.is_not(None),
            PMProyecto.fecha_fin_planificada < today,
        )
    ) or 0
    overdue_tasks = db.scalar(
        select(func.count(PMTarea.id)).where(
            PMTarea.empresa_id == pm_context.empresa_id,
            PMTarea.activo == True,
            PMTarea.estatus.in_(["pendiente", "en_progreso", "en_revision"]),
            PMTarea.fecha_vencimiento.is_not(None),
            PMTarea.fecha_vencimiento < today,
        )
    ) or 0

    task_rows = db.execute(
        select(PMTarea.estatus, func.count(PMTarea.id))
        .where(
            PMTarea.empresa_id == pm_context.empresa_id,
            PMTarea.activo == True,
        )
        .group_by(PMTarea.estatus)
    ).all()
    task_counts = {status_name: count for status_name, count in task_rows}

    project_rows = db.execute(
        select(PMProyecto.estatus, func.count(PMProyecto.id))
        .where(
            PMProyecto.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
        )
        .group_by(PMProyecto.estatus)
    ).all()

    upcoming_task_rows = db.execute(
        select(PMTarea, PMProyecto)
        .join(PMProyecto, PMProyecto.id == PMTarea.proyecto_id)
        .where(
            PMTarea.empresa_id == pm_context.empresa_id,
            PMTarea.activo == True,
            PMTarea.estatus.in_(["pendiente", "en_progreso", "en_revision"]),
            PMTarea.fecha_vencimiento.is_not(None),
            PMTarea.fecha_vencimiento >= today,
            PMTarea.fecha_vencimiento <= upcoming_limit,
        )
        .order_by(PMTarea.fecha_vencimiento.asc(), PMTarea.prioridad.desc(), PMTarea.created_at.asc())
        .limit(8)
    ).all()

    overdue_task_rows = db.execute(
        select(PMTarea, PMProyecto)
        .join(PMProyecto, PMProyecto.id == PMTarea.proyecto_id)
        .where(
            PMTarea.empresa_id == pm_context.empresa_id,
            PMTarea.activo == True,
            PMTarea.estatus.in_(["pendiente", "en_progreso", "en_revision"]),
            PMTarea.fecha_vencimiento.is_not(None),
            PMTarea.fecha_vencimiento < today,
        )
        .order_by(PMTarea.fecha_vencimiento.asc(), PMTarea.prioridad.desc(), PMTarea.created_at.asc())
        .limit(8)
    ).all()

    upcoming_projects = db.scalars(
        select(PMProyecto)
        .where(
            PMProyecto.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
            PMProyecto.estatus.in_(["borrador", "activo", "en_pausa"]),
            PMProyecto.fecha_fin_planificada.is_not(None),
            PMProyecto.fecha_fin_planificada >= today,
            PMProyecto.fecha_fin_planificada <= upcoming_limit,
        )
        .order_by(PMProyecto.fecha_fin_planificada.asc(), PMProyecto.prioridad.desc(), PMProyecto.created_at.asc())
        .limit(8)
    ).all()

    return PMDashboardOut(
        kpis=PMDashboardKpis(
            proyectos_activos=active_projects,
            proyectos_atrasados=delayed_projects,
            tareas_vencidas=overdue_tasks,
            tareas_pendientes=task_counts.get("pendiente", 0),
            tareas_en_progreso=task_counts.get("en_progreso", 0),
            tareas_completadas=task_counts.get("completada", 0),
        ),
        proyectos_por_estatus=build_status_counts(project_rows, ALLOWED_PROJECT_STATUS),
        tareas_por_estatus=build_status_counts(task_rows, ALLOWED_TASK_STATUS),
        proximos_vencimientos=[
            PMDashboardDueItem(
                project_id=project.id,
                task_id=task.id,
                proyecto_nombre=project.nombre,
                titulo=task.titulo,
                estatus=task.estatus,
                prioridad=task.prioridad,
                fecha=task.fecha_vencimiento,
                responsable_nombre=task.asignado_nombre_snapshot,
            )
            for task, project in upcoming_task_rows
        ],
        proyectos_proximos=[
            PMDashboardDueItem(
                project_id=project.id,
                task_id=None,
                proyecto_nombre=project.nombre,
                titulo=project.nombre,
                estatus=project.estatus,
                prioridad=project.prioridad,
                fecha=project.fecha_fin_planificada,
                responsable_nombre=project.responsable_nombre_snapshot,
            )
            for project in upcoming_projects
        ],
        tareas_vencidas_items=[
            PMDashboardDueItem(
                project_id=project.id,
                task_id=task.id,
                proyecto_nombre=project.nombre,
                titulo=task.titulo,
                estatus=task.estatus,
                prioridad=task.prioridad,
                fecha=task.fecha_vencimiento,
                responsable_nombre=task.asignado_nombre_snapshot,
            )
            for task, project in overdue_task_rows
        ],
    )


def serialize_pm_config(config: EmpresaPMConfig) -> PMConfigOut:
    return PMConfigOut(
        empresa_id=config.empresa_id,
        pm_enabled=config.pm_enabled,
        pm_tareas_enabled=config.pm_tareas_enabled,
        pm_materiales_enabled=config.pm_materiales_enabled,
        pm_tiempo_enabled=config.pm_tiempo_enabled,
        pm_templates_enabled=config.pm_templates_enabled,
        pm_comercial_enabled=config.pm_comercial_enabled,
        pm_portal_enabled=config.pm_portal_enabled,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )
