from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Empresa, EmpresaUsuario, Plan, Usuario
from app.models.pm import EmpresaPMConfig, PMPresupuesto, PMPresupuestoTaskLink, PMProyecto, PMTarea
from app.services.pm import (
    PMContext,
    build_budget_item_record,
    create_budget_item,
    create_budget_task_link,
    create_project_budget,
    get_budget_task_link_by_project_lineage,
    get_budget_task_link_by_task,
    list_project_tasks_for_planning,
    update_budget_item,
)


class PMBudgetLineageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend_dir = Path(__file__).resolve().parents[1]
        cls.temp_root = Path(tempfile.mkdtemp(prefix="pm-budget-lineage-"))
        cls.template_db_path = cls.temp_root / "template.db"
        env = dict(__import__("os").environ)
        env["DATABASE_URL"] = f"sqlite:///{cls.template_db_path.as_posix()}"
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=cls.backend_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Alembic template upgrade failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temp_root, ignore_errors=True)

    def setUp(self) -> None:
        self.db_path = self.temp_root / f"{self._testMethodName}.db"
        shutil.copyfile(self.template_db_path, self.db_path)
        self.engine = create_engine(f"sqlite:///{self.db_path.as_posix()}", future=True)

        @event.listens_for(self.engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, class_=Session)
        self.db = self.SessionLocal()

        self.plan = Plan(code="basic", name="Basic", modules=["pm"])
        self.db.add(self.plan)
        self.db.flush()

        (
            self.company_a,
            self.user_a,
            self.pm_context_a,
        ) = self._create_company_user_context("alpha", "admin")
        (
            self.company_b,
            self.user_b,
            self.pm_context_b,
        ) = self._create_company_user_context("bravo", "admin")
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_company_user_context(self, slug_suffix: str, role: str) -> tuple[Empresa, Usuario, PMContext]:
        company = Empresa(
            name=f"Empresa {slug_suffix}",
            slug=f"empresa-{slug_suffix}",
            plan_code=self.plan.code,
            access_status="active",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        user = Usuario(
            email=f"{slug_suffix}@example.com",
            full_name=f"User {slug_suffix}",
            password_hash="hash",
            is_active=True,
            is_superadmin=False,
        )
        self.db.add_all([company, user])
        self.db.flush()
        membership = EmpresaUsuario(
            empresa_id=company.id,
            usuario_id=user.id,
            role=role,
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
        self.db.add_all([membership, config])
        self.db.flush()
        return company, user, PMContext(user=user, empresa_id=company.id, membership_role=role, config=config)

    def _create_project(self, company: Empresa, *, name: str, user: Usuario) -> PMProyecto:
        project = PMProyecto(
            empresa_id=company.id,
            nombre=name,
            codigo=None,
            estatus="activo",
            prioridad="media",
            created_by=user.id,
            updated_by=user.id,
        )
        self.db.add(project)
        self.db.flush()
        return project

    def _create_budget(self, project: PMProyecto, *, name: str = "Presupuesto base") -> PMPresupuesto:
        budget = PMPresupuesto(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            nombre=name,
            version=1,
            estatus="borrador",
            moneda="MXN",
            activo=True,
        )
        self.db.add(budget)
        self.db.flush()
        return budget

    def _create_task(self, project: PMProyecto, *, title: str) -> PMTarea:
        task = PMTarea(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            titulo=title,
            estatus="pendiente",
            prioridad="media",
            activo=True,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def test_create_budget_item_generates_lineage_for_chapter_and_partida(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Uno", user=self.user_a)
        budget = create_project_budget(
            self.db,
            self.pm_context_a,
            project_id=project.id,
            nombre="Presupuesto principal",
            moneda="MXN",
            indirectos_pct=Decimal("0"),
            notas=None,
            ip_address=None,
        )
        chapter = create_budget_item(
            self.db,
            self.pm_context_a,
            budget_id=budget.id,
            parent_id=None,
            codigo="CAP-1",
            nombre="Capitulo 1",
            descripcion=None,
            tipo="capitulo",
            unidad=None,
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=None,
            orden=1,
            ip_address=None,
        )
        partida = create_budget_item(
            self.db,
            self.pm_context_a,
            budget_id=budget.id,
            parent_id=chapter.id,
            codigo="PART-1",
            nombre="Partida 1",
            descripcion="Trabajo base",
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("2"),
            margen_pct=Decimal("15"),
            precio_unitario_manual=Decimal("1250"),
            orden=2,
            ip_address=None,
        )

        self.assertTrue(chapter.lineage_id)
        self.assertTrue(partida.lineage_id)
        self.assertNotEqual(chapter.lineage_id, partida.lineage_id)

    def test_update_budget_item_preserves_lineage_and_budget_flow(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Dos", user=self.user_a)
        budget = create_project_budget(
            self.db,
            self.pm_context_a,
            project_id=project.id,
            nombre="Presupuesto flujo",
            moneda="MXN",
            indirectos_pct=Decimal("0"),
            notas=None,
            ip_address=None,
        )
        partida = create_budget_item(
            self.db,
            self.pm_context_a,
            budget_id=budget.id,
            parent_id=None,
            codigo="P-100",
            nombre="Partida actualizable",
            descripcion=None,
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("1"),
            margen_pct=Decimal("10"),
            precio_unitario_manual=Decimal("1000"),
            orden=1,
            ip_address=None,
        )
        original_lineage = partida.lineage_id

        updated = update_budget_item(
            self.db,
            self.pm_context_a,
            item_id=partida.id,
            parent_id=partida.parent_id,
            codigo="P-100A",
            nombre="Partida actualizada",
            descripcion="Actualizada",
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("3"),
            margen_pct=Decimal("12"),
            precio_unitario_manual=Decimal("1500"),
            orden=3,
            activo=True,
            ip_address=None,
        )

        self.assertEqual(updated.lineage_id, original_lineage)
        self.assertEqual(updated.nombre, "Partida actualizada")
        self.assertEqual(updated.cantidad, Decimal("3"))

    def test_duplicate_lineage_rejected_within_same_budget(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Tres", user=self.user_a)
        budget = self._create_budget(project)
        lineage_id = "11111111-1111-1111-1111-111111111111"
        item_a = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="A",
            nombre="Partida A",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("10"),
            orden=1,
            lineage_id=lineage_id,
        )
        item_b = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="B",
            nombre="Partida B",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("20"),
            orden=2,
            lineage_id=lineage_id,
        )
        self.db.add_all([item_a, item_b])
        with self.assertRaises(IntegrityError):
            self.db.flush()
        self.db.rollback()

    def test_same_lineage_allowed_in_different_budgets(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Cuatro", user=self.user_a)
        budget_v1 = self._create_budget(project, name="V1")
        budget_v2 = PMPresupuesto(
            empresa_id=self.company_a.id,
            proyecto_id=project.id,
            nombre="V2",
            version=2,
            estatus="borrador",
            moneda="MXN",
            activo=True,
        )
        self.db.add(budget_v2)
        self.db.flush()
        lineage_id = "22222222-2222-2222-2222-222222222222"
        item_v1 = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget_v1.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="A",
            nombre="Partida V1",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("10"),
            orden=1,
            lineage_id=lineage_id,
        )
        item_v2 = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget_v2.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="A",
            nombre="Partida V2",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("15"),
            orden=1,
            lineage_id=lineage_id,
        )
        self.db.add_all([item_v1, item_v2])
        self.db.flush()

        self.assertEqual(item_v1.lineage_id, item_v2.lineage_id)

    def test_create_valid_budget_task_link_and_lookup(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Cinco", user=self.user_a)
        budget = self._create_budget(project)
        chapter = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="CAP",
            nombre="Capitulo",
            descripcion=None,
            tipo="capitulo",
            unidad=None,
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=None,
            orden=1,
        )
        self.db.add(chapter)
        self.db.flush()
        partida = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=chapter.id,
            codigo="PART",
            nombre="Partida vinculada",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("100"),
            orden=2,
        )
        task = self._create_task(project, title="Tarea vinculada")
        self.db.add(partida)
        self.db.flush()

        link = create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=partida.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=partida.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="linked",
        )

        self.assertEqual(link.source_partida_id, partida.id)
        self.assertEqual(link.tarea_id, task.id)
        self.assertTrue(link.source_hash)
        self.assertEqual(
            get_budget_task_link_by_project_lineage(
                self.db,
                empresa_id=self.company_a.id,
                project_id=project.id,
                lineage_id=partida.lineage_id,
            ).id,
            link.id,
        )
        self.assertEqual(
            get_budget_task_link_by_task(
                self.db,
                empresa_id=self.company_a.id,
                task_id=task.id,
            ).id,
            link.id,
        )

    def test_reject_duplicate_task_link(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Seis", user=self.user_a)
        budget = self._create_budget(project)
        task = self._create_task(project, title="Tarea unica")
        partida_a = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="A",
            nombre="Partida A",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("10"),
            orden=1,
        )
        partida_b = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="B",
            nombre="Partida B",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("20"),
            orden=2,
        )
        self.db.add_all([partida_a, partida_b])
        self.db.flush()

        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=partida_a.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=partida_a.id,
            sync_status="linked",
        )
        with self.assertRaises(HTTPException) as exc:
            create_budget_task_link(
                self.db,
                empresa_id=self.company_a.id,
                project_id=project.id,
                lineage_id=partida_b.lineage_id,
                tarea_id=task.id,
                source_presupuesto_id=budget.id,
                source_partida_id=partida_b.id,
                sync_status="linked",
            )
        self.assertEqual(exc.exception.status_code, 409)

    def test_multiple_links_can_keep_nullable_history_fields_null(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Seis B", user=self.user_a)
        budget = self._create_budget(project)
        chapter_a = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="CA",
            nombre="Capitulo A",
            descripcion=None,
            tipo="capitulo",
            unidad=None,
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=None,
            orden=1,
        )
        chapter_b = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="CB",
            nombre="Capitulo B",
            descripcion=None,
            tipo="capitulo",
            unidad=None,
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=None,
            orden=2,
        )
        self.db.add_all([chapter_a, chapter_b])
        self.db.flush()
        partida_a = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=chapter_a.id,
            codigo="PA",
            nombre="Partida A",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("10"),
            orden=3,
        )
        partida_b = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=chapter_b.id,
            codigo="PB",
            nombre="Partida B",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("20"),
            orden=4,
        )
        task_a = self._create_task(project, title="Tarea A")
        task_b = self._create_task(project, title="Tarea B")
        self.db.add_all([partida_a, partida_b])
        self.db.flush()

        link_a = create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=partida_a.lineage_id,
            tarea_id=task_a.id,
            source_presupuesto_id=budget.id,
            source_partida_id=partida_a.id,
            source_capitulo_id=chapter_a.id,
            sync_status="linked",
        )
        link_b = create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=partida_b.lineage_id,
            tarea_id=task_b.id,
            source_presupuesto_id=budget.id,
            source_partida_id=partida_b.id,
            source_capitulo_id=chapter_b.id,
            sync_status="linked",
        )

        link_a.tarea_id = None
        link_b.tarea_id = None
        link_a.source_partida_id = None
        link_b.source_partida_id = None
        link_a.source_capitulo_id = None
        link_b.source_capitulo_id = None
        self.db.flush()

        rows = (
            self.db.query(PMPresupuestoTaskLink)
            .filter(PMPresupuestoTaskLink.proyecto_id == project.id)
            .order_by(PMPresupuestoTaskLink.id.asc())
            .all()
        )

        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.tarea_id is None for row in rows))
        self.assertTrue(all(row.source_partida_id is None for row in rows))
        self.assertTrue(all(row.source_capitulo_id is None for row in rows))

    def test_reject_duplicate_project_lineage_link(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Siete", user=self.user_a)
        budget = self._create_budget(project)
        partida = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="LINE",
            nombre="Partida",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("10"),
            orden=1,
        )
        task_a = self._create_task(project, title="Tarea A")
        task_b = self._create_task(project, title="Tarea B")
        self.db.add(partida)
        self.db.flush()

        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=partida.lineage_id,
            tarea_id=task_a.id,
            source_presupuesto_id=budget.id,
            source_partida_id=partida.id,
            sync_status="linked",
        )
        with self.assertRaises(HTTPException) as exc:
            create_budget_task_link(
                self.db,
                empresa_id=self.company_a.id,
                project_id=project.id,
                lineage_id=partida.lineage_id,
                tarea_id=task_b.id,
                source_presupuesto_id=budget.id,
                source_partida_id=partida.id,
                sync_status="linked",
            )
        self.assertEqual(exc.exception.status_code, 409)

    def test_reject_cross_company_and_cross_project_links(self) -> None:
        project_a = self._create_project(self.company_a, name="Proyecto Ocho A", user=self.user_a)
        project_b = self._create_project(self.company_a, name="Proyecto Ocho B", user=self.user_a)
        budget_a = self._create_budget(project_a)
        budget_b = self._create_budget(project_b)
        partida_b = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget_b.id,
            proyecto_id=project_b.id,
            parent_id=None,
            codigo="PB",
            nombre="Partida B",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("10"),
            orden=1,
        )
        project_other_company = self._create_project(self.company_b, name="Proyecto Empresa B", user=self.user_b)
        budget_other_company = self._create_budget(project_other_company)
        partida_other_company = build_budget_item_record(
            empresa_id=self.company_b.id,
            presupuesto_id=budget_other_company.id,
            proyecto_id=project_other_company.id,
            parent_id=None,
            codigo="PO",
            nombre="Partida externa",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("10"),
            orden=1,
        )
        task_a = self._create_task(project_a, title="Tarea A")
        task_other_company = self._create_task(project_other_company, title="Tarea externa")
        self.db.add_all([partida_b, partida_other_company])
        self.db.flush()

        with self.assertRaises(HTTPException) as exc_project:
            create_budget_task_link(
                self.db,
                empresa_id=self.company_a.id,
                project_id=project_a.id,
                lineage_id=partida_b.lineage_id,
                tarea_id=task_a.id,
                source_presupuesto_id=budget_a.id,
                source_partida_id=partida_b.id,
                sync_status="linked",
            )
        self.assertEqual(exc_project.exception.status_code, 400)

        with self.assertRaises(HTTPException) as exc_company:
            create_budget_task_link(
                self.db,
                empresa_id=self.company_a.id,
                project_id=project_a.id,
                lineage_id=partida_other_company.lineage_id,
                tarea_id=task_other_company.id,
                source_presupuesto_id=budget_a.id,
                source_partida_id=partida_other_company.id,
                sync_status="linked",
            )
        self.assertIn(exc_company.exception.status_code, {400, 404})

    def test_manual_tasks_without_link_still_work_in_planning(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Nueve", user=self.user_a)
        manual_task = self._create_task(project, title="Manual sin vinculo")
        linked_task = self._create_task(project, title="Tarea vinculable")
        budget = self._create_budget(project)
        partida = build_budget_item_record(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=project.id,
            parent_id=None,
            codigo="PV",
            nombre="Partida vinculable",
            descripcion=None,
            tipo="partida",
            unidad="pieza",
            cantidad=Decimal("1"),
            margen_pct=Decimal("0"),
            precio_unitario_manual=Decimal("10"),
            orden=1,
        )
        self.db.add(partida)
        self.db.flush()
        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=partida.lineage_id,
            tarea_id=linked_task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=partida.id,
            sync_status="linked",
        )

        tasks = list_project_tasks_for_planning(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
        )
        task_ids = {task.id for task in tasks}

        self.assertIn(manual_task.id, task_ids)
        self.assertIn(linked_task.id, task_ids)
        self.assertIsNone(
            get_budget_task_link_by_task(
                self.db,
                empresa_id=self.company_a.id,
                task_id=manual_task.id,
            )
        )


if __name__ == "__main__":
    unittest.main()
