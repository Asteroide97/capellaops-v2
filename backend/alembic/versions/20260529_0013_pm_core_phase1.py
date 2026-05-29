"""Create PM core phase 1 tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260529_0013"
down_revision = "20260528_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "empresa_pm_config",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("pm_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("pm_tareas_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("pm_materiales_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("pm_tiempo_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("pm_templates_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("pm_comercial_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("pm_portal_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
    )
    op.create_index("ix_empresa_pm_config_empresa_id", "empresa_pm_config", ["empresa_id"], unique=False)
    op.create_index("uq_empresa_pm_config_empresa_id", "empresa_pm_config", ["empresa_id"], unique=True)

    op.create_table(
        "pm_proyectos",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("nombre", sa.String(length=180), nullable=False),
        sa.Column("codigo", sa.String(length=60), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("tipo_proyecto", sa.String(length=80), nullable=True),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default="borrador"),
        sa.Column("prioridad", sa.String(length=20), nullable=False, server_default="media"),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_fin_planificada", sa.Date(), nullable=True),
        sa.Column("fecha_fin_real", sa.Date(), nullable=True),
        sa.Column("porcentaje_avance", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("responsable_user_id", sa.String(length=36), nullable=True),
        sa.Column("responsable_nombre_snapshot", sa.String(length=160), nullable=True),
        sa.Column("cliente_nombre_snapshot", sa.String(length=180), nullable=True),
        sa.Column("presupuesto_estimado", sa.Numeric(18, 2), nullable=True, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("porcentaje_avance >= 0 AND porcentaje_avance <= 100", name="ck_pm_proyectos_porcentaje"),
        sa.CheckConstraint(
            "presupuesto_estimado IS NULL OR presupuesto_estimado >= 0",
            name="ck_pm_proyectos_presupuesto_non_negative",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["responsable_user_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
    )
    op.create_index("ix_pm_proyectos_empresa_id", "pm_proyectos", ["empresa_id"], unique=False)
    op.create_index("ix_pm_proyectos_estatus", "pm_proyectos", ["estatus"], unique=False)
    op.create_index("ix_pm_proyectos_activo", "pm_proyectos", ["activo"], unique=False)
    op.create_index(
        "uq_pm_proyectos_empresa_codigo",
        "pm_proyectos",
        ["empresa_id", "codigo"],
        unique=True,
        sqlite_where=sa.text("codigo IS NOT NULL"),
        mssql_where=sa.text("codigo IS NOT NULL"),
    )

    op.create_table(
        "pm_proyecto_miembros",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("proyecto_id", sa.String(length=36), nullable=False),
        sa.Column("usuario_id", sa.String(length=36), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("nombre_snapshot", sa.String(length=160), nullable=True),
        sa.Column("rol_en_proyecto", sa.String(length=20), nullable=False, server_default="colaborador"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("usuario_id IS NOT NULL OR email IS NOT NULL", name="ck_pm_miembros_usuario_or_email"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
    )
    op.create_index("ix_pm_proyecto_miembros_empresa_id", "pm_proyecto_miembros", ["empresa_id"], unique=False)
    op.create_index("ix_pm_proyecto_miembros_proyecto_id", "pm_proyecto_miembros", ["proyecto_id"], unique=False)
    op.create_index("ix_pm_proyecto_miembros_activo", "pm_proyecto_miembros", ["activo"], unique=False)
    op.create_index(
        "uq_pm_proyecto_miembro_usuario_activo",
        "pm_proyecto_miembros",
        ["proyecto_id", "usuario_id"],
        unique=True,
        sqlite_where=sa.text("activo = 1 AND usuario_id IS NOT NULL"),
        mssql_where=sa.text("activo = 1 AND usuario_id IS NOT NULL"),
    )
    op.create_index(
        "uq_pm_proyecto_miembro_email_activo",
        "pm_proyecto_miembros",
        ["proyecto_id", "email"],
        unique=True,
        sqlite_where=sa.text("activo = 1 AND email IS NOT NULL"),
        mssql_where=sa.text("activo = 1 AND email IS NOT NULL"),
    )

    op.create_table(
        "pm_tareas",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("proyecto_id", sa.String(length=36), nullable=False),
        sa.Column("titulo", sa.String(length=180), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default="pendiente"),
        sa.Column("prioridad", sa.String(length=20), nullable=False, server_default="media"),
        sa.Column("asignado_user_id", sa.String(length=36), nullable=True),
        sa.Column("asignado_nombre_snapshot", sa.String(length=160), nullable=True),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=True),
        sa.Column("fecha_completada", sa.Date(), nullable=True),
        sa.Column("estimacion_horas", sa.Numeric(12, 2), nullable=True, server_default="0"),
        sa.Column("porcentaje_avance", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bloqueada", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("requiere_materiales", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("requiere_compra", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("requiere_venta_pos", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("requiere_factura", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("porcentaje_avance >= 0 AND porcentaje_avance <= 100", name="ck_pm_tareas_porcentaje"),
        sa.CheckConstraint(
            "estimacion_horas IS NULL OR estimacion_horas >= 0",
            name="ck_pm_tareas_estimacion_non_negative",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
        sa.ForeignKeyConstraint(["asignado_user_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
    )
    op.create_index("ix_pm_tareas_empresa_id", "pm_tareas", ["empresa_id"], unique=False)
    op.create_index("ix_pm_tareas_proyecto_id", "pm_tareas", ["proyecto_id"], unique=False)
    op.create_index("ix_pm_tareas_estatus", "pm_tareas", ["estatus"], unique=False)
    op.create_index("ix_pm_tareas_activo", "pm_tareas", ["activo"], unique=False)
    op.create_index("ix_pm_tareas_fecha_vencimiento", "pm_tareas", ["fecha_vencimiento"], unique=False)

    op.create_table(
        "pm_subtareas",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("tarea_id", sa.String(length=36), nullable=False),
        sa.Column("titulo", sa.String(length=180), nullable=False),
        sa.Column("estatus", sa.String(length=20), nullable=False, server_default="pendiente"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("asignado_user_id", sa.String(length=36), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
        sa.ForeignKeyConstraint(["asignado_user_id"], ["usuarios.id"]),
    )
    op.create_index("ix_pm_subtareas_empresa_id", "pm_subtareas", ["empresa_id"], unique=False)
    op.create_index("ix_pm_subtareas_tarea_id", "pm_subtareas", ["tarea_id"], unique=False)
    op.create_index("ix_pm_subtareas_activo", "pm_subtareas", ["activo"], unique=False)

    op.create_table(
        "pm_checklist_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("tarea_id", sa.String(length=36), nullable=False),
        sa.Column("titulo", sa.String(length=180), nullable=False),
        sa.Column("completado", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
    )
    op.create_index("ix_pm_checklist_empresa_id", "pm_checklist_items", ["empresa_id"], unique=False)
    op.create_index("ix_pm_checklist_tarea_id", "pm_checklist_items", ["tarea_id"], unique=False)
    op.create_index("ix_pm_checklist_activo", "pm_checklist_items", ["activo"], unique=False)

    op.create_table(
        "pm_comentarios",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("empresa_id", sa.String(length=36), nullable=False),
        sa.Column("proyecto_id", sa.String(length=36), nullable=True),
        sa.Column("tarea_id", sa.String(length=36), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_by_nombre_snapshot", sa.String(length=160), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("proyecto_id IS NOT NULL OR tarea_id IS NOT NULL", name="ck_pm_comentarios_target"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["proyecto_id"], ["pm_proyectos.id"]),
        sa.ForeignKeyConstraint(["tarea_id"], ["pm_tareas.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
    )
    op.create_index("ix_pm_comentarios_empresa_id", "pm_comentarios", ["empresa_id"], unique=False)
    op.create_index("ix_pm_comentarios_proyecto_id", "pm_comentarios", ["proyecto_id"], unique=False)
    op.create_index("ix_pm_comentarios_tarea_id", "pm_comentarios", ["tarea_id"], unique=False)
    op.create_index("ix_pm_comentarios_activo", "pm_comentarios", ["activo"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pm_comentarios_activo", table_name="pm_comentarios")
    op.drop_index("ix_pm_comentarios_tarea_id", table_name="pm_comentarios")
    op.drop_index("ix_pm_comentarios_proyecto_id", table_name="pm_comentarios")
    op.drop_index("ix_pm_comentarios_empresa_id", table_name="pm_comentarios")
    op.drop_table("pm_comentarios")

    op.drop_index("ix_pm_checklist_activo", table_name="pm_checklist_items")
    op.drop_index("ix_pm_checklist_tarea_id", table_name="pm_checklist_items")
    op.drop_index("ix_pm_checklist_empresa_id", table_name="pm_checklist_items")
    op.drop_table("pm_checklist_items")

    op.drop_index("ix_pm_subtareas_activo", table_name="pm_subtareas")
    op.drop_index("ix_pm_subtareas_tarea_id", table_name="pm_subtareas")
    op.drop_index("ix_pm_subtareas_empresa_id", table_name="pm_subtareas")
    op.drop_table("pm_subtareas")

    op.drop_index("ix_pm_tareas_fecha_vencimiento", table_name="pm_tareas")
    op.drop_index("ix_pm_tareas_activo", table_name="pm_tareas")
    op.drop_index("ix_pm_tareas_estatus", table_name="pm_tareas")
    op.drop_index("ix_pm_tareas_proyecto_id", table_name="pm_tareas")
    op.drop_index("ix_pm_tareas_empresa_id", table_name="pm_tareas")
    op.drop_table("pm_tareas")

    op.drop_index("uq_pm_proyecto_miembro_email_activo", table_name="pm_proyecto_miembros")
    op.drop_index("uq_pm_proyecto_miembro_usuario_activo", table_name="pm_proyecto_miembros")
    op.drop_index("ix_pm_proyecto_miembros_activo", table_name="pm_proyecto_miembros")
    op.drop_index("ix_pm_proyecto_miembros_proyecto_id", table_name="pm_proyecto_miembros")
    op.drop_index("ix_pm_proyecto_miembros_empresa_id", table_name="pm_proyecto_miembros")
    op.drop_table("pm_proyecto_miembros")

    op.drop_index("uq_pm_proyectos_empresa_codigo", table_name="pm_proyectos")
    op.drop_index("ix_pm_proyectos_activo", table_name="pm_proyectos")
    op.drop_index("ix_pm_proyectos_estatus", table_name="pm_proyectos")
    op.drop_index("ix_pm_proyectos_empresa_id", table_name="pm_proyectos")
    op.drop_table("pm_proyectos")

    op.drop_index("uq_empresa_pm_config_empresa_id", table_name="empresa_pm_config")
    op.drop_index("ix_empresa_pm_config_empresa_id", table_name="empresa_pm_config")
    op.drop_table("empresa_pm_config")
