from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator


class PMConfigOut(BaseModel):
    empresa_id: str
    pm_enabled: bool
    pm_tareas_enabled: bool
    pm_materiales_enabled: bool
    pm_tiempo_enabled: bool
    pm_templates_enabled: bool
    pm_comercial_enabled: bool
    pm_portal_enabled: bool
    created_at: datetime
    updated_at: datetime


class PMStatusCount(BaseModel):
    estatus: str
    total: int


class PMTaskStats(BaseModel):
    total: int = 0
    pendientes: int = 0
    en_progreso: int = 0
    en_revision: int = 0
    completadas: int = 0
    canceladas: int = 0
    vencidas: int = 0


class PMCommentOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str | None = None
    tarea_id: str | None = None
    body: str
    created_by: str | None = None
    created_by_nombre_snapshot: str | None = None
    externo: bool = False
    autor_nombre_snapshot: str | None = None
    invitado_externo_id: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class PMSubtareaOut(BaseModel):
    id: str
    empresa_id: str
    tarea_id: str
    titulo: str
    estatus: str
    orden: int
    asignado_user_id: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class PMChecklistItemOut(BaseModel):
    id: str
    empresa_id: str
    tarea_id: str
    titulo: str
    completado: bool
    orden: int
    activo: bool
    created_at: datetime
    updated_at: datetime


class PMProyectoMiembroCreate(BaseModel):
    usuario_id: str | None = None
    email: EmailStr | None = None
    nombre_snapshot: str | None = Field(default=None, max_length=160)
    rol_en_proyecto: str = Field(default="colaborador", min_length=4, max_length=20)


class PMProyectoMiembroOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    usuario_id: str | None = None
    email: EmailStr | None = None
    nombre_snapshot: str | None = None
    rol_en_proyecto: str
    activo: bool
    created_at: datetime
    updated_at: datetime


class PMProyectoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=180)
    codigo: str | None = Field(default=None, max_length=60)
    descripcion: str | None = None
    tipo_proyecto: str | None = Field(default=None, max_length=80)
    estatus: str = Field(default="borrador", min_length=4, max_length=20)
    prioridad: str = Field(default="media", min_length=4, max_length=20)
    fecha_inicio: date | None = None
    fecha_fin_planificada: date | None = None
    fecha_fin_real: date | None = None
    porcentaje_avance: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    responsable_user_id: str | None = None
    responsable_nombre_snapshot: str | None = Field(default=None, max_length=160)
    cliente_nombre_snapshot: str | None = Field(default=None, max_length=180)
    presupuesto_estimado: Decimal | None = Field(default=Decimal("0"), ge=0)
    activo: bool = True


class PMProyectoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=180)
    codigo: str | None = Field(default=None, max_length=60)
    descripcion: str | None = None
    tipo_proyecto: str | None = Field(default=None, max_length=80)
    estatus: str | None = Field(default=None, min_length=4, max_length=20)
    prioridad: str | None = Field(default=None, min_length=4, max_length=20)
    fecha_inicio: date | None = None
    fecha_fin_planificada: date | None = None
    fecha_fin_real: date | None = None
    porcentaje_avance: Decimal | None = Field(default=None, ge=0, le=100)
    responsable_user_id: str | None = None
    responsable_nombre_snapshot: str | None = Field(default=None, max_length=160)
    cliente_nombre_snapshot: str | None = Field(default=None, max_length=180)
    presupuesto_estimado: Decimal | None = Field(default=None, ge=0)
    activo: bool | None = None


class PMProyectoOut(BaseModel):
    id: str
    empresa_id: str
    nombre: str
    codigo: str | None = None
    descripcion: str | None = None
    tipo_proyecto: str | None = None
    estatus: str
    prioridad: str
    fecha_inicio: date | None = None
    fecha_fin_planificada: date | None = None
    fecha_fin_real: date | None = None
    porcentaje_avance: Decimal
    responsable_user_id: str | None = None
    responsable_nombre_snapshot: str | None = None
    cliente_nombre_snapshot: str | None = None
    presupuesto_estimado: Decimal | None = None
    activo: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    miembros_activos: int = 0
    task_stats: PMTaskStats = Field(default_factory=PMTaskStats)
    comments: list[PMCommentOut] = Field(default_factory=list)


class PMProyectoListResponse(BaseModel):
    items: list[PMProyectoOut]
    total: int
    limit: int
    offset: int


class PMTareaCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=180)
    descripcion: str | None = None
    estatus: str = Field(default="pendiente", min_length=4, max_length=20)
    prioridad: str = Field(default="media", min_length=4, max_length=20)
    asignado_user_id: str | None = None
    asignado_nombre_snapshot: str | None = Field(default=None, max_length=160)
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None
    fecha_completada: date | None = None
    estimacion_horas: Decimal | None = Field(default=Decimal("0"), ge=0)
    porcentaje_avance: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    orden: int = Field(default=0, ge=0)
    bloqueada: bool = False
    requiere_materiales: bool = False
    requiere_compra: bool = False
    requiere_venta_pos: bool = False
    requiere_factura: bool = False
    activo: bool = True


class PMTareaUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=180)
    descripcion: str | None = None
    estatus: str | None = Field(default=None, min_length=4, max_length=20)
    prioridad: str | None = Field(default=None, min_length=4, max_length=20)
    asignado_user_id: str | None = None
    asignado_nombre_snapshot: str | None = Field(default=None, max_length=160)
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None
    fecha_completada: date | None = None
    estimacion_horas: Decimal | None = Field(default=None, ge=0)
    porcentaje_avance: Decimal | None = Field(default=None, ge=0, le=100)
    orden: int | None = Field(default=None, ge=0)
    bloqueada: bool | None = None
    requiere_materiales: bool | None = None
    requiere_compra: bool | None = None
    requiere_venta_pos: bool | None = None
    requiere_factura: bool | None = None
    activo: bool | None = None


class PMTaskBlockerOut(BaseModel):
    tarea_id: str
    titulo: str
    estatus: str


class PMTareaDependenciaCreate(BaseModel):
    depende_de_tarea_id: str
    tipo_dependencia: str = Field(default="finish_to_start", min_length=1, max_length=30)
    lag_dias: int = Field(default=0, ge=0)
    bloqueante: bool = True
    notas: str | None = None


class PMTareaDependenciaOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    tarea_id: str
    tarea_titulo: str | None = None
    depende_de_tarea_id: str
    depende_de_tarea_titulo: str | None = None
    depende_de_tarea_estatus: str | None = None
    tipo_dependencia: str
    lag_dias: int = 0
    bloqueante: bool
    notas: str | None = None
    activo: bool
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMTaskDependenciesOut(BaseModel):
    task_id: str
    is_blocked: bool = False
    dependencies_count: int = 0
    blockers_count: int = 0
    successors_count: int = 0
    dependencies: list[PMTareaDependenciaOut] = Field(default_factory=list)
    blockers: list[PMTaskBlockerOut] = Field(default_factory=list)
    successors: list[PMTaskBlockerOut] = Field(default_factory=list)


class PMDependencyStateOut(BaseModel):
    task_id: str = ""
    is_blocked: bool = False
    can_start: bool = True
    dependencies_count: int = 0
    blockers_count: int = 0
    successors_count: int = 0
    title: str = ""
    detail: str = ""
    badge_label: str | None = None
    badge_tone: str = "neutral"
    blocking_task_names: list[str] = Field(default_factory=list)
    desbloquea_a: list[str] = Field(default_factory=list)
    dependencies: list[PMTareaDependenciaOut] = Field(default_factory=list)
    blockers: list[PMTaskBlockerOut] = Field(default_factory=list)
    successors: list[PMTaskBlockerOut] = Field(default_factory=list)


class PMScheduleSuggestionOut(BaseModel):
    task_id: str
    fecha_inicio_actual: date | None = None
    fecha_fin_actual: date | None = None
    fecha_inicio_sugerida: date | None = None
    fecha_fin_sugerida: date | None = None
    dias_desplazamiento: int = 0
    fuera_de_secuencia: bool = False
    razon: str | None = None


class PMTareaListItem(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    titulo: str
    descripcion: str | None = None
    estatus: str
    prioridad: str
    asignado_user_id: str | None = None
    asignado_nombre_snapshot: str | None = None
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None
    fecha_completada: date | None = None
    estimacion_horas: Decimal | None = None
    porcentaje_avance: Decimal
    orden: int
    bloqueada: bool
    requiere_materiales: bool
    requiere_compra: bool
    requiere_venta_pos: bool
    requiere_factura: bool
    activo: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    subtareas_count: int = 0
    checklist_total: int = 0
    checklist_completado: int = 0
    is_blocked: bool = False
    blockers_count: int = 0
    dependencies_count: int = 0
    successors_count: int = 0
    blockers: list[PMTaskBlockerOut] = Field(default_factory=list)


class PMTareaOut(PMTareaListItem):
    subtasks: list[PMSubtareaOut] = Field(default_factory=list)
    checklist_items: list[PMChecklistItemOut] = Field(default_factory=list)
    comments: list[PMCommentOut] = Field(default_factory=list)
    dependencies: list[PMTareaDependenciaOut] = Field(default_factory=list)
    successors: list[PMTaskBlockerOut] = Field(default_factory=list)


class PMPlanningTaskOut(PMTareaListItem):
    dependency_state: PMDependencyStateOut | None = None
    schedule_suggestion: PMScheduleSuggestionOut | None = None
    es_critica: bool = False
    holgura_dias: int | None = None


class PMTareaListResponse(BaseModel):
    items: list[PMTareaListItem]
    total: int
    limit: int
    offset: int


class PMSubtareaCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=180)
    estatus: str = Field(default="pendiente", min_length=4, max_length=20)
    orden: int = Field(default=0, ge=0)
    asignado_user_id: str | None = None


class PMSubtareaUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=180)
    estatus: str | None = Field(default=None, min_length=4, max_length=20)
    orden: int | None = Field(default=None, ge=0)
    asignado_user_id: str | None = None
    activo: bool | None = None


class PMChecklistItemCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=180)
    completado: bool = False
    orden: int = Field(default=0, ge=0)


class PMChecklistItemUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=180)
    completado: bool | None = None
    orden: int | None = Field(default=None, ge=0)
    activo: bool | None = None


class PMComentarioCreate(BaseModel):
    body: str = Field(min_length=1)


class PMDocumentoCreate(BaseModel):
    tipo_documento: str = Field(default="otro", min_length=3, max_length=40)
    nombre: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=2000)
    visible_externo: bool = False


class PMDocumentoUpdate(BaseModel):
    tipo_documento: str | None = Field(default=None, min_length=3, max_length=40)
    nombre: str | None = Field(default=None, min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=2000)
    visible_externo: bool | None = None
    activo: bool | None = None


class PMDocumentoOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    tipo_documento: str
    nombre: str
    descripcion: str | None = None
    url_archivo: str
    nombre_archivo: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    visible_externo: bool
    activo: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMAprobacionCreate(BaseModel):
    tipo_aprobacion: str = Field(default="otro", min_length=3, max_length=40)
    titulo: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    entidad_tipo: str | None = Field(default=None, max_length=40)
    entidad_id: str | None = Field(default=None, max_length=36)


class PMAprobacionResolve(BaseModel):
    comentario_resolucion: str | None = Field(default=None, max_length=4000)


class PMAprobacionOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    tipo_aprobacion: str
    titulo: str
    descripcion: str | None = None
    estatus: str
    entidad_tipo: str | None = None
    entidad_id: str | None = None
    solicitado_por: str | None = None
    solicitado_por_nombre: str | None = None
    solicitado_en: datetime | None = None
    resuelto_por: str | None = None
    resuelto_por_nombre: str | None = None
    resuelto_en: datetime | None = None
    comentario_resolucion: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class PMInvitadoExternoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=180)
    email: EmailStr | None = None
    modo_acceso: str = Field(default="solo_lectura", min_length=4, max_length=20)
    expira_at: datetime | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_empty_email(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("expira_at", mode="before")
    @classmethod
    def normalize_empty_expiry(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("expira_at", mode="after")
    @classmethod
    def normalize_expiry_timezone(cls, value: datetime | None):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class PMInvitadoExternoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=180)
    email: EmailStr | None = None
    modo_acceso: str | None = Field(default=None, min_length=4, max_length=20)
    expira_at: datetime | None = None
    activo: bool | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_empty_email(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("expira_at", mode="before")
    @classmethod
    def normalize_empty_expiry(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("expira_at", mode="after")
    @classmethod
    def normalize_expiry_timezone(cls, value: datetime | None):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class PMInvitadoExternoOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    nombre: str
    email: str | None = None
    modo_acceso: str
    token_preview: str | None = None
    activo: bool
    revocado_at: datetime | None = None
    expira_at: datetime | None = None
    ultimo_acceso_at: datetime | None = None
    total_accesos: int = 0
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMInvitadoExternoCreatedOut(PMInvitadoExternoOut):
    token: str
    portal_path: str
    portal_url: str | None = None


class PMPortalCommentCreate(BaseModel):
    autor_nombre: str | None = Field(default=None, max_length=160)
    body: str = Field(min_length=1, max_length=1000)


class PMPortalCommentOut(BaseModel):
    body: str
    autor_nombre: str
    created_at: datetime


class PMPortalDocumentOut(BaseModel):
    nombre: str
    tipo_documento: str
    descripcion: str | None = None
    url_archivo: str
    nombre_archivo: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime


class PMPortalTaskItemOut(BaseModel):
    titulo: str
    estatus: str
    porcentaje_avance: Decimal = Decimal("0")
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None


class PMPortalTaskSummaryOut(BaseModel):
    total: int = 0
    pendientes: int = 0
    en_progreso: int = 0
    en_revision: int = 0
    completadas: int = 0


class PMPortalAccessLogOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    invitado_externo_id: str | None = None
    accion: str
    resultado: str
    detalle: str | None = None
    created_at: datetime


class PMPortalProjectOut(BaseModel):
    nombre: str
    codigo: str | None = None
    estatus: str
    prioridad: str | None = None
    porcentaje_avance: Decimal = Decimal("0")
    fecha_inicio: date | None = None
    fecha_fin_planificada: date | None = None
    access_mode: str = "solo_lectura"
    can_comment: bool = False
    invite_name: str | None = None
    tasks_summary: PMPortalTaskSummaryOut = Field(default_factory=PMPortalTaskSummaryOut)
    tasks: list[PMPortalTaskItemOut] = Field(default_factory=list)
    documents: list[PMPortalDocumentOut] = Field(default_factory=list)
    comments: list[PMPortalCommentOut] = Field(default_factory=list)


class PMDashboardDueItem(BaseModel):
    project_id: str | None = None
    task_id: str | None = None
    proyecto_nombre: str
    titulo: str
    estatus: str
    prioridad: str
    fecha: date | None = None
    responsable_nombre: str | None = None


class PMDashboardKpis(BaseModel):
    proyectos_activos: int = 0
    proyectos_atrasados: int = 0
    tareas_vencidas: int = 0
    tareas_pendientes: int = 0
    tareas_en_progreso: int = 0
    tareas_completadas: int = 0
    tareas_bloqueadas: int = 0
    tareas_criticas: int = 0
    alertas_activas: int = 0
    costo_materiales_estimado_total: Decimal = Decimal("0")
    costo_materiales_real_total: Decimal = Decimal("0")
    variacion_materiales_total: Decimal = Decimal("0")
    horas_totales: Decimal = Decimal("0")
    costo_horas_real: Decimal = Decimal("0")
    horas_sin_tarifa: Decimal = Decimal("0")
    costo_total_real: Decimal = Decimal("0")
    presupuesto_detallado_total: Decimal = Decimal("0")
    margen_estimado_total: Decimal = Decimal("0")
    proyectos_sin_presupuesto: int = 0


class PMDashboardProjectCostItem(BaseModel):
    project_id: str
    proyecto_nombre: str
    costo_materiales_real: Decimal = Decimal("0")
    costo_materiales_estimado: Decimal = Decimal("0")
    costo_horas_real: Decimal = Decimal("0")
    horas_totales: Decimal = Decimal("0")
    costo_total_real: Decimal = Decimal("0")
    variacion_materiales: Decimal = Decimal("0")
    presupuesto_estimado: Decimal = Decimal("0")
    variacion_presupuesto: Decimal = Decimal("0")
    presupuesto_detallado_costo: Decimal = Decimal("0")
    presupuesto_detallado_venta: Decimal = Decimal("0")
    variacion_vs_presupuesto_detallado: Decimal = Decimal("0")
    margen_estimado: Decimal | None = None
    presupuesto_origen: str = "simple"


class PMDashboardUserMetricItem(BaseModel):
    usuario_id: str | None = None
    usuario_email: str | None = None
    usuario_nombre: str | None = None
    horas_totales: Decimal = Decimal("0")
    costo_total: Decimal = Decimal("0")


class PMDashboardOut(BaseModel):
    kpis: PMDashboardKpis
    proyectos_por_estatus: list[PMStatusCount] = Field(default_factory=list)
    tareas_por_estatus: list[PMStatusCount] = Field(default_factory=list)
    proximos_vencimientos: list[PMDashboardDueItem] = Field(default_factory=list)
    tareas_criticas_proximas: list[PMDashboardDueItem] = Field(default_factory=list)
    proyectos_proximos: list[PMDashboardDueItem] = Field(default_factory=list)
    tareas_vencidas_items: list[PMDashboardDueItem] = Field(default_factory=list)
    top_proyectos_por_costo_materiales: list[PMDashboardProjectCostItem] = Field(default_factory=list)
    proyectos_sobre_presupuesto_materiales: list[PMDashboardProjectCostItem] = Field(default_factory=list)
    top_proyectos_por_costo_total: list[PMDashboardProjectCostItem] = Field(default_factory=list)
    proyectos_sobre_presupuesto: list[PMDashboardProjectCostItem] = Field(default_factory=list)
    proyectos_sin_presupuesto: list[PMDashboardProjectCostItem] = Field(default_factory=list)
    top_usuarios_por_horas: list[PMDashboardUserMetricItem] = Field(default_factory=list)
    top_usuarios_por_costo: list[PMDashboardUserMetricItem] = Field(default_factory=list)


class PMCriticalPathTaskOut(BaseModel):
    task_id: str
    titulo: str
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    duracion_dias: int = 0
    holgura_dias: int | None = None


class PMCriticalPathOut(BaseModel):
    critical_task_ids: list[str] = Field(default_factory=list)
    critical_path: list[PMCriticalPathTaskOut] = Field(default_factory=list)
    total_duration_days: int = 0
    has_cycle: bool = False
    warnings: list[str] = Field(default_factory=list)


class PMAlertOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    tarea_id: str | None = None
    tarea_titulo: str | None = None
    tipo: str
    severidad: str
    titulo: str
    descripcion: str | None = None
    estatus: str
    dedupe_key: str | None = None
    activa: bool
    created_at: datetime
    updated_at: datetime
    resuelta_at: datetime | None = None
    resuelta_por: str | None = None


class PMAlertResolveRequest(BaseModel):
    comentario: str | None = Field(default=None, max_length=2000)


class PMPlanningSummaryOut(BaseModel):
    total_tareas: int = 0
    tareas_criticas: int = 0
    tareas_bloqueadas: int = 0
    tareas_fuera_de_secuencia: int = 0
    tareas_vencidas: int = 0
    alertas_abiertas: int = 0


class PMProjectPlanningOut(BaseModel):
    project_id: str
    tasks: list[PMPlanningTaskOut] = Field(default_factory=list)
    dependencies: list[PMTareaDependenciaOut] = Field(default_factory=list)
    dependency_state_by_task_id: dict[str, PMDependencyStateOut] = Field(default_factory=dict)
    schedule_suggestions_by_task_id: dict[str, PMScheduleSuggestionOut] = Field(default_factory=dict)
    critical_path: PMCriticalPathOut = Field(default_factory=PMCriticalPathOut)
    alerts_summary: PMPlanningSummaryOut = Field(default_factory=PMPlanningSummaryOut)


class PMProjectMembersListResponse(BaseModel):
    items: list[PMProyectoMiembroOut]


class PMProyectoMaterialPlanCreate(BaseModel):
    tarea_id: str | None = None
    material_id: str
    cantidad_planificada: Decimal = Field(gt=0)
    costo_unitario_estimado: Decimal | None = Field(default=None, ge=0)
    observaciones: str | None = None


class PMProyectoMaterialPlanUpdate(BaseModel):
    tarea_id: str | None = None
    material_id: str | None = None
    cantidad_planificada: Decimal | None = Field(default=None, gt=0)
    costo_unitario_estimado: Decimal | None = Field(default=None, ge=0)
    observaciones: str | None = None
    activo: bool | None = None


class PMProyectoMaterialPlanOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    tarea_id: str | None = None
    tarea_titulo: str | None = None
    material_id: str
    material_nombre_snapshot: str
    material_sku_snapshot: str
    cantidad_planificada: Decimal
    cantidad_consumida_real: Decimal = Decimal("0")
    cantidad_pendiente: Decimal = Decimal("0")
    unidad: str
    costo_unitario_estimado: Decimal = Decimal("0")
    costo_total_estimado: Decimal = Decimal("0")
    estatus: str
    observaciones: str | None = None
    activo: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMProyectoMaterialConsumoOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    tarea_id: str | None = None
    tarea_titulo: str | None = None
    material_id: str
    material_nombre_snapshot: str
    material_sku_snapshot: str
    movimiento_id: str | None = None
    requisicion_id: str | None = None
    requisicion_detalle_id: str | None = None
    cantidad_consumida: Decimal
    unidad: str
    costo_unitario_snapshot: Decimal = Decimal("0")
    costo_total_snapshot: Decimal = Decimal("0")
    origen: str
    documento_referencia: str | None = None
    notas: str | None = None
    activo: bool
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMProyectoMaterialSummaryOut(BaseModel):
    costo_estimado: Decimal = Decimal("0")
    costo_real: Decimal = Decimal("0")
    variacion: Decimal = Decimal("0")
    porcentaje_consumido: Decimal = Decimal("0")
    materiales_pendientes: int = 0
    materiales_sobreconsumidos: int = 0
    total_materiales_planeados: Decimal = Decimal("0")
    total_materiales_consumidos: Decimal = Decimal("0")
    planes_count: int = 0
    consumos_count: int = 0


class PMProyectoMaterialesOut(BaseModel):
    summary: PMProyectoMaterialSummaryOut
    plans: list[PMProyectoMaterialPlanOut] = Field(default_factory=list)
    consumptions: list[PMProyectoMaterialConsumoOut] = Field(default_factory=list)


class PMCreateProjectRequisitionItem(BaseModel):
    plan_id: str
    cantidad_solicitada: Decimal = Field(gt=0)


class PMCreateProjectRequisitionRequest(BaseModel):
    almacen_destino_id: str
    items: list[PMCreateProjectRequisitionItem] = Field(min_length=1)
    notas: str | None = None


class PMProjectCostsOut(BaseModel):
    costo_materiales_estimado: Decimal = Decimal("0")
    costo_materiales_real: Decimal = Decimal("0")
    variacion_materiales: Decimal = Decimal("0")
    compras_estimado: Decimal = Decimal("0")
    costo_horas_real: Decimal = Decimal("0")
    horas_totales: Decimal = Decimal("0")
    horas_sin_tarifa: Decimal = Decimal("0")
    costo_total_real: Decimal = Decimal("0")
    presupuesto_estimado: Decimal = Decimal("0")
    variacion_presupuesto: Decimal = Decimal("0")
    presupuesto_detallado_costo: Decimal = Decimal("0")
    presupuesto_detallado_venta: Decimal = Decimal("0")
    variacion_vs_presupuesto_detallado: Decimal = Decimal("0")
    presupuesto_origen: str = "simple"
    margen_estimado: Decimal | None = None


class PMPresupuestoCreate(BaseModel):
    nombre: str = Field(default="Presupuesto base", min_length=1, max_length=180)
    moneda: str = Field(default="MXN", min_length=3, max_length=8)
    indirectos_pct: Decimal = Field(default=Decimal("0"), ge=0)
    utilidad_pct: Decimal = Field(default=Decimal("0"), ge=0)
    notas: str | None = None


class PMPresupuestoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=180)
    moneda: str | None = Field(default=None, min_length=3, max_length=8)
    indirectos_pct: Decimal | None = Field(default=None, ge=0)
    notas: str | None = None
    activo: bool | None = None


class PMPresupuestoPartidaMaterialCreate(BaseModel):
    material_id: str | None = None
    material_nombre_snapshot: str | None = Field(default=None, max_length=180)
    material_sku_snapshot: str | None = Field(default=None, max_length=60)
    unidad: str | None = Field(default=None, max_length=40)
    cantidad_por_unidad: Decimal = Field(default=Decimal("0"), ge=0)
    costo_unitario: Decimal | None = Field(default=None, ge=0)
    proveedor_nombre_snapshot: str | None = Field(default=None, max_length=180)


class PMPresupuestoPartidaMaterialUpdate(BaseModel):
    material_id: str | None = None
    material_nombre_snapshot: str | None = Field(default=None, max_length=180)
    material_sku_snapshot: str | None = Field(default=None, max_length=60)
    unidad: str | None = Field(default=None, max_length=40)
    cantidad_por_unidad: Decimal | None = Field(default=None, ge=0)
    costo_unitario: Decimal | None = Field(default=None, ge=0)
    proveedor_nombre_snapshot: str | None = Field(default=None, max_length=180)
    activo: bool | None = None


class PMPresupuestoPartidaMaterialOut(BaseModel):
    id: str
    empresa_id: str
    partida_id: str
    proyecto_id: str
    material_id: str | None = None
    material_nombre_snapshot: str
    material_sku_snapshot: str | None = None
    unidad: str | None = None
    cantidad_por_unidad: Decimal = Decimal("0")
    costo_unitario: Decimal = Decimal("0")
    costo_total: Decimal = Decimal("0")
    proveedor_nombre_snapshot: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class PMPresupuestoPartidaManoObraCreate(BaseModel):
    rol: str | None = Field(default=None, max_length=40)
    descripcion: str | None = None
    horas_por_unidad: Decimal = Field(default=Decimal("0"), ge=0)
    tarifa_hora: Decimal = Field(default=Decimal("0"), ge=0)


class PMPresupuestoPartidaManoObraUpdate(BaseModel):
    rol: str | None = Field(default=None, max_length=40)
    descripcion: str | None = None
    horas_por_unidad: Decimal | None = Field(default=None, ge=0)
    tarifa_hora: Decimal | None = Field(default=None, ge=0)
    activo: bool | None = None


class PMPresupuestoPartidaManoObraOut(BaseModel):
    id: str
    empresa_id: str
    partida_id: str
    proyecto_id: str
    rol: str | None = None
    descripcion: str | None = None
    horas_por_unidad: Decimal = Decimal("0")
    tarifa_hora: Decimal = Decimal("0")
    costo_total: Decimal = Decimal("0")
    activo: bool
    created_at: datetime
    updated_at: datetime


class PMPresupuestoPartidaCreate(BaseModel):
    parent_id: str | None = None
    codigo: str | None = Field(default=None, max_length=60)
    nombre: str = Field(min_length=1, max_length=180)
    descripcion: str | None = None
    tipo: str = Field(default="partida", min_length=4, max_length=20)
    unidad: str | None = Field(default=None, max_length=40)
    cantidad: Decimal = Field(default=Decimal("1"), ge=0)
    margen_pct: Decimal = Field(default=Decimal("0"), ge=0)
    precio_unitario_manual: Decimal | None = Field(default=None, ge=0)
    orden: int = Field(default=0, ge=0)


class PMPresupuestoPartidaUpdate(BaseModel):
    parent_id: str | None = None
    codigo: str | None = Field(default=None, max_length=60)
    nombre: str | None = Field(default=None, min_length=1, max_length=180)
    descripcion: str | None = None
    tipo: str | None = Field(default=None, min_length=4, max_length=20)
    unidad: str | None = Field(default=None, max_length=40)
    cantidad: Decimal | None = Field(default=None, ge=0)
    margen_pct: Decimal | None = Field(default=None, ge=0)
    precio_unitario_manual: Decimal | None = Field(default=None, ge=0)
    orden: int | None = Field(default=None, ge=0)
    activo: bool | None = None


class PMPresupuestoPartidaOut(BaseModel):
    id: str
    empresa_id: str
    presupuesto_id: str
    proyecto_id: str
    parent_id: str | None = None
    codigo: str | None = None
    nombre: str
    descripcion: str | None = None
    tipo: str
    unidad: str | None = None
    cantidad: Decimal = Decimal("0")
    costo_unitario: Decimal = Decimal("0")
    precio_unitario: Decimal = Decimal("0")
    precio_unitario_manual: Decimal | None = None
    subtotal_costo: Decimal = Decimal("0")
    subtotal_venta: Decimal = Decimal("0")
    margen_pct: Decimal = Decimal("0")
    orden: int = 0
    activo: bool
    materials: list[PMPresupuestoPartidaMaterialOut] = Field(default_factory=list)
    labor_components: list[PMPresupuestoPartidaManoObraOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PMPresupuestoIndirectoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    tipo: str = Field(default="monto", min_length=4, max_length=20)
    porcentaje: Decimal | None = Field(default=None, ge=0)
    monto: Decimal = Field(default=Decimal("0"), ge=0)


class PMPresupuestoIndirectoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    tipo: str | None = Field(default=None, min_length=4, max_length=20)
    porcentaje: Decimal | None = Field(default=None, ge=0)
    monto: Decimal | None = Field(default=None, ge=0)
    activo: bool | None = None


class PMPresupuestoIndirectoOut(BaseModel):
    id: str
    empresa_id: str
    presupuesto_id: str
    proyecto_id: str
    nombre: str
    tipo: str
    porcentaje: Decimal | None = None
    monto: Decimal = Decimal("0")
    activo: bool
    created_at: datetime
    updated_at: datetime


class PMBudgetVsActualOut(BaseModel):
    project_id: str
    presupuesto_id: str | None = None
    presupuesto_nombre: str | None = None
    presupuesto_estatus: str | None = None
    presupuesto_origen: str = "simple"
    moneda: str = "MXN"
    presupuesto_detallado_costo: Decimal = Decimal("0")
    presupuesto_detallado_venta: Decimal = Decimal("0")
    costo_materiales_real: Decimal = Decimal("0")
    costo_horas_real: Decimal = Decimal("0")
    costo_real_total: Decimal = Decimal("0")
    variacion: Decimal = Decimal("0")
    porcentaje_consumido: Decimal = Decimal("0")
    margen_estimado: Decimal | None = None


class PMPresupuestoOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    nombre: str
    version: int = 1
    estatus: str
    moneda: str = "MXN"
    subtotal_costo: Decimal = Decimal("0")
    subtotal_venta: Decimal = Decimal("0")
    indirectos_pct: Decimal = Decimal("0")
    indirectos_monto: Decimal = Decimal("0")
    utilidad_pct: Decimal = Decimal("0")
    utilidad_monto: Decimal = Decimal("0")
    total_costo: Decimal = Decimal("0")
    total_venta: Decimal = Decimal("0")
    margen_estimado: Decimal = Decimal("0")
    notas: str | None = None
    aprobado_por: str | None = None
    aprobado_at: datetime | None = None
    activo: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[PMPresupuestoPartidaOut] = Field(default_factory=list)
    indirects: list[PMPresupuestoIndirectoOut] = Field(default_factory=list)


class PMProjectBudgetBundleOut(BaseModel):
    budget: PMPresupuestoOut | None = None
    summary: PMProjectCostsOut
    vs_actual: PMBudgetVsActualOut


class PMTimeEntryCreate(BaseModel):
    tarea_id: str | None = None
    usuario_id: str | None = None
    usuario_email_snapshot: EmailStr | None = None
    usuario_nombre_snapshot: str | None = Field(default=None, max_length=160)
    fecha: date
    horas: Decimal = Field(gt=0, le=24)
    descripcion: str | None = None
    moneda: str = Field(default="MXN", min_length=3, max_length=8)


class PMTimeEntryUpdate(BaseModel):
    tarea_id: str | None = None
    usuario_id: str | None = None
    usuario_email_snapshot: EmailStr | None = None
    usuario_nombre_snapshot: str | None = Field(default=None, max_length=160)
    fecha: date | None = None
    horas: Decimal | None = Field(default=None, gt=0, le=24)
    descripcion: str | None = None
    moneda: str | None = Field(default=None, min_length=3, max_length=8)
    activo: bool | None = None


class PMTimeEntryOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    tarea_id: str | None = None
    tarea_titulo: str | None = None
    usuario_id: str | None = None
    usuario_email_snapshot: str | None = None
    usuario_nombre_snapshot: str | None = None
    fecha: date
    horas: Decimal = Decimal("0")
    descripcion: str | None = None
    costo_hora_aplicado_snapshot: Decimal = Decimal("0")
    costo_total_snapshot: Decimal = Decimal("0")
    fuente_tarifa: str
    moneda: str = "MXN"
    activo: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMTimeEntryListResponse(BaseModel):
    items: list[PMTimeEntryOut]
    total: int
    limit: int
    offset: int


class PMTarifaHoraUsuarioCreate(BaseModel):
    usuario_id: str | None = None
    usuario_email: EmailStr
    usuario_nombre_snapshot: str | None = Field(default=None, max_length=160)
    tarifa_hora: Decimal = Field(ge=0)
    moneda: str = Field(default="MXN", min_length=3, max_length=8)
    effective_from: date | None = None
    effective_to: date | None = None
    notas: str | None = None


class PMTarifaHoraUsuarioUpdate(BaseModel):
    usuario_id: str | None = None
    usuario_email: EmailStr | None = None
    usuario_nombre_snapshot: str | None = Field(default=None, max_length=160)
    tarifa_hora: Decimal | None = Field(default=None, ge=0)
    moneda: str | None = Field(default=None, min_length=3, max_length=8)
    effective_from: date | None = None
    effective_to: date | None = None
    activa: bool | None = None
    notas: str | None = None


class PMTarifaHoraUsuarioOut(BaseModel):
    id: str
    empresa_id: str
    usuario_id: str | None = None
    usuario_email: str
    usuario_nombre_snapshot: str | None = None
    tarifa_hora: Decimal = Decimal("0")
    moneda: str = "MXN"
    effective_from: date | None = None
    effective_to: date | None = None
    activa: bool
    notas: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMTarifaHoraUsuarioListResponse(BaseModel):
    items: list[PMTarifaHoraUsuarioOut]
    total: int
    limit: int
    offset: int


class PMTarifaHoraRolCreate(BaseModel):
    rol: str = Field(min_length=4, max_length=40)
    tarifa_hora: Decimal = Field(ge=0)
    moneda: str = Field(default="MXN", min_length=3, max_length=8)
    effective_from: date | None = None
    effective_to: date | None = None
    notas: str | None = None


class PMTarifaHoraRolUpdate(BaseModel):
    rol: str | None = Field(default=None, min_length=4, max_length=40)
    tarifa_hora: Decimal | None = Field(default=None, ge=0)
    moneda: str | None = Field(default=None, min_length=3, max_length=8)
    effective_from: date | None = None
    effective_to: date | None = None
    activa: bool | None = None
    notas: str | None = None


class PMTarifaHoraRolOut(BaseModel):
    id: str
    empresa_id: str
    rol: str
    tarifa_hora: Decimal = Decimal("0")
    moneda: str = "MXN"
    effective_from: date | None = None
    effective_to: date | None = None
    activa: bool
    notas: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMTarifaHoraRolListResponse(BaseModel):
    items: list[PMTarifaHoraRolOut]
    total: int
    limit: int
    offset: int
