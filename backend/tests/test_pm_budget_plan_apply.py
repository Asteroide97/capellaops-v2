from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditLog, Empresa, EmpresaUsuario, Plan, Usuario
from app.models.pm import (
    EmpresaPMConfig,
    PMPresupuesto,
    PMPresupuestoPartida,
    PMPresupuestoTaskLink,
    PMProyecto,
    PMTarea,
    PMTareaDependencia,
)
from app.services.pm import (
    PMContext,
    apply_budget_plan,
    build_budget_item_source_hash,
    create_budget_item,
    create_budget_task_link,
    create_project_budget,
    get_budget_plan_preview,
)


class PMBudgetPlanApplyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend_dir = Path(__file__).resolve().parents[1]
        cls.temp_root = Path(tempfile.mkdtemp(prefix="pm-budget-apply-"))
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

    def _create_budget(
        self,
        project: PMProyecto,
        *,
        name: str = "Presupuesto base",
        version: int = 1,
        status_name: str = "aprobado",
        active: bool = True,
    ) -> PMPresupuesto:
        budget = PMPresupuesto(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            nombre=name,
            version=version,
            estatus=status_name,
            moneda="MXN",
            activo=active,
        )
        self.db.add(budget)
        self.db.flush()
        return budget

    def _create_task(
        self,
        project: PMProyecto,
        *,
        title: str,
        description: str | None = None,
        status_name: str = "pendiente",
        assigned_user_id: str | None = None,
        assigned_name: str | None = None,
        progress: Decimal = Decimal("0"),
        start_date: date | None = None,
        due_date: date | None = None,
    ) -> PMTarea:
        task = PMTarea(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            titulo=title,
            descripcion=description,
            estatus=status_name,
            prioridad="media",
            asignado_user_id=assigned_user_id,
            asignado_nombre_snapshot=assigned_name,
            fecha_inicio=start_date,
            fecha_vencimiento=due_date,
            estimacion_horas=Decimal("8"),
            porcentaje_avance=progress,
            orden=0,
            bloqueada=False,
            requiere_materiales=False,
            requiere_compra=False,
            requiere_venta_pos=False,
            requiere_factura=False,
            activo=True,
            created_by=self.user_a.id if project.empresa_id == self.company_a.id else self.user_b.id,
            updated_by=self.user_a.id if project.empresa_id == self.company_a.id else self.user_b.id,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _create_budget_item(
        self,
        budget: PMPresupuesto,
        *,
        parent_id: str | None,
        codigo: str | None,
        nombre: str,
        descripcion: str | None,
        tipo: str,
        unidad: str | None = None,
        cantidad: Decimal = Decimal("1"),
        precio_unitario_manual: Decimal | None = Decimal("100"),
        orden: int = 0,
    ) -> PMPresupuestoPartida:
        context = self.pm_context_a if budget.empresa_id == self.company_a.id else self.pm_context_b
        item = create_budget_item(
            self.db,
            context,
            budget_id=budget.id,
            parent_id=parent_id,
            codigo=codigo,
            nombre=nombre,
            descripcion=descripcion,
            tipo=tipo,
            unidad=unidad,
            cantidad=cantidad,
            margen_pct=Decimal("0"),
            precio_unitario_manual=precio_unitario_manual,
            orden=orden,
            ip_address=None,
        )
        return self.db.get(PMPresupuestoPartida, item.id)

    def _create_raw_budget_item(
        self,
        budget: PMPresupuesto,
        *,
        parent_id: str | None,
        nombre: str,
        codigo: str | None = None,
        descripcion: str | None = None,
        tipo: str = "partida",
        lineage_id: str | None = None,
        cantidad: Decimal = Decimal("1"),
        precio_unitario_manual: Decimal = Decimal("100"),
        orden: int = 0,
    ) -> PMPresupuestoPartida:
        item = PMPresupuestoPartida(
            empresa_id=budget.empresa_id,
            presupuesto_id=budget.id,
            proyecto_id=budget.proyecto_id,
            parent_id=parent_id,
            lineage_id=lineage_id or str(uuid4()),
            codigo=codigo,
            nombre=nombre,
            descripcion=descripcion,
            tipo=tipo,
            unidad="pz" if tipo == "partida" else None,
            cantidad=cantidad,
            costo_unitario=Decimal("0"),
            precio_unitario=Decimal("0"),
            precio_unitario_manual=precio_unitario_manual if tipo == "partida" else None,
            subtotal_costo=Decimal("0"),
            subtotal_venta=precio_unitario_manual * cantidad if tipo == "partida" else Decimal("0"),
            margen_pct=Decimal("0"),
            orden=orden,
            activo=True,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def _create_dependency(self, project: PMProyecto, *, task: PMTarea, depends_on: PMTarea) -> PMTareaDependencia:
        dependency = PMTareaDependencia(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            tarea_id=task.id,
            depende_de_tarea_id=depends_on.id,
            tipo_dependencia="finish_to_start",
            lag_dias=0,
            bloqueante=True,
            notas=None,
            activo=True,
            created_by=self.user_a.id if project.empresa_id == self.company_a.id else self.user_b.id,
        )
        self.db.add(dependency)
        self.db.flush()
        return dependency

    def _link_task(
        self,
        *,
        project: PMProyecto,
        budget: PMPresupuesto,
        chapter: PMPresupuestoPartida | None,
        partida: PMPresupuestoPartida,
        task: PMTarea,
        generated_from_budget: bool = True,
        sync_status: str = "linked",
        source_hash: str | None = None,
    ) -> PMPresupuestoTaskLink:
        link = create_budget_task_link(
            self.db,
            empresa_id=project.empresa_id,
            project_id=project.id,
            lineage_id=partida.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=partida.id,
            source_capitulo_id=chapter.id if chapter else None,
            generated_from_budget=generated_from_budget,
            sync_status=sync_status,
            source_hash=source_hash
            or build_budget_item_source_hash(partida, parent_lineage_id=chapter.lineage_id if chapter else None),
        )
        self.db.flush()
        return link

    def _preview(self, budget: PMPresupuesto):
        context = self.pm_context_a if budget.empresa_id == self.company_a.id else self.pm_context_b
        return get_budget_plan_preview(self.db, context, budget_id=budget.id)

    def _apply(
        self,
        budget: PMPresupuesto,
        *,
        expected_preview_token: str | None = None,
        confirm: bool = True,
        allow_draft: bool = False,
    ):
        context = self.pm_context_a if budget.empresa_id == self.company_a.id else self.pm_context_b
        preview = self._preview(budget)
        return apply_budget_plan(
            self.db,
            context,
            budget_id=budget.id,
            expected_preview_token=expected_preview_token or preview.preview_token,
            confirm=confirm,
            allow_draft=allow_draft,
            ip_address=None,
        )

    def test_apply_creates_task_for_partida_and_link_only(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto apply create", user=self.user_a)
        budget_out = create_project_budget(
            self.db,
            self.pm_context_a,
            project_id=project.id,
            nombre="Base",
            moneda="MXN",
            indirectos_pct=Decimal("0"),
            notas=None,
            ip_address=None,
        )
        budget = self.db.get(PMPresupuesto, budget_out.id)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Preliminares", descripcion=None, tipo="capitulo", orden=1)
        part = self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.01",
            nombre="Trazo",
            descripcion="Trazar area",
            tipo="partida",
            unidad="m2",
            cantidad=Decimal("2"),
            precio_unitario_manual=Decimal("500"),
            orden=2,
        )

        result = self._apply(self.db.get(PMPresupuesto, budget.id), allow_draft=True)

        self.assertEqual(result.summary.created_tasks, 1)
        self.assertEqual(result.summary.linked, 1)
        self.assertEqual(result.summary.no_change, 0)
        self.assertEqual(self.db.scalar(select(func.count(PMTarea.id)).where(PMTarea.proyecto_id == project.id)), 1)
        self.assertEqual(self.db.scalar(select(func.count(PMPresupuestoTaskLink.id)).where(PMPresupuestoTaskLink.proyecto_id == project.id)), 1)
        task = self.db.scalar(select(PMTarea).where(PMTarea.proyecto_id == project.id))
        self.assertEqual(task.titulo, "01.01 - Trazo")
        self.assertEqual(task.descripcion, "Trazar area")
        link = self.db.scalar(select(PMPresupuestoTaskLink).where(PMPresupuestoTaskLink.proyecto_id == project.id))
        self.assertEqual(link.source_partida_id, part.id)
        self.assertEqual(link.source_capitulo_id, chapter.id)
        self.assertTrue(link.generated_from_budget)

    def test_apply_is_idempotent_after_refreshing_preview(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto apply idempotente", user=self.user_a)
        budget = self._create_budget(project, status_name="borrador")
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Acabados", descripcion=None, tipo="capitulo")
        self._create_budget_item(budget, parent_id=chapter.id, codigo="01.01", nombre="Yeso", descripcion=None, tipo="partida", unidad="m2")
        budget.estatus = "aprobado"
        self.db.flush()

        first = self._apply(budget)
        second_preview = self._preview(self.db.get(PMPresupuesto, budget.id))
        second = apply_budget_plan(
            self.db,
            self.pm_context_a,
            budget_id=budget.id,
            expected_preview_token=second_preview.preview_token,
            confirm=True,
            allow_draft=False,
            ip_address=None,
        )

        self.assertEqual(first.summary.created_tasks, 1)
        self.assertEqual(second.summary.created_tasks, 0)
        self.assertEqual(second.summary.updated_tasks, 0)
        self.assertEqual(second.summary.linked, 0)
        self.assertEqual(second.summary.no_change, 1)
        self.assertEqual(self.db.scalar(select(func.count(PMTarea.id)).where(PMTarea.proyecto_id == project.id)), 1)
        self.assertEqual(self.db.scalar(select(func.count(PMPresupuestoTaskLink.id)).where(PMPresupuestoTaskLink.proyecto_id == project.id)), 1)

    def test_apply_updates_generated_task_title_and_link_sources(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto update", user=self.user_a)
        budget_v1 = self._create_budget(project, version=1, status_name="aprobado")
        chapter_v1 = self._create_raw_budget_item(budget_v1, parent_id=None, nombre="Estructura", codigo="01", tipo="capitulo", lineage_id="chapter-lineage", orden=1)
        part_v1 = self._create_raw_budget_item(
            budget_v1,
            parent_id=chapter_v1.id,
            nombre="Cimbra",
            codigo="01.01",
            descripcion="Original",
            lineage_id="part-lineage",
            orden=2,
        )
        task = self._create_task(project, title="01.01 - Cimbra")
        link = self._link_task(project=project, budget=budget_v1, chapter=chapter_v1, partida=part_v1, task=task, generated_from_budget=True)

        budget_v2 = self._create_budget(project, version=2, status_name="aprobado")
        chapter_v2 = self._create_raw_budget_item(
            budget_v2,
            parent_id=None,
            nombre="Estructura",
            codigo="01",
            tipo="capitulo",
            lineage_id=chapter_v1.lineage_id,
            orden=1,
        )
        part_v2 = self._create_raw_budget_item(
            budget_v2,
            parent_id=chapter_v2.id,
            nombre="Cimbra metalica",
            codigo="01.02",
            descripcion="Actualizada",
            lineage_id=part_v1.lineage_id,
            orden=2,
        )

        result = self._apply(budget_v2)

        self.assertEqual(result.summary.updated_tasks, 1)
        updated_task = self.db.get(PMTarea, task.id)
        self.assertEqual(updated_task.titulo, "01.02 - Cimbra metalica")
        self.assertEqual(updated_task.descripcion, "Actualizada")
        updated_link = self.db.get(PMPresupuestoTaskLink, link.id)
        self.assertEqual(updated_link.source_presupuesto_id, budget_v2.id)
        self.assertEqual(updated_link.source_partida_id, part_v2.id)
        self.assertEqual(updated_link.source_capitulo_id, chapter_v2.id)

    def test_apply_rejects_manual_task_update_conflict_without_writing(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto manual conflict", user=self.user_a)
        budget_v1 = self._create_budget(project, version=1, status_name="aprobado")
        chapter_v1 = self._create_raw_budget_item(budget_v1, parent_id=None, nombre="Muros", codigo="01", tipo="capitulo", lineage_id="manual-chapter")
        part_v1 = self._create_raw_budget_item(budget_v1, parent_id=chapter_v1.id, nombre="Block", codigo="01.01", lineage_id="manual-part")
        task = self._create_task(project, title="Nombre manual distinto")
        link = self._link_task(project=project, budget=budget_v1, chapter=chapter_v1, partida=part_v1, task=task, generated_from_budget=False)

        budget_v2 = self._create_budget(project, version=2, status_name="aprobado")
        chapter_v2 = self._create_raw_budget_item(budget_v2, parent_id=None, nombre="Muros", codigo="01", tipo="capitulo", lineage_id=chapter_v1.lineage_id)
        self._create_raw_budget_item(budget_v2, parent_id=chapter_v2.id, nombre="Block aparente", codigo="01.01", lineage_id=part_v1.lineage_id)

        with self.assertRaises(HTTPException) as exc_info:
            self._apply(budget_v2)

        self.assertEqual(exc_info.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.db.get(PMTarea, task.id).titulo, "Nombre manual distinto")
        self.assertEqual(self.db.get(PMPresupuestoTaskLink, link.id).source_presupuesto_id, budget_v1.id)

    def test_apply_refreshes_source_hash_without_touching_operational_fields(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto economico", user=self.user_a)
        budget_v1 = self._create_budget(project, version=1, status_name="aprobado")
        chapter_v1 = self._create_raw_budget_item(budget_v1, parent_id=None, nombre="Pisos", codigo="01", tipo="capitulo", lineage_id="econ-chapter")
        part_v1 = self._create_raw_budget_item(
            budget_v1,
            parent_id=chapter_v1.id,
            nombre="Loseta",
            codigo="01.01",
            descripcion="Base",
            lineage_id="econ-part",
            cantidad=Decimal("10"),
            precio_unitario_manual=Decimal("100"),
        )
        task = self._create_task(
            project,
            title="01.01 - Loseta",
            description="Base",
            status_name="en_progreso",
            assigned_user_id=self.user_a.id,
            assigned_name=self.user_a.full_name,
            progress=Decimal("55"),
            start_date=date(2026, 8, 1),
            due_date=date(2026, 8, 20),
        )
        link = self._link_task(project=project, budget=budget_v1, chapter=chapter_v1, partida=part_v1, task=task, generated_from_budget=True)
        original_source_hash = link.source_hash

        budget_v2 = self._create_budget(project, version=2, status_name="aprobado")
        chapter_v2 = self._create_raw_budget_item(budget_v2, parent_id=None, nombre="Pisos", codigo="01", tipo="capitulo", lineage_id=chapter_v1.lineage_id)
        part_v2 = self._create_raw_budget_item(
            budget_v2,
            parent_id=chapter_v2.id,
            nombre="Loseta",
            codigo="01.01",
            descripcion="Base",
            lineage_id=part_v1.lineage_id,
            cantidad=Decimal("12"),
            precio_unitario_manual=Decimal("120"),
        )

        result = self._apply(budget_v2)

        self.assertEqual(result.summary.created_tasks, 0)
        self.assertEqual(result.summary.updated_tasks, 0)
        self.assertEqual(result.summary.no_change, 1)
        self.assertEqual(result.summary.linked, 1)
        updated_task = self.db.get(PMTarea, task.id)
        self.assertEqual(updated_task.estatus, "en_progreso")
        self.assertEqual(Decimal(updated_task.porcentaje_avance), Decimal("55"))
        self.assertEqual(updated_task.asignado_user_id, self.user_a.id)
        self.assertEqual(updated_task.fecha_inicio, date(2026, 8, 1))
        self.assertEqual(updated_task.fecha_vencimiento, date(2026, 8, 20))
        updated_link = self.db.get(PMPresupuestoTaskLink, link.id)
        self.assertNotEqual(updated_link.source_hash, original_source_hash)
        self.assertEqual(updated_link.source_presupuesto_id, budget_v2.id)
        self.assertEqual(updated_link.source_partida_id, part_v2.id)

    def test_apply_reports_orphan_without_deleting_task(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto orphan", user=self.user_a)
        budget_v1 = self._create_budget(project, version=1, status_name="aprobado")
        chapter_v1 = self._create_raw_budget_item(budget_v1, parent_id=None, nombre="Instalaciones", codigo="01", tipo="capitulo", lineage_id="orph-chapter")
        part_v1 = self._create_raw_budget_item(budget_v1, parent_id=chapter_v1.id, nombre="Tuberia", codigo="01.01", lineage_id="orph-part")
        task = self._create_task(project, title="01.01 - Tuberia")
        link = self._link_task(project=project, budget=budget_v1, chapter=chapter_v1, partida=part_v1, task=task)

        budget_v2 = self._create_budget(project, version=2, status_name="aprobado")
        self._create_raw_budget_item(budget_v2, parent_id=None, nombre="Otro capitulo", codigo="02", tipo="capitulo", lineage_id="other-chapter")

        result = self._apply(budget_v2)

        self.assertEqual(result.summary.orphans, 1)
        self.assertEqual(result.summary.created_tasks, 0)
        self.assertEqual(self.db.get(PMTarea, task.id).titulo, "01.01 - Tuberia")
        self.assertEqual(self.db.get(PMPresupuestoTaskLink, link.id).source_presupuesto_id, budget_v1.id)

    def test_apply_keeps_orphan_and_still_creates_other_safe_items(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto mixed orphan", user=self.user_a)
        budget = self._create_budget(project, version=1, status_name="aprobado")
        chapter = self._create_raw_budget_item(budget, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="mix-chapter")
        orphan_part = self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Orphan", codigo="01.01", lineage_id="mix-orphan")
        create_part = self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Nueva", codigo="01.02", lineage_id="mix-create")
        orphan_link = PMPresupuestoTaskLink(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            lineage_id=orphan_part.lineage_id,
            tarea_id=None,
            source_presupuesto_id=budget.id,
            source_partida_id=orphan_part.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=build_budget_item_source_hash(orphan_part, parent_lineage_id=chapter.lineage_id),
        )
        self.db.add(orphan_link)
        self.db.flush()

        result = self._apply(budget)

        self.assertEqual(result.summary.created_tasks, 1)
        self.assertEqual(result.summary.orphans, 1)
        self.assertEqual(self.db.scalar(select(func.count(PMTarea.id)).where(PMTarea.proyecto_id == project.id)), 1)
        self.assertTrue(any(item.lineage_id == orphan_part.lineage_id for item in result.orphans))
        self.assertTrue(any(item.lineage_id == create_part.lineage_id for item in result.created))

    def test_apply_rejects_detached_link_as_blocking_conflict(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto detached", user=self.user_a)
        budget = self._create_budget(project, version=1, status_name="aprobado")
        chapter = self._create_raw_budget_item(budget, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="det-chapter")
        part = self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida", codigo="01.01", lineage_id="det-part")
        task = self._create_task(project, title="01.01 - Partida")
        self._link_task(project=project, budget=budget, chapter=chapter, partida=part, task=task, sync_status="detached")

        with self.assertRaises(HTTPException) as exc_info:
            self._apply(budget)

        self.assertEqual(exc_info.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.db.scalar(select(func.count(PMTarea.id)).where(PMTarea.proyecto_id == project.id)), 1)

    def test_apply_rejects_draft_without_allow_draft(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto draft", user=self.user_a)
        budget = self._create_budget(project, version=1, status_name="borrador")
        chapter = self._create_raw_budget_item(budget, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="draft-chapter")
        self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida", codigo="01.01", lineage_id="draft-part")

        with self.assertRaises(HTTPException) as exc_info:
            self._apply(budget, allow_draft=False)

        self.assertEqual(exc_info.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.db.scalar(select(func.count(PMTarea.id)).where(PMTarea.proyecto_id == project.id)), 0)

    def test_apply_allows_draft_with_warning(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto draft ok", user=self.user_a)
        budget = self._create_budget(project, version=1, status_name="borrador")
        chapter = self._create_raw_budget_item(budget, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="draft-ok-chapter")
        self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida", codigo="01.01", lineage_id="draft-ok-part")

        result = self._apply(budget, allow_draft=True)

        self.assertEqual(result.summary.created_tasks, 1)
        self.assertTrue(any(item.code == "budget_in_draft" for item in result.warnings))

    def test_apply_rejects_obsolete_preview_token_without_writes(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto stale", user=self.user_a)
        budget = self._create_budget(project, version=1, status_name="aprobado")
        chapter = self._create_raw_budget_item(budget, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="stale-chapter")
        self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida 1", codigo="01.01", lineage_id="stale-part-a")
        preview = self._preview(budget)
        self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida 2", codigo="01.02", lineage_id="stale-part-b")

        with self.assertRaises(HTTPException) as exc_info:
            apply_budget_plan(
                self.db,
                self.pm_context_a,
                budget_id=budget.id,
                expected_preview_token=preview.preview_token,
                confirm=True,
                allow_draft=False,
                ip_address=None,
            )

        self.assertEqual(exc_info.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.db.scalar(select(func.count(PMTarea.id)).where(PMTarea.proyecto_id == project.id)), 0)
        self.assertEqual(self.db.scalar(select(func.count(PMPresupuestoTaskLink.id)).where(PMPresupuestoTaskLink.proyecto_id == project.id)), 0)

    def test_apply_rollback_on_mid_operation_error(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto rollback", user=self.user_a)
        budget = self._create_budget(project, version=1, status_name="aprobado")
        chapter = self._create_raw_budget_item(budget, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="rb-chapter")
        self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida A", codigo="01.01", lineage_id="rb-part-a")
        self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida B", codigo="01.02", lineage_id="rb-part-b")
        preview = self._preview(budget)

        original_create_budget_task_link = create_budget_task_link

        def fail_on_first_link(*args, **kwargs):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fallo forzado durante pruebas.")

        with patch("app.services.pm.create_budget_task_link", side_effect=fail_on_first_link):
            with self.assertRaises(HTTPException):
                apply_budget_plan(
                    self.db,
                    self.pm_context_a,
                    budget_id=budget.id,
                    expected_preview_token=preview.preview_token,
                    confirm=True,
                    allow_draft=False,
                    ip_address=None,
                )
        self.db.rollback()

        self.assertEqual(self.db.scalar(select(func.count(PMTarea.id)).where(PMTarea.proyecto_id == project.id)), 0)
        self.assertEqual(self.db.scalar(select(func.count(PMPresupuestoTaskLink.id)).where(PMPresupuestoTaskLink.proyecto_id == project.id)), 0)
        self.assertTrue(callable(original_create_budget_task_link))

    def test_apply_preserves_status_progress_dates_assignment_and_dependencies(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto preserve", user=self.user_a)
        budget_v1 = self._create_budget(project, version=1, status_name="aprobado")
        chapter_v1 = self._create_raw_budget_item(budget_v1, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="pres-chapter")
        part_v1 = self._create_raw_budget_item(budget_v1, parent_id=chapter_v1.id, nombre="Instalacion", codigo="01.01", lineage_id="pres-part")
        task = self._create_task(
            project,
            title="01.01 - Instalacion vieja",
            description="Vieja",
            status_name="en_progreso",
            assigned_user_id=self.user_a.id,
            assigned_name=self.user_a.full_name,
            progress=Decimal("40"),
            start_date=date(2026, 8, 1),
            due_date=date(2026, 8, 15),
        )
        blocker = self._create_task(project, title="Bloqueadora")
        self._create_dependency(project, task=task, depends_on=blocker)
        self._link_task(project=project, budget=budget_v1, chapter=chapter_v1, partida=part_v1, task=task, generated_from_budget=True)

        budget_v2 = self._create_budget(project, version=2, status_name="aprobado")
        chapter_v2 = self._create_raw_budget_item(budget_v2, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id=chapter_v1.lineage_id)
        self._create_raw_budget_item(
            budget_v2,
            parent_id=chapter_v2.id,
            nombre="Instalacion nueva",
            codigo="01.02",
            descripcion="Nueva",
            lineage_id=part_v1.lineage_id,
        )

        self._apply(budget_v2)

        updated_task = self.db.get(PMTarea, task.id)
        self.assertEqual(updated_task.titulo, "01.02 - Instalacion nueva")
        self.assertEqual(updated_task.estatus, "en_progreso")
        self.assertEqual(Decimal(updated_task.porcentaje_avance), Decimal("40"))
        self.assertEqual(updated_task.asignado_user_id, self.user_a.id)
        self.assertEqual(updated_task.fecha_inicio, date(2026, 8, 1))
        self.assertEqual(updated_task.fecha_vencimiento, date(2026, 8, 15))
        self.assertEqual(
            self.db.scalar(select(func.count(PMTareaDependencia.id)).where(PMTareaDependencia.tarea_id == task.id, PMTareaDependencia.activo == True)),
            1,
        )

    def test_apply_rejects_cross_tenant_budget_access(self) -> None:
        project = self._create_project(self.company_b, name="Proyecto externo", user=self.user_b)
        budget = self._create_budget(project, version=1, status_name="aprobado")
        chapter = self._create_raw_budget_item(budget, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="xt-chapter")
        self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida", codigo="01.01", lineage_id="xt-part")

        with self.assertRaises(HTTPException):
            apply_budget_plan(
                self.db,
                self.pm_context_a,
                budget_id=budget.id,
                expected_preview_token="fake-token",
                confirm=True,
                allow_draft=False,
                ip_address=None,
            )

    def test_apply_response_counts_match_mixed_actions(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto summary", user=self.user_a)
        budget_v1 = self._create_budget(project, version=1, status_name="aprobado")
        chapter_v1 = self._create_raw_budget_item(budget_v1, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="sum-chapter")
        part_no_change_v1 = self._create_raw_budget_item(budget_v1, parent_id=chapter_v1.id, nombre="No cambio", codigo="01.01", lineage_id="sum-no-change")
        task = self._create_task(project, title="01.01 - No cambio")
        self._link_task(project=project, budget=budget_v1, chapter=chapter_v1, partida=part_no_change_v1, task=task)

        budget_v2 = self._create_budget(project, version=2, status_name="aprobado")
        chapter_v2 = self._create_raw_budget_item(budget_v2, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id=chapter_v1.lineage_id)
        self._create_raw_budget_item(budget_v2, parent_id=chapter_v2.id, nombre="No cambio", codigo="01.01", lineage_id=part_no_change_v1.lineage_id)
        self._create_raw_budget_item(budget_v2, parent_id=chapter_v2.id, nombre="Crear", codigo="01.02", lineage_id="sum-create")
        self._create_raw_budget_item(budget_v2, parent_id=chapter_v2.id, nombre="   ", codigo="01.03", lineage_id="sum-skip")

        result = self._apply(budget_v2)

        self.assertEqual(result.summary.created_tasks, 1)
        self.assertEqual(result.summary.no_change, 1)
        self.assertEqual(result.summary.skipped, 1)
        self.assertEqual(len(result.created), 1)
        self.assertEqual(len(result.skipped), 1)

    def test_apply_writes_summary_audit_log(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto audit", user=self.user_a)
        budget = self._create_budget(project, version=1, status_name="aprobado")
        chapter = self._create_raw_budget_item(budget, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="audit-chapter")
        self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida", codigo="01.01", lineage_id="audit-part")
        preview_before = self._preview(budget)

        result = self._apply(budget)

        audit = self.db.scalar(
            select(AuditLog)
            .where(
                AuditLog.empresa_id == self.company_a.id,
                AuditLog.action == "pm.plan.generated_from_budget",
                AuditLog.entity_id == budget.id,
            )
            .order_by(AuditLog.created_at.desc())
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit.metadata_json["created_tasks"], result.summary.created_tasks)
        self.assertEqual(audit.metadata_json["preview_token"], preview_before.preview_token)

    def test_preview_token_changes_after_apply(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto token", user=self.user_a)
        budget = self._create_budget(project, version=1, status_name="aprobado")
        chapter = self._create_raw_budget_item(budget, parent_id=None, nombre="Capitulo", codigo="01", tipo="capitulo", lineage_id="token-chapter")
        self._create_raw_budget_item(budget, parent_id=chapter.id, nombre="Partida", codigo="01.01", lineage_id="token-part")

        preview_before = self._preview(budget)
        self._apply(budget)
        preview_after = self._preview(budget)

        self.assertNotEqual(preview_before.preview_token, preview_after.preview_token)

    def test_apply_rejects_cancelled_budget(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto cancelado", user=self.user_a)
        budget = self._create_budget(project, version=1, status_name="cancelado", active=False)

        with self.assertRaises(HTTPException) as exc_info:
            self._apply(budget)

        self.assertEqual(exc_info.exception.status_code, status.HTTP_409_CONFLICT)


if __name__ == "__main__":
    unittest.main()
