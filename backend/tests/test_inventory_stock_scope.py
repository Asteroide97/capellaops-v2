from decimal import Decimal
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from sqlalchemy import event, select

from app.api.routes.inventory import create_inventory_movement_bulk
from app.models.inventory import Almacen, Existencia, Material, MovimientoInventario
from app.schemas.inventory import InventoryBulkMovementCreateRequest
from app.services.inventory import get_kardex, list_stock
from tests import test_inventory_requisition_list as fixtures


class InventoryStockScopeTests(unittest.TestCase):
    setUp = fixtures.InventoryRequisitionListTests.setUp
    tearDown = fixtures.InventoryRequisitionListTests.tearDown

    def configure_stock(self, quantity):
        self.material.costo_unitario = Decimal('10')
        self.material.costo_promedio_actual = Decimal('10')
        self.db.scalar(select(Existencia)).cantidad = Decimal(quantity)
        self.b = Almacen(empresa_id=self.company.id, codigo='B', nombre='Warehouse B')
        self.empty = Almacen(empresa_id=self.company.id, codigo='C', nombre='Empty')
        self.db.add_all([self.b, self.empty])
        self.db.flush()
        self.db.add(Existencia(empresa_id=self.company.id, almacen_id=self.b.id,
                               material_id=self.material.id, cantidad=Decimal('1')))
        self.db.commit()

    def bulk(self, movement_type, items):
        payload = InventoryBulkMovementCreateRequest(almacen_id=self.warehouse.id, tipo=movement_type, items=items)
        return create_inventory_movement_bulk(payload, SimpleNamespace(client=None),
                                              SimpleNamespace(empresa=self.company, user=self.user), self.db)

    def test_kardex_existing_contract_is_scoped_and_read_only(self):
        self.configure_stock('4')
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split()[0].upper())
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            for warehouse, expected in [(None, 5), (self.warehouse.id, 4), (self.b.id, 1), (self.empty.id, 0)]:
                with self.subTest(warehouse=warehouse):
                    result = get_kardex(self.db, self.company.id, self.material.id, warehouse)
                    self.assertEqual(result.existencia_total, Decimal(expected))
                    self.assertEqual(result.material.valor_inventario, Decimal('50'))
                    self.assertEqual(result.material.costo_promedio_actual, Decimal('10'))
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        self.assertFalse(set(statements) & {'INSERT', 'UPDATE', 'DELETE'})
        self.assertEqual(self.db.scalars(select(MovimientoInventario)).all(), [])

    def test_stock_lookup_and_tenant_isolation(self):
        self.configure_stock('9')
        for warehouse, expected in [(self.warehouse.id, 9), (self.b.id, 1), (self.empty.id, 0)]:
            total, rows = list_stock(self.db, self.company.id, almacen_id=warehouse)
            self.assertEqual(sum(row.cantidad for row in rows), Decimal(expected))
            self.assertTrue(all(row.almacen_id == warehouse for row in rows))
        self.assertEqual(list_stock(self.db, self.other.id), (0, []))
        with self.assertRaises(HTTPException) as error:
            get_kardex(self.db, self.other.id, self.material.id, self.warehouse.id)
        self.assertEqual(error.exception.status_code, 404)

    def test_existing_entry_exit_and_local_insufficiency(self):
        self.configure_stock('9')
        with self.assertRaises(HTTPException) as error:
            self.bulk('salida', [{'material_id': self.material.id, 'cantidad': 10}])
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(get_kardex(self.db, self.company.id, self.material.id).existencia_total, Decimal('10'))
        self.bulk('entrada', [{'material_id': self.material.id, 'cantidad': 2}])
        self.bulk('salida', [{'material_id': self.material.id, 'cantidad': 3}])
        self.assertEqual(get_kardex(self.db, self.company.id, self.material.id, self.warehouse.id).existencia_total, Decimal('8'))
        self.assertEqual(get_kardex(self.db, self.company.id, self.material.id, self.b.id).existencia_total, Decimal('1'))

    def test_multiarticle_failure_still_rolls_back_all_lines(self):
        self.configure_stock('9')
        second = Material(empresa_id=self.company.id, sku='ONLY-B', nombre='Only B', unidad='pieza')
        self.db.add(second)
        self.db.flush()
        self.db.add(Existencia(empresa_id=self.company.id, almacen_id=self.b.id, material_id=second.id, cantidad=7))
        self.db.commit()
        with self.assertRaises(HTTPException):
            self.bulk('salida', [{'material_id': self.material.id, 'cantidad': 1}, {'material_id': second.id, 'cantidad': 1}])
        self.assertEqual(get_kardex(self.db, self.company.id, self.material.id, self.warehouse.id).existencia_total, Decimal('9'))
        self.assertEqual(get_kardex(self.db, self.company.id, second.id, self.warehouse.id).existencia_total, Decimal('0'))
        self.assertEqual(get_kardex(self.db, self.company.id, second.id).existencia_total, Decimal('7'))
        self.assertEqual(self.db.scalars(select(MovimientoInventario)).all(), [])

    def test_existing_multiarticle_success(self):
        self.configure_stock('9')
        second = Material(empresa_id=self.company.id, sku='SECOND', nombre='Second', unidad='pieza')
        self.db.add(second)
        self.db.flush()
        self.db.add(Existencia(empresa_id=self.company.id, almacen_id=self.warehouse.id, material_id=second.id, cantidad=5))
        self.db.commit()
        response = self.bulk('salida', [{'material_id': self.material.id, 'cantidad': 1}, {'material_id': second.id, 'cantidad': 2}])
        self.assertEqual(len(response.items), 2)
        self.assertEqual(get_kardex(self.db, self.company.id, self.material.id, self.warehouse.id).existencia_total, Decimal('8'))
        self.assertEqual(get_kardex(self.db, self.company.id, second.id, self.warehouse.id).existencia_total, Decimal('3'))
