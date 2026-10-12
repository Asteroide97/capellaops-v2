import asyncio
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from sqlalchemy import event

from app.api.routes import auth, inventory, superadmin, users
from app.db.session import get_db
from app.models import Empresa, EmpresaUsuario, PendingRegistration
from app.schemas.auth import RegisterVerifyRequest
from app.schemas.superadmin import UpdateCompanyAccessRequest
from app.services import access
from tests import test_inventory_requisition_list as fixtures


NOW = datetime(2030, 6, 17, 17, 4, tzinfo=timezone.utc)


class TrialAccessMatrixTests(unittest.TestCase):
    def company(self, status='trial', ends_at=NOW + timedelta(seconds=1), plan='basico'):
        return SimpleNamespace(access_status=status, trial_ends_at=ends_at, plan_code=plan, modules=[])

    def allowed(self, company, *, active=True, module='inventory', superadmin=False):
        user = SimpleNamespace(is_active=active, is_superadmin=superadmin)
        with patch.object(access, 'utcnow', return_value=NOW, create=True):
            return access.can_access_module(user, company, module)

    def test_A_unpaid_current_trial_allows_access(self):
        self.assertTrue(self.allowed(self.company()))

    def test_B_unpaid_expired_trial_denies_access(self):
        self.assertFalse(self.allowed(self.company(ends_at=NOW - timedelta(seconds=1))))
        for module in ['inventory', 'pos', 'crm', 'pm', 'billing_pending']:
            with self.subTest(module=module):
                self.assertFalse(self.allowed(self.company(ends_at=NOW, plan='total'), module=module))

    def test_C_administrative_active_right_survives_trial_expiration(self):
        self.assertTrue(self.allowed(self.company('active', NOW - timedelta(days=1))))

    def test_D_suspended_cancelled_or_unknown_denies_regardless_of_trial(self):
        for status in ['suspended', 'cancelled', 'unknown']:
            with self.subTest(status=status):
                self.assertFalse(self.allowed(self.company(status)))

    def test_E_inactive_user_denied_even_with_active_right(self):
        self.assertFalse(self.allowed(self.company('active'), active=False))

    def test_F_basic_plan_only_enables_inventory(self):
        company = self.company('active')
        for module in ['pos', 'crm', 'pm', 'billing_pending', 'superadmin']:
            with self.subTest(module=module):
                self.assertFalse(self.allowed(company, module=module))
        self.assertTrue(self.allowed(company))

    def test_expiry_boundary_missing_and_naive_dates_fail_safely(self):
        for end in [NOW, None, NOW.replace(tzinfo=None)]:
            with self.subTest(end=end):
                self.assertFalse(self.allowed(self.company(ends_at=end)))
        self.assertTrue(self.allowed(self.company(ends_at=(NOW + timedelta(seconds=1)).replace(tzinfo=None))))
        offset = timezone(timedelta(hours=-6))
        self.assertFalse(self.allowed(self.company(ends_at=(NOW - timedelta(seconds=1)).astimezone(offset))))
        self.assertTrue(self.allowed(self.company(ends_at=(NOW + timedelta(seconds=1)).astimezone(offset))))

    def test_past_due_policy_and_platform_superadmin_are_unchanged(self):
        self.assertTrue(self.allowed(self.company('past_due', NOW - timedelta(days=1))))
        self.assertTrue(self.allowed(self.company('suspended'), module='superadmin', superadmin=True))
        self.assertFalse(self.allowed(self.company(), active=False, module='superadmin', superadmin=True))
        self.assertFalse(self.allowed(self.company(ends_at=NOW), superadmin=True))

    def test_disabled_company_module_and_module_payload_still_obey_access(self):
        company = self.company('active')
        company.modules = [SimpleNamespace(module_name='inventory', is_enabled=False)]
        self.assertFalse(self.allowed(company))
        user = SimpleNamespace(is_active=True, is_superadmin=False)
        with patch.object(access, 'utcnow', return_value=NOW, create=True):
            payload = access.build_module_payload(user, self.company(ends_at=NOW))
        self.assertEqual(len(payload), 1)
        self.assertFalse(payload[0].enabled)
        self.assertIsNone(payload[0].route)

    def test_module_payload_uses_one_clock_sample_for_all_modules(self):
        company = self.company(plan='total')
        user = SimpleNamespace(is_active=True, is_superadmin=False)
        with patch.object(access, 'utcnow', side_effect=[NOW, NOW + timedelta(seconds=2)], create=True) as clock:
            payload = access.build_module_payload(user, company)
        self.assertEqual(clock.call_count, 1)
        self.assertTrue(all(item.enabled for item in payload if item.name != 'billing_pending'))


class TrialProtectedRequestTests(unittest.TestCase):
    setUp = fixtures.InventoryRequisitionListTests.setUp
    tearDown = fixtures.InventoryRequisitionListTests.tearDown

    def http(self, method, path, *, body=None, headers=()):
        app = FastAPI()
        for router in [auth.router, inventory.router, users.router]:
            app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        sent = []
        async def receive():
            return {'type': 'http.request', 'body': json.dumps(body or {}).encode(), 'more_body': False}
        async def send(message):
            sent.append(message)
        scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': method,
                 'scheme': 'http', 'path': path, 'raw_path': path.encode(), 'query_string': b'',
                 'headers': [(b'content-type', b'application/json'), *headers],
                 'client': ('127.0.0.1', 1), 'server': ('local-test', 80), 'root_path': ''}
        asyncio.run(app(scope, receive, send))
        status = next(message['status'] for message in sent if message['type'] == 'http.response.start')
        content = b''.join(message.get('body', b'') for message in sent if message['type'] == 'http.response.body')
        return status, json.loads(content)

    def login(self):
        self.db.add(EmpresaUsuario(empresa_id=self.company.id, usuario_id=self.user.id, role='owner'))
        self.db.commit()
        with patch.object(auth, 'verify_password', return_value=True):
            status, response = self.http('POST', '/auth/login', body={
                'email': self.user.email, 'password': 'synthetic-fixture-only', 'empresa_id': self.company.id})
        self.assertEqual(status, 200)
        return [(b'authorization', ('Bearer ' + response['access_token']).encode())]

    def test_open_session_blocks_protected_request_after_expiry_without_writes(self):
        self.company.access_status = 'trial'
        self.company.trial_ends_at = NOW + timedelta(seconds=1)
        self.db.commit()
        headers = self.login()
        with patch.object(access, 'utcnow', return_value=NOW, create=True):
            self.assertEqual(self.http('GET', '/inventory/warehouses', headers=headers)[0], 200)
        writes = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE', 'MERGE'}:
                writes.append(statement)
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            with patch.object(access, 'utcnow', return_value=NOW + timedelta(seconds=1), create=True):
                status, response = self.http('GET', '/inventory/warehouses', headers=headers)
                self.assertEqual(status, 403)
                self.assertIn('Inventario', response['detail'])
                # Identity/access metadata remains available; it does not grant module access.
                status, me = self.http('GET', '/me', headers=headers)
                self.assertEqual(status, 200)
                self.assertFalse(me['modules'][0]['enabled'])
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        self.assertEqual(writes, [])
        self.assertEqual(self.http('GET', '/inventory/warehouses', headers=[*headers,
            (b'x-empresa-id', self.other.id.encode())])[0], 403)

    def test_sms_verification_generates_exactly_fifteen_days_not_from_created_at(self):
        pending = PendingRegistration(empresa_nombre='Synthetic trial', nombre_completo='Synthetic owner',
            email='trial-fixture@example.com', password_hash='synthetic-fixture', plan_code='basico',
            country_code='+52', phone_number='0000000000', phone_e164='+520000000000',
            expires_at=NOW + timedelta(minutes=5), created_at=NOW - timedelta(days=3))
        self.db.add(pending)
        self.db.commit()
        with patch.object(auth, 'datetime') as clock, patch.object(auth, 'check_phone_verification', return_value=True):
            clock.now.return_value = NOW
            response = auth.register_verify(RegisterVerifyRequest(pending_id=pending.id, code='123456'),
                                            SimpleNamespace(client=None), self.db)
        self.assertEqual(auth.ensure_utc(response.empresa.trial_ends_at), NOW + timedelta(days=15))
        self.assertEqual(response.empresa.access_status, 'trial')
        self.assertEqual(self.db.get(PendingRegistration, pending.id).status, 'verified')
        self.assertEqual(auth.ensure_utc(self.db.get(Empresa, response.empresa.id).trial_ends_at),
                         NOW + timedelta(days=15))

    def test_inactive_user_cannot_use_an_existing_session(self):
        headers = self.login()
        self.user.is_active = False
        self.db.commit()
        self.assertEqual(self.http('GET', '/inventory/warehouses', headers=headers)[0], 401)

    def test_superadmin_access_update_retains_full_timestamp_in_sqlite_fixture(self):
        raw = '2030-06-17T17:04:05.123456Z'
        payload = UpdateCompanyAccessRequest(plan_code='basico', access_status='active', trial_ends_at=raw,
                                             reason='Synthetic round-trip')
        self.company.trial_ends_at = payload.trial_ends_at
        self.db.commit()
        before = auth.ensure_utc(self.db.get(Empresa, self.company.id).trial_ends_at)
        result = superadmin.update_company_access(self.company.id, payload, SimpleNamespace(user=self.user), self.db)
        self.assertEqual(auth.ensure_utc(result.trial_ends_at), before)
        self.assertEqual(before.microsecond, 123456)
        self.db.expire_all()
        self.assertEqual(auth.ensure_utc(self.db.get(Empresa, self.company.id).trial_ends_at), before)
