from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class WarehouseCreateRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    codigo: str = Field(min_length=1, max_length=60)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool = True


class WarehouseUpdateRequest(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    codigo: str | None = Field(default=None, min_length=1, max_length=60)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool | None = None


class WarehouseItem(BaseModel):
    id: str
    empresa_id: str
    nombre: str
    codigo: str
    descripcion: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class WarehouseListResponse(BaseModel):
    items: list[WarehouseItem]
    total: int
    limit: int
    offset: int


class InventoryOnboardingStatusResponse(BaseModel):
    requires_first_warehouse: bool
    warehouses_count: int
    message: str


class InventorySummaryKpis(BaseModel):
    valor_total_inventario: Decimal = Decimal("0")
    materiales_bajo_stock: int
    materiales_sin_stock: int = 0
    materiales_sin_precio_venta: int = 0
    materiales_sin_costo: int = 0
    ordenes_compra_pendientes: int
    requisiciones_pendientes: int
    movimientos_mes: int = 0
    total_materiales: int


class InventorySummaryIndicators(BaseModel):
    valor_inventario: Decimal
    costo_reposicion: Decimal
    ajustes_mes: int
    merma_mes: Decimal


class InventorySummaryCoreProductItem(BaseModel):
    material_id: str
    sku: str
    nombre: str
    categoria: str | None = None
    stock_total: Decimal
    valor_total: Decimal
    dias_sin_movimiento: int


class InventorySummaryLowRotationItem(BaseModel):
    material_id: str
    sku: str
    nombre: str
    categoria: str | None = None
    stock_total: Decimal
    valor_retenido: Decimal
    dias_sin_movimiento: int


class InventorySummaryLowStockItem(BaseModel):
    material_id: str
    sku: str
    nombre: str
    categoria: str | None = None
    stock_total: Decimal
    stock_minimo: Decimal
    stock_maximo: Decimal = Decimal("0")
    faltante: Decimal
    cantidad_sugerida: Decimal = Decimal("0")
    estado: str
    requisicion_pendiente: bool = False
    requisicion_id: str | None = None
    requisicion_folio: str | None = None


class InventorySummaryMaterialIssueItem(BaseModel):
    material_id: str
    sku: str
    nombre: str
    categoria: str | None = None
    stock_total: Decimal = Decimal("0")
    precio_venta: Decimal | None = None
    costo_unitario: Decimal | None = None
    costo_promedio_actual: Decimal | None = None
    valor_inventario: Decimal = Decimal("0")


class InventorySummaryTopMovementItem(BaseModel):
    material_id: str
    sku: str
    nombre: str
    categoria: str | None = None
    cantidad_entrada: Decimal = Decimal("0")
    cantidad_salida: Decimal = Decimal("0")
    movimientos_count: int = 0


class InventorySummaryRecentMovementItem(BaseModel):
    id: str
    fecha: datetime
    tipo: str
    material_id: str
    material_sku: str
    material_nombre: str
    almacen_id: str
    almacen_nombre: str
    cantidad: Decimal
    referencia: str | None = None
    usuario: str | None = None


class InventorySummaryAlertItem(BaseModel):
    tipo: str
    severidad: str
    titulo: str
    descripcion: str
    accion_label: str | None = None
    accion_url: str | None = None
    action: str | None = None
    material_id: str | None = None
    almacen_id: str | None = None
    requisicion_id: str | None = None
    nivel: str | None = None
    mensaje: str | None = None
    route: str | None = None


class InventorySummaryResponse(BaseModel):
    kpis: InventorySummaryKpis
    indicadores: InventorySummaryIndicators
    productos_core: list[InventorySummaryCoreProductItem]
    baja_rotacion: list[InventorySummaryLowRotationItem]
    materiales_bajo_stock: list[InventorySummaryLowStockItem]
    bajo_stock: list[InventorySummaryLowStockItem] = Field(default_factory=list)
    sin_precio_venta: list[InventorySummaryMaterialIssueItem] = Field(default_factory=list)
    sin_costo: list[InventorySummaryMaterialIssueItem] = Field(default_factory=list)
    productos_mas_movidos: list[InventorySummaryTopMovementItem] = Field(default_factory=list)
    ultimos_movimientos: list[InventorySummaryRecentMovementItem] = Field(default_factory=list)
    alertas: list[InventorySummaryAlertItem]


class MaterialCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    nombre: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=2000)
    categoria: str = Field(min_length=1, max_length=120)
    subcategoria: str | None = Field(default=None, max_length=120)
    unidad: str = Field(min_length=1, max_length=40)
    imagen_url: str | None = Field(default=None, max_length=1000)
    imagenes_extra: list[str] | None = None
    codigo_barras: str | None = Field(default=None, max_length=120)
    costo_unitario: Decimal = Field(default=Decimal("0"), ge=0)
    costo_promedio_actual: Decimal | None = Field(default=None, ge=0)
    precio_venta: Decimal = Field(default=Decimal("0"), ge=0)
    stock_minimo: Decimal = Field(default=Decimal("0"), ge=0)
    stock_maximo: Decimal = Field(default=Decimal("0"), ge=0)
    ubicacion_texto: str | None = Field(default=None, max_length=255)
    proveedor_principal_id: str | None = Field(default=None, max_length=64)
    lead_time_dias: int = Field(default=0, ge=0)
    activo: bool = True


class MaterialUpdateRequest(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    nombre: str | None = Field(default=None, min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=2000)
    categoria: str | None = Field(default=None, max_length=120)
    subcategoria: str | None = Field(default=None, max_length=120)
    unidad: str | None = Field(default=None, min_length=1, max_length=40)
    imagen_url: str | None = Field(default=None, max_length=1000)
    imagenes_extra: list[str] | None = None
    codigo_barras: str | None = Field(default=None, max_length=120)
    costo_unitario: Decimal | None = Field(default=None, ge=0)
    costo_promedio_actual: Decimal | None = Field(default=None, ge=0)
    precio_venta: Decimal | None = Field(default=None, ge=0)
    stock_minimo: Decimal | None = Field(default=None, ge=0)
    stock_maximo: Decimal | None = Field(default=None, ge=0)
    ubicacion_texto: str | None = Field(default=None, max_length=255)
    proveedor_principal_id: str | None = Field(default=None, max_length=64)
    lead_time_dias: int | None = Field(default=None, ge=0)
    activo: bool | None = None


class MaterialItem(BaseModel):
    id: str
    empresa_id: str
    sku: str
    nombre: str
    descripcion: str | None = None
    categoria: str | None = None
    subcategoria: str | None = None
    unidad: str
    imagen_url: str | None = None
    imagenes_extra: list[str] = Field(default_factory=list)
    codigo_barras: str | None = None
    costo_unitario: Decimal
    costo_promedio_actual: Decimal | None = None
    precio_venta: Decimal
    stock_minimo: Decimal
    stock_maximo: Decimal
    stock_total: Decimal
    valor_inventario: Decimal
    ubicacion_texto: str | None = None
    proveedor_principal_id: str | None = None
    proveedor_principal_nombre: str | None = None
    proveedor_principal_rfc: str | None = None
    lead_time_dias: int
    stock_bajo: bool
    activo: bool
    created_at: datetime
    updated_at: datetime


class MaterialListResponse(BaseModel):
    items: list[MaterialItem]
    total: int
    limit: int
    offset: int


class MaterialLookupWarehouseStockItem(BaseModel):
    almacen_id: str
    almacen_nombre: str
    stock_actual: Decimal


class MaterialLookupItem(MaterialItem):
    stock_por_almacen: list[MaterialLookupWarehouseStockItem] = Field(default_factory=list)


class MaterialLookupResponse(BaseModel):
    material: MaterialLookupItem


class MaterialImageUploadResponse(BaseModel):
    imagen_url: str
    filename: str
    content_type: str
    size_bytes: int


class StockItem(BaseModel):
    id: str
    empresa_id: str
    almacen_id: str
    almacen_nombre: str
    almacen_codigo: str
    material_id: str
    material_sku: str
    material_nombre: str
    material_unidad: str
    stock_minimo: Decimal
    cantidad: Decimal
    low_stock: bool
    updated_at: datetime


class StockListResponse(BaseModel):
    items: list[StockItem]
    total: int
    limit: int
    offset: int


class InventoryMovementCreateRequest(BaseModel):
    almacen_id: str = Field(min_length=1, max_length=64)
    material_id: str = Field(min_length=1, max_length=64)
    tipo: Literal["entrada", "salida", "ajuste"]
    cantidad: Decimal | None = Field(default=None, gt=0)
    cantidad_nueva: Decimal | None = Field(default=None, ge=0)
    referencia_tipo: str | None = Field(default=None, max_length=60)
    referencia_id: str | None = Field(default=None, max_length=64)
    motivo: str | None = Field(default=None, max_length=160)
    entregado_por: str | None = Field(default=None, max_length=160)
    recibido_por: str | None = Field(default=None, max_length=160)
    documento_referencia: str | None = Field(default=None, max_length=160)
    evidencia_url: str | None = Field(default=None, max_length=1000)
    es_proyecto: bool = False
    proyecto_id: str | None = Field(default=None, max_length=64)
    proyecto_nombre_snapshot: str | None = Field(default=None, max_length=180)
    pm_tarea_id: str | None = Field(default=None, max_length=64)
    pm_tarea_nombre_snapshot: str | None = Field(default=None, max_length=180)
    pm_partida_id: str | None = Field(default=None, max_length=64)
    pm_partida_nombre_snapshot: str | None = Field(default=None, max_length=180)
    costo_unitario: Decimal | None = Field(default=None, ge=0)
    notas: str | None = Field(default=None, max_length=2000)


class InventoryBulkMovementLineCreateRequest(BaseModel):
    material_id: str = Field(min_length=1, max_length=64)
    cantidad: Decimal | None = Field(default=None, gt=0)
    cantidad_nueva: Decimal | None = Field(default=None, ge=0)
    costo_unitario: Decimal | None = Field(default=None, ge=0)
    notas: str | None = Field(default=None, max_length=500)


class InventoryBulkMovementCreateRequest(BaseModel):
    almacen_id: str = Field(min_length=1, max_length=64)
    tipo: Literal["entrada", "salida", "ajuste"]
    referencia_tipo: str | None = Field(default=None, max_length=60)
    referencia_id: str | None = Field(default=None, max_length=64)
    motivo: str | None = Field(default=None, max_length=160)
    entregado_por: str | None = Field(default=None, max_length=160)
    recibido_por: str | None = Field(default=None, max_length=160)
    documento_referencia: str | None = Field(default=None, max_length=160)
    evidencia_url: str | None = Field(default=None, max_length=1000)
    es_proyecto: bool = False
    proyecto_id: str | None = Field(default=None, max_length=64)
    proyecto_nombre_snapshot: str | None = Field(default=None, max_length=180)
    pm_tarea_id: str | None = Field(default=None, max_length=64)
    pm_tarea_nombre_snapshot: str | None = Field(default=None, max_length=180)
    pm_partida_id: str | None = Field(default=None, max_length=64)
    pm_partida_nombre_snapshot: str | None = Field(default=None, max_length=180)
    notas: str | None = Field(default=None, max_length=2000)
    items: list[InventoryBulkMovementLineCreateRequest] = Field(min_length=1, max_length=100)


class MovementItem(BaseModel):
    id: str
    empresa_id: str
    almacen_id: str
    almacen_nombre: str
    material_id: str
    material_sku: str
    material_nombre: str
    tipo: str
    estatus: str
    cantidad: Decimal
    cantidad_anterior: Decimal
    cantidad_nueva: Decimal
    referencia_tipo: str | None = None
    referencia_id: str | None = None
    grupo_referencia: str | None = None
    motivo: str | None = None
    entregado_por: str | None = None
    recibido_por: str | None = None
    documento_referencia: str | None = None
    evidencia_url: str | None = None
    es_proyecto: bool = False
    proyecto_id: str | None = None
    proyecto_nombre_snapshot: str | None = None
    pm_tarea_id: str | None = None
    pm_tarea_nombre_snapshot: str | None = None
    pm_partida_id: str | None = None
    pm_partida_nombre_snapshot: str | None = None
    costo_unitario_snapshot: Decimal | None = None
    costo_promedio_snapshot: Decimal | None = None
    costo_total_snapshot: Decimal | None = None
    valor_inventario: Decimal | None = None
    notas: str | None = None
    created_by: str
    created_by_nombre: str | None = None
    created_at: datetime


class InventoryBulkMovementResponse(BaseModel):
    group_reference: str
    tipo: str
    almacen_id: str
    movement_count: int
    items: list[MovementItem]


class MovementListResponse(BaseModel):
    items: list[MovementItem]
    total: int
    limit: int
    offset: int


class KardexStockItem(BaseModel):
    almacen_id: str
    almacen_nombre: str
    almacen_codigo: str
    cantidad: Decimal


class KardexResponse(BaseModel):
    material: MaterialItem
    existencia_total: Decimal
    stock_por_almacen: list[KardexStockItem]
    movements: list[MovementItem]


class InventoryProjectSummaryItem(BaseModel):
    project_id: str
    nombre: str
    codigo: str | None = None
    estatus: str
    total_materiales_consumidos: Decimal = Decimal("0")
    costo_materiales_real: Decimal = Decimal("0")
    movimientos_count: int = 0
    ultimo_movimiento_at: datetime | None = None


class InventoryProjectListResponse(BaseModel):
    items: list[InventoryProjectSummaryItem]
    total: int
    limit: int
    offset: int


class InventoryProjectMaterialItem(BaseModel):
    material_id: str
    material_sku: str
    material_nombre: str
    unidad: str
    cantidad_consumida: Decimal = Decimal("0")
    costo_total: Decimal = Decimal("0")
    almacenes_involucrados: list[str] = Field(default_factory=list)
    ultima_salida_at: datetime | None = None
    tarea_titulos: list[str] = Field(default_factory=list)
    partida_titulos: list[str] = Field(default_factory=list)


class InventoryProjectMaterialsResponse(BaseModel):
    project_id: str
    items: list[InventoryProjectMaterialItem] = Field(default_factory=list)


class TransferDetailCreateRequest(BaseModel):
    material_id: str = Field(min_length=1, max_length=64)
    cantidad: Decimal = Field(gt=0)
    costo_unitario_snapshot: Decimal | None = Field(default=None, ge=0)


class TransferDetailUpdateRequest(BaseModel):
    material_id: str | None = Field(default=None, min_length=1, max_length=64)
    cantidad: Decimal | None = Field(default=None, gt=0)
    costo_unitario_snapshot: Decimal | None = Field(default=None, ge=0)


class TransferCreateRequest(BaseModel):
    folio: str | None = Field(default=None, max_length=60)
    almacen_origen_id: str = Field(min_length=1, max_length=64)
    almacen_destino_id: str = Field(min_length=1, max_length=64)
    notas: str | None = Field(default=None, max_length=2000)


class TransferUpdateRequest(BaseModel):
    folio: str | None = Field(default=None, min_length=1, max_length=60)
    almacen_origen_id: str | None = Field(default=None, min_length=1, max_length=64)
    almacen_destino_id: str | None = Field(default=None, min_length=1, max_length=64)
    notas: str | None = Field(default=None, max_length=2000)


class TransferDetailItem(BaseModel):
    id: str
    transferencia_id: str
    material_id: str
    material_sku: str
    material_nombre: str
    material_unidad: str
    cantidad: Decimal
    costo_unitario_snapshot: Decimal | None = None


class TransferItem(BaseModel):
    id: str
    empresa_id: str
    folio: str
    almacen_origen_id: str
    almacen_origen_nombre: str
    almacen_destino_id: str
    almacen_destino_nombre: str
    estatus: str
    notas: str | None = None
    created_by_user_id: str
    confirmed_by_user_id: str | None = None
    cancelled_by_user_id: str | None = None
    created_at: datetime
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    detalles_count: int


class TransferResponse(TransferItem):
    details: list[TransferDetailItem]


class TransferListResponse(BaseModel):
    items: list[TransferItem]
    total: int
    limit: int
    offset: int


class CountCreateRequest(BaseModel):
    folio: str | None = Field(default=None, max_length=60)
    almacen_id: str = Field(min_length=1, max_length=64)
    notas: str | None = Field(default=None, max_length=2000)


class CountUpdateRequest(BaseModel):
    folio: str | None = Field(default=None, min_length=1, max_length=60)
    almacen_id: str | None = Field(default=None, min_length=1, max_length=64)
    notas: str | None = Field(default=None, max_length=2000)


class CountDetailCreateRequest(BaseModel):
    material_id: str = Field(min_length=1, max_length=64)
    cantidad_fisica: Decimal = Field(ge=0)


class CountDetailUpdateRequest(BaseModel):
    material_id: str | None = Field(default=None, min_length=1, max_length=64)
    cantidad_fisica: Decimal | None = Field(default=None, ge=0)


class CountDetailItem(BaseModel):
    id: str
    conteo_id: str
    material_id: str
    material_sku: str
    material_nombre: str
    material_unidad: str
    cantidad_sistema_snapshot: Decimal
    cantidad_fisica: Decimal
    diferencia: Decimal
    ajuste_movimiento_id: str | None = None


class CountItem(BaseModel):
    id: str
    empresa_id: str
    almacen_id: str
    almacen_nombre: str
    folio: str
    estatus: str
    notas: str | None = None
    created_by_user_id: str
    applied_by_user_id: str | None = None
    cancelled_by_user_id: str | None = None
    created_at: datetime
    applied_at: datetime | None = None
    cancelled_at: datetime | None = None
    detalles_count: int


class CountResponse(CountItem):
    details: list[CountDetailItem]


class CountListResponse(BaseModel):
    items: list[CountItem]
    total: int
    limit: int
    offset: int
