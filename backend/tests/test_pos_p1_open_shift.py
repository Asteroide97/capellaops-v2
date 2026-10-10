from decimal import Decimal as D
import asyncio
import json
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy import event, select

from app.api.routes.pos import open_shift_endpoint
from app.api.routes import pos as routes
from app.models import AuditLog, Plan
from app.models.inventory import Almacen, MovimientoInventario
from app.models.pos import PosTurnoCaja
from app.schemas.pos import PosShiftOpenRequest, SaleCreateLineRequest
from app.services import pos
from tests import test_inventory_requisition_list as fixtures


class PosOpenShiftTests(unittest.TestCase):
    def setUp(self):
        fixtures.InventoryRequisitionListTests.setUp(self)
        self.db.add(Plan(code='pro', name='Synthetic POS', modules=['inventory', 'pos']))
        self.company.plan_code = self.other.plan_code = 'pro'
        self.db.commit()

    tearDown = fixtures.InventoryRequisitionListTests.tearDown
    call = fixtures.InventoryRequisitionListTests.call

    def endpoint(self, amount, warehouse=None, company=None):
        return open_shift_endpoint(PosShiftOpenRequest(warehouse_id=warehouse or self.warehouse.id,
            fondo_inicial=amount, notas=None), request=SimpleNamespace(client=None),
            context=SimpleNamespace(empresa=company or self.company, user=self.user), db=self.db)

    def test_zero_and_positive_funds_preserve_amount_tenant_and_warehouse(self):
        for index, amount in enumerate(['0', '1', '10.50']):
            with self.subTest(amount=amount):
                warehouse = Almacen(empresa_id=self.company.id, codigo=f'OPEN-{index}', nombre='Synthetic')
                self.db.add(warehouse)
                self.db.commit()
                shift = self.endpoint(amount, warehouse=warehouse.id)
                self.assertEqual(shift.fondo_inicial, D(amount))
                self.assertEqual((shift.empresa_id, shift.almacen_id), (self.company.id, warehouse.id))

    def test_direct_negative_fund_is_business_error_before_any_dml(self):
        writes = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if context.compiled is not None and not context.compiled.statement.is_select:
                writes.append(statement.split()[0])
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            for amount in ['-1', '-0.01']:
                with self.subTest(amount=amount):
                    try:
                        with self.assertRaises(HTTPException) as error:
                            pos.open_shift(self.db, empresa=self.company, user=self.user,
                                warehouse_id=self.warehouse.id, fondo_inicial=D(amount), notas=None, ip_address=None)
                        self.assertEqual(error.exception.status_code, 400)
                        self.assertEqual(error.exception.detail, 'El fondo inicial debe ser cero o positivo.')
                    finally:
                        self.db.rollback()
            self.assertEqual(writes, [])
            self.assertEqual(self.db.scalars(select(PosTurnoCaja)).all(), [])
            self.assertEqual(self.db.scalars(select(AuditLog)).all(), [])
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)

    def test_schema_rejects_negative_empty_and_invalid_text_before_route(self):
        for amount in ['-1', '-0.01', '', 'not-a-number']:
            with self.subTest(amount=amount):
                with self.assertRaises(ValidationError):
                    PosShiftOpenRequest(warehouse_id=self.warehouse.id, fondo_inicial=amount)
        self.assertEqual(self.db.scalars(select(PosTurnoCaja)).all(), [])

    def test_http_negative_fund_returns_422_without_shift_or_audit(self):
        api = FastAPI()
        api.include_router(routes.router)
        async def context():
            return SimpleNamespace(empresa=self.company, user=self.user)
        async def db():
            return self.db
        api.dependency_overrides[routes.get_pos_context] = context
        api.dependency_overrides[routes.get_db] = db
        async def scenario():
            messages = []
            body = json.dumps({'warehouse_id': self.warehouse.id, 'fondo_inicial': '-1'}).encode()
            received = False
            async def receive():
                nonlocal received
                if received:
                    await asyncio.sleep(0)
                    return {'type': 'http.disconnect'}
                received = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            async def send(message):
                messages.append(message)
            await asyncio.wait_for(api({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                'method': 'POST', 'scheme': 'http', 'path': '/pos/shift/open', 'raw_path': b'/pos/shift/open',
                'root_path': '', 'query_string': b'', 'headers': [(b'content-type', b'application/json')],
                'client': ('127.0.0.1', 1), 'server': ('fixture.invalid', 80)}, receive, send), timeout=5)
            self.assertEqual(next(message['status'] for message in messages if message['type'] == 'http.response.start'), 422)
        asyncio.run(scenario())
        self.assertEqual(self.db.scalars(select(PosTurnoCaja)).all(), [])
        self.assertEqual(self.db.scalars(select(AuditLog)).all(), [])

    def test_direct_invalid_and_nonfinite_funds_are_business_errors(self):
        for amount in ['invalid', D('NaN'), D('Infinity')]:
            with self.subTest(amount=str(amount)):
                with self.assertRaises(HTTPException) as error:
                    pos.open_shift(self.db, empresa=self.company, user=self.user, warehouse_id=self.warehouse.id,
                                   fondo_inicial=amount, notas=None, ip_address=None)
                self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(self.db.scalars(select(PosTurnoCaja)).all(), [])

    def test_duplicate_submit_creates_one_shift_and_one_open_audit(self):
        self.endpoint('1')
        with self.assertRaises(HTTPException) as error:
            self.endpoint('1')
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(len(self.db.scalars(select(PosTurnoCaja)).all()), 1)
        self.assertEqual(len(self.db.scalars(select(AuditLog).where(AuditLog.action == 'pos.shift.open')).all()), 1)

    def test_other_tenant_cannot_open_shift_in_this_warehouse(self):
        with self.assertRaises(HTTPException) as error:
            self.endpoint('1', company=self.other)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(self.db.scalars(select(PosTurnoCaja)).all(), [])

    def test_existing_suspend_resume_preserves_folio_values_and_stock(self):
        lines = [SaleCreateLineRequest(material_id=self.material.id, cantidad=D('2'), precio_unitario=D('10.01'),
                    descuento_unitario=D('0.02'), impuesto_tasa=D('0.16')),
                 SaleCreateLineRequest(tipo_linea='servicio', descripcion='Synthetic service', cantidad=D('1'),
                    precio_unitario=D('5'), descuento_unitario=D('0'), impuesto_tasa=D('0'))]
        sale = self.call(pos.create_suspended_sale, almacen_id=self.warehouse.id, cliente_nombre=None,
            cliente_email=None, metodo_pago='efectivo', descuento_global=D('1'), notas='Synthetic', items=lines, payments=[])
        resumed = pos.resume_suspended_sale(self.db, empresa=self.company, user=self.user, sale_id=sale.id)
        self.assertEqual((resumed.id, resumed.folio, resumed.total), (sale.id, sale.folio, sale.total))
        self.assertEqual([row.model_dump() for row in resumed.details], [row.model_dump() for row in sale.details])
        self.assertEqual(resumed.estatus, 'suspendida')
        self.assertEqual(self.db.scalars(select(MovimientoInventario)).all(), [])
