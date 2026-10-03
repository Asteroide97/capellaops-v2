from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PMExcelImportSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_excel_import_sessions"
    __table_args__ = (
        Index("ix_pm_excel_import_sessions_empresa", "empresa_id"),
        Index("ix_pm_excel_import_sessions_proyecto", "proyecto_id"),
        Index("ix_pm_excel_import_sessions_status", "status"),
        Index("ix_pm_excel_import_sessions_hash", "empresa_id", "file_hash"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    original_file_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_file_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="review", server_default="review")
    format_type: Mapped[str] = mapped_column(String(30), nullable=False, default="generic", server_default="generic")
    selected_sheet: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mapping_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PMExcelImportRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_excel_import_rows"
    __table_args__ = (
        Index("ix_pm_excel_import_rows_empresa", "empresa_id"),
        Index("ix_pm_excel_import_rows_session", "session_id"),
        Index("ix_pm_excel_import_rows_source", "session_id", "source_sheet", "source_row"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(ForeignKey("pm_excel_import_sessions.id"), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    row_type: Mapped[str] = mapped_column(String(20), nullable=False, default="item", server_default="item")
    raw_values_json: Mapped[str] = mapped_column(Text, nullable=False)
    interpreted_values_json: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_values_json: Mapped[str] = mapped_column(Text, nullable=False)
    warning_codes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    include: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    edited_by_user: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)


class PMEstimacionEvidencia(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pm_estimacion_evidencias"
    __table_args__ = (
        Index("ix_pm_estimacion_evidencias_empresa", "empresa_id"),
        Index("ix_pm_estimacion_evidencias_estimacion", "estimacion_id"),
        Index("ix_pm_estimacion_evidencias_partida", "presupuesto_partida_id"),
        Index("ix_pm_estimacion_evidencias_session", "import_session_id"),
    )

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    proyecto_id: Mapped[str] = mapped_column(ForeignKey("pm_proyectos.id"), nullable=False)
    estimacion_id: Mapped[str | None] = mapped_column(ForeignKey("pm_estimaciones.id"), nullable=True)
    presupuesto_partida_id: Mapped[str | None] = mapped_column(ForeignKey("pm_presupuesto_partidas.id"), nullable=True)
    import_session_id: Mapped[str | None] = mapped_column(ForeignKey("pm_excel_import_sessions.id"), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url_archivo: Mapped[str] = mapped_column(String(1000), nullable=False)
    blob_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fecha_evidencia: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ubicacion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
