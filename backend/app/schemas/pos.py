from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


class SaleCreateLineRequest(BaseModel):
    tipo_linea: Literal["material", "manual", "servicio"] = "material"
    material_id: str | None = Field(default=None, min_length=1, max_length=64)
    descripcion: str | None = Field(default=None, min_length=1, max_length=4000)
    cantidad: Decimal = Field(gt=0)
    precio_unitario: Decimal | None = Field(default=None, ge=0)
    descuento_unitario: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        validation_alias=AliasChoices("descuento_unitario", "descuento"),
    )
    impuesto_tasa: Decimal = Field(default=Decimal("0"), ge=0)


class SalePaymentRequest(BaseModel):
    metodo: Literal["efectivo", "tarjeta", "transferencia", "otro"]
    monto: Decimal = Field(gt=0)
    referencia: str | None = Field(default=None, max_length=255)
    notas: str | None = Field(default=None, max_length=2000)


class SaleCreateRequest(BaseModel):
    almacen_id: str = Field(min_length=1, max_length=64)
    cliente_nombre: str | None = Field(default=None, max_length=160)
    cliente_email: str | None = Field(default=None, max_length=255)
    metodo_pago: Literal["efectivo", "tarjeta", "transferencia", "mixto", "otro"] | None = None
    monto_recibido: Decimal | None = Field(default=None, ge=0)
    descuento_global: Decimal = Field(default=Decimal("0"), ge=0)
    notas: str | None = Field(default=None, max_length=2000)
    items: list[SaleCreateLineRequest] = Field(min_length=1)
    payments: list[SalePaymentRequest] = Field(default_factory=list)


class SaleCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class SaleLineAddRequest(SaleCreateLineRequest):
    motivo: str | None = Field(default=None, max_length=2000)
    costo_unitario_manual: Decimal | None = Field(default=None, ge=0)


class SaleLineUpdateRequest(BaseModel):
    cantidad: Decimal | None = Field(default=None, gt=0)
    precio_unitario: Decimal | None = Field(default=None, ge=0)
    descuento_unitario: Decimal | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("descuento_unitario", "descuento"),
    )
    impuesto_tasa: Decimal | None = Field(default=None, ge=0)
    descripcion_manual: str | None = Field(
        default=None,
        min_length=1,
        max_length=4000,
        validation_alias=AliasChoices("descripcion_manual", "descripcion"),
    )
    costo_unitario_manual: Decimal | None = Field(default=None, ge=0)
    motivo: str | None = Field(default=None, max_length=2000)


class SaleLineDeleteRequest(BaseModel):
    motivo: str | None = Field(default=None, max_length=2000)


class SaleRecalculateRequest(BaseModel):
    descuento_global: Decimal | None = Field(default=None, ge=0)
    motivo: str | None = Field(default=None, max_length=2000)


class SaleApprovalRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class SaleApprovalDecisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class SaleCrmLinkRequest(BaseModel):
    cliente_id: str = Field(min_length=1, max_length=36)
    contacto_id: str | None = Field(default=None, max_length=36)


class SaleDetailItem(BaseModel):
    id: str
    venta_id: str
    tipo_linea: str
    material_id: str | None = None
    material_nombre: str | None = None
    descripcion: str
    descripcion_manual: str | None = None
    es_inventariable: bool = True
    sku_snapshot: str
    nombre_snapshot: str
    unidad: str | None = None
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_unitario: Decimal
    descuento: Decimal = Decimal("0")
    impuesto_tasa: Decimal = Decimal("0")
    impuesto: Decimal = Decimal("0")
    impuesto_linea: Decimal = Decimal("0")
    subtotal_linea: Decimal
    total_linea: Decimal
    movimiento_inventario_id: str | None = None
    stock_actual: Decimal | None = None


class SaleEditableLineItem(SaleDetailItem):
    subtotal_bruto: Decimal = Decimal("0")
    descuento_total: Decimal = Decimal("0")
    descuento_global_asignado: Decimal = Decimal("0")
    subtotal_neto: Decimal = Decimal("0")
    costo_unitario_estimado: Decimal | None = None
    costo_total_estimado: Decimal | None = None
    margen_estimado: Decimal | None = None
    margen_porcentaje: Decimal | None = None
    warnings: list[str] = Field(default_factory=list)


class SaleEditableTotals(BaseModel):
    subtotal_bruto: Decimal = Decimal("0")
    descuento_lineas_total: Decimal = Decimal("0")
    descuento_global: Decimal = Decimal("0")
    descuento_total: Decimal = Decimal("0")
    subtotal_neto: Decimal = Decimal("0")
    impuesto_total: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    costo_total_estimado: Decimal | None = None
    margen_estimado: Decimal | None = None
    margen_completo: bool = False
    warnings: list[str] = Field(default_factory=list)


class PosSaleRiskReason(BaseModel):
    code: str
    message: str


class PosSaleApprovalItem(BaseModel):
    id: str
    sale_id: str
    status: str
    reason: str | None = None
    decision_note: str | None = None
    requested_by_usuario_id: str
    requested_by_usuario_nombre: str
    approved_by_usuario_id: str | None = None
    approved_by_usuario_nombre: str | None = None
    rejected_by_usuario_id: str | None = None
    rejected_by_usuario_nombre: str | None = None
    risk_summary_json: dict | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PosSaleApprovalRequestResponse(BaseModel):
    approval_id: str
    status: str
    requires_approval: bool
    reasons: list[PosSaleRiskReason] = Field(default_factory=list)


class PosSaleApprovalListResponse(BaseModel):
    items: list[PosSaleApprovalItem]
    total: int
    limit: int
    offset: int


class PosSaleAdjustmentItem(BaseModel):
    id: str
    sale_id: str
    line_id: str | None = None
    tipo: str
    usuario_id: str
    usuario_nombre: str
    before_json: dict | None = None
    after_json: dict | None = None
    motivo: str | None = None
    created_at: datetime


class PosSaleAdjustmentListResponse(BaseModel):
    items: list[PosSaleAdjustmentItem]
    total: int
    limit: int
    offset: int


class SalePaymentItem(BaseModel):
    id: str
    metodo: str
    monto: Decimal
    referencia: str | None = None
    notas: str | None = None
    created_at: datetime | None = None


class SaleItem(BaseModel):
    id: str
    empresa_id: str
    folio: str
    almacen_id: str
    almacen_nombre: str
    turno_id: str | None = None
    turno_folio: str | None = None
    usuario_id: str
    vendedor_nombre: str
    cliente_nombre: str | None = None
    cliente_email: str | None = None
    crm_cliente_id: str | None = None
    crm_cliente_nombre: str | None = None
    crm_contacto_id: str | None = None
    crm_contacto_nombre: str | None = None
    subtotal: Decimal
    descuento_lineas_total: Decimal = Decimal("0")
    descuento_global: Decimal = Decimal("0")
    descuento_total: Decimal
    impuesto_total: Decimal
    total: Decimal
    metodo_pago: str
    monto_recibido: Decimal | None = None
    monto_pagado: Decimal | None = None
    cambio: Decimal | None = None
    estatus: str
    factura_estado: str = "no_solicitada"
    factura_solicitada_at: datetime | None = None
    factura_cliente_nombre: str | None = None
    factura_rfc: str | None = None
    factura_razon_social: str | None = None
    factura_email: str | None = None
    factura_uso_cfdi: str | None = None
    factura_regimen_fiscal: str | None = None
    factura_codigo_postal: str | None = None
    factura_notas: str | None = None
    factura_requiere_factura_global: bool = False
    notas: str | None = None
    created_at: datetime
    paid_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancelled_by_user_id: str | None = None
    cancel_reason: str | None = None
    items_count: int


class SaleResponse(SaleItem):
    details: list[SaleDetailItem]
    payments: list[SalePaymentItem] = Field(default_factory=list)


class SaleListResponse(BaseModel):
    items: list[SaleItem]
    total: int
    limit: int
    offset: int


class SaleEditableSummaryResponse(BaseModel):
    sale: SaleItem
    lines: list[SaleEditableLineItem] = Field(default_factory=list)
    editable: bool
    reason: str | None = None
    totals: SaleEditableTotals
    requires_approval: bool = False
    approval_status: str | None = None
    approval_id: str | None = None
    approval_reasons: list[PosSaleRiskReason] = Field(default_factory=list)
    can_charge: bool = True
    last_adjustments: list[PosSaleAdjustmentItem] = Field(default_factory=list)


class PosInvoiceRequestUpsertRequest(BaseModel):
    cliente_nombre: str | None = Field(default=None, max_length=160)
    rfc: str | None = Field(default=None, max_length=20)
    razon_social: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    uso_cfdi: str | None = Field(default=None, max_length=10)
    regimen_fiscal: str | None = Field(default=None, max_length=10)
    codigo_postal: str | None = Field(default=None, max_length=12)
    notas: str | None = Field(default=None, max_length=2000)


class PosInvoiceRequestItem(BaseModel):
    venta_id: str
    folio: str
    fecha: datetime
    total: Decimal
    venta_estatus: str
    factura_estado: str
    cliente_nombre: str | None = None
    rfc: str | None = None
    email: str | None = None
    uso_cfdi: str | None = None
    fecha_solicitud: datetime | None = None


class PosInvoiceRequestResponse(PosInvoiceRequestItem):
    almacen_id: str
    almacen_nombre: str
    usuario_id: str
    vendedor_nombre: str
    cliente_email: str | None = None
    razon_social: str | None = None
    regimen_fiscal: str | None = None
    codigo_postal: str | None = None
    notas: str | None = None
    factura_crm_cliente_id: str | None = None
    factura_crm_cliente_nombre: str | None = None
    factura_crm_contacto_id: str | None = None
    factura_crm_contacto_nombre: str | None = None
    factura_requiere_factura_global: bool = False


class PosInvoiceRequestListResponse(BaseModel):
    items: list[PosInvoiceRequestItem]
    total: int
    limit: int
    offset: int


class PosCatalogItem(BaseModel):
    material_id: str
    sku: str
    nombre: str
    unidad: str
    precio: Decimal
    existencia: Decimal
    stock_minimo: Decimal
    stock_bajo: bool


class PosCatalogResponse(BaseModel):
    items: list[PosCatalogItem]
    total: int
    limit: int
    offset: int


class TicketLineItem(BaseModel):
    tipo_linea: str = "material"
    sku: str
    nombre: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_unitario: Decimal
    descuento: Decimal = Decimal("0")
    impuesto_tasa: Decimal = Decimal("0")
    impuesto: Decimal = Decimal("0")
    impuesto_linea: Decimal = Decimal("0")
    subtotal_linea: Decimal
    total_linea: Decimal


class PosTicketResponse(BaseModel):
    id: str
    folio: str
    turno_folio: str | None = None
    fecha: datetime
    paid_at: datetime | None = None
    empresa: str
    almacen: str
    vendedor: str
    cliente_nombre: str | None = None
    cliente_email: str | None = None
    productos: list[TicketLineItem]
    subtotal: Decimal
    descuento_lineas_total: Decimal = Decimal("0")
    descuento_global: Decimal = Decimal("0")
    descuento_total: Decimal
    impuesto_total: Decimal
    total: Decimal
    metodo_pago: str
    monto_recibido: Decimal | None = None
    monto_pagado: Decimal | None = None
    cambio: Decimal | None = None
    estatus: str
    notas: str | None = None
    cancel_reason: str | None = None
    cancelled_at: datetime | None = None
    pagos: list[SalePaymentItem] = Field(default_factory=list)


class PosShiftMovementResponse(BaseModel):
    id: str
    tipo: str
    monto: Decimal
    motivo: str
    usuario_id: str
    usuario_nombre: str
    created_at: datetime


class PosShiftResponse(BaseModel):
    id: str
    empresa_id: str
    almacen_id: str
    almacen_nombre: str
    folio: str
    estatus: str
    usuario_apertura_id: str
    usuario_apertura_nombre: str
    usuario_cierre_id: str | None = None
    usuario_cierre_nombre: str | None = None
    fondo_inicial: Decimal
    total_ventas: Decimal
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_transferencia: Decimal
    total_otro: Decimal
    ingresos_manuales: Decimal
    retiros_manuales: Decimal
    efectivo_esperado: Decimal
    efectivo_contado: Decimal | None = None
    diferencia: Decimal | None = None
    notas_apertura: str | None = None
    notas_cierre: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    ventas_count: int
    ventas_canceladas_count: int = 0
    total_bruto: Decimal = Decimal("0")
    ventas_canceladas_total: Decimal = Decimal("0")
    total_neto: Decimal = Decimal("0")
    movimientos: list[PosShiftMovementResponse] = Field(default_factory=list)


class PosActiveShiftResponse(BaseModel):
    active_shift: PosShiftResponse | None = None


class PosShiftOpenRequest(BaseModel):
    warehouse_id: str = Field(min_length=1, max_length=64)
    fondo_inicial: Decimal = Field(ge=0)
    notas: str | None = Field(default=None, max_length=2000)


class PosShiftCloseRequest(BaseModel):
    warehouse_id: str = Field(min_length=1, max_length=64)
    efectivo_contado: Decimal = Field(ge=0)
    notas: str | None = Field(default=None, max_length=2000)


class PosShiftManualMovementRequest(BaseModel):
    warehouse_id: str = Field(min_length=1, max_length=64)
    monto: Decimal = Field(gt=0)
    motivo: str = Field(min_length=1, max_length=2000)


class PosShiftSaleReportItem(BaseModel):
    id: str
    folio: str
    fecha: datetime
    estatus: str
    total: Decimal
    subtotal: Decimal
    descuento_lineas_total: Decimal = Decimal("0")
    descuento_global: Decimal = Decimal("0")
    descuento_total: Decimal = Decimal("0")
    metodo_pago: str
    cliente_nombre: str | None = None
    cliente_email: str | None = None
    vendedor_nombre: str
    turno_folio: str | None = None
    monto_pagado: Decimal | None = None
    cambio: Decimal | None = None


class PosShiftCancellationReportItem(BaseModel):
    id: str
    folio: str
    fecha: datetime
    total: Decimal
    metodo_pago: str
    cliente_nombre: str | None = None
    motivo: str | None = None
    usuario_id: str | None = None
    usuario_nombre: str | None = None


class PosShiftReportResponse(BaseModel):
    shift: PosShiftResponse
    generated_at: datetime
    duracion_segundos: int
    descuento_lineas_total: Decimal = Decimal("0")
    descuento_global_total: Decimal = Decimal("0")
    descuentos_totales: Decimal = Decimal("0")
    movimientos_manuales: list[PosShiftMovementResponse] = Field(default_factory=list)
    ventas: list[PosShiftSaleReportItem] = Field(default_factory=list)
    cancelaciones: list[PosShiftCancellationReportItem] = Field(default_factory=list)


class PosShiftListResponse(BaseModel):
    items: list[PosShiftResponse]
    total: int
    limit: int
    offset: int


class PosReportKpis(BaseModel):
    ventas_count: int = 0
    ventas_pagadas_count: int = 0
    ventas_canceladas_count: int = 0
    ventas_suspendidas_count: int = 0
    total_bruto: Decimal = Decimal("0")
    total_descuentos: Decimal = Decimal("0")
    total_cancelado: Decimal = Decimal("0")
    total_neto: Decimal = Decimal("0")
    ticket_promedio: Decimal = Decimal("0")
    utilidad_estimada: Decimal = Decimal("0")


class PosReportPaymentMethodItem(BaseModel):
    metodo: str
    total: Decimal = Decimal("0")
    ventas_count: int = 0


class PosReportSalesTimelineItem(BaseModel):
    fecha: str
    ventas_count: int = 0
    total_neto: Decimal = Decimal("0")
    cancelado: Decimal = Decimal("0")


class PosReportSalesByCashierItem(BaseModel):
    usuario_id: str | None = None
    nombre: str
    ventas_count: int = 0
    total_neto: Decimal = Decimal("0")


class PosReportSalesByWarehouseItem(BaseModel):
    almacen_id: str | None = None
    nombre: str
    ventas_count: int = 0
    total_neto: Decimal = Decimal("0")


class PosReportTopProductItem(BaseModel):
    material_id: str
    sku: str
    nombre: str
    cantidad: Decimal = Decimal("0")
    total_venta: Decimal = Decimal("0")
    costo_estimado: Decimal = Decimal("0")
    utilidad_estimada: Decimal = Decimal("0")


class PosReportDiscountSummary(BaseModel):
    descuento_lineas_total: Decimal = Decimal("0")
    descuento_global_total: Decimal = Decimal("0")
    descuento_total: Decimal = Decimal("0")


class PosReportCancellationItem(BaseModel):
    venta_id: str
    folio: str
    fecha: datetime
    total: Decimal = Decimal("0")
    motivo: str | None = None
    usuario: str | None = None


class PosReportSummaryResponse(BaseModel):
    agrupacion: str = "day"
    kpis: PosReportKpis
    metodos_pago: list[PosReportPaymentMethodItem] = Field(default_factory=list)
    ventas_por_dia: list[PosReportSalesTimelineItem] = Field(default_factory=list)
    ventas_por_cajero: list[PosReportSalesByCashierItem] = Field(default_factory=list)
    ventas_por_almacen: list[PosReportSalesByWarehouseItem] = Field(default_factory=list)
    productos_mas_vendidos: list[PosReportTopProductItem] = Field(default_factory=list)
    descuentos: PosReportDiscountSummary
    cancelaciones: list[PosReportCancellationItem] = Field(default_factory=list)
