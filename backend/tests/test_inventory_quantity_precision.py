from decimal import Decimal as D
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select

from app.api.routes import inventory as routes
from app.models.inventory import Existencia, MovimientoInventario
from app.schemas import inventory as schemas, procurement, pm, pos
from app.services import inventory as service, inventory_documents as documents
from tests import test_inventory_weighted_cost as fixtures
from tests import test_inventory_material_stock_range as http_fixtures


class QuantityPrecisionTests(unittest.TestCase):
    setUp = fixtures.WeightedCostTests.setUp
    tearDown = fixtures.WeightedCostTests.tearDown
    seed = fixtures.WeightedCostTests.seed
    move = fixtures.WeightedCostTests.move
    document = fixtures.WeightedCostTests.document

    def snapshot(self):
        self.db.expire_all()
        return (self.db.scalar(select(Existencia.cantidad)), self.material.costo_promedio_actual,
                self.material.costo_unitario, self.material.costing_token,
                self.db.scalar(select(func.count(MovimientoInventario.id))))

    http = http_fixtures.MaterialStockRangeTests.http

    def context(self):
        return SimpleNamespace(empresa=self.company, user=self.user)

    def body(self, quantity):
        return dict(almacen_id=self.warehouse.id, material_id=self.material.id,
                    tipo='entrada', cantidad=quantity, costo_unitario='30')

    def test_Q1_Q3_exact_four_decimals_and_trailing_zeros_are_valid(self):
        for quantity in ('1', '1.2', '0.0001', '1.2345', '1.23450000'):
            with self.subTest(quantity=quantity):
                self.seed('5', '10', '77')
                status, body = self.http('POST', '/inventory/movements', self.body(quantity))
                self.assertEqual(status, 201, str(body))
                self.assertEqual(self.db.scalar(select(Existencia.cantidad)), D('5') + D(quantity))

    def test_Q2_Q4_http_rejection_has_no_lock_or_write(self):
        for quantity in ('0.00004', '1.23456'):
            with self.subTest(quantity=quantity):
                self.seed('5', '10', '77')
                before = self.snapshot()
                statements, locks = [], []
                def capture(conn, cursor, statement, parameters, context, executemany):
                    statements.append(statement.lstrip().split()[0].upper())
                    if context.compiled and getattr(context.compiled.statement, '_for_update_arg', None) is not None:
                        locks.append(statement)
                event.listen(self.engine, 'before_cursor_execute', capture)
                try:
                    status, body = self.http('POST', '/inventory/movements', self.body(quantity))
                finally:
                    event.remove(self.engine, 'before_cursor_execute', capture)
                self.assertEqual(status, 422, str(body))
                self.assertIn('La cantidad admite como máximo 4 decimales.', str(body))
                self.assertFalse(set(statements) & {'INSERT', 'UPDATE', 'DELETE'})
                self.assertEqual(locks, [])
                self.assertEqual(self.snapshot(), before)

    def test_Q5_invalid_bulk_is_rejected_before_first_line(self):
        self.seed('5', '10')
        before = self.snapshot()
        body = dict(almacen_id=self.warehouse.id, tipo='entrada', items=[
            dict(material_id=self.material.id, cantidad='1', costo_unitario='30'),
            dict(material_id=self.material.id, cantidad='0.00004', costo_unitario='30'),
        ])
        status, response = self.http('POST', '/inventory/movements/bulk', body)
        self.assertEqual(status, 422, str(response))
        self.assertEqual(self.snapshot(), before)
        items = [schemas.InventoryBulkMovementLineCreateRequest.model_construct(
            **{**line, 'cantidad': D(line['cantidad']), 'costo_unitario': D(line['costo_unitario'])}) for line in body['items']]
        payload = schemas.InventoryBulkMovementCreateRequest.model_construct(**{**body, 'items': items})
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split()[0].upper())
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            with self.assertRaises(HTTPException) as error:
                routes.create_inventory_movement_bulk(payload, SimpleNamespace(client=None),
                    SimpleNamespace(empresa=self.company, user=self.user), self.db)
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        self.assertEqual(error.exception.status_code, 400)
        self.assertFalse(set(statements) & {'INSERT', 'UPDATE', 'DELETE'})
        self.assertEqual(self.snapshot(), before)

    def test_internal_movement_bypass_rejected_before_claim(self):
        self.seed('5', '10')
        before = self.snapshot()
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split()[0].upper())
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            with self.assertRaises(HTTPException) as error:
                self.move('entrada', '0.00004', '30')
            self.assertEqual(error.exception.status_code, 400)
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
            self.db.rollback()
        self.assertFalse(set(statements) & {'INSERT', 'UPDATE', 'DELETE'})
        self.assertEqual(self.snapshot(), before)

    def test_Q6_Q7_Q8_shared_schema_contract(self):
        cases = [
            (schemas.TransferDetailCreateRequest, dict(material_id='fixture'), 'cantidad'),
            (schemas.TransferDetailUpdateRequest, {}, 'cantidad'),
            (schemas.CountDetailCreateRequest, dict(material_id='fixture'), 'cantidad_fisica'),
            (schemas.CountDetailUpdateRequest, {}, 'cantidad_fisica'),
            (schemas.InventoryMovementCreateRequest, dict(almacen_id='fixture', material_id='fixture', tipo='ajuste'), 'cantidad_nueva'),
            (procurement.RequisitionDetailCreateRequest, dict(material_id='fixture'), 'cantidad'),
            (procurement.RequisitionDetailUpdateRequest, {}, 'cantidad'),
            (procurement.RequisitionApproveLineRequest, dict(detail_id='fixture'), 'cantidad_aprobada'),
            (procurement.RequisitionFulfillLineRequest, dict(detail_id='fixture'), 'cantidad_surtir'),
            (procurement.PurchaseOrderDetailCreateRequest, dict(material_id='fixture', costo_unitario='30'), 'cantidad'),
            (procurement.PurchaseOrderDetailUpdateRequest, {}, 'cantidad'),
            (procurement.PurchaseOrderReceiveLineRequest, dict(detail_id='fixture'), 'cantidad'),
            (procurement.PurchaseOrderReceiveLineRequest, dict(detail_id='fixture'), 'cantidad_recibida'),
            (pm.PMProjectMaterialConsumeRequest, dict(material_id='fixture', almacen_id='fixture'), 'cantidad'),
            (pm.PMProjectMaterialReturnRequest, dict(material_id='fixture', almacen_id='fixture'), 'cantidad'),
            (pm.PMCreateProjectRequisitionItem, dict(plan_id='fixture'), 'cantidad_solicitada'),
            (pos.SaleCreateLineRequest, dict(tipo_linea='servicio', descripcion='Test'), 'cantidad'),
            (pos.SaleLineUpdateRequest, {}, 'cantidad'),
        ]
        for model, base, field in cases:
            with self.subTest(model=model.__name__, field=field):
                for valid in ('0.0001', '1.2345', '1.23450000'):
                    result = model.model_validate({**base, field: valid})
                    self.assertEqual(getattr(result, field), D(valid))
                for invalid in ('0.00004', '1.23456'):
                    with self.assertRaises(ValidationError):
                        model.model_validate({**base, field: invalid})

    def test_document_service_bypasses_rejected_before_lock(self):
        # Invalid quantities must fail before attempting to resolve the supplied document ID.
        calls = [
            lambda: self.document(documents.add_transfer_detail, transfer_id='missing', material_id=self.material.id,
                                  cantidad=D('1.23456'), costo_unitario_snapshot=None),
            lambda: self.document(documents.add_count_detail, count_id='missing', material_id=self.material.id,
                                  cantidad_fisica=D('1.23456')),
        ]
        for call in calls:
            with self.assertRaises(HTTPException) as error:
                call()
            self.assertEqual(error.exception.status_code, 400)
            self.assertIn('4 decimales', error.exception.detail)
            self.db.rollback()
