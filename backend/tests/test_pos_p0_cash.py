from decimal import Decimal as D
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.pos import manual_withdrawal_endpoint
from app.models import Empresa, Plan, Usuario
from app.models.inventory import Almacen
from app.models.pos import PosTurnoCaja, PosTurnoCajaMovimiento
from app.schemas.pos import PosShiftManualMovementRequest
from app.services import pos
from tests import test_inventory_requisition_list as fixtures


class PosCashRegressionTests(unittest.TestCase):
    def setUp(self):
        fixtures.InventoryRequisitionListTests.setUp(self)
        self.db.add(Plan(code='pro', name='Synthetic POS', modules=['inventory', 'pos']))
        self.company.plan_code = 'pro'
        self.other.plan_code = 'pro'
        self.db.commit()
        self.shift = self.call(pos.open_shift, warehouse_id=self.warehouse.id,
                               fondo_inicial=D('1'), notas=None)
        self.call(pos.add_shift_manual_movement, warehouse_id=self.warehouse.id,
                  movement_type='ingreso', amount=D('10'), reason='Synthetic income')

    tearDown = fixtures.InventoryRequisitionListTests.tearDown
    call = fixtures.InventoryRequisitionListTests.call

    def withdraw(self, amount, db=None, company=None, warehouse=None, user=None):
        return manual_withdrawal_endpoint(PosShiftManualMovementRequest(
            warehouse_id=warehouse or self.warehouse.id, monto=D(amount), motivo='Synthetic withdrawal'),
            request=SimpleNamespace(client=None),
            context=SimpleNamespace(empresa=company or self.company, user=user or self.user), db=db or self.db)

    def test_withdraw_less_than_available(self):
        self.assertEqual(self.withdraw('10').efectivo_esperado, D('1'))

    def test_withdraw_exact_available(self):
        self.assertEqual(self.withdraw('11').efectivo_esperado, D('0'))

    def test_income_still_increases_available_cash(self):
        result = self.call(pos.add_shift_manual_movement, warehouse_id=self.warehouse.id,
                           movement_type='ingreso', amount=D('5'), reason='Synthetic income')
        self.assertEqual(result.efectivo_esperado, D('16'))

    def test_failure_after_withdrawal_update_rolls_back_balance_and_movement(self):
        with patch.object(pos, 'create_audit_log', side_effect=SQLAlchemyError('synthetic failure')):
            with self.assertRaises(HTTPException) as error:
                self.withdraw('8')
        self.assertEqual(error.exception.status_code, 500)
        self.assertEqual(self.db.get(PosTurnoCaja, self.shift.id).retiros_manuales, D('0'))
        self.assertEqual(len(self.db.scalars(select(PosTurnoCajaMovimiento)).all()), 1)

    def test_excess_rejected_and_no_movement_persisted(self):
        with self.assertRaises(HTTPException) as error:
            self.withdraw('12')
        self.assertEqual(error.exception.status_code, 409)
        self.assertIn('efectivo disponible', error.exception.detail)
        self.assertEqual(len(self.db.scalars(select(PosTurnoCajaMovimiento)).all()), 1)
        self.assertEqual(self.db.get(PosTurnoCaja, self.shift.id).retiros_manuales, D('0'))

    def test_stale_session_cannot_spend_already_withdrawn_cash(self):
        with Session(self.engine, autoflush=False) as stale:
            cached = stale.get(PosTurnoCaja, self.shift.id)
            self.assertEqual(cached.retiros_manuales, D('0'))
            self.withdraw('10')
            with self.assertRaises(HTTPException) as error:
                self.withdraw('2', db=stale)
            self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.db.get(PosTurnoCaja, self.shift.id).retiros_manuales, D('10'))

    def test_tenant_and_other_warehouse_cannot_use_this_shift(self):
        with self.assertRaises(HTTPException):
            self.withdraw('1', company=self.other)
        other_warehouse = Almacen(empresa_id=self.company.id, codigo='POS-B', nombre='Synthetic B')
        self.db.add(other_warehouse)
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            self.withdraw('1', warehouse=other_warehouse.id)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.db.get(PosTurnoCaja, self.shift.id).retiros_manuales, D('0'))

    def test_real_queries_compile_mssql_lock_and_atomic_balance_condition(self):
        captured = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if context.compiled is not None:
                captured.append(context.compiled.statement)
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            self.withdraw('1')
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        sql = [str(query.compile(dialect=mssql.dialect())) for query in captured]
        self.assertTrue(any('UPDLOCK' in query and 'HOLDLOCK' in query for query in sql))
        updates = [query for query in sql if query.startswith('UPDATE pos_turnos_caja')]
        self.assertTrue(any('fondo_inicial' in query.split('WHERE')[-1]
                            and 'empresa_id' in query.split('WHERE')[-1] for query in updates))

    def test_two_concurrent_withdrawals_cannot_exceed_available(self):
        # Copy synthetic fixtures only to an isolated temporary SQLite database.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cash.db'
            raw = self.engine.raw_connection()
            try:
                with closing(sqlite3.connect(path)) as destination:
                    raw.driver_connection.backup(destination)
            finally:
                raw.close()
            engine = create_engine(f'sqlite:///{path}', connect_args={'timeout': 10})
            barrier = threading.Barrier(2, timeout=10)
            outcomes = []
            def synchronize(conn, cursor, statement, parameters, context, executemany):
                if statement.startswith('UPDATE pos_turnos_caja') and 'retiros_manuales' in statement:
                    barrier.wait()
            event.listen(engine, 'before_cursor_execute', synchronize)
            company_id, user_id, warehouse_id, shift_id = self.company.id, self.user.id, self.warehouse.id, self.shift.id
            def worker():
                try:
                    with Session(engine, autoflush=False) as db:
                        self.withdraw('8', db=db, company=db.get(Empresa, company_id),
                                      warehouse=warehouse_id, user=db.get(Usuario, user_id))
                    outcomes.append('ok')
                except HTTPException as exc:
                    outcomes.append(exc.status_code)
                except Exception as exc:
                    outcomes.append(type(exc).__name__)
            threads = [threading.Thread(target=worker) for _ in range(2)]
            try:
                for thread in threads: thread.start()
                for thread in threads: thread.join(20)
                self.assertFalse(any(thread.is_alive() for thread in threads))
                self.assertCountEqual(outcomes, ['ok', 409])
                with Session(engine) as db:
                    shift = db.get(PosTurnoCaja, shift_id)
                    self.assertEqual(pos.calculate_expected_cash(shift), D('3'))
                    withdrawals = db.scalars(select(PosTurnoCajaMovimiento).where(
                        PosTurnoCajaMovimiento.turno_id == shift_id, PosTurnoCajaMovimiento.tipo == 'retiro')).all()
                    self.assertEqual(sum((row.monto for row in withdrawals), D('0')), D('8'))
            finally:
                event.remove(engine, 'before_cursor_execute', synchronize)
                engine.dispose()
