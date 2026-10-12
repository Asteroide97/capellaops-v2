from decimal import Decimal as D
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.routes import crm as routes
from app.models.crm import CRMCliente, CRMContacto
from app.schemas.crm import CRMOpportunityCreateRequest, CRMOpportunityUpdateRequest
from app.services import crm
from tests import test_crm_quote_commercial_contract as fixtures


class CrmListContextRegressionTests(unittest.TestCase):
    setUp = fixtures.CrmQuoteCommercialContractTests.setUp
    tearDown = fixtures.CrmQuoteCommercialContractTests.tearDown

    def test_contact_read_contract_remains_client_and_tenant_scoped(self):
        other_client = CRMCliente(empresa_id=self.company.id, nombre_comercial='Synthetic B')
        self.db.add(other_client)
        self.db.flush()
        self.db.add_all([CRMContacto(empresa_id=self.company.id, cliente_id=self.client.id, nombre='Synthetic A', activo=True),
                         CRMContacto(empresa_id=self.company.id, cliente_id=self.client.id, nombre='Synthetic inactive', activo=False),
                         CRMContacto(empresa_id=self.company.id, cliente_id=other_client.id, nombre='Synthetic B', activo=True)])
        self.db.commit()
        total, contacts = crm.list_client_contacts(self.db, self.company.id, self.client.id)
        self.assertEqual(total, 2)
        self.assertTrue(all(item.cliente_id == self.client.id for item in contacts))
        self.assertEqual(crm.list_client_contacts(self.db, self.company.id, self.client.id, activo=True)[0], 1)
        self.assertEqual(crm.list_client_contacts(self.db, self.company.id, self.client.id, q='no-match')[0], 0)
        with self.assertRaises(HTTPException) as error:
            crm.list_client_contacts(self.db, self.other.id, self.client.id)
        self.assertEqual(error.exception.status_code, 404)

    def opportunity(self, amount):
        return routes.crm_create_opportunity(CRMOpportunityCreateRequest(cliente_id=self.client.id,
            titulo='Synthetic opportunity', monto_estimado=amount, probabilidad=50), request=SimpleNamespace(client=None),
            context=SimpleNamespace(empresa=self.company, user=self.user), db=self.db)

    def test_filtered_opportunities_do_not_change_global_summary(self):
        self.opportunity('1234.56')
        total, rows = crm.list_opportunities(self.db, self.company.id, q='QA_NO_EXISTE')
        self.assertEqual((total, rows), (0, []))
        summary = crm.build_crm_summary(self.db, self.company.id)
        self.assertEqual(summary.kpis.oportunidades_abiertas, 1)
        self.assertEqual(summary.kpis.monto_pipeline, D('1234.56'))
        self.assertEqual(crm.list_opportunities(self.db, self.other.id)[0], 0)

    def test_negative_amount_rejected_by_schema_and_direct_service(self):
        for amount in ['-1', '-0.01']:
            with self.assertRaises(ValidationError):
                CRMOpportunityCreateRequest(cliente_id=self.client.id, titulo='Synthetic', monto_estimado=amount)
            with self.assertRaises(ValidationError):
                CRMOpportunityUpdateRequest(monto_estimado=amount)
            with self.assertRaises(HTTPException) as error:
                crm.normalize_nonnegative_amount(D(amount))
            self.assertEqual(error.exception.status_code, 400)

    def test_zero_positive_and_failed_direct_edit_preserve_amount_and_probability(self):
        self.assertEqual(self.opportunity('0').monto_estimado, D('0'))
        opportunity = self.opportunity('1234.56')
        with self.assertRaises(HTTPException):
            routes.crm_update_opportunity(opportunity.id, CRMOpportunityUpdateRequest.model_construct(monto_estimado=D('-1')),
                request=SimpleNamespace(client=None), context=SimpleNamespace(empresa=self.company, user=self.user), db=self.db)
        unchanged = crm.get_opportunity_for_company(self.db, self.company.id, opportunity.id)
        self.assertEqual(unchanged.monto_estimado, D('1234.56'))
        self.assertEqual(unchanged.probabilidad, 50)
