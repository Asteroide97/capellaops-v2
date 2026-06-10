from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.pos import SaleDetailItem, SalePaymentItem


class BillingInvoiceValidationResult(BaseModel):
    is_valid: bool
    errors: list[str] = Field(default_factory=list)


class BillingInvoiceActionRequest(BaseModel):
    nota: str | None = Field(default=None, max_length=2000)


class BillingPosInvoiceRequestItem(BaseModel):
    venta_id: str
    folio: str
    fecha_venta: datetime
    total: Decimal
    estado_solicitud: str
    estado_revision: str
    cliente: str | None = None
    rfc: str | None = None
    razon_social: str | None = None
    email: str | None = None
    uso_cfdi: str | None = None
    regimen_fiscal: str | None = None
    codigo_postal: str | None = None
    notas: str | None = None
    errores_datos: list[str] = Field(default_factory=list)
    venta_cancelada: bool = False


class BillingPosInvoiceRequestDetail(BillingPosInvoiceRequestItem):
    venta_estatus: str
    factura_solicitada_at: datetime | None = None
    factura_revisada_at: datetime | None = None
    factura_preparada_at: datetime | None = None
    factura_descartada_at: datetime | None = None
    factura_revision_notas: str | None = None
    revisada_por_user_id: str | None = None
    revisada_por_nombre: str | None = None
    productos: list[SaleDetailItem] = Field(default_factory=list)
    pagos: list[SalePaymentItem] = Field(default_factory=list)
    validation: BillingInvoiceValidationResult


class BillingPosInvoiceRequestKpis(BaseModel):
    pendientes_datos: int = 0
    listas_para_facturar: int = 0
    en_revision: int = 0
    observadas: int = 0
    preparadas: int = 0


class BillingPosInvoiceRequestListResponse(BaseModel):
    items: list[BillingPosInvoiceRequestItem]
    total: int
    limit: int
    offset: int
    kpis: BillingPosInvoiceRequestKpis
