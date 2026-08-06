from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Empresa, EmpresaUsuario, Plan, Usuario
from app.models.pm import EmpresaPMConfig, PMPresupuesto, PMPresupuestoPartida, PMPresupuestoTaskLink, PMProyecto
from app.services.pm import (
    PMContext,
    create_budget_item,
    get_current_project_budget_row,
    get_project_budget,
    get_project_budget_vs_actual,
    get_project_costs,
    get_project_estimations_summary,
    list_project_estimation_candidates,
)


class PMBudgetCurrentResolutionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend_dir = Path(__file__).resolve().parents[1]
        cls.temp_root = Path(tempfile.mkdtemp(prefix="pm-budget-current-resolution-"))
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

        self.company_a, self.user_a, self.pm_context_a = self._create_company_user_context("alpha", "admin")
        self.company_b, self.user_b, self.pm_context_b = self._create_company_user_context("bravo", "admin")
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

    def _context_for_company(self, empresa_id: str) -> PMContext:
        return self.pm_context_a if empresa_id == self.company_a.id else self.pm_context_b

    def _user_for_company(self, empresa_id: str) -> Usuario:
        return self.user_a if empresa_id == self.company_a.id else self.user_b

    def _create_project(
        self,
        company: Empresa,
        *,
        name: str,
        presupuesto_estimado: Decimal | None = None,
    ) -> PMProyecto:
        user = self._user_for_company(company.id)
        project = PMProyecto(
            empresa_id=company.id,
            nombre=name,
            codigo=None,
            estatus="activo",
            prioridad="media",
            presupuesto_estimado=presupuesto_estimado,
            created_by=user.id,
            updated_by=user.id,
        )
        self.db.add(project)
        self.db.flush()
        return project

    def _create_budget(
        self,
        project: PMProyecto,
        *,
        name: str = "Presupuesto base",
        status_name: str = "borrador",
        version: int = 1,
        active: bool | None = None,
    ) -> PMPresupuesto:
        user = self._user_for_company(project.empresa_id)
        budget = PMPresupuesto(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            nombre=name,
            version=version,
            estatus=status_name,
            moneda="MXN",
            activo=bool(active) if active is not None else status_name != "cancelado",
            aprobado_por=user.id if status_name == "aprobado" else None,
            aprobado_at=datetime.now(timezone.utc) if status_name == "aprobado" else None,
            created_by=user.id,
            updated_by=user.id,
        )
        self.db.add(budget)
        self.db.flush()
        return budget

    def _create_budget_item(
        self,
        budget: PMPresupuesto,
        *,
        parent_id: str | None,
        codigo: str | None,
        nombre: str,
        tipo: str,
        unidad: str | None = None,
        cantidad: Decimal = Decimal("1"),
        precio_unitario_manual: Decimal | None = None,
        orden: int = 0,
    ) -> PMPresupuestoPartida:
        item = create_budget_item(
            self.db,
            self._context_for_company(budget.empresa_id),
            budget_id=budget.id,
            parent_id=parent_id,
            codigo=codigo,
            nombre=nombre,
            descripcion=None,
            tipo=tipo,
            unidad=unidad,
            cantidad=cantidad,
            margen_pct=Decimal("0"),
            precio_unitario_manual=precio_unitario_manual,
            fecha_inicio_sugerida=None,
            fecha_fin_sugerida=None,
            duracion_dias_sugerida=None,
            responsable_sugerido_usuario_id=None,
            notas_planificacion=None,
            orden=orden,
            ip_address=None,
        )
        return self.db.get(PMPresupuestoPartida, item.id)

    def test_reference_only_project_returns_reference_budget_context(self) -> None:
        project = self._create_project(self.company_a, name="Solo referencia", presupuesto_estimado=Decimal("1096"))

        bundle = get_project_budget(self.db, self.pm_context_a, project.id)
        costs = get_project_costs(self.db, self.pm_context_a, project.id)
        vs_actual = get_project_budget_vs_actual(self.db, self.pm_context_a, project.id)

        self.assertIsNone(bundle.budget)
        self.assertFalse(bundle.budget_context.has_detailed_budget)
        self.assertEqual(bundle.budget_context.budget_source, "project_estimate")
        self.assertEqual(bundle.budget_context.reference_budget, Decimal("1096.00"))
        self.assertEqual(costs.budget_context.budget_source, "project_estimate")
        self.assertIsNone(costs.budget_context.budget_id)
        self.assertEqual(vs_actual.reference_budget, Decimal("1096.00"))
        self.assertEqual(vs_actual.presupuesto_detallado_costo, Decimal("0"))

    def test_draft_budget_exposes_consistent_context_and_estimation_readiness(self) -> None:
        project = self._create_project(self.company_a, name="Borrador operativo", presupuesto_estimado=Decimal("500"))
        budget = self._create_budget(project, status_name="borrador", version=1)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Acabados", tipo="capitulo", orden=1)
        self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.01",
            nombre="Yeso",
            tipo="partida",
            unidad="m2",
            cantidad=Decimal("2"),
            precio_unitario_manual=Decimal("250"),
            orden=2,
        )

        bundle = get_project_budget(self.db, self.pm_context_a, project.id)
        summary = get_project_estimations_summary(self.db, self.pm_context_a, project_id=project.id)
        candidates = list_project_estimation_candidates(self.db, self.pm_context_a, project_id=project.id)

        self.assertIsNotNone(bundle.budget)
        self.assertEqual(bundle.budget.id, budget.id)
        self.assertTrue(bundle.budget_context.has_detailed_budget)
        self.assertEqual(bundle.budget_context.budget_status, "borrador")
        self.assertTrue(bundle.budget_context.has_active_items)
        self.assertEqual(summary.budget_context.budget_id, budget.id)
        self.assertEqual(summary.estimation_state, "borrador")
        self.assertTrue(summary.can_create_estimations)
        self.assertEqual(len(candidates), 1)

    def test_approved_budget_is_preferred_over_newer_draft(self) -> None:
        project = self._create_project(self.company_a, name="Versionado", presupuesto_estimado=Decimal("100"))
        approved_budget = self._create_budget(project, name="Aprobado", status_name="borrador", version=1)
        draft_budget = self._create_budget(project, name="Borrador nuevo", status_name="borrador", version=2)
        approved_chapter = self._create_budget_item(approved_budget, parent_id=None, codigo="01", nombre="Base", tipo="capitulo", orden=1)
        self._create_budget_item(
            approved_budget,
            parent_id=approved_chapter.id,
            codigo="01.01",
            nombre="Partida aprobada",
            tipo="partida",
            unidad="pz",
            cantidad=Decimal("1"),
            precio_unitario_manual=Decimal("100"),
            orden=2,
        )
        approved_budget.estatus = "aprobado"
        approved_budget.aprobado_por = self.user_a.id
        approved_budget.aprobado_at = datetime.now(timezone.utc)
        draft_chapter = self._create_budget_item(draft_budget, parent_id=None, codigo="02", nombre="Cambio", tipo="capitulo", orden=1)
        self._create_budget_item(
            draft_budget,
            parent_id=draft_chapter.id,
            codigo="02.01",
            nombre="Partida borrador",
            tipo="partida",
            unidad="pz",
            cantidad=Decimal("1"),
            precio_unitario_manual=Decimal("200"),
            orden=2,
        )

        resolved = get_current_project_budget_row(self.db, self.company_a.id, project.id)
        bundle = get_project_budget(self.db, self.pm_context_a, project.id)

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, approved_budget.id)
        self.assertEqual(bundle.budget.id, approved_budget.id)
        self.assertTrue(bundle.budget_context.is_approved)
        self.assertEqual(bundle.budget_context.budget_status, "aprobado")

    def test_cancelled_budget_is_ignored(self) -> None:
        project = self._create_project(self.company_a, name="Cancelado", presupuesto_estimado=Decimal("700"))
        self._create_budget(project, status_name="cancelado", version=1, active=False)

        resolved = get_current_project_budget_row(self.db, self.company_a.id, project.id)
        bundle = get_project_budget(self.db, self.pm_context_a, project.id)

        self.assertIsNone(resolved)
        self.assertFalse(bundle.budget_context.has_detailed_budget)
        self.assertEqual(bundle.budget_context.budget_source, "project_estimate")

    def test_estimations_without_active_items_report_sin_partidas(self) -> None:
        project = self._create_project(self.company_a, name="Sin partidas")
        budget = self._create_budget(project, status_name="borrador", version=1)

        summary = get_project_estimations_summary(self.db, self.pm_context_a, project_id=project.id)
        candidates = list_project_estimation_candidates(self.db, self.pm_context_a, project_id=project.id)

        self.assertEqual(summary.budget_context.budget_id, budget.id)
        self.assertTrue(summary.budget_context.has_detailed_budget)
        self.assertFalse(summary.budget_context.has_active_items)
        self.assertEqual(summary.estimation_state, "sin_partidas")
        self.assertFalse(summary.can_create_estimations)
        self.assertEqual(candidates, [])

    def test_costs_budget_and_vs_actual_share_same_budget_id(self) -> None:
        project = self._create_project(self.company_a, name="Consistente")
        budget = self._create_budget(project, status_name="borrador", version=1)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Base", tipo="capitulo", orden=1)
        self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.01",
            nombre="Partida",
            tipo="partida",
            unidad="pz",
            cantidad=Decimal("3"),
            precio_unitario_manual=Decimal("50"),
            orden=2,
        )
        budget.estatus = "aprobado"
        budget.aprobado_por = self.user_a.id
        budget.aprobado_at = datetime.now(timezone.utc)

        bundle = get_project_budget(self.db, self.pm_context_a, project.id)
        costs = get_project_costs(self.db, self.pm_context_a, project.id)
        vs_actual = get_project_budget_vs_actual(self.db, self.pm_context_a, project.id)

        self.assertEqual(bundle.budget_context.budget_id, budget.id)
        self.assertEqual(costs.budget_context.budget_id, budget.id)
        self.assertEqual(vs_actual.presupuesto_id, budget.id)

    def test_budget_queries_do_not_create_new_budget_rows_or_links(self) -> None:
        project = self._create_project(self.company_a, name="Sin side effects")
        budget = self._create_budget(project, status_name="borrador", version=1)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Base", tipo="capitulo", orden=1)
        self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.01",
            nombre="Partida",
            tipo="partida",
            unidad="pz",
            cantidad=Decimal("1"),
            precio_unitario_manual=Decimal("90"),
            orden=2,
        )
        before_counts = (
            self.db.scalar(select(func.count(PMPresupuesto.id))) or 0,
            self.db.scalar(select(func.count(PMPresupuestoPartida.id))) or 0,
            self.db.scalar(select(func.count(PMPresupuestoTaskLink.id))) or 0,
        )

        get_project_budget(self.db, self.pm_context_a, project.id)
        get_project_costs(self.db, self.pm_context_a, project.id)
        get_project_budget_vs_actual(self.db, self.pm_context_a, project.id)
        get_project_estimations_summary(self.db, self.pm_context_a, project_id=project.id)

        after_counts = (
            self.db.scalar(select(func.count(PMPresupuesto.id))) or 0,
            self.db.scalar(select(func.count(PMPresupuestoPartida.id))) or 0,
            self.db.scalar(select(func.count(PMPresupuestoTaskLink.id))) or 0,
        )
        self.assertEqual(before_counts, after_counts)


if __name__ == "__main__":
    unittest.main()
