from decimal import Decimal as D
from types import SimpleNamespace
import unittest

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.inventory import add_transfer_detail_endpoint, update_transfer_detail_endpoint
from app.models.inventory import Almacen, MovimientoInventario, TransferenciaInventarioDetalle
from app.schemas.inventory import TransferDetailCreateRequest, TransferDetailUpdateRequest
from app.services import inventory_documents as documents
from tests import test_inventory_weighted_cost as fixtures


class TransferSnapshotTests(unittest.TestCase):
    setUp = fixtures.WeightedCostTests.setUp
    tearDown = fixtures.WeightedCostTests.tearDown
    seed = fixtures.WeightedCostTests.seed
    document = fixtures.WeightedCostTests.document

    def test_document_cost_is_not_the_weighted_transfer_movement_cost(self):
        for captured, expected in [(None, None), (D('99'), D('99')), (D('0'), D('0'))]:
            with self.subTest(captured=captured):
                self.seed('10', '20', '0')
                destination = Almacen(empresa_id=self.company.id, codigo=f'B-{captured}', nombre='Synthetic B')
                self.db.add(destination)
                self.db.commit()
                transfer = self.document(documents.create_transfer, folio=None,
                    almacen_origen_id=self.warehouse.id, almacen_destino_id=destination.id, notas=None)
                transfer = self.document(documents.add_transfer_detail, transfer_id=transfer.id,
                    material_id=self.material.id, cantidad=D('1'), costo_unitario_snapshot=captured)
                self.assertEqual(transfer.details[0].costo_unitario_snapshot, expected)
                self.document(documents.confirm_transfer, transfer_id=transfer.id)
                rows = self.db.scalars(select(MovimientoInventario).where(
                    MovimientoInventario.referencia_id == transfer.id)).all()
                self.assertEqual(len(rows), 2)
                self.assertTrue(all(row.costo_unitario_snapshot == D('20') for row in rows))
                self.assertTrue(all(row.costo_promedio_snapshot == D('20') for row in rows))
                self.assertEqual(self.material.costo_promedio_actual, D('20'))

    def test_legacy_document_snapshot_serializes_unchanged(self):
        from types import SimpleNamespace
        legacy = SimpleNamespace(id='legacy', transferencia_id='document', cantidad=D('1'),
                                 costo_unitario_snapshot=D('7'))
        row = documents.serialize_transfer_detail(legacy, self.material)
        self.assertEqual(row.costo_unitario_snapshot, D('7'))

    def draft(self):
        self.seed('10', '20', '77')
        destination = self.db.scalar(select(Almacen).where(Almacen.codigo == 'DOC-B'))
        if destination is None:
            destination = Almacen(empresa_id=self.company.id, codigo='DOC-B', nombre='Synthetic B')
            self.db.add(destination)
            self.db.commit()
        return self.document(documents.create_transfer, folio=None,
            almacen_origen_id=self.warehouse.id, almacen_destino_id=destination.id, notas=None)

    def add(self, transfer, **fields):
        return add_transfer_detail_endpoint(transfer.id,
            TransferDetailCreateRequest(material_id=self.material.id, cantidad=D('1'), **fields),
            request=SimpleNamespace(client=None),
            context=SimpleNamespace(empresa=self.company, user=self.user), db=self.db)

    def edit(self, transfer, **fields):
        return update_transfer_detail_endpoint(transfer.id, transfer.details[0].id,
            TransferDetailUpdateRequest(**fields), request=SimpleNamespace(client=None),
            context=SimpleNamespace(empresa=self.company, user=self.user), db=self.db)

    def check_persisted_and_reopened(self, transfer, expected):
        with Session(self.engine, autoflush=False) as reopened:
            stored = reopened.scalar(select(TransferenciaInventarioDetalle).where(
                TransferenciaInventarioDetalle.id == transfer.details[0].id))
            self.assertEqual(stored.costo_unitario_snapshot, expected)
            response = documents.serialize_transfer_response(reopened,
                documents.get_transfer_for_company(reopened, self.company.id, transfer.id))
            self.assertEqual(response.details[0].costo_unitario_snapshot, expected)
            if expected is None:
                self.assertIsNone(response.model_dump(mode='json')['details'][0]['costo_unitario_snapshot'])

    def test_empty_zero_value_create_persist_and_reopen(self):
        for supplied in [None, D('0'), D('20')]:
            with self.subTest(supplied=supplied):
                transfer = self.add(self.draft(), costo_unitario_snapshot=supplied)
                self.assertEqual(transfer.details[0].costo_unitario_snapshot, supplied)
                self.check_persisted_and_reopened(transfer, supplied)

    def test_omitted_create_cost_persists_null_not_material_reference(self):
        transfer = self.add(self.draft())
        self.check_persisted_and_reopened(transfer, None)

    def test_edit_empty_to_value_then_clear_with_explicit_null(self):
        transfer = self.add(self.draft(), costo_unitario_snapshot=None)
        transfer = self.edit(transfer, costo_unitario_snapshot=D('20'))
        self.check_persisted_and_reopened(transfer, D('20'))
        transfer = self.edit(transfer, material_id=self.material.id, cantidad=D('2'), costo_unitario_snapshot=None)
        self.check_persisted_and_reopened(transfer, None)
        self.assertEqual(transfer.details[0].cantidad, D('2'))

    def test_partial_edit_omitted_cost_preserves_zero_and_value(self):
        for supplied in [D('0'), D('20')]:
            with self.subTest(supplied=supplied):
                transfer = self.add(self.draft(), costo_unitario_snapshot=supplied)
                transfer = self.edit(transfer, material_id=self.material.id, cantidad=D('2'))
                self.check_persisted_and_reopened(transfer, supplied)

    def test_edit_explicit_zero_is_not_empty(self):
        transfer = self.add(self.draft(), costo_unitario_snapshot=D('20'))
        transfer = self.edit(transfer, costo_unitario_snapshot=D('0'))
        self.check_persisted_and_reopened(transfer, D('0'))

    def test_legacy_zero_serializes_without_reinterpretation(self):
        row = documents.serialize_transfer_detail(SimpleNamespace(id='legacy-zero',
            transferencia_id='document', cantidad=D('1'), costo_unitario_snapshot=D('0')), self.material)
        self.assertEqual(row.costo_unitario_snapshot, D('0'))

    def test_draft_document_cost_changes_do_not_touch_stock_or_movement_cost(self):
        from app.models.inventory import Existencia
        transfer = self.add(self.draft(), costo_unitario_snapshot=D('20'))
        self.edit(transfer, costo_unitario_snapshot=None)
        self.db.refresh(self.material)
        self.assertEqual(self.material.costo_unitario, D('77'))
        self.assertEqual(self.material.costo_promedio_actual, D('20'))
        self.assertEqual(self.db.scalar(select(Existencia.cantidad).where(
            Existencia.material_id == self.material.id, Existencia.almacen_id == self.warehouse.id)), D('10'))
        self.assertEqual(self.db.scalars(select(MovimientoInventario)).all(), [])
