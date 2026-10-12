from decimal import Decimal
import unittest

from sqlalchemy import select

from app.models import AuditLog, EmpresaUsuario, Plan, Usuario
from app.models.inventory import Almacen, Existencia, MovimientoInventario
from app.models.user import EmpresaUsuarioInvitacion
from app.services.company import get_company_plan_limits, ensure_within_company_user_limit, normalize_company_role
from app.services.seed import PLAN_SEED_DATA
from fastapi import HTTPException
from tests import test_superadmin_trial_access as trial_fixtures
from tests import test_inventory_requisition_list as fixtures


class CompanyAccessLimitTests(unittest.TestCase):
    setUp = fixtures.InventoryRequisitionListTests.setUp
    tearDown = fixtures.InventoryRequisitionListTests.tearDown
    http = trial_fixtures.TrialProtectedRequestTests.http
    login = trial_fixtures.TrialProtectedRequestTests.login

    def configure(self):
        plan = self.db.get(Plan, 'basico')
        plan.max_almacenes = PLAN_SEED_DATA['basico']['max_almacenes']
        plan.max_usuarios = PLAN_SEED_DATA['basico']['max_usuarios']
        self.db.commit()
        return self.login()

    def snapshot(self):
        return ([tuple((row.id, row.nombre, row.codigo, row.activo)) for row in self.db.scalars(
                    select(Almacen).order_by(Almacen.id))],
                len(self.db.scalars(select(AuditLog)).all()), self.db.scalar(select(Existencia.cantidad)),
                len(self.db.scalars(select(MovimientoInventario)).all()))

    def test_second_active_warehouse_is_409_through_real_endpoint_without_writes(self):
        headers = self.configure()
        before = self.snapshot()
        status, response = self.http('POST', '/inventory/warehouses', headers=headers,
                                    body={'nombre': 'Synthetic extra', 'codigo': 'EXTRA', 'activo': True})
        self.assertEqual(status, 409)
        self.assertIn('1', response['detail'])
        self.assertEqual(self.snapshot(), before)

    def test_inactive_creation_does_not_count_and_reactivation_is_blocked(self):
        headers = self.configure()
        status, warehouse = self.http('POST', '/inventory/warehouses', headers=headers,
                                     body={'nombre': 'Synthetic inactive', 'codigo': 'INACTIVE', 'activo': False})
        self.assertEqual(status, 201)
        self.assertEqual(get_company_plan_limits(self.db, self.company).almacenes_actuales, 1)
        before = self.snapshot()
        status, _ = self.http('PUT', '/inventory/warehouses/' + warehouse['id'], headers=headers,
                              body={'activo': True})
        self.assertEqual(status, 409)
        self.assertEqual(self.snapshot(), before)

    def test_legacy_over_limit_remains_readable_and_cannot_grow_or_reactivate(self):
        headers = self.configure()
        second = Almacen(empresa_id=self.company.id, nombre='Synthetic legacy', codigo='LEGACY', activo=True)
        inactive = Almacen(empresa_id=self.company.id, nombre='Synthetic inactive', codigo='OFF', activo=False)
        self.db.add_all([second, inactive])
        self.db.commit()
        before = self.snapshot()
        status, response = self.http('GET', '/inventory/warehouses', headers=headers)
        self.assertEqual((status, response['total']), (200, 3))
        self.assertEqual(get_company_plan_limits(self.db, self.company).almacenes_actuales, 2)
        self.assertEqual(self.http('POST', '/inventory/warehouses', headers=headers,
                                 body={'nombre': 'Synthetic extra', 'codigo': 'EXTRA', 'activo': True})[0], 409)
        self.assertEqual(self.http('PUT', '/inventory/warehouses/' + inactive.id, headers=headers,
                                 body={'activo': True})[0], 409)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(before[2:], (Decimal('20'), 0))

    def test_foreign_tenant_does_not_share_capacity_or_warehouse_access(self):
        headers = self.configure()
        foreign = Almacen(empresa_id=self.other.id, nombre='Synthetic foreign', codigo='FOREIGN')
        self.db.add(foreign)
        self.db.commit()
        self.assertEqual(get_company_plan_limits(self.db, self.company).almacenes_actuales, 1)
        self.assertEqual(get_company_plan_limits(self.db, self.other).almacenes_actuales, 1)
        self.assertEqual(self.http('PUT', '/inventory/warehouses/' + foreign.id, headers=headers,
                                 body={'nombre': 'No change'})[0], 404)
        self.assertEqual(self.http('GET', '/inventory/warehouses', headers=[*headers,
                                 (b'x-empresa-id', self.other.id.encode())])[0], 403)

    def test_basic_user_capacity_counts_active_memberships_including_owner_only(self):
        self.configure()
        inactive = Usuario(email='inactive-fixture@example.com', full_name='Synthetic inactive', password_hash='fixture')
        self.db.add(inactive)
        self.db.flush()
        self.db.add_all([EmpresaUsuario(empresa_id=self.company.id, usuario_id=inactive.id, role='user', is_active=False),
            EmpresaUsuario(empresa_id=self.other.id, usuario_id=self.user.id, role='owner'),
            EmpresaUsuarioInvitacion(empresa_id=self.company.id, email='pending-fixture@example.com', role='admin',
                                     status='pending', invited_by_user_id=self.user.id)])
        self.db.commit()
        limits = get_company_plan_limits(self.db, self.company)
        self.assertEqual((limits.max_usuarios, limits.usuarios_actuales), (2, 1))
        ensure_within_company_user_limit(self.db, self.company)
        membership = self.db.scalar(select(EmpresaUsuario).where(EmpresaUsuario.usuario_id == inactive.id,
                                                                EmpresaUsuario.empresa_id == self.company.id))
        membership.is_active = True
        inactive.is_active = False
        self.db.commit()
        # Existing policy counts the membership, not the global user flag.
        self.assertEqual(get_company_plan_limits(self.db, self.company).usuarios_actuales, 2)
        with self.assertRaises(HTTPException) as error:
            ensure_within_company_user_limit(self.db, self.company)
        self.assertEqual(error.exception.status_code, 409)
        for role in ['user', 'admin', 'almacenista']:
            self.assertEqual(normalize_company_role(role), role)
        with self.assertRaises(HTTPException):
            normalize_company_role('superadmin')
