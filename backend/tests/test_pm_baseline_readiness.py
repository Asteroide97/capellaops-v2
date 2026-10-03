from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Empresa, EmpresaUsuario, Plan, Usuario
from app.models.pm import (
    EmpresaPMConfig,
    PMPresupuesto,
    PMPresupuestoPartida,
    PMPresupuestoTaskLink,
    PMProyecto,
    PMProyectoLineaBase,
    PMTarea,
    PMTareaDependencia,
)
from app.services.pm import (
    PMContext,
    create_project_baseline,
    get_project_baseline_readiness,
    get_project_baseline_vs_actual,
)


class PMBaselineReadinessTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend_dir = Path(__file__).resolve().parents[1]
        cls.temp_root = Path(tempfile.mkdtemp(prefix="pm-baseline-readiness-"))
        cls.template_db_path = cls.temp_root / "template.db"
        env = dict(os.environ)
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
            raise RuntimeError(f"Alembic template upgrade failed:\n{result.stdout}\n{result.stderr}")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temp_root, ignore_errors=True)

    def setUp(self) -> None:
        self.db_path = self.temp_root / f"{self._testMethodName}.db"
        shutil.copyfile(self.template_db_path, self.db_path)
        self.engine = create_engine(f"sqlite:///{self.db_path.as_posix()}", future=True)

        @event.listens_for(self.engine, "connect")
        def _enable_sqlite_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, class_=Session)
        self.db = self.SessionLocal()
        self.plan = Plan(code="basic", name="Basic", modules=["pm"])
        self.db.add(self.plan)
        self.db.flush()
        self.company_a, self.user_a, self.context_a = self._company_context("alpha")
        self.company_b, self.user_b, self.context_b = self._company_context("bravo")
        self.project = self._project(self.company_a, "Proyecto Alpha")
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        if self.db_path.exists():
            self.db_path.unlink()

    def _company_context(self, slug: str):
        company = Empresa(
            name=f"Empresa {slug}",
            slug=slug,
            plan_code=self.plan.code,
            access_status="active",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        user = Usuario(email=f"{slug}@example.com", full_name=f"Usuario {slug}", password_hash="hash", is_active=True)
        self.db.add_all([company, user])
        self.db.flush()
        membership = EmpresaUsuario(empresa_id=company.id, usuario_id=user.id, role="admin", is_active=True)
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
        return company, user, PMContext(user=user, empresa_id=company.id, membership_role="admin", config=config)

    def _project(self, company: Empresa, name: str) -> PMProyecto:
        project = PMProyecto(
            empresa_id=company.id,
            nombre=name,
            estatus="activo",
            prioridad="media",
            created_by=self.user_a.id if hasattr(self, "user_a") else None,
        )
        self.db.add(project)
        self.db.flush()
        return project

    def _budget(self, status_name: str = "aprobado") -> PMPresupuesto:
        budget = PMPresupuesto(
            empresa_id=self.company_a.id,
            proyecto_id=self.project.id,
            nombre="Presupuesto operativo",
            version=3,
            estatus=status_name,
            moneda="MXN",
            subtotal_costo=Decimal("800"),
            subtotal_venta=Decimal("1200"),
            total_costo=Decimal("800"),
            total_venta=Decimal("1200"),
            margen_estimado=Decimal("400"),
            activo=status_name != "cancelado",
            created_by=self.user_a.id,
            updated_by=self.user_a.id,
        )
        self.db.add(budget)
        self.db.flush()
        return budget

    def _task(
        self,
        project: PMProyecto | None = None,
        *,
        title: str = "Instalación",
        start: date | None = date(2026, 7, 1),
        end: date | None = date(2026, 7, 3),
        responsible: str | None = None,
        progress: Decimal = Decimal("25"),
    ) -> PMTarea:
        project = project or self.project
        task = PMTarea(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            titulo=title,
            estatus="pendiente",
            prioridad="media",
            fecha_inicio=start,
            fecha_vencimiento=end,
            asignado_user_id=responsible,
            porcentaje_avance=progress,
            estimacion_horas=Decimal("8"),
            orden=1,
            activo=True,
            created_by=self.user_a.id if project.empresa_id == self.company_a.id else self.user_b.id,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _readiness(self):
        return get_project_baseline_readiness(self.db, self.context_a, project_id=self.project.id)

    def _create_baseline(self, readiness, name="Línea base inicial"):
        return create_project_baseline(
            self.db,
            self.context_a,
            project_id=self.project.id,
            nombre=name,
            descripcion=None,
            es_principal=True,
            confirm=True,
            expected_readiness_token=readiness.readiness_token,
            confirm_presupuesto_borrador=False,
            ip_address=None,
        )

    def test_missing_tasks_dates_and_budget_are_blockers(self) -> None:
        readiness = self._readiness()
        self.assertEqual(
            self.db.scalar(select(PMProyectoLineaBase.id).where(PMProyectoLineaBase.proyecto_id == self.project.id)),
            None,
        )
        self.assertIn("tasks_missing", {issue.code for issue in readiness.blocking_issues})
        self.assertIn("budget_missing", {issue.code for issue in readiness.blocking_issues})

        self._task(start=None)
        readiness = self._readiness()
        self.assertIn("task_missing_dates", {issue.code for issue in readiness.blocking_issues})
        self.db.query(PMTarea).filter(PMTarea.proyecto_id == self.project.id).delete()
        self._task(end=None)
        self.assertIn("task_missing_dates", {issue.code for issue in self._readiness().blocking_issues})

    def test_responsible_is_warning_and_draft_budget_requires_confirmation(self) -> None:
        self._budget("borrador")
        task = self._task()
        readiness = self._readiness()
        codes = {issue.code for issue in readiness.warnings}
        self.assertIn("task_without_responsible", codes)
        self.assertIn("budget_draft", codes)
        self.assertTrue(readiness.ready)

        with self.assertRaises(HTTPException) as raised:
            self._create_baseline(readiness)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("presupuesto está en borrador", raised.exception.detail)

        created = create_project_baseline(
            self.db,
            self.context_a,
            project_id=self.project.id,
            nombre="Base confirmada",
            descripcion=None,
            es_principal=True,
            confirm=True,
            expected_readiness_token=readiness.readiness_token,
            confirm_presupuesto_borrador=True,
            ip_address=None,
        )
        self.assertEqual(created.tasks[0].tarea_id, task.id)

    def test_cancelled_budget_invalid_dates_and_invalid_dependencies_block(self) -> None:
        cancelled = self._budget("cancelado")
        self._task(start=date(2026, 7, 5), end=date(2026, 7, 1))
        readiness = self._readiness()
        codes = {issue.code for issue in readiness.blocking_issues}
        self.assertIn("budget_cancelled", codes)
        self.assertIn("task_invalid_dates", codes)

        other_project = self._project(self.company_a, "Otro proyecto")
        other_task = self._task(other_project, title="Fuera del proyecto")
        task = self.db.scalar(select(PMTarea).where(PMTarea.proyecto_id == self.project.id))
        self.db.add(PMTareaDependencia(
            empresa_id=self.company_a.id,
            proyecto_id=self.project.id,
            tarea_id=task.id,
            depende_de_tarea_id=other_task.id,
            tipo_dependencia="finish_to_start",
            lag_dias=0,
            bloqueante=True,
            activo=True,
            created_by=self.user_a.id,
        ))
        self.db.flush()
        self.assertIn("dependency_invalid", {issue.code for issue in self._readiness().blocking_issues})
        self.assertIsNotNone(cancelled.id)

    def test_dependency_cycle_and_budget_link_conflict_block(self) -> None:
        budget = self._budget("aprobado")
        task_a = self._task(title="A")
        task_b = self._task(title="B")
        for task, prerequisite in ((task_a, task_b), (task_b, task_a)):
            self.db.add(PMTareaDependencia(
                empresa_id=self.company_a.id,
                proyecto_id=self.project.id,
                tarea_id=task.id,
                depende_de_tarea_id=prerequisite.id,
                tipo_dependencia="finish_to_start",
                lag_dias=0,
                bloqueante=True,
                activo=True,
                created_by=self.user_a.id,
            ))
        item = PMPresupuestoPartida(
            empresa_id=self.company_a.id,
            presupuesto_id=budget.id,
            proyecto_id=self.project.id,
            nombre="Partida",
            tipo="partida",
            cantidad=Decimal("1"),
            costo_unitario=Decimal("10"),
            precio_unitario=Decimal("15"),
            subtotal_costo=Decimal("10"),
            subtotal_venta=Decimal("15"),
            margen_pct=Decimal("50"),
            orden=1,
            activo=True,
        )
        self.db.add(item)
        self.db.flush()
        self.db.add(PMPresupuestoTaskLink(
            empresa_id=self.company_a.id,
            proyecto_id=self.project.id,
            lineage_id=item.lineage_id,
            tarea_id=task_a.id,
            source_presupuesto_id=budget.id,
            source_partida_id=item.id,
            generated_from_budget=True,
            sync_status="conflict",
        ))
        self.db.flush()
        codes = {issue.code for issue in self._readiness().blocking_issues}
        self.assertIn("dependency_cycle", codes)
        self.assertIn("budget_link_conflict", codes)

    def test_approved_budget_and_valid_dates_are_ready_with_manual_task_warning(self) -> None:
        self._budget("aprobado")
        task = self._task()
        readiness = self._readiness()
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.summary.total_tasks, 1)
        self.assertEqual(readiness.summary.tasks_without_dates, 0)
        self.assertIn("manual_task_without_budget", {issue.code for issue in readiness.warnings})
        self.assertEqual(readiness.budget_context.budget_version, 3)
        self.assertEqual(readiness.budget_context.planned_cost, Decimal("800.00"))
        self.assertEqual(readiness.budget_context.planned_sale, Decimal("1200.00"))
        self.assertEqual(task.fecha_inicio, date(2026, 7, 1))

    def test_readiness_token_is_stable_and_tracks_tasks_dependencies_and_budget(self) -> None:
        self._budget("aprobado")
        task_a = self._task(title="A")
        task_b = self._task(title="B")
        first = self._readiness().readiness_token
        self.assertEqual(first, self._readiness().readiness_token)
        task_a.fecha_inicio = date(2026, 7, 2)
        self.db.flush()
        after_date = self._readiness().readiness_token
        self.assertNotEqual(first, after_date)
        self.db.add(PMTareaDependencia(
            empresa_id=self.company_a.id,
            proyecto_id=self.project.id,
            tarea_id=task_b.id,
            depende_de_tarea_id=task_a.id,
            tipo_dependencia="finish_to_start",
            lag_dias=0,
            bloqueante=True,
            activo=True,
            created_by=self.user_a.id,
        ))
        self.db.flush()
        after_dependency = self._readiness().readiness_token
        self.assertNotEqual(after_date, after_dependency)
        budget = self.db.scalar(select(PMPresupuesto).where(PMPresupuesto.proyecto_id == self.project.id))
        budget.version += 1
        budget.total_costo = Decimal("801")
        self.db.flush()
        self.assertNotEqual(after_dependency, self._readiness().readiness_token)

    def test_creation_rejects_stale_token_and_blockers_without_mutating_plan(self) -> None:
        self._budget("aprobado")
        task = self._task()
        readiness = self._readiness()
        task_before = (task.fecha_inicio, task.fecha_vencimiento, task.porcentaje_avance)
        budget = self.db.scalar(select(PMPresupuesto).where(PMPresupuesto.proyecto_id == self.project.id))
        budget_before = (budget.version, budget.estatus, budget.total_costo, budget.total_venta)
        task.fecha_inicio = date(2026, 7, 2)
        self.db.flush()
        with self.assertRaises(HTTPException) as stale:
            self._create_baseline(readiness)
        self.assertEqual(stale.exception.status_code, 409)
        self.assertIn("El plan cambió", stale.exception.detail)

        fresh = self._readiness()
        task.fecha_vencimiento = None
        self.db.flush()
        with self.assertRaises(HTTPException) as blocked:
            self._create_baseline(fresh)
        self.assertEqual(blocked.exception.status_code, 409)
        self.assertEqual(task_before[2], task.porcentaje_avance)
        self.assertEqual(budget_before, (budget.version, budget.estatus, budget.total_costo, budget.total_venta))

    def test_snapshot_is_complete_idempotent_history_and_comparison_still_works(self) -> None:
        budget = self._budget("aprobado")
        task = self._task(responsible=self.user_a.id)
        readiness = self._readiness()
        task_state = (task.fecha_inicio, task.fecha_vencimiento, task.estatus, task.porcentaje_avance)
        budget_state = (budget.version, budget.estatus, budget.total_costo, budget.total_venta)
        created = self._create_baseline(readiness)
        snapshot = created.snapshot_json
        self.assertEqual(snapshot["budget_reference"]["budget_id"], budget.id)
        self.assertEqual(snapshot["budget_reference"]["budget_version"], 3)
        self.assertEqual(snapshot["operational"]["tasks"][0]["task_id"], task.id)
        self.assertEqual(snapshot["operational"]["tasks"][0]["responsible_user_id"], self.user_a.id)
        self.assertIn("calendar", snapshot["operational"])
        self.assertEqual(task_state, (task.fecha_inicio, task.fecha_vencimiento, task.estatus, task.porcentaje_avance))
        self.assertEqual(budget_state, (budget.version, budget.estatus, budget.total_costo, budget.total_venta))

        duplicate = self._create_baseline(readiness, name="Doble submit")
        self.assertEqual(created.id, duplicate.id)
        task.porcentaje_avance = Decimal("30")
        self.db.flush()
        next_readiness = self._readiness()
        second = self._create_baseline(next_readiness, name="Línea base posterior")
        self.assertNotEqual(created.id, second.id)
        self.assertEqual(second.version, created.version + 1)
        comparison = get_project_baseline_vs_actual(self.db, self.context_a, project_id=self.project.id)
        self.assertEqual(comparison.baseline.id, second.id)

    def test_cross_tenant_readiness_and_creation_are_rejected(self) -> None:
        project_b = self._project(self.company_b, "Proyecto Bravo")
        with self.assertRaises(HTTPException) as raised:
            get_project_baseline_readiness(self.db, self.context_a, project_id=project_b.id)
        self.assertEqual(raised.exception.status_code, 404)
        with self.assertRaises(HTTPException) as create_raised:
            create_project_baseline(
                self.db,
                self.context_a,
                project_id=project_b.id,
                nombre="No autorizado",
                descripcion=None,
                es_principal=True,
                confirm=True,
                expected_readiness_token="0" * 64,
                confirm_presupuesto_borrador=False,
                ip_address=None,
            )
        self.assertEqual(create_raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
