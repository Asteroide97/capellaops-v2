import asyncio
from datetime import date
from decimal import Decimal as D
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import Date, event, select
from sqlalchemy.orm import Session

from app.api.routes import crm as routes
from app.models import Plan
from app.models.crm import CRMCliente, CRMCotizacion, CRMCotizacionItem
from app.schemas.crm import CRMCotizacionCreate, CRMCotizacionItemCreate, CRMCotizacionUpdate
from app.services import crm, documents_pdf
from tests import test_inventory_requisition_list as fixtures


class CrmQuoteCommercialContractTests(unittest.TestCase):
    def setUp(self):
        fixtures.InventoryRequisitionListTests.setUp(self)
        self.db.add(Plan(code='total', name='Synthetic CRM', modules=['crm']))
        self.company.plan_code = 'total'
        self.client = CRMCliente(empresa_id=self.company.id, nombre_comercial='Synthetic client')
        self.db.add(self.client)
        self.db.commit()

    tearDown = fixtures.InventoryRequisitionListTests.tearDown

    def item(self, factor='0.16'):
        return dict(descripcion='Synthetic service', cantidad='2', precio_unitario='100',
                    descuento='10', impuesto_tasa=factor)

    def payload(self, factor='0.16'):
        return dict(cliente_id=self.client.id, titulo='Synthetic quote', fecha_emision=date(2026, 10, 5),
                    fecha_vencimiento=date(2026, 10, 15), items=[self.item(factor)])

    def create(self, factor='0.16'):
        return routes.crm_create_quote(CRMCotizacionCreate(**self.payload(factor)),
            request=SimpleNamespace(client=None), context=SimpleNamespace(empresa=self.company, user=self.user), db=self.db)

    def edit(self, quote_id, **data):
        return routes.crm_update_quote(quote_id, CRMCotizacionUpdate(**data),
            request=SimpleNamespace(client=None), context=SimpleNamespace(empresa=self.company, user=self.user), db=self.db)

    def test_date_storage_api_listing_detail_and_pdf_are_the_same_civil_day(self):
        quote = self.create()
        self.assertIsInstance(CRMCotizacion.__table__.c.fecha_emision.type, Date)
        with Session(self.engine, autoflush=False) as reopened:
            stored = reopened.get(CRMCotizacion, quote.id)
            detail = crm.get_crm_quote(reopened, self.company.id, quote.id)
            _, items = crm.list_crm_quotes(reopened, self.company.id)
            self.assertEqual(stored.fecha_emision, date(2026, 10, 5))
            self.assertEqual(items[0].model_dump(mode='json')['fecha_emision'], '2026-10-05')
            self.assertEqual(detail.model_dump(mode='json')['fecha_emision'], '2026-10-05')
            self.assertEqual(documents_pdf._date_label(detail.fecha_emision), '05/10/2026')
        unchanged = self.edit(quote.id, titulo='Synthetic edited')
        self.assertEqual(unchanged.fecha_emision, date(2026, 10, 5))

    def test_actual_pdf_render_uses_civil_dates_and_authoritative_tax_totals(self):
        quote = self.create()
        original = documents_pdf._build_story_shell
        with patch.object(documents_pdf, '_build_story_shell', wraps=original) as shell:
            result = routes.crm_quote_pdf(quote.id, context=SimpleNamespace(empresa=self.company), db=self.db)
        self.assertEqual(result.media_type, 'application/pdf')
        self.assertTrue(result.body.startswith(b'%PDF-'))
        self.assertIn('cotizacion-COT-', result.headers['content-disposition'])
        kwargs = shell.call_args.kwargs
        self.assertIn(('Fecha emision', '05/10/2026'), kwargs['intro_rows'])
        self.assertIn(('Fecha vencimiento', '15/10/2026'), kwargs['intro_rows'])
        self.assertIn(('Impuesto total', '$30.40'), kwargs['totals_rows'])
        self.assertIn(('Total', '$220.40'), kwargs['totals_rows'])

    def test_factor_zero_sixteen_percent_and_hundred_percent_keep_existing_formula(self):
        for factor, tax, total in [('0', '0', '190'), ('0.16', '30.40', '220.40'), ('1', '190', '380')]:
            with self.subTest(factor=factor):
                quote = self.create(factor)
                self.assertEqual(quote.subtotal, D('190'))
                self.assertEqual(quote.descuento_total, D('10'))
                self.assertEqual(quote.impuesto_total, D(tax))
                self.assertEqual(quote.total, D(total))
                self.assertEqual(quote.items[0].impuesto_tasa, D(factor))

    def test_schema_protects_factor_domain_even_when_frontend_is_bypassed(self):
        for factor in ['16', '1.00001', '-0.01', 'NaN', 'Infinity']:
            with self.subTest(factor=factor):
                with self.assertRaises(ValidationError):
                    CRMCotizacionCreate(**self.payload(factor))
                with self.assertRaises(ValidationError):
                    CRMCotizacionUpdate(items=[self.item(factor)])
        self.assertEqual(self.db.scalars(select(CRMCotizacion)).all(), [])

    def test_http_invalid_create_and_update_are_422_before_any_write(self):
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[routes.get_crm_context] = lambda: SimpleNamespace(empresa=self.company, user=self.user)
        app.dependency_overrides[routes.get_db] = lambda: self.db
        writes = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if context.compiled is not None and not getattr(context.compiled.statement, 'is_select', False):
                writes.append(statement)
        event.listen(self.engine, 'before_cursor_execute', capture)
        async def request(method, path, payload):
            body = json.dumps(jsonable_encoder(payload)).encode('utf-8')
            messages = []
            async def receive():
                return {'type': 'http.request', 'body': body, 'more_body': False}
            async def send(message):
                messages.append(message)
            # Exercise the real ASGI router/schema without a network server or optional HTTP client.
            await app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                       'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
                       'root_path': '', 'query_string': b'', 'headers': [(b'content-type', b'application/json')],
                       'client': ('fixture', 0), 'server': ('fixture', 80)}, receive, send)
            self.assertEqual(next(message['status'] for message in messages if message['type'] == 'http.response.start'), 422)
            response = b''.join(message.get('body', b'') for message in messages)
            self.assertIn(b'impuesto_tasa', response)
        try:
            for factor in ['16', '-0.01', '1.00001']:
                asyncio.run(request('POST', '/crm/quotes', self.payload(factor)))
                asyncio.run(request('PUT', '/crm/quotes/synthetic-quote', {'items': [self.item(factor)]}))
            self.assertEqual(writes, [])
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        self.assertEqual(self.db.scalars(select(CRMCotizacion)).all(), [])

    def test_service_protects_unquantized_factor_domain_for_direct_callers(self):
        for factor in ['16', '1.00001', '-0.00001', 'NaN', 'Infinity']:
            with self.subTest(factor=factor):
                with self.assertRaises(HTTPException) as error:
                    crm.build_quote_item_amounts(self.item(factor), order=1)
                self.assertEqual(error.exception.status_code, 400)

    def test_failed_direct_update_rolls_back_and_does_not_change_legacy_quote(self):
        quote = self.create()
        try:
            with self.assertRaises(HTTPException):
                crm.update_crm_quote(self.db, empresa=self.company, user=self.user, quote_id=quote.id,
                    data={'items': [self.item('16')]}, ip_address=None)
        finally:
            self.db.rollback()
        unchanged = crm.get_crm_quote(self.db, self.company.id, quote.id)
        self.assertEqual(unchanged.items[0].impuesto_tasa, D('0.16'))
        self.assertEqual(unchanged.total, D('220.40'))
        self.assertEqual(unchanged.fecha_emision, date(2026, 10, 5))

    def test_existing_legacy_factor_sixteen_is_not_repaired_or_reinterpreted_on_reads(self):
        quote = self.create()
        row = self.db.get(CRMCotizacionItem, quote.items[0].id)
        row.impuesto_tasa, row.impuesto, row.total = D('16'), D('3040'), D('3230')
        crm.recalculate_quote_totals(self.db.get(CRMCotizacion, quote.id))
        self.db.commit()
        legacy = crm.get_crm_quote(self.db, self.company.id, quote.id)
        self.assertEqual(legacy.items[0].impuesto_tasa, D('16'))
        self.assertEqual(legacy.total, D('3230'))

    def test_draft_edit_keeps_factor_date_and_recalculates_without_client_totals(self):
        quote = self.create()
        updated = self.edit(quote.id, items=[self.item('0')])
        self.assertEqual(updated.fecha_emision, date(2026, 10, 5))
        self.assertEqual(updated.total, D('190'))
        self.assertEqual(updated.estatus, 'borrador')

    def test_pdf_and_detail_remain_tenant_scoped(self):
        quote = self.create()
        for operation in [lambda: crm.get_crm_quote(self.db, self.other.id, quote.id),
                          lambda: routes.crm_quote_pdf(quote.id, context=SimpleNamespace(empresa=self.other), db=self.db)]:
            with self.assertRaises(HTTPException) as error:
                operation()
            self.assertEqual(error.exception.status_code, 404)

    def test_omitted_factor_still_defaults_to_zero_and_empty_api_value_is_invalid(self):
        item = self.item()
        item.pop('impuesto_tasa')
        self.assertEqual(CRMCotizacionItemCreate(**item).impuesto_tasa, D('0'))
        for empty in ['', None]:
            with self.assertRaises(ValidationError):
                CRMCotizacionItemCreate(**item, impuesto_tasa=empty)
