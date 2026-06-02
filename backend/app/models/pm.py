from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EmpresaPMConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "empresa_pm_config"
    __table_args__ = (Index("uq_empresa_pm_config_empresa_id", "empresa_id", unique=True),)

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    pm_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    pm_tareas_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    pm_materiales_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    pm_tiempo_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    pm_templates_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    pm_comercial_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    pm_portal_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class PMProyecto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_proyectos"
    __table_args__ = (
        CheckConstraint("porcentaje_avance >= 0 AND porcentaje_avance <= 100", name="ck_pm_proyectos_porcentaje"),
        CheckConstraint(
            "presupuesto_estimado IS NULL OR presupuesto_estimado >= 0",
            name="ck_pm_proyectos_presupuesto_non_negative",
        ),
        Index("ix_pm_proyectos_empresa_id", "empresa_id"),
        Index("ix_pm_proyectos_estatus", "estatus"),
        Index("ix_pm_proyectos_activo", "activo"),
        Index(
            "uq_pm_proyectos_empresa_codigo",
            "empresa_id",
            "codigo",
            unique=True,
            sqlite_where=text("codigo IS NOT NULL"),
            mssql_where=text("codigo IS NOT NULL"),
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo_proyecto: Mapped[str | None] = mapped_column(String(80), nullable=True)
    estatus: Mapped[str] = mapped_column(String(20), nullable=False, default="borrador", server_default="borrador")
    prioridad: Mapped[str] = mapped_column(String(20), nullable=False, default="media", server_default="media")
    fecha_inicio: Mapped[date | None] = mapped_column(Date(), nullable=True)
    fecha_fin_planificada: Mapped[date | None] = mapped_column(Date(), nullable=True)
    fecha_fin_real: Mapped[date | None] = mapped_column(Date(), nullable=True)
    porcentaje_avance: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    responsable_user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    responsable_nombre_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cliente_nombre_snapshot: Mapped[str | None] = mapped_column(String(180), nullable=True)
    presupuesto_estimado: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True, default=0, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    members = relationship("PMProyectoMiembro", back_populates="proyecto", cascade="all, delete-orphan")
    tasks = relationship("PMTarea", back_populates="proyecto", cascade="all, delete-orphan")
    comments = relationship("PMComentario", back_populates="proyecto", cascade="all, delete-orphan")
    documents = relationship("PMDocumento", back_populates="proyecto", cascade="all, delete-orphan")
    approvals = relationship("PMAprobacion", back_populates="proyecto", cascade="all, delete-orphan")
    external_invites = relationship("PMInvitadoExterno", back_populates="proyecto", cascade="all, delete-orphan")
    portal_access_logs = relationship("PMPortalAccessLog", back_populates="proyecto", cascade="all, delete-orphan")
    alerts = relationship("PMAlerta", back_populates="proyecto", cascade="all, delete-orphan")
    work_calendars = relationship("PMCalendarioLaboral", back_populates="proyecto", cascade="all, delete-orphan")
    material_plans = relationship("PMProyectoMaterialPlan", back_populates="proyecto", cascade="all, delete-orphan")
    material_consumptions = relationship("PMProyectoMaterialConsumo", back_populates="proyecto", cascade="all, delete-orphan")
    time_entries = relationship("PMTimeEntry", back_populates="proyecto", cascade="all, delete-orphan")
    budgets = relationship("PMPresupuesto", back_populates="proyecto", cascade="all, delete-orphan")
    material_cost_summary = relationship(
        "PMProyectoCostoResumen",
        back_populates="proyecto",
        cascade="all, delete-orphan",
        uselist=False,
    )


class PMProyectoMiembro(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_proyecto_miembros"
    __table_args__ = (
        CheckConstraint("usuario_id IS NOT NULL OR email IS NOT NULL", name="ck_pm_miembros_usuario_or_email"),
        Index("ix_pm_proyecto_miembros_empresa_id", "empresa_id"),
        Index("ix_pm_proyecto_miembros_proyecto_id", "proyecto_id"),
        Index("ix_pm_proyecto_miembros_activo", "activo"),
        Index(
            "uq_pm_proyecto_miembro_usuario_activo",
            "proyecto_id",
            "usuario_id",
            unique=True,
            sqlite_where=text("activo = 1 AND usuario_id IS NOT NULL"),
            mssql_where=text("activo = 1 AND usuario_id IS NOT NULL"),
        ),
        Index(
            "uq_pm_proyecto_miembro_email_activo",
            "proyecto_id",
            "email",
            unique=True,
            sqlite_where=text("activo = 1 AND email IS NOT NULL"),
            mssql_where=text("activo = 1 AND email IS NOT NULL"),
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    usuario_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nombre_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    rol_en_proyecto: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="colaborador",
        server_default="colaborador",
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    proyecto = relationship("PMProyecto", back_populates="members")


class PMTarea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_tareas"
    __table_args__ = (
        CheckConstraint("porcentaje_avance >= 0 AND porcentaje_avance <= 100", name="ck_pm_tareas_porcentaje"),
        CheckConstraint(
            "estimacion_horas IS NULL OR estimacion_horas >= 0",
            name="ck_pm_tareas_estimacion_non_negative",
        ),
        Index("ix_pm_tareas_empresa_id", "empresa_id"),
        Index("ix_pm_tareas_proyecto_id", "proyecto_id"),
        Index("ix_pm_tareas_estatus", "estatus"),
        Index("ix_pm_tareas_activo", "activo"),
        Index("ix_pm_tareas_fecha_vencimiento", "fecha_vencimiento"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    estatus: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente", server_default="pendiente")
    prioridad: Mapped[str] = mapped_column(String(20), nullable=False, default="media", server_default="media")
    asignado_user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    asignado_nombre_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    fecha_inicio: Mapped[date | None] = mapped_column(Date(), nullable=True)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date(), nullable=True)
    fecha_completada: Mapped[date | None] = mapped_column(Date(), nullable=True)
    estimacion_horas: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, default=0, server_default="0")
    porcentaje_avance: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    bloqueada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    requiere_materiales: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    requiere_compra: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    requiere_venta_pos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    requiere_factura: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    proyecto = relationship("PMProyecto", back_populates="tasks")
    prerequisites = relationship(
        "PMTareaDependencia",
        back_populates="tarea",
        cascade="all, delete-orphan",
        foreign_keys="PMTareaDependencia.tarea_id",
    )
    unlocked_tasks = relationship(
        "PMTareaDependencia",
        back_populates="prerequisite_task",
        cascade="all, delete-orphan",
        foreign_keys="PMTareaDependencia.depende_de_tarea_id",
    )
    subtasks = relationship("PMSubtarea", back_populates="tarea", cascade="all, delete-orphan")
    checklist_items = relationship("PMChecklistItem", back_populates="tarea", cascade="all, delete-orphan")
    comments = relationship("PMComentario", back_populates="tarea", cascade="all, delete-orphan")
    alerts = relationship("PMAlerta", back_populates="tarea")
    material_plans = relationship("PMProyectoMaterialPlan", back_populates="tarea")
    material_consumptions = relationship("PMProyectoMaterialConsumo", back_populates="tarea")
    time_entries = relationship("PMTimeEntry", back_populates="tarea")


class PMTareaDependencia(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_tarea_dependencias"
    __table_args__ = (
        Index("ix_pm_tarea_dependencias_empresa_id", "empresa_id"),
        Index("ix_pm_tarea_dependencias_proyecto_id", "proyecto_id"),
        Index("ix_pm_tarea_dependencias_tarea_id", "tarea_id"),
        Index("ix_pm_tarea_dependencias_depende_de_tarea_id", "depende_de_tarea_id"),
        Index("ix_pm_tarea_dependencias_activo", "activo"),
        Index(
            "uq_pm_tarea_dependencia_activa",
            "empresa_id",
            "proyecto_id",
            "tarea_id",
            "depende_de_tarea_id",
            unique=True,
            sqlite_where=text("activo = 1"),
            mssql_where=text("activo = 1"),
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    tarea_id: Mapped[str] = mapped_column(ForeignKey("pm_tareas.id"), nullable=False, index=True)
    depende_de_tarea_id: Mapped[str] = mapped_column(ForeignKey("pm_tareas.id"), nullable=False, index=True)
    tipo_dependencia: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="finish_to_start",
        server_default="finish_to_start",
    )
    lag_dias: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    bloqueante: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    tarea = relationship("PMTarea", back_populates="prerequisites", foreign_keys=[tarea_id])
    prerequisite_task = relationship("PMTarea", back_populates="unlocked_tasks", foreign_keys=[depende_de_tarea_id])
    proyecto = relationship("PMProyecto")


class PMSubtarea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_subtareas"
    __table_args__ = (
        Index("ix_pm_subtareas_empresa_id", "empresa_id"),
        Index("ix_pm_subtareas_tarea_id", "tarea_id"),
        Index("ix_pm_subtareas_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    tarea_id: Mapped[str] = mapped_column(ForeignKey("pm_tareas.id"), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(180), nullable=False)
    estatus: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente", server_default="pendiente")
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    asignado_user_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    tarea = relationship("PMTarea", back_populates="subtasks")


class PMChecklistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_checklist_items"
    __table_args__ = (
        Index("ix_pm_checklist_empresa_id", "empresa_id"),
        Index("ix_pm_checklist_tarea_id", "tarea_id"),
        Index("ix_pm_checklist_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    tarea_id: Mapped[str] = mapped_column(ForeignKey("pm_tareas.id"), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(180), nullable=False)
    completado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    tarea = relationship("PMTarea", back_populates="checklist_items")


class PMComentario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_comentarios"
    __table_args__ = (
        CheckConstraint("proyecto_id IS NOT NULL OR tarea_id IS NOT NULL", name="ck_pm_comentarios_target"),
        Index("ix_pm_comentarios_empresa_id", "empresa_id"),
        Index("ix_pm_comentarios_proyecto_id", "proyecto_id"),
        Index("ix_pm_comentarios_tarea_id", "tarea_id"),
        Index("ix_pm_comentarios_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str | None] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=True, index=True)
    tarea_id: Mapped[str | None] = mapped_column(ForeignKey("pm_tareas.id"), nullable=True, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    created_by_nombre_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    externo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    autor_nombre_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    invitado_externo_id: Mapped[str | None] = mapped_column(
        ForeignKey("pm_invitados_externos.id"),
        nullable=True,
        index=True,
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    proyecto = relationship("PMProyecto", back_populates="comments")
    tarea = relationship("PMTarea", back_populates="comments")
    invitado_externo = relationship("PMInvitadoExterno", back_populates="comments")


class PMProyectoMaterialPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_proyecto_material_plan"
    __table_args__ = (
        CheckConstraint("cantidad_planificada > 0", name="ck_pm_material_plan_qty_positive"),
        CheckConstraint(
            "costo_unitario_estimado IS NULL OR costo_unitario_estimado >= 0",
            name="ck_pm_material_plan_unit_cost_non_negative",
        ),
        CheckConstraint(
            "costo_total_estimado IS NULL OR costo_total_estimado >= 0",
            name="ck_pm_material_plan_total_cost_non_negative",
        ),
        Index("ix_pm_material_plan_empresa_id", "empresa_id"),
        Index("ix_pm_material_plan_proyecto_id", "proyecto_id"),
        Index("ix_pm_material_plan_tarea_id", "tarea_id"),
        Index("ix_pm_material_plan_material_id", "material_id"),
        Index("ix_pm_material_plan_estatus", "estatus"),
        Index("ix_pm_material_plan_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    tarea_id: Mapped[str | None] = mapped_column(ForeignKey("pm_tareas.id"), nullable=True, index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materiales.id"), nullable=False, index=True)
    material_nombre_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    material_sku_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    cantidad_planificada: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    unidad: Mapped[str] = mapped_column(String(40), nullable=False)
    costo_unitario_estimado: Mapped[float | None] = mapped_column(
        Numeric(18, 4), nullable=True, default=0, server_default="0"
    )
    costo_total_estimado: Mapped[float | None] = mapped_column(
        Numeric(18, 2), nullable=True, default=0, server_default="0"
    )
    estatus: Mapped[str] = mapped_column(String(20), nullable=False, default="planeado", server_default="planeado")
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    proyecto = relationship("PMProyecto", back_populates="material_plans")
    tarea = relationship("PMTarea", back_populates="material_plans")


class PMProyectoMaterialConsumo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_proyecto_material_consumo"
    __table_args__ = (
        CheckConstraint("cantidad_consumida > 0", name="ck_pm_material_consumo_qty_positive"),
        CheckConstraint(
            "costo_unitario_snapshot IS NULL OR costo_unitario_snapshot >= 0",
            name="ck_pm_material_consumo_unit_cost_non_negative",
        ),
        CheckConstraint(
            "costo_total_snapshot IS NULL OR costo_total_snapshot >= 0",
            name="ck_pm_material_consumo_total_cost_non_negative",
        ),
        Index("ix_pm_material_consumo_empresa_id", "empresa_id"),
        Index("ix_pm_material_consumo_proyecto_id", "proyecto_id"),
        Index("ix_pm_material_consumo_tarea_id", "tarea_id"),
        Index("ix_pm_material_consumo_material_id", "material_id"),
        Index("ix_pm_material_consumo_movimiento_id", "movimiento_id"),
        Index("ix_pm_material_consumo_requisicion_id", "requisicion_id"),
        Index(
            "uq_pm_material_consumo_movimiento_id",
            "movimiento_id",
            unique=True,
            sqlite_where=text("movimiento_id IS NOT NULL"),
            mssql_where=text("movimiento_id IS NOT NULL"),
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    tarea_id: Mapped[str | None] = mapped_column(ForeignKey("pm_tareas.id"), nullable=True, index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materiales.id"), nullable=False, index=True)
    material_nombre_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    material_sku_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    movimiento_id: Mapped[str | None] = mapped_column(ForeignKey("movimientos_inventario.id"), nullable=True, index=True)
    requisicion_id: Mapped[str | None] = mapped_column(ForeignKey("requisiciones.id"), nullable=True, index=True)
    requisicion_detalle_id: Mapped[str | None] = mapped_column(
        ForeignKey("requisiciones_detalles.id"),
        nullable=True,
        index=True,
    )
    cantidad_consumida: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    unidad: Mapped[str] = mapped_column(String(40), nullable=False)
    costo_unitario_snapshot: Mapped[float | None] = mapped_column(
        Numeric(18, 4), nullable=True, default=0, server_default="0"
    )
    costo_total_snapshot: Mapped[float | None] = mapped_column(
        Numeric(18, 2), nullable=True, default=0, server_default="0"
    )
    origen: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="movimiento_manual",
        server_default="movimiento_manual",
    )
    documento_referencia: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    proyecto = relationship("PMProyecto", back_populates="material_consumptions")
    tarea = relationship("PMTarea", back_populates="material_consumptions")


class PMProyectoCostoResumen(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_proyecto_costo_resumen"
    __table_args__ = (
        Index("ix_pm_costo_resumen_empresa_id", "empresa_id"),
        Index("uq_pm_costo_resumen_proyecto_id", "proyecto_id", unique=True),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    costo_materiales_estimado: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    costo_materiales_real: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    variacion_materiales: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    total_materiales_planeados: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    total_materiales_consumidos: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    costo_horas_real: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    horas_totales: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    horas_sin_tarifa: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    costo_total_real: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    presupuesto_estimado: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    variacion_presupuesto: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    presupuesto_detallado_costo: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    presupuesto_detallado_venta: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    variacion_vs_presupuesto_detallado: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    presupuesto_origen: Mapped[str] = mapped_column(String(20), nullable=False, default="simple", server_default="simple")
    margen_estimado: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    proyecto = relationship("PMProyecto", back_populates="material_cost_summary")


class PMPresupuesto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_presupuestos"
    __table_args__ = (
        Index("ix_pm_presupuestos_empresa_id", "empresa_id"),
        Index("ix_pm_presupuestos_proyecto_id", "proyecto_id"),
        Index("ix_pm_presupuestos_estatus", "estatus"),
        Index("ix_pm_presupuestos_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    estatus: Mapped[str] = mapped_column(String(20), nullable=False, default="borrador", server_default="borrador")
    moneda: Mapped[str] = mapped_column(String(8), nullable=False, default="MXN", server_default="MXN")
    subtotal_costo: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    subtotal_venta: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    indirectos_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0, server_default="0")
    indirectos_monto: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    utilidad_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0, server_default="0")
    utilidad_monto: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    total_costo: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    total_venta: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    margen_estimado: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    aprobado_por: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    aprobado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    proyecto = relationship("PMProyecto", back_populates="budgets")
    items = relationship("PMPresupuestoPartida", back_populates="presupuesto", cascade="all, delete-orphan")
    indirects = relationship("PMPresupuestoIndirecto", back_populates="presupuesto", cascade="all, delete-orphan")


class PMPresupuestoPartida(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_presupuesto_partidas"
    __table_args__ = (
        Index("ix_pm_presupuesto_partidas_empresa_id", "empresa_id"),
        Index("ix_pm_presupuesto_partidas_presupuesto_id", "presupuesto_id"),
        Index("ix_pm_presupuesto_partidas_proyecto_id", "proyecto_id"),
        Index("ix_pm_presupuesto_partidas_parent_id", "parent_id"),
        Index("ix_pm_presupuesto_partidas_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    presupuesto_id: Mapped[str] = mapped_column(ForeignKey("pm_presupuestos.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("pm_presupuesto_partidas.id"), nullable=True, index=True)
    codigo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="partida", server_default="partida")
    unidad: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cantidad: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=1, server_default="1")
    costo_unitario: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    precio_unitario: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    precio_unitario_manual: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    subtotal_costo: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    subtotal_venta: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    margen_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0, server_default="0")
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    presupuesto = relationship("PMPresupuesto", back_populates="items")
    proyecto = relationship("PMProyecto")
    parent = relationship("PMPresupuestoPartida", remote_side="PMPresupuestoPartida.id")
    materials = relationship("PMPresupuestoPartidaMaterial", back_populates="partida", cascade="all, delete-orphan")
    labor_components = relationship("PMPresupuestoPartidaManoObra", back_populates="partida", cascade="all, delete-orphan")


class PMPresupuestoPartidaMaterial(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_presupuesto_partida_materiales"
    __table_args__ = (
        Index("ix_pm_presupuesto_partida_materiales_empresa_id", "empresa_id"),
        Index("ix_pm_presupuesto_partida_materiales_partida_id", "partida_id"),
        Index("ix_pm_presupuesto_partida_materiales_proyecto_id", "proyecto_id"),
        Index("ix_pm_presupuesto_partida_materiales_material_id", "material_id"),
        Index("ix_pm_presupuesto_partida_materiales_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    partida_id: Mapped[str] = mapped_column(ForeignKey("pm_presupuesto_partidas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    material_id: Mapped[str | None] = mapped_column(ForeignKey("materiales.id"), nullable=True, index=True)
    material_nombre_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    material_sku_snapshot: Mapped[str | None] = mapped_column(String(60), nullable=True)
    unidad: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cantidad_por_unidad: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    costo_unitario: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    costo_total: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    proveedor_nombre_snapshot: Mapped[str | None] = mapped_column(String(180), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    partida = relationship("PMPresupuestoPartida", back_populates="materials")
    proyecto = relationship("PMProyecto")


class PMPresupuestoPartidaManoObra(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_presupuesto_partida_mano_obra"
    __table_args__ = (
        Index("ix_pm_presupuesto_partida_mano_obra_empresa_id", "empresa_id"),
        Index("ix_pm_presupuesto_partida_mano_obra_partida_id", "partida_id"),
        Index("ix_pm_presupuesto_partida_mano_obra_proyecto_id", "proyecto_id"),
        Index("ix_pm_presupuesto_partida_mano_obra_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    partida_id: Mapped[str] = mapped_column(ForeignKey("pm_presupuesto_partidas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    rol: Mapped[str | None] = mapped_column(String(40), nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    horas_por_unidad: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    tarifa_hora: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    costo_total: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    partida = relationship("PMPresupuestoPartida", back_populates="labor_components")
    proyecto = relationship("PMProyecto")


class PMPresupuestoIndirecto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_presupuesto_indirectos"
    __table_args__ = (
        Index("ix_pm_presupuesto_indirectos_empresa_id", "empresa_id"),
        Index("ix_pm_presupuesto_indirectos_presupuesto_id", "presupuesto_id"),
        Index("ix_pm_presupuesto_indirectos_proyecto_id", "proyecto_id"),
        Index("ix_pm_presupuesto_indirectos_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    presupuesto_id: Mapped[str] = mapped_column(ForeignKey("pm_presupuestos.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="monto", server_default="monto")
    porcentaje: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    monto: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    presupuesto = relationship("PMPresupuesto", back_populates="indirects")
    proyecto = relationship("PMProyecto")


class PMTimeEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_time_entries"
    __table_args__ = (
        Index("ix_pm_time_entries_empresa_id", "empresa_id"),
        Index("ix_pm_time_entries_proyecto_id", "proyecto_id"),
        Index("ix_pm_time_entries_tarea_id", "tarea_id"),
        Index("ix_pm_time_entries_usuario_id", "usuario_id"),
        Index("ix_pm_time_entries_fecha", "fecha"),
        Index("ix_pm_time_entries_activo", "activo"),
        CheckConstraint("horas > 0", name="ck_pm_time_entries_horas_positive"),
        CheckConstraint("horas <= 24", name="ck_pm_time_entries_horas_max"),
        CheckConstraint(
            "costo_hora_aplicado_snapshot IS NULL OR costo_hora_aplicado_snapshot >= 0",
            name="ck_pm_time_entries_rate_non_negative",
        ),
        CheckConstraint(
            "costo_total_snapshot IS NULL OR costo_total_snapshot >= 0",
            name="ck_pm_time_entries_total_non_negative",
        ),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    tarea_id: Mapped[str | None] = mapped_column(ForeignKey("pm_tareas.id"), nullable=True, index=True)
    usuario_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    usuario_email_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    usuario_nombre_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    fecha: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    horas: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    costo_hora_aplicado_snapshot: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0, server_default="0")
    costo_total_snapshot: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    fuente_tarifa: Mapped[str] = mapped_column(String(20), nullable=False, default="sin_tarifa", server_default="sin_tarifa")
    moneda: Mapped[str] = mapped_column(String(8), nullable=False, default="MXN", server_default="MXN")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    proyecto = relationship("PMProyecto", back_populates="time_entries")
    tarea = relationship("PMTarea", back_populates="time_entries")


class PMTarifaHoraUsuario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_tarifas_hora_usuario"
    __table_args__ = (
        Index("ix_pm_tarifa_usuario_empresa_id", "empresa_id"),
        Index("ix_pm_tarifa_usuario_usuario_id", "usuario_id"),
        Index("ix_pm_tarifa_usuario_email", "usuario_email"),
        Index("ix_pm_tarifa_usuario_activa", "activa"),
        CheckConstraint("tarifa_hora >= 0", name="ck_pm_tarifa_usuario_non_negative"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    usuario_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    usuario_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    usuario_nombre_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tarifa_hora: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    moneda: Mapped[str] = mapped_column(String(8), nullable=False, default="MXN", server_default="MXN")
    effective_from: Mapped[date | None] = mapped_column(Date(), nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date(), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)


class PMTarifaHoraRol(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_tarifas_hora_rol"
    __table_args__ = (
        Index("ix_pm_tarifa_rol_empresa_id", "empresa_id"),
        Index("ix_pm_tarifa_rol_rol", "rol"),
        Index("ix_pm_tarifa_rol_activa", "activa"),
        CheckConstraint("tarifa_hora >= 0", name="ck_pm_tarifa_rol_non_negative"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    rol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    tarifa_hora: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    moneda: Mapped[str] = mapped_column(String(8), nullable=False, default="MXN", server_default="MXN")
    effective_from: Mapped[date | None] = mapped_column(Date(), nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date(), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)


class PMDocumento(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_documentos"
    __table_args__ = (
        Index("ix_pm_documentos_empresa_id", "empresa_id"),
        Index("ix_pm_documentos_proyecto_id", "proyecto_id"),
        Index("ix_pm_documentos_tipo", "tipo_documento"),
        Index("ix_pm_documentos_visible_externo", "visible_externo"),
        Index("ix_pm_documentos_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    tipo_documento: Mapped[str] = mapped_column(String(40), nullable=False, default="otro", server_default="otro")
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_archivo: Mapped[str] = mapped_column(String(500), nullable=False)
    nombre_archivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visible_externo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    proyecto = relationship("PMProyecto", back_populates="documents")


class PMCalendarioLaboral(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_calendarios_laborales"
    __table_args__ = (
        Index("ix_pm_calendarios_laborales_empresa_id", "empresa_id"),
        Index("ix_pm_calendarios_laborales_proyecto_id", "proyecto_id"),
        Index("ix_pm_calendarios_laborales_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str | None] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False, default="Calendario estándar", server_default="Calendario estándar")
    lunes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    martes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    miercoles: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    jueves: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    viernes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    sabado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    domingo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    proyecto = relationship("PMProyecto", back_populates="work_calendars")


class PMAprobacion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_aprobaciones"
    __table_args__ = (
        Index("ix_pm_aprobaciones_empresa_id", "empresa_id"),
        Index("ix_pm_aprobaciones_proyecto_id", "proyecto_id"),
        Index("ix_pm_aprobaciones_tipo", "tipo_aprobacion"),
        Index("ix_pm_aprobaciones_estatus", "estatus"),
        Index("ix_pm_aprobaciones_activo", "activo"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    tipo_aprobacion: Mapped[str] = mapped_column(String(40), nullable=False, default="otro", server_default="otro")
    titulo: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    estatus: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente", server_default="pendiente")
    entidad_tipo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entidad_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    solicitado_por: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    solicitado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resuelto_por: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comentario_resolucion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    proyecto = relationship("PMProyecto", back_populates="approvals")


class PMInvitadoExterno(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_invitados_externos"
    __table_args__ = (
        Index("ix_pm_invitados_externos_empresa_id", "empresa_id"),
        Index("ix_pm_invitados_externos_proyecto_id", "proyecto_id"),
        Index("ix_pm_invitados_externos_activo", "activo"),
        Index("ix_pm_invitados_externos_token_preview", "token_preview"),
        Index("uq_pm_invitados_externos_token_hash", "token_hash", unique=True),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    modo_acceso: Mapped[str] = mapped_column(String(20), nullable=False, default="solo_lectura", server_default="solo_lectura")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_preview: Mapped[str | None] = mapped_column(String(24), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    revocado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expira_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_acceso_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_accesos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    proyecto = relationship("PMProyecto", back_populates="external_invites")
    comments = relationship("PMComentario", back_populates="invitado_externo")
    access_logs = relationship("PMPortalAccessLog", back_populates="invitado_externo", cascade="all, delete-orphan")


class PMPortalAccessLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_portal_access_logs"
    __table_args__ = (
        Index("ix_pm_portal_logs_empresa_id", "empresa_id"),
        Index("ix_pm_portal_logs_proyecto_id", "proyecto_id"),
        Index("ix_pm_portal_logs_invitado_id", "invitado_externo_id"),
        Index("ix_pm_portal_logs_accion", "accion"),
        Index("ix_pm_portal_logs_resultado", "resultado"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    invitado_externo_id: Mapped[str | None] = mapped_column(
        ForeignKey("pm_invitados_externos.id"),
        nullable=True,
        index=True,
    )
    accion: Mapped[str] = mapped_column(String(60), nullable=False)
    resultado: Mapped[str] = mapped_column(String(40), nullable=False, default="ok", server_default="ok")
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    proyecto = relationship("PMProyecto", back_populates="portal_access_logs")
    invitado_externo = relationship("PMInvitadoExterno", back_populates="access_logs")


class PMAlerta(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_alertas"
    __table_args__ = (
        Index("ix_pm_alertas_empresa_id", "empresa_id"),
        Index("ix_pm_alertas_proyecto_id", "proyecto_id"),
        Index("ix_pm_alertas_tarea_id", "tarea_id"),
        Index("ix_pm_alertas_tipo", "tipo"),
        Index("ix_pm_alertas_severidad", "severidad"),
        Index("ix_pm_alertas_estatus", "estatus"),
        Index("ix_pm_alertas_activa", "activa"),
        Index("ix_pm_alertas_dedupe_key", "dedupe_key"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False, index=True)
    tarea_id: Mapped[str | None] = mapped_column(ForeignKey("pm_tareas.id"), nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    severidad: Mapped[str] = mapped_column(String(20), nullable=False, default="warning", server_default="warning")
    titulo: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    estatus: Mapped[str] = mapped_column(String(20), nullable=False, default="abierta", server_default="abierta")
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    resuelta_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resuelta_por: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)

    proyecto = relationship("PMProyecto", back_populates="alerts")
    tarea = relationship("PMTarea", back_populates="alerts")
