from datetime import datetime, timedelta, timezone
import hashlib
import secrets

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings


password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def generate_secret_token() -> str:
    return secrets.token_urlsafe(32)


def hash_secret_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_token_expiration(expires_minutes: int | None = None) -> datetime:
    settings = get_settings()
    ttl_minutes = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    return datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)


def create_access_token(
    subject: str,
    empresa_id: str,
    extra_claims: dict | None = None,
    expires_minutes: int | None = None,
) -> str:
    settings = get_settings()
    payload = {
        "sub": subject,
        "empresa_id": empresa_id,
        "exp": build_token_expiration(expires_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
