from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateIndex

from app.models import Empresa, EmpresaUsuario, Plan, Usuario
from app.models.pm import EmpresaPMConfig, PMPresupuesto, PMPresupuestoPartida, PMProyecto
from app.services.pm import PMContext, create_budget_item, get_project_costs


class PMBudgetSchemaRepairMigrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend_dir = Path(__file__).resolve().parents[1]
        cls.temp_root = Path(tempfile.mkdtemp(prefix="pm-budget-schema-repair-"))
        cls.template_0044_path = cls.temp_root / "template_0044.db"
        cls.template_0045_path = cls.temp_root / "template_0045.db"
        cls._create_template(cls.template_0044_path, "20260621_0044")
        cls._create_template(cls.template_0045_path, "20260805_0045")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temp_root, ignore_errors=True)

    @classmethod
    def _create_template(cls, target_path: Path, revision: str) -> None:
        env = dict(__import__("os").environ)
        env["DATABASE_URL"] = f"sqlite:///{target_path.as_posix()}"
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            cwd=cls.backend_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Alembic template upgrade to {revision} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

    def setUp(self) -> None:
        self.db_path = self.temp_root / f"{self._testMethodName}.db"
        self.engine = None
        self.db = None
        self.SessionLocal = None

    def tearDown(self) -> None:
        if self.db is not None:
            self.db.close()
        if self.engine is not None:
            self.engine.dispose()
        if self.db_path.exists():
            self.db_path.unlink()

    def _prepare_database(self, template_path: Path) -> None:
        shutil.copyfile(template_path, self.db_path)
        self._connect_current_database()

    def _connect_current_database(self) -> None:
        self.engine = create_engine(f"sqlite:///{self.db_path.as_posix()}", future=True)

        @event.listens_for(self.engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, class_=Session)
        self.db = self.SessionLocal()

    def _upgrade(self, revision: str = "head") -> None:
        env = dict(__import__("os").environ)
        env["DATABASE_URL"] = f"sqlite:///{self.db_path.as_posix()}"
        if self.db is not None:
            self.db.close()
            self.db = None
        if self.engine is not None:
            self.engine.dispose()
            self.engine = None
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            cwd=self.backend_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(f"Alembic upgrade to {revision} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        self._connect_current_database()

    def _seed_company_context(self, *, suffix: str) -> tuple[Empresa, Usuario, PMContext, PMProyecto, PMPresupuesto]:
        plan = Plan(code=f"basic-{suffix}", name=f"Basic {suffix}", modules=["pm"])
        company = Empresa(
            name=f"Empresa {suffix}",
            slug=f"empresa-{suffix}",
            plan_code=plan.code,
            access_status="active",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        user = Usuario(
            email=f"{suffix}@example.com",
            full_name=f"User {suffix}",
            password_hash="hash",
            is_active=True,
            is_superadmin=False,
        )
        self.db.add_all([plan, company, user])
        self.db.flush()

        membership = EmpresaUsuario(
            empresa_id=company.id,
            usuario_id=user.id,
            role="admin",
            is_active=True,
        )
        config = EmpresaPMConfig(
            empresa_id=company.id,
            pm_enabled=True,
            pm_tareas_enabled=True,
            pm_materiales_enabled=True,
            pm_tiempo_enabled=True,
            pm_templates_enabled=False,
            pm_comercial_enabled=False,
            pm_portal_enabled=True,
        )
        project = PMProyecto(
            empresa_id=company.id,
            nombre=f"Proyecto {suffix}",
            codigo=None,
            estatus="activo",
            prioridad="media",
            created_by=user.id,
            updated_by=user.id,
        )
        self.db.add_all([membership, config, project])
        self.db.flush()
        budget = PMPresupuesto(
            empresa_id=company.id,
            proyecto_id=project.id,
            nombre="Presupuesto base",
            version=1,
            estatus="borrador",
            moneda="MXN",
            activo=True,
        )
        self.db.add(budget)
        self.db.flush()
        self.db.commit()

        pm_context = PMContext(user=user, empresa_id=company.id, membership_role="admin", config=config)
        return company, user, pm_context, project, budget

    def _insert_budget_item_without_lineage(
        self,
        *,
        company_id: str,
        budget_id: str,
        project_id: str,
        item_id: str | None = None,
        parent_id: str | None = None,
        codigo: str | None = None,
        nombre: str = "Partida base",
        tipo: str = "partida",
    ) -> str:
        item_id = item_id or str(uuid4())
        now = datetime.now(timezone.utc)
        is_partida = tipo == "partida"
        self.db.execute(
            text(
                """
                INSERT INTO pm_presupuesto_partidas (
                    id,
                    empresa_id,
                    presupuesto_id,
                    proyecto_id,
                    parent_id,
                    codigo,
                    nombre,
                    descripcion,
                    tipo,
                    unidad,
                    cantidad,
                    costo_unitario,
                    precio_unitario,
                    precio_unitario_manual,
                    subtotal_costo,
                    subtotal_venta,
                    margen_pct,
                    orden,
                    activo,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :empresa_id,
                    :presupuesto_id,
                    :proyecto_id,
                    :parent_id,
                    :codigo,
                    :nombre,
                    :descripcion,
                    :tipo,
                    :unidad,
                    :cantidad,
                    :costo_unitario,
                    :precio_unitario,
                    :precio_unitario_manual,
                    :subtotal_costo,
                    :subtotal_venta,
                    :margen_pct,
                    :orden,
                    :activo,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": item_id,
                "empresa_id": company_id,
                "presupuesto_id": budget_id,
                "proyecto_id": project_id,
                "parent_id": parent_id,
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": None,
                "tipo": tipo,
                "unidad": "servicio" if is_partida else None,
                "cantidad": 1,
                "costo_unitario": 0,
                "precio_unitario": 1000,
                "precio_unitario_manual": 1000 if is_partida else None,
                "subtotal_costo": 0,
                "subtotal_venta": 1000 if is_partida else 0,
                "margen_pct": 0,
                "orden": 1,
                "activo": True,
                "created_at": now,
                "updated_at": now,
            },
        )
        self.db.commit()
        return item_id

    def _insert_budget_item_with_lineage(
        self,
        *,
        company_id: str,
        budget_id: str,
        project_id: str,
        lineage_id: str | None,
        item_id: str | None = None,
        parent_id: str | None = None,
        codigo: str | None = None,
        nombre: str = "Partida con lineage",
        tipo: str = "partida",
    ) -> str:
        item_id = item_id or str(uuid4())
        now = datetime.now(timezone.utc)
        is_partida = tipo == "partida"
        self.db.execute(
            text(
                """
                INSERT INTO pm_presupuesto_partidas (
                    id,
                    empresa_id,
                    presupuesto_id,
                    proyecto_id,
                    parent_id,
                    lineage_id,
                    codigo,
                    nombre,
                    descripcion,
                    tipo,
                    unidad,
                    cantidad,
                    costo_unitario,
                    precio_unitario,
                    precio_unitario_manual,
                    subtotal_costo,
                    subtotal_venta,
                    margen_pct,
                    orden,
                    activo,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :empresa_id,
                    :presupuesto_id,
                    :proyecto_id,
                    :parent_id,
                    :lineage_id,
                    :codigo,
                    :nombre,
                    :descripcion,
                    :tipo,
                    :unidad,
                    :cantidad,
                    :costo_unitario,
                    :precio_unitario,
                    :precio_unitario_manual,
                    :subtotal_costo,
                    :subtotal_venta,
                    :margen_pct,
                    :orden,
                    :activo,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": item_id,
                "empresa_id": company_id,
                "presupuesto_id": budget_id,
                "proyecto_id": project_id,
                "parent_id": parent_id,
                "lineage_id": lineage_id,
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": None,
                "tipo": tipo,
                "unidad": "servicio" if is_partida else None,
                "cantidad": 1,
                "costo_unitario": 0,
                "precio_unitario": 1000,
                "precio_unitario_manual": 1000 if is_partida else None,
                "subtotal_costo": 0,
                "subtotal_venta": 1000 if is_partida else 0,
                "margen_pct": 0,
                "orden": 1,
                "activo": True,
                "created_at": now,
                "updated_at": now,
            },
        )
        self.db.commit()
        return item_id

    def _stamp_revision(self, revision: str) -> None:
        self.db.execute(text("UPDATE alembic_version SET version_num = :revision"), {"revision": revision})
        self.db.commit()

    def _reload_pm_context(self, *, user_id: str, company_id: str) -> PMContext:
        user = self.db.get(Usuario, user_id)
        config = self.db.execute(
            select(EmpresaPMConfig).where(EmpresaPMConfig.empresa_id == company_id)
        ).scalar_one()
        return PMContext(user=user, empresa_id=company_id, membership_role="admin", config=config)

    def test_upgrade_from_0044_to_head_repairs_schema_and_costs_query(self) -> None:
        self._prepare_database(self.template_0044_path)
        company, _user, pm_context, project, budget = self._seed_company_context(suffix="from0044")
        user_id = pm_context.user.id
        company_id = pm_context.empresa_id
        project_id = project.id
        self._insert_budget_item_without_lineage(
            company_id=company.id,
            budget_id=budget.id,
            project_id=project.id,
            codigo="01.01",
            nombre="Instalacion base",
        )

        self._upgrade("head")
        pm_context = self._reload_pm_context(user_id=user_id, company_id=company_id)

        inspector = inspect(self.engine)
        columns = {column["name"]: column for column in inspector.get_columns("pm_presupuesto_partidas")}
        self.assertIn("lineage_id", columns)
        self.assertFalse(columns["lineage_id"]["nullable"])
        self.assertTrue(inspector.has_table("pm_presupuesto_task_links"))
        null_count = self.db.execute(
            text("SELECT COUNT(*) FROM pm_presupuesto_partidas WHERE lineage_id IS NULL OR lineage_id = ''")
        ).scalar_one()
        self.assertEqual(null_count, 0)

        costs = get_project_costs(self.db, pm_context, project_id)
        self.assertIsNotNone(costs)

    def test_repair_stamped_0045_without_lineage_column(self) -> None:
        self._prepare_database(self.template_0044_path)
        company, _user, _pm_context, project, budget = self._seed_company_context(suffix="stamped0045")
        self._insert_budget_item_without_lineage(
            company_id=company.id,
            budget_id=budget.id,
            project_id=project.id,
            codigo="02.01",
            nombre="Partida sin lineage",
        )
        self._stamp_revision("20260805_0045")

        self._upgrade("head")

        inspector = inspect(self.engine)
        self.assertIn("lineage_id", {column["name"] for column in inspector.get_columns("pm_presupuesto_partidas")})
        self.assertTrue(inspector.has_table("pm_presupuesto_task_links"))

    def test_repair_fills_null_lineage_values_and_sets_not_null(self) -> None:
        self._prepare_database(self.template_0044_path)
        company, _user, _pm_context, project, budget = self._seed_company_context(suffix="null-lineage")
        self.db.execute(text("ALTER TABLE pm_presupuesto_partidas ADD COLUMN lineage_id VARCHAR(36)"))
        self.db.commit()
        self._insert_budget_item_with_lineage(
            company_id=company.id,
            budget_id=budget.id,
            project_id=project.id,
            lineage_id=None,
            codigo="03.01",
            nombre="Partida con lineage nulo",
        )
        self._stamp_revision("20260805_0045")

        self._upgrade("head")

        inspector = inspect(self.engine)
        lineage_column = next(column for column in inspector.get_columns("pm_presupuesto_partidas") if column["name"] == "lineage_id")
        self.assertFalse(lineage_column["nullable"])
        null_count = self.db.execute(
            text("SELECT COUNT(*) FROM pm_presupuesto_partidas WHERE lineage_id IS NULL OR lineage_id = ''")
        ).scalar_one()
        self.assertEqual(null_count, 0)

    def test_repair_creates_task_links_table_when_missing(self) -> None:
        self._prepare_database(self.template_0044_path)
        self._stamp_revision("20260805_0045")

        self._upgrade("head")

        inspector = inspect(self.engine)
        self.assertTrue(inspector.has_table("pm_presupuesto_task_links"))
        index_names = {index["name"] for index in inspector.get_indexes("pm_presupuesto_task_links")}
        self.assertIn("uq_pm_presupuesto_task_links_tarea_id_not_null", index_names)

    def test_repair_completes_partial_task_links_table_without_losing_rows(self) -> None:
        self._prepare_database(self.template_0044_path)
        company, _user, _pm_context, project, budget = self._seed_company_context(suffix="partial-links")
        self.db.execute(text("ALTER TABLE pm_presupuesto_partidas ADD COLUMN lineage_id VARCHAR(36)"))
        self.db.commit()

        lineage_id = str(uuid4())
        self._insert_budget_item_with_lineage(
            company_id=company.id,
            budget_id=budget.id,
            project_id=project.id,
            lineage_id=lineage_id,
            codigo="04.01",
            nombre="Partida con enlace parcial",
        )

        self.db.execute(
            text(
                """
                CREATE TABLE pm_presupuesto_task_links (
                    id VARCHAR(36) NOT NULL,
                    empresa_id VARCHAR(36) NOT NULL,
                    proyecto_id VARCHAR(36) NOT NULL,
                    lineage_id VARCHAR(36) NOT NULL,
                    tarea_id VARCHAR(36) NULL
                )
                """
            )
        )
        self.db.execute(
            text(
                """
                INSERT INTO pm_presupuesto_task_links (
                    id,
                    empresa_id,
                    proyecto_id,
                    lineage_id,
                    tarea_id
                ) VALUES (
                    :id,
                    :empresa_id,
                    :proyecto_id,
                    :lineage_id,
                    NULL
                )
                """
            ),
            {
                "id": str(uuid4()),
                "empresa_id": company.id,
                "proyecto_id": project.id,
                "lineage_id": lineage_id,
            },
        )
        self.db.commit()
        self._stamp_revision("20260805_0045")

        self._upgrade("head")

        inspector = inspect(self.engine)
        column_names = {column["name"] for column in inspector.get_columns("pm_presupuesto_task_links")}
        self.assertIn("source_presupuesto_id", column_names)
        self.assertIn("generated_from_budget", column_names)
        self.assertIn("sync_status", column_names)
        row_count = self.db.execute(text("SELECT COUNT(*) FROM pm_presupuesto_task_links")).scalar_one()
        self.assertEqual(row_count, 1)
        generated_value = self.db.execute(
            text("SELECT generated_from_budget, sync_status FROM pm_presupuesto_task_links")
        ).first()
        self.assertEqual(int(generated_value[0]), 0)
        self.assertEqual(generated_value[1], "linked")

    def test_repair_on_correct_0045_schema_keeps_lineage_and_does_not_duplicate_indexes(self) -> None:
        self._prepare_database(self.template_0045_path)
        company, user, pm_context, project, budget = self._seed_company_context(suffix="correct-0045")
        chapter = create_budget_item(
            self.db,
            pm_context,
            budget_id=budget.id,
            parent_id=None,
            codigo="05",
            nombre="Capitulo 5",
            descripcion=None,
            tipo="capitulo",
            unidad=None,
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=None,
            orden=1,
            ip_address=None,
        )
        item = create_budget_item(
            self.db,
            pm_context,
            budget_id=budget.id,
            parent_id=chapter.id,
            codigo="05.01",
            nombre="Partida estable",
            descripcion=None,
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("1000"),
            orden=2,
            ip_address=None,
        )
        original_lineage = item.lineage_id
        self.db.commit()

        self._upgrade("head")

        refreshed = self.db.get(PMPresupuestoPartida, item.id)
        self.assertEqual(refreshed.lineage_id, original_lineage)
        inspector = inspect(self.engine)
        self.assertEqual(
            sum(1 for index in inspector.get_indexes("pm_presupuesto_partidas") if index["name"] == "ix_pm_presupuesto_partidas_lineage_id"),
            1,
        )
        self.assertEqual(
            sum(1 for index in inspector.get_indexes("pm_presupuesto_task_links") if index["name"] == "ix_pm_presupuesto_task_links_lineage_id"),
            1,
        )

    def test_filtered_task_id_index_compiles_for_mssql(self) -> None:
        metadata = sa.MetaData()
        table = sa.Table(
            "pm_presupuesto_task_links",
            metadata,
            sa.Column("tarea_id", sa.String(length=36)),
        )
        index = sa.Index(
            "uq_pm_presupuesto_task_links_tarea_id_not_null",
            table.c.tarea_id,
            unique=True,
            mssql_where=sa.text("tarea_id IS NOT NULL"),
        )
        ddl = str(CreateIndex(index).compile(dialect=mssql.dialect()))
        self.assertIn("WHERE tarea_id IS NOT NULL", ddl)


if __name__ == "__main__":
    unittest.main()
