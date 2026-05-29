from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SupplierCreateRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    razon_social: str | None = Field(default=None, max_length=200)
    rfc: str | None = Field(default=None, max_length=40)
    contacto_nombre: str | None = Field(default=None, max_length=160)
    correo: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=40)
    direccion: str | None = Field(default=None, max_length=2000)
    notas: str | None = Field(default=None, max_length=2000)
    activo: bool = True


class SupplierUpdateRequest(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    razon_social: str | None = Field(default=None, max_length=200)
    rfc: str | None = Field(default=None, max_length=40)
    contacto_nombre: str | None = Field(default=None, max_length=160)
    correo: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=40)
    direccion: str | None = Field(default=None, max_length=2000)
    notas: str | None = Field(default=None, max_length=2000)
    activo: bool | None = None


class SupplierItem(BaseModel):
    id: str
    empresa_id: str
    nombre: str
    razon_social: str | None = None
    rfc: str | None = None
    contacto_nombre: str | None = None
    correo: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    notas: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierItem]
    total: int
    limit: int
    offset: int


class RequisitionCreateRequest(BaseModel):
    folio: str | None = Field(default=None, max_length=60)
    notas: str | None = Field(default=None, max_length=2000)


class RequisitionUpdateRequest(BaseModel):
    folio: str | None = Field(default=None, min_length=1, max_length=60)
    notas: str | None = Field(default=None, max_length=2000)


class RequisitionDetailCreateRequest(BaseModel):
    material_id: str = Field(min_length=1, max_length=64)
    cantidad: Decimal = Field(gt=0)
    notas: str | None = Field(default=None, max_length=2000)


class RequisitionDetailUpdateRequest(BaseModel):
    material_id: str | None = Field(default=None, min_length=1, max_length=64)
    cantidad: Decimal | None = Field(default=None, gt=0)
    notas: str | None = Field(default=None, max_length=2000)


class RequisitionDetailItem(BaseModel):
    id: str
    requisicion_id: str
    material_id: str
    material_sku: str
    material_nombre: str
    material_unidad: str
    cantidad: Decimal
    notas: str | None = None


class RequisitionItem(BaseModel):
    id: str
    empresa_id: str
    folio: str
    solicitante_user_id: str
    solicitante_nombre: str
    proveedor_sugerido_id: str | None = None
    proveedor_sugerido_nombre: str | None = None
    orden_compra_id: str | None = None
    orden_compra_folio: str | None = None
    estatus: str
    notas: str | None = None
    created_at: datetime
    updated_at: datetime
    details_count: int


class RequisitionResponse(RequisitionItem):
    details: list[RequisitionDetailItem]


class RequisitionListResponse(BaseModel):
    items: list[RequisitionItem]
    total: int
    limit: int
    offset: int


class RequisitionCreatePurchaseOrderRequest(BaseModel):
    proveedor_id: str = Field(min_length=1, max_length=64)
    almacen_destino_id: str = Field(min_length=1, max_length=64)
    folio: str | None = Field(default=None, max_length=60)


class PurchaseOrderCreateRequest(BaseModel):
    folio: str | None = Field(default=None, max_length=60)
    proveedor_id: str = Field(min_length=1, max_length=64)
    almacen_destino_id: str = Field(min_length=1, max_length=64)
    notas: str | None = Field(default=None, max_length=2000)


class PurchaseOrderUpdateRequest(BaseModel):
    folio: str | None = Field(default=None, min_length=1, max_length=60)
    proveedor_id: str | None = Field(default=None, min_length=1, max_length=64)
    almacen_destino_id: str | None = Field(default=None, min_length=1, max_length=64)
    notas: str | None = Field(default=None, max_length=2000)


class PurchaseOrderDetailCreateRequest(BaseModel):
    material_id: str = Field(min_length=1, max_length=64)
    cantidad: Decimal = Field(gt=0)
    costo_unitario: Decimal = Field(ge=0)


class PurchaseOrderDetailUpdateRequest(BaseModel):
    material_id: str | None = Field(default=None, min_length=1, max_length=64)
    cantidad: Decimal | None = Field(default=None, gt=0)
    costo_unitario: Decimal | None = Field(default=None, ge=0)


class PurchaseOrderReceiveLineRequest(BaseModel):
    detail_id: str = Field(min_length=1, max_length=64)
    cantidad: Decimal = Field(gt=0)


class PurchaseOrderReceiveRequest(BaseModel):
    documento_referencia: str | None = Field(default=None, max_length=160)
    notas: str | None = Field(default=None, max_length=2000)
    items: list[PurchaseOrderReceiveLineRequest] = Field(min_length=1)


class PurchaseOrderDetailItem(BaseModel):
    id: str
    orden_compra_id: str
    material_id: str
    material_sku: str
    material_nombre: str
    material_unidad: str
    cantidad: Decimal
    cantidad_recibida: Decimal
    cantidad_pendiente: Decimal
    costo_unitario: Decimal
    subtotal_linea: Decimal
    total_linea: Decimal
    estado_linea: str


class PurchaseOrderMovementTraceItem(BaseModel):
    id: str
    created_at: datetime
    tipo: str
    material_id: str
    material_sku: str
    material_nombre: str
    cantidad: Decimal
    documento_referencia: str | None = None
    notas: str | None = None
    recibido_por: str | None = None
    created_by_nombre: str | None = None


class PurchaseOrderItem(BaseModel):
    id: str
    empresa_id: str
    folio: str
    proveedor_id: str
    proveedor_nombre: str
    almacen_destino_id: str
    almacen_destino_nombre: str
    created_by_user_id: str
    created_by_nombre: str
    estatus: str
    subtotal: Decimal
    descuento_total: Decimal
    impuesto_total: Decimal
    total: Decimal
    notas: str | None = None
    created_at: datetime
    updated_at: datetime
    details_count: int
    cantidad_renglones: int
    cantidad_total_ordenada: Decimal
    cantidad_total_recibida: Decimal
    cantidad_total_pendiente: Decimal
    requisicion_id: str | None = None
    requisicion_folio: str | None = None


class PurchaseOrderResponse(PurchaseOrderItem):
    details: list[PurchaseOrderDetailItem]
    movements: list[PurchaseOrderMovementTraceItem]


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderItem]
    total: int
    limit: int
    offset: int
