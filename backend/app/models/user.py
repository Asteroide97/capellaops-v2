from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Usuario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        Index(
            "uq_usuarios_phone_e164",
            "phone_e164",
            unique=True,
            sqlite_where=text("phone_e164 IS NOT NULL"),
            mssql_where=text("phone_e164 IS NOT NULL"),
        ),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    memberships = relationship("EmpresaUsuario", back_populates="usuario", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="usuario")


class EmpresaUsuario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "empresa_usuarios"
    __table_args__ = (UniqueConstraint("empresa_id", "usuario_id", name="uq_empresa_usuario"),)

    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="staff")

    empresa = relationship("Empresa", back_populates="users")
    usuario = relationship("Usuario", back_populates="memberships")


class PendingRegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pending_registrations"
    __table_args__ = (
        UniqueConstraint("email", name="uq_pending_registration_email"),
        Index(
            "uq_pending_registrations_phone_e164",
            "phone_e164",
            unique=True,
            sqlite_where=text("phone_e164 IS NOT NULL AND status = 'pending'"),
            mssql_where=text("phone_e164 IS NOT NULL AND status = 'pending'"),
        ),
    )

    empresa_nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_code: Mapped[str] = mapped_column(ForeignKey("planes.code"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
