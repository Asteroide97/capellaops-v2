from contextlib import closing
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.inventory import run_inventory_write
from app.api.routes.inventory import create_inventory_movement
from app.schemas.inventory import InventoryMovementCreateRequest
from app.models.inventory import Existencia, MovimientoInventario
from app.models.pm import PMProyecto, PMProyectoCostoResumen, PMTarea
from app.services import inventory as service, pm
from tests import test_inventory_weighted_cost as fixtures


class ProjectReturnLockTests(unittest.TestCase):
    setUp = fixtures.WeightedCostTests.setUp
    tearDown = fixtures.WeightedCostTests.tearDown
    seed = fixtures.WeightedCostTests.seed
    document = fixtures.WeightedCostTests.document
    move = fixtures.WeightedCostTests.move

    def project(self):
        self.seed('10', '20', '77')
        project = PMProyecto(empresa_id=self.company.id, nombre='Test', estatus='activo', activo=True)
        self.db.add(project)
        self.db.commit()
        self.document(service.consume_material_for_project, empresa_id=self.company.id,
                      proyecto_id=project.id, material_id=self.material.id, almacen_id=self.warehouse.id, cantidad=D('3'))
        return project.id

    def return_quantity(self, pid, quantity):
        return run_inventory_write(self.db, 'fixture_return', lambda: service.return_material_from_project(
            self.db, empresa=self.company, user=self.user, empresa_id=self.company.id, proyecto_id=pid,
            material_id=self.material.id, almacen_id=self.warehouse.id, cantidad=D(quantity), ip_address=None))

    def state(self, pid, db=None):
        db = db or self.db
        db.expire_all()
        material = db.get(type(self.material), self.material.id)
        summary = db.scalar(select(PMProyectoCostoResumen).where(PMProyectoCostoResumen.proyecto_id == pid))
        return (db.scalar(select(Existencia.cantidad)),
                service.get_project_material_net_quantity(db, empresa_id=self.company.id, project_id=pid, material_id=self.material.id),
                summary.costo_materiales_real, material.costo_promedio_actual, material.costing_token,
                db.scalar(select(func.count(MovimientoInventario.id))))

    def test_R1_R2_R4_R5_serial_returns(self):
        pid = self.project()
        before = self.state(pid)
        with self.assertRaises(HTTPException):
            self.return_quantity(pid, '4')
        self.assertEqual(self.state(pid), before)
        self.return_quantity(pid, '2')
        after_partial = self.state(pid)
        self.assertEqual(after_partial[:3], (D('9'), D('1'), D('20')))
        with self.assertRaises(HTTPException):
            self.return_quantity(pid, '2')
        self.assertEqual(self.state(pid), after_partial)
        self.return_quantity(pid, '1')
        self.assertEqual(self.state(pid)[:3], (D('10'), D('0'), D('0')))

    def test_R1_full_return_and_R4_one_plus_two(self):
        for amounts in [('3',), ('1', '2')]:
            pid = self.project()
            for amount in amounts:
                self.return_quantity(pid, amount)
            self.assertEqual(self.state(pid)[1:3], (D('0'), D('0')))

    def test_R6_failure_after_movement_rolls_back_all_state(self):
        pid = self.project()
        self.move('entrada', '3', '40')
        before = self.state(pid)
        with self.assertLogs('app.api.routes.inventory', level='ERROR'), patch.object(pm, 'refresh_project_material_costs', side_effect=SQLAlchemyError('fixture failure')):
            with self.assertRaises(HTTPException):
                self.return_quantity(pid, '3')
        self.assertEqual(self.state(pid), before)

    def test_shared_ledger_writer_cannot_bypass_return_limit(self):
        pid = self.project()
        before = self.state(pid)
        payload = InventoryMovementCreateRequest(almacen_id=self.warehouse.id, material_id=self.material.id,
            tipo='entrada', cantidad=D('4'), costo_unitario=D('20'), es_proyecto=True,
            proyecto_id=pid, referencia_tipo='DEVOLUCION_PROYECTO')
        with self.assertRaises(HTTPException) as error:
            create_inventory_movement(payload, SimpleNamespace(client=None),
                SimpleNamespace(empresa=self.company, user=self.user), self.db)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.state(pid), before)

    def test_scoped_return_cannot_reuse_general_project_return(self):
        self.seed('10', '20', '77')
        project = PMProyecto(empresa_id=self.company.id, nombre='Test', estatus='activo', activo=True)
        self.db.add(project)
        self.db.flush()
        task = PMTarea(empresa_id=self.company.id, proyecto_id=project.id, titulo='Test task')
        self.db.add(task)
        self.db.commit()
        common = dict(empresa_id=self.company.id, proyecto_id=project.id, material_id=self.material.id,
                      almacen_id=self.warehouse.id, cantidad=D('3'))
        self.document(service.consume_material_for_project, **common, tarea_id=task.id)
        self.return_quantity(project.id, '3')
        before = self.state(project.id)
        with self.assertRaises(HTTPException) as error:
            run_inventory_write(self.db, 'fixture_scoped_return', lambda: service.return_material_from_project(
                self.db, empresa=self.company, user=self.user, ip_address=None, **common, tarea_id=task.id))
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.state(project.id), before)

    def test_lock_and_claim_precede_net_read_mssql_compiles(self):
        pid = self.project()
        events = []
        original_net = service.get_project_material_net_quantity
        original_claim = service.claim_material_costing_write
        def net(*args, **kwargs):
            events.append('net')
            return original_net(*args, **kwargs)
        def claim(*args, **kwargs):
            events.append('claim')
            return original_claim(*args, **kwargs)
        queries = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if context.compiled:
                queries.append(context.compiled.statement)
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            with patch.object(service, 'get_project_material_net_quantity', side_effect=net), patch.object(service, 'claim_material_costing_write', side_effect=claim):
                self.return_quantity(pid, '3')
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        self.assertLess(events.index('claim'), events.index('net'))
        sql = [str(query.compile(dialect=mssql.dialect())) for query in queries]
        self.assertTrue(any('WITH (UPDLOCK, HOLDLOCK)' in text and 'materiales.empresa_id' in text for text in sql))
        self.assertTrue(all(' IS 1' not in text and ' IS 0' not in text for text in sql))

    def test_R3_two_returns_one_wins_after_fresh_locked_read(self):
        pid = self.project()
        company = SimpleNamespace(id=self.company.id, plan_code='basico', access_status='active', modules=[])
        user = SimpleNamespace(id=self.user.id, full_name='Test', is_active=True, is_superadmin=False)
        mid, wid = self.material.id, self.warehouse.id
        with tempfile.TemporaryDirectory(prefix='inventory-pm-return-lock-') as directory:
            filename = Path(directory) / 'test.db'
            with self.engine.connect() as source, closing(sqlite3.connect(filename)) as target:
                source.connection.driver_connection.backup(target)
            engine = create_engine(f'sqlite:///{filename.as_posix()}', connect_args={'timeout': 10})
            second_lock_attempt = threading.Event()
            first_committed = threading.Event()
            original_load, original_net = service.get_material_for_company, service.get_project_material_net_quantity
            results = []
            def load(*args, **kwargs):
                if kwargs.get('for_update') and threading.current_thread().name == 'SECOND':
                    second_lock_attempt.set()
                    if not first_committed.wait(10):
                        raise RuntimeError('fixture timeout')
                return original_load(*args, **kwargs)
            def net(*args, **kwargs):
                quantity = original_net(*args, **kwargs)
                if threading.current_thread().name == 'FIRST' and not second_lock_attempt.wait(10):
                    raise RuntimeError('fixture timeout')
                return quantity
            def worker():
                name = threading.current_thread().name
                try:
                    with Session(engine, autoflush=False) as db, db.begin():
                        service.return_material_from_project(db, empresa=company, user=user, empresa_id=company.id,
                            proyecto_id=pid, material_id=mid, almacen_id=wid, cantidad=D('3'), ip_address=None)
                    results.append((name, 'ok'))
                except HTTPException as error:
                    results.append((name, error.status_code))
                except Exception as error:
                    results.append((name, repr(error)))
                finally:
                    if name == 'FIRST':
                        first_committed.set()
            try:
                with patch.object(service, 'get_material_for_company', side_effect=load), patch.object(service, 'get_project_material_net_quantity', side_effect=net):
                    threads = [threading.Thread(target=worker, name=name) for name in ('FIRST', 'SECOND')]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=15)
                    self.assertFalse(any(thread.is_alive() for thread in threads))
                self.assertCountEqual([result for _, result in results], ['ok', 409])
                with Session(engine) as db:
                    self.assertEqual(db.scalar(select(Existencia.cantidad)), D('10'))
                    self.assertEqual(original_net(db, empresa_id=company.id, project_id=pid, material_id=mid), D('0'))
                    self.assertEqual(db.scalar(select(PMProyectoCostoResumen.costo_materiales_real)), D('0'))
            finally:
                engine.dispose()
