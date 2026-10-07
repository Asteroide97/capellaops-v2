from datetime import datetime, timezone
from contextlib import closing
from decimal import Decimal
from types import SimpleNamespace
import unittest
from pathlib import Path
import sqlite3
import tempfile
import threading
import os
import subprocess
import sys
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, event, inspect, select, MetaData, Table
from sqlalchemy.dialects import mssql, postgresql, sqlite
from sqlalchemy.orm import Session

from app.api.routes.inventory import update_material
from app.models.inventory import Almacen, Existencia, MovimientoInventario
from app.models.procurement import Proveedor
from app.models.pm import PMProyecto, PMProyectoCostoResumen
from app.models.pos import Venta, VentaDetalle
from app.schemas.inventory import MaterialUpdateRequest
from app.schemas.procurement import PurchaseOrderReceiveLineRequest
from app.services import inventory as service, inventory_documents as documents, procurement
from app.services.pm import serialize_project_material_movement_event
from app.services.pos import resolve_sale_detail_estimated_cost, cancel_sale
from tests import test_inventory_requisition_list as fixtures


D = Decimal


class WeightedCostTests(unittest.TestCase):
    setUp = fixtures.InventoryRequisitionListTests.setUp
    tearDown = fixtures.InventoryRequisitionListTests.tearDown

    def seed(self, qty, avg, reference='10'):
        self.material.costo_unitario = D(reference)
        self.material.costo_promedio_actual = None if avg is None else D(avg)
        self.db.scalar(select(Existencia)).cantidad = D(qty)
        self.db.commit()

    def move(self, kind, qty=None, cost=None, target=None, warehouse=None, reference=None):
        result = service.apply_inventory_movement(
            self.db, empresa=self.company, user=self.user, almacen_id=warehouse or self.warehouse.id,
            material_id=self.material.id, tipo=kind, cantidad=D(qty) if qty is not None else None,
            cantidad_nueva=D(target) if target is not None else None,
            costo_unitario=D(cost) if cost is not None else None,
            referencia_tipo=reference, referencia_id=None, notas=None, ip_address=None,
        )
        self.db.commit()
        return result

    def check(self, qty, avg, value):
        result = service.get_kardex(self.db, self.company.id, self.material.id)
        self.assertEqual(result.existencia_total, D(qty))
        self.assertEqual(result.material.costo_promedio_actual, D(avg))
        self.assertEqual(result.material.valor_inventario, D(value))

    def document(self, fn, **kwargs):
        result = fn(self.db, empresa=self.company, user=self.user, ip_address=None, **kwargs)
        self.db.commit()
        return result

    def test_T1_entry_weighted_global(self):
        self.seed('5', '10')
        self.move('entrada', '5', '30')
        self.check('10', '20', '200')

    def test_T2_same_cost_entry(self):
        self.seed('10', '20')
        self.move('entrada', '5', '20')
        self.check('15', '20', '300')

    def test_T3_zero_stock_resets_average(self):
        self.seed('0', '20')
        self.move('entrada', '5', '30')
        self.check('5', '30', '150')

    def test_T4_decimal_rounding(self):
        self.seed('5', '10.1234')
        self.move('entrada', '3', '20.5678')
        self.check('8', '14.0401', '112.3208')

    def test_T5_exit_keeps_average_even_with_override(self):
        self.seed('10', '20')
        result = self.move('salida', '3', '99')
        self.check('7', '20', '140')
        self.assertEqual(result.costo_unitario_snapshot, D('20'))

    def test_T6_exit_to_zero_keeps_average(self):
        self.seed('1', '20')
        self.move('salida', '1')
        self.check('0', '20', '0')

    def test_T7_positive_adjustment_explicit_cost(self):
        self.seed('5', '20')
        self.move('ajuste', cost='40', target='10')
        self.check('10', '30', '300')

    def test_T8_positive_adjustment_without_cost(self):
        self.seed('5', '20')
        self.move('ajuste', target='10')
        self.check('10', '20', '200')

    def test_uncosted_adjustment_does_not_initialize_legacy_null_average(self):
        self.seed('5', None, '77')
        self.move('ajuste', target='10')
        self.assertIsNone(self.material.costo_promedio_actual)

    def test_T9_negative_adjustment_ignores_override(self):
        self.seed('10', '20')
        result = self.move('ajuste', cost='99', target='7')
        self.check('7', '20', '140')
        self.assertEqual(result.costo_unitario_snapshot, D('20'))

    def transfer(self, captured_cost):
        destination = Almacen(empresa_id=self.company.id, codigo='B', nombre='B')
        self.db.add(destination)
        self.db.commit()
        transfer = self.document(documents.create_transfer, folio=None, almacen_origen_id=self.warehouse.id,
                                 almacen_destino_id=destination.id, notas=None)
        self.document(documents.add_transfer_detail, transfer_id=transfer.id, material_id=self.material.id,
                      cantidad=D('3'), costo_unitario_snapshot=D(captured_cost))
        self.document(documents.confirm_transfer, transfer_id=transfer.id)
        return self.db.scalars(select(MovimientoInventario)).all()

    def test_T10_transfer_keeps_global_average(self):
        self.seed('10', '20')
        self.transfer('20')
        self.check('10', '20', '200')

    def test_T11_stale_transfer_snapshot_does_not_change_average(self):
        self.seed('10', '20')
        movements = self.transfer('99')
        self.check('10', '20', '200')
        self.assertTrue(all(row.costo_unitario_snapshot == D('20') for row in movements))
        self.assertTrue(all(row.costo_promedio_snapshot == D('20') for row in movements))

    def count(self, physical):
        count = self.document(documents.create_count, folio=None, almacen_id=self.warehouse.id, notas=None)
        self.document(documents.add_count_detail, count_id=count.id, material_id=self.material.id,
                      cantidad_fisica=D(physical))
        self.document(documents.apply_count, count_id=count.id)

    def test_T12_count_increase(self):
        self.seed('5', '20')
        self.count('10')
        self.check('10', '20', '200')

    def test_T13_count_decrease(self):
        self.seed('10', '20')
        self.count('7')
        self.check('7', '20', '140')

    def order(self):
        supplier = Proveedor(empresa_id=self.company.id, nombre='Test')
        self.db.add(supplier)
        self.db.commit()
        order = self.document(procurement.create_purchase_order, folio=None, proveedor_id=supplier.id,
                              almacen_destino_id=self.warehouse.id, notas=None)
        order = self.document(procurement.add_purchase_order_detail, order_id=order.id,
                              material_id=self.material.id, cantidad=D('5'), costo_unitario=D('30'))
        self.document(procurement.issue_purchase_order, order_id=order.id)
        return order

    def receive(self, order, qty):
        return self.document(procurement.receive_purchase_order, order_id=order.id,
                             items=[PurchaseOrderReceiveLineRequest(detail_id=order.details[0].id, cantidad_recibida=D(qty))],
                             almacen_id=self.warehouse.id, documento_referencia=None, notas_recepcion=None)

    def test_T14_purchase_receipt(self):
        self.seed('5', '10')
        self.receive(self.order(), '5')
        self.check('10', '20', '200')

    def test_T15_partial_receipts(self):
        self.seed('5', '10')
        order = self.order()
        self.receive(order, '2')
        self.check('7', '15.7143', '110.0001')
        self.receive(order, '3')
        self.check('10', '20', '200')

    def test_T16_reference_edit_never_changes_average(self):
        for avg in ('20', '0', None):
            with self.subTest(avg=avg):
                self.seed('5', avg)
                update_material(self.material.id, MaterialUpdateRequest(costo_unitario=D('99')),
                                SimpleNamespace(client=None), SimpleNamespace(empresa=self.company, user=self.user), self.db)
                self.assertEqual(self.material.costo_promedio_actual, D(avg) if avg is not None else None)

    def test_T17_entry_does_not_change_reference(self):
        self.seed('5', '10', '77')
        self.move('entrada', '5', '30')
        self.assertEqual(self.material.costo_unitario, D('77'))

    def test_T18_entry_snapshots_separate_cost_and_average(self):
        self.seed('5', '10')
        result = self.move('entrada', '5', '30')
        self.assertEqual(result.costo_unitario_snapshot, D('30'))
        self.assertEqual(result.costo_promedio_snapshot, D('20'))
        self.assertEqual(result.costo_total_snapshot, D('150'))

    def test_T19_exit_snapshot(self):
        self.seed('10', '20')
        result = self.move('salida', '3')
        self.assertEqual(result.costo_unitario_snapshot, D('20'))
        self.assertEqual(result.costo_promedio_snapshot, D('20'))
        self.assertEqual(result.costo_total_snapshot, D('60'))

    def test_T20_historical_snapshots_unchanged(self):
        self.seed('5', '10')
        historical = MovimientoInventario(empresa_id=self.company.id, almacen_id=self.warehouse.id,
            material_id=self.material.id, tipo='entrada', cantidad=D('5'), cantidad_anterior=D('0'),
            cantidad_nueva=D('5'), costo_unitario_snapshot=D('10'), costo_promedio_snapshot=D('7'), created_by=self.user.id)
        self.db.add(historical)
        self.db.commit()
        before = (historical.costo_unitario_snapshot, historical.costo_promedio_snapshot)
        self.move('entrada', '5', '30')
        self.db.refresh(historical)
        self.assertEqual(before, (historical.costo_unitario_snapshot, historical.costo_promedio_snapshot))

    def test_global_quantity_includes_other_warehouse(self):
        self.seed('4', '20')
        other = Almacen(empresa_id=self.company.id, codigo='B', nombre='B')
        self.db.add(other)
        self.db.flush()
        self.db.add(Existencia(empresa_id=self.company.id, almacen_id=other.id, material_id=self.material.id, cantidad=D('1')))
        self.db.commit()
        self.move('entrada', '5', '40')
        self.check('10', '30', '300')

    def test_manual_reference_cannot_impersonate_transfer_costing(self):
        self.seed('5', '10')
        self.move('entrada', '5', '30', reference='transferencia_entrada')
        self.check('10', '20', '200')

    def test_null_average_seeds_from_reference_but_zero_is_real_cost(self):
        for avg, expected in [(None, '20'), ('0', '15')]:
            with self.subTest(avg=avg):
                self.seed('5', avg)
                self.move('entrada', '5', '30')
                self.assertEqual(self.material.costo_promedio_actual, D(expected))
        self.seed('0', '20', '77')
        self.move('entrada', '5', '0')
        self.check('5', '0', '0')

    def test_existing_average_cannot_be_edited(self):
        self.seed('5', '20')
        with self.assertRaises(HTTPException):
            update_material(self.material.id, MaterialUpdateRequest(costo_promedio_actual=D('99')),
                            SimpleNamespace(client=None), SimpleNamespace(empresa=self.company, user=self.user), self.db)
        self.assertEqual(self.material.costo_promedio_actual, D('20'))

    def test_new_and_legacy_pm_pos_snapshot_semantics(self):
        for policy, expected in [(None, '7'), ('weighted_global_v1', '10')]:
            row = MovimientoInventario(empresa_id=self.company.id, almacen_id=self.warehouse.id,
                material_id=self.material.id, tipo='entrada', referencia_tipo='DEVOLUCION_PROYECTO',
                cantidad=D('1'), cantidad_anterior=D('1'), cantidad_nueva=D('2'), created_by=self.user.id,
                costo_unitario_snapshot=D('10'), costo_promedio_snapshot=D('7'))
            row.costing_policy = policy
            row.id = 'test-movement'
            row.created_at = datetime.now(timezone.utc)
            result = serialize_project_material_movement_event(row, warehouse_name='A', material_name='M', material_sku='M', material_unit='pz')
            self.assertEqual(result.costo_unitario_snapshot, D(expected))
        row.costing_policy = 'weighted_global_v1'
        row.costo_unitario_snapshot = D('0')
        row.costo_promedio_snapshot = D('20')
        detail = SimpleNamespace(movimiento_inventario=row, material=self.material, costo_unitario_manual=None)
        self.assertEqual(resolve_sale_detail_estimated_cost(detail), D('0'))
        row.costing_policy = None
        row.costo_promedio_snapshot = D('0')
        self.material.costo_promedio_actual = D('0')
        self.material.costo_unitario = D('10')
        self.assertEqual(resolve_sale_detail_estimated_cost(detail), D('10'))

    def test_material_lock_is_real_mssql_and_precedes_stock_read(self):
        self.seed('5', '10')
        queries = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if context.compiled and getattr(context.compiled.statement, 'is_select', False):
                queries.append(context.compiled.statement)
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            self.move('entrada', '5', '30')
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        locks = [(i, query) for i, query in enumerate(queries)
                 if 'UPDLOCK' in str(query.compile(dialect=mssql.dialect()))]
        self.assertTrue(locks, 'with_for_update alone is ignored by MSSQL')
        i, query = locks[0]
        for dialect in (mssql.dialect(), postgresql.dialect(), sqlite.dialect()):
            sql = str(query.compile(dialect=dialect))
            self.assertNotIn('IS 1', sql)
        self.assertIn('HOLDLOCK', str(query.compile(dialect=mssql.dialect())))
        self.assertIn('FOR UPDATE', str(query.compile(dialect=postgresql.dialect())))
        stock_reads = [j for j, query in enumerate(queries) if 'FROM existencias' in str(query)]
        self.assertTrue(stock_reads)
        self.assertLess(i, min(stock_reads))

    def test_helper_decimal_quantity_zero_and_half_up(self):
        fn = getattr(service, 'weighted_average_cost', None)
        self.assertIsNotNone(fn)
        for args, expected in [((D('5'), D('10'), D('5'), D('30')), '20'),
                               ((D('0'), None, D('5'), D('30')), '30'),
                               ((D('5'), D('20'), D('0'), D('99')), '20'),
                               ((D('.5'), D('10'), D('1.5'), D('30')), '25'),
                               ((D('1'), D('0'), D('1'), D('0.0001')), '0.0001')]:
            self.assertEqual(fn(*args), D(expected))
            self.assertIsInstance(fn(*args), Decimal)

    def test_pm_return_uses_original_cost_not_new_average(self):
        self.seed('10', '20', '77')
        project = PMProyecto(empresa_id=self.company.id, nombre='Test', estatus='activo', activo=True)
        self.db.add(project)
        self.db.commit()
        self.document(service.consume_material_for_project, empresa_id=self.company.id,
                      proyecto_id=project.id, material_id=self.material.id, almacen_id=self.warehouse.id, cantidad=D('3'))
        self.move('entrada', '3', '40')
        self.document(service.return_material_from_project, empresa_id=self.company.id,
                      proyecto_id=project.id, material_id=self.material.id, almacen_id=self.warehouse.id, cantidad=D('3'))
        self.check('13', '24.6154', '320.0002')
        summary = self.db.scalar(select(PMProyectoCostoResumen).where(PMProyectoCostoResumen.proyecto_id == project.id))
        self.assertEqual(summary.costo_materiales_real, D('0'))

    def test_legacy_pm_return_uses_cost_originally_read_by_pm(self):
        legacy = MovimientoInventario(empresa_id=self.company.id, almacen_id=self.warehouse.id,
            material_id=self.material.id, proyecto_id='test-project', referencia_tipo='CONSUMO_PROYECTO',
            tipo='salida', cantidad=D('1'), cantidad_anterior=D('2'), cantidad_nueva=D('1'),
            costo_unitario_snapshot=D('10'), costo_promedio_snapshot=D('7'), created_by=self.user.id)
        self.db.add(legacy)
        self.db.commit()
        cost = service.resolve_project_return_unit_cost(self.db, empresa_id=self.company.id,
            project_id='test-project', material_id=self.material.id, almacen_id=self.warehouse.id)
        self.assertEqual(cost, D('7'))

    def test_pos_cancel_reenters_at_original_snapshot(self):
        self.seed('10', '20', '77')
        self.company.plan_code = 'pro'
        self.db.commit()
        original = self.move('salida', '3')
        sale = Venta(empresa_id=self.company.id, almacen_id=self.warehouse.id, folio='TEST', estatus='pagada',
                     usuario_id=self.user.id, subtotal=D('60'), total=D('60'), metodo_pago='efectivo',
                     monto_recibido=D('60'), cambio=D('0'))
        self.db.add(sale)
        self.db.flush()
        self.db.add(VentaDetalle(venta_id=sale.id, material_id=self.material.id, cantidad=D('3'),
            precio_unitario=D('20'), subtotal_linea=D('60'), total_linea=D('60'), sku_snapshot='M1',
            nombre_snapshot='Material', movimiento_inventario_id=original.id))
        self.db.commit()
        self.move('entrada', '3', '40')
        self.document(cancel_sale, sale_id=sale.id, reason='Test')
        self.check('13', '24.6154', '320.0002')

    def test_tenant_and_rollback_on_insufficient_stock(self):
        self.seed('5', '20')
        token = self.material.costing_token
        with self.assertRaises(HTTPException):
            self.move('salida', '6')
        self.db.rollback()
        self.check('5', '20', '100')
        self.assertEqual(self.material.costing_token, token)
        with self.assertRaises(HTTPException):
            service.get_material_for_company(self.db, self.other.id, self.material.id, for_update=True)
        self.assertEqual(self.db.scalars(select(MovimientoInventario)).all(), [])

    def test_new_average_marker_persists_in_new_session(self):
        self.seed('5', '10')
        movement = self.move('entrada', '5', '30')
        with Session(self.engine) as db:
            stored = db.get(MovimientoInventario, movement.id)
            self.assertEqual(stored.costing_policy, 'weighted_global_v1')
            self.assertEqual(service.movement_applied_cost(stored), D('30'))

    def test_migration_upgrade_downgrade_preserves_legacy_rows(self):
        backend = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='inventory-weighted-migration-') as directory:
            filename = Path(directory) / 'test.db'
            environment = {**os.environ, 'DATABASE_URL': f'sqlite:///{filename.as_posix()}'}
            def migrate(action, revision):
                result = subprocess.run([sys.executable, '-m', 'alembic', action, revision], cwd=backend,
                                        env=environment, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            migrate('upgrade', '20260929_0048')
            legacy = MovimientoInventario(empresa_id=self.company.id, almacen_id=self.warehouse.id,
                material_id=self.material.id, tipo='entrada', cantidad=D('1'), cantidad_anterior=D('0'),
                cantidad_nueva=D('1'), costo_unitario_snapshot=D('10'), costo_promedio_snapshot=D('7'), created_by=self.user.id)
            self.db.add(legacy)
            self.db.commit()
            engine = create_engine(environment['DATABASE_URL'])
            try:
                with engine.begin() as target, self.engine.connect() as source:
                    for name in ('planes', 'empresas', 'usuarios', 'almacenes', 'materiales', 'existencias', 'movimientos_inventario'):
                        if name not in inspect(engine).get_table_names():
                            continue
                        table = Table(name, MetaData(), autoload_with=target)
                        source_table = type(self.material).metadata.tables[name]
                        rows = [{key: value for key, value in row._mapping.items() if key in table.c}
                                for row in source.execute(select(source_table))]
                        if rows:
                            target.execute(table.insert(), rows)
            finally:
                engine.dispose()
            migrate('upgrade', 'head')
            engine = create_engine(environment['DATABASE_URL'])
            try:
                self.assertIn('costing_token', {c['name'] for c in inspect(engine).get_columns('materiales')})
                self.assertIn('costing_policy', {c['name'] for c in inspect(engine).get_columns('movimientos_inventario')})
                with Session(engine) as db:
                    stored = db.get(MovimientoInventario, legacy.id)
                    self.assertIsNone(stored.costing_policy)
                    self.assertEqual((stored.costo_unitario_snapshot, stored.costo_promedio_snapshot), (D('10'), D('7')))
                    self.assertIsNone(db.get(type(self.material), self.material.id).costing_token)
            finally:
                engine.dispose()
            migrate('downgrade', '20260929_0048')
            engine = create_engine(environment['DATABASE_URL'])
            try:
                self.assertNotIn('costing_token', {c['name'] for c in inspect(engine).get_columns('materiales')})
            finally:
                engine.dispose()

    def test_concurrent_sqlite_entries_reject_stale_writer_then_retry(self):
        self.seed('5', '10')
        company = SimpleNamespace(id=self.company.id, plan_code='basico', access_status='active', modules=[])
        user = SimpleNamespace(id=self.user.id, full_name='Test', is_active=True, is_superadmin=False)
        warehouse_id, material_id = self.warehouse.id, self.material.id
        with tempfile.TemporaryDirectory(prefix='inventory-weighted-concurrency-') as directory:
            filename = Path(directory) / 'test.db'
            with self.engine.connect() as source, closing(sqlite3.connect(filename)) as destination:
                source.connection.driver_connection.backup(destination)
            engine = create_engine(f'sqlite:///{filename.as_posix()}', connect_args={'timeout': 10})
            barrier = threading.Barrier(2, timeout=10)
            original = service.get_material_for_company
            results = []
            def load(*args, **kwargs):
                material = original(*args, **kwargs)
                barrier.wait()
                return material
            def worker(cost):
                try:
                    with Session(engine, autoflush=False) as db, db.begin():
                        service.apply_inventory_movement(db, empresa=company, user=user, almacen_id=warehouse_id,
                            material_id=material_id, tipo='entrada', cantidad=D('5'), cantidad_nueva=None,
                            costo_unitario=D(cost), referencia_tipo=None, referencia_id=None, notas=None, ip_address=None)
                    results.append((cost, 'ok'))
                except HTTPException as error:
                    results.append((cost, error.status_code))
                except Exception as error:
                    results.append((cost, repr(error)))
            try:
                with patch.object(service, 'get_material_for_company', side_effect=load):
                    threads = [threading.Thread(target=worker, args=(cost,)) for cost in ('30', '50')]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=15)
                    self.assertFalse(any(thread.is_alive() for thread in threads))
                self.assertCountEqual([status for _, status in results], ['ok', 409])
                loser = next(cost for cost, status in results if status == 409)
                with Session(engine) as db:
                    self.assertEqual(db.scalar(select(Existencia.cantidad)), D('10'))
                worker(loser)
                with Session(engine) as db:
                    self.assertEqual(db.scalar(select(Existencia.cantidad)), D('15'))
                    self.assertEqual(db.scalar(select(type(self.material).costo_promedio_actual)), D('30'))
                    self.assertEqual(len(db.scalars(select(MovimientoInventario)).all()), 2)
            finally:
                engine.dispose()


if __name__ == '__main__':
    unittest.main()
