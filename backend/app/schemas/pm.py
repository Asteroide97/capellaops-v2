from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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


class PMProjectCrmLinkRequest(BaseModel):
    cliente_id: str = Field(min_length=1, max_length=36)
    contacto_id: str | None = Field(default=None, max_length=36)


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
    crm_cliente_id: str | None = None
    crm_cliente_nombre: str | None = None
    crm_contacto_id: str | None = None
    crm_contacto_nombre: str | None = None
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


class PMSimpleProjectProgressCreate(BaseModel):
    comentario: str = Field(min_length=1)
    avance_porcentaje: Decimal | None = Field(default=None, ge=0, le=100)
    estado_operativo: str | None = Field(default=None, min_length=4, max_length=30)
    proximo_paso: str | None = Field(default=None, max_length=255)
    bloqueo_actual: str | None = None
    fecha_compromiso: date | None = None
    evidencia_url: str | None = Field(default=None, max_length=500)


class PMSimpleProjectProgressOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    usuario_id: str | None = None
    usuario_nombre: str | None = None
    comentario: str
    avance_porcentaje: Decimal = Decimal("0")
    estado_operativo: str
    proximo_paso: str | None = None
    bloqueo_actual: str | None = None
    fecha_compromiso: date | None = None
    evidencia_url: str | None = None
    created_at: datetime


class PMSimpleProjectProgressHistoryResponse(BaseModel):
    items: list[PMSimpleProjectProgressOut] = Field(default_factory=list)


class PMSimpleWorkProgressRowOut(BaseModel):
    proyecto_id: str
    codigo: str | None = None
    nombre: str
    cliente_nombre: str | None = None
    responsable_id: str | None = None
    responsable_nombre: str | None = None
    estado_operativo: str
    avance_porcentaje: Decimal = Decimal("0")
    fecha_compromiso: date | None = None
    proximo_paso: str | None = None
    bloqueo_actual: str | None = None
    ultima_actualizacion_avance_at: datetime | None = None
    presupuesto_estimado: Decimal | None = None
    costo_real: Decimal | None = None
    saldo_pendiente: Decimal | None = None
    semaforo: str = "sin_fecha"


class PMSimpleWorkProgressListResponse(BaseModel):
    items: list[PMSimpleWorkProgressRowOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class PMSimpleSummaryOut(BaseModel):
    trabajos_totales: int = 0
    en_proceso: int = 0
    atrasados: int = 0
    pendientes_cliente: int = 0
    listos_entrega: int = 0
    entregados: int = 0
    cobrados: int = 0
    avance_promedio: Decimal = Decimal("0")
    monto_total_trabajos: Decimal = Decimal("0")
    monto_pendiente_cobro: Decimal = Decimal("0")


class PMSimpleProjectProgressMutationOut(BaseModel):
    avance: PMSimpleProjectProgressOut
    proyecto: PMSimpleWorkProgressRowOut
    summary: PMSimpleSummaryOut


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


class PMWorkCalendarOut(BaseModel):
    id: str | None = None
    empresa_id: str | None = None
    proyecto_id: str | None = None
    nombre: str = "Calendario estándar"
    lunes: bool = True
    martes: bool = True
    miercoles: bool = True
    jueves: bool = True
    viernes: bool = True
    sabado: bool = False
    domingo: bool = False
    activo: bool = True
    origen: str = "default"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PMWorkCalendarUpdate(BaseModel):
    nombre: str = Field(default="Calendario estándar", min_length=1, max_length=120)
    lunes: bool = True
    martes: bool = True
    miercoles: bool = True
    jueves: bool = True
    viernes: bool = True
    sabado: bool = False
    domingo: bool = False


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
    usa_calendario_laboral: bool = False
    calendario_nombre: str | None = None


class PMScheduleApplySuggestionRequest(BaseModel):
    apply_dependents: bool = False


class PMTaskDateUpdateRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    apply_dependents: bool = False


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


class PMLineaBaseCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    es_principal: bool = True


class PMLineaBaseTareaOut(BaseModel):
    id: str
    empresa_id: str
    linea_base_id: str
    proyecto_id: str
    tarea_id: str | None = None
    tarea_titulo_snapshot: str
    tarea_codigo_snapshot: str | None = None
    estatus_base: str
    prioridad_base: str | None = None
    fecha_inicio_base: date | None = None
    fecha_fin_base: date | None = None
    duracion_dias_base: int | None = None
    porcentaje_avance_base: Decimal = Decimal("0")
    estimacion_horas_base: Decimal = Decimal("0")
    es_critica_base: bool = False
    orden_base: int = 0
    activo_base: bool = True
    created_at: datetime


class PMLineaBaseOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    nombre: str
    descripcion: str | None = None
    version: int = 1
    estatus: str
    es_principal: bool = False
    fecha_inicio_base: date | None = None
    fecha_fin_base: date | None = None
    duracion_dias_base: int | None = None
    presupuesto_base: Decimal = Decimal("0")
    costo_estimado_base: Decimal = Decimal("0")
    precio_venta_base: Decimal = Decimal("0")
    margen_base: Decimal = Decimal("0")
    porcentaje_avance_base: Decimal = Decimal("0")
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMLineaBaseDetailOut(PMLineaBaseOut):
    ruta_critica_json: dict | list | str | None = None
    snapshot_json: dict | list | str | None = None
    tasks: list[PMLineaBaseTareaOut] = Field(default_factory=list)


class PMBaselineTaskComparisonOut(BaseModel):
    task_id: str | None = None
    tarea_titulo: str
    fecha_inicio_base: date | None = None
    fecha_inicio_actual: date | None = None
    fecha_fin_base: date | None = None
    fecha_fin_actual: date | None = None
    duracion_dias_base: int | None = None
    duracion_dias_actual: int | None = None
    desviacion_dias_fin: int = 0
    estatus_base: str | None = None
    estatus_actual: str | None = None
    porcentaje_avance_base: Decimal = Decimal("0")
    porcentaje_avance_actual: Decimal = Decimal("0")
    es_critica_base: bool = False
    es_critica_actual: bool = False
    activo_base: bool = True
    activo_actual: bool = True
    added_after_baseline: bool = False
    removed_after_baseline: bool = False
    changed_fields: list[str] = Field(default_factory=list)
    cambio_detectado: str = ""


class PMBaselineDeviationOut(BaseModel):
    baseline_id: str
    baseline_name: str
    fecha_inicio_base: date | None = None
    fecha_inicio_actual: date | None = None
    fecha_fin_base: date | None = None
    fecha_fin_actual: date | None = None
    duracion_dias_base: int | None = None
    duracion_dias_actual: int | None = None
    desviacion_fecha_fin_dias: int = 0
    desviacion_duracion_dias: int = 0
    presupuesto_base: Decimal = Decimal("0")
    presupuesto_actual: Decimal = Decimal("0")
    costo_real_actual: Decimal = Decimal("0")
    desviacion_costo: Decimal = Decimal("0")
    desviacion_presupuesto: Decimal = Decimal("0")
    porcentaje_desviacion_costo: Decimal = Decimal("0")
    total_tareas_base: int = 0
    total_tareas_actual: int = 0
    tareas_agregadas_count: int = 0
    tareas_eliminadas_count: int = 0
    tareas_desviadas_count: int = 0
    tareas_criticas_desviadas_count: int = 0
    cambios_pendientes_count: int = 0


class PMBaselineVsActualOut(BaseModel):
    baseline: PMLineaBaseOut
    deviation: PMBaselineDeviationOut
    task_changes: list[PMBaselineTaskComparisonOut] = Field(default_factory=list)


class PMCambioProyectoCreate(BaseModel):
    linea_base_id: str | None = None
    tipo_cambio: str = Field(default="otro", min_length=3, max_length=40)
    titulo: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    motivo: str | None = Field(default=None, max_length=4000)
    requiere_aprobacion: bool = False
    entidad_tipo: str | None = Field(default=None, max_length=40)
    entidad_id: str | None = Field(default=None, max_length=36)
    antes_json: dict | list | str | None = None
    despues_json: dict | list | str | None = None
    impacto_dias: int = 0
    impacto_costo: Decimal = Field(default=Decimal("0"))
    impacto_venta: Decimal = Field(default=Decimal("0"))


class PMCambioProyectoUpdate(BaseModel):
    linea_base_id: str | None = None
    tipo_cambio: str | None = Field(default=None, min_length=3, max_length=40)
    titulo: str | None = Field(default=None, min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    motivo: str | None = Field(default=None, max_length=4000)
    requiere_aprobacion: bool | None = None
    entidad_tipo: str | None = Field(default=None, max_length=40)
    entidad_id: str | None = Field(default=None, max_length=36)
    antes_json: dict | list | str | None = None
    despues_json: dict | list | str | None = None
    impacto_dias: int | None = None
    impacto_costo: Decimal | None = None
    impacto_venta: Decimal | None = None


class PMCambioProyectoSubmitRequest(BaseModel):
    comentario: str | None = Field(default=None, max_length=2000)


class PMCambioProyectoApplyRequest(BaseModel):
    apply_dependents: bool = False
    comentario: str | None = Field(default=None, max_length=2000)


class PMCambioProyectoOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    linea_base_id: str | None = None
    tipo_cambio: str
    titulo: str
    descripcion: str | None = None
    motivo: str | None = None
    estatus: str
    requiere_aprobacion: bool = False
    aprobacion_id: str | None = None
    aprobacion_estatus: str | None = None
    aprobacion_titulo: str | None = None
    entidad_tipo: str | None = None
    entidad_id: str | None = None
    antes_json: dict | list | str | None = None
    despues_json: dict | list | str | None = None
    impacto_dias: int = 0
    impacto_costo: Decimal = Decimal("0")
    impacto_venta: Decimal = Decimal("0")
    solicitado_por: str | None = None
    solicitado_at: datetime | None = None
    aprobado_por: str | None = None
    aprobado_at: datetime | None = None
    aplicado_por: str | None = None
    aplicado_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PMEstimacionCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    periodo_inicio: date | None = None
    periodo_fin: date | None = None
    retencion_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    anticipo_aplicado: Decimal = Field(default=Decimal("0"), ge=0)
    requiere_aprobacion: bool = True
    moneda: str = Field(default="MXN", min_length=3, max_length=8)
    linea_base_id: str | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.periodo_inicio and self.periodo_fin and self.periodo_fin < self.periodo_inicio:
            raise ValueError("El periodo final no puede ser anterior al periodo inicial.")
        return self


class PMEstimacionUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    periodo_inicio: date | None = None
    periodo_fin: date | None = None
    retencion_pct: Decimal | None = Field(default=None, ge=0, le=100)
    anticipo_aplicado: Decimal | None = Field(default=None, ge=0)
    requiere_aprobacion: bool | None = None
    moneda: str | None = Field(default=None, min_length=3, max_length=8)
    linea_base_id: str | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.periodo_inicio and self.periodo_fin and self.periodo_fin < self.periodo_inicio:
            raise ValueError("El periodo final no puede ser anterior al periodo inicial.")
        return self


class PMEstimacionDetalleCreate(BaseModel):
    presupuesto_partida_id: str | None = None
    tarea_id: str | None = None
    avance_actual_pct: Decimal = Field(ge=0, le=100)
    notas: str | None = Field(default=None, max_length=4000)


class PMEstimacionDetalleUpdate(BaseModel):
    tarea_id: str | None = None
    avance_actual_pct: Decimal | None = Field(default=None, ge=0, le=100)
    notas: str | None = Field(default=None, max_length=4000)
    activo: bool | None = None


class PMEstimacionSubmitRequest(BaseModel):
    comentario: str | None = Field(default=None, max_length=2000)


class PMEstimacionResolveRequest(BaseModel):
    comentario: str | None = Field(default=None, max_length=2000)


class PMEstimacionCobroRequest(BaseModel):
    monto_cobrado: Decimal | None = Field(default=None, ge=0)
    comentario: str | None = Field(default=None, max_length=2000)


class PMEstimacionDetalleOut(BaseModel):
    id: str
    empresa_id: str
    estimacion_id: str
    proyecto_id: str
    presupuesto_partida_id: str | None = None
    tarea_id: str | None = None
    codigo_snapshot: str | None = None
    concepto_snapshot: str
    unidad_snapshot: str | None = None
    cantidad_presupuestada: Decimal = Decimal("0")
    precio_unitario_snapshot: Decimal = Decimal("0")
    importe_presupuestado: Decimal = Decimal("0")
    avance_anterior_pct: Decimal = Decimal("0")
    avance_actual_pct: Decimal = Decimal("0")
    avance_periodo_pct: Decimal = Decimal("0")
    importe_anterior: Decimal = Decimal("0")
    importe_periodo: Decimal = Decimal("0")
    importe_acumulado: Decimal = Decimal("0")
    saldo_por_estimar: Decimal = Decimal("0")
    notas: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class PMEstimacionOut(BaseModel):
    id: str
    empresa_id: str
    proyecto_id: str
    presupuesto_id: str | None = None
    linea_base_id: str | None = None
    folio: str | None = None
    nombre: str
    descripcion: str | None = None
    periodo_inicio: date | None = None
    periodo_fin: date | None = None
    estatus: str
    moneda: str = "MXN"
    monto_bruto: Decimal = Decimal("0")
    anticipo_aplicado: Decimal = Decimal("0")
    retencion_pct: Decimal = Decimal("0")
    retencion_monto: Decimal = Decimal("0")
    monto_neto: Decimal = Decimal("0")
    monto_aprobado: Decimal = Decimal("0")
    monto_cobrado: Decimal = Decimal("0")
    saldo_pendiente: Decimal = Decimal("0")
    requiere_aprobacion: bool = True
    aprobacion_id: str | None = None
    aprobacion_estatus: str | None = None
    aprobacion_titulo: str | None = None
    partidas_activas_count: int = 0
    enviada_at: datetime | None = None
    aprobada_at: datetime | None = None
    rechazada_at: datetime | None = None
    cobrada_at: datetime | None = None
    cancelada_at: datetime | None = None
    comentario_resolucion: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    activo: bool


class PMEstimacionDetailOut(PMEstimacionOut):
    details: list[PMEstimacionDetalleOut] = Field(default_factory=list)


class PMEstimationCandidateOut(BaseModel):
    partida_id: str
    codigo: str | None = None
    nombre: str
    unidad: str | None = None
    cantidad: Decimal = Decimal("0")
    precio_unitario: Decimal = Decimal("0")
    importe_presupuestado: Decimal = Decimal("0")
    avance_estimado_anterior: Decimal = Decimal("0")
    saldo_por_estimar: Decimal = Decimal("0")


class PMProyectoEstimacionesResumenOut(BaseModel):
    project_id: str
    presupuesto_id: str | None = None
    total_estimado: Decimal = Decimal("0")
    total_aprobado: Decimal = Decimal("0")
    total_cobrado: Decimal = Decimal("0")
    pendiente_por_cobrar: Decimal = Decimal("0")
    presupuesto_total: Decimal = Decimal("0")
    porcentaje_presupuesto_estimado: Decimal = Decimal("0")


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


class PMExecutiveReportKpisOut(BaseModel):
    proyectos_activos: int = 0
    proyectos_atrasados: int = 0
    proyectos_en_riesgo: int = 0
    alertas_criticas_abiertas: int = 0
    cambios_pendientes_aprobacion: int = 0
    estimaciones_pendientes_aprobacion: int = 0
    presupuesto_total_aprobado: Decimal = Decimal("0")
    costo_real_total: Decimal = Decimal("0")
    total_estimado: Decimal = Decimal("0")
    total_aprobado: Decimal = Decimal("0")
    total_cobrado: Decimal = Decimal("0")
    pendiente_por_cobrar: Decimal = Decimal("0")
    margen_estimado_global: Decimal = Decimal("0")


class PMExecutiveProjectRowOut(BaseModel):
    project_id: str
    nombre: str
    codigo: str | None = None
    estatus: str
    prioridad: str | None = None
    responsable_id: str | None = None
    responsable_nombre: str | None = None
    porcentaje_avance: Decimal = Decimal("0")
    fecha_inicio: date | None = None
    fecha_fin_planificada: date | None = None
    fecha_fin_actual: date | None = None
    desviacion_dias: int = 0
    presupuesto: Decimal = Decimal("0")
    costo_real: Decimal = Decimal("0")
    variacion_costo: Decimal = Decimal("0")
    total_estimado: Decimal = Decimal("0")
    total_aprobado: Decimal = Decimal("0")
    total_cobrado: Decimal = Decimal("0")
    pendiente_cobrar: Decimal = Decimal("0")
    alertas_abiertas: int = 0
    alertas_criticas: int = 0
    cambios_pendientes: int = 0
    estimaciones_pendientes: int = 0
    health: str = "verde"
    health_label: str = "En orden"
    health_reasons: list[str] = Field(default_factory=list)


class PMExecutiveRiskOut(BaseModel):
    project_id: str
    proyecto_nombre: str
    tipo_riesgo: str
    severidad: str
    descripcion: str
    accion_sugerida: str | None = None


class PMExecutiveFinancialSummaryOut(BaseModel):
    presupuesto_total: Decimal = Decimal("0")
    costo_real_total: Decimal = Decimal("0")
    variacion_costo: Decimal = Decimal("0")
    total_estimado: Decimal = Decimal("0")
    total_aprobado: Decimal = Decimal("0")
    total_cobrado: Decimal = Decimal("0")
    pendiente_por_cobrar: Decimal = Decimal("0")
    porcentaje_cobrado_sobre_estimado: Decimal = Decimal("0")
    margen_estimado_global: Decimal = Decimal("0")


class PMExecutiveAlertsSummaryOut(BaseModel):
    abiertas: int = 0
    criticas: int = 0
    warning: int = 0
    info: int = 0


class PMExecutiveFiltersAppliedOut(BaseModel):
    estatus: str | None = None
    prioridad: str | None = None
    responsable_id: str | None = None
    fecha_desde: date | None = None
    fecha_hasta: date | None = None
    salud: str | None = None
    con_alertas: bool | None = None
    con_pendiente_cobro: bool | None = None
    limit: int = 50
    offset: int = 0


class PMExecutiveReportOut(BaseModel):
    kpis: PMExecutiveReportKpisOut
    projects: list[PMExecutiveProjectRowOut] = Field(default_factory=list)
    risks: list[PMExecutiveRiskOut] = Field(default_factory=list)
    financial_summary: PMExecutiveFinancialSummaryOut
    alerts_summary: PMExecutiveAlertsSummaryOut
    filters_applied: PMExecutiveFiltersAppliedOut


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


class PMRescheduleAffectedTaskOut(BaseModel):
    task_id: str
    titulo: str
    estatus: str
    fecha_inicio_actual: date | None = None
    fecha_fin_actual: date | None = None
    fecha_inicio_sugerida: date | None = None
    fecha_fin_sugerida: date | None = None


class PMRescheduleImpactOut(BaseModel):
    task_id: str
    affected_task_ids: list[str] = Field(default_factory=list)
    affected_tasks: list[PMRescheduleAffectedTaskOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_affected: int = 0


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
    work_calendar: PMWorkCalendarOut | None = None


class PMApplyScheduleOut(BaseModel):
    task: PMPlanningTaskOut | None = None
    planning: PMProjectPlanningOut
    affected_tasks: list[PMRescheduleAffectedTaskOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    alerts_summary: PMPlanningSummaryOut
    message: str


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
    almacen_principal_nombre: str | None = None
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
    partida_id: str | None = None
    partida_nombre: str | None = None
    material_id: str
    material_nombre_snapshot: str
    material_sku_snapshot: str
    movimiento_id: str | None = None
    almacen_id: str | None = None
    almacen_nombre: str | None = None
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


class PMProjectMaterialConsumeRequest(BaseModel):
    material_id: str
    almacen_id: str
    cantidad: Decimal = Field(gt=0)
    tarea_id: str | None = None
    partida_id: str | None = None
    notas: str | None = None


class PMProjectMaterialReturnRequest(BaseModel):
    material_id: str
    almacen_id: str
    cantidad: Decimal = Field(gt=0)
    tarea_id: str | None = None
    partida_id: str | None = None
    notas: str | None = None


class PMCreateProjectRequisitionItem(BaseModel):
    plan_id: str
    cantidad_solicitada: Decimal = Field(gt=0)
    notas: str | None = None


class PMCreateProjectRequisitionRequest(BaseModel):
    tarea_id: str | None = None
    partida_id: str | None = None
    prioridad: str = Field(default="normal", min_length=4, max_length=20)
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
