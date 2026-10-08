from decimal import Decimal
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.dialects import mssql
from sqlalchemy.sql import visitors
from sqlalchemy.sql.selectable import Select

from app.models.inventory import Material
from app.models.procurement import Proveedor, OrdenCompra, OrdenCompraDetalle
from app.services import procurement
from tests import test_inventory_requisition_list as fixtures


class SupplierSummaryTests(unittest.TestCase):
    setUp = fixtures.InventoryRequisitionListTests.setUp
    tearDown = fixtures.InventoryRequisitionListTests.tearDown

    def supplier(self, company=None):
        supplier = Proveedor(empresa_id=(company or self.company).id, nombre='Synthetic supplier')
        self.db.add(supplier)
        self.db.commit()
        return supplier

    def order(self, supplier, state='borrador', company=None):
        order = OrdenCompra(empresa_id=(company or self.company).id, proveedor_id=supplier.id,
                            almacen_destino_id=self.warehouse.id, created_by_user_id=self.user.id,
                            folio=f'QA-{state}-{len(self.db.scalars(select(OrdenCompra)).all())}',
                            estatus=state, subtotal=Decimal('20'), total=Decimal('20'))
        self.db.add(order)
        self.db.flush()
        self.db.add(OrdenCompraDetalle(orden_compra_id=order.id, material_id=self.material.id,
                                      cantidad=Decimal('2'), costo_unitario=Decimal('10'),
                                      subtotal_linea=Decimal('20'), total_linea=Decimal('20')))
        self.db.commit()
        return order

    def test_no_orders_is_a_legitimate_zero(self):
        summary = procurement.get_supplier_summary(self.db, self.company.id, self.supplier().id)
        self.assertEqual(summary.ordenes_totales, 0)
        self.assertEqual(summary.ordenes_recientes, [])
        self.assertEqual(summary.materiales_asociados, 0)

    def test_draft_order_counts_in_total_but_not_open_orders(self):
        supplier = self.supplier()
        order = self.order(supplier)
        summary = procurement.get_supplier_summary(self.db, self.company.id, supplier.id)
        self.assertEqual(summary.ordenes_totales, 1)
        self.assertEqual(summary.ordenes_abiertas, 0)
        self.assertEqual([row.id for row in summary.ordenes_recientes], [order.id])
        self.assertEqual(summary.materiales_asociados, 1)
        self.assertEqual(summary.materiales_relacionados[0].ordenes_count, 1)

    def test_multiple_orders_counts_and_pagination(self):
        supplier = self.supplier()
        for state in ['borrador', 'emitida', 'recibida_parcial', 'recibida', 'cancelada']:
            self.order(supplier, state)
        summary = procurement.get_supplier_summary(self.db, self.company.id, supplier.id)
        self.assertEqual((summary.ordenes_totales, summary.ordenes_abiertas, summary.ordenes_recibidas), (5, 2, 1))
        self.assertEqual(summary.monto_total_comprado, Decimal('80'))
        self.assertEqual(summary.monto_pendiente_por_recibir, Decimal('40'))
        self.assertEqual(summary.materiales_relacionados[0].ordenes_count, 5)
        total, rows = procurement.list_supplier_materials(self.db, self.company.id, supplier.id, limit=1, offset=1)
        self.assertEqual((total, rows), (1, []))

    def test_query_failure_is_not_silently_a_zero_summary(self):
        supplier = self.supplier()
        with patch.object(procurement, 'list_supplier_materials', side_effect=RuntimeError('synthetic query failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic query failure'):
                procurement.get_supplier_summary(self.db, self.company.id, supplier.id)

    def test_orders_and_supplier_access_are_tenant_scoped(self):
        supplier = self.supplier()
        self.order(supplier)
        self.order(supplier, company=self.other)
        summary = procurement.get_supplier_summary(self.db, self.company.id, supplier.id)
        self.assertEqual(summary.ordenes_totales, 1)
        self.assertEqual(summary.materiales_relacionados[0].ordenes_count, 1)
        with self.assertRaises(HTTPException) as error:
            procurement.get_supplier_summary(self.db, self.other.id, supplier.id)
        self.assertEqual(error.exception.status_code, 404)

    def test_real_summary_queries_have_sql_server_valid_material_grouping(self):
        supplier = self.supplier()
        self.order(supplier)
        queries = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            if context.compiled is not None:
                queries.append(context.compiled.statement)

        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            procurement.get_supplier_summary(self.db, self.company.id, supplier.id)
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        found_material_query = False
        for query in queries:
            sql = str(query.compile(dialect=mssql.dialect()))
            self.assertNotIn(' IS 1', sql)
            for node in visitors.iterate(query):
                if not isinstance(node, Select):
                    continue
                material_columns = [col for col in node.selected_columns
                                    if getattr(col, 'table', None) is Material.__table__]
                if not material_columns:
                    continue
                found_material_query = True
                grouped = list(node._group_by_clauses)
                if grouped:
                    for column in material_columns:
                        self.assertTrue(any(column.compare(group) for group in grouped), sql)
        self.assertTrue(found_material_query)

    def test_material_sort_supports_orders_and_unordered_primary_materials(self):
        supplier = self.supplier()
        self.order(supplier)
        self.db.add(Material(empresa_id=self.company.id, proveedor_principal_id=supplier.id,
                             sku='PRIMARY', nombre='Primary only', unidad='pieza'))
        self.db.commit()
        total, rows = procurement.list_supplier_materials(self.db, self.company.id, supplier.id)
        self.assertEqual(total, 2)
        self.assertEqual(rows[0].material_id, self.material.id)
