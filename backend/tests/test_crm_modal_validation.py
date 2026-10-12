from decimal import Decimal as D
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.api.routes import crm as routes
from app.models.crm import CRMCotizacion, CRMOportunidad
from app.schemas.crm import CRMCotizacionCreate, CRMOpportunityCreateRequest, CRMOpportunityUpdateRequest
from app.services import crm
from tests import test_crm_quote_commercial_contract as fixtures


class CrmModalValidationRegressionTests(unittest.TestCase):
    setUp = fixtures.CrmQuoteCommercialContractTests.setUp
    tearDown = fixtures.CrmQuoteCommercialContractTests.tearDown
    item = fixtures.CrmQuoteCommercialContractTests.item
    payload = fixtures.CrmQuoteCommercialContractTests.payload

    def test_discount_over_gross_returns_business_400_and_rolls_back_quote(self):
        data = self.payload()
        data['items'][0]['descuento'] = '201'
        with self.assertRaises(HTTPException) as error:
            routes.crm_create_quote(CRMCotizacionCreate(**data), request=SimpleNamespace(client=None),
                context=SimpleNamespace(empresa=self.company, user=self.user), db=self.db)
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.detail, 'El descuento no puede superar el subtotal de la partida.')
        self.assertEqual(self.db.scalars(select(CRMCotizacion)).all(), [])

    def test_zero_quantity_still_fails_validation(self):
        data = self.payload()
        data['items'][0]['cantidad'] = '0'
        with self.assertRaises(ValidationError):
            CRMCotizacionCreate(**data)

    def test_probability_101_is_rejected_by_both_schemas_and_service(self):
        with self.assertRaises(ValidationError):
            CRMOpportunityCreateRequest(cliente_id=self.client.id, titulo='Synthetic', probabilidad=101)
        with self.assertRaises(ValidationError):
            CRMOpportunityUpdateRequest(probabilidad=101)
        with self.assertRaises(HTTPException) as error:
            crm.normalize_probability(101)
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(self.db.scalars(select(CRMOportunidad)).all(), [])

    def test_probability_100_save_and_edit_keep_existing_tenant_contract(self):
        context = SimpleNamespace(empresa=self.company, user=self.user)
        opportunity = routes.crm_create_opportunity(CRMOpportunityCreateRequest(
            cliente_id=self.client.id, titulo='Synthetic', probabilidad=100, monto_estimado=D('200')),
            request=SimpleNamespace(client=None), context=context, db=self.db)
        updated = routes.crm_update_opportunity(opportunity.id, CRMOpportunityUpdateRequest(probabilidad=50),
            request=SimpleNamespace(client=None), context=context, db=self.db)
        self.assertEqual(updated.probabilidad, 50)
        self.assertEqual(updated.monto_estimado, D('200'))
        with self.assertRaises(HTTPException) as error:
            crm.get_opportunity_for_company(self.db, self.other.id, opportunity.id)
        self.assertEqual(error.exception.status_code, 404)
