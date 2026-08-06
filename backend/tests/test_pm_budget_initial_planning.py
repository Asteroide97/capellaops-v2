from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from fastapi import HTTPException, status
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Empresa, EmpresaUsuario, Plan, Usuario
from app.models.pm import (
    EmpresaPMConfig,
    PMPresupuesto,
    PMPresupuestoPartida,
    PMPresupuestoPartidaPrerequisito,
    PMPresupuestoTaskLink,
    PMProyecto,
    PMProyectoMiembro,
    PMTarea,
    PMTareaDependencia,
)
from app.services.pm import (
    PMContext,
    apply_budget_plan,
    create_budget_item,
    create_budget_item_prerequisite,
    create_budget_task_link,
    delete_budget_item_prerequisite,
    get_budget_plan_preview,
    list_project_tasks_for_planning,
    update_budget_item,
)


class PMBudgetInitialPlanningTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend_dir = Path(__file__).resolve().parents[1]
        cls.temp_root = Path(tempfile.mkdtemp(prefix="pm-budget-initial-planning-"))
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

    def _create_additional_company_user(self, company: Empresa, *, suffix: str, role: str = "user") -> Usuario:
        user = Usuario(
            email=f"{suffix}@example.com",
            full_name=f"User {suffix}",
            password_hash="hash",
            is_active=True,
            is_superadmin=False,
        )
        self.db.add(user)
        self.db.flush()
        membership = EmpresaUsuario(
            empresa_id=company.id,
            usuario_id=user.id,
            role=role,
            is_active=True,
        )
        self.db.add(membership)
        self.db.flush()
        return user

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

    def _add_project_member(self, project: PMProyecto, user: Usuario, *, role_name: str = "colaborador") -> PMProyectoMiembro:
        member = PMProyectoMiembro(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            usuario_id=user.id,
            email=user.email,
            nombre_snapshot=user.full_name,
            rol_en_proyecto=role_name,
            activo=True,
        )
        self.db.add(member)
        self.db.flush()
        return member

    def _create_task(self, project: PMProyecto, *, title: str) -> PMTarea:
        task = PMTarea(
            empresa_id=project.empresa_id,
            proyecto_id=project.id,
            titulo=title,
            estatus="pendiente",
            prioridad="media",
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
        margen_pct: Decimal = Decimal("0"),
        precio_unitario_manual: Decimal | None = None,
        fecha_inicio_sugerida: date | None = None,
        fecha_fin_sugerida: date | None = None,
        duracion_dias_sugerida: int | None = None,
        responsable_sugerido_usuario_id: str | None = None,
        notas_planificacion: str | None = None,
        orden: int = 0,
    ):
        context = self.pm_context_a if budget.empresa_id == self.company_a.id else self.pm_context_b
        return create_budget_item(
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
            margen_pct=margen_pct,
            precio_unitario_manual=precio_unitario_manual,
            fecha_inicio_sugerida=fecha_inicio_sugerida,
            fecha_fin_sugerida=fecha_fin_sugerida,
            duracion_dias_sugerida=duracion_dias_sugerida,
            responsable_sugerido_usuario_id=responsable_sugerido_usuario_id,
            notas_planificacion=notas_planificacion,
            orden=orden,
            ip_address=None,
        )

    @staticmethod
    def _find_preview_item(preview, name: str):
        for chapter_group in preview.chapters:
            for item in chapter_group.items:
                if item.name == name:
                    return item
        for collection in (preview.unassigned_items, preview.orphans, preview.conflicts):
            for item in collection:
                if item.name == name:
                    return item
        raise AssertionError(f"No preview item found for {name!r}")

    def test_create_budget_item_persists_planning_fields_and_resolves_responsible_name(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Planeado", user=self.user_a)
        self._add_project_member(project, self.user_a)
        budget = self._create_budget(project)

        chapter = self._create_budget_item(
            budget,
            parent_id=None,
            codigo="01",
            nombre="Preparacion",
            descripcion=None,
            tipo="capitulo",
            fecha_inicio_sugerida=date(2026, 8, 10),
            fecha_fin_sugerida=date(2026, 8, 12),
            notas_planificacion="Marco general",
            orden=1,
        )
        item = self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.01",
            nombre="Instalacion",
            descripcion="Trabajo inicial",
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("2"),
            margen_pct=Decimal("12"),
            precio_unitario_manual=Decimal("1800"),
            fecha_inicio_sugerida=date(2026, 8, 11),
            duracion_dias_sugerida=3,
            responsable_sugerido_usuario_id=self.user_a.id,
            notas_planificacion="Arranque en sitio",
            orden=2,
        )

        self.assertEqual(chapter.fecha_inicio_sugerida, date(2026, 8, 10))
        self.assertEqual(chapter.fecha_fin_sugerida, date(2026, 8, 12))
        self.assertIsNone(chapter.duracion_dias_sugerida)
        self.assertEqual(item.fecha_inicio_sugerida, date(2026, 8, 11))
        self.assertEqual(item.fecha_fin_sugerida, date(2026, 8, 13))
        self.assertEqual(item.duracion_dias_sugerida, 3)
        self.assertEqual(item.responsable_sugerido_usuario_id, self.user_a.id)
        self.assertEqual(item.responsable_sugerido_nombre, self.user_a.full_name)
        self.assertEqual(item.notas_planificacion, "Arranque en sitio")
        self.assertIsNone(item.linked_task_id)
        self.assertIsNone(item.linked_task_title)

    def test_update_budget_item_returns_linked_task_reference_and_allows_optional_planning_fields(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Con Vinculo", user=self.user_a)
        self._add_project_member(project, self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(
            budget,
            parent_id=None,
            codigo="01",
            nombre="Acabados",
            descripcion=None,
            tipo="capitulo",
            orden=1,
        )
        item = self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.01",
            nombre="Pintura",
            descripcion=None,
            tipo="partida",
            unidad="m2",
            cantidad=Decimal("5"),
            precio_unitario_manual=Decimal("150"),
            orden=2,
        )
        item_row = self.db.get(PMPresupuestoPartida, item.id)
        linked_task = self._create_task(project, title="Tarea Pintura")
        create_budget_task_link(
            self.db,
            empresa_id=project.empresa_id,
            project_id=project.id,
            lineage_id=item_row.lineage_id,
            tarea_id=linked_task.id,
            source_presupuesto_id=budget.id,
            source_partida_id=item_row.id,
            source_capitulo_id=chapter.id,
            generated_from_budget=True,
            sync_status="linked",
        )

        updated = update_budget_item(
            self.db,
            self.pm_context_a,
            item_id=item.id,
            parent_id=item.parent_id,
            codigo="01.01A",
            nombre="Pintura final",
            descripcion="Con ajuste",
            tipo="partida",
            unidad="m2",
            cantidad=Decimal("6"),
            margen_pct=Decimal("10"),
            precio_unitario_manual=Decimal("175"),
            fecha_inicio_sugerida=date(2026, 8, 20),
            fecha_fin_sugerida=date(2026, 8, 21),
            responsable_sugerido_usuario_id=self.user_a.id,
            notas_planificacion="Ajuste de remate",
            orden=3,
            activo=True,
            provided_fields={
                "codigo",
                "nombre",
                "descripcion",
                "cantidad",
                "margen_pct",
                "precio_unitario_manual",
                "fecha_inicio_sugerida",
                "fecha_fin_sugerida",
                "responsable_sugerido_usuario_id",
                "notas_planificacion",
                "orden",
            },
            ip_address=None,
        )

        self.assertEqual(updated.linked_task_id, linked_task.id)
        self.assertEqual(updated.linked_task_title, "Tarea Pintura")
        self.assertEqual(updated.fecha_inicio_sugerida, date(2026, 8, 20))
        self.assertEqual(updated.fecha_fin_sugerida, date(2026, 8, 21))
        self.assertEqual(updated.responsable_sugerido_nombre, self.user_a.full_name)

    def test_create_budget_item_rejects_invalid_chapter_planning_and_non_member_responsible(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Validacion", user=self.user_a)
        budget = self._create_budget(project)
        outsider = self._create_additional_company_user(self.company_a, suffix="outsider")

        with self.assertRaises(HTTPException) as chapter_error:
            self._create_budget_item(
                budget,
                parent_id=None,
                codigo="01",
                nombre="Capitulo invalido",
                descripcion=None,
                tipo="capitulo",
                duracion_dias_sugerida=4,
                orden=1,
            )
        self.assertEqual(chapter_error.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("duración sugerida", chapter_error.exception.detail.lower())

        chapter = self._create_budget_item(
            budget,
            parent_id=None,
            codigo="02",
            nombre="Capitulo valido",
            descripcion=None,
            tipo="capitulo",
            orden=2,
        )
        with self.assertRaises(HTTPException) as member_error:
            self._create_budget_item(
                budget,
                parent_id=chapter.id,
                codigo="02.01",
                nombre="Partida sin miembro",
                descripcion=None,
                tipo="partida",
                unidad="servicio",
                cantidad=Decimal("1"),
                precio_unitario_manual=Decimal("500"),
                responsable_sugerido_usuario_id=outsider.id,
                orden=3,
            )
        self.assertEqual(member_error.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("miembro activo del proyecto", member_error.exception.detail.lower())

    def test_budget_item_prerequisites_support_crud_duplicate_guard_and_cycle_detection(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Dependencias", user=self.user_a)
        self._add_project_member(project, self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(
            budget,
            parent_id=None,
            codigo="01",
            nombre="Estructura",
            descripcion=None,
            tipo="capitulo",
            orden=1,
        )
        first = self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.01",
            nombre="Trazo",
            descripcion=None,
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("1"),
            precio_unitario_manual=Decimal("100"),
            orden=2,
        )
        second = self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.02",
            nombre="Colado",
            descripcion=None,
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("1"),
            precio_unitario_manual=Decimal("200"),
            orden=3,
        )

        prerequisite = create_budget_item_prerequisite(
            self.db,
            self.pm_context_a,
            item_id=second.id,
            prerequisito_partida_id=first.id,
            tipo_dependencia="finish_to_start",
            desfase_dias=2,
            ip_address=None,
        )
        self.assertEqual(prerequisite.prerequisito_partida_id, first.id)
        self.assertEqual(prerequisite.prerequisito_nombre, "Trazo")
        self.assertEqual(prerequisite.desfase_dias, 2)

        with self.assertRaises(HTTPException) as duplicate_error:
            create_budget_item_prerequisite(
                self.db,
                self.pm_context_a,
                item_id=second.id,
                prerequisito_partida_id=first.id,
                tipo_dependencia="finish_to_start",
                desfase_dias=0,
                ip_address=None,
            )
        self.assertEqual(duplicate_error.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("ya tiene ese requisito previo", duplicate_error.exception.detail.lower())

        with self.assertRaises(HTTPException) as cycle_error:
            create_budget_item_prerequisite(
                self.db,
                self.pm_context_a,
                item_id=first.id,
                prerequisito_partida_id=second.id,
                tipo_dependencia="finish_to_start",
                desfase_dias=0,
                ip_address=None,
            )
        self.assertEqual(cycle_error.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("crea un ciclo", cycle_error.exception.detail.lower())

        deleted = delete_budget_item_prerequisite(
            self.db,
            self.pm_context_a,
            item_id=second.id,
            prerequisite_id=prerequisite.id,
            ip_address=None,
        )
        self.assertEqual(deleted.id, prerequisite.id)
        remaining = self.db.scalars(
            select(PMPresupuestoPartidaPrerequisito).where(
                PMPresupuestoPartidaPrerequisito.empresa_id == self.company_a.id,
                PMPresupuestoPartidaPrerequisito.partida_id == second.id,
            )
        ).all()
        self.assertEqual(remaining, [])

    def test_preview_includes_planning_suggestions_and_prerequisites(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Preview", user=self.user_a)
        self._add_project_member(project, self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(
            budget,
            parent_id=None,
            codigo="01",
            nombre="Obra civil",
            descripcion=None,
            tipo="capitulo",
            fecha_inicio_sugerida=date(2026, 8, 1),
            fecha_fin_sugerida=date(2026, 8, 15),
            notas_planificacion="Bloque principal",
            orden=1,
        )
        first = self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.01",
            nombre="Trazo",
            descripcion="Inicio",
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("1"),
            precio_unitario_manual=Decimal("100"),
            fecha_inicio_sugerida=date(2026, 8, 1),
            fecha_fin_sugerida=date(2026, 8, 2),
            responsable_sugerido_usuario_id=self.user_a.id,
            notas_planificacion="Arranque",
            orden=2,
        )
        second = self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.02",
            nombre="Colado",
            descripcion="Siguiente paso",
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("1"),
            precio_unitario_manual=Decimal("200"),
            fecha_inicio_sugerida=date(2026, 8, 3),
            duracion_dias_sugerida=2,
            responsable_sugerido_usuario_id=self.user_a.id,
            notas_planificacion="Coordinar concreto",
            orden=3,
        )
        create_budget_item_prerequisite(
            self.db,
            self.pm_context_a,
            item_id=second.id,
            prerequisito_partida_id=first.id,
            tipo_dependencia="finish_to_start",
            desfase_dias=1,
            ip_address=None,
        )
        budget.estatus = "aprobado"
        self.db.flush()

        preview = get_budget_plan_preview(self.db, self.pm_context_a, budget_id=budget.id)
        second_preview = self._find_preview_item(preview, "Colado")

        self.assertEqual(preview.summary.create, 2)
        self.assertEqual(preview.chapters[0].chapter.target_start_date, date(2026, 8, 1))
        self.assertEqual(preview.chapters[0].chapter.target_end_date, date(2026, 8, 15))
        self.assertEqual(second_preview.suggested_start_date, date(2026, 8, 3))
        self.assertEqual(second_preview.suggested_end_date, date(2026, 8, 4))
        self.assertEqual(second_preview.suggested_duration_days, 2)
        self.assertEqual(second_preview.suggested_responsible_id, self.user_a.id)
        self.assertEqual(second_preview.suggested_responsible_name, self.user_a.full_name)
        self.assertEqual(second_preview.planning_notes, "Coordinar concreto")
        self.assertEqual(len(second_preview.suggested_prerequisites), 1)
        self.assertEqual(second_preview.suggested_prerequisites[0].name, "Trazo")

    def test_apply_creates_tasks_with_planning_fields_and_dependencies(self) -> None:
        project = self._create_project(self.company_a, name="Proyecto Apply", user=self.user_a)
        self._add_project_member(project, self.user_a)
        budget = self._create_budget(project)
        chapter = self._create_budget_item(
            budget,
            parent_id=None,
            codigo="01",
            nombre="Instalaciones",
            descripcion=None,
            tipo="capitulo",
            fecha_inicio_sugerida=date(2026, 8, 5),
            fecha_fin_sugerida=date(2026, 8, 15),
            orden=1,
        )
        first = self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.01",
            nombre="Canalizacion",
            descripcion="Primera tarea",
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("1"),
            precio_unitario_manual=Decimal("300"),
            fecha_inicio_sugerida=date(2026, 8, 5),
            fecha_fin_sugerida=date(2026, 8, 6),
            responsable_sugerido_usuario_id=self.user_a.id,
            orden=2,
        )
        second = self._create_budget_item(
            budget,
            parent_id=chapter.id,
            codigo="01.02",
            nombre="Cableado",
            descripcion="Segunda tarea",
            tipo="partida",
            unidad="servicio",
            cantidad=Decimal("1"),
            precio_unitario_manual=Decimal("450"),
            fecha_inicio_sugerida=date(2026, 8, 7),
            duracion_dias_sugerida=2,
            responsable_sugerido_usuario_id=self.user_a.id,
            orden=3,
        )
        create_budget_item_prerequisite(
            self.db,
            self.pm_context_a,
            item_id=second.id,
            prerequisito_partida_id=first.id,
            tipo_dependencia="finish_to_start",
            desfase_dias=0,
            ip_address=None,
        )
        budget.estatus = "aprobado"
        self.db.flush()

        preview = get_budget_plan_preview(self.db, self.pm_context_a, budget_id=budget.id)
        result = apply_budget_plan(
            self.db,
            self.pm_context_a,
            budget_id=budget.id,
            expected_preview_token=preview.preview_token,
            confirm=True,
            allow_draft=False,
            ip_address=None,
        )

        self.assertEqual(result.summary.created_tasks, 2)
        self.assertEqual(result.summary.tasks_with_dates, 2)
        self.assertEqual(result.summary.tasks_with_responsible, 2)
        self.assertEqual(result.summary.dependencies_created, 1)
        self.assertEqual(result.summary.dependencies_skipped, 0)

        links = {
            link.lineage_id: link
            for link in self.db.scalars(
                select(PMPresupuestoTaskLink).where(
                    PMPresupuestoTaskLink.empresa_id == self.company_a.id,
                    PMPresupuestoTaskLink.proyecto_id == project.id,
                )
            ).all()
        }
        first_task = self.db.get(PMTarea, links[first.lineage_id].tarea_id)
        second_task = self.db.get(PMTarea, links[second.lineage_id].tarea_id)
        self.assertEqual(first_task.fecha_inicio, date(2026, 8, 5))
        self.assertEqual(first_task.fecha_vencimiento, date(2026, 8, 6))
        self.assertEqual(first_task.asignado_user_id, self.user_a.id)
        self.assertEqual(second_task.fecha_inicio, date(2026, 8, 7))
        self.assertEqual(second_task.fecha_vencimiento, date(2026, 8, 8))
        self.assertEqual(second_task.asignado_user_id, self.user_a.id)

        dependencies = self.db.scalars(
            select(PMTareaDependencia).where(
                PMTareaDependencia.empresa_id == self.company_a.id,
                PMTareaDependencia.proyecto_id == project.id,
            )
        ).all()
        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0].tarea_id, second_task.id)
        self.assertEqual(dependencies[0].depende_de_tarea_id, first_task.id)

        planned_tasks = list_project_tasks_for_planning(
            self.db,
            empresa_id=self.company_a.id,
            project_id=project.id,
        )
        self.assertEqual(len(planned_tasks), 2)

    def test_pm_budget_initial_planning_schema_compiles_for_mssql(self) -> None:
        prerequisite_table_sql = str(CreateTable(PMPresupuestoPartidaPrerequisito.__table__).compile(dialect=mssql.dialect()))
        self.assertIn("pm_presupuesto_partida_prerequisitos", prerequisite_table_sql)
        self.assertIn("tipo_dependencia", prerequisite_table_sql)

        new_indexes = {
            index.name: str(CreateIndex(index).compile(dialect=mssql.dialect()))
            for index in PMPresupuestoPartidaPrerequisito.__table__.indexes
        }
        self.assertIn("ix_pm_presupuesto_partida_prerequisitos_partida_lineage", new_indexes)
        self.assertIn("ix_pm_presupuesto_partida_prerequisitos_prerequisito_lineage", new_indexes)

        responsible_index = next(
            index
            for index in PMPresupuestoPartida.__table__.indexes
            if index.name == "ix_pm_presupuesto_partidas_responsable_sugerido_usuario_id"
        )
        responsible_index_sql = str(CreateIndex(responsible_index).compile(dialect=mssql.dialect()))
        self.assertIn("responsable_sugerido_usuario_id", responsible_index_sql)


if __name__ == "__main__":
    unittest.main()
