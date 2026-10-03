"""Add persistent PM spreadsheet import staging and estimation evidence."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260929_0048"
down_revision: str | None = "20260806_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pm_excel_import_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("proyecto_id", sa.String(length=36), nullable=False),
        sa.Column("uploaded_by", sa.String(length=36), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("original_file_reference", sa.String(length=1000), nullable=True),
        sa.Column("original_file_size", sa.Integer(), nullable=True),
        sa.Column("original_file_content_type", sa.String(length=120), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="review", nullable=False),
        sa.Column("format_type", sa.String(length=30), server_default="generic", nullable=False),
        sa.Column("selected_sheet", sa.String(length=255), nullable=True),
        sa.Column("mapping_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("metadata_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("summary_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pm_excel_import_sessions_empresa", "pm_excel_import_sessions", ["empresa_id"])
    op.create_index("ix_pm_excel_import_sessions_proyecto", "pm_excel_import_sessions", ["proyecto_id"])
    op.create_index("ix_pm_excel_import_sessions_status", "pm_excel_import_sessions", ["status"])
    op.create_index("ix_pm_excel_import_sessions_hash", "pm_excel_import_sessions", ["empresa_id", "file_hash"])

    op.create_table(
        "pm_excel_import_rows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("source_sheet", sa.String(length=255), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("row_type", sa.String(length=20), server_default="item", nullable=False),
        sa.Column("raw_values_json", sa.Text(), nullable=False),
        sa.Column("interpreted_values_json", sa.Text(), nullable=False),
        sa.Column("confirmed_values_json", sa.Text(), nullable=False),
        sa.Column("warning_codes_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("include", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("edited_by_user", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["pm_excel_import_sessions.id"]),
        sa.ForeignKeyConstraint(["edited_by_user"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pm_excel_import_rows_empresa", "pm_excel_import_rows", ["empresa_id"])
    op.create_index("ix_pm_excel_import_rows_session", "pm_excel_import_rows", ["session_id"])
    op.create_index(
        "ix_pm_excel_import_rows_source",
        "pm_excel_import_rows",
        ["session_id", "source_sheet", "source_row"],
    )

    op.create_table(
        "pm_estimacion_evidencias",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("proyecto_id", sa.String(length=36), nullable=False),
        sa.Column("estimacion_id", sa.String(length=36), nullable=True),
        sa.Column("presupuesto_partida_id", sa.String(length=36), nullable=True),
        sa.Column("import_session_id", sa.String(length=36), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("url_archivo", sa.String(length=1000), nullable=False),
        sa.Column("blob_path", sa.String(length=1000), nullable=True),
        sa.Column("nombre_archivo", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("descripcion", sa.String(length=500), nullable=True),
        sa.Column("fecha_evidencia", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ubicacion", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
        sa.ForeignKeyConstraint(["estimacion_id"], ["pm_estimaciones.id"]),
        sa.ForeignKeyConstraint(["presupuesto_partida_id"], ["pm_presupuesto_partidas.id"]),
        sa.ForeignKeyConstraint(["import_session_id"], ["pm_excel_import_sessions.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pm_estimacion_evidencias_empresa", "pm_estimacion_evidencias", ["empresa_id"])
    op.create_index("ix_pm_estimacion_evidencias_estimacion", "pm_estimacion_evidencias", ["estimacion_id"])
    op.create_index("ix_pm_estimacion_evidencias_partida", "pm_estimacion_evidencias", ["presupuesto_partida_id"])
    op.create_index("ix_pm_estimacion_evidencias_session", "pm_estimacion_evidencias", ["import_session_id"])


def downgrade() -> None:
    op.drop_index("ix_pm_estimacion_evidencias_session", table_name="pm_estimacion_evidencias")
    op.drop_index("ix_pm_estimacion_evidencias_partida", table_name="pm_estimacion_evidencias")
    op.drop_index("ix_pm_estimacion_evidencias_estimacion", table_name="pm_estimacion_evidencias")
    op.drop_index("ix_pm_estimacion_evidencias_empresa", table_name="pm_estimacion_evidencias")
    op.drop_table("pm_estimacion_evidencias")
    op.drop_index("ix_pm_excel_import_rows_source", table_name="pm_excel_import_rows")
    op.drop_index("ix_pm_excel_import_rows_session", table_name="pm_excel_import_rows")
    op.drop_index("ix_pm_excel_import_rows_empresa", table_name="pm_excel_import_rows")
    op.drop_table("pm_excel_import_rows")
    op.drop_index("ix_pm_excel_import_sessions_hash", table_name="pm_excel_import_sessions")
    op.drop_index("ix_pm_excel_import_sessions_status", table_name="pm_excel_import_sessions")
    op.drop_index("ix_pm_excel_import_sessions_proyecto", table_name="pm_excel_import_sessions")
    op.drop_index("ix_pm_excel_import_sessions_empresa", table_name="pm_excel_import_sessions")
    op.drop_table("pm_excel_import_sessions")
