from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import CompanyLimitsSummary


class CompanyUserItem(BaseModel):
    id: str
    kind: str
    usuario_id: str | None = None
    email: EmailStr
    full_name: str | None = None
    role: str
    status: str
    is_active: bool
    last_login_at: datetime | None = None
    invited_by_user_id: str | None = None
    created_at: datetime


class CompanyUsersListResponse(BaseModel):
    empresa_id: str
    empresa_nombre: str
    plan_code: str
    limits: CompanyLimitsSummary
    items: list[CompanyUserItem]


class CompanyUserInviteRequest(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=160)
    role: str = Field(default="user", min_length=4, max_length=40)


class CompanyUserInviteResponse(BaseModel):
    status: str
    message: str
    item: CompanyUserItem
    limits: CompanyLimitsSummary


class CompanyUserUpdateRequest(BaseModel):
    role: str | None = Field(default=None, min_length=4, max_length=40)
    is_active: bool | None = None


class CompanyUserDeactivateResponse(BaseModel):
    ok: bool
    message: str
    item: CompanyUserItem
    limits: CompanyLimitsSummary


class CompanyProfileResponse(BaseModel):
    id: str
    name: str
    slug: str
    nombre_comercial: str | None = None
    razon_social: str | None = None
    rfc: str | None = None
    email_contacto: str | None = None
    telefono: str | None = None
    sitio_web: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    estado: str | None = None
    pais: str | None = None
    codigo_postal: str | None = None
    logo_url: str | None = None


class CompanyProfileUpdateRequest(BaseModel):
    nombre_comercial: str | None = Field(default=None, max_length=180)
    razon_social: str | None = Field(default=None, max_length=180)
    rfc: str | None = Field(default=None, max_length=32)
    email_contacto: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=40)
    sitio_web: str | None = Field(default=None, max_length=255)
    direccion: str | None = Field(default=None, max_length=1000)
    ciudad: str | None = Field(default=None, max_length=80)
    estado: str | None = Field(default=None, max_length=80)
    pais: str | None = Field(default=None, max_length=80)
    codigo_postal: str | None = Field(default=None, max_length=20)


class CompanyLogoUploadResponse(BaseModel):
    logo_url: str
    filename: str
    content_type: str
    size_bytes: int


class CompanyLogoDeleteResponse(BaseModel):
    ok: bool
    message: str
    logo_url: str | None = None
