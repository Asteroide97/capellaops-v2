from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Empresa, EmpresaUsuario, Usuario


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@dataclass
class TenantContext:
    user: Usuario
    empresa: Empresa
    membership: EmpresaUsuario
    token_payload: dict


@dataclass
class SuperadminContext:
    user: Usuario
    token_payload: dict


def get_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        return decode_access_token(token)
    except InvalidTokenError as exc:
        raise credentials_error from exc


def get_current_user(
    token_payload: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> Usuario:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = token_payload.get("sub")
    if not user_id:
        raise credentials_error

    user = db.get(Usuario, user_id)
    if not user or not user.is_active:
        raise credentials_error

    return user


def get_tenant_context(
    x_empresa_id: str | None = Header(default=None),
    token_payload: dict = Depends(get_token_payload),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    empresa_id = x_empresa_id or token_payload.get("empresa_id")
    if not empresa_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere empresa_id en el token o en X-Empresa-Id.",
        )

    membership = db.scalar(
        select(EmpresaUsuario).where(
            EmpresaUsuario.empresa_id == empresa_id,
            EmpresaUsuario.usuario_id == current_user.id,
            EmpresaUsuario.is_active == True,
        )
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no pertenece a la empresa solicitada o su acceso esta desactivado.",
        )

    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada.",
        )

    return TenantContext(
        user=current_user,
        empresa=empresa,
        membership=membership,
        token_payload=token_payload,
    )


def get_superadmin_context(
    current_user: Usuario = Depends(get_current_user),
    token_payload: dict = Depends(get_token_payload),
) -> SuperadminContext:
    if token_payload.get("impersonation"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes acceder a Superadmin mientras estas impersonando.",
        )

    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder al portal Superadmin.",
        )

    return SuperadminContext(user=current_user, token_payload=token_payload)
