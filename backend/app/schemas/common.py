from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.module import ModuleItem


class UserSummary(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    is_superadmin: bool
    role: str | None = None


class EmpresaSummary(BaseModel):
    id: str
    name: str
    slug: str
    nombre_comercial: str | None = None
    razon_social: str | None = None
    rfc: str | None = None
    giro: str | None = None
    telefono: str | None = None
    email_contacto: str | None = None
    sitio_web: str | None = None
    pais: str | None = None
    estado: str | None = None
    ciudad: str | None = None
    codigo_postal: str | None = None
    direccion: str | None = None
    logo_url: str | None = None
    plan_code: str
    access_status: str
    trial_ends_at: datetime
    is_trial: bool = False


class MembershipSummary(BaseModel):
    role: str
    is_active: bool = True


class CompanyLimitsSummary(BaseModel):
    max_usuarios: int | None = None
    usuarios_actuales: int = 0
    max_almacenes: int | None = None
    almacenes_actuales: int = 0
    max_facturas_mensuales: int | None = None
    productos_ilimitados: bool = True
    ventas_ilimitadas: bool = True


class MeResponse(BaseModel):
    user: UserSummary
    empresa: EmpresaSummary
    membership: MembershipSummary
    empresas: list[EmpresaSummary]
    limits: CompanyLimitsSummary
    modules: list[ModuleItem] = Field(default_factory=list)
    impersonation: bool = False
    impersonated_by: str | None = None
    impersonation_ends_at: datetime | None = None
