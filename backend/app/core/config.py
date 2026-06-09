from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus
from urllib.parse import unquote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "Capella Ops V2 API"
    secret_key: str = "change-this-secret-key"
    access_token_expire_minutes: int = 1440
    cors_origins_raw: str = Field(default="", alias="CORS_ORIGINS")
    public_frontend_url: str = Field(default="", alias="PUBLIC_FRONTEND_URL")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    azure_sql_server: str | None = Field(default=None, alias="AZURE_SQL_SERVER")
    azure_sql_database: str | None = Field(default=None, alias="AZURE_SQL_DATABASE")
    azure_sql_username: str | None = Field(default=None, alias="AZURE_SQL_USERNAME")
    azure_sql_password: str | None = Field(default=None, alias="AZURE_SQL_PASSWORD")
    azure_sql_driver: str = Field(default="ODBC Driver 18 for SQL Server", alias="AZURE_SQL_DRIVER")
    azure_storage_connection_string: str | None = Field(default=None, alias="AZURE_STORAGE_CONNECTION_STRING")
    azure_storage_container: str | None = Field(default=None, alias="AZURE_STORAGE_CONTAINER")
    azure_storage_public_base_url: str | None = Field(default=None, alias="AZURE_STORAGE_PUBLIC_BASE_URL")
    sendgrid_api_key: str | None = Field(default=None, alias="SENDGRID_API_KEY")
    email_from: str | None = Field(default=None, alias="EMAIL_FROM")
    twilio_account_sid: str | None = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str | None = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_sms_from: str | None = Field(default=None, alias="TWILIO_SMS_FROM")
    twilio_verify_service_sid: str | None = Field(default=None, alias="TWILIO_VERIFY_SERVICE_SID")
    twilio_verify_channel: str = Field(default="sms", alias="TWILIO_VERIFY_CHANNEL")
    verify_dev_mode: bool = Field(default=False, alias="VERIFY_DEV_MODE")
    verify_dev_code: str = Field(default="123456", alias="VERIFY_DEV_CODE")
    recaptcha_secret_key: str | None = Field(default=None, alias="RECAPTCHA_SECRET_KEY")
    recaptcha_min_score: float = Field(default=0.5, alias="RECAPTCHA_MIN_SCORE")
    recaptcha_enabled: bool = Field(default=True, alias="RECAPTCHA_ENABLED")
    pending_registration_ttl_minutes: int = Field(default=10, alias="PENDING_REGISTRATION_TTL_MINUTES")
    pending_registration_max_attempts: int = Field(default=5, alias="PENDING_REGISTRATION_MAX_ATTEMPTS")
    pending_registration_resend_cooldown_seconds: int = Field(
        default=60,
        alias="PENDING_REGISTRATION_RESEND_COOLDOWN_SECONDS",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def cors_origins(self) -> list[str]:
        origins = [origin.strip().rstrip("/") for origin in self.cors_origins_raw.split(",") if origin.strip()]
        if origins:
            return origins
        if self.public_frontend_origin:
            return [self.public_frontend_origin]
        return []

    @property
    def public_frontend_origin(self) -> str:
        return str(self.public_frontend_url or "").strip().rstrip("/")

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url

        if all(
            [
                self.azure_sql_server,
                self.azure_sql_database,
                self.azure_sql_username,
                self.azure_sql_password,
            ]
        ):
            connection = (
                f"DRIVER={{{self.azure_sql_driver}}};"
                f"SERVER=tcp:{self.azure_sql_server},1433;"
                f"DATABASE={self.azure_sql_database};"
                f"UID={self.azure_sql_username};"
                f"PWD={self.azure_sql_password};"
                "Encrypt=yes;"
                "TrustServerCertificate=no;"
                "Connection Timeout=30;"
            )
            return f"mssql+pyodbc:///?odbc_connect={quote_plus(connection)}"

        sqlite_path = BACKEND_DIR / "capella_ops_v2.db"
        return f"sqlite:///{sqlite_path.as_posix()}"

    def database_summary(self) -> dict[str, str]:
        url = make_url(self.sqlalchemy_database_url)
        engine = url.get_backend_name()
        driver = url.get_driver_name()
        host = url.host or ""
        database = (url.database or "").lstrip("/")

        odbc_connect = url.query.get("odbc_connect")
        if odbc_connect:
            parts: dict[str, str] = {}
            for segment in unquote_plus(odbc_connect).split(";"):
                if "=" not in segment:
                    continue
                key, value = segment.split("=", 1)
                parts[key.strip().upper()] = value.strip()
            host = parts.get("SERVER", host).replace("tcp:", "")
            if "," in host:
                host = host.split(",", 1)[0]
            database = parts.get("DATABASE", database)

        engine_name = f"{engine}+{driver}" if driver else engine
        return {
            "engine": engine_name,
            "host": host,
            "database": database,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
