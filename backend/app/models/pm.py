from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, Text, text
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
    subtasks = relationship("PMSubtarea", back_populates="tarea", cascade="all, delete-orphan")
    checklist_items = relationship("PMChecklistItem", back_populates="tarea", cascade="all, delete-orphan")
    comments = relationship("PMComentario", back_populates="tarea", cascade="all, delete-orphan")


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
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    proyecto = relationship("PMProyecto", back_populates="comments")
    tarea = relationship("PMTarea", back_populates="comments")
