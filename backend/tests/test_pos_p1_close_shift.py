from decimal import Decimal as D
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.api.routes.pos import close_shift_endpoint
from app.models import AuditLog
from app.models.inventory import Almacen
from app.models.pos import PosTurnoCaja
from app.schemas.pos import PosShiftCloseRequest
from app.services import pos
from tests import test_pos_p1_open_shift as fixtures


class PosCloseShiftTests(unittest.TestCase):
    setUp = fixtures.PosOpenShiftTests.setUp
    tearDown = fixtures.PosOpenShiftTests.tearDown
    call = fixtures.PosOpenShiftTests.call

    def open(self, code):
        warehouse = Almacen(empresa_id=self.company.id, codigo=code, nombre='Synthetic closing')
        self.db.add(warehouse)
        self.db.commit()
        return self.call(pos.open_shift, warehouse_id=warehouse.id, fondo_inicial=D('100'), notas=None)

    def close(self, warehouse_id, amount, company=None):
        return close_shift_endpoint(PosShiftCloseRequest(warehouse_id=warehouse_id, efectivo_contado=amount),
            request=SimpleNamespace(client=None),
            context=SimpleNamespace(empresa=company or self.company, user=self.user), db=self.db)

    def test_expected_and_counted_remain_independent_and_difference_is_correct(self):
        for counted, difference in [('0', '-100'), ('100', '0'), ('90', '-10'), ('110', '10')]:
            with self.subTest(counted=counted):
                shift = self.open('COUNT-' + counted)
                result = self.close(shift.almacen_id, counted)
                self.assertEqual(result.efectivo_esperado, D('100'))
                self.assertEqual(result.efectivo_contado, D(counted))
                self.assertEqual(result.diferencia, D(difference))
                self.assertEqual(result.estatus, 'cerrada')

    def test_direct_negative_rejected_before_writes_or_history_changes(self):
        shift = self.open('NEGATIVE')
        audits = len(self.db.scalars(select(AuditLog)).all())
        for amount in ['-1', '-0.01']:
            with self.subTest(amount=amount):
                try:
                    with self.assertRaises(HTTPException) as error:
                        pos.close_shift(self.db, empresa=self.company, user=self.user, warehouse_id=shift.almacen_id,
                            efectivo_contado=D(amount), notas=None, ip_address=None)
                    self.assertEqual(error.exception.status_code, 400)
                finally:
                    self.db.rollback()
        row = self.db.get(PosTurnoCaja, shift.id)
        self.assertEqual(row.estatus, 'abierta')
        self.assertIsNone(row.efectivo_contado)
        self.assertEqual(len(self.db.scalars(select(AuditLog)).all()), audits)

    def test_direct_missing_invalid_and_nonfinite_counts_are_not_zero(self):
        shift = self.open('INVALID')
        for amount in [None, '', 'invalid', D('NaN'), D('Infinity')]:
            with self.subTest(amount=str(amount)):
                try:
                    with self.assertRaises(HTTPException) as error:
                        pos.close_shift(self.db, empresa=self.company, user=self.user, warehouse_id=shift.almacen_id,
                            efectivo_contado=amount, notas=None, ip_address=None)
                    self.assertEqual(error.exception.status_code, 400)
                finally:
                    self.db.rollback()

    def test_schema_rejects_negative_and_empty_raw_request(self):
        for amount in ['', '-1', 'invalid', None]:
            with self.assertRaises(ValidationError):
                PosShiftCloseRequest(warehouse_id=self.warehouse.id, efectivo_contado=amount)

    def test_closed_shift_history_is_not_overwritten_by_a_second_close(self):
        shift = self.open('HISTORY')
        closed = self.close(shift.almacen_id, '90')
        previous = (closed.efectivo_contado, closed.diferencia, closed.closed_at)
        with self.assertRaises(HTTPException) as error:
            self.close(shift.almacen_id, '110')
        self.assertEqual(error.exception.status_code, 409)
        result = pos.get_shift_detail_response(self.db, self.company.id, shift.id)
        self.assertEqual((result.efectivo_contado, result.diferencia, result.closed_at), previous)

    def test_wrong_tenant_cannot_close_this_shift(self):
        shift = self.open('TENANT')
        with self.assertRaises(HTTPException) as error:
            self.close(shift.almacen_id, '100', company=self.other)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(self.db.get(PosTurnoCaja, shift.id).estatus, 'abierta')
