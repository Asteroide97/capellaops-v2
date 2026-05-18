from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SaleCreateLineRequest(BaseModel):
    material_id: str = Field(min_length=1, max_length=64)
    cantidad: Decimal = Field(gt=0)
    descuento_unitario: Decimal = Field(default=Decimal("0"), ge=0)


class SaleCreateRequest(BaseModel):
    almacen_id: str = Field(min_length=1, max_length=64)
    cliente_nombre: str | None = Field(default=None, max_length=160)
    cliente_email: str | None = Field(default=None, max_length=255)
    metodo_pago: Literal["efectivo", "tarjeta", "transferencia", "mixto", "otro"]
    monto_recibido: Decimal | None = Field(default=None, ge=0)
    notas: str | None = Field(default=None, max_length=2000)
    items: list[SaleCreateLineRequest] = Field(min_length=1)


class SaleCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class SaleDetailItem(BaseModel):
    id: str
    venta_id: str
    material_id: str
    sku_snapshot: str
    nombre_snapshot: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_unitario: Decimal
    subtotal_linea: Decimal
    total_linea: Decimal
    movimiento_inventario_id: str | None = None


class SaleItem(BaseModel):
    id: str
    empresa_id: str
    folio: str
    almacen_id: str
    almacen_nombre: str
    usuario_id: str
    vendedor_nombre: str
    cliente_nombre: str | None = None
    cliente_email: str | None = None
    subtotal: Decimal
    descuento_total: Decimal
    impuesto_total: Decimal
    total: Decimal
    metodo_pago: str
    monto_recibido: Decimal | None = None
    cambio: Decimal | None = None
    estatus: str
    notas: str | None = None
    created_at: datetime
    cancelled_at: datetime | None = None
    cancelled_by_user_id: str | None = None
    cancel_reason: str | None = None
    items_count: int


class SaleResponse(SaleItem):
    details: list[SaleDetailItem]


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
    fecha: datetime
    empresa: str
    almacen: str
    vendedor: str
    cliente_nombre: str | None = None
    cliente_email: str | None = None
    productos: list[TicketLineItem]
    subtotal: Decimal
    descuento_total: Decimal
    impuesto_total: Decimal
    total: Decimal
    metodo_pago: str
    monto_recibido: Decimal | None = None
    cambio: Decimal | None = None
    estatus: str
    notas: str | None = None
    cancel_reason: str | None = None
    cancelled_at: datetime | None = None
