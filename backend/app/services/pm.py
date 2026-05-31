from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.api.deps import TenantContext
from app.models import AuditLog, EmpresaModulo, EmpresaUsuario, Material, MovimientoInventario, Requisicion, RequisicionDetalle, Usuario
from app.models.pm import (
    EmpresaPMConfig,
    PMChecklistItem,
    PMComentario,
    PMPresupuesto,
    PMPresupuestoIndirecto,
    PMPresupuestoPartida,
    PMPresupuestoPartidaManoObra,
    PMPresupuestoPartidaMaterial,
    PMProyectoCostoResumen,
    PMProyectoMaterialConsumo,
    PMProyectoMaterialPlan,
    PMProyecto,
    PMProyectoMiembro,
    PMTarifaHoraRol,
    PMTarifaHoraUsuario,
    PMSubtarea,
    PMTareaDependencia,
    PMTarea,
    PMTimeEntry,
)
from app.schemas.pm import (
    PMBudgetVsActualOut,
    PMChecklistItemOut,
    PMCommentOut,
    PMConfigOut,
    PMDashboardDueItem,
    PMDashboardProjectCostItem,
    PMDashboardKpis,
    PMDashboardOut,
    PMDashboardUserMetricItem,
    PMCreateProjectRequisitionRequest,
    PMProjectMembersListResponse,
    PMProjectBudgetBundleOut,
    PMProjectCostsOut,
    PMPresupuestoIndirectoOut,
    PMPresupuestoOut,
    PMPresupuestoPartidaManoObraOut,
    PMPresupuestoPartidaMaterialOut,
    PMPresupuestoPartidaOut,
    PMProyectoMaterialConsumoOut,
    PMProyectoMaterialPlanOut,
    PMProyectoMaterialSummaryOut,
    PMProyectoMaterialesOut,
    PMProyectoMiembroOut,
    PMProyectoOut,
    PMProyectoListResponse,
    PMStatusCount,
    PMSubtareaOut,
    PMTarifaHoraRolListResponse,
    PMTarifaHoraRolOut,
    PMTarifaHoraUsuarioListResponse,
    PMTarifaHoraUsuarioOut,
    PMTaskStats,
    PMTaskBlockerOut,
    PMTaskDependenciesOut,
    PMTimeEntryListResponse,
    PMTimeEntryOut,
    PMTareaDependenciaOut,
    PMTareaDependenciaCreate,
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
PM_MATERIAL_PLAN_STATUS = {"planeado", "parcial", "completo", "cancelado"}
PM_MATERIAL_CONSUMPTION_ORIGIN = {"movimiento_manual", "requisicion_surtida", "ajuste_admin"}
PM_RATE_SOURCE = {"usuario", "rol", "manual", "sin_tarifa"}
PM_ALLOWED_RATE_ROLES = {"owner", "admin", "user", "almacenista", "lider", "colaborador", "observador"}
PM_MANAGE_RATES_ROLES = {"owner", "admin"}
PM_BUDGET_STATUS = {"borrador", "aprobado", "sustituido", "cancelado"}
PM_BUDGET_ITEM_TYPES = {"capitulo", "partida"}
PM_BUDGET_INDIRECT_TYPES = {"porcentaje", "monto"}
PM_TASK_DEPENDENCY_TYPES = {"finish_to_start"}
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


def normalize_rate_source(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Fuente de tarifa").lower()
    if normalized not in PM_RATE_SOURCE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fuente de tarifa invalida.")
    return normalized


def normalize_rate_role(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Rol").lower()
    if normalized not in PM_ALLOWED_RATE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol de tarifa invalido.")
    return normalized


def normalize_budget_status(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Estatus").lower()
    if normalized not in PM_BUDGET_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estatus de presupuesto invalido.")
    return normalized


def normalize_budget_item_type(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Tipo").lower()
    if normalized not in PM_BUDGET_ITEM_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de partida invalido.")
    return normalized


def normalize_budget_indirect_type(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Tipo").lower()
    if normalized not in PM_BUDGET_INDIRECT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de indirecto invalido.")
    return normalized


def normalize_task_dependency_type(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Tipo de dependencia").lower()
    if normalized not in PM_TASK_DEPENDENCY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se soporta la dependencia finish_to_start en esta fase.",
        )
    return normalized


def validate_effective_dates(effective_from: date | None, effective_to: date | None) -> None:
    if effective_from and effective_to and effective_to < effective_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La vigencia final no puede ser menor que la vigencia inicial.",
        )


def quantize_percentage(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quantize_money(value: Decimal) -> Decimal:
    return decimal_or_zero(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quantize_rate(value: Decimal) -> Decimal:
    return decimal_or_zero(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


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
        pm_materiales_enabled=True,
        pm_tiempo_enabled=True,
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


def ensure_pm_materials_enabled(pm_context: PMContext) -> None:
    if not pm_context.config.pm_materiales_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Los materiales de PM estan deshabilitados para la empresa activa.",
        )


def ensure_pm_time_enabled(pm_context: PMContext) -> None:
    if not pm_context.config.pm_tiempo_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El registro de tiempo de PM esta deshabilitado para la empresa activa.",
        )


def ensure_pm_rates_manage_access(pm_context: PMContext) -> None:
    if pm_context.membership_role not in PM_MANAGE_RATES_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo owner o admin pueden configurar tarifas PM.",
        )


def ensure_pm_budget_manage_access(pm_context: PMContext) -> None:
    if pm_context.membership_role not in PM_MANAGE_RATES_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo owner o admin pueden gestionar presupuestos PM.",
        )


def ensure_can_manage_time_entry(pm_context: PMContext, entry: PMTimeEntry) -> None:
    if pm_context.membership_role in PM_MANAGE_RATES_ROLES:
        return
    if entry.usuario_id == pm_context.user.id or entry.created_by == pm_context.user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permiso para modificar este registro de horas.",
    )


def is_pm_materials_enabled_for_company(db: Session, empresa_id: str) -> bool:
    module_enabled = db.scalar(
        select(EmpresaModulo.is_enabled).where(
            EmpresaModulo.empresa_id == empresa_id,
            EmpresaModulo.module_name == "pm",
        )
    )
    if not module_enabled:
        return False

    config, created = get_or_create_pm_config(db, empresa_id)
    if created:
        config.pm_materiales_enabled = True
        db.flush()
    return bool(config.pm_enabled and config.pm_materiales_enabled)


def is_pm_time_enabled_for_company(db: Session, empresa_id: str) -> bool:
    module_enabled = db.scalar(
        select(EmpresaModulo.is_enabled).where(
            EmpresaModulo.empresa_id == empresa_id,
            EmpresaModulo.module_name == "pm",
        )
    )
    if not module_enabled:
        return False

    config, created = get_or_create_pm_config(db, empresa_id)
    if created:
        config.pm_tiempo_enabled = True
        db.flush()
    return bool(config.pm_enabled and config.pm_tiempo_enabled)


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


def get_task_dependency_for_company(db: Session, empresa_id: str, dependency_id: str) -> PMTareaDependencia:
    dependency = db.scalar(
        select(PMTareaDependencia).where(
            PMTareaDependencia.id == dependency_id,
            PMTareaDependencia.empresa_id == empresa_id,
        )
    )
    if not dependency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependencia de tarea no encontrada.")
    return dependency


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


def get_budget_for_company(db: Session, empresa_id: str, budget_id: str) -> PMPresupuesto:
    budget = db.scalar(
        select(PMPresupuesto).where(
            PMPresupuesto.id == budget_id,
            PMPresupuesto.empresa_id == empresa_id,
        )
    )
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado.")
    return budget


def get_budget_item_for_company(db: Session, empresa_id: str, item_id: str) -> PMPresupuestoPartida:
    item = db.scalar(
        select(PMPresupuestoPartida).where(
            PMPresupuestoPartida.id == item_id,
            PMPresupuestoPartida.empresa_id == empresa_id,
        )
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partida de presupuesto no encontrada.")
    return item


def get_budget_item_material_for_company(db: Session, empresa_id: str, component_id: str) -> PMPresupuestoPartidaMaterial:
    component = db.scalar(
        select(PMPresupuestoPartidaMaterial).where(
            PMPresupuestoPartidaMaterial.id == component_id,
            PMPresupuestoPartidaMaterial.empresa_id == empresa_id,
        )
    )
    if not component:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Componente de material no encontrado.")
    return component


def get_budget_item_labor_for_company(db: Session, empresa_id: str, component_id: str) -> PMPresupuestoPartidaManoObra:
    component = db.scalar(
        select(PMPresupuestoPartidaManoObra).where(
            PMPresupuestoPartidaManoObra.id == component_id,
            PMPresupuestoPartidaManoObra.empresa_id == empresa_id,
        )
    )
    if not component:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Componente de mano de obra no encontrado.")
    return component


def get_budget_indirect_for_company(db: Session, empresa_id: str, indirect_id: str) -> PMPresupuestoIndirecto:
    indirect = db.scalar(
        select(PMPresupuestoIndirecto).where(
            PMPresupuestoIndirecto.id == indirect_id,
            PMPresupuestoIndirecto.empresa_id == empresa_id,
        )
    )
    if not indirect:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Indirecto de presupuesto no encontrado.")
    return indirect


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


def serialize_task_dependency(
    db: Session,
    dependency: PMTareaDependencia,
    *,
    successor_task: PMTarea | None = None,
    prerequisite_task: PMTarea | None = None,
) -> PMTareaDependenciaOut:
    successor = successor_task or get_task_for_company(db, dependency.empresa_id, dependency.tarea_id)
    prerequisite = prerequisite_task or get_task_for_company(db, dependency.empresa_id, dependency.depende_de_tarea_id)
    return PMTareaDependenciaOut(
        id=dependency.id,
        empresa_id=dependency.empresa_id,
        proyecto_id=dependency.proyecto_id,
        tarea_id=dependency.tarea_id,
        tarea_titulo=successor.titulo,
        depende_de_tarea_id=dependency.depende_de_tarea_id,
        depende_de_tarea_titulo=prerequisite.titulo,
        depende_de_tarea_estatus=prerequisite.estatus,
        tipo_dependencia=dependency.tipo_dependencia,
        lag_dias=dependency.lag_dias,
        bloqueante=dependency.bloqueante,
        notas=dependency.notas,
        activo=dependency.activo,
        created_by=dependency.created_by,
        created_at=dependency.created_at,
        updated_at=dependency.updated_at,
    )


def build_task_blocker(task: PMTarea) -> PMTaskBlockerOut:
    return PMTaskBlockerOut(
        tarea_id=task.id,
        titulo=task.titulo,
        estatus=task.estatus,
    )


def get_task_dependency_counts(db: Session, empresa_id: str, task_id: str) -> tuple[int, int]:
    dependencies_count = db.scalar(
        select(func.count(PMTareaDependencia.id)).where(
            PMTareaDependencia.empresa_id == empresa_id,
            PMTareaDependencia.tarea_id == task_id,
            PMTareaDependencia.activo == True,
        )
    ) or 0
    successors_count = db.scalar(
        select(func.count(PMTareaDependencia.id)).where(
            PMTareaDependencia.empresa_id == empresa_id,
            PMTareaDependencia.depende_de_tarea_id == task_id,
            PMTareaDependencia.activo == True,
        )
    ) or 0
    return dependencies_count, successors_count


def get_task_blockers(db: Session, empresa_id: str, task_id: str) -> list[PMTaskBlockerOut]:
    prerequisite_task = aliased(PMTarea)
    rows = db.execute(
        select(prerequisite_task)
        .join(
            PMTareaDependencia,
            PMTareaDependencia.depende_de_tarea_id == prerequisite_task.id,
        )
        .where(
            PMTareaDependencia.empresa_id == empresa_id,
            PMTareaDependencia.tarea_id == task_id,
            PMTareaDependencia.activo == True,
            PMTareaDependencia.bloqueante == True,
            prerequisite_task.estatus != "completada",
        )
        .order_by(prerequisite_task.orden.asc(), prerequisite_task.created_at.asc())
    ).scalars().all()
    return [build_task_blocker(task) for task in rows]


def list_dependencies_for_task(
    db: Session,
    *,
    empresa_id: str,
    task_id: str,
) -> list[PMTareaDependenciaOut]:
    prerequisite_task = aliased(PMTarea)
    successor_task = aliased(PMTarea)
    rows = db.execute(
        select(PMTareaDependencia, successor_task, prerequisite_task)
        .join(successor_task, successor_task.id == PMTareaDependencia.tarea_id)
        .join(prerequisite_task, prerequisite_task.id == PMTareaDependencia.depende_de_tarea_id)
        .where(
            PMTareaDependencia.empresa_id == empresa_id,
            PMTareaDependencia.tarea_id == task_id,
            PMTareaDependencia.activo == True,
        )
        .order_by(prerequisite_task.orden.asc(), prerequisite_task.created_at.asc())
    ).all()
    return [
        serialize_task_dependency(
            db,
            dependency,
            successor_task=successor,
            prerequisite_task=prerequisite,
        )
        for dependency, successor, prerequisite in rows
    ]


def list_task_successors(
    db: Session,
    *,
    empresa_id: str,
    task_id: str,
) -> list[PMTaskBlockerOut]:
    successor_task = aliased(PMTarea)
    rows = db.execute(
        select(successor_task)
        .join(PMTareaDependencia, PMTareaDependencia.tarea_id == successor_task.id)
        .where(
            PMTareaDependencia.empresa_id == empresa_id,
            PMTareaDependencia.depende_de_tarea_id == task_id,
            PMTareaDependencia.activo == True,
            successor_task.activo == True,
        )
        .order_by(successor_task.orden.asc(), successor_task.created_at.asc())
    ).scalars().all()
    return [build_task_blocker(task) for task in rows]


def is_task_blocked(db: Session, empresa_id: str, task_id: str, manual_flag: bool = False) -> bool:
    return manual_flag or len(get_task_blockers(db, empresa_id, task_id)) > 0


def build_task_dependencies_payload(db: Session, task: PMTarea) -> PMTaskDependenciesOut:
    blockers = get_task_blockers(db, task.empresa_id, task.id)
    dependencies = list_dependencies_for_task(db, empresa_id=task.empresa_id, task_id=task.id)
    successors = list_task_successors(db, empresa_id=task.empresa_id, task_id=task.id)
    dependencies_count, successors_count = get_task_dependency_counts(db, task.empresa_id, task.id)
    return PMTaskDependenciesOut(
        task_id=task.id,
        is_blocked=bool(task.bloqueada or blockers),
        dependencies_count=dependencies_count,
        blockers_count=len(blockers),
        successors_count=successors_count,
        dependencies=dependencies,
        blockers=blockers,
        successors=successors,
    )


def validate_task_status_transition(db: Session, task: PMTarea, new_status: str) -> None:
    if new_status not in {"en_progreso", "en_revision", "completada"}:
        return
    blockers = get_task_blockers(db, task.empresa_id, task.id)
    if not blockers:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": "No puedes avanzar esta tarea porque tiene prerrequisitos pendientes.",
            "blockers": [blocker.model_dump() for blocker in blockers],
        },
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
    dependencies_payload = build_task_dependencies_payload(db, task)

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
        is_blocked=dependencies_payload.is_blocked,
        blockers_count=dependencies_payload.blockers_count,
        dependencies_count=dependencies_payload.dependencies_count,
        successors_count=dependencies_payload.successors_count,
        blockers=dependencies_payload.blockers,
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
    dependencies_payload = build_task_dependencies_payload(db, task)
    return PMTareaOut(
        **serialize_task_list_item(db, task).model_dump(),
        subtasks=[serialize_subtask(item) for item in subtasks],
        checklist_items=[serialize_checklist_item(item) for item in checklist_items],
        comments=[serialize_comment(item) for item in comments],
        dependencies=dependencies_payload.dependencies,
        successors=dependencies_payload.successors,
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


def list_task_dependencies(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
) -> list[PMTareaDependenciaOut]:
    ensure_pm_tasks_enabled(pm_context)
    get_project_for_company(db, pm_context.empresa_id, project_id)
    prerequisite_task = aliased(PMTarea)
    successor_task = aliased(PMTarea)
    rows = db.execute(
        select(PMTareaDependencia, successor_task, prerequisite_task)
        .join(successor_task, successor_task.id == PMTareaDependencia.tarea_id)
        .join(prerequisite_task, prerequisite_task.id == PMTareaDependencia.depende_de_tarea_id)
        .where(
            PMTareaDependencia.empresa_id == pm_context.empresa_id,
            PMTareaDependencia.proyecto_id == project_id,
            PMTareaDependencia.activo == True,
        )
        .order_by(successor_task.orden.asc(), prerequisite_task.orden.asc(), PMTareaDependencia.created_at.asc())
    ).all()
    return [
        serialize_task_dependency(
            db,
            dependency,
            successor_task=successor,
            prerequisite_task=prerequisite,
        )
        for dependency, successor, prerequisite in rows
    ]


def get_task_dependencies(
    db: Session,
    pm_context: PMContext,
    *,
    task_id: str,
) -> PMTaskDependenciesOut:
    ensure_pm_tasks_enabled(pm_context)
    task = get_task_for_company(db, pm_context.empresa_id, task_id)
    return build_task_dependencies_payload(db, task)


def would_create_task_dependency_cycle(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    successor_task_id: str,
    prerequisite_task_id: str,
) -> bool:
    if successor_task_id == prerequisite_task_id:
        return True
    rows = db.execute(
        select(PMTareaDependencia.tarea_id, PMTareaDependencia.depende_de_tarea_id).where(
            PMTareaDependencia.empresa_id == empresa_id,
            PMTareaDependencia.proyecto_id == project_id,
            PMTareaDependencia.activo == True,
        )
    ).all()
    adjacency: dict[str, set[str]] = {}
    for successor_id, dependency_id in rows:
        adjacency.setdefault(dependency_id, set()).add(successor_id)

    stack = [successor_task_id]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for next_task_id in adjacency.get(current, set()):
            if next_task_id == prerequisite_task_id:
                return True
            stack.append(next_task_id)
    return False


def create_task_dependency(
    db: Session,
    pm_context: PMContext,
    *,
    task_id: str,
    depende_de_tarea_id: str,
    tipo_dependencia: str,
    lag_dias: int,
    bloqueante: bool,
    notas: str | None,
    ip_address: str | None,
) -> PMTaskDependenciesOut:
    ensure_pm_tasks_enabled(pm_context)
    task = get_task_for_company(db, pm_context.empresa_id, task_id)
    prerequisite_task = get_task_for_company(db, pm_context.empresa_id, depende_de_tarea_id)
    if task.proyecto_id != prerequisite_task.proyecto_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El prerrequisito debe pertenecer al mismo proyecto.",
        )
    if task.id == prerequisite_task.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una tarea no puede depender de si misma.",
        )
    normalized_type = normalize_task_dependency_type(tipo_dependencia)
    duplicate = db.scalar(
        select(PMTareaDependencia.id).where(
            PMTareaDependencia.empresa_id == pm_context.empresa_id,
            PMTareaDependencia.proyecto_id == task.proyecto_id,
            PMTareaDependencia.tarea_id == task.id,
            PMTareaDependencia.depende_de_tarea_id == prerequisite_task.id,
            PMTareaDependencia.activo == True,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta tarea ya tiene ese prerrequisito activo.",
        )
    if would_create_task_dependency_cycle(
        db,
        empresa_id=pm_context.empresa_id,
        project_id=task.proyecto_id,
        successor_task_id=task.id,
        prerequisite_task_id=prerequisite_task.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La dependencia crea un ciclo entre tareas.",
        )

    dependency = PMTareaDependencia(
        empresa_id=pm_context.empresa_id,
        proyecto_id=task.proyecto_id,
        tarea_id=task.id,
        depende_de_tarea_id=prerequisite_task.id,
        tipo_dependencia=normalized_type,
        lag_dias=max(0, lag_dias),
        bloqueante=bloqueante,
        notas=normalize_optional_text(notas),
        activo=True,
        created_by=pm_context.user.id,
    )
    db.add(dependency)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.task_dependency.create",
            entity_name="pm_tarea_dependencia",
            entity_id=dependency.id,
            ip_address=ip_address,
            metadata_json={
                "project_id": task.proyecto_id,
                "task_id": task.id,
                "depends_on_task_id": prerequisite_task.id,
            },
        )
    )
    return build_task_dependencies_payload(db, task)


def deactivate_task_dependency(
    db: Session,
    pm_context: PMContext,
    *,
    dependency_id: str,
    ip_address: str | None,
) -> PMTaskDependenciesOut:
    ensure_pm_tasks_enabled(pm_context)
    dependency = get_task_dependency_for_company(db, pm_context.empresa_id, dependency_id)
    dependency.activo = False
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.task_dependency.deactivate",
            entity_name="pm_tarea_dependencia",
            entity_id=dependency.id,
            ip_address=ip_address,
            metadata_json={
                "project_id": dependency.proyecto_id,
                "task_id": dependency.tarea_id,
                "depends_on_task_id": dependency.depende_de_tarea_id,
            },
        )
    )
    task = get_task_for_company(db, pm_context.empresa_id, dependency.tarea_id)
    return build_task_dependencies_payload(db, task)


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
        next_status = normalize_task_status(estatus)
        validate_task_status_transition(db, task, next_status)
        task.estatus = next_status
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


def get_project_material_plan_for_company(db: Session, empresa_id: str, plan_id: str) -> PMProyectoMaterialPlan:
    plan = db.scalar(
        select(PMProyectoMaterialPlan).where(
            PMProyectoMaterialPlan.id == plan_id,
            PMProyectoMaterialPlan.empresa_id == empresa_id,
        )
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material planeado no encontrado.")
    return plan


def get_project_material_consumption_for_company(
    db: Session,
    empresa_id: str,
    consumption_id: str,
) -> PMProyectoMaterialConsumo:
    consumption = db.scalar(
        select(PMProyectoMaterialConsumo).where(
            PMProyectoMaterialConsumo.id == consumption_id,
            PMProyectoMaterialConsumo.empresa_id == empresa_id,
        )
    )
    if not consumption:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consumo de material no encontrado.")
    return consumption


def get_time_entry_for_company(db: Session, empresa_id: str, time_entry_id: str) -> PMTimeEntry:
    entry = db.scalar(
        select(PMTimeEntry).where(
            PMTimeEntry.id == time_entry_id,
            PMTimeEntry.empresa_id == empresa_id,
        )
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de horas no encontrado.")
    return entry


def get_user_hourly_rate_for_company(db: Session, empresa_id: str, rate_id: str) -> PMTarifaHoraUsuario:
    rate = db.scalar(
        select(PMTarifaHoraUsuario).where(
            PMTarifaHoraUsuario.id == rate_id,
            PMTarifaHoraUsuario.empresa_id == empresa_id,
        )
    )
    if not rate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarifa por usuario no encontrada.")
    return rate


def get_role_hourly_rate_for_company(db: Session, empresa_id: str, rate_id: str) -> PMTarifaHoraRol:
    rate = db.scalar(
        select(PMTarifaHoraRol).where(
            PMTarifaHoraRol.id == rate_id,
            PMTarifaHoraRol.empresa_id == empresa_id,
        )
    )
    if not rate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarifa por rol no encontrada.")
    return rate


def build_time_entry_role_candidates(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    user_id: str | None,
) -> list[str]:
    if not user_id:
        return []

    roles: list[str] = []
    project_role = db.scalar(
        select(PMProyectoMiembro.rol_en_proyecto).where(
            PMProyectoMiembro.empresa_id == empresa_id,
            PMProyectoMiembro.proyecto_id == project_id,
            PMProyectoMiembro.usuario_id == user_id,
            PMProyectoMiembro.activo == True,
        )
    )
    if project_role:
        roles.append(str(project_role).lower())

    company_role = db.scalar(
        select(EmpresaUsuario.role).where(
            EmpresaUsuario.empresa_id == empresa_id,
            EmpresaUsuario.usuario_id == user_id,
            EmpresaUsuario.is_active == True,
        )
    )
    if company_role and str(company_role).lower() not in roles:
        roles.append(str(company_role).lower())
    return roles


def normalize_material_consumption_origin(value: str | None) -> str:
    normalized = normalize_required_text(value or "", "Origen").lower()
    if normalized not in PM_MATERIAL_CONSUMPTION_ORIGIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Origen de consumo invalido.")
    return normalized


def get_material_for_company_pm(db: Session, empresa_id: str, material_id: str) -> Material:
    material = db.scalar(
        select(Material).where(
            Material.id == material_id,
            Material.empresa_id == empresa_id,
        )
    )
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material no encontrado.")
    return material


def resolve_project_task(
    db: Session,
    empresa_id: str,
    project_id: str,
    task_id: str | None,
) -> PMTarea | None:
    normalized_task_id = normalize_optional_text(task_id)
    if not normalized_task_id:
        return None
    task = get_task_for_company(db, empresa_id, normalized_task_id)
    if task.proyecto_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La tarea indicada no pertenece al proyecto seleccionado.",
        )
    return task


def ensure_unique_project_material_plan(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    material_id: str,
    task_id: str | None,
    exclude_plan_id: str | None = None,
) -> None:
    query = select(PMProyectoMaterialPlan.id).where(
        PMProyectoMaterialPlan.empresa_id == empresa_id,
        PMProyectoMaterialPlan.proyecto_id == project_id,
        PMProyectoMaterialPlan.material_id == material_id,
        PMProyectoMaterialPlan.activo == True,
    )
    if task_id:
        query = query.where(PMProyectoMaterialPlan.tarea_id == task_id)
    else:
        query = query.where(PMProyectoMaterialPlan.tarea_id.is_(None))
    if exclude_plan_id:
        query = query.where(PMProyectoMaterialPlan.id != exclude_plan_id)
    if db.scalar(query):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un material planeado activo para esa combinacion de proyecto, tarea y material.",
        )


def calculate_material_consumed_quantity(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    material_id: str,
    task_id: str | None,
) -> Decimal:
    query = select(func.coalesce(func.sum(PMProyectoMaterialConsumo.cantidad_consumida), 0)).where(
        PMProyectoMaterialConsumo.empresa_id == empresa_id,
        PMProyectoMaterialConsumo.proyecto_id == project_id,
        PMProyectoMaterialConsumo.material_id == material_id,
        PMProyectoMaterialConsumo.activo == True,
    )
    if task_id:
        query = query.where(PMProyectoMaterialConsumo.tarea_id == task_id)
    else:
        query = query.where(PMProyectoMaterialConsumo.tarea_id.is_(None))
    return decimal_or_zero(db.scalar(query))


def resolve_material_plan_status(
    *,
    cantidad_planificada: Decimal,
    cantidad_consumida: Decimal,
    activo: bool,
) -> str:
    if not activo:
        return "cancelado"
    if cantidad_consumida >= cantidad_planificada and cantidad_planificada > ZERO:
        return "completo"
    if cantidad_consumida > ZERO:
        return "parcial"
    return "planeado"


def serialize_project_material_plan(db: Session, plan: PMProyectoMaterialPlan) -> PMProyectoMaterialPlanOut:
    consumed = calculate_material_consumed_quantity(
        db,
        empresa_id=plan.empresa_id,
        project_id=plan.proyecto_id,
        material_id=plan.material_id,
        task_id=plan.tarea_id,
    )
    planned = decimal_or_zero(plan.cantidad_planificada)
    pending = planned - consumed
    if pending < ZERO:
        pending = ZERO
    task_title = None
    if plan.tarea_id:
        task_title = db.scalar(select(PMTarea.titulo).where(PMTarea.id == plan.tarea_id))
    return PMProyectoMaterialPlanOut(
        id=plan.id,
        empresa_id=plan.empresa_id,
        proyecto_id=plan.proyecto_id,
        tarea_id=plan.tarea_id,
        tarea_titulo=task_title,
        material_id=plan.material_id,
        material_nombre_snapshot=plan.material_nombre_snapshot,
        material_sku_snapshot=plan.material_sku_snapshot,
        cantidad_planificada=planned,
        cantidad_consumida_real=consumed,
        cantidad_pendiente=pending,
        unidad=plan.unidad,
        costo_unitario_estimado=decimal_or_zero(plan.costo_unitario_estimado),
        costo_total_estimado=decimal_or_zero(plan.costo_total_estimado),
        estatus=resolve_material_plan_status(
            cantidad_planificada=planned,
            cantidad_consumida=consumed,
            activo=bool(plan.activo),
        ),
        observaciones=plan.observaciones,
        activo=plan.activo,
        created_by=plan.created_by,
        updated_by=plan.updated_by,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def serialize_project_material_consumption(
    db: Session,
    consumption: PMProyectoMaterialConsumo,
) -> PMProyectoMaterialConsumoOut:
    task_title = None
    if consumption.tarea_id:
        task_title = db.scalar(select(PMTarea.titulo).where(PMTarea.id == consumption.tarea_id))
    return PMProyectoMaterialConsumoOut(
        id=consumption.id,
        empresa_id=consumption.empresa_id,
        proyecto_id=consumption.proyecto_id,
        tarea_id=consumption.tarea_id,
        tarea_titulo=task_title,
        material_id=consumption.material_id,
        material_nombre_snapshot=consumption.material_nombre_snapshot,
        material_sku_snapshot=consumption.material_sku_snapshot,
        movimiento_id=consumption.movimiento_id,
        requisicion_id=consumption.requisicion_id,
        requisicion_detalle_id=consumption.requisicion_detalle_id,
        cantidad_consumida=decimal_or_zero(consumption.cantidad_consumida),
        unidad=consumption.unidad,
        costo_unitario_snapshot=decimal_or_zero(consumption.costo_unitario_snapshot),
        costo_total_snapshot=decimal_or_zero(consumption.costo_total_snapshot),
        origen=consumption.origen,
        documento_referencia=consumption.documento_referencia,
        notas=consumption.notas,
        activo=consumption.activo,
        created_by=consumption.created_by,
        created_at=consumption.created_at,
        updated_at=consumption.updated_at,
    )


def get_or_create_project_cost_summary_row(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
) -> PMProyectoCostoResumen:
    summary = db.scalar(
        select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.empresa_id == empresa_id,
            PMProyectoCostoResumen.proyecto_id == project_id,
        )
    )
    if summary is None:
        summary = PMProyectoCostoResumen(
            empresa_id=empresa_id,
            proyecto_id=project_id,
        )
        db.add(summary)
        db.flush()
    return summary


def recalculate_project_cost_summary_totals(
    project: PMProyecto,
    summary: PMProyectoCostoResumen,
) -> None:
    detailed_budget = decimal_or_zero(summary.presupuesto_detallado_costo)
    simple_budget = decimal_or_zero(project.presupuesto_estimado)
    presupuesto = detailed_budget if detailed_budget > ZERO else simple_budget
    summary.presupuesto_estimado = presupuesto
    summary.presupuesto_origen = "detallado" if detailed_budget > ZERO else "simple"
    summary.costo_total_real = decimal_or_zero(summary.costo_materiales_real) + decimal_or_zero(summary.costo_horas_real)
    summary.variacion_presupuesto = presupuesto - decimal_or_zero(summary.costo_total_real)
    summary.variacion_vs_presupuesto_detallado = detailed_budget - decimal_or_zero(summary.costo_total_real)


def refresh_project_material_costs(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
) -> PMProyectoMaterialSummaryOut:
    project = get_project_for_company(db, empresa_id, project_id)
    plans = db.scalars(
        select(PMProyectoMaterialPlan).where(
            PMProyectoMaterialPlan.empresa_id == empresa_id,
            PMProyectoMaterialPlan.proyecto_id == project_id,
            PMProyectoMaterialPlan.activo == True,
        )
    ).all()
    consumptions = db.scalars(
        select(PMProyectoMaterialConsumo).where(
            PMProyectoMaterialConsumo.empresa_id == empresa_id,
            PMProyectoMaterialConsumo.proyecto_id == project_id,
            PMProyectoMaterialConsumo.activo == True,
        )
    ).all()

    total_estimated_cost = ZERO
    total_real_cost = ZERO
    total_planned_quantity = ZERO
    total_consumed_quantity = ZERO
    pending_count = 0
    overconsumed_count = 0

    for plan in plans:
        planned_qty = decimal_or_zero(plan.cantidad_planificada)
        consumed_qty = calculate_material_consumed_quantity(
            db,
            empresa_id=empresa_id,
            project_id=project_id,
            material_id=plan.material_id,
            task_id=plan.tarea_id,
        )
        status_name = resolve_material_plan_status(
            cantidad_planificada=planned_qty,
            cantidad_consumida=consumed_qty,
            activo=bool(plan.activo),
        )
        plan.estatus = status_name

        if consumed_qty < planned_qty:
            pending_count += 1
        if consumed_qty > planned_qty:
            overconsumed_count += 1

        total_estimated_cost += decimal_or_zero(plan.costo_total_estimado)
        total_planned_quantity += planned_qty

    for consumption in consumptions:
        total_real_cost += decimal_or_zero(consumption.costo_total_snapshot)
        total_consumed_quantity += decimal_or_zero(consumption.cantidad_consumida)

    summary = get_or_create_project_cost_summary_row(db, empresa_id=empresa_id, project_id=project_id)
    summary.costo_materiales_estimado = total_estimated_cost
    summary.costo_materiales_real = total_real_cost
    summary.variacion_materiales = total_real_cost - total_estimated_cost
    summary.total_materiales_planeados = total_planned_quantity
    summary.total_materiales_consumidos = total_consumed_quantity
    recalculate_project_cost_summary_totals(project, summary)
    db.flush()

    percentage_consumed = ZERO
    if total_planned_quantity > ZERO:
        percentage_consumed = quantize_percentage((total_consumed_quantity / total_planned_quantity) * Decimal("100"))

    return PMProyectoMaterialSummaryOut(
        costo_estimado=total_estimated_cost,
        costo_real=total_real_cost,
        variacion=total_real_cost - total_estimated_cost,
        porcentaje_consumido=percentage_consumed,
        materiales_pendientes=pending_count,
        materiales_sobreconsumidos=overconsumed_count,
        total_materiales_planeados=total_planned_quantity,
        total_materiales_consumidos=total_consumed_quantity,
        planes_count=len(plans),
        consumos_count=len(consumptions),
    )


def list_project_material_plan(
    db: Session,
    pm_context: PMContext,
    project_id: str,
) -> PMProyectoMaterialesOut:
    ensure_pm_materials_enabled(pm_context)
    get_project_for_company(db, pm_context.empresa_id, project_id)
    summary = refresh_project_material_costs(db, empresa_id=pm_context.empresa_id, project_id=project_id)
    plans = db.scalars(
        select(PMProyectoMaterialPlan)
        .where(
            PMProyectoMaterialPlan.empresa_id == pm_context.empresa_id,
            PMProyectoMaterialPlan.proyecto_id == project_id,
            PMProyectoMaterialPlan.activo == True,
        )
        .order_by(PMProyectoMaterialPlan.created_at.asc(), PMProyectoMaterialPlan.id.asc())
    ).all()
    consumptions = db.scalars(
        select(PMProyectoMaterialConsumo)
        .where(
            PMProyectoMaterialConsumo.empresa_id == pm_context.empresa_id,
            PMProyectoMaterialConsumo.proyecto_id == project_id,
            PMProyectoMaterialConsumo.activo == True,
        )
        .order_by(desc(PMProyectoMaterialConsumo.created_at), desc(PMProyectoMaterialConsumo.id))
    ).all()
    return PMProyectoMaterialesOut(
        summary=summary,
        plans=[serialize_project_material_plan(db, plan) for plan in plans],
        consumptions=[serialize_project_material_consumption(db, item) for item in consumptions],
    )


def add_project_material_plan(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    task_id: str | None,
    material_id: str,
    cantidad_planificada: Decimal,
    costo_unitario_estimado: Decimal | None,
    observaciones: str | None,
    ip_address: str | None,
) -> PMProyectoMaterialPlanOut:
    ensure_pm_materials_enabled(pm_context)
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    task = resolve_project_task(db, pm_context.empresa_id, project.id, task_id)
    material = get_material_for_company_pm(db, pm_context.empresa_id, material_id)
    ensure_unique_project_material_plan(
        db,
        empresa_id=pm_context.empresa_id,
        project_id=project.id,
        material_id=material.id,
        task_id=task.id if task else None,
    )
    estimated_unit_cost = decimal_or_zero(
        costo_unitario_estimado
        if costo_unitario_estimado is not None
        else material.costo_promedio_actual or material.costo_unitario
    )
    planned_quantity = decimal_or_zero(cantidad_planificada)
    plan = PMProyectoMaterialPlan(
        empresa_id=pm_context.empresa_id,
        proyecto_id=project.id,
        tarea_id=task.id if task else None,
        material_id=material.id,
        material_nombre_snapshot=material.nombre,
        material_sku_snapshot=material.sku,
        cantidad_planificada=planned_quantity,
        unidad=material.unidad,
        costo_unitario_estimado=estimated_unit_cost,
        costo_total_estimado=planned_quantity * estimated_unit_cost,
        estatus="planeado",
        observaciones=normalize_optional_text(observaciones),
        activo=True,
        created_by=pm_context.user.id,
        updated_by=pm_context.user.id,
    )
    db.add(plan)
    db.flush()
    refresh_project_material_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.material_plan.create",
            entity_name="pm_proyecto_material_plan",
            entity_id=plan.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id, "material_id": material.id},
        )
    )
    return serialize_project_material_plan(db, plan)


def update_project_material_plan(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    plan_id: str,
    task_id: str | None,
    material_id: str | None,
    cantidad_planificada: Decimal | None,
    costo_unitario_estimado: Decimal | None,
    observaciones: str | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMProyectoMaterialPlanOut:
    ensure_pm_materials_enabled(pm_context)
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    plan = get_project_material_plan_for_company(db, pm_context.empresa_id, plan_id)
    if plan.proyecto_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material planeado no encontrado.")

    next_task = resolve_project_task(
        db,
        pm_context.empresa_id,
        project.id,
        task_id if task_id is not None else plan.tarea_id,
    )
    next_material = get_material_for_company_pm(
        db,
        pm_context.empresa_id,
        material_id if material_id is not None else plan.material_id,
    )
    ensure_unique_project_material_plan(
        db,
        empresa_id=pm_context.empresa_id,
        project_id=project.id,
        material_id=next_material.id,
        task_id=next_task.id if next_task else None,
        exclude_plan_id=plan.id,
    )

    plan.tarea_id = next_task.id if next_task else None
    plan.material_id = next_material.id
    plan.material_nombre_snapshot = next_material.nombre
    plan.material_sku_snapshot = next_material.sku
    plan.unidad = next_material.unidad
    if cantidad_planificada is not None:
        plan.cantidad_planificada = decimal_or_zero(cantidad_planificada)
    if costo_unitario_estimado is not None:
        plan.costo_unitario_estimado = decimal_or_zero(costo_unitario_estimado)
    else:
        plan.costo_unitario_estimado = decimal_or_zero(plan.costo_unitario_estimado or next_material.costo_promedio_actual or next_material.costo_unitario)
    if observaciones is not None:
        plan.observaciones = normalize_optional_text(observaciones)
    if activo is not None:
        plan.activo = activo
    plan.costo_total_estimado = decimal_or_zero(plan.cantidad_planificada) * decimal_or_zero(plan.costo_unitario_estimado)
    plan.updated_by = pm_context.user.id
    db.flush()
    refresh_project_material_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.material_plan.update",
            entity_name="pm_proyecto_material_plan",
            entity_id=plan.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id, "material_id": plan.material_id},
        )
    )
    return serialize_project_material_plan(db, plan)


def deactivate_project_material_plan(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    plan_id: str,
    ip_address: str | None,
) -> PMProyectoMaterialPlanOut:
    ensure_pm_materials_enabled(pm_context)
    get_project_for_company(db, pm_context.empresa_id, project_id)
    plan = get_project_material_plan_for_company(db, pm_context.empresa_id, plan_id)
    if plan.proyecto_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material planeado no encontrado.")
    plan.activo = False
    plan.estatus = "cancelado"
    plan.updated_by = pm_context.user.id
    db.flush()
    refresh_project_material_costs(db, empresa_id=pm_context.empresa_id, project_id=project_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.material_plan.deactivate",
            entity_name="pm_proyecto_material_plan",
            entity_id=plan.id,
            ip_address=ip_address,
            metadata_json={"project_id": project_id, "material_id": plan.material_id},
        )
    )
    return serialize_project_material_plan(db, plan)


def create_project_material_consumption_from_movement(
    db: Session,
    *,
    empresa_id: str,
    movement_id: str,
    project_id: str | None = None,
    tarea_id: str | None = None,
    requisition_id: str | None = None,
    requisition_detail_id: str | None = None,
    origen: str = "movimiento_manual",
) -> PMProyectoMaterialConsumoOut | None:
    if not is_pm_materials_enabled_for_company(db, empresa_id):
        return None

    movement = db.scalar(
        select(MovimientoInventario).where(
            MovimientoInventario.id == movement_id,
            MovimientoInventario.empresa_id == empresa_id,
        )
    )
    if movement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimiento no encontrado.")
    if movement.tipo != "salida":
        return None

    existing = db.scalar(
        select(PMProyectoMaterialConsumo).where(
            PMProyectoMaterialConsumo.empresa_id == empresa_id,
            PMProyectoMaterialConsumo.movimiento_id == movement.id,
        )
    )
    if existing:
        return serialize_project_material_consumption(db, existing)

    resolved_project_id = normalize_optional_text(project_id) or normalize_optional_text(movement.proyecto_id)
    if not resolved_project_id:
        return None

    project = get_project_for_company(db, empresa_id, resolved_project_id)
    task = resolve_project_task(db, empresa_id, project.id, tarea_id)
    material = get_material_for_company_pm(db, empresa_id, movement.material_id)
    normalized_origin = normalize_material_consumption_origin(origen)
    quantity = decimal_or_zero(movement.cantidad)
    if quantity <= ZERO:
        return None
    unit_cost = decimal_or_zero(
        movement.costo_promedio_snapshot or movement.costo_unitario_snapshot or material.costo_promedio_actual or material.costo_unitario
    )
    consumption = PMProyectoMaterialConsumo(
        empresa_id=empresa_id,
        proyecto_id=project.id,
        tarea_id=task.id if task else None,
        material_id=material.id,
        material_nombre_snapshot=material.nombre,
        material_sku_snapshot=material.sku,
        movimiento_id=movement.id,
        requisicion_id=normalize_optional_text(requisition_id),
        requisicion_detalle_id=normalize_optional_text(requisition_detail_id),
        cantidad_consumida=quantity,
        unidad=material.unidad,
        costo_unitario_snapshot=unit_cost,
        costo_total_snapshot=quantity * unit_cost,
        origen=normalized_origin,
        documento_referencia=movement.documento_referencia,
        notas=movement.notas,
        activo=True,
        created_by=movement.created_by,
    )
    db.add(consumption)
    db.flush()
    refresh_project_material_costs(db, empresa_id=empresa_id, project_id=project.id)
    db.add(
        AuditLog(
            empresa_id=empresa_id,
            usuario_id=movement.created_by,
            action="pm.project.material_consumption.create",
            entity_name="pm_proyecto_material_consumo",
            entity_id=consumption.id,
            ip_address=None,
            metadata_json={"project_id": project.id, "movement_id": movement.id, "origen": normalized_origin},
        )
    )
    return serialize_project_material_consumption(db, consumption)


def create_project_material_consumption_manual(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    task_id: str | None,
    material_id: str,
    cantidad_consumida: Decimal,
    costo_unitario_snapshot: Decimal | None,
    documento_referencia: str | None,
    notas: str | None,
    origen: str = "ajuste_admin",
    ip_address: str | None,
) -> PMProyectoMaterialConsumoOut:
    ensure_pm_materials_enabled(pm_context)
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    task = resolve_project_task(db, pm_context.empresa_id, project.id, task_id)
    material = get_material_for_company_pm(db, pm_context.empresa_id, material_id)
    quantity = decimal_or_zero(cantidad_consumida)
    if quantity <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad consumida debe ser mayor a 0.")
    unit_cost = decimal_or_zero(
        costo_unitario_snapshot if costo_unitario_snapshot is not None else material.costo_promedio_actual or material.costo_unitario
    )
    consumption = PMProyectoMaterialConsumo(
        empresa_id=pm_context.empresa_id,
        proyecto_id=project.id,
        tarea_id=task.id if task else None,
        material_id=material.id,
        material_nombre_snapshot=material.nombre,
        material_sku_snapshot=material.sku,
        movimiento_id=None,
        requisicion_id=None,
        requisicion_detalle_id=None,
        cantidad_consumida=quantity,
        unidad=material.unidad,
        costo_unitario_snapshot=unit_cost,
        costo_total_snapshot=quantity * unit_cost,
        origen=normalize_material_consumption_origin(origen),
        documento_referencia=normalize_optional_text(documento_referencia),
        notas=normalize_optional_text(notas),
        activo=True,
        created_by=pm_context.user.id,
    )
    db.add(consumption)
    db.flush()
    refresh_project_material_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.material_consumption.manual_create",
            entity_name="pm_proyecto_material_consumo",
            entity_id=consumption.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id, "material_id": material.id},
        )
    )
    return serialize_project_material_consumption(db, consumption)


def create_project_material_requisition(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    almacen_destino_id: str,
    items: list[dict[str, Decimal | str]],
    notas: str | None,
    ip_address: str | None,
) -> object:
    ensure_pm_materials_enabled(pm_context)
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    from app.services.inventory import get_warehouse_for_company
    from app.services.procurement import add_requisition_detail, create_requisition

    get_warehouse_for_company(db, pm_context.empresa_id, almacen_destino_id)
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes seleccionar al menos un material.")

    selected_plans: list[PMProyectoMaterialPlan] = []
    unique_supplier_ids: set[str] = set()
    for item in items:
        plan = get_project_material_plan_for_company(db, pm_context.empresa_id, str(item["plan_id"]))
        if plan.proyecto_id != project.id or not plan.activo:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uno de los materiales planeados ya no esta disponible.")
        selected_plans.append(plan)
        material = get_material_for_company_pm(db, pm_context.empresa_id, plan.material_id)
        if material.proveedor_principal_id:
            unique_supplier_ids.add(material.proveedor_principal_id)

    supplier_id = next(iter(unique_supplier_ids)) if len(unique_supplier_ids) == 1 else None
    requisition_response = create_requisition(
        db,
        empresa=type("EmpresaProxy", (), {"id": pm_context.empresa_id})(),
        user=pm_context.user,
        folio=None,
        notas=normalize_optional_text(notas),
        proveedor_sugerido_id=supplier_id,
        es_proyecto=True,
        proyecto_id=project.id,
        proyecto_nombre_snapshot=project.nombre,
        ip_address=ip_address,
    )
    db.flush()

    for item in items:
        plan = next(plan_row for plan_row in selected_plans if plan_row.id == str(item["plan_id"]))
        requested_qty = decimal_or_zero(item["cantidad_solicitada"])
        if requested_qty <= ZERO:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad solicitada debe ser mayor a 0.")
        serialized_plan = serialize_project_material_plan(db, plan)
        if requested_qty > serialized_plan.cantidad_pendiente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La cantidad solicitada excede el pendiente planeado para {plan.material_nombre_snapshot}.",
            )
        add_requisition_detail(
            db,
            empresa=type("EmpresaProxy", (), {"id": pm_context.empresa_id})(),
            user=pm_context.user,
            requisition_id=requisition_response.id,
            material_id=plan.material_id,
            cantidad=requested_qty,
            notas=f"Proyecto: {project.nombre}",
            ip_address=ip_address,
        )

    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.project.material_requisition.create",
            entity_name="requisicion",
            entity_id=requisition_response.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id, "almacen_destino_id": almacen_destino_id},
        )
    )
    db.flush()
    from app.services.procurement import get_requisition_for_company, serialize_requisition_response

    return serialize_requisition_response(
        db,
        get_requisition_for_company(db, pm_context.empresa_id, requisition_response.id),
    )


def serialize_time_entry(db: Session, entry: PMTimeEntry) -> PMTimeEntryOut:
    task_title = None
    if entry.tarea_id:
        task_title = db.scalar(select(PMTarea.titulo).where(PMTarea.id == entry.tarea_id))
    return PMTimeEntryOut(
        id=entry.id,
        empresa_id=entry.empresa_id,
        proyecto_id=entry.proyecto_id,
        tarea_id=entry.tarea_id,
        tarea_titulo=task_title,
        usuario_id=entry.usuario_id,
        usuario_email_snapshot=entry.usuario_email_snapshot,
        usuario_nombre_snapshot=entry.usuario_nombre_snapshot,
        fecha=entry.fecha,
        horas=decimal_or_zero(entry.horas),
        descripcion=entry.descripcion,
        costo_hora_aplicado_snapshot=decimal_or_zero(entry.costo_hora_aplicado_snapshot),
        costo_total_snapshot=decimal_or_zero(entry.costo_total_snapshot),
        fuente_tarifa=entry.fuente_tarifa,
        moneda=entry.moneda,
        activo=entry.activo,
        created_by=entry.created_by,
        updated_by=entry.updated_by,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def serialize_user_hourly_rate(rate: PMTarifaHoraUsuario) -> PMTarifaHoraUsuarioOut:
    return PMTarifaHoraUsuarioOut(
        id=rate.id,
        empresa_id=rate.empresa_id,
        usuario_id=rate.usuario_id,
        usuario_email=rate.usuario_email,
        usuario_nombre_snapshot=rate.usuario_nombre_snapshot,
        tarifa_hora=decimal_or_zero(rate.tarifa_hora),
        moneda=rate.moneda,
        effective_from=rate.effective_from,
        effective_to=rate.effective_to,
        activa=rate.activa,
        notas=rate.notas,
        created_by=rate.created_by,
        created_at=rate.created_at,
        updated_at=rate.updated_at,
    )


def serialize_role_hourly_rate(rate: PMTarifaHoraRol) -> PMTarifaHoraRolOut:
    return PMTarifaHoraRolOut(
        id=rate.id,
        empresa_id=rate.empresa_id,
        rol=rate.rol,
        tarifa_hora=decimal_or_zero(rate.tarifa_hora),
        moneda=rate.moneda,
        effective_from=rate.effective_from,
        effective_to=rate.effective_to,
        activa=rate.activa,
        notas=rate.notas,
        created_by=rate.created_by,
        created_at=rate.created_at,
        updated_at=rate.updated_at,
    )


def resolve_time_entry_user(
    db: Session,
    *,
    empresa_id: str,
    user_id: str | None,
    email: str | None,
    name: str | None,
    fallback_user: Usuario | None = None,
) -> tuple[Usuario | None, str | None, str | None]:
    resolved_user: Usuario | None = None
    normalized_email = normalize_email(email)
    normalized_name = normalize_optional_text(name)

    if user_id:
        resolved_user = get_company_member_by_user_id(db, empresa_id, user_id)
    elif normalized_email:
        resolved_user = get_company_member_by_email(db, empresa_id, normalized_email)

    if resolved_user is None and fallback_user is not None:
        resolved_user = get_company_member_by_user_id(db, empresa_id, fallback_user.id)

    if resolved_user:
        return resolved_user, resolved_user.email, resolved_user.full_name

    return None, normalized_email, normalized_name


def resolve_hourly_rate(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
    user_id: str | None,
    user_email: str | None,
    entry_date: date,
) -> tuple[Decimal, str, str]:
    normalized_email = normalize_email(user_email)
    user_rate_query = (
        select(PMTarifaHoraUsuario)
        .where(
            PMTarifaHoraUsuario.empresa_id == empresa_id,
            PMTarifaHoraUsuario.activa == True,
            or_(
                and_(PMTarifaHoraUsuario.effective_from.is_(None), PMTarifaHoraUsuario.effective_to.is_(None)),
                and_(
                    or_(PMTarifaHoraUsuario.effective_from.is_(None), PMTarifaHoraUsuario.effective_from <= entry_date),
                    or_(PMTarifaHoraUsuario.effective_to.is_(None), PMTarifaHoraUsuario.effective_to >= entry_date),
                ),
            ),
        )
        .order_by(desc(PMTarifaHoraUsuario.effective_from), desc(PMTarifaHoraUsuario.updated_at), desc(PMTarifaHoraUsuario.created_at))
    )
    if user_id:
        user_rate = db.scalar(user_rate_query.where(PMTarifaHoraUsuario.usuario_id == user_id))
        if user_rate:
            return decimal_or_zero(user_rate.tarifa_hora), "usuario", user_rate.moneda
    if normalized_email:
        user_rate = db.scalar(user_rate_query.where(PMTarifaHoraUsuario.usuario_email == normalized_email))
        if user_rate:
            return decimal_or_zero(user_rate.tarifa_hora), "usuario", user_rate.moneda

    candidate_roles = build_time_entry_role_candidates(
        db,
        empresa_id=empresa_id,
        project_id=project_id,
        user_id=user_id,
    )
    if candidate_roles:
        role_rates = db.scalars(
            select(PMTarifaHoraRol).where(
                PMTarifaHoraRol.empresa_id == empresa_id,
                PMTarifaHoraRol.activa == True,
                PMTarifaHoraRol.rol.in_(candidate_roles),
                or_(
                    PMTarifaHoraRol.effective_from.is_(None),
                    PMTarifaHoraRol.effective_from <= entry_date,
                ),
                or_(
                    PMTarifaHoraRol.effective_to.is_(None),
                    PMTarifaHoraRol.effective_to >= entry_date,
                ),
            )
        ).all()
        if role_rates:
            for candidate_role in candidate_roles:
                matches = [item for item in role_rates if item.rol == candidate_role]
                if not matches:
                    continue
                matches.sort(
                    key=lambda item: (
                        item.effective_from or date.min,
                        item.updated_at,
                        item.created_at,
                    ),
                    reverse=True,
                )
                rate = matches[0]
                return decimal_or_zero(rate.tarifa_hora), "rol", rate.moneda

    return ZERO, "sin_tarifa", "MXN"


def refresh_project_labor_costs(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
) -> PMProyectoCostoResumen:
    project = get_project_for_company(db, empresa_id, project_id)
    summary = get_or_create_project_cost_summary_row(db, empresa_id=empresa_id, project_id=project_id)
    aggregates = db.execute(
        select(
            func.coalesce(func.sum(PMTimeEntry.costo_total_snapshot), 0),
            func.coalesce(func.sum(PMTimeEntry.horas), 0),
            func.coalesce(
                func.sum(
                    case(
                        (PMTimeEntry.fuente_tarifa == "sin_tarifa", PMTimeEntry.horas),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(
            PMTimeEntry.empresa_id == empresa_id,
            PMTimeEntry.proyecto_id == project_id,
            PMTimeEntry.activo == True,
        )
    ).one()
    summary.costo_horas_real = decimal_or_zero(aggregates[0])
    summary.horas_totales = decimal_or_zero(aggregates[1])
    summary.horas_sin_tarifa = decimal_or_zero(aggregates[2])
    recalculate_project_cost_summary_totals(project, summary)
    db.flush()
    return summary


def build_project_costs_response(
    project: PMProyecto,
    summary: PMProyectoCostoResumen,
) -> PMProjectCostsOut:
    return PMProjectCostsOut(
        costo_materiales_estimado=decimal_or_zero(summary.costo_materiales_estimado),
        costo_materiales_real=decimal_or_zero(summary.costo_materiales_real),
        variacion_materiales=decimal_or_zero(summary.variacion_materiales),
        compras_estimado=ZERO,
        costo_horas_real=decimal_or_zero(summary.costo_horas_real),
        horas_totales=decimal_or_zero(summary.horas_totales),
        horas_sin_tarifa=decimal_or_zero(summary.horas_sin_tarifa),
        costo_total_real=decimal_or_zero(summary.costo_total_real),
        presupuesto_estimado=decimal_or_zero(summary.presupuesto_estimado or project.presupuesto_estimado),
        variacion_presupuesto=decimal_or_zero(summary.variacion_presupuesto),
        presupuesto_detallado_costo=decimal_or_zero(summary.presupuesto_detallado_costo),
        presupuesto_detallado_venta=decimal_or_zero(summary.presupuesto_detallado_venta),
        variacion_vs_presupuesto_detallado=decimal_or_zero(summary.variacion_vs_presupuesto_detallado),
        presupuesto_origen=summary.presupuesto_origen or "simple",
        margen_estimado=summary.margen_estimado,
    )


def refresh_project_total_costs(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
) -> PMProjectCostsOut:
    project = get_project_for_company(db, empresa_id, project_id)
    refresh_project_material_costs(db, empresa_id=empresa_id, project_id=project_id)
    summary = refresh_project_labor_costs(db, empresa_id=empresa_id, project_id=project_id)
    refresh_project_budget_totals(db, empresa_id=empresa_id, project_id=project_id)
    recalculate_project_cost_summary_totals(project, summary)
    db.flush()
    return build_project_costs_response(project, summary)


def list_project_time_entries(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    user_id: str | None = None,
    task_id: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    activo: bool | None = True,
    limit: int = 50,
    offset: int = 0,
) -> PMTimeEntryListResponse:
    ensure_pm_time_enabled(pm_context)
    get_project_for_company(db, pm_context.empresa_id, project_id)
    query = select(PMTimeEntry).where(
        PMTimeEntry.empresa_id == pm_context.empresa_id,
        PMTimeEntry.proyecto_id == project_id,
    )
    if user_id:
        query = query.where(PMTimeEntry.usuario_id == user_id)
    if task_id:
        query = query.where(PMTimeEntry.tarea_id == task_id)
    if fecha_desde:
        query = query.where(PMTimeEntry.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.where(PMTimeEntry.fecha <= fecha_hasta)
    if activo is not None:
        query = query.where(PMTimeEntry.activo == activo)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    entries = db.scalars(
        query.order_by(desc(PMTimeEntry.fecha), desc(PMTimeEntry.created_at))
        .offset(offset)
        .limit(limit)
    ).all()
    return PMTimeEntryListResponse(
        items=[serialize_time_entry(db, entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


def create_project_time_entry(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    tarea_id: str | None,
    usuario_id: str | None,
    usuario_email_snapshot: str | None,
    usuario_nombre_snapshot: str | None,
    fecha: date,
    horas: Decimal,
    descripcion: str | None,
    moneda: str | None,
    ip_address: str | None,
) -> PMTimeEntryOut:
    ensure_pm_time_enabled(pm_context)
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    task = resolve_project_task(db, pm_context.empresa_id, project.id, tarea_id)
    resolved_user, resolved_email, resolved_name = resolve_time_entry_user(
        db,
        empresa_id=pm_context.empresa_id,
        user_id=usuario_id,
        email=usuario_email_snapshot,
        name=usuario_nombre_snapshot,
        fallback_user=pm_context.user
        if not usuario_id and not normalize_email(usuario_email_snapshot) and not normalize_optional_text(usuario_nombre_snapshot)
        else None,
    )
    hours_value = decimal_or_zero(horas)
    if hours_value <= ZERO or hours_value > Decimal("24"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Las horas deben ser mayores a 0 y no exceder 24.")
    rate_value, rate_source, resolved_currency = resolve_hourly_rate(
        db,
        empresa_id=pm_context.empresa_id,
        project_id=project.id,
        user_id=resolved_user.id if resolved_user else None,
        user_email=resolved_email,
        entry_date=fecha,
    )
    entry = PMTimeEntry(
        empresa_id=pm_context.empresa_id,
        proyecto_id=project.id,
        tarea_id=task.id if task else None,
        usuario_id=resolved_user.id if resolved_user else None,
        usuario_email_snapshot=resolved_email,
        usuario_nombre_snapshot=resolved_name,
        fecha=fecha,
        horas=hours_value,
        descripcion=normalize_optional_text(descripcion),
        costo_hora_aplicado_snapshot=rate_value,
        costo_total_snapshot=hours_value * rate_value,
        fuente_tarifa=normalize_rate_source(rate_source),
        moneda=normalize_optional_text(moneda) or resolved_currency or "MXN",
        activo=True,
        created_by=pm_context.user.id,
        updated_by=pm_context.user.id,
    )
    db.add(entry)
    db.flush()
    refresh_project_labor_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.time_entry.create",
            entity_name="pm_time_entry",
            entity_id=entry.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id, "task_id": entry.tarea_id, "user_id": entry.usuario_id},
        )
    )
    return serialize_time_entry(db, entry)


def update_project_time_entry(
    db: Session,
    pm_context: PMContext,
    *,
    time_entry_id: str,
    tarea_id: str | None,
    usuario_id: str | None,
    usuario_email_snapshot: str | None,
    usuario_nombre_snapshot: str | None,
    fecha: date | None,
    horas: Decimal | None,
    descripcion: str | None,
    moneda: str | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMTimeEntryOut:
    ensure_pm_time_enabled(pm_context)
    entry = get_time_entry_for_company(db, pm_context.empresa_id, time_entry_id)
    ensure_can_manage_time_entry(pm_context, entry)
    project = get_project_for_company(db, pm_context.empresa_id, entry.proyecto_id)
    next_task = resolve_project_task(db, pm_context.empresa_id, project.id, tarea_id if tarea_id is not None else entry.tarea_id)
    next_date = fecha or entry.fecha
    next_hours = decimal_or_zero(horas if horas is not None else entry.horas)
    if next_hours <= ZERO or next_hours > Decimal("24"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Las horas deben ser mayores a 0 y no exceder 24.")
    resolved_user, resolved_email, resolved_name = resolve_time_entry_user(
        db,
        empresa_id=pm_context.empresa_id,
        user_id=usuario_id if usuario_id is not None else entry.usuario_id,
        email=usuario_email_snapshot if usuario_email_snapshot is not None else entry.usuario_email_snapshot,
        name=usuario_nombre_snapshot if usuario_nombre_snapshot is not None else entry.usuario_nombre_snapshot,
        fallback_user=None,
    )
    rate_value, rate_source, resolved_currency = resolve_hourly_rate(
        db,
        empresa_id=pm_context.empresa_id,
        project_id=project.id,
        user_id=resolved_user.id if resolved_user else None,
        user_email=resolved_email,
        entry_date=next_date,
    )
    entry.tarea_id = next_task.id if next_task else None
    entry.usuario_id = resolved_user.id if resolved_user else None
    entry.usuario_email_snapshot = resolved_email
    entry.usuario_nombre_snapshot = resolved_name
    entry.fecha = next_date
    entry.horas = next_hours
    if descripcion is not None:
        entry.descripcion = normalize_optional_text(descripcion)
    if activo is not None:
        entry.activo = activo
    entry.costo_hora_aplicado_snapshot = rate_value
    entry.costo_total_snapshot = next_hours * rate_value
    entry.fuente_tarifa = normalize_rate_source(rate_source)
    entry.moneda = normalize_optional_text(moneda) or resolved_currency or entry.moneda or "MXN"
    entry.updated_by = pm_context.user.id
    db.flush()
    refresh_project_labor_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.time_entry.update",
            entity_name="pm_time_entry",
            entity_id=entry.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id, "task_id": entry.tarea_id, "active": entry.activo},
        )
    )
    return serialize_time_entry(db, entry)


def deactivate_project_time_entry(
    db: Session,
    pm_context: PMContext,
    *,
    time_entry_id: str,
    ip_address: str | None,
) -> PMTimeEntryOut:
    ensure_pm_time_enabled(pm_context)
    entry = get_time_entry_for_company(db, pm_context.empresa_id, time_entry_id)
    ensure_can_manage_time_entry(pm_context, entry)
    entry.activo = False
    entry.updated_by = pm_context.user.id
    db.flush()
    refresh_project_labor_costs(db, empresa_id=pm_context.empresa_id, project_id=entry.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.time_entry.deactivate",
            entity_name="pm_time_entry",
            entity_id=entry.id,
            ip_address=ip_address,
            metadata_json={"project_id": entry.proyecto_id},
        )
    )
    return serialize_time_entry(db, entry)


def list_user_hourly_rates(
    db: Session,
    pm_context: PMContext,
    *,
    q: str | None = None,
    activa: bool | None = True,
    limit: int = 50,
    offset: int = 0,
) -> PMTarifaHoraUsuarioListResponse:
    ensure_pm_time_enabled(pm_context)
    ensure_pm_rates_manage_access(pm_context)
    query = select(PMTarifaHoraUsuario).where(PMTarifaHoraUsuario.empresa_id == pm_context.empresa_id)
    if activa is not None:
        query = query.where(PMTarifaHoraUsuario.activa == activa)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(func.coalesce(PMTarifaHoraUsuario.usuario_email, "")).like(pattern),
                func.lower(func.coalesce(PMTarifaHoraUsuario.usuario_nombre_snapshot, "")).like(pattern),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = db.scalars(
        query.order_by(desc(PMTarifaHoraUsuario.activa), PMTarifaHoraUsuario.usuario_email.asc(), desc(PMTarifaHoraUsuario.effective_from))
        .offset(offset)
        .limit(limit)
    ).all()
    return PMTarifaHoraUsuarioListResponse(
        items=[serialize_user_hourly_rate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def create_user_hourly_rate(
    db: Session,
    pm_context: PMContext,
    *,
    usuario_id: str | None,
    usuario_email: str,
    usuario_nombre_snapshot: str | None,
    tarifa_hora: Decimal,
    moneda: str,
    effective_from: date | None,
    effective_to: date | None,
    notas: str | None,
    ip_address: str | None,
) -> PMTarifaHoraUsuarioOut:
    ensure_pm_time_enabled(pm_context)
    ensure_pm_rates_manage_access(pm_context)
    validate_effective_dates(effective_from, effective_to)
    resolved_user, resolved_email, resolved_name = resolve_time_entry_user(
        db,
        empresa_id=pm_context.empresa_id,
        user_id=usuario_id,
        email=usuario_email,
        name=usuario_nombre_snapshot,
    )
    rate = PMTarifaHoraUsuario(
        empresa_id=pm_context.empresa_id,
        usuario_id=resolved_user.id if resolved_user else None,
        usuario_email=resolved_email or normalize_email(usuario_email) or "",
        usuario_nombre_snapshot=resolved_name,
        tarifa_hora=decimal_or_zero(tarifa_hora),
        moneda=(normalize_optional_text(moneda) or "MXN").upper(),
        effective_from=effective_from,
        effective_to=effective_to,
        activa=True,
        notas=normalize_optional_text(notas),
        created_by=pm_context.user.id,
    )
    db.add(rate)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.user_rate.create",
            entity_name="pm_tarifa_hora_usuario",
            entity_id=rate.id,
            ip_address=ip_address,
            metadata_json={"user_id": rate.usuario_id, "email": rate.usuario_email},
        )
    )
    return serialize_user_hourly_rate(rate)


def update_user_hourly_rate(
    db: Session,
    pm_context: PMContext,
    *,
    rate_id: str,
    usuario_id: str | None,
    usuario_email: str | None,
    usuario_nombre_snapshot: str | None,
    tarifa_hora: Decimal | None,
    moneda: str | None,
    effective_from: date | None,
    effective_to: date | None,
    activa: bool | None,
    notas: str | None,
    ip_address: str | None,
) -> PMTarifaHoraUsuarioOut:
    ensure_pm_time_enabled(pm_context)
    ensure_pm_rates_manage_access(pm_context)
    rate = get_user_hourly_rate_for_company(db, pm_context.empresa_id, rate_id)
    next_effective_from = effective_from if effective_from is not None else rate.effective_from
    next_effective_to = effective_to if effective_to is not None else rate.effective_to
    validate_effective_dates(next_effective_from, next_effective_to)
    resolved_user, resolved_email, resolved_name = resolve_time_entry_user(
        db,
        empresa_id=pm_context.empresa_id,
        user_id=usuario_id if usuario_id is not None else rate.usuario_id,
        email=usuario_email if usuario_email is not None else rate.usuario_email,
        name=usuario_nombre_snapshot if usuario_nombre_snapshot is not None else rate.usuario_nombre_snapshot,
    )
    rate.usuario_id = resolved_user.id if resolved_user else None
    rate.usuario_email = resolved_email or rate.usuario_email
    rate.usuario_nombre_snapshot = resolved_name
    if tarifa_hora is not None:
        rate.tarifa_hora = decimal_or_zero(tarifa_hora)
    if moneda is not None:
        rate.moneda = (normalize_optional_text(moneda) or "MXN").upper()
    rate.effective_from = next_effective_from
    rate.effective_to = next_effective_to
    if activa is not None:
        rate.activa = activa
    if notas is not None:
        rate.notas = normalize_optional_text(notas)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.user_rate.update",
            entity_name="pm_tarifa_hora_usuario",
            entity_id=rate.id,
            ip_address=ip_address,
            metadata_json={"user_id": rate.usuario_id, "email": rate.usuario_email, "active": rate.activa},
        )
    )
    return serialize_user_hourly_rate(rate)


def deactivate_user_hourly_rate(
    db: Session,
    pm_context: PMContext,
    *,
    rate_id: str,
    ip_address: str | None,
) -> PMTarifaHoraUsuarioOut:
    ensure_pm_time_enabled(pm_context)
    ensure_pm_rates_manage_access(pm_context)
    rate = get_user_hourly_rate_for_company(db, pm_context.empresa_id, rate_id)
    rate.activa = False
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.user_rate.deactivate",
            entity_name="pm_tarifa_hora_usuario",
            entity_id=rate.id,
            ip_address=ip_address,
            metadata_json={"email": rate.usuario_email},
        )
    )
    return serialize_user_hourly_rate(rate)


def list_role_hourly_rates(
    db: Session,
    pm_context: PMContext,
    *,
    q: str | None = None,
    activa: bool | None = True,
    limit: int = 50,
    offset: int = 0,
) -> PMTarifaHoraRolListResponse:
    ensure_pm_time_enabled(pm_context)
    ensure_pm_rates_manage_access(pm_context)
    query = select(PMTarifaHoraRol).where(PMTarifaHoraRol.empresa_id == pm_context.empresa_id)
    if activa is not None:
        query = query.where(PMTarifaHoraRol.activa == activa)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(func.lower(func.coalesce(PMTarifaHoraRol.rol, "")).like(pattern))
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = db.scalars(
        query.order_by(desc(PMTarifaHoraRol.activa), PMTarifaHoraRol.rol.asc(), desc(PMTarifaHoraRol.effective_from))
        .offset(offset)
        .limit(limit)
    ).all()
    return PMTarifaHoraRolListResponse(
        items=[serialize_role_hourly_rate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def create_role_hourly_rate(
    db: Session,
    pm_context: PMContext,
    *,
    rol: str,
    tarifa_hora: Decimal,
    moneda: str,
    effective_from: date | None,
    effective_to: date | None,
    notas: str | None,
    ip_address: str | None,
) -> PMTarifaHoraRolOut:
    ensure_pm_time_enabled(pm_context)
    ensure_pm_rates_manage_access(pm_context)
    validate_effective_dates(effective_from, effective_to)
    rate = PMTarifaHoraRol(
        empresa_id=pm_context.empresa_id,
        rol=normalize_rate_role(rol),
        tarifa_hora=decimal_or_zero(tarifa_hora),
        moneda=(normalize_optional_text(moneda) or "MXN").upper(),
        effective_from=effective_from,
        effective_to=effective_to,
        activa=True,
        notas=normalize_optional_text(notas),
        created_by=pm_context.user.id,
    )
    db.add(rate)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.role_rate.create",
            entity_name="pm_tarifa_hora_rol",
            entity_id=rate.id,
            ip_address=ip_address,
            metadata_json={"rol": rate.rol},
        )
    )
    return serialize_role_hourly_rate(rate)


def update_role_hourly_rate(
    db: Session,
    pm_context: PMContext,
    *,
    rate_id: str,
    rol: str | None,
    tarifa_hora: Decimal | None,
    moneda: str | None,
    effective_from: date | None,
    effective_to: date | None,
    activa: bool | None,
    notas: str | None,
    ip_address: str | None,
) -> PMTarifaHoraRolOut:
    ensure_pm_time_enabled(pm_context)
    ensure_pm_rates_manage_access(pm_context)
    rate = get_role_hourly_rate_for_company(db, pm_context.empresa_id, rate_id)
    next_effective_from = effective_from if effective_from is not None else rate.effective_from
    next_effective_to = effective_to if effective_to is not None else rate.effective_to
    validate_effective_dates(next_effective_from, next_effective_to)
    if rol is not None:
        rate.rol = normalize_rate_role(rol)
    if tarifa_hora is not None:
        rate.tarifa_hora = decimal_or_zero(tarifa_hora)
    if moneda is not None:
        rate.moneda = (normalize_optional_text(moneda) or "MXN").upper()
    rate.effective_from = next_effective_from
    rate.effective_to = next_effective_to
    if activa is not None:
        rate.activa = activa
    if notas is not None:
        rate.notas = normalize_optional_text(notas)
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.role_rate.update",
            entity_name="pm_tarifa_hora_rol",
            entity_id=rate.id,
            ip_address=ip_address,
            metadata_json={"rol": rate.rol, "active": rate.activa},
        )
    )
    return serialize_role_hourly_rate(rate)


def deactivate_role_hourly_rate(
    db: Session,
    pm_context: PMContext,
    *,
    rate_id: str,
    ip_address: str | None,
) -> PMTarifaHoraRolOut:
    ensure_pm_time_enabled(pm_context)
    ensure_pm_rates_manage_access(pm_context)
    rate = get_role_hourly_rate_for_company(db, pm_context.empresa_id, rate_id)
    rate.activa = False
    db.flush()
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.role_rate.deactivate",
            entity_name="pm_tarifa_hora_rol",
            entity_id=rate.id,
            ip_address=ip_address,
            metadata_json={"rol": rate.rol},
        )
    )
    return serialize_role_hourly_rate(rate)


def ensure_budget_editable(budget: PMPresupuesto) -> None:
    if not budget.activo or budget.estatus != "borrador":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden editar presupuestos en borrador.",
        )


def get_active_project_budget_row(db: Session, empresa_id: str, project_id: str) -> PMPresupuesto | None:
    return db.scalar(
        select(PMPresupuesto)
        .where(
            PMPresupuesto.empresa_id == empresa_id,
            PMPresupuesto.proyecto_id == project_id,
            PMPresupuesto.activo == True,
            PMPresupuesto.estatus != "cancelado",
        )
        .order_by(desc(PMPresupuesto.version), desc(PMPresupuesto.updated_at), desc(PMPresupuesto.created_at))
    )


def validate_budget_item_parent(
    db: Session,
    *,
    empresa_id: str,
    budget_id: str,
    item_type: str,
    parent_id: str | None,
    current_item_id: str | None = None,
) -> PMPresupuestoPartida | None:
    if not parent_id:
        return None
    parent = get_budget_item_for_company(db, empresa_id, parent_id)
    if parent.presupuesto_id != budget_id or not parent.activo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La partida padre no pertenece al presupuesto activo.")
    if parent.tipo != "capitulo":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo los capitulos pueden agrupar partidas.")
    if current_item_id and parent.id == current_item_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La partida no puede ser su propio padre.")
    if item_type == "capitulo":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se soportan capitulos anidados en esta fase.")
    return parent


def resolve_budget_labor_rate(
    db: Session,
    *,
    empresa_id: str,
    rol: str | None,
    provided_rate: Decimal | None,
) -> Decimal:
    if provided_rate is not None:
        return quantize_rate(provided_rate)
    normalized_role = normalize_optional_text(rol)
    if not normalized_role:
        return ZERO
    rate = db.scalar(
        select(PMTarifaHoraRol)
        .where(
            PMTarifaHoraRol.empresa_id == empresa_id,
            PMTarifaHoraRol.activa == True,
            PMTarifaHoraRol.rol == normalized_role.lower(),
            or_(PMTarifaHoraRol.effective_from.is_(None), PMTarifaHoraRol.effective_from <= today_utc()),
            or_(PMTarifaHoraRol.effective_to.is_(None), PMTarifaHoraRol.effective_to >= today_utc()),
        )
        .order_by(desc(PMTarifaHoraRol.effective_from), desc(PMTarifaHoraRol.updated_at), desc(PMTarifaHoraRol.created_at))
    )
    return quantize_rate(rate.tarifa_hora if rate else ZERO)


def refresh_budget_item_component_totals(item: PMPresupuestoPartida) -> None:
    for component in item.materials:
        if not component.activo:
            continue
        component.costo_total = quantize_rate(decimal_or_zero(component.cantidad_por_unidad) * decimal_or_zero(component.costo_unitario))
    for component in item.labor_components:
        if not component.activo:
            continue
        component.costo_total = quantize_rate(decimal_or_zero(component.horas_por_unidad) * decimal_or_zero(component.tarifa_hora))


def refresh_budget_item_totals(db: Session, item: PMPresupuestoPartida) -> PMPresupuestoPartida:
    refresh_budget_item_component_totals(item)
    quantity = decimal_or_zero(item.cantidad)
    if item.tipo == "capitulo":
        child_rows = db.scalars(
            select(PMPresupuestoPartida).where(
                PMPresupuestoPartida.empresa_id == item.empresa_id,
                PMPresupuestoPartida.presupuesto_id == item.presupuesto_id,
                PMPresupuestoPartida.parent_id == item.id,
                PMPresupuestoPartida.activo == True,
            )
        ).all()
        subtotal_cost = sum((decimal_or_zero(child.subtotal_costo) for child in child_rows), ZERO)
        subtotal_sale = sum((decimal_or_zero(child.subtotal_venta) for child in child_rows), ZERO)
        divisor = quantity if quantity > ZERO else Decimal("1")
        item.costo_unitario = quantize_rate(subtotal_cost / divisor) if divisor > ZERO else ZERO
        item.precio_unitario = quantize_rate(subtotal_sale / divisor) if divisor > ZERO else ZERO
        item.subtotal_costo = quantize_money(subtotal_cost)
        item.subtotal_venta = quantize_money(subtotal_sale)
        return item

    material_cost = sum((decimal_or_zero(component.costo_total) for component in item.materials if component.activo), ZERO)
    labor_cost = sum((decimal_or_zero(component.costo_total) for component in item.labor_components if component.activo), ZERO)
    unit_cost = material_cost + labor_cost
    margin_pct = decimal_or_zero(item.margen_pct)
    price_unit = (
        decimal_or_zero(item.precio_unitario_manual)
        if item.precio_unitario_manual is not None
        else unit_cost * (Decimal("1") + (margin_pct / Decimal("100")))
    )
    item.costo_unitario = quantize_rate(unit_cost)
    item.precio_unitario = quantize_rate(price_unit)
    item.subtotal_costo = quantize_money(quantity * decimal_or_zero(item.costo_unitario))
    item.subtotal_venta = quantize_money(quantity * decimal_or_zero(item.precio_unitario))
    return item


def refresh_budget_item_tree(db: Session, item: PMPresupuestoPartida) -> None:
    current = refresh_budget_item_totals(db, item)
    while current.parent_id:
        parent = get_budget_item_for_company(db, current.empresa_id, current.parent_id)
        current = refresh_budget_item_totals(db, parent)


def refresh_project_budget_totals(
    db: Session,
    *,
    empresa_id: str,
    project_id: str,
) -> PMPresupuesto | None:
    project = get_project_for_company(db, empresa_id, project_id)
    summary = get_or_create_project_cost_summary_row(db, empresa_id=empresa_id, project_id=project_id)
    budget = get_active_project_budget_row(db, empresa_id, project_id)

    if budget is None:
        summary.presupuesto_detallado_costo = ZERO
        summary.presupuesto_detallado_venta = ZERO
        summary.variacion_vs_presupuesto_detallado = ZERO - decimal_or_zero(summary.costo_total_real)
        if summary.presupuesto_origen == "detallado":
            summary.presupuesto_origen = "simple"
        summary.margen_estimado = None
        recalculate_project_cost_summary_totals(project, summary)
        db.flush()
        return None

    leaf_items = db.scalars(
        select(PMPresupuestoPartida).where(
            PMPresupuestoPartida.empresa_id == empresa_id,
            PMPresupuestoPartida.presupuesto_id == budget.id,
            PMPresupuestoPartida.activo == True,
            PMPresupuestoPartida.tipo == "partida",
        )
    ).all()
    for item in leaf_items:
        refresh_budget_item_totals(db, item)

    chapter_items = db.scalars(
        select(PMPresupuestoPartida).where(
            PMPresupuestoPartida.empresa_id == empresa_id,
            PMPresupuestoPartida.presupuesto_id == budget.id,
            PMPresupuestoPartida.activo == True,
            PMPresupuestoPartida.tipo == "capitulo",
        )
    ).all()
    for item in chapter_items:
        refresh_budget_item_totals(db, item)

    subtotal_cost = db.scalar(
        select(func.coalesce(func.sum(PMPresupuestoPartida.subtotal_costo), 0)).where(
            PMPresupuestoPartida.empresa_id == empresa_id,
            PMPresupuestoPartida.presupuesto_id == budget.id,
            PMPresupuestoPartida.activo == True,
            PMPresupuestoPartida.tipo == "partida",
        )
    ) or ZERO
    subtotal_sale = db.scalar(
        select(func.coalesce(func.sum(PMPresupuestoPartida.subtotal_venta), 0)).where(
            PMPresupuestoPartida.empresa_id == empresa_id,
            PMPresupuestoPartida.presupuesto_id == budget.id,
            PMPresupuestoPartida.activo == True,
            PMPresupuestoPartida.tipo == "partida",
        )
    ) or ZERO

    indirect_rows = db.scalars(
        select(PMPresupuestoIndirecto).where(
            PMPresupuestoIndirecto.empresa_id == empresa_id,
            PMPresupuestoIndirecto.presupuesto_id == budget.id,
            PMPresupuestoIndirecto.activo == True,
        )
    ).all()
    header_indirect_amount = decimal_or_zero(subtotal_cost) * (decimal_or_zero(budget.indirectos_pct) / Decimal("100"))
    detail_indirect_amount = ZERO
    for indirect in indirect_rows:
        if indirect.tipo == "porcentaje":
            indirect_amount = decimal_or_zero(subtotal_cost) * (decimal_or_zero(indirect.porcentaje) / Decimal("100"))
        else:
            indirect_amount = decimal_or_zero(indirect.monto)
        indirect.monto = quantize_money(indirect_amount)
        detail_indirect_amount += decimal_or_zero(indirect.monto)

    indirect_total = quantize_money(header_indirect_amount + detail_indirect_amount)
    total_cost = quantize_money(decimal_or_zero(subtotal_cost) + indirect_total)
    total_sale = quantize_money(subtotal_sale)
    profit_amount = quantize_money(total_sale - total_cost)
    profit_pct = quantize_percentage((profit_amount / total_cost) * Decimal("100")) if total_cost > ZERO else ZERO

    budget.subtotal_costo = quantize_money(subtotal_cost)
    budget.subtotal_venta = quantize_money(subtotal_sale)
    budget.indirectos_monto = indirect_total
    budget.total_costo = total_cost
    budget.total_venta = total_sale
    budget.utilidad_monto = profit_amount
    budget.utilidad_pct = profit_pct
    budget.margen_estimado = profit_amount

    summary.presupuesto_detallado_costo = total_cost
    summary.presupuesto_detallado_venta = total_sale
    summary.variacion_vs_presupuesto_detallado = total_cost - decimal_or_zero(summary.costo_total_real)
    summary.margen_estimado = profit_amount
    recalculate_project_cost_summary_totals(project, summary)
    db.flush()
    return budget


def serialize_budget_item_material(component: PMPresupuestoPartidaMaterial) -> PMPresupuestoPartidaMaterialOut:
    return PMPresupuestoPartidaMaterialOut(
        id=component.id,
        empresa_id=component.empresa_id,
        partida_id=component.partida_id,
        proyecto_id=component.proyecto_id,
        material_id=component.material_id,
        material_nombre_snapshot=component.material_nombre_snapshot,
        material_sku_snapshot=component.material_sku_snapshot,
        unidad=component.unidad,
        cantidad_por_unidad=decimal_or_zero(component.cantidad_por_unidad),
        costo_unitario=decimal_or_zero(component.costo_unitario),
        costo_total=decimal_or_zero(component.costo_total),
        proveedor_nombre_snapshot=component.proveedor_nombre_snapshot,
        activo=component.activo,
        created_at=component.created_at,
        updated_at=component.updated_at,
    )


def serialize_budget_item_labor(component: PMPresupuestoPartidaManoObra) -> PMPresupuestoPartidaManoObraOut:
    return PMPresupuestoPartidaManoObraOut(
        id=component.id,
        empresa_id=component.empresa_id,
        partida_id=component.partida_id,
        proyecto_id=component.proyecto_id,
        rol=component.rol,
        descripcion=component.descripcion,
        horas_por_unidad=decimal_or_zero(component.horas_por_unidad),
        tarifa_hora=decimal_or_zero(component.tarifa_hora),
        costo_total=decimal_or_zero(component.costo_total),
        activo=component.activo,
        created_at=component.created_at,
        updated_at=component.updated_at,
    )


def serialize_budget_item(db: Session, item: PMPresupuestoPartida) -> PMPresupuestoPartidaOut:
    materials = db.scalars(
        select(PMPresupuestoPartidaMaterial)
        .where(
            PMPresupuestoPartidaMaterial.empresa_id == item.empresa_id,
            PMPresupuestoPartidaMaterial.partida_id == item.id,
            PMPresupuestoPartidaMaterial.activo == True,
        )
        .order_by(PMPresupuestoPartidaMaterial.created_at.asc(), PMPresupuestoPartidaMaterial.id.asc())
    ).all()
    labor_components = db.scalars(
        select(PMPresupuestoPartidaManoObra)
        .where(
            PMPresupuestoPartidaManoObra.empresa_id == item.empresa_id,
            PMPresupuestoPartidaManoObra.partida_id == item.id,
            PMPresupuestoPartidaManoObra.activo == True,
        )
        .order_by(PMPresupuestoPartidaManoObra.created_at.asc(), PMPresupuestoPartidaManoObra.id.asc())
    ).all()
    return PMPresupuestoPartidaOut(
        id=item.id,
        empresa_id=item.empresa_id,
        presupuesto_id=item.presupuesto_id,
        proyecto_id=item.proyecto_id,
        parent_id=item.parent_id,
        codigo=item.codigo,
        nombre=item.nombre,
        descripcion=item.descripcion,
        tipo=item.tipo,
        unidad=item.unidad,
        cantidad=decimal_or_zero(item.cantidad),
        costo_unitario=decimal_or_zero(item.costo_unitario),
        precio_unitario=decimal_or_zero(item.precio_unitario),
        precio_unitario_manual=item.precio_unitario_manual,
        subtotal_costo=decimal_or_zero(item.subtotal_costo),
        subtotal_venta=decimal_or_zero(item.subtotal_venta),
        margen_pct=decimal_or_zero(item.margen_pct),
        orden=item.orden,
        activo=item.activo,
        materials=[serialize_budget_item_material(component) for component in materials],
        labor_components=[serialize_budget_item_labor(component) for component in labor_components],
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def serialize_budget_indirect(indirect: PMPresupuestoIndirecto) -> PMPresupuestoIndirectoOut:
    return PMPresupuestoIndirectoOut(
        id=indirect.id,
        empresa_id=indirect.empresa_id,
        presupuesto_id=indirect.presupuesto_id,
        proyecto_id=indirect.proyecto_id,
        nombre=indirect.nombre,
        tipo=indirect.tipo,
        porcentaje=decimal_or_zero(indirect.porcentaje) if indirect.porcentaje is not None else None,
        monto=decimal_or_zero(indirect.monto),
        activo=indirect.activo,
        created_at=indirect.created_at,
        updated_at=indirect.updated_at,
    )


def serialize_budget(db: Session, budget: PMPresupuesto) -> PMPresupuestoOut:
    items = db.scalars(
        select(PMPresupuestoPartida)
        .where(
            PMPresupuestoPartida.empresa_id == budget.empresa_id,
            PMPresupuestoPartida.presupuesto_id == budget.id,
            PMPresupuestoPartida.activo == True,
        )
        .order_by(PMPresupuestoPartida.orden.asc(), PMPresupuestoPartida.created_at.asc(), PMPresupuestoPartida.id.asc())
    ).all()
    indirects = db.scalars(
        select(PMPresupuestoIndirecto)
        .where(
            PMPresupuestoIndirecto.empresa_id == budget.empresa_id,
            PMPresupuestoIndirecto.presupuesto_id == budget.id,
            PMPresupuestoIndirecto.activo == True,
        )
        .order_by(PMPresupuestoIndirecto.created_at.asc(), PMPresupuestoIndirecto.id.asc())
    ).all()
    return PMPresupuestoOut(
        id=budget.id,
        empresa_id=budget.empresa_id,
        proyecto_id=budget.proyecto_id,
        nombre=budget.nombre,
        version=budget.version,
        estatus=budget.estatus,
        moneda=budget.moneda,
        subtotal_costo=decimal_or_zero(budget.subtotal_costo),
        subtotal_venta=decimal_or_zero(budget.subtotal_venta),
        indirectos_pct=decimal_or_zero(budget.indirectos_pct),
        indirectos_monto=decimal_or_zero(budget.indirectos_monto),
        utilidad_pct=decimal_or_zero(budget.utilidad_pct),
        utilidad_monto=decimal_or_zero(budget.utilidad_monto),
        total_costo=decimal_or_zero(budget.total_costo),
        total_venta=decimal_or_zero(budget.total_venta),
        margen_estimado=decimal_or_zero(budget.margen_estimado),
        notas=budget.notas,
        aprobado_por=budget.aprobado_por,
        aprobado_at=budget.aprobado_at,
        activo=budget.activo,
        created_by=budget.created_by,
        updated_by=budget.updated_by,
        created_at=budget.created_at,
        updated_at=budget.updated_at,
        items=[serialize_budget_item(db, item) for item in items],
        indirects=[serialize_budget_indirect(indirect) for indirect in indirects],
    )


def build_budget_vs_actual_response(
    project: PMProyecto,
    summary: PMProyectoCostoResumen,
    budget: PMPresupuesto | None,
) -> PMBudgetVsActualOut:
    budget_cost = decimal_or_zero(summary.presupuesto_detallado_costo or summary.presupuesto_estimado or project.presupuesto_estimado)
    total_real = decimal_or_zero(summary.costo_total_real)
    percentage_consumed = ZERO
    if budget_cost > ZERO:
        percentage_consumed = quantize_percentage((total_real / budget_cost) * Decimal("100"))
    return PMBudgetVsActualOut(
        project_id=project.id,
        presupuesto_id=budget.id if budget else None,
        presupuesto_nombre=budget.nombre if budget else None,
        presupuesto_estatus=budget.estatus if budget else None,
        presupuesto_origen=summary.presupuesto_origen or "simple",
        moneda=budget.moneda if budget else "MXN",
        presupuesto_detallado_costo=budget_cost,
        presupuesto_detallado_venta=decimal_or_zero(summary.presupuesto_detallado_venta),
        costo_materiales_real=decimal_or_zero(summary.costo_materiales_real),
        costo_horas_real=decimal_or_zero(summary.costo_horas_real),
        costo_real_total=total_real,
        variacion=budget_cost - total_real,
        porcentaje_consumido=percentage_consumed,
        margen_estimado=summary.margen_estimado,
    )


def build_dashboard_project_cost_item(summary: PMProyectoCostoResumen, project: PMProyecto) -> PMDashboardProjectCostItem:
    return PMDashboardProjectCostItem(
        project_id=project.id,
        proyecto_nombre=project.nombre,
        costo_materiales_real=decimal_or_zero(summary.costo_materiales_real),
        costo_materiales_estimado=decimal_or_zero(summary.costo_materiales_estimado),
        costo_horas_real=decimal_or_zero(summary.costo_horas_real),
        horas_totales=decimal_or_zero(summary.horas_totales),
        costo_total_real=decimal_or_zero(summary.costo_total_real),
        variacion_materiales=decimal_or_zero(summary.variacion_materiales),
        presupuesto_estimado=decimal_or_zero(summary.presupuesto_estimado or project.presupuesto_estimado),
        variacion_presupuesto=decimal_or_zero(summary.variacion_presupuesto),
        presupuesto_detallado_costo=decimal_or_zero(summary.presupuesto_detallado_costo),
        presupuesto_detallado_venta=decimal_or_zero(summary.presupuesto_detallado_venta),
        variacion_vs_presupuesto_detallado=decimal_or_zero(summary.variacion_vs_presupuesto_detallado),
        margen_estimado=summary.margen_estimado,
        presupuesto_origen=summary.presupuesto_origen or "simple",
    )


def get_project_budget(
    db: Session,
    pm_context: PMContext,
    project_id: str,
) -> PMProjectBudgetBundleOut:
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    if pm_context.config.pm_materiales_enabled:
        refresh_project_material_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    summary = (
        refresh_project_labor_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
        if pm_context.config.pm_tiempo_enabled
        else get_or_create_project_cost_summary_row(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    )
    budget = refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    recalculate_project_cost_summary_totals(project, summary)
    db.flush()
    return PMProjectBudgetBundleOut(
        budget=serialize_budget(db, budget) if budget else None,
        summary=build_project_costs_response(project, summary),
        vs_actual=build_budget_vs_actual_response(project, summary, budget),
    )


def create_project_budget(
    db: Session,
    pm_context: PMContext,
    *,
    project_id: str,
    nombre: str | None,
    moneda: str | None,
    indirectos_pct: Decimal | None,
    notas: str | None,
    ip_address: str | None,
) -> PMPresupuestoOut:
    ensure_pm_budget_manage_access(pm_context)
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    current_budget = get_active_project_budget_row(db, pm_context.empresa_id, project.id)
    if current_budget:
        refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=project.id)
        return serialize_budget(db, current_budget)

    next_version = (db.scalar(
        select(func.coalesce(func.max(PMPresupuesto.version), 0)).where(
            PMPresupuesto.empresa_id == pm_context.empresa_id,
            PMPresupuesto.proyecto_id == project.id,
        )
    ) or 0) + 1
    budget = PMPresupuesto(
        empresa_id=pm_context.empresa_id,
        proyecto_id=project.id,
        nombre=normalize_required_text(nombre or "Presupuesto base", "Nombre"),
        version=next_version,
        estatus="borrador",
        moneda=(normalize_optional_text(moneda) or "MXN").upper(),
        indirectos_pct=decimal_or_zero(indirectos_pct),
        notas=normalize_optional_text(notas),
        activo=True,
        created_by=pm_context.user.id,
        updated_by=pm_context.user.id,
    )
    db.add(budget)
    db.flush()
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget.create",
            entity_name="pm_presupuesto",
            entity_id=budget.id,
            ip_address=ip_address,
            metadata_json={"project_id": project.id, "version": budget.version},
        )
    )
    return serialize_budget(db, budget)


def update_project_budget(
    db: Session,
    pm_context: PMContext,
    *,
    budget_id: str,
    nombre: str | None,
    moneda: str | None,
    indirectos_pct: Decimal | None,
    notas: str | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMPresupuestoOut:
    ensure_pm_budget_manage_access(pm_context)
    budget = get_budget_for_company(db, pm_context.empresa_id, budget_id)
    ensure_budget_editable(budget)
    if nombre is not None:
        budget.nombre = normalize_required_text(nombre, "Nombre")
    if moneda is not None:
        budget.moneda = (normalize_optional_text(moneda) or "MXN").upper()
    if indirectos_pct is not None:
        budget.indirectos_pct = decimal_or_zero(indirectos_pct)
    if notas is not None:
        budget.notas = normalize_optional_text(notas)
    if activo is not None:
        budget.activo = activo
    budget.updated_by = pm_context.user.id
    db.flush()
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget.update",
            entity_name="pm_presupuesto",
            entity_id=budget.id,
            ip_address=ip_address,
            metadata_json={"project_id": budget.proyecto_id},
        )
    )
    return serialize_budget(db, budget)


def approve_project_budget(
    db: Session,
    pm_context: PMContext,
    *,
    budget_id: str,
    ip_address: str | None,
) -> PMPresupuestoOut:
    ensure_pm_budget_manage_access(pm_context)
    budget = get_budget_for_company(db, pm_context.empresa_id, budget_id)
    ensure_budget_editable(budget)
    active_items = db.scalar(
        select(func.count(PMPresupuestoPartida.id)).where(
            PMPresupuestoPartida.empresa_id == pm_context.empresa_id,
            PMPresupuestoPartida.presupuesto_id == budget.id,
            PMPresupuestoPartida.activo == True,
            PMPresupuestoPartida.tipo == "partida",
        )
    ) or 0
    if active_items <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes agregar al menos una partida antes de aprobar el presupuesto.")
    budget.estatus = "aprobado"
    budget.aprobado_por = pm_context.user.id
    budget.aprobado_at = utcnow()
    budget.updated_by = pm_context.user.id
    db.flush()
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget.approve",
            entity_name="pm_presupuesto",
            entity_id=budget.id,
            ip_address=ip_address,
            metadata_json={"project_id": budget.proyecto_id},
        )
    )
    return serialize_budget(db, budget)


def cancel_project_budget(
    db: Session,
    pm_context: PMContext,
    *,
    budget_id: str,
    ip_address: str | None,
) -> PMPresupuestoOut:
    ensure_pm_budget_manage_access(pm_context)
    budget = get_budget_for_company(db, pm_context.empresa_id, budget_id)
    budget.estatus = "cancelado"
    budget.activo = False
    budget.updated_by = pm_context.user.id
    db.flush()
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget.cancel",
            entity_name="pm_presupuesto",
            entity_id=budget.id,
            ip_address=ip_address,
            metadata_json={"project_id": budget.proyecto_id},
        )
    )
    return serialize_budget(db, budget)


def create_budget_item(
    db: Session,
    pm_context: PMContext,
    *,
    budget_id: str,
    parent_id: str | None,
    codigo: str | None,
    nombre: str,
    descripcion: str | None,
    tipo: str,
    unidad: str | None,
    cantidad: Decimal,
    margen_pct: Decimal,
    precio_unitario_manual: Decimal | None,
    orden: int,
    ip_address: str | None,
) -> PMPresupuestoPartidaOut:
    ensure_pm_budget_manage_access(pm_context)
    budget = get_budget_for_company(db, pm_context.empresa_id, budget_id)
    ensure_budget_editable(budget)
    item_type = normalize_budget_item_type(tipo)
    validate_budget_item_parent(
        db,
        empresa_id=pm_context.empresa_id,
        budget_id=budget.id,
        item_type=item_type,
        parent_id=parent_id,
    )
    quantity = decimal_or_zero(cantidad)
    if item_type == "partida" and quantity <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad de la partida debe ser mayor a 0.")
    item = PMPresupuestoPartida(
        empresa_id=pm_context.empresa_id,
        presupuesto_id=budget.id,
        proyecto_id=budget.proyecto_id,
        parent_id=normalize_optional_text(parent_id),
        codigo=normalize_optional_text(codigo),
        nombre=normalize_required_text(nombre, "Nombre"),
        descripcion=normalize_optional_text(descripcion),
        tipo=item_type,
        unidad=normalize_optional_text(unidad),
        cantidad=quantity if item_type == "partida" else quantity,
        margen_pct=decimal_or_zero(margen_pct),
        precio_unitario_manual=decimal_or_zero(precio_unitario_manual) if precio_unitario_manual is not None else None,
        orden=max(int(orden), 0),
        activo=True,
    )
    db.add(item)
    db.flush()
    refresh_budget_item_tree(db, item)
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget_item.create",
            entity_name="pm_presupuesto_partida",
            entity_id=item.id,
            ip_address=ip_address,
            metadata_json={"project_id": budget.proyecto_id, "budget_id": budget.id},
        )
    )
    return serialize_budget_item(db, item)


def update_budget_item(
    db: Session,
    pm_context: PMContext,
    *,
    item_id: str,
    parent_id: str | None,
    codigo: str | None,
    nombre: str | None,
    descripcion: str | None,
    tipo: str | None,
    unidad: str | None,
    cantidad: Decimal | None,
    margen_pct: Decimal | None,
    precio_unitario_manual: Decimal | None,
    orden: int | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMPresupuestoPartidaOut:
    ensure_pm_budget_manage_access(pm_context)
    item = get_budget_item_for_company(db, pm_context.empresa_id, item_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, item.presupuesto_id)
    ensure_budget_editable(budget)
    next_type = normalize_budget_item_type(tipo or item.tipo)
    next_parent_id = parent_id if parent_id is not None else item.parent_id
    validate_budget_item_parent(
        db,
        empresa_id=pm_context.empresa_id,
        budget_id=budget.id,
        item_type=next_type,
        parent_id=next_parent_id,
        current_item_id=item.id,
    )
    next_quantity = decimal_or_zero(cantidad if cantidad is not None else item.cantidad)
    if next_type == "partida" and next_quantity <= ZERO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cantidad de la partida debe ser mayor a 0.")
    item.tipo = next_type
    item.parent_id = normalize_optional_text(next_parent_id)
    if codigo is not None:
        item.codigo = normalize_optional_text(codigo)
    if nombre is not None:
        item.nombre = normalize_required_text(nombre, "Nombre")
    if descripcion is not None:
        item.descripcion = normalize_optional_text(descripcion)
    if unidad is not None:
        item.unidad = normalize_optional_text(unidad)
    item.cantidad = next_quantity
    if margen_pct is not None:
        item.margen_pct = decimal_or_zero(margen_pct)
    if precio_unitario_manual is not None:
        item.precio_unitario_manual = decimal_or_zero(precio_unitario_manual)
    if orden is not None:
        item.orden = max(int(orden), 0)
    if activo is not None:
        item.activo = activo
    db.flush()
    refresh_budget_item_tree(db, item)
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget_item.update",
            entity_name="pm_presupuesto_partida",
            entity_id=item.id,
            ip_address=ip_address,
            metadata_json={"project_id": budget.proyecto_id, "budget_id": budget.id},
        )
    )
    return serialize_budget_item(db, item)


def deactivate_budget_item(
    db: Session,
    pm_context: PMContext,
    *,
    item_id: str,
    ip_address: str | None,
) -> PMPresupuestoPartidaOut:
    ensure_pm_budget_manage_access(pm_context)
    item = get_budget_item_for_company(db, pm_context.empresa_id, item_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, item.presupuesto_id)
    ensure_budget_editable(budget)
    item.activo = False
    db.flush()
    if item.parent_id:
        parent = get_budget_item_for_company(db, pm_context.empresa_id, item.parent_id)
        refresh_budget_item_tree(db, parent)
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget_item.deactivate",
            entity_name="pm_presupuesto_partida",
            entity_id=item.id,
            ip_address=ip_address,
            metadata_json={"project_id": budget.proyecto_id, "budget_id": budget.id},
        )
    )
    return serialize_budget_item(db, item)


def add_budget_item_material(
    db: Session,
    pm_context: PMContext,
    *,
    item_id: str,
    material_id: str | None,
    material_nombre_snapshot: str | None,
    material_sku_snapshot: str | None,
    unidad: str | None,
    cantidad_por_unidad: Decimal,
    costo_unitario: Decimal | None,
    proveedor_nombre_snapshot: str | None,
    ip_address: str | None,
) -> PMPresupuestoPartidaMaterialOut:
    ensure_pm_budget_manage_access(pm_context)
    item = get_budget_item_for_company(db, pm_context.empresa_id, item_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, item.presupuesto_id)
    ensure_budget_editable(budget)
    if item.tipo != "partida":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo las partidas pueden tener APU de materiales.")

    material = get_material_for_company_pm(db, pm_context.empresa_id, material_id) if material_id else None
    snapshot_name = material.nombre if material else normalize_required_text(material_nombre_snapshot or "", "Material")
    snapshot_sku = material.sku if material else normalize_optional_text(material_sku_snapshot)
    snapshot_unit = material.unidad if material else normalize_optional_text(unidad)
    snapshot_cost = quantize_rate(
        decimal_or_zero(costo_unitario if costo_unitario is not None else (material.costo_promedio_actual or material.costo_unitario if material else ZERO))
    )
    quantity = decimal_or_zero(cantidad_por_unidad)
    component = PMPresupuestoPartidaMaterial(
        empresa_id=pm_context.empresa_id,
        partida_id=item.id,
        proyecto_id=item.proyecto_id,
        material_id=material.id if material else None,
        material_nombre_snapshot=snapshot_name,
        material_sku_snapshot=snapshot_sku,
        unidad=snapshot_unit,
        cantidad_por_unidad=quantity,
        costo_unitario=snapshot_cost,
        costo_total=quantize_rate(quantity * snapshot_cost),
        proveedor_nombre_snapshot=normalize_optional_text(proveedor_nombre_snapshot),
        activo=True,
    )
    db.add(component)
    db.flush()
    refresh_budget_item_tree(db, item)
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=item.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget_item.material.create",
            entity_name="pm_presupuesto_partida_material",
            entity_id=component.id,
            ip_address=ip_address,
            metadata_json={"project_id": item.proyecto_id, "item_id": item.id},
        )
    )
    return serialize_budget_item_material(component)


def update_budget_item_material(
    db: Session,
    pm_context: PMContext,
    *,
    component_id: str,
    material_id: str | None,
    material_nombre_snapshot: str | None,
    material_sku_snapshot: str | None,
    unidad: str | None,
    cantidad_por_unidad: Decimal | None,
    costo_unitario: Decimal | None,
    proveedor_nombre_snapshot: str | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMPresupuestoPartidaMaterialOut:
    ensure_pm_budget_manage_access(pm_context)
    component = get_budget_item_material_for_company(db, pm_context.empresa_id, component_id)
    item = get_budget_item_for_company(db, pm_context.empresa_id, component.partida_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, item.presupuesto_id)
    ensure_budget_editable(budget)
    material = get_material_for_company_pm(db, pm_context.empresa_id, material_id) if material_id else None
    if material:
        component.material_id = material.id
        component.material_nombre_snapshot = material.nombre
        component.material_sku_snapshot = material.sku
        component.unidad = material.unidad
        if costo_unitario is None:
            component.costo_unitario = quantize_rate(decimal_or_zero(material.costo_promedio_actual or material.costo_unitario))
    else:
        if material_nombre_snapshot is not None:
            component.material_nombre_snapshot = normalize_required_text(material_nombre_snapshot, "Material")
        if material_sku_snapshot is not None:
            component.material_sku_snapshot = normalize_optional_text(material_sku_snapshot)
        if unidad is not None:
            component.unidad = normalize_optional_text(unidad)
        if material_id is not None:
            component.material_id = None
    if cantidad_por_unidad is not None:
        component.cantidad_por_unidad = decimal_or_zero(cantidad_por_unidad)
    if costo_unitario is not None:
        component.costo_unitario = quantize_rate(costo_unitario)
    if proveedor_nombre_snapshot is not None:
        component.proveedor_nombre_snapshot = normalize_optional_text(proveedor_nombre_snapshot)
    if activo is not None:
        component.activo = activo
    component.costo_total = quantize_rate(decimal_or_zero(component.cantidad_por_unidad) * decimal_or_zero(component.costo_unitario))
    db.flush()
    refresh_budget_item_tree(db, item)
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=item.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget_item.material.update",
            entity_name="pm_presupuesto_partida_material",
            entity_id=component.id,
            ip_address=ip_address,
            metadata_json={"project_id": item.proyecto_id, "item_id": item.id},
        )
    )
    return serialize_budget_item_material(component)


def deactivate_budget_item_material(
    db: Session,
    pm_context: PMContext,
    *,
    component_id: str,
    ip_address: str | None,
) -> PMPresupuestoPartidaMaterialOut:
    ensure_pm_budget_manage_access(pm_context)
    component = get_budget_item_material_for_company(db, pm_context.empresa_id, component_id)
    item = get_budget_item_for_company(db, pm_context.empresa_id, component.partida_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, item.presupuesto_id)
    ensure_budget_editable(budget)
    component.activo = False
    db.flush()
    refresh_budget_item_tree(db, item)
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=item.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget_item.material.deactivate",
            entity_name="pm_presupuesto_partida_material",
            entity_id=component.id,
            ip_address=ip_address,
            metadata_json={"project_id": item.proyecto_id, "item_id": item.id},
        )
    )
    return serialize_budget_item_material(component)


def add_budget_item_labor(
    db: Session,
    pm_context: PMContext,
    *,
    item_id: str,
    rol: str | None,
    descripcion: str | None,
    horas_por_unidad: Decimal,
    tarifa_hora: Decimal | None,
    ip_address: str | None,
) -> PMPresupuestoPartidaManoObraOut:
    ensure_pm_budget_manage_access(pm_context)
    item = get_budget_item_for_company(db, pm_context.empresa_id, item_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, item.presupuesto_id)
    ensure_budget_editable(budget)
    if item.tipo != "partida":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo las partidas pueden tener mano de obra APU.")
    hours = decimal_or_zero(horas_por_unidad)
    rate = resolve_budget_labor_rate(db, empresa_id=pm_context.empresa_id, rol=rol, provided_rate=tarifa_hora)
    component = PMPresupuestoPartidaManoObra(
        empresa_id=pm_context.empresa_id,
        partida_id=item.id,
        proyecto_id=item.proyecto_id,
        rol=normalize_optional_text(rol),
        descripcion=normalize_optional_text(descripcion),
        horas_por_unidad=hours,
        tarifa_hora=rate,
        costo_total=quantize_rate(hours * rate),
        activo=True,
    )
    db.add(component)
    db.flush()
    refresh_budget_item_tree(db, item)
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=item.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget_item.labor.create",
            entity_name="pm_presupuesto_partida_mano_obra",
            entity_id=component.id,
            ip_address=ip_address,
            metadata_json={"project_id": item.proyecto_id, "item_id": item.id},
        )
    )
    return serialize_budget_item_labor(component)


def update_budget_item_labor(
    db: Session,
    pm_context: PMContext,
    *,
    component_id: str,
    rol: str | None,
    descripcion: str | None,
    horas_por_unidad: Decimal | None,
    tarifa_hora: Decimal | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMPresupuestoPartidaManoObraOut:
    ensure_pm_budget_manage_access(pm_context)
    component = get_budget_item_labor_for_company(db, pm_context.empresa_id, component_id)
    item = get_budget_item_for_company(db, pm_context.empresa_id, component.partida_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, item.presupuesto_id)
    ensure_budget_editable(budget)
    if rol is not None:
        component.rol = normalize_optional_text(rol)
    if descripcion is not None:
        component.descripcion = normalize_optional_text(descripcion)
    if horas_por_unidad is not None:
        component.horas_por_unidad = decimal_or_zero(horas_por_unidad)
    if tarifa_hora is not None:
        component.tarifa_hora = resolve_budget_labor_rate(
            db,
            empresa_id=pm_context.empresa_id,
            rol=component.rol,
            provided_rate=tarifa_hora,
        )
    elif rol is not None:
        component.tarifa_hora = resolve_budget_labor_rate(
            db,
            empresa_id=pm_context.empresa_id,
            rol=component.rol,
            provided_rate=None,
        )
    if activo is not None:
        component.activo = activo
    component.costo_total = quantize_rate(decimal_or_zero(component.horas_por_unidad) * decimal_or_zero(component.tarifa_hora))
    db.flush()
    refresh_budget_item_tree(db, item)
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=item.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget_item.labor.update",
            entity_name="pm_presupuesto_partida_mano_obra",
            entity_id=component.id,
            ip_address=ip_address,
            metadata_json={"project_id": item.proyecto_id, "item_id": item.id},
        )
    )
    return serialize_budget_item_labor(component)


def deactivate_budget_item_labor(
    db: Session,
    pm_context: PMContext,
    *,
    component_id: str,
    ip_address: str | None,
) -> PMPresupuestoPartidaManoObraOut:
    ensure_pm_budget_manage_access(pm_context)
    component = get_budget_item_labor_for_company(db, pm_context.empresa_id, component_id)
    item = get_budget_item_for_company(db, pm_context.empresa_id, component.partida_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, item.presupuesto_id)
    ensure_budget_editable(budget)
    component.activo = False
    db.flush()
    refresh_budget_item_tree(db, item)
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=item.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget_item.labor.deactivate",
            entity_name="pm_presupuesto_partida_mano_obra",
            entity_id=component.id,
            ip_address=ip_address,
            metadata_json={"project_id": item.proyecto_id, "item_id": item.id},
        )
    )
    return serialize_budget_item_labor(component)


def add_budget_indirect(
    db: Session,
    pm_context: PMContext,
    *,
    budget_id: str,
    nombre: str,
    tipo: str,
    porcentaje: Decimal | None,
    monto: Decimal,
    ip_address: str | None,
) -> PMPresupuestoIndirectoOut:
    ensure_pm_budget_manage_access(pm_context)
    budget = get_budget_for_company(db, pm_context.empresa_id, budget_id)
    ensure_budget_editable(budget)
    normalized_type = normalize_budget_indirect_type(tipo)
    indirect = PMPresupuestoIndirecto(
        empresa_id=pm_context.empresa_id,
        presupuesto_id=budget.id,
        proyecto_id=budget.proyecto_id,
        nombre=normalize_required_text(nombre, "Nombre"),
        tipo=normalized_type,
        porcentaje=decimal_or_zero(porcentaje) if porcentaje is not None else None,
        monto=decimal_or_zero(monto),
        activo=True,
    )
    db.add(indirect)
    db.flush()
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget.indirect.create",
            entity_name="pm_presupuesto_indirecto",
            entity_id=indirect.id,
            ip_address=ip_address,
            metadata_json={"project_id": budget.proyecto_id, "budget_id": budget.id},
        )
    )
    return serialize_budget_indirect(indirect)


def update_budget_indirect(
    db: Session,
    pm_context: PMContext,
    *,
    indirect_id: str,
    nombre: str | None,
    tipo: str | None,
    porcentaje: Decimal | None,
    monto: Decimal | None,
    activo: bool | None,
    ip_address: str | None,
) -> PMPresupuestoIndirectoOut:
    ensure_pm_budget_manage_access(pm_context)
    indirect = get_budget_indirect_for_company(db, pm_context.empresa_id, indirect_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, indirect.presupuesto_id)
    ensure_budget_editable(budget)
    if nombre is not None:
        indirect.nombre = normalize_required_text(nombre, "Nombre")
    if tipo is not None:
        indirect.tipo = normalize_budget_indirect_type(tipo)
    if porcentaje is not None:
        indirect.porcentaje = decimal_or_zero(porcentaje)
    if monto is not None:
        indirect.monto = decimal_or_zero(monto)
    if activo is not None:
        indirect.activo = activo
    db.flush()
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget.indirect.update",
            entity_name="pm_presupuesto_indirecto",
            entity_id=indirect.id,
            ip_address=ip_address,
            metadata_json={"project_id": budget.proyecto_id, "budget_id": budget.id},
        )
    )
    return serialize_budget_indirect(indirect)


def deactivate_budget_indirect(
    db: Session,
    pm_context: PMContext,
    *,
    indirect_id: str,
    ip_address: str | None,
) -> PMPresupuestoIndirectoOut:
    ensure_pm_budget_manage_access(pm_context)
    indirect = get_budget_indirect_for_company(db, pm_context.empresa_id, indirect_id)
    budget = get_budget_for_company(db, pm_context.empresa_id, indirect.presupuesto_id)
    ensure_budget_editable(budget)
    indirect.activo = False
    db.flush()
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(
        AuditLog(
            empresa_id=pm_context.empresa_id,
            usuario_id=pm_context.user.id,
            action="pm.budget.indirect.deactivate",
            entity_name="pm_presupuesto_indirecto",
            entity_id=indirect.id,
            ip_address=ip_address,
            metadata_json={"project_id": budget.proyecto_id, "budget_id": budget.id},
        )
    )
    return serialize_budget_indirect(indirect)


def get_project_budget_vs_actual(
    db: Session,
    pm_context: PMContext,
    project_id: str,
) -> PMBudgetVsActualOut:
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    if pm_context.config.pm_materiales_enabled:
        refresh_project_material_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    summary = (
        refresh_project_labor_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
        if pm_context.config.pm_tiempo_enabled
        else get_or_create_project_cost_summary_row(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    )
    budget = refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    recalculate_project_cost_summary_totals(project, summary)
    db.flush()
    return build_budget_vs_actual_response(project, summary, budget)


def get_project_costs(
    db: Session,
    pm_context: PMContext,
    project_id: str,
) -> PMProjectCostsOut:
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    if pm_context.config.pm_materiales_enabled:
        refresh_project_material_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    summary = (
        refresh_project_labor_costs(db, empresa_id=pm_context.empresa_id, project_id=project.id)
        if pm_context.config.pm_tiempo_enabled
        else get_or_create_project_cost_summary_row(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    )
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    recalculate_project_cost_summary_totals(project, summary)
    db.flush()
    return build_project_costs_response(project, summary)


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

    material_estimated_total = db.scalar(
        select(func.coalesce(func.sum(PMProyectoCostoResumen.costo_materiales_estimado), 0)).where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
        )
    ) or ZERO
    material_real_total = db.scalar(
        select(func.coalesce(func.sum(PMProyectoCostoResumen.costo_materiales_real), 0)).where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
        )
    ) or ZERO
    material_variation_total = decimal_or_zero(material_real_total) - decimal_or_zero(material_estimated_total)
    labor_hours_total = db.scalar(
        select(func.coalesce(func.sum(PMProyectoCostoResumen.horas_totales), 0)).where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
        )
    ) or ZERO
    labor_cost_total = db.scalar(
        select(func.coalesce(func.sum(PMProyectoCostoResumen.costo_horas_real), 0)).where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
        )
    ) or ZERO
    hours_without_rate_total = db.scalar(
        select(func.coalesce(func.sum(PMProyectoCostoResumen.horas_sin_tarifa), 0)).where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
        )
    ) or ZERO
    total_real_cost = db.scalar(
        select(func.coalesce(func.sum(PMProyectoCostoResumen.costo_total_real), 0)).where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
        )
    ) or ZERO
    total_budget_cost = db.scalar(
        select(func.coalesce(func.sum(PMProyectoCostoResumen.presupuesto_estimado), 0)).where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
        )
    ) or ZERO
    total_estimated_margin = db.scalar(
        select(func.coalesce(func.sum(PMProyectoCostoResumen.margen_estimado), 0)).where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
        )
    ) or ZERO
    projects_without_budget_count = db.scalar(
        select(func.count(PMProyecto.id))
        .select_from(PMProyecto)
        .outerjoin(PMProyectoCostoResumen, PMProyectoCostoResumen.proyecto_id == PMProyecto.id)
        .where(
            PMProyecto.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
            func.coalesce(PMProyectoCostoResumen.presupuesto_estimado, 0) <= 0,
        )
    ) or 0

    top_material_cost_projects = db.execute(
        select(PMProyectoCostoResumen, PMProyecto)
        .join(PMProyecto, PMProyecto.id == PMProyectoCostoResumen.proyecto_id)
        .where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
        )
        .order_by(PMProyectoCostoResumen.costo_materiales_real.desc(), PMProyecto.nombre.asc())
        .limit(5)
    ).all()
    over_budget_material_projects = db.execute(
        select(PMProyectoCostoResumen, PMProyecto)
        .join(PMProyecto, PMProyecto.id == PMProyectoCostoResumen.proyecto_id)
        .where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
            PMProyectoCostoResumen.costo_materiales_real > func.coalesce(PMProyectoCostoResumen.presupuesto_estimado, 0),
        )
        .order_by((PMProyectoCostoResumen.costo_materiales_real - func.coalesce(PMProyectoCostoResumen.presupuesto_estimado, 0)).desc())
        .limit(5)
    ).all()
    top_total_cost_projects = db.execute(
        select(PMProyectoCostoResumen, PMProyecto)
        .join(PMProyecto, PMProyecto.id == PMProyectoCostoResumen.proyecto_id)
        .where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
        )
        .order_by(PMProyectoCostoResumen.costo_total_real.desc(), PMProyecto.nombre.asc())
        .limit(5)
    ).all()
    over_budget_total_projects = db.execute(
        select(PMProyectoCostoResumen, PMProyecto)
        .join(PMProyecto, PMProyecto.id == PMProyectoCostoResumen.proyecto_id)
        .where(
            PMProyectoCostoResumen.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
            PMProyectoCostoResumen.costo_total_real > func.coalesce(PMProyectoCostoResumen.presupuesto_estimado, 0),
        )
        .order_by((PMProyectoCostoResumen.costo_total_real - func.coalesce(PMProyectoCostoResumen.presupuesto_estimado, 0)).desc())
        .limit(5)
    ).all()
    projects_without_budget_rows = db.execute(
        select(PMProyecto, PMProyectoCostoResumen)
        .select_from(PMProyecto)
        .outerjoin(PMProyectoCostoResumen, PMProyectoCostoResumen.proyecto_id == PMProyecto.id)
        .where(
            PMProyecto.empresa_id == pm_context.empresa_id,
            PMProyecto.activo == True,
            func.coalesce(PMProyectoCostoResumen.presupuesto_estimado, 0) <= 0,
        )
        .order_by(PMProyecto.nombre.asc())
        .limit(5)
    ).all()
    top_users_by_hours_rows = db.execute(
        select(
            PMTimeEntry.usuario_id,
            PMTimeEntry.usuario_email_snapshot,
            PMTimeEntry.usuario_nombre_snapshot,
            func.coalesce(func.sum(PMTimeEntry.horas), 0),
            func.coalesce(func.sum(PMTimeEntry.costo_total_snapshot), 0),
        )
        .where(
            PMTimeEntry.empresa_id == pm_context.empresa_id,
            PMTimeEntry.activo == True,
        )
        .group_by(
            PMTimeEntry.usuario_id,
            PMTimeEntry.usuario_email_snapshot,
            PMTimeEntry.usuario_nombre_snapshot,
        )
        .order_by(
            desc(func.sum(PMTimeEntry.horas)),
            func.lower(func.coalesce(PMTimeEntry.usuario_nombre_snapshot, PMTimeEntry.usuario_email_snapshot, "")),
        )
        .limit(5)
    ).all()
    top_users_by_cost_rows = db.execute(
        select(
            PMTimeEntry.usuario_id,
            PMTimeEntry.usuario_email_snapshot,
            PMTimeEntry.usuario_nombre_snapshot,
            func.coalesce(func.sum(PMTimeEntry.horas), 0),
            func.coalesce(func.sum(PMTimeEntry.costo_total_snapshot), 0),
        )
        .where(
            PMTimeEntry.empresa_id == pm_context.empresa_id,
            PMTimeEntry.activo == True,
        )
        .group_by(
            PMTimeEntry.usuario_id,
            PMTimeEntry.usuario_email_snapshot,
            PMTimeEntry.usuario_nombre_snapshot,
        )
        .order_by(
            desc(func.sum(PMTimeEntry.costo_total_snapshot)),
            func.lower(func.coalesce(PMTimeEntry.usuario_nombre_snapshot, PMTimeEntry.usuario_email_snapshot, "")),
        )
        .limit(5)
    ).all()

    return PMDashboardOut(
        kpis=PMDashboardKpis(
            proyectos_activos=active_projects,
            proyectos_atrasados=delayed_projects,
            tareas_vencidas=overdue_tasks,
            tareas_pendientes=task_counts.get("pendiente", 0),
            tareas_en_progreso=task_counts.get("en_progreso", 0),
            tareas_completadas=task_counts.get("completada", 0),
            costo_materiales_estimado_total=decimal_or_zero(material_estimated_total),
            costo_materiales_real_total=decimal_or_zero(material_real_total),
            variacion_materiales_total=decimal_or_zero(material_variation_total),
            horas_totales=decimal_or_zero(labor_hours_total),
            costo_horas_real=decimal_or_zero(labor_cost_total),
            horas_sin_tarifa=decimal_or_zero(hours_without_rate_total),
            costo_total_real=decimal_or_zero(total_real_cost),
            presupuesto_detallado_total=decimal_or_zero(total_budget_cost),
            margen_estimado_total=decimal_or_zero(total_estimated_margin),
            proyectos_sin_presupuesto=projects_without_budget_count,
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
        top_proyectos_por_costo_materiales=[
            build_dashboard_project_cost_item(summary, project)
            for summary, project in top_material_cost_projects
        ],
        proyectos_sobre_presupuesto_materiales=[
            build_dashboard_project_cost_item(summary, project)
            for summary, project in over_budget_material_projects
        ],
        top_proyectos_por_costo_total=[
            build_dashboard_project_cost_item(summary, project)
            for summary, project in top_total_cost_projects
        ],
        proyectos_sobre_presupuesto=[
            build_dashboard_project_cost_item(summary, project)
            for summary, project in over_budget_total_projects
        ],
        proyectos_sin_presupuesto=[
            build_dashboard_project_cost_item(
                summary or PMProyectoCostoResumen(empresa_id=project.empresa_id, proyecto_id=project.id),
                project,
            )
            for project, summary in projects_without_budget_rows
        ],
        top_usuarios_por_horas=[
            PMDashboardUserMetricItem(
                usuario_id=user_id,
                usuario_email=email,
                usuario_nombre=name,
                horas_totales=decimal_or_zero(hours_total),
                costo_total=decimal_or_zero(cost_total),
            )
            for user_id, email, name, hours_total, cost_total in top_users_by_hours_rows
        ],
        top_usuarios_por_costo=[
            PMDashboardUserMetricItem(
                usuario_id=user_id,
                usuario_email=email,
                usuario_nombre=name,
                horas_totales=decimal_or_zero(hours_total),
                costo_total=decimal_or_zero(cost_total),
            )
            for user_id, email, name, hours_total, cost_total in top_users_by_cost_rows
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
