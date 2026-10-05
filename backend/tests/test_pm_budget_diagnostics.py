from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
import copy
import unittest
from unittest.mock import patch
import io
import hashlib
import json

from sqlalchemy import create_engine, event, select, update, text
from sqlalchemy.dialects import mssql, sqlite
from app.models.pm import PMPresupuesto, PMPresupuestoPartida, PMTarea, PMProyectoLineaBase, PMProyectoCostoResumen
from app.models.inventory import Almacen, Material, MovimientoInventario
from app.services.pm import add_budget_item_labor, add_budget_indirect, get_project_budget, get_project_baseline_readiness, create_project_time_entry, add_project_material_plan, create_project_material_consumption_manual, refresh_project_material_costs
from app.services.pm_budget_diagnostics import diagnose_budget_headers, diagnose_project_economics, repair_budget_headers, repair_missing_project_summaries
from app.services.pm_budget_diagnostics import build_existing_summary_repair_plan, repair_existing_project_summary
from app.services.pm_budget_diagnostics import fingerprint_repair_state, REPAIR_FINGERPRINT_FIELDS
from app.scripts.diagnose_pm_budget_totals import main, read_only_guard
from tests import test_pm_budget_current_resolution as fixtures


class PMBudgetDiagnosticsTestCase(unittest.TestCase):
    setUpClass = classmethod(fixtures.PMBudgetCurrentResolutionTestCase.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.PMBudgetCurrentResolutionTestCase.tearDownClass.__func__)
    setUp = fixtures.PMBudgetCurrentResolutionTestCase.setUp
    tearDown = fixtures.PMBudgetCurrentResolutionTestCase.tearDown
    _create_company_user_context = fixtures.PMBudgetCurrentResolutionTestCase._create_company_user_context
    _context_for_company = fixtures.PMBudgetCurrentResolutionTestCase._context_for_company
    _user_for_company = fixtures.PMBudgetCurrentResolutionTestCase._user_for_company
    _create_project = fixtures.PMBudgetCurrentResolutionTestCase._create_project
    _create_budget = fixtures.PMBudgetCurrentResolutionTestCase._create_budget
    _create_budget_item = fixtures.PMBudgetCurrentResolutionTestCase._create_budget_item

    def fixture(self, company=None):
        company = company or self.company_a
        project = self._create_project(company, name="Diagnostic fixture")
        budget = self._create_budget(project)
        item = self._create_budget_item(budget, parent_id=None, codigo="QA", nombre="Service",
                                       tipo="partida", cantidad=Decimal("3"), precio_unitario_manual=Decimal("125.55"))
        context = self._context_for_company(company.id)
        add_budget_item_labor(self.db, context, item_id=item.id, rol=None, descripcion=None,
                              horas_por_unidad=Decimal("1"), tarifa_hora=Decimal("50"), ip_address=None)
        add_budget_indirect(self.db, context, budget_id=budget.id, nombre="Freight", tipo="monto",
                            porcentaje=None, monto=Decimal("20"), ip_address=None)
        self.db.commit()
        return project, budget

    def stale(self, budget):
        budget.total_costo, budget.total_venta = Decimal("120"), Decimal("251.10")
        self.db.commit()

    def snapshot(self):
        return {name: [tuple(str(value) for value in row) for row in self.db.execute(select(table)).all()]
                for name, table in PMPresupuesto.metadata.tables.items()}

    def test_atomic_existing_summary_repairs_both_rows(self):
        project, budget = self.fixture()
        self.stale(budget)
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        summary.presupuesto_detallado_costo = Decimal("120")
        summary.presupuesto_detallado_venta = Decimal("251.10")
        summary.presupuesto_estimado = Decimal("120")
        summary.margen_estimado = Decimal("131.10")
        self.db.commit()
        summary_id = summary.id
        plan = build_existing_summary_repair_plan(self.db, empresa_id=self.company_a.id,
            project_id=project.id, budget_id=budget.id, summary_id=summary.id)
        before = self.snapshot()
        repair_existing_project_summary(self.db, empresa_id=self.company_a.id,
            project_id=project.id, budget_id=budget.id, summary_id=summary.id,
            expected_fingerprint=plan["fingerprint"])
        self.db.commit()
        self.assertEqual(summary.id, summary_id)
        self.assertEqual(summary.presupuesto_detallado_costo, Decimal("170"))
        self.assertEqual(summary.presupuesto_detallado_venta, Decimal("376.65"))
        self.assertEqual(summary.margen_estimado, Decimal("206.65"))
        self.assertEqual(summary.presupuesto_estimado, Decimal("170"))
        self.assertEqual(summary.variacion_presupuesto, Decimal("170"))
        self.assertEqual(summary.variacion_vs_presupuesto_detallado, Decimal("170"))
        after = self.snapshot()
        for table in before:
            if table not in {"pm_presupuestos", "pm_proyecto_costo_resumen"}:
                self.assertEqual(before[table], after[table], table)
        for model, derived in ((PMPresupuesto, plan["header_after"]),
                               (PMProyectoCostoResumen, plan["summary_after"])):
            old = plan["before"][model.__tablename__]
            current = self.db.get(model, old["id"])
            for field, value in old.items():
                if field not in {*derived, "updated_at"}:
                    self.assertEqual(getattr(current, field), value, field)
        report = diagnose_project_economics(self.db, empresa_id=self.company_a.id)
        self.assertEqual(report["project_states"][0]["status"], "consistent")
        fresh = build_existing_summary_repair_plan(self.db, empresa_id=self.company_a.id,
            project_id=project.id, budget_id=budget.id, summary_id=summary.id)
        self.assertNotEqual(plan["fingerprint"], fresh["fingerprint"])
        with self.assertRaisesRegex(ValueError, "cambiaron"):
            repair_existing_project_summary(self.db, empresa_id=self.company_a.id,
                project_id=project.id, budget_id=budget.id, summary_id=summary.id,
                expected_fingerprint=plan["fingerprint"])
        self.assertEqual(after, self.snapshot())
        self.assertEqual(repair_existing_project_summary(self.db, empresa_id=self.company_a.id,
            project_id=project.id, budget_id=budget.id, summary_id=summary.id,
            expected_fingerprint=fresh["fingerprint"]), [])
        self.db.commit()
        self.assertEqual(after, self.snapshot())

    def atomic_fixture(self):
        project, budget = self.fixture()
        self.stale(budget)
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        kwargs = dict(empresa_id=self.company_a.id, project_id=project.id,
                      budget_id=budget.id, summary_id=summary.id)
        plan = build_existing_summary_repair_plan(self.db, **kwargs)
        self.db.rollback()
        return kwargs, plan

    def test_fingerprint_real_plan_is_stable_across_reload_and_collection_order(self):
        kwargs, _ = self.atomic_fixture()
        budget = self.db.get(PMPresupuesto, kwargs["budget_id"])
        self._create_budget_item(budget, parent_id=None, codigo="ORDER", nombre="Order test",
            tipo="partida", cantidad=Decimal("1"), precio_unitario_manual=Decimal("0"))
        self.db.commit()
        captured = []
        def capture(state):
            captured.append(copy.deepcopy(state))
            return fingerprint_repair_state(state)
        with patch("app.services.pm_budget_diagnostics.fingerprint_repair_state", side_effect=capture):
            first = build_existing_summary_repair_plan(self.db, **kwargs)
        self.db.rollback()
        self.db.expire_all()
        second = build_existing_summary_repair_plan(self.db, **kwargs)
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        state = captured[0]
        self.assertGreaterEqual(len(state["sources"]["pm_presupuesto_partidas"]), 2)
        for rows in state["sources"].values():
            rows.reverse()
        state = dict(reversed(list(state.items())))
        self.assertEqual(first["fingerprint"], fingerprint_repair_state(state))
        self.assertFalse(any("notas" in fields or "descripcion" in fields or "nombre" in fields
                             for fields in REPAIR_FINGERPRINT_FIELDS.values()))

    def test_fingerprint_canonical_decimal_uuid_and_utc_timestamp(self):
        identity = "6fc6f285-b36e-4b7b-9f59-31b993ad8083"
        state = {"id": identity, "cost": Decimal("170.00"),
                 "updated_at": datetime(2026, 10, 5, 12, tzinfo=timezone.utc)}
        expected = fingerprint_repair_state(state)
        equivalent = {"updated_at": datetime(2026, 10, 5, 6,
                      tzinfo=timezone(timedelta(hours=-6))), "cost": Decimal("170"), "id": UUID(identity)}
        self.assertEqual(expected, fingerprint_repair_state(equivalent))
        equivalent["updated_at"] = datetime(2026, 10, 5, 12)
        self.assertEqual(expected, fingerprint_repair_state(equivalent))
        equivalent["cost"] = Decimal("171")
        self.assertNotEqual(expected, fingerprint_repair_state(equivalent))

    def test_cli_isolation_reset_after_commit_and_failure_no_silent_retry(self):
        kwargs, plan = self.atomic_fixture()
        args = ["--sqlite-path", str(self.db_path), "--apply", "--repair-inconsistent-summary",
                "--empresa-id", kwargs["empresa_id"], "--proyecto-id", kwargs["project_id"],
                "--presupuesto-id", kwargs["budget_id"], "--resumen-id", kwargs["summary_id"],
                "--expected-fingerprint", plan["fingerprint"]]
        for failure in (False, True):
            engine = create_engine(f"sqlite:///{self.db_path.as_posix()}", isolation_level="READ UNCOMMITTED")
            calls = []
            original = engine.dialect.set_isolation_level
            def set_isolation(connection, level):
                calls.append(level)
                return original(connection, level)
            def repair(db, **selected):
                self.assertEqual(db.connection().get_isolation_level(), "SERIALIZABLE")
                if failure:
                    raise RuntimeError("Simulated serialization failure")
                return []
            with patch("app.scripts.diagnose_pm_budget_totals.create_engine", return_value=engine), \
                    patch.object(engine.dialect, "set_isolation_level", side_effect=set_isolation), \
                    patch("app.services.pm_budget_diagnostics.repair_existing_project_summary", side_effect=repair) as repair_mock, \
                    patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main(args), 1 if failure else 0)
            self.assertEqual(repair_mock.call_count, 1)
            self.assertIn("SERIALIZABLE", calls)
            self.assertEqual(calls[-1], "READ UNCOMMITTED")
            engine.dispose()

    def test_atomic_wrong_ids_abort_without_writes(self):
        kwargs, plan = self.atomic_fixture()
        other, other_budget = self.fixture(self.company_b)
        other_summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == other.id))
        wrong = dict(empresa_id=self.company_b.id, project_id=other.id,
                     budget_id=other_budget.id, summary_id=other_summary.id)
        before = self.snapshot()
        for field in kwargs:
            with self.assertRaises(ValueError):
                repair_existing_project_summary(self.db, **{**kwargs, field: wrong[field]},
                                                expected_fingerprint=plan["fingerprint"])
        self.assertEqual(before, self.snapshot())
        local_other, _ = self.fixture()
        local_summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == local_other.id))
        before = self.snapshot()
        for field, identity in (("project_id", local_other.id), ("summary_id", local_summary.id)):
            with self.assertRaises(ValueError):
                repair_existing_project_summary(self.db, **{**kwargs, field: identity},
                                                expected_fingerprint=plan["fingerprint"])
        self.assertEqual(before, self.snapshot())

    def test_atomic_stale_fingerprint_rejects_header_summary_and_source_changes(self):
        kwargs, plan = self.atomic_fixture()
        budget = self.db.get(PMPresupuesto, kwargs["budget_id"])
        budget.total_costo = Decimal("121")
        self.db.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "cambiaron"):
            repair_existing_project_summary(self.db, **kwargs, expected_fingerprint=plan["fingerprint"])
        self.assertEqual(before, self.snapshot())
        for model, field, value in ((PMProyectoCostoResumen, "costo_horas_real", Decimal("1")),
                                    (PMPresupuesto, "indirectos_pct", Decimal("1"))):
            plan = build_existing_summary_repair_plan(self.db, **kwargs)
            identity = kwargs["summary_id"] if model is PMProyectoCostoResumen else kwargs["budget_id"]
            setattr(self.db.get(model, identity), field, value)
            self.db.commit()
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "cambiaron"):
                repair_existing_project_summary(self.db, **kwargs, expected_fingerprint=plan["fingerprint"])
            self.assertEqual(before, self.snapshot())

    def test_atomic_empty_project_and_missing_summary_are_rejected(self):
        kwargs, plan = self.atomic_fixture()
        empty = self._create_project(self.company_a, name="Empty")
        self.db.commit()
        before = self.snapshot()
        with self.assertRaises(ValueError):
            repair_existing_project_summary(self.db, **{**kwargs, "project_id": empty.id},
                                            expected_fingerprint=plan["fingerprint"])
        summary = self.db.get(PMProyectoCostoResumen, kwargs["summary_id"])
        self.db.delete(summary)
        self.db.commit()
        missing_before = self.snapshot()
        with self.assertRaises(ValueError):
            repair_existing_project_summary(self.db, **kwargs, expected_fingerprint=plan["fingerprint"])
        self.assertEqual(missing_before, self.snapshot())

    def test_atomic_cas_queries_are_portable_and_zero_rowcount_rolls_back(self):
        kwargs, plan = self.atomic_fixture()
        summary = self.db.get(PMProyectoCostoResumen, kwargs["summary_id"])
        summary.presupuesto_detallado_costo = Decimal("120")
        self.db.commit()
        plan = build_existing_summary_repair_plan(self.db, **kwargs)
        before = self.snapshot()
        self.db.rollback()
        original = self.db.execute
        statements = []
        def execute(statement, *args, **kw):
            if getattr(statement, "is_update", False):
                statements.append(statement)
                if statement.table.name == "pm_proyecto_costo_resumen":
                    from types import SimpleNamespace
                    return SimpleNamespace(rowcount=0)
            return original(statement, *args, **kw)
        with patch.object(self.db, "execute", side_effect=execute):
            with self.assertRaisesRegex(ValueError, "durante"), self.db.begin():
                repair_existing_project_summary(self.db, **kwargs, expected_fingerprint=plan["fingerprint"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(len(statements), 2)
        for statement in statements:
            sql = str(statement.compile(dialect=mssql.dialect())).upper()
            self.assertNotRegex(sql, r"\bIS\s+[01]\b")
            self.assertNotIn("NOTAS =", sql)

    def test_atomic_no_longer_current_budget_is_rejected(self):
        kwargs, plan = self.atomic_fixture()
        budget = self.db.get(PMPresupuesto, kwargs["budget_id"])
        budget.estatus = "cancelado"
        self.db.commit()
        before = self.snapshot()
        with self.assertRaises(ValueError):
            repair_existing_project_summary(self.db, **kwargs, expected_fingerprint=plan["fingerprint"])
        self.assertEqual(before, self.snapshot())

    def test_atomic_changed_partida_rejects_old_diagnostic(self):
        kwargs, plan = self.atomic_fixture()
        item = self.db.scalar(select(PMPresupuestoPartida).where(
            PMPresupuestoPartida.presupuesto_id == kwargs["budget_id"]))
        item.cantidad = Decimal("4")
        self.db.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "cambiaron"):
            repair_existing_project_summary(self.db, **kwargs, expected_fingerprint=plan["fingerprint"])
        self.assertEqual(before, self.snapshot())

    def test_atomic_repair_preserves_separate_control_1096_25000(self):
        kwargs, plan = self.atomic_fixture()
        project = self._create_project(self.company_a, name="Control")
        budget = self._create_budget(project)
        item = self._create_budget_item(budget, parent_id=None, codigo="CONTROL", nombre="Control",
            tipo="partida", cantidad=Decimal("1"), precio_unitario_manual=Decimal("25000"))
        add_budget_item_labor(self.db, self.pm_context_a, item_id=item.id, rol=None, descripcion=None,
            horas_por_unidad=Decimal("8"), tarifa_hora=Decimal("137"), ip_address=None)
        self.db.commit()
        self.assertEqual(budget.total_costo, Decimal("1096"))
        self.assertEqual(budget.total_venta, Decimal("25000"))
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        before = {model.__tablename__: dict(self.db.execute(select(model.__table__).where(
            model.id == row.id)).mappings().one()) for model, row in
            ((PMPresupuesto, budget), (PMProyectoCostoResumen, summary))}
        repair_existing_project_summary(self.db, **kwargs, expected_fingerprint=plan["fingerprint"])
        self.db.commit()
        for model, row in ((PMPresupuesto, budget), (PMProyectoCostoResumen, summary)):
            self.assertEqual(before[model.__tablename__], dict(self.db.execute(select(model.__table__).where(
                model.id == row.id)).mappings().one()))

    def test_atomic_failure_rolls_back_header_and_summary(self):
        kwargs, plan = self.atomic_fixture()
        summary = self.db.get(PMProyectoCostoResumen, kwargs["summary_id"])
        summary.presupuesto_detallado_costo = Decimal("120")
        self.db.commit()
        plan = build_existing_summary_repair_plan(self.db, **kwargs)
        before = self.snapshot()
        self.db.rollback()
        def fail_summary(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("UPDATE PM_PROYECTO_COSTO_RESUMEN"):
                raise ValueError("Injected summary failure")
        event.listen(self.engine, "before_cursor_execute", fail_summary)
        try:
            with self.assertRaisesRegex(ValueError, "Injected"), self.db.begin():
                repair_existing_project_summary(self.db, **kwargs, expected_fingerprint=plan["fingerprint"])
        finally:
            event.remove(self.engine, "before_cursor_execute", fail_summary)
        self.assertEqual(before, self.snapshot())

    def test_atomic_consistent_summary_and_control_are_untouched(self):
        project, budget = self.fixture()
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        kwargs = dict(empresa_id=self.company_a.id, project_id=project.id,
                      budget_id=budget.id, summary_id=summary.id)
        plan = build_existing_summary_repair_plan(self.db, **kwargs)
        before = self.snapshot()
        self.assertEqual(repair_existing_project_summary(self.db, **kwargs,
            expected_fingerprint=plan["fingerprint"]), [])
        self.db.commit()
        self.assertEqual(before, self.snapshot())

    def test_atomic_cli_rejects_incomplete_or_mixed_modes_before_connection(self):
        for args in (["--repair-inconsistent-summary"],
                     ["--apply", "--repair-inconsistent-summary"],
                     ["--apply", "--repair-inconsistent-summary", "--repair-missing-summaries"]):
            with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO), \
                    patch("app.scripts.diagnose_pm_budget_totals.create_engine") as engine:
                main(["--empresa-id", self.company_a.id, *args])
            engine.assert_not_called()
        valid = ["--apply", "--repair-inconsistent-summary", "--proyecto-id", self.company_a.id,
                 "--presupuesto-id", self.company_a.id, "--resumen-id", self.company_a.id,
                 "--expected-fingerprint", "0" * 64]
        for flag in ("--proyecto-id", "--presupuesto-id", "--resumen-id", "--expected-fingerprint"):
            invalid = valid.copy()
            at = invalid.index(flag)
            del invalid[at:at + 2]
            with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO), \
                    patch("app.scripts.diagnose_pm_budget_totals.create_engine") as engine:
                main(["--empresa-id", self.company_a.id, *invalid])
            engine.assert_not_called()
        for flag, value in (("--empresa-id", self.company_a.id), ("--resumen-id", self.company_a.id),
                            ("--expected-fingerprint", "0" * 64)):
            with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO), \
                    patch("app.scripts.diagnose_pm_budget_totals.create_engine") as engine:
                main(["--empresa-id", self.company_a.id, *valid, flag, value])
            engine.assert_not_called()

    def test_consistent_budget_is_omitted_and_dry_run_has_no_writes(self):
        self.fixture()
        before = self.snapshot()
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split()[0].upper())
        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            self.assertEqual(diagnose_budget_headers(self.db, empresa_id=self.company_a.id), [])
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertFalse(set(statements) & {"INSERT", "UPDATE", "DELETE"})
        self.assertEqual(before, self.snapshot())

    def test_stale_header_report_and_cli_read_only(self):
        _, budget = self.fixture()
        self.stale(budget)
        company_id = self.company_a.id
        rows = diagnose_budget_headers(self.db, empresa_id=company_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_costo_recalculado"], Decimal("170"))
        self.assertEqual(rows[0]["total_venta_recalculado"], Decimal("376.65"))
        self.assertEqual(rows[0]["diferencia_costo"], Decimal("50"))
        self.assertEqual(rows[0]["diferencia_venta"], Decimal("125.55"))
        self.db.close()
        before = hashlib.sha256(self.db_path.read_bytes()).digest()
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(main(["--sqlite-path", str(self.db_path), "--empresa-id", company_id]), 0)
            self.assertIn('"170.00"', output.getvalue())
        self.assertEqual(before, hashlib.sha256(self.db_path.read_bytes()).digest())
        self.db = self.SessionLocal()

    def test_apply_repairs_only_header_and_is_idempotent(self):
        project, budget = self.fixture()
        self.db.add(PMTarea(empresa_id=self.company_a.id, proyecto_id=project.id, titulo="Keep task", activo=True))
        self.db.add(PMProyectoLineaBase(empresa_id=self.company_a.id, proyecto_id=project.id,
                                       nombre="Keep baseline", version=1, created_by=self.user_a.id, snapshot_json="{}"))
        self.db.commit()
        self.stale(budget)
        budget_id, company_id = budget.id, self.company_a.id
        before = self.snapshot()
        header_before = {column.name: getattr(budget, column.name) for column in PMPresupuesto.__table__.columns}
        self.assertEqual(len(repair_budget_headers(self.db, empresa_id=company_id, budget_ids={budget_id})), 1)
        self.db.commit()
        after = self.snapshot()
        for name in before:
            if name != "pm_presupuestos":
                self.assertEqual(before[name], after[name], name)
        row = self.db.get(PMPresupuesto, budget_id)
        self.assertEqual(row.total_costo, Decimal("170"))
        self.assertEqual(row.total_venta, Decimal("376.65"))
        derived = {"subtotal_costo", "subtotal_venta", "indirectos_monto", "total_costo", "total_venta",
                   "utilidad_monto", "utilidad_pct", "margen_estimado"}
        for name, value in header_before.items():
            if name not in derived:
                self.assertEqual(getattr(row, name), value, name)
        self.assertEqual(repair_budget_headers(self.db, empresa_id=company_id, budget_ids={budget_id}), [])
        self.db.commit()
        self.assertEqual(after, self.snapshot())
        official = get_project_budget(self.db, self.pm_context_a, project.id).budget
        self.assertEqual(official.total_costo, row.total_costo)
        self.assertEqual(official.total_venta, row.total_venta)

    def test_tenant_inactive_cancelled_and_replaced_are_excluded(self):
        _, first = self.fixture()
        _, other = self.fixture(self.company_b)
        self.stale(first)
        self.stale(other)
        first_id, other_id = first.id, other.id
        self.assertEqual([row["presupuesto_id"] for row in diagnose_budget_headers(self.db, empresa_id=self.company_a.id)], [first_id])
        with self.assertRaises(ValueError):
            repair_budget_headers(self.db, empresa_id=self.company_a.id, budget_ids={other_id})
        first.estatus = "cancelado"
        self.db.commit()
        self.assertEqual(diagnose_budget_headers(self.db, empresa_id=self.company_a.id), [])
        first.estatus, first.activo = "borrador", False
        self.db.commit()
        self.assertEqual(diagnose_budget_headers(self.db, empresa_id=self.company_a.id), [])

    def test_cli_apply_requires_explicit_ids_and_service_requires_clean_session(self):
        _, budget = self.fixture()
        with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO):
            main(["--sqlite-path", str(self.db_path), "--empresa-id", self.company_a.id, "--apply"])
        budget.nombre = "Pending change"
        with self.assertRaises(ValueError):
            diagnose_budget_headers(self.db, empresa_id=self.company_a.id)

    def test_percentage_indirects_match_official_and_consistent_headers_are_untouched(self):
        project, budget = self.fixture()
        _, consistent = self.fixture()
        consistent_id = consistent.id
        budget.indirectos_pct = Decimal("10")
        self.db.flush()
        add_budget_indirect(self.db, self.pm_context_a, budget_id=budget.id, nombre="Percentage",
                            tipo="porcentaje", porcentaje=Decimal("5"), monto=Decimal("0"), ip_address=None)
        official = get_project_budget(self.db, self.pm_context_a, project.id).budget
        self.assertEqual(official.total_costo, Decimal("192.50"))
        self.db.commit()
        self.stale(budget)
        budget_id = budget.id
        consistent_before = tuple(getattr(consistent, column.name) for column in PMPresupuesto.__table__.columns)
        rows = diagnose_budget_headers(self.db, empresa_id=self.company_a.id)
        self.assertEqual(rows[0]["total_costo_recalculado"], official.total_costo)
        repair_budget_headers(self.db, empresa_id=self.company_a.id, budget_ids={budget_id, consistent_id})
        self.db.commit()
        unchanged = self.db.get(PMPresupuesto, consistent_id)
        self.assertEqual(consistent_before, tuple(getattr(unchanged, column.name) for column in PMPresupuesto.__table__.columns))

    def test_guard_blocks_dml_ddl_raw_sql_and_commits(self):
        self.fixture()
        for statement in (
            update(PMPresupuesto).values(total_costo=0),
            text("DELETE FROM pm_presupuestos"),
            text("CREATE TABLE forbidden (id INTEGER)"),
            text("SELECT 1"),
        ):
            with read_only_guard(self.engine, self.db):
                with self.assertRaises(ValueError):
                    self.db.execute(statement)
        with read_only_guard(self.engine, self.db):
            self.assertIsNotNone(self.db.scalar(select(PMPresupuesto.id)))
            with self.assertRaises(ValueError):
                self.db.commit()

    def test_explicit_tenant_and_ids_are_required_before_engine_creation(self):
        for args in ([], ["--apply"], ["--empresa-id", " "],
                     ["--empresa-id", "QA", "--apply"],
                     ["--empresa-id", "QA", "--apply", "--presupuesto-id", " "]):
            with patch("app.scripts.diagnose_pm_budget_totals.create_engine") as create:
                with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO):
                    main(args)
                create.assert_not_called()
        with self.assertRaises(ValueError):
            repair_budget_headers(self.db, empresa_id="", budget_ids={"QA"})
        with self.assertRaises(ValueError):
            repair_budget_headers(self.db, empresa_id=self.company_a.id, budget_ids=set())

    def test_normal_environment_database_url_works_without_argument_credentials(self):
        self.fixture()
        with patch.dict("os.environ", {"DATABASE_URL": f"sqlite:///{self.db_path.as_posix()}"}):
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(main(["--empresa-id", self.company_a.id]), 0)
                report = json.loads(output.getvalue())
                self.assertEqual(report["budget_header_discrepancies"], [])
                self.assertEqual(report["project_cost_summary_discrepancies"], [])
        with patch.dict("os.environ", {"DATABASE_URL": ""}):
            with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO):
                main(["--empresa-id", self.company_a.id])

    def test_executed_queries_compile_for_sql_server_and_sqlite(self):
        _, budget = self.fixture()
        self._create_project(self.company_a, name="Empty portable queries")
        self.db.commit()
        self.stale(budget)
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if context.compiled is not None:
                statements.append(context.compiled.statement)
        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            diagnose_project_economics(self.db, empresa_id=self.company_a.id)
            repair_budget_headers(self.db, empresa_id=self.company_a.id, budget_ids={budget.id})
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertTrue(any(getattr(statement, "is_update", False) for statement in statements))
        for statement in statements:
            for dialect in (mssql.dialect(), sqlite.dialect()):
                compiled = str(statement.compile(dialect=dialect)).upper()
                self.assertNotRegex(compiled, r"\bIS\s+[01]\b")
                for forbidden in ("PRAGMA", "ROWID", "NULLS FIRST", "NULLS LAST", "BEGIN IMMEDIATE"):
                    self.assertNotIn(forbidden, compiled)

    def test_header_repair_does_not_automatically_repair_project_summary(self):
        project, budget = self.fixture()
        self.stale(budget)
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        summary.presupuesto_detallado_costo = Decimal("120")
        summary.presupuesto_detallado_venta = Decimal("251.10")
        self.db.commit()
        project_id, company_id, budget_id = project.id, self.company_a.id, budget.id
        repair_budget_headers(self.db, empresa_id=company_id, budget_ids={budget_id})
        self.db.commit()
        self.db.expire_all()
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project_id))
        self.assertEqual(summary.presupuesto_detallado_costo, Decimal("120"))
        self.assertEqual(summary.presupuesto_detallado_venta, Decimal("251.10"))
        readiness = get_project_baseline_readiness(self.db, self.pm_context_a, project_id=project_id)
        self.assertEqual(readiness.budget_context.planned_cost, Decimal("170"))
        self.assertEqual(readiness.budget_context.planned_sale, Decimal("376.65"))
        get_project_budget(self.db, self.pm_context_a, project_id)
        self.assertEqual(summary.presupuesto_detallado_costo, Decimal("170"))
        self.db.rollback()
        self.db.expire_all()
        self.assertEqual(summary.presupuesto_detallado_costo, Decimal("120"))

    def test_dry_run_distinguishes_all_four_consistency_combinations(self):
        for bad_header, bad_summary, expected_status in (
            (False, False, "consistent"), (True, False, "header_inconsistent"),
            (False, True, "summary_inconsistent"), (True, True, "both_inconsistent"),
        ):
            with self.subTest(status=expected_status):
                project, budget = self.fixture()
                summary = self.db.scalar(select(PMProyectoCostoResumen).where(
                    PMProyectoCostoResumen.proyecto_id == project.id))
                if bad_header:
                    self.stale(budget)
                if bad_summary:
                    summary.presupuesto_detallado_costo = Decimal("120")
                self.db.commit()
                before = self.snapshot()
                with read_only_guard(self.engine, self.db):
                    report = diagnose_project_economics(self.db, empresa_id=self.company_a.id, budget_ids={budget.id})
                self.assertEqual(report["project_states"][0]["status"], expected_status)
                self.assertEqual(bool(report["budget_header_discrepancies"]), bad_header)
                self.assertEqual(bool(report["project_cost_summary_discrepancies"]), bad_summary)
                self.assertEqual(report["requires_summary_repair"], bad_summary)
                self.assertEqual(before, self.snapshot())

    def test_missing_summary_is_reported_but_never_created(self):
        project, budget = self.fixture()
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        self.db.delete(summary)
        self.db.commit()
        before = self.snapshot()
        with read_only_guard(self.engine, self.db):
            report = diagnose_project_economics(self.db, empresa_id=self.company_a.id)
        row = report["project_cost_summary_discrepancies"][0]
        self.assertEqual(row["status"], "missing_summary")
        self.assertIsNone(row["resumen_id"])
        self.assertIsNone(row["valor_recalculado"])
        self.assertTrue(report["requires_summary_repair"])
        self.assertEqual(before, self.snapshot())

    def test_empty_projects_with_reference_amount_do_not_require_summary(self):
        for reference in (Decimal("0"), Decimal("18000400")):
            self._create_project(self.company_a, name="No economic activity", presupuesto_estimado=reference)
        self.db.commit()
        before = self.snapshot()
        with read_only_guard(self.engine, self.db):
            report = diagnose_project_economics(self.db, empresa_id=self.company_a.id)
        self.assertFalse(report["requires_summary_repair"])
        self.assertEqual(report["project_cost_summary_discrepancies"], [])
        self.assertTrue(all(row["status"] == "summary_not_required" for row in report["project_states"]))
        self.assertEqual(before, self.snapshot())

    def test_cancelled_budget_still_requires_missing_summary(self):
        project, budget = self.fixture()
        budget.activo, budget.estatus = False, "cancelado"
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        self.db.delete(summary)
        self.db.commit()
        with read_only_guard(self.engine, self.db):
            report = diagnose_project_economics(self.db, empresa_id=self.company_a.id)
        self.assertTrue(report["requires_summary_repair"])
        self.assertEqual(report["project_states"][0]["status"], "missing_summary")
        self.assertIn("budget_history", report["project_states"][0]["summary_requirement_reasons"])

    def test_time_without_budget_requires_summary_even_without_rate(self):
        project = self._create_project(self.company_a, name="Hours only")
        self.db.flush()
        create_project_time_entry(
            self.db, self.pm_context_a, project_id=project.id, tarea_id=None, usuario_id=None,
            usuario_email_snapshot=None, usuario_nombre_snapshot=None, fecha=date(2026, 10, 4),
            horas=Decimal("1.5"), descripcion="Actual work", moneda="MXN", ip_address=None,
        )
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        self.assertIsNotNone(summary)
        self.db.delete(summary)
        self.db.commit()
        with read_only_guard(self.engine, self.db):
            report = diagnose_project_economics(self.db, empresa_id=self.company_a.id)
        self.assertTrue(report["requires_summary_repair"])
        self.assertIn("time_entries", report["project_states"][0]["summary_requirement_reasons"])

    def test_missing_summary_top_level_excludes_empty_projects_in_mixed_tenant(self):
        empty = self._create_project(self.company_a, name="Empty")
        project, _ = self.fixture()
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        self.db.delete(summary)
        self.db.commit()
        report = diagnose_project_economics(self.db, empresa_id=self.company_a.id)
        self.assertTrue(report["requires_summary_repair"])
        states = {row["proyecto_id"]: row for row in report["project_states"]}
        self.assertFalse(states[empty.id]["requires_summary_repair"])
        self.assertEqual(len(report["project_cost_summary_discrepancies"]), 1)

    def test_missing_summary_repair_skips_empty_and_existing_and_is_idempotent(self):
        empty = self._create_project(self.company_a, name="Empty")
        existing, _ = self.fixture()
        missing, budget = self.fixture()
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == missing.id))
        self.db.delete(summary)
        self.db.commit()
        ids = {empty.id, existing.id, missing.id}
        before = self.snapshot()
        rows = repair_missing_project_summaries(self.db, empresa_id=self.company_a.id, project_ids=ids)
        self.assertEqual([row["proyecto_id"] for row in rows], [missing.id])
        self.db.commit()
        after = self.snapshot()
        for table in before:
            if table != "pm_proyecto_costo_resumen":
                self.assertEqual(before[table], after[table], table)
        for row in before["pm_proyecto_costo_resumen"]:
            self.assertIn(row, after["pm_proyecto_costo_resumen"])
        self.assertEqual(repair_missing_project_summaries(self.db, empresa_id=self.company_a.id, project_ids=ids), [])
        self.db.commit()
        self.assertEqual(after, self.snapshot())
        self.assertFalse(diagnose_project_economics(self.db, empresa_id=self.company_a.id)["requires_summary_repair"])

    def test_missing_summary_repair_preserves_stale_header_and_existing_bad_summary(self):
        missing, budget = self.fixture()
        self.stale(budget)
        existing, _ = self.fixture()
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == missing.id))
        self.db.delete(summary)
        existing_summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == existing.id))
        existing_summary.presupuesto_detallado_costo = Decimal("1")
        self.db.commit()
        before = self.snapshot()
        repair_missing_project_summaries(self.db, empresa_id=self.company_a.id, project_ids={missing.id, existing.id})
        self.db.commit()
        self.assertEqual(before["pm_presupuestos"], self.snapshot()["pm_presupuestos"])
        self.assertEqual(existing_summary.presupuesto_detallado_costo, Decimal("1"))
        self.assertEqual(diagnose_budget_headers(self.db, empresa_id=self.company_a.id)[0]["diferencia_costo"], Decimal("50"))

    def test_materials_without_budget_require_summary_and_repair_matches_official_sources(self):
        project = self._create_project(self.company_a, name="Materials only", presupuesto_estimado=Decimal("500"))
        material = Material(empresa_id=self.company_a.id, sku="SUMMARY-QA", nombre="Test material", unidad="pz")
        self.db.add(material)
        self.db.flush()
        add_project_material_plan(
            self.db, self.pm_context_a, project_id=project.id, task_id=None, material_id=material.id,
            cantidad_planificada=Decimal("3"), costo_unitario_estimado=Decimal("20"), observaciones=None, ip_address=None,
        )
        create_project_material_consumption_manual(
            self.db, self.pm_context_a, project_id=project.id, task_id=None, material_id=material.id,
            cantidad_consumida=Decimal("2"), costo_unitario_snapshot=Decimal("10"),
            documento_referencia=None, notas=None, ip_address=None,
        )
        create_project_time_entry(
            self.db, self.pm_context_a, project_id=project.id, tarea_id=None, usuario_id=None,
            usuario_email_snapshot=None, usuario_nombre_snapshot=None, fecha=date(2026, 10, 4),
            horas=Decimal("1.5"), descripcion=None, moneda="MXN", ip_address=None,
        )
        warehouse = Almacen(empresa_id=self.company_a.id, nombre="Test warehouse", codigo="SUMMARY-QA")
        self.db.add(warehouse)
        self.db.flush()
        for kind, quantity, reference, status in (
            ("salida", "3", None, "confirmado"),
            ("entrada", "1", "DEVOLUCION_PROYECTO", "confirmado"),
            ("salida", "99", None, "cancelado"),
        ):
            self.db.add(MovimientoInventario(
                empresa_id=self.company_a.id, almacen_id=warehouse.id, material_id=material.id,
                tipo=kind, cantidad=Decimal(quantity), cantidad_anterior=Decimal("100"),
                cantidad_nueva=Decimal("100"), referencia_tipo=reference, estatus=status,
                es_proyecto=True, proyecto_id=project.id, costo_promedio_snapshot=Decimal("7"),
                costo_unitario_snapshot=Decimal("10"), created_by=self.user_a.id,
            ))
        self.db.flush()
        refresh_project_material_costs(self.db, empresa_id=self.company_a.id, project_id=project.id)
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        self.assertEqual(summary.costo_materiales_real, Decimal("34"))
        self.assertEqual(summary.total_materiales_consumidos, Decimal("4"))
        self.db.commit()
        expected = {column.name: getattr(summary, column.name) for column in PMProyectoCostoResumen.__table__.columns
                    if column.name not in {"id", "created_at", "updated_at"}}
        self.db.delete(summary)
        self.db.commit()
        before = self.snapshot()
        with read_only_guard(self.engine, self.db):
            report = diagnose_project_economics(self.db, empresa_id=self.company_a.id)
        self.assertTrue(report["requires_summary_repair"])
        self.assertIn("material_plans", report["project_states"][0]["summary_requirement_reasons"])
        self.assertEqual(before, self.snapshot())
        repair_missing_project_summaries(self.db, empresa_id=self.company_a.id, project_ids={project.id})
        self.db.commit()
        recreated = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        for field, value in expected.items():
            self.assertEqual(getattr(recreated, field), value, field)
        for table, rows in before.items():
            if table != "pm_proyecto_costo_resumen":
                self.assertEqual(rows, self.snapshot()[table], table)

    def test_summary_repair_requires_explicit_tenant_and_ids_and_aborts_foreign_batch(self):
        local, _ = self.fixture()
        foreign, _ = self.fixture(self.company_b)
        before = self.snapshot()
        for tenant, ids in (("", {local.id}), (self.company_a.id, set()),
                            (self.company_a.id, {local.id, foreign.id})):
            with self.assertRaises(ValueError):
                repair_missing_project_summaries(self.db, empresa_id=tenant, project_ids=ids)
        self.assertEqual(before, self.snapshot())
        for args in (["--repair-missing-summaries"], ["--apply", "--repair-missing-summaries"],
                     ["--proyecto-id", local.id],
                     ["--apply", "--repair-missing-summaries", "--proyecto-id", local.id, "--presupuesto-id", "x"]):
            with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO), \
                    patch("app.scripts.diagnose_pm_budget_totals.create_engine") as create:
                main(["--empresa-id", self.company_a.id, *args])
            create.assert_not_called()

    def test_summary_repair_queries_compile_portably_and_dry_run_guard_blocks_creation(self):
        project, _ = self.fixture()
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        self.db.delete(summary)
        self.db.commit()
        before = self.snapshot()
        with self.assertRaises(ValueError), read_only_guard(self.engine, self.db):
            repair_missing_project_summaries(self.db, empresa_id=self.company_a.id, project_ids={project.id})
        self.assertEqual(before, self.snapshot())
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if context.compiled is not None and getattr(context.compiled.statement, "is_select", False):
                statements.append(context.compiled.statement)
        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            repair_missing_project_summaries(self.db, empresa_id=self.company_a.id, project_ids={project.id})
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertGreater(len(statements), 5)
        for statement in statements:
            for dialect in (mssql.dialect(), sqlite.dialect()):
                compiled = str(statement.compile(dialect=dialect)).upper()
                self.assertNotRegex(compiled, r"\bIS\s+[01]\b")
                self.assertNotIn("NULLS FIRST", compiled)
                self.assertNotIn("NULLS LAST", compiled)
        self.db.rollback()

    def test_cancelled_budget_summary_repair_uses_simple_reference_not_old_budget(self):
        project, budget = self.fixture()
        project.presupuesto_estimado = Decimal("500")
        budget.activo, budget.estatus = False, "cancelado"
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        self.db.delete(summary)
        self.db.commit()
        repair_missing_project_summaries(self.db, empresa_id=self.company_a.id, project_ids={project.id})
        self.db.commit()
        recreated = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        self.assertEqual(recreated.presupuesto_estimado, Decimal("500"))
        self.assertEqual(recreated.presupuesto_detallado_costo, Decimal("0"))
        self.assertEqual(recreated.presupuesto_origen, "simple")
        self.assertIsNone(recreated.margen_estimado)

    def test_empty_tenant_does_not_inherit_another_tenants_economic_activity(self):
        self._create_project(self.company_a, name="Empty local")
        self.fixture(self.company_b)
        self.db.commit()
        report = diagnose_project_economics(self.db, empresa_id=self.company_a.id)
        self.assertFalse(report["requires_summary_repair"])
        self.assertEqual(report["project_states"][0]["status"], "summary_not_required")

    def test_summary_diagnosis_is_tenant_scoped_and_requires_empresa(self):
        _, budget = self.fixture(self.company_b)
        report = diagnose_project_economics(self.db, empresa_id=self.company_a.id, budget_ids={budget.id})
        self.assertEqual(report["project_states"], [])
        self.assertEqual(report["project_cost_summary_discrepancies"], [])
        with self.assertRaises(ValueError):
            diagnose_project_economics(self.db, empresa_id="")

    def test_variations_use_stored_actual_components_without_verifying_or_writing_them(self):
        project, budget = self.fixture()
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        summary.costo_materiales_real, summary.costo_horas_real = Decimal("10"), Decimal("5")
        summary.costo_total_real = Decimal("999")
        self.db.commit()
        before = self.snapshot()
        with read_only_guard(self.engine, self.db):
            report = diagnose_project_economics(self.db, empresa_id=self.company_a.id)
        rows = {row["campo"]: row for row in report["project_cost_summary_discrepancies"]}
        self.assertEqual(rows["variacion_presupuesto"]["valor_recalculado"], Decimal("155"))
        self.assertEqual(rows["variacion_vs_presupuesto_detallado"]["valor_recalculado"], Decimal("155"))
        self.assertNotIn("costo_total_real", rows)
        self.assertIn("not_performed", report["actual_costs_validation"])
        self.assertEqual(before, self.snapshot())

    def test_header_apply_leaves_bad_summary_and_second_apply_changes_nothing(self):
        project, budget = self.fixture()
        self.stale(budget)
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(
            PMProyectoCostoResumen.proyecto_id == project.id))
        summary.presupuesto_detallado_venta = Decimal("251.10")
        self.db.commit()
        budget_id, company_id = budget.id, self.company_a.id
        summary_before = self.snapshot()["pm_proyecto_costo_resumen"]
        repair_budget_headers(self.db, empresa_id=company_id, budget_ids={budget_id})
        self.db.commit()
        self.assertEqual(summary_before, self.snapshot()["pm_proyecto_costo_resumen"])
        self.assertEqual(repair_budget_headers(self.db, empresa_id=company_id, budget_ids={budget_id}), [])
        self.db.commit()
        report = diagnose_project_economics(self.db, empresa_id=company_id, budget_ids={budget_id})
        self.assertEqual(report["project_states"][0]["status"], "summary_inconsistent")
        self.assertTrue(report["requires_summary_repair"])
