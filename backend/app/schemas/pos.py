from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SaleCreateLineRequest(BaseModel):
    material_id: str = Field(min_length=1, max_length=64)
    cantidad: Decimal = Field(gt=0)
    precio_unitario: Decimal | None = Field(default=None, ge=0)
    descuento_unitario: Decimal = Field(default=Decimal("0"), ge=0)


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


class SaleDetailItem(BaseModel):
    id: str
    venta_id: str
    material_id: str
    sku_snapshot: str
    nombre_snapshot: str
    unidad: str | None = None
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_unitario: Decimal
    subtotal_linea: Decimal
    total_linea: Decimal
    movimiento_inventario_id: str | None = None
    stock_actual: Decimal | None = None


class SalePaymentItem(BaseModel):
    id: str
    metodo: str
    monto: Decimal
    referencia: str | None = None
    notas: str | None = None
    created_at: datetime | None = None


class PosTicketDeliveryItem(BaseModel):
    id: str
    canal: str
    destino: str
    estatus: str
    proveedor: str | None = None
    error_message: str | None = None
    sent_by_user_id: str
    sent_by_user_nombre: str | None = None
    created_at: datetime


class PosTicketSendEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    nombre: str | None = Field(default=None, max_length=160)


class PosTicketSendSmsRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=20)


class PosTicketDeliveryResponse(BaseModel):
    sent: bool
    message: str
    delivery: PosTicketDeliveryItem | None = None


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
    sku: str
    nombre: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_unitario: Decimal
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
    deliveries: list[PosTicketDeliveryItem] = Field(default_factory=list)


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
