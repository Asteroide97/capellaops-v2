from decimal import Decimal as D
import unittest

from sqlalchemy import select

from app.models.inventory import Almacen, MovimientoInventario
from app.services import inventory_documents as documents
from tests import test_inventory_weighted_cost as fixtures


class TransferSnapshotTests(unittest.TestCase):
    setUp = fixtures.WeightedCostTests.setUp
    tearDown = fixtures.WeightedCostTests.tearDown
    seed = fixtures.WeightedCostTests.seed
    document = fixtures.WeightedCostTests.document

    def test_document_cost_is_not_the_weighted_transfer_movement_cost(self):
        for captured, expected in [(None, D('0')), (D('99'), D('99')), (D('0'), D('0'))]:
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
