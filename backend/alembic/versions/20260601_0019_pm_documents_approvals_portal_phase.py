"""PM documents, approvals and external portal phase 5.

Revision ID: 20260601_0019
Revises: 20260531_0018
Create Date: 2026-06-01 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260601_0019"
down_revision: str | None = "20260531_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def has_index(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def using_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def create_index_if_missing(index_name: str, table_name: str, columns: list[str], **kwargs) -> None:
    if not has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, **kwargs)


def upgrade() -> None:
    if has_table("empresa_pm_config") and has_column("empresa_pm_config", "pm_portal_enabled"):
        op.execute(
            sa.text(
                """
                UPDATE empresa_pm_config
                SET pm_portal_enabled = 1
                WHERE pm_enabled = 1
                  AND (pm_portal_enabled IS NULL OR pm_portal_enabled = 0)
                """
            )
        )

    if not has_table("pm_documentos"):
        op.create_table(
            "pm_documentos",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("tipo_documento", sa.String(length=40), nullable=False, server_default="otro"),
            sa.Column("nombre", sa.String(length=180), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("url_archivo", sa.String(length=500), nullable=False),
            sa.Column("nombre_archivo", sa.String(length=255), nullable=True),
            sa.Column("mime_type", sa.String(length=160), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("visible_externo", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_documentos_empresa_id", "pm_documentos", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_documentos_proyecto_id", "pm_documentos", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_documentos_tipo", "pm_documentos", ["tipo_documento"], unique=False)
    create_index_if_missing("ix_pm_documentos_visible_externo", "pm_documentos", ["visible_externo"], unique=False)
    create_index_if_missing("ix_pm_documentos_activo", "pm_documentos", ["activo"], unique=False)

    if not has_table("pm_aprobaciones"):
        op.create_table(
            "pm_aprobaciones",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("tipo_aprobacion", sa.String(length=40), nullable=False, server_default="otro"),
            sa.Column("titulo", sa.String(length=180), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("estatus", sa.String(length=20), nullable=False, server_default="pendiente"),
            sa.Column("entidad_tipo", sa.String(length=40), nullable=True),
            sa.Column("entidad_id", sa.String(length=36), nullable=True),
            sa.Column("solicitado_por", sa.String(length=36), nullable=True),
            sa.Column("solicitado_en", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resuelto_por", sa.String(length=36), nullable=True),
            sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
            sa.Column("comentario_resolucion", sa.Text(), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["solicitado_por"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["resuelto_por"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_aprobaciones_empresa_id", "pm_aprobaciones", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_aprobaciones_proyecto_id", "pm_aprobaciones", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_aprobaciones_tipo", "pm_aprobaciones", ["tipo_aprobacion"], unique=False)
    create_index_if_missing("ix_pm_aprobaciones_estatus", "pm_aprobaciones", ["estatus"], unique=False)
    create_index_if_missing("ix_pm_aprobaciones_activo", "pm_aprobaciones", ["activo"], unique=False)

    if not has_table("pm_invitados_externos"):
        op.create_table(
            "pm_invitados_externos",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("nombre", sa.String(length=180), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("modo_acceso", sa.String(length=20), nullable=False, server_default="solo_lectura"),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("token_preview", sa.String(length=24), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("revocado_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expira_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ultimo_acceso_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_accesos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_invitados_externos_empresa_id", "pm_invitados_externos", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_invitados_externos_proyecto_id", "pm_invitados_externos", ["proyecto_id"], unique=False)
    create_index_if_missing("ix_pm_invitados_externos_activo", "pm_invitados_externos", ["activo"], unique=False)
    create_index_if_missing(
        "ix_pm_invitados_externos_token_preview",
        "pm_invitados_externos",
        ["token_preview"],
        unique=False,
    )
    create_index_if_missing(
        "uq_pm_invitados_externos_token_hash",
        "pm_invitados_externos",
        ["token_hash"],
        unique=True,
    )

    if not has_table("pm_portal_access_logs"):
        op.create_table(
            "pm_portal_access_logs",
            sa.Column("empresa_id", sa.String(length=36), nullable=False),
            sa.Column("proyecto_id", sa.String(length=36), nullable=False),
            sa.Column("invitado_externo_id", sa.String(length=36), nullable=True),
            sa.Column("accion", sa.String(length=60), nullable=False),
            sa.Column("resultado", sa.String(length=40), nullable=False, server_default="ok"),
            sa.Column("detalle", sa.Text(), nullable=True),
            sa.Column("ip_hash", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
            sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
            sa.ForeignKeyConstraint(["invitado_externo_id"], ["pm_invitados_externos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    create_index_if_missing("ix_pm_portal_logs_empresa_id", "pm_portal_access_logs", ["empresa_id"], unique=False)
    create_index_if_missing("ix_pm_portal_logs_proyecto_id", "pm_portal_access_logs", ["proyecto_id"], unique=False)
    create_index_if_missing(
        "ix_pm_portal_logs_invitado_id",
        "pm_portal_access_logs",
        ["invitado_externo_id"],
        unique=False,
    )
    create_index_if_missing("ix_pm_portal_logs_accion", "pm_portal_access_logs", ["accion"], unique=False)
    create_index_if_missing("ix_pm_portal_logs_resultado", "pm_portal_access_logs", ["resultado"], unique=False)

    if has_table("pm_comentarios"):
        if not has_column("pm_comentarios", "externo"):
            op.add_column(
                "pm_comentarios",
                sa.Column("externo", sa.Boolean(), nullable=False, server_default="0"),
            )
        if not has_column("pm_comentarios", "autor_nombre_snapshot"):
            op.add_column(
                "pm_comentarios",
                sa.Column("autor_nombre_snapshot", sa.String(length=160), nullable=True),
            )
        if not has_column("pm_comentarios", "invitado_externo_id"):
            op.add_column(
                "pm_comentarios",
                sa.Column("invitado_externo_id", sa.String(length=36), nullable=True),
            )
        create_index_if_missing("ix_pm_comentarios_externo", "pm_comentarios", ["externo"], unique=False)
        create_index_if_missing(
            "ix_pm_comentarios_invitado_externo_id",
            "pm_comentarios",
            ["invitado_externo_id"],
            unique=False,
        )


def downgrade() -> None:
    if has_table("pm_comentarios"):
        if has_index("pm_comentarios", "ix_pm_comentarios_invitado_externo_id"):
            op.drop_index("ix_pm_comentarios_invitado_externo_id", table_name="pm_comentarios")
        if has_index("pm_comentarios", "ix_pm_comentarios_externo"):
            op.drop_index("ix_pm_comentarios_externo", table_name="pm_comentarios")
        recreate_mode = "always" if using_sqlite() else "auto"
        with op.batch_alter_table("pm_comentarios", recreate=recreate_mode) as batch_op:
            if has_column("pm_comentarios", "invitado_externo_id"):
                batch_op.drop_column("invitado_externo_id")
            if has_column("pm_comentarios", "autor_nombre_snapshot"):
                batch_op.drop_column("autor_nombre_snapshot")
            if has_column("pm_comentarios", "externo"):
                batch_op.drop_column("externo")

    if has_table("pm_portal_access_logs"):
        for index_name in [
            "ix_pm_portal_logs_resultado",
            "ix_pm_portal_logs_accion",
            "ix_pm_portal_logs_invitado_id",
            "ix_pm_portal_logs_proyecto_id",
            "ix_pm_portal_logs_empresa_id",
        ]:
            if has_index("pm_portal_access_logs", index_name):
                op.drop_index(index_name, table_name="pm_portal_access_logs")
        op.drop_table("pm_portal_access_logs")

    if has_table("pm_invitados_externos"):
        for index_name in [
            "uq_pm_invitados_externos_token_hash",
            "ix_pm_invitados_externos_token_preview",
            "ix_pm_invitados_externos_activo",
            "ix_pm_invitados_externos_proyecto_id",
            "ix_pm_invitados_externos_empresa_id",
        ]:
            if has_index("pm_invitados_externos", index_name):
                op.drop_index(index_name, table_name="pm_invitados_externos")
        op.drop_table("pm_invitados_externos")

    if has_table("pm_aprobaciones"):
        for index_name in [
            "ix_pm_aprobaciones_activo",
            "ix_pm_aprobaciones_estatus",
            "ix_pm_aprobaciones_tipo",
            "ix_pm_aprobaciones_proyecto_id",
            "ix_pm_aprobaciones_empresa_id",
        ]:
            if has_index("pm_aprobaciones", index_name):
                op.drop_index(index_name, table_name="pm_aprobaciones")
        op.drop_table("pm_aprobaciones")

    if has_table("pm_documentos"):
        for index_name in [
            "ix_pm_documentos_activo",
            "ix_pm_documentos_visible_externo",
            "ix_pm_documentos_tipo",
            "ix_pm_documentos_proyecto_id",
            "ix_pm_documentos_empresa_id",
        ]:
            if has_index("pm_documentos", index_name):
                op.drop_index(index_name, table_name="pm_documentos")
        op.drop_table("pm_documentos")
