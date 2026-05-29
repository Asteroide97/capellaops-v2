from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


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


class PMTareaOut(PMTareaListItem):
    subtasks: list[PMSubtareaOut] = Field(default_factory=list)
    checklist_items: list[PMChecklistItemOut] = Field(default_factory=list)
    comments: list[PMCommentOut] = Field(default_factory=list)


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


class PMDashboardOut(BaseModel):
    kpis: PMDashboardKpis
    proyectos_por_estatus: list[PMStatusCount] = Field(default_factory=list)
    tareas_por_estatus: list[PMStatusCount] = Field(default_factory=list)
    proximos_vencimientos: list[PMDashboardDueItem] = Field(default_factory=list)
    proyectos_proximos: list[PMDashboardDueItem] = Field(default_factory=list)
    tareas_vencidas_items: list[PMDashboardDueItem] = Field(default_factory=list)


class PMProjectMembersListResponse(BaseModel):
    items: list[PMProyectoMiembroOut]
