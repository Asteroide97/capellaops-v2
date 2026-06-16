from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class CRMClientCreateRequest(BaseModel):
    nombre_comercial: str = Field(min_length=1, max_length=180)
    razon_social: str | None = Field(default=None, max_length=200)
    rfc: str | None = Field(default=None, max_length=40)
    tipo: Literal["prospecto", "cliente", "otro"] = "prospecto"
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=40)
    sitio_web: str | None = Field(default=None, max_length=255)
    direccion: str | None = Field(default=None, max_length=2000)
    ciudad: str | None = Field(default=None, max_length=120)
    estado: str | None = Field(default=None, max_length=120)
    pais: str | None = Field(default=None, max_length=120)
    codigo_postal: str | None = Field(default=None, max_length=20)
    origen: str | None = Field(default=None, max_length=120)
    industria: str | None = Field(default=None, max_length=120)
    notas: str | None = Field(default=None, max_length=4000)
    estatus: Literal["activo", "inactivo"] = "activo"


class CRMClientUpdateRequest(BaseModel):
    nombre_comercial: str | None = Field(default=None, min_length=1, max_length=180)
    razon_social: str | None = Field(default=None, max_length=200)
    rfc: str | None = Field(default=None, max_length=40)
    tipo: Literal["prospecto", "cliente", "otro"] | None = None
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=40)
    sitio_web: str | None = Field(default=None, max_length=255)
    direccion: str | None = Field(default=None, max_length=2000)
    ciudad: str | None = Field(default=None, max_length=120)
    estado: str | None = Field(default=None, max_length=120)
    pais: str | None = Field(default=None, max_length=120)
    codigo_postal: str | None = Field(default=None, max_length=20)
    origen: str | None = Field(default=None, max_length=120)
    industria: str | None = Field(default=None, max_length=120)
    notas: str | None = Field(default=None, max_length=4000)
    estatus: Literal["activo", "inactivo"] | None = None


class CRMClientItem(BaseModel):
    id: str
    empresa_id: str
    nombre_comercial: str
    razon_social: str | None = None
    rfc: str | None = None
    tipo: str
    email: str | None = None
    telefono: str | None = None
    sitio_web: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    estado: str | None = None
    pais: str | None = None
    codigo_postal: str | None = None
    origen: str | None = None
    industria: str | None = None
    notas: str | None = None
    estatus: str
    created_at: datetime
    updated_at: datetime


class CRMClientListResponse(BaseModel):
    items: list[CRMClientItem]
    total: int
    limit: int
    offset: int


class CRMClientTimelineItem(BaseModel):
    tipo: str
    fecha: datetime
    titulo: str
    descripcion: str | None = None
    monto: Decimal | None = None
    estatus: str | None = None
    referencia_id: str


class CRMClientTimelineResponse(BaseModel):
    items: list[CRMClientTimelineItem]


class CRMClientCommercialSummaryResponse(BaseModel):
    client_id: str
    total_ventas_pos: Decimal = Decimal("0")
    ventas_count: int = 0
    proyectos_count: int = 0
    proyectos_activos: int = 0
    oportunidades_abiertas: int = 0
    monto_pipeline: Decimal = Decimal("0")
    facturas_solicitadas: int = 0
    actividades_pendientes: int = 0
    ultima_actividad_at: datetime | None = None


class CRMContactCreateRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    puesto: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=40)
    whatsapp: str | None = Field(default=None, max_length=40)
    principal: bool = False
    notas: str | None = Field(default=None, max_length=4000)
    activo: bool = True


class CRMContactUpdateRequest(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    puesto: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=40)
    whatsapp: str | None = Field(default=None, max_length=40)
    principal: bool | None = None
    notas: str | None = Field(default=None, max_length=4000)
    activo: bool | None = None


class CRMContactItem(BaseModel):
    id: str
    empresa_id: str
    cliente_id: str
    cliente_nombre_comercial: str | None = None
    nombre: str
    puesto: str | None = None
    email: str | None = None
    telefono: str | None = None
    whatsapp: str | None = None
    principal: bool
    notas: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class CRMContactListResponse(BaseModel):
    items: list[CRMContactItem]
    total: int
    limit: int
    offset: int


class CRMOpportunityCreateRequest(BaseModel):
    cliente_id: str = Field(min_length=1, max_length=36)
    contacto_id: str | None = Field(default=None, max_length=36)
    titulo: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    etapa: Literal["nueva", "contactado", "propuesta", "negociacion", "ganada", "perdida"] = "nueva"
    monto_estimado: Decimal = Field(default=Decimal("0"), ge=0)
    probabilidad: int = Field(default=0, ge=0, le=100)
    fecha_estimada_cierre: date | None = None
    responsable_user_id: str | None = Field(default=None, max_length=36)
    origen: str | None = Field(default=None, max_length=120)
    motivo_perdida: str | None = Field(default=None, max_length=4000)
    notas: str | None = Field(default=None, max_length=4000)
    activa: bool = True


class CRMOpportunityUpdateRequest(BaseModel):
    cliente_id: str | None = Field(default=None, max_length=36)
    contacto_id: str | None = Field(default=None, max_length=36)
    titulo: str | None = Field(default=None, min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    etapa: Literal["nueva", "contactado", "propuesta", "negociacion", "ganada", "perdida"] | None = None
    monto_estimado: Decimal | None = Field(default=None, ge=0)
    probabilidad: int | None = Field(default=None, ge=0, le=100)
    fecha_estimada_cierre: date | None = None
    responsable_user_id: str | None = Field(default=None, max_length=36)
    origen: str | None = Field(default=None, max_length=120)
    motivo_perdida: str | None = Field(default=None, max_length=4000)
    notas: str | None = Field(default=None, max_length=4000)
    activa: bool | None = None


class CRMOpportunityCloseWonRequest(BaseModel):
    notas: str | None = Field(default=None, max_length=4000)


class CRMOpportunityCloseLostRequest(BaseModel):
    motivo_perdida: str = Field(min_length=1, max_length=4000)
    notas: str | None = Field(default=None, max_length=4000)


class CRMOpportunityItem(BaseModel):
    id: str
    empresa_id: str
    cliente_id: str
    cliente_nombre_comercial: str | None = None
    contacto_id: str | None = None
    contacto_nombre: str | None = None
    titulo: str
    descripcion: str | None = None
    etapa: str
    monto_estimado: Decimal
    probabilidad: int
    fecha_estimada_cierre: date | None = None
    responsable_user_id: str | None = None
    responsable_nombre: str | None = None
    origen: str | None = None
    motivo_perdida: str | None = None
    notas: str | None = None
    activa: bool
    cerrada_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CRMOpportunityListResponse(BaseModel):
    items: list[CRMOpportunityItem]
    total: int
    limit: int
    offset: int


class CRMActivityCreateRequest(BaseModel):
    cliente_id: str | None = Field(default=None, max_length=36)
    oportunidad_id: str | None = Field(default=None, max_length=36)
    contacto_id: str | None = Field(default=None, max_length=36)
    tipo: Literal["llamada", "email", "reunion", "tarea", "nota", "whatsapp", "otro"] = "nota"
    titulo: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    fecha_actividad: datetime
    fecha_vencimiento: datetime | None = None
    completada: bool = False
    usuario_id: str | None = Field(default=None, max_length=36)
    activo: bool = True


class CRMActivityUpdateRequest(BaseModel):
    cliente_id: str | None = Field(default=None, max_length=36)
    oportunidad_id: str | None = Field(default=None, max_length=36)
    contacto_id: str | None = Field(default=None, max_length=36)
    tipo: Literal["llamada", "email", "reunion", "tarea", "nota", "whatsapp", "otro"] | None = None
    titulo: str | None = Field(default=None, min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=4000)
    fecha_actividad: datetime | None = None
    fecha_vencimiento: datetime | None = None
    completada: bool | None = None
    usuario_id: str | None = Field(default=None, max_length=36)
    activo: bool | None = None


class CRMActivityItem(BaseModel):
    id: str
    empresa_id: str
    cliente_id: str | None = None
    cliente_nombre_comercial: str | None = None
    oportunidad_id: str | None = None
    oportunidad_titulo: str | None = None
    contacto_id: str | None = None
    contacto_nombre: str | None = None
    tipo: str
    titulo: str
    descripcion: str | None = None
    fecha_actividad: datetime
    fecha_vencimiento: datetime | None = None
    completada: bool
    completada_at: datetime | None = None
    usuario_id: str | None = None
    usuario_nombre: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


class CRMActivityListResponse(BaseModel):
    items: list[CRMActivityItem]
    total: int
    limit: int
    offset: int


class CRMSummaryKpis(BaseModel):
    clientes_activos: int
    prospectos: int
    oportunidades_abiertas: int
    oportunidades_ganadas: int
    oportunidades_perdidas: int
    monto_pipeline: Decimal
    monto_ganado: Decimal
    actividades_pendientes: int
    actividades_vencidas: int


class CRMSummaryPipelineStageItem(BaseModel):
    etapa: str
    oportunidades_count: int
    monto_total: Decimal


class CRMSummaryResponse(BaseModel):
    kpis: CRMSummaryKpis
    pipeline_por_etapa: list[CRMSummaryPipelineStageItem]
    oportunidades_recientes: list[CRMOpportunityItem]
    actividades_pendientes: list[CRMActivityItem]
    clientes_recientes: list[CRMClientItem]
