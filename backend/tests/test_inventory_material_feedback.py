from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.dialects import mssql

from app.api.routes.inventory import create_material, update_material, get_materials
from app.schemas.inventory import MaterialCreateRequest, MaterialUpdateRequest
from tests import test_inventory_requisition_list as fixtures


class MaterialFeedbackTests(unittest.TestCase):
    setUp = fixtures.InventoryRequisitionListTests.setUp
    tearDown = fixtures.InventoryRequisitionListTests.tearDown

    def context(self, company=None):
        return SimpleNamespace(empresa=company or self.company, user=self.user)

    def create(self, sku, active=True, company=None):
        return create_material(MaterialCreateRequest(sku=sku, nombre=sku, categoria='Test', unidad='pieza', activo=active),
                               SimpleNamespace(client=None), self.context(company), self.db)

    def listing(self, company=None, **filters):
        return get_materials(context=self.context(company), db=self.db, limit=filters.pop('limit', 25),
                             offset=filters.pop('offset', 0), **filters)

    def test_global_registered_total_is_independent_of_filters_pages_and_active_state(self):
        self.create('MATCH-1')
        self.create('MATCH-2')
        self.create('ARCHIVE-1', False)
        self.create('ARCHIVE-2', False)
        for filters, expected in [({}, 5), ({'q': 'MATCH'}, 2), ({'q': 'NOT-FOUND'}, 0),
                                  ({'limit': 1, 'offset': 2}, 5), ({'activo': True}, 3), ({'activo': False}, 2)]:
            with self.subTest(filters=filters):
                response = self.listing(**filters)
                self.assertEqual(response.total, expected)
                self.assertEqual(response.registered_total, 5)
        self.assertEqual(self.listing(self.other).registered_total, 0)

    def test_registered_count_changes_only_for_new_material_not_activation_or_sku_edit(self):
        created = self.create('NEW')
        self.assertEqual(self.listing().registered_total, 2)
        for payload in [MaterialUpdateRequest(activo=False), MaterialUpdateRequest(activo=True), MaterialUpdateRequest(sku='RENAMED')]:
            update_material(created.id, payload, SimpleNamespace(client=None), self.context(), self.db)
            self.assertEqual(self.listing().registered_total, 2)

    def test_existing_duplicate_protection_create_edit_and_tenant_is_preserved(self):
        first = self.create('UNIQUE')
        second = self.create('OTHER')
        for action in [lambda: self.create('UNIQUE'),
                       lambda: update_material(second.id, MaterialUpdateRequest(sku='UNIQUE'),
                                               SimpleNamespace(client=None), self.context(), self.db)]:
            with self.assertRaises(HTTPException) as error:
                action()
            self.assertEqual(error.exception.status_code, 409)
            self.assertIn('El SKU ya existe en esta empresa', error.exception.detail)
        same = update_material(first.id, MaterialUpdateRequest(sku='UNIQUE'), SimpleNamespace(client=None), self.context(), self.db)
        self.assertEqual(same.sku, 'UNIQUE')
        self.assertEqual(self.create('UNIQUE', company=self.other).empresa_id, self.other.id)

    def test_registered_count_is_one_portable_read_without_joins_or_writes(self):
        self.create('MATCH')
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append((statement, context.compiled.statement))
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            self.listing(q='MATCH')
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        self.assertTrue(all(sql.lstrip().upper().startswith('SELECT') for sql, _ in statements))
        counts = [query for sql, query in statements if 'count(materiales.id)' in sql.lower()]
        self.assertEqual(len(counts), 1)
        compiled = str(counts[0].compile(dialect=mssql.dialect())).upper()
        self.assertNotIn('JOIN', compiled)
        self.assertIn('WHERE MATERIALES.EMPRESA_ID', compiled)
