import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace
import unittest

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.api.routes import inventory as routes
from app.db.session import get_db
from app.models import AuditLog
from app.models.inventory import Material, MovimientoInventario, Existencia
from app.schemas.inventory import MaterialCreateRequest, MaterialUpdateRequest
from app.services.inventory import list_materials
from tests import test_inventory_requisition_list as fixtures


MESSAGE = 'El stock mínimo no puede ser mayor que el stock máximo.'


class MaterialStockRangeTests(unittest.TestCase):
    setUp = fixtures.InventoryRequisitionListTests.setUp
    tearDown = fixtures.InventoryRequisitionListTests.tearDown

    def context(self, company=None):
        return SimpleNamespace(empresa=company or self.company, user=self.user)

    def request(self):
        return SimpleNamespace(client=None)

    def payload(self, **fields):
        return MaterialCreateRequest(sku='NEW', nombre='Test material', categoria='Test', unidad='pieza', **fields)

    def create(self, **fields):
        return routes.create_material(self.payload(**fields), self.request(), self.context(), self.db)

    def update(self, material_id, **fields):
        return routes.update_material(material_id, MaterialUpdateRequest(**fields), self.request(), self.context(), self.db)

    def http(self, method, path, body):
        # Exercise FastAPI validation/serialization without another test dependency.
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[routes.get_inventory_context] = self.context
        app.dependency_overrides[get_db] = lambda: self.db
        sent = []
        raw = json.dumps(body).encode()
        async def receive():
            return {'type': 'http.request', 'body': raw, 'more_body': False}
        async def send(message):
            sent.append(message)
        scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                 'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
                 'query_string': b'', 'headers': [(b'content-type', b'application/json')],
                 'client': ('127.0.0.1', 1), 'server': ('local-test', 80), 'root_path': ''}
        asyncio.run(app(scope, receive, send))
        status = next(message['status'] for message in sent if message['type'] == 'http.response.start')
        content = b''.join(message.get('body', b'') for message in sent if message['type'] == 'http.response.body')
        return status, json.loads(content)

    def test_valid_equal_and_default_schema_ranges(self):
        for minimum, maximum in [('2', '100'), ('100', '100'), ('0', '0')]:
            with self.subTest(minimum=minimum, maximum=maximum):
                for schema in [MaterialCreateRequest, MaterialUpdateRequest]:
                    fields = {'stock_minimo': minimum, 'stock_maximo': maximum}
                    if schema is MaterialCreateRequest:
                        fields.update(sku='TEST', nombre='Test', categoria='Test', unidad='pieza')
                    self.assertEqual(schema(**fields).stock_minimo, Decimal(minimum))
        self.assertEqual(self.payload().stock_maximo, Decimal('0'))

    def test_invalid_range_rejected_by_both_schemas(self):
        with self.assertRaisesRegex(ValidationError, MESSAGE):
            self.payload(stock_minimo=101, stock_maximo=100)
        with self.assertRaisesRegex(ValidationError, MESSAGE):
            MaterialUpdateRequest(stock_minimo=101, stock_maximo=100)

    def test_null_and_negative_contract_is_preserved(self):
        for fields in [{'stock_minimo': None, 'stock_maximo': 100},
                       {'stock_minimo': 2, 'stock_maximo': None},
                       {'stock_minimo': None, 'stock_maximo': None}]:
            with self.subTest(fields=fields):
                with self.assertRaises(ValidationError):
                    self.payload(**fields)
                MaterialUpdateRequest(**fields)
        for schema in [MaterialCreateRequest, MaterialUpdateRequest]:
            for field in ['stock_minimo', 'stock_maximo']:
                with self.subTest(schema=schema, field=field), self.assertRaises(ValidationError):
                    if schema is MaterialCreateRequest:
                        self.payload(**{field: -1})
                    else:
                        schema(**{field: -1})

    def test_invalid_create_is_422_even_without_frontend(self):
        status, body = self.http('POST', '/inventory/materials', dict(
            sku='INVALID', nombre='Test', categoria='Test', unidad='pieza', stock_minimo=101, stock_maximo=100))
        self.assertEqual(status, 422)
        self.assertIn(MESSAGE, str(body))
        self.assertIsNone(self.db.scalar(select(Material).where(Material.sku == 'INVALID')))

    def test_partial_updates_use_persisted_other_limit_and_do_not_write(self):
        material = self.create(stock_minimo=2, stock_maximo=100)
        audits = len(self.db.scalars(select(AuditLog)).all())
        for fields in [{'stock_minimo': 101}, {'stock_maximo': 1},
                       {'stock_minimo': 101, 'stock_maximo': None},
                       {'stock_minimo': None, 'stock_maximo': 1}]:
            with self.subTest(fields=fields):
                with self.assertRaises(HTTPException) as error:
                    self.update(material.id, **fields)
                self.assertEqual(error.exception.status_code, 400)
                self.assertEqual(error.exception.detail, MESSAGE)
        self.db.expire_all()
        row = self.db.get(Material, material.id)
        self.assertEqual((row.stock_minimo, row.stock_maximo), (Decimal('2'), Decimal('100')))
        self.assertEqual(len(self.db.scalars(select(AuditLog)).all()), audits)

    def test_update_bypassed_frontend_returns_business_4xx(self):
        material = self.create(stock_minimo=2, stock_maximo=100)
        status, body = self.http('PUT', '/inventory/materials/' + material.id, {'stock_minimo': 101})
        self.assertEqual(status, 400)
        self.assertEqual(body['detail'], MESSAGE)
        status, body = self.http('PUT', '/inventory/materials/' + material.id,
                                 {'stock_minimo': 101, 'stock_maximo': 100})
        self.assertEqual(status, 422)
        self.assertIn(MESSAGE, str(body))

    def test_direct_create_with_constructed_schema_is_also_rejected(self):
        payload = self.payload().model_copy(update={'stock_minimo': Decimal('101'), 'stock_maximo': Decimal('100')})
        with self.assertRaises(HTTPException) as error:
            routes.create_material(payload, self.request(), self.context(), self.db)
        self.assertEqual(error.exception.status_code, 400)

    def test_valid_create_and_equal_update_through_http(self):
        status, material = self.http('POST', '/inventory/materials', dict(
            sku='HTTP-VALID', nombre='Test', categoria='Test', unidad='pieza', stock_minimo=2, stock_maximo=100))
        self.assertEqual(status, 201)
        status, updated = self.http('PUT', '/inventory/materials/' + material['id'],
                                    {'stock_minimo': 100, 'stock_maximo': 100})
        self.assertEqual(status, 200)
        self.assertEqual(Decimal(updated['stock_minimo']), Decimal(updated['stock_maximo']))

    def test_valid_create_edit_null_update_status_filters_and_duplicate_sku(self):
        material = self.create(stock_minimo=2, stock_maximo=100)
        edited = self.update(material.id, stock_minimo=100, stock_maximo=100)
        self.assertEqual(edited.stock_minimo, edited.stock_maximo)
        self.assertEqual(self.update(material.id, stock_minimo=50).stock_minimo, Decimal('50'))
        self.assertEqual(self.update(material.id, stock_maximo=60).stock_maximo, Decimal('60'))
        unchanged = self.update(material.id, stock_minimo=None, stock_maximo=None)
        self.assertEqual(unchanged.stock_minimo, Decimal('50'))
        with self.assertRaises(HTTPException) as error:
            self.create(stock_minimo=2, stock_maximo=100)
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(self.update(material.id, activo=False).activo)
        self.assertEqual(list_materials(self.db, self.company.id, q='NEW', activo=False)[0], 1)
        self.assertTrue(self.update(material.id, activo=True).activo)
        self.assertEqual(list_materials(self.db, self.company.id, categoria='Test', activo=True)[0], 1)
        self.assertEqual(list_materials(self.db, self.other.id)[0], 0)
        self.assertEqual(self.db.scalar(select(Existencia.cantidad)), Decimal('20'))
        self.assertEqual(self.db.scalars(select(MovimientoInventario)).all(), [])

    def test_foreign_tenant_update_rejected(self):
        material = self.create(stock_minimo=2, stock_maximo=100)
        with self.assertRaises(HTTPException) as error:
            routes.update_material(material.id, MaterialUpdateRequest(stock_minimo=50),
                                   self.request(), self.context(self.other), self.db)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
