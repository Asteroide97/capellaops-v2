from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SupplierCreateRequest(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    nombre_comercial: str | None = Field(default=None, max_length=160)
    razon_social: str | None = Field(default=None, max_length=200)
    rfc: str | None = Field(default=None, max_length=40)
    contacto_nombre: str | None = Field(default=None, max_length=160)
    contacto_principal: str | None = Field(default=None, max_length=160)
    correo: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=40)
    sitio_web: str | None = Field(default=None, max_length=255)
    direccion: str | None = Field(default=None, max_length=2000)
    ciudad: str | None = Field(default=None, max_length=120)
    estado: str | None = Field(default=None, max_length=120)
    pais: str | None = Field(default=None, max_length=120)
    codigo_postal: str | None = Field(default=None, max_length=20)
    telefono_contacto: str | None = Field(default=None, max_length=40)
    email_contacto: str | None = Field(default=None, max_length=255)
    moneda_preferida: str | None = Field(default=None, max_length=16)
    condiciones_pago: str | None = Field(default=None, max_length=2000)
    dias_credito: int = Field(default=0, ge=0)
    lead_time_dias: int = Field(default=0, ge=0)
    metodo_pago_preferido: str | None = Field(default=None, max_length=120)
    banco: str | None = Field(default=None, max_length=160)
    cuenta_bancaria: str | None = Field(default=None, max_length=80)
    clabe: str | None = Field(default=None, max_length=40)
    notas: str | None = Field(default=None, max_length=2000)
    activo: bool = True


class SupplierUpdateRequest(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    nombre_comercial: str | None = Field(default=None, max_length=160)
    razon_social: str | None = Field(default=None, max_length=200)
    rfc: str | None = Field(default=None, max_length=40)
    contacto_nombre: str | None = Field(default=None, max_length=160)
    contacto_principal: str | None = Field(default=None, max_length=160)
    correo: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=40)
    sitio_web: str | None = Field(default=None, max_length=255)
    direccion: str | None = Field(default=None, max_length=2000)
    ciudad: str | None = Field(default=None, max_length=120)
    estado: str | None = Field(default=None, max_length=120)
    pais: str | None = Field(default=None, max_length=120)
    codigo_postal: str | None = Field(default=None, max_length=20)
    telefono_contacto: str | None = Field(default=None, max_length=40)
    email_contacto: str | None = Field(default=None, max_length=255)
    moneda_preferida: str | None = Field(default=None, max_length=16)
    condiciones_pago: str | None = Field(default=None, max_length=2000)
    dias_credito: int | None = Field(default=None, ge=0)
    lead_time_dias: int | None = Field(default=None, ge=0)
    metodo_pago_preferido: str | None = Field(default=None, max_length=120)
    banco: str | None = Field(default=None, max_length=160)
    cuenta_bancaria: str | None = Field(default=None, max_length=80)
    clabe: str | None = Field(default=None, max_length=40)
    notas: str | None = Field(default=None, max_length=2000)
    activo: bool | None = None


class SupplierItem(BaseModel):
    id: str
    empresa_id: str
    nombre: str
    nombre_comercial: str | None = None
    razon_social: str | None = None
    rfc: str | None = None
    contacto_nombre: str | None = None
    contacto_principal: str | None = None
    correo: str | None = None
    email: str | None = None
    telefono: str | None = None
    sitio_web: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    estado: str | None = None
    pais: str | None = None
    codigo_postal: str | None = None
    telefono_contacto: str | None = None
    email_contacto: str | None = None
    moneda_preferida: str | None = None
    condiciones_pago: str | None = None
    dias_credito: int = 0
    lead_time_dias: int = 0
    metodo_pago_preferido: str | None = None
    banco: str | None = None
    cuenta_bancaria: str | None = None
    clabe: str | None = None
    notas: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierItem]
    total: int
    limit: int
    offset: int


class SupplierMaterialItem(BaseModel):
    material_id: str
    sku: str
    nombre: str
    unidad: str
    activo: bool
    es_proveedor_principal: bool = False
    ordenes_count: int = 0
    total_ordenado: Decimal = Decimal("0")
    total_recibido: Decimal = Decimal("0")
    monto_total_comprado: Decimal = Decimal("0")
    ultima_orden_at: datetime | None = None


class SupplierMaterialListResponse(BaseModel):
    items: list[SupplierMaterialItem]
    total: int
    limit: int
    offset: int


class SupplierReceiptListResponse(BaseModel):
    items: list["PurchaseOrderReceiptItem"]
    total: int
    limit: int
    offset: int


class SupplierSummaryResponse(BaseModel):
    proveedor: SupplierItem
    ordenes_totales: int
    ordenes_abiertas: int
    ordenes_recibidas: int
    monto_total_comprado: Decimal
    monto_pendiente_por_recibir: Decimal
    recepciones_totales: int
    materiales_asociados: int
    ordenes_recientes: list["PurchaseOrderItem"] = Field(default_factory=list)
    recepciones_recientes: list["PurchaseOrderReceiptItem"] = Field(default_factory=list)
    materiales_relacionados: list[SupplierMaterialItem] = Field(default_factory=list)


class RequisitionCreateRequest(BaseModel):
    folio: str | None = Field(default=None, max_length=60)
    notas: str | None = Field(default=None, max_length=2000)
    proveedor_sugerido_id: str | None = Field(default=None, max_length=64)
    es_proyecto: bool = False
    proyecto_id: str | None = Field(default=None, max_length=64)
    proyecto_nombre_snapshot: str | None = Field(default=None, max_length=180)
    prioridad: str = Field(default="normal", min_length=4, max_length=20)
    tarea_id: str | None = Field(default=None, max_length=64)
    partida_id: str | None = Field(default=None, max_length=64)


class RequisitionUpdateRequest(BaseModel):
    folio: str | None = Field(default=None, min_length=1, max_length=60)
    notas: str | None = Field(default=None, max_length=2000)
    proveedor_sugerido_id: str | None = Field(default=None, max_length=64)
    es_proyecto: bool | None = None
    proyecto_id: str | None = Field(default=None, max_length=64)
    proyecto_nombre_snapshot: str | None = Field(default=None, max_length=180)
    prioridad: str | None = Field(default=None, min_length=4, max_length=20)
    tarea_id: str | None = Field(default=None, max_length=64)
    partida_id: str | None = Field(default=None, max_length=64)


class RequisitionDetailCreateRequest(BaseModel):
    material_id: str = Field(min_length=1, max_length=64)
    cantidad: Decimal = Field(gt=0)
    notas: str | None = Field(default=None, max_length=2000)


class RequisitionDetailUpdateRequest(BaseModel):
    material_id: str | None = Field(default=None, min_length=1, max_length=64)
    cantidad: Decimal | None = Field(default=None, gt=0)
    notas: str | None = Field(default=None, max_length=2000)


class RequisitionDetailStockItem(BaseModel):
    almacen_id: str
    almacen_nombre: str
    stock_actual: Decimal


class RequisitionDetailItem(BaseModel):
    id: str
    requisicion_id: str
    material_id: str
    material_sku: str
    material_nombre: str
    material_unidad: str
    cantidad: Decimal
    cantidad_aprobada: Decimal
    cantidad_surtida: Decimal
    cantidad_pendiente: Decimal
    estado_linea: str
    stock_total: Decimal
    proveedor_sugerido_id: str | None = None
    proveedor_sugerido_nombre: str | None = None
    stock_por_almacen: list[RequisitionDetailStockItem] = Field(default_factory=list)
    notas: str | None = None


class RequisitionMovementTraceItem(BaseModel):
    id: str
    created_at: datetime
    almacen_id: str
    almacen_nombre: str
    tipo: str
    material_id: str
    material_sku: str
    material_nombre: str
    cantidad: Decimal
    documento_referencia: str | None = None
    notas: str | None = None
    proyecto_id: str | None = None
    proyecto_nombre_snapshot: str | None = None
    tarea_nombre_snapshot: str | None = None
    partida_nombre_snapshot: str | None = None
    created_by_nombre: str | None = None


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
    es_proyecto: bool = False
    proyecto_id: str | None = None
    proyecto_nombre_snapshot: str | None = None
    prioridad: str = "normal"
    tarea_id: str | None = None
    tarea_nombre_snapshot: str | None = None
    partida_id: str | None = None
    partida_nombre_snapshot: str | None = None
    aprobador_user_id: str | None = None
    estatus: str
    total_renglones: int
    cantidad_total_solicitada: Decimal
    cantidad_total_aprobada: Decimal
    cantidad_total_surtida: Decimal
    cantidad_total_pendiente: Decimal
    notas: str | None = None
    motivo_rechazo: str | None = None
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    fulfilled_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    details_count: int


class RequisitionResponse(RequisitionItem):
    details: list[RequisitionDetailItem]
    movements: list[RequisitionMovementTraceItem] = Field(default_factory=list)


class RequisitionListResponse(BaseModel):
    items: list[RequisitionItem]
    total: int
    limit: int
    offset: int


class RequisitionCreatePurchaseOrderRequest(BaseModel):
    proveedor_id: str = Field(min_length=1, max_length=64)
    almacen_destino_id: str = Field(min_length=1, max_length=64)
    folio: str | None = Field(default=None, max_length=60)


class RequisitionFulfillLineRequest(BaseModel):
    detail_id: str = Field(min_length=1, max_length=64)
    cantidad_surtir: Decimal = Field(gt=0)


class RequisitionApproveLineRequest(BaseModel):
    detail_id: str = Field(min_length=1, max_length=64)
    cantidad_aprobada: Decimal = Field(gt=0)


class RequisitionApproveRequest(BaseModel):
    items: list[RequisitionApproveLineRequest] = Field(default_factory=list)


class RequisitionRejectRequest(BaseModel):
    motivo_rechazo: str = Field(min_length=3, max_length=2000)


class RequisitionFulfillRequest(BaseModel):
    almacen_id: str = Field(min_length=1, max_length=64)
    documento_referencia: str | None = Field(default=None, max_length=160)
    notas: str | None = Field(default=None, max_length=2000)
    proyecto_id: str | None = Field(default=None, max_length=64)
    proyecto_nombre_snapshot: str | None = Field(default=None, max_length=180)
    items: list[RequisitionFulfillLineRequest] = Field(min_length=1)


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
    cantidad: Decimal | None = Field(default=None, gt=0)
    cantidad_recibida: Decimal | None = Field(default=None, gt=0)

    @property
    def resolved_cantidad(self) -> Decimal:
        return self.cantidad_recibida if self.cantidad_recibida is not None else self.cantidad or Decimal("0")


class PurchaseOrderReceiveRequest(BaseModel):
    almacen_id: str = Field(min_length=1, max_length=64)
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
    ultima_recepcion_at: datetime | None = None


class PurchaseOrderMovementTraceItem(BaseModel):
    id: str
    created_at: datetime
    almacen_id: str
    almacen_nombre: str
    tipo: str
    material_id: str
    material_sku: str
    material_nombre: str
    cantidad: Decimal
    documento_referencia: str | None = None
    notas: str | None = None
    recibido_por: str | None = None
    created_by_nombre: str | None = None
    grupo_referencia: str | None = None


class PurchaseOrderPendingQuantityItem(BaseModel):
    detail_id: str
    material_id: str
    material_sku: str
    material_nombre: str
    cantidad_ordenada: Decimal
    cantidad_recibida: Decimal
    cantidad_pendiente: Decimal
    estado_linea: str


class PurchaseOrderReceiptDetailItem(BaseModel):
    id: str
    recepcion_id: str
    orden_compra_detalle_id: str
    material_id: str
    material_sku: str
    material_nombre: str
    material_unidad: str
    cantidad_recibida: Decimal
    costo_unitario_snapshot: Decimal
    movimiento_inventario_id: str | None = None


class PurchaseOrderReceiptItem(BaseModel):
    id: str
    empresa_id: str
    orden_compra_id: str
    almacen_id: str
    almacen_nombre: str
    documento_referencia: str | None = None
    notas: str | None = None
    recibido_por_user_id: str
    recibido_por_nombre: str
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseOrderReceiptDetailItem] = Field(default_factory=list)
    movements: list[PurchaseOrderMovementTraceItem] = Field(default_factory=list)


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
    fecha_emitida: datetime | None = None
    fecha_esperada: datetime | None = None
    fecha_ultima_recepcion: datetime | None = None
    documento_referencia: str | None = None
    notas_recepcion: str | None = None
    recibido_por_user_id: str | None = None
    recibido_por_nombre: str | None = None
    proveedor_contacto_snapshot: str | None = None
    proveedor_email_snapshot: str | None = None
    proveedor_telefono_snapshot: str | None = None
    condiciones_pago_snapshot: str | None = None
    moneda_snapshot: str | None = None
    notas: str | None = None
    created_at: datetime
    updated_at: datetime
    details_count: int
    cantidad_renglones: int
    cantidad_total_ordenada: Decimal
    cantidad_total_recibida: Decimal
    cantidad_total_pendiente: Decimal
    valor_total_recibido: Decimal = Decimal("0")
    valor_total_pendiente: Decimal = Decimal("0")
    recepciones_count: int = 0
    requisicion_id: str | None = None
    requisicion_folio: str | None = None


class PurchaseOrderResponse(PurchaseOrderItem):
    details: list[PurchaseOrderDetailItem]
    movements: list[PurchaseOrderMovementTraceItem]
    receipts: list[PurchaseOrderReceiptItem] = Field(default_factory=list)


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderItem]
    total: int
    limit: int
    offset: int


class PurchaseOrderReceiptListResponse(BaseModel):
    items: list[PurchaseOrderReceiptItem]


class PurchaseOrderReceiveResponse(BaseModel):
    order: PurchaseOrderResponse
    receipt: PurchaseOrderReceiptItem
    movements: list[PurchaseOrderMovementTraceItem]
    pending_items: list[PurchaseOrderPendingQuantityItem] = Field(default_factory=list)
    cantidad_total_recibida: Decimal
    cantidad_total_pendiente: Decimal


class PurchaseOrderPendingReportKpis(BaseModel):
    ordenes_pendientes: int
    ordenes_parciales: int
    materiales_pendientes: int
    monto_pendiente: Decimal


class PurchaseOrderPendingReportOrderItem(BaseModel):
    id: str
    folio: str
    proveedor: str
    estatus: str
    fecha_emitida: datetime | None = None
    fecha_esperada: datetime | None = None
    total: Decimal
    pendiente: Decimal
    cantidad_pendiente: Decimal


class PurchaseOrderPendingReportMaterialItem(BaseModel):
    material_id: str
    material: str
    sku: str
    cantidad_pendiente: Decimal
    proveedor: str
    ordenes_abiertas: int


class PurchaseOrderPendingReportSupplierItem(BaseModel):
    proveedor_id: str
    proveedor: str
    ordenes_abiertas: int
    monto_pendiente: Decimal


class PurchaseOrderPendingReportResponse(BaseModel):
    kpis: PurchaseOrderPendingReportKpis
    ordenes: list[PurchaseOrderPendingReportOrderItem] = Field(default_factory=list)
    materiales: list[PurchaseOrderPendingReportMaterialItem] = Field(default_factory=list)
    proveedores: list[PurchaseOrderPendingReportSupplierItem] = Field(default_factory=list)
