from decimal import Decimal as D
import unittest

from sqlalchemy import select

from app.models import Plan
from app.models.pos import Venta, VentaDetalle
from app.schemas.pos import SaleCreateLineRequest, SalePaymentRequest
from app.services import pos
from tests import test_inventory_requisition_list as fixtures


class PosReportRegressionTests(unittest.TestCase):
    def setUp(self):
        fixtures.InventoryRequisitionListTests.setUp(self)
        self.db.add(Plan(code='pro', name='Synthetic POS', modules=['inventory', 'pos']))
        self.company.plan_code = 'pro'
        self.material.costo_promedio_actual = D('3')
        self.db.commit()
        self.shift = self.call(pos.open_shift, warehouse_id=self.warehouse.id,
                               fondo_inicial=D('1'), notas=None)

    tearDown = fixtures.InventoryRequisitionListTests.tearDown
    call = fixtures.InventoryRequisitionListTests.call

    def sale(self, manual=False, payments=None, received='22.1768'):
        item = SaleCreateLineRequest(tipo_linea='servicio' if manual else 'material',
            material_id=None if manual else self.material.id,
            descripcion='Synthetic service' if manual else None, cantidad=D('2'),
            precio_unitario=D('10.01'), descuento_unitario=D('0.02'), impuesto_tasa=D('0.16'))
        return self.call(pos.create_sale, almacen_id=self.warehouse.id,
            cliente_nombre=None, cliente_email=None, metodo_pago='efectivo',
            monto_recibido=D(received), descuento_global=D('1'), notas=None,
            items=[item], payments=payments or [])

    def report(self, **filters):
        return pos.get_pos_report_summary(self.db, self.company.id, **filters)

    def assert_groups(self, report, expected):
        self.assertEqual(report.kpis.total_neto, expected)
        for group in [report.ventas_por_dia, report.ventas_por_cajero, report.ventas_por_almacen]:
            self.assertEqual(sum((item.total_neto for item in group), D('0')), expected)
        self.assertEqual(sum((item.total for item in report.metodos_pago), D('0')), expected)

    def test_paid_exact_qa_discount_tax_and_groups_match_cut(self):
        sale = self.sale()
        self.assertEqual(sale.total, D('22.1768'))
        report = self.report()
        self.assert_groups(report, sale.total)
        self.assertEqual(report.kpis.total_bruto, sale.total)
        self.assertEqual(report.kpis.total_cancelado, D('0'))
        self.assertEqual(report.kpis.total_descuentos, D('1.04'))
        self.assertEqual(report.kpis.total_impuestos, D('3.1968'))
        self.assertEqual(report.descuentos.descuento_lineas_total, D('0.04'))
        self.assertEqual(report.descuentos.descuento_global_total, D('1'))
        self.assertEqual(report.kpis.utilidad_estimada, D('12.98'))
        cut = pos.get_shift_report(self.db, self.company.id, self.shift.id)
        self.assertEqual(report.kpis.total_neto, cut.shift.total_neto)
        self.assertEqual(report.kpis.total_bruto, cut.shift.total_bruto)

    def test_fully_cancelled_sale_has_zero_everywhere_not_negative(self):
        sale = self.sale()
        self.call(pos.cancel_sale, sale_id=sale.id, reason='Synthetic cancellation')
        report = self.report()
        self.assert_groups(report, D('0'))
        self.assertEqual(report.kpis.total_bruto, sale.total)
        self.assertEqual(report.kpis.total_cancelado, sale.total)
        self.assertEqual(report.kpis.utilidad_estimada, D('0'))
        self.assertEqual(report.productos_mas_vendidos, [])
        cut = pos.get_shift_report(self.db, self.company.id, self.shift.id)
        self.assertEqual(cut.shift.total_neto, D('0'))
        self.assertEqual(report.kpis.total_bruto, cut.shift.total_bruto)
        self.assertEqual(report.kpis.total_cancelado, cut.shift.ventas_canceladas_total)

    def test_paid_and_cancelled_are_not_subtracted_twice(self):
        self.sale()
        cancelled = self.sale()
        self.call(pos.cancel_sale, sale_id=cancelled.id, reason='Synthetic cancellation')
        report = self.report()
        self.assert_groups(report, D('22.1768'))
        self.assertEqual(report.kpis.total_bruto, D('44.3536'))
        self.assertEqual(report.kpis.total_cancelado, D('22.1768'))

    def test_cash_change_is_not_reported_as_revenue(self):
        self.sale(received='30')
        self.assert_groups(self.report(), D('22.1768'))

    def test_mixed_payments_reconcile_after_change_and_cancellation(self):
        sale = self.sale(payments=[SalePaymentRequest(metodo='efectivo', monto=D('20')),
                                  SalePaymentRequest(metodo='tarjeta', monto=D('10'))], received='30')
        report = self.report()
        self.assert_groups(report, sale.total)
        methods = {item.metodo: item.total for item in report.metodos_pago}
        self.assertEqual(methods['efectivo'], D('12.1768'))
        self.assertEqual(methods['tarjeta'], D('10'))
        self.call(pos.cancel_sale, sale_id=sale.id, reason='Synthetic cancellation')
        self.assert_groups(self.report(), D('0'))

    def test_unknown_service_cost_does_not_invent_profit(self):
        sale = self.sale(manual=True)
        self.assertIsNone(self.report().kpis.utilidad_estimada)
        self.call(pos.cancel_sale, sale_id=sale.id, reason='Synthetic cancellation')
        self.assertEqual(self.report().kpis.utilidad_estimada, D('0'))

    def test_explicit_zero_cost_is_known_but_missing_cost_is_not(self):
        sale = self.sale(manual=True)
        detail = self.db.scalar(select(VentaDetalle).where(VentaDetalle.venta_id == sale.id))
        detail.costo_unitario_manual = D('0')
        self.db.commit()
        self.assertEqual(self.report().kpis.utilidad_estimada, D('18.98'))

    def test_reports_filter_tenant_warehouse_and_cashier(self):
        self.sale()
        self.assertEqual(pos.get_pos_report_summary(self.db, self.other.id).kpis.total_neto, D('0'))
        self.assertEqual(self.report(almacen_id='foreign').kpis.total_neto, D('0'))
        self.assertEqual(self.report(usuario_id='foreign').kpis.total_neto, D('0'))
        self.assert_groups(self.report(almacen_id=self.warehouse.id, usuario_id=self.user.id), D('22.1768'))

    def test_suspended_sale_is_not_revenue(self):
        sale = self.sale()
        row = self.db.get(Venta, sale.id)
        row.estatus = 'suspendida'
        self.db.commit()
        self.assert_groups(self.report(), D('0'))

    def test_zero_weighted_snapshot_is_a_known_material_cost(self):
        self.material.costo_promedio_actual = D('0')
        self.db.commit()
        self.sale()
        self.assertEqual(self.report().kpis.utilidad_estimada, D('18.98'))

    def test_material_without_average_or_reference_has_unknown_profit(self):
        self.material.costo_promedio_actual = None
        self.material.costo_unitario = D('0')
        self.db.commit()
        self.sale()
        report = self.report()
        self.assertIsNone(report.kpis.utilidad_estimada)
        self.assertIsNone(report.productos_mas_vendidos[0].costo_estimado)
        self.assertIsNone(report.productos_mas_vendidos[0].utilidad_estimada)

    def test_product_totals_include_global_discount_and_exclude_tax_from_profit(self):
        self.sale()
        product = self.report().productos_mas_vendidos[0]
        self.assertEqual(product.total_venta, D('22.1768'))
        self.assertEqual(product.costo_estimado, D('6'))
        self.assertEqual(product.utilidad_estimada, D('12.98'))
