from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import CompanyLimitsSummary


class SuperadminPlanCounts(BaseModel):
    basico: int
    pro: int
    total: int


class SuperadminOverviewResponse(BaseModel):
    total_empresas: int
    total_usuarios: int
    empresas_en_trial: int
    empresas_activas: int
    empresas_suspendidas: int
    trials_por_vencer_7_dias: int
    plan_counts: SuperadminPlanCounts


class SuperadminAuditLogItem(BaseModel):
    id: str
    empresa_id: str | None = None
    empresa_nombre: str | None = None
    usuario_id: str | None = None
    usuario_nombre: str | None = None
    action: str
    entity_name: str
    entity_id: str | None = None
    created_at: datetime
    metadata_json: dict | None = None


class SuperadminCompanyListItem(BaseModel):
    id: str
    nombre: str
    razon_social: str | None = None
    rfc: str | None = None
    plan_code: str
    access_status: str
    trial_ends_at: datetime
    created_at: datetime
    usuarios_count: int
    almacenes_count: int
    materiales_count: int
    max_usuarios: int | None = None
    max_almacenes: int | None = None
    ultimo_login_at: datetime | None = None
    estado_pago: str | None = None


class SuperadminCompanyListResponse(BaseModel):
    total: int
    items: list[SuperadminCompanyListItem]


class SuperadminCompanyUserItem(BaseModel):
    membership_id: str
    usuario_id: str
    nombre_completo: str
    email: str
    phone_e164_masked: str | None = None
    role: str
    activo: bool
    created_at: datetime
    last_login_at: datetime | None = None


class SuperadminCompanyModuleItem(BaseModel):
    module_name: str
    is_enabled: bool
    notes: str | None = None


class SuperadminInventoryCounts(BaseModel):
    almacenes: int
    materiales: int
    existencias: int
    movimientos: int


class SuperadminCompanyDetailResponse(BaseModel):
    id: str
    nombre: str
    slug: str
    razon_social: str | None = None
    rfc: str | None = None
    giro: str | None = None
    telefono: str | None = None
    email_contacto: str | None = None
    pais: str | None = None
    estado: str | None = None
    ciudad: str | None = None
    direccion: str | None = None
    plan_code: str
    access_status: str
    trial_ends_at: datetime
    created_at: datetime
    is_trial: bool = False
    estado_pago: str | None = None
    limits: CompanyLimitsSummary
    users: list[SuperadminCompanyUserItem]
    modules: list[SuperadminCompanyModuleItem]
    inventory_counts: SuperadminInventoryCounts
    recent_audit_logs: list[SuperadminAuditLogItem]


class SuperadminUserCompanyItem(BaseModel):
    empresa_id: str
    empresa_nombre: str
    role: str
    is_active: bool = True
    plan_code: str
    access_status: str


class SuperadminUserListItem(BaseModel):
    id: str
    nombre_completo: str
    email: str
    phone_e164_masked: str | None = None
    created_at: datetime
    last_login_at: datetime | None = None
    activo: bool
    empresas: list[SuperadminUserCompanyItem]


class SuperadminUserListResponse(BaseModel):
    total: int
    items: list[SuperadminUserListItem]


class SuperadminUserDetailResponse(BaseModel):
    id: str
    nombre_completo: str
    email: str
    phone_e164_masked: str | None = None
    created_at: datetime
    last_login_at: datetime | None = None
    activo: bool
    is_superadmin: bool
    empresas: list[SuperadminUserCompanyItem]
    recent_audit_logs: list[SuperadminAuditLogItem]


class UpdateCompanyAccessRequest(BaseModel):
    plan_code: str
    access_status: str
    trial_ends_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=500)


class ImpersonateRequest(BaseModel):
    empresa_id: str = Field(min_length=1, max_length=64)
    usuario_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=3, max_length=500)


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime
    empresa_id: str
    empresa_nombre: str
    usuario_id: str
    usuario_nombre: str


class SuperadminAuditLogListResponse(BaseModel):
    total: int
    items: list[SuperadminAuditLogItem]
