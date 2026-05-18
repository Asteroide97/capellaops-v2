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


class MaterialCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    nombre: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=2000)
    categoria: str | None = Field(default=None, max_length=120)
    unidad: str = Field(min_length=1, max_length=40)
    costo_unitario: Decimal = Field(default=Decimal("0"), ge=0)
    precio_venta: Decimal = Field(default=Decimal("0"), ge=0)
    stock_minimo: Decimal = Field(default=Decimal("0"), ge=0)
    activo: bool = True


class MaterialUpdateRequest(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    nombre: str | None = Field(default=None, min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=2000)
    categoria: str | None = Field(default=None, max_length=120)
    unidad: str | None = Field(default=None, min_length=1, max_length=40)
    costo_unitario: Decimal | None = Field(default=None, ge=0)
    precio_venta: Decimal | None = Field(default=None, ge=0)
    stock_minimo: Decimal | None = Field(default=None, ge=0)
    activo: bool | None = None


class MaterialItem(BaseModel):
    id: str
    empresa_id: str
    sku: str
    nombre: str
    descripcion: str | None = None
    categoria: str | None = None
    unidad: str
    costo_unitario: Decimal
    precio_venta: Decimal
    stock_minimo: Decimal
    activo: bool
    created_at: datetime
    updated_at: datetime


class MaterialListResponse(BaseModel):
    items: list[MaterialItem]
    total: int
    limit: int
    offset: int


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
    notas: str | None = Field(default=None, max_length=2000)


class MovementItem(BaseModel):
    id: str
    empresa_id: str
    almacen_id: str
    almacen_nombre: str
    material_id: str
    material_sku: str
    material_nombre: str
    tipo: str
    cantidad: Decimal
    cantidad_anterior: Decimal
    cantidad_nueva: Decimal
    referencia_tipo: str | None = None
    referencia_id: str | None = None
    notas: str | None = None
    created_by: str
    created_at: datetime


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
