from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable
from sqlalchemy.pool import StaticPool

from app.models import Empresa, EmpresaModulo, Plan, Usuario
from app.models.base import Base
from app.models.inventory import Almacen, Existencia, Material, MovimientoInventario
from app.schemas.procurement import RequisitionFulfillLineRequest, RequisitionListResponse
from app.services import procurement as service
from app.api.routes import procurement as routes


class InventoryRequisitionListTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        # Isolated fixtures need tables, not duplicated legacy index declarations.
        with self.engine.begin() as connection:
            for table in Base.metadata.sorted_tables:
                connection.execute(CreateTable(table))
        self.db = Session(self.engine, autoflush=False)
        plan = Plan(code='basico', name='Test', modules=['inventory'])
        self.db.add(plan)
        self.db.flush()
        self.company = Empresa(name='Test', slug='test', plan_code=plan.code, access_status='active', trial_ends_at=datetime.now(timezone.utc))
        self.other = Empresa(name='Other', slug='other', plan_code=plan.code, access_status='active', trial_ends_at=datetime.now(timezone.utc))
        self.user = Usuario(email='test@example.com', full_name='Test', password_hash='fixture')
        self.db.add_all([self.company, self.other, self.user])
        self.db.flush()
        self.db.add(EmpresaModulo(empresa_id=self.company.id, module_name='inventory', is_enabled=True))
        self.material = Material(empresa_id=self.company.id, sku='M1', nombre='Material', unidad='pieza')
        self.warehouse = Almacen(empresa_id=self.company.id, codigo='A', nombre='Warehouse')
        self.db.add_all([self.material, self.warehouse])
        self.db.flush()
        self.db.add(Existencia(empresa_id=self.company.id, material_id=self.material.id,
                               almacen_id=self.warehouse.id, cantidad=Decimal('20')))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def call(self, function, **kwargs):
        result = function(self.db, empresa=self.company, user=self.user, ip_address=None, **kwargs)
        self.db.commit()
        return result

    def create(self, folio='REQ-TEST'):
        result = self.call(service.create_requisition, folio=folio, notas=None)
        return self.call(service.add_requisition_detail, requisition_id=result.id,
                         material_id=self.material.id, cantidad=Decimal('4'), notas=None)

    def listing(self, **filters):
        total, items = service.list_requisitions(self.db, self.company.id, **filters)
        return RequisitionListResponse(items=items, total=total, limit=25, offset=0)

    def test_real_page_query_is_valid_for_mssql(self):
        self.create()
        captured = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if context.compiled is not None:
                captured.append(context.compiled.statement)
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            self.listing(q='Material')
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        pages = [query for query in captured if getattr(query, '_distinct', False)
                 and len(getattr(query, '_order_by_clauses', ())) > 0]
        self.assertTrue(pages)
        for query in pages:
            dialect = mssql.dialect()
            dialect._supports_offset_fetch = True
            sql = str(query.compile(dialect=dialect))
            self.assertNotIn('IS 1', sql)
            # SQL Server requires every DISTINCT ORDER BY column in SELECT.
            selected = {column.key for column in query.selected_columns}
            self.assertIn('created_at', selected, sql)
            self.assertIn('id', selected, sql)
            self.assertIn('OFFSET', sql)

    def test_endpoint_contract_and_backend_error_are_not_empty_success(self):
        context = SimpleNamespace(empresa=self.company, user=self.user)
        def endpoint(**filters):
            return routes.get_requisitions(context=context, db=self.db, limit=25, offset=0, **filters)
        self.assertEqual(endpoint().model_dump(), {'items': [], 'total': 0, 'limit': 25, 'offset': 0})
        document = self.create()
        self.assertEqual(endpoint(q='REQ-TEST').items[0].id, document.id)
        with patch.object(routes, 'list_requisitions', side_effect=RuntimeError('fixture read error')):
            with self.assertRaises(RuntimeError):
                endpoint()

    def test_empty_existing_search_pagination_and_tenant(self):
        self.assertEqual(self.listing().items, [])
        self.assertEqual(self.listing().total, 0)
        first = self.create()
        self.call(service.add_requisition_detail, requisition_id=first.id,
                  material_id=self.material.id, cantidad=Decimal('1'), notas=None)
        self.create('REQ-SECOND')
        self.assertEqual(self.listing(q='Material').total, 2)
        self.assertEqual(len(self.listing(q='Material').items), 2)
        self.assertEqual(len(self.listing(limit=1, offset=1).items), 1)
        self.assertEqual(service.list_requisitions(self.db, self.other.id), (0, []))
        with self.assertRaises(HTTPException) as error:
            service.get_requisition_for_company(self.db, self.other.id, first.id)
        self.assertEqual(error.exception.status_code, 404)

    def test_transitions_remain_visible_and_stock_is_correct(self):
        document = self.create()
        def check(state):
            response = self.listing()
            self.assertEqual(response.items[0].estatus, state)
            self.assertEqual(Counter(row.estatus for row in response.items)[state], 1)
            self.assertEqual(self.listing(estatus=state).total, 1)
        check('borrador')
        self.call(service.submit_requisition, requisition_id=document.id)
        check('enviada')
        self.call(service.approve_requisition, requisition_id=document.id, items=[])
        check('aprobada')
        for state in ['parcial', 'surtida']:
            self.call(service.fulfill_requisition, requisition_id=document.id,
                      almacen_id=self.warehouse.id,
                      items=[RequisitionFulfillLineRequest(detail_id=document.details[0].id,
                                                          cantidad_surtir=Decimal('2'))],
                      documento_referencia=None, notas=None, proyecto_id=None,
                      proyecto_nombre_snapshot=None)
            check(state)
        self.assertEqual(self.db.scalar(select(Existencia.cantidad)), Decimal('16'))
        self.assertEqual(len(self.db.scalars(select(MovimientoInventario)).all()), 2)
        self.assertEqual(service.serialize_requisition_response(
            self.db, service.get_requisition_for_company(self.db, self.company.id, document.id)
        ).estatus, 'surtida')

    def test_cancelled_and_rejected_are_visible(self):
        cancelled = self.create('REQ-CANCEL')
        self.call(service.cancel_requisition, requisition_id=cancelled.id)
        rejected = self.create('REQ-REJECT')
        self.call(service.submit_requisition, requisition_id=rejected.id)
        self.call(service.reject_requisition, requisition_id=rejected.id, motivo_rechazo='Test')
        counts = Counter(item.estatus for item in self.listing().items)
        self.assertEqual(counts, {'cancelada': 1, 'rechazada': 1})


if __name__ == '__main__':
    unittest.main()
