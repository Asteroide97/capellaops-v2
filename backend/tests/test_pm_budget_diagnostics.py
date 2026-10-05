from decimal import Decimal
import unittest
from unittest.mock import patch
import io
import hashlib
import json

from sqlalchemy import event, select, update, text
from sqlalchemy.dialects import mssql, sqlite
from app.models.pm import PMPresupuesto, PMTarea, PMProyectoLineaBase, PMProyectoCostoResumen
from app.services.pm import add_budget_item_labor, add_budget_indirect, get_project_budget, get_project_baseline_readiness
from app.services.pm_budget_diagnostics import diagnose_budget_headers, diagnose_project_economics, repair_budget_headers
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
