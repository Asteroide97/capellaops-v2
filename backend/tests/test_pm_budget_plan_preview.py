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

from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Empresa, EmpresaUsuario, Plan, Usuario
from app.models.pm import EmpresaPMConfig, PMPresupuesto, PMPresupuestoPartida, PMPresupuestoTaskLink, PMProyecto, PMTarea
from app.services.pm import (
    PMContext,
    build_budget_item_source_hash,
    create_budget_item,
    create_budget_task_link,
    create_project_budget,
    get_budget_plan_preview,
)


class PMBudgetPlanPreviewTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend_dir = Path(__file__).resolve().parents[1]
        cls.temp_root = Path(tempfile.mkdtemp(prefix="pm-budget-preview-"))
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

    def _create_budget(self, project: PMProyecto, *, name: str = "Presupuesto base", status_name: str = "borrador") -> PMPresupuesto:
        budget = PMPresupuesto(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            nombre=name,
            version=1,
            estatus=status_name,
            moneda="MXN",
            activo=status_name != "cancelado",
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
        margen_pct: Decimal = Decimal("0"),
        precio_unitario_manual: Decimal | None = None,
        orden: int = 0,
    ) -> PMPresupuestoPartida:
        item = create_budget_item(
            self.db,
            self.pm_context_a if budget.empresa_id == self.company_a.id else self.pm_context_b,
            budget_id=budget.id,
            parent_id=parent_id,
            codigo=codigo,
            nombre=nombre,
            descripcion=descripcion,
            tipo=tipo,
            unidad=unidad,
            cantidad=cantidad,
            margen_pct=margen_pct,
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
        tipo: str = "partida",
        lineage_id: str | None = None,
    ) -> PMPresupuestoPartida:
        item = PMPresupuestoPartida(
            empresa_id=budget.empresa_id,
            presupuesto_id=budget.id,
            proyecto_id=budget.proyecto_id,
            parent_id=parent_id,
            lineage_id=lineage_id or str(uuid4()),
            codigo=None,
            nombre=nombre,
            descripcion=None,
            tipo=tipo,
            unidad="pz" if tipo == "partida" else None,
            cantidad=Decimal("1"),
            costo_unitario=Decimal("0"),
            precio_unitario=Decimal("0"),
            precio_unitario_manual=Decimal("100"),
            subtotal_costo=Decimal("0"),
            subtotal_venta=Decimal("100"),
            margen_pct=Decimal("0"),
            orden=0,
            activo=True,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def _preview(self, budget: PMPresupuesto):
        return get_budget_plan_preview(
            self.db,
            self.pm_context_a if budget.empresa_id == self.company_a.id else self.pm_context_b,
            budget_id=budget.id,
        )

    def test_preview_create_for_partida_without_link(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto create", user=self.user_a)
        budget = create_project_budget(self.db, self.pm_context_a, project_id=project.id, nombre="Base", moneda="MXN", indirectos_pct=Decimal("0"), notas=None, ip_address=None)
        chapter = self._create_budget_item(self.db.get(PMPresupuesto, budget.id), parent_id=None, codigo="01", nombre="Preliminares", descripcion=None, tipo="capitulo", orden=1)
        self._create_budget_item(self.db.get(PMPresupuesto, budget.id), parent_id=chapter.id, codigo="01.01", nombre="Trazo", descripcion=None, tipo="partida", unidad="m2", cantidad=Decimal("2"), precio_unitario_manual=Decimal("500"), orden=2)

        preview = self._preview(self.db.get(PMPresupuesto, budget.id))

        self.assertEqual(preview.summary.create, 1)
        self.assertEqual(preview.summary.parts, 1)
        self.assertEqual(preview.summary.chapters, 1)
        self.assertEqual(len(preview.chapters), 1)
        self.assertEqual(preview.chapters[0].chapter.child_parts_count, 1)
        self.assertEqual(preview.chapters[0].items[0].action, "create")
        self.assertEqual(preview.chapters[0].items[0].reason_code, "no_existing_link")

    def test_preview_no_change_for_linked_generated_task(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto linked", user=self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Acabados", descripcion=None, tipo="capitulo")
        part = self._create_budget_item(budget, parent_id=chapter.id, codigo="01.01", nombre="Yeso", descripcion=None, tipo="partida", unidad="m2", cantidad=Decimal("1"), precio_unitario_manual=Decimal("450"))
        task = self._create_task(project, title="01.01 - Yeso")
        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=part.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=part.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=build_budget_item_source_hash(part),
        )
        self.db.commit()

        preview = self._preview(budget)

        item = preview.chapters[0].items[0]
        self.assertEqual(item.action, "no_change")
        self.assertEqual(item.reason_code, "linked_without_changes")
        self.assertFalse(item.source_changed)
        self.assertEqual(item.task_id, task.id)

    def test_preview_update_for_generated_task_title_change(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto update", user=self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Muros", descripcion=None, tipo="capitulo")
        part = self._create_budget_item(budget, parent_id=chapter.id, codigo="01.01", nombre="Tablaroca", descripcion=None, tipo="partida", unidad="m2", cantidad=Decimal("1"), precio_unitario_manual=Decimal("750"))
        task = self._create_task(project, title="Titulo anterior")
        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=part.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=part.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=build_budget_item_source_hash(part),
        )
        self.db.commit()

        preview = self._preview(budget)
        item = preview.chapters[0].items[0]

        self.assertEqual(item.action, "update")
        self.assertEqual(item.reason_code, "generated_task_title_changed")
        self.assertEqual(item.proposed_changes[0].field, "task_title")

    def test_preview_conflict_for_manual_task_title_change(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto manual", user=self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Muros", descripcion=None, tipo="capitulo")
        part = self._create_budget_item(budget, parent_id=chapter.id, codigo="01.01", nombre="Pintura", descripcion=None, tipo="partida", unidad="m2", cantidad=Decimal("1"), precio_unitario_manual=Decimal("300"))
        task = self._create_task(project, title="Pintura revisada manualmente")
        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=part.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=part.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=False,
            sync_status="linked",
            source_hash=build_budget_item_source_hash(part),
        )
        self.db.commit()

        preview = self._preview(budget)
        item = preview.chapters[0].items[0]

        self.assertEqual(item.action, "conflict")
        self.assertEqual(item.reason_code, "manual_task_requires_review")

    def test_preview_reports_economic_change_without_operational_update(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto economico", user=self.user_a)
        old_budget = self._create_budget(project, name="Presupuesto v1", status_name="borrador")
        chapter_v1 = self._create_budget_item(old_budget, parent_id=None, codigo="01", nombre="Instalacion", descripcion=None, tipo="capitulo")
        part_v1 = self._create_budget_item(old_budget, parent_id=chapter_v1.id, codigo="01.01", nombre="Canalizacion", descripcion=None, tipo="partida", unidad="m", cantidad=Decimal("1"), precio_unitario_manual=Decimal("100"))
        old_budget.estatus = "aprobado"
        new_budget = self._create_budget(project, name="Presupuesto v2", status_name="borrador")
        chapter_v2 = self._create_budget_item(new_budget, parent_id=None, codigo="01", nombre="Instalacion", descripcion=None, tipo="capitulo")
        chapter_v2.lineage_id = chapter_v1.lineage_id
        part_v2 = self._create_raw_budget_item(new_budget, parent_id=chapter_v2.id, nombre="Canalizacion", lineage_id=part_v1.lineage_id)
        part_v2.codigo = "01.01"
        part_v2.unidad = "m"
        part_v2.cantidad = Decimal("3")
        part_v2.precio_unitario_manual = Decimal("100")
        part_v2.subtotal_venta = Decimal("300")
        new_budget.estatus = "aprobado"
        self.db.flush()
        task = self._create_task(project, title="01.01 - Canalizacion")
        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=part_v1.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=old_budget.id,
            source_partida_id=part_v1.id,
            source_capitulo_id=chapter_v1.id,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=build_budget_item_source_hash(part_v1),
        )
        self.db.commit()

        preview = self._preview(new_budget)
        item = preview.chapters[0].items[0]

        self.assertEqual(item.action, "no_change")
        self.assertEqual(item.reason_code, "source_hash_changed")
        self.assertTrue(item.source_changed)
        self.assertTrue(any(change.field == "cantidad" for change in item.economic_changes))

    def test_preview_keeps_source_hash_stable_when_only_physical_parent_ids_change(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto hash estable preview", user=self.user_a)
        old_budget = self._create_budget(project, name="Presupuesto v1", status_name="borrador")
        chapter_v1 = self._create_budget_item(old_budget, parent_id=None, codigo="01", nombre="Instalacion", descripcion=None, tipo="capitulo")
        part_v1 = self._create_budget_item(old_budget, parent_id=chapter_v1.id, codigo="01.01", nombre="Canalizacion", descripcion=None, tipo="partida", unidad="m", cantidad=Decimal("1"), precio_unitario_manual=Decimal("100"))
        old_budget.estatus = "aprobado"
        new_budget = self._create_budget(project, name="Presupuesto v2", status_name="borrador")
        chapter_v2 = self._create_budget_item(new_budget, parent_id=None, codigo="01", nombre="Instalacion", descripcion=None, tipo="capitulo")
        chapter_v2.lineage_id = chapter_v1.lineage_id
        part_v2 = self._create_raw_budget_item(new_budget, parent_id=chapter_v2.id, nombre="Canalizacion", lineage_id=part_v1.lineage_id)
        part_v2.codigo = part_v1.codigo
        part_v2.nombre = part_v1.nombre
        part_v2.descripcion = part_v1.descripcion
        part_v2.tipo = part_v1.tipo
        part_v2.unidad = part_v1.unidad
        part_v2.cantidad = part_v1.cantidad
        part_v2.costo_unitario = part_v1.costo_unitario
        part_v2.precio_unitario = part_v1.precio_unitario
        part_v2.precio_unitario_manual = part_v1.precio_unitario_manual
        part_v2.subtotal_costo = part_v1.subtotal_costo
        part_v2.subtotal_venta = part_v1.subtotal_venta
        part_v2.margen_pct = part_v1.margen_pct
        part_v2.orden = part_v1.orden
        part_v2.activo = part_v1.activo
        new_budget.estatus = "aprobado"
        self.db.flush()
        task = self._create_task(project, title="01.01 - Canalizacion")
        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=part_v1.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=old_budget.id,
            source_partida_id=part_v1.id,
            source_capitulo_id=chapter_v1.id,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=build_budget_item_source_hash(part_v1, parent_lineage_id=chapter_v1.lineage_id),
        )
        self.db.commit()

        preview = self._preview(new_budget)
        item = preview.chapters[0].items[0]

        self.assertEqual(item.action, "no_change")
        self.assertFalse(item.source_changed)
        self.assertEqual(item.reason_code, "linked_without_changes")
        self.assertEqual(item.current_source_hash, item.linked_source_hash)

    def test_preview_orphan_for_null_task_and_missing_lineage(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto orphan", user=self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Preparacion", descripcion=None, tipo="capitulo")
        part = self._create_budget_item(budget, parent_id=chapter.id, codigo="01.01", nombre="Limpieza", descripcion=None, tipo="partida", unidad="m2", cantidad=Decimal("1"), precio_unitario_manual=Decimal("50"))
        orphan_link = PMPresupuestoTaskLink(
            empresa_id=self.company_a.id,
            proyecto_id=project.id,
            lineage_id=part.lineage_id,
            tarea_id=None,
            source_presupuesto_id=budget.id,
            source_partida_id=part.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=build_budget_item_source_hash(part),
        )
        missing_link = PMPresupuestoTaskLink(
            empresa_id=self.company_a.id,
            proyecto_id=project.id,
            lineage_id=str(uuid4()),
            tarea_id=None,
            source_presupuesto_id=budget.id,
            source_partida_id=None,
            source_capitulo_id=None,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=None,
        )
        self.db.add_all([orphan_link, missing_link])
        self.db.commit()

        preview = self._preview(budget)

        self.assertEqual(preview.summary.orphan, 2)
        self.assertTrue(any(item.reason_code == "missing_task" for item in preview.orphans))
        self.assertTrue(any(item.reason_code == "missing_source_item" for item in preview.orphans))

    def test_preview_conflict_for_detached_and_existing_conflict_status(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto detached", user=self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Acero", descripcion=None, tipo="capitulo")
        detached_part = self._create_budget_item(budget, parent_id=chapter.id, codigo="01.01", nombre="Perfil", descripcion=None, tipo="partida", unidad="pza", cantidad=Decimal("1"), precio_unitario_manual=Decimal("200"))
        conflict_part = self._create_budget_item(budget, parent_id=chapter.id, codigo="01.02", nombre="Placa", descripcion=None, tipo="partida", unidad="pza", cantidad=Decimal("1"), precio_unitario_manual=Decimal("250"))
        detached_task = self._create_task(project, title="01.01 - Perfil")
        conflict_task = self._create_task(project, title="01.02 - Placa")
        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=detached_part.lineage_id,
            tarea_id=detached_task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=detached_part.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="detached",
            source_hash=build_budget_item_source_hash(detached_part),
        )
        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=conflict_part.lineage_id,
            tarea_id=conflict_task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=conflict_part.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="conflict",
            source_hash=build_budget_item_source_hash(conflict_part),
        )
        self.db.commit()

        preview = self._preview(budget)
        reasons = {item.reason_code for item in preview.conflicts}

        self.assertIn("detached_link", reasons)
        self.assertIn("existing_conflict", reasons)

    def test_preview_unassigned_invalid_parent_and_skip(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto unassigned", user=self.user_a)
        budget = self._create_budget(project)
        valid_part = self._create_budget_item(budget, parent_id=None, codigo="01.01", nombre="Partida libre", descripcion=None, tipo="partida", unidad="pza", cantidad=Decimal("1"), precio_unitario_manual=Decimal("100"))
        invalid_parent_item = self._create_raw_budget_item(budget, parent_id=valid_part.id, nombre="Partida mal colgada")
        blank_name_item = self._create_raw_budget_item(budget, parent_id=None, nombre="   ")
        self.db.commit()

        preview = self._preview(budget)
        actions_by_id = {item.item_id: item for item in preview.unassigned_items}

        self.assertEqual(actions_by_id[valid_part.id].action, "create")
        self.assertEqual(actions_by_id[invalid_parent_item.id].action, "conflict")
        self.assertEqual(actions_by_id[blank_name_item.id].action, "skip")
        self.assertEqual(actions_by_id[blank_name_item.id].reason_code, "missing_item_name")

    def test_preview_rejects_cancelled_and_cross_company_budgets(self) -> None:
        project_a = self._create_project(self.company_a, name="Proyecto cancelado", user=self.user_a)
        cancelled_budget = self._create_budget(project_a, status_name="cancelado")
        project_b = self._create_project(self.company_b, name="Proyecto externo", user=self.user_b)
        external_budget = self._create_budget(project_b)
        self.db.commit()

        with self.assertRaises(HTTPException) as cancelled_exc:
            self._preview(cancelled_budget)
        self.assertEqual(cancelled_exc.exception.status_code, 409)

        with self.assertRaises(HTTPException) as external_exc:
            get_budget_plan_preview(self.db, self.pm_context_a, budget_id=external_budget.id)
        self.assertEqual(external_exc.exception.status_code, 404)

    def test_preview_is_read_only_for_tasks_links_and_source_hash(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto readonly", user=self.user_a)
        budget = self._create_budget(project, status_name="borrador")
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Obra civil", descripcion=None, tipo="capitulo")
        part = self._create_budget_item(budget, parent_id=chapter.id, codigo="01.01", nombre="Cimentacion", descripcion=None, tipo="partida", unidad="m3", cantidad=Decimal("1"), precio_unitario_manual=Decimal("1000"))
        budget.estatus = "aprobado"
        self.db.flush()
        task = self._create_task(project, title="01.01 - Cimentacion")
        link = create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=part.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=part.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=build_budget_item_source_hash(part),
        )
        self.db.commit()

        task_updated_at = task.updated_at
        link_updated_at = link.updated_at
        link_source_hash = link.source_hash
        task_count_before = self.db.scalar(select(func.count(PMTarea.id)).where(PMTarea.empresa_id == self.company_a.id))
        link_count_before = self.db.scalar(select(func.count(PMPresupuestoTaskLink.id)).where(PMPresupuestoTaskLink.empresa_id == self.company_a.id))

        preview = self._preview(budget)

        task_after = self.db.get(PMTarea, task.id)
        link_after = self.db.get(PMPresupuestoTaskLink, link.id)
        task_count_after = self.db.scalar(select(func.count(PMTarea.id)).where(PMTarea.empresa_id == self.company_a.id))
        link_count_after = self.db.scalar(select(func.count(PMPresupuestoTaskLink.id)).where(PMPresupuestoTaskLink.empresa_id == self.company_a.id))

        self.assertEqual(preview.summary.no_change, 1)
        self.assertEqual(task_count_before, task_count_after)
        self.assertEqual(link_count_before, link_count_after)
        self.assertEqual(task_updated_at, task_after.updated_at)
        self.assertEqual(link_updated_at, link_after.updated_at)
        self.assertEqual(link_source_hash, link_after.source_hash)
        self.assertEqual(link_after.sync_status, "linked")
        self.assertEqual(len(self.db.new), 0)
        self.assertEqual(len(self.db.dirty), 0)

    def test_preview_summary_matches_grouped_items(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto summary", user=self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(budget, parent_id=None, codigo="01", nombre="Capitulo", descripcion=None, tipo="capitulo")
        part_a = self._create_budget_item(budget, parent_id=chapter.id, codigo="01.01", nombre="Partida A", descripcion=None, tipo="partida", unidad="pza", cantidad=Decimal("1"), precio_unitario_manual=Decimal("10"))
        part_b = self._create_budget_item(budget, parent_id=chapter.id, codigo="01.02", nombre="Partida B", descripcion=None, tipo="partida", unidad="pza", cantidad=Decimal("1"), precio_unitario_manual=Decimal("20"))
        task = self._create_task(project, title="01.02 - Partida B")
        create_budget_task_link(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
            lineage_id=part_b.lineage_id,
            tarea_id=task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=part_b.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=build_budget_item_source_hash(part_b),
        )
        missing_lineage = PMPresupuestoTaskLink(
            empresa_id=self.company_a.id,
            proyecto_id=project.id,
            lineage_id=str(uuid4()),
            tarea_id=None,
            source_presupuesto_id=budget.id,
            source_partida_id=None,
            source_capitulo_id=None,
            generated_from_budget=True,
            sync_status="linked",
            source_hash=None,
        )
        self.db.add(missing_lineage)
        self.db.commit()

        preview = self._preview(budget)
        grouped_count = sum(len(group.items) for group in preview.chapters) + len(preview.unassigned_items) + len(preview.orphans)

        self.assertEqual(preview.summary.parts, 2)
        self.assertEqual(preview.summary.create, 1)
        self.assertEqual(preview.summary.no_change, 1)
        self.assertEqual(preview.summary.orphan, 1)
        self.assertEqual(grouped_count, 3)


if __name__ == "__main__":
    unittest.main()
