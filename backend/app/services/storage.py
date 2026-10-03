from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

try:
    from azure.core.exceptions import AzureError, ResourceNotFoundError
    from azure.storage.blob import BlobServiceClient, ContentSettings
except ModuleNotFoundError:  # pragma: no cover - handled at runtime when dependency is absent
    AzureError = Exception
    ResourceNotFoundError = type("ResourceNotFoundError", (Exception,), {})
    BlobServiceClient = None
    ContentSettings = None


MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
MAX_PM_DOCUMENT_SIZE_BYTES = 15 * 1024 * 1024
MAX_PM_EVIDENCE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
ALLOWED_PM_DOCUMENT_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/plain": ".txt",
}


class StorageConfigurationError(Exception):
    pass


class StorageOperationError(Exception):
    pass


class StorageBlobNotFoundError(StorageOperationError):
    pass


@dataclass
class UploadedMaterialImage:
    imagen_url: str
    filename: str
    content_type: str
    size_bytes: int


@dataclass
class UploadedCompanyLogo:
    logo_url: str
    blob_path: str
    filename: str
    content_type: str
    size_bytes: int


@dataclass
class UploadedProjectDocument:
    archivo_url: str
    filename: str
    content_type: str
    size_bytes: int
    blob_path: str | None = None


def validate_image_content_type(content_type: str | None) -> str:
    normalized = (content_type or "").strip().lower()
    if normalized not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de imagen no permitido. Usa JPG, PNG o WEBP.",
        )
    return normalized


def validate_pm_document_content_type(content_type: str | None) -> str:
    normalized = (content_type or "").strip().lower()
    if normalized not in ALLOWED_PM_DOCUMENT_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de documento no permitido.",
        )
    return normalized


def build_material_blob_path(*, empresa_id: str, extension: str) -> str:
    current = datetime.now(timezone.utc)
    return f"{empresa_id}/materials/{current:%Y/%m}/{uuid4().hex}{extension}"


def build_company_logo_blob_path(*, empresa_id: str, extension: str) -> str:
    current = datetime.now(timezone.utc)
    return f"{empresa_id}/company/logo/{current:%Y/%m}/{uuid4().hex}{extension}"


def build_pm_document_blob_path(*, empresa_id: str, project_id: str, extension: str) -> str:
    current = datetime.now(timezone.utc)
    return f"{empresa_id}/pm/projects/{project_id}/documents/{current:%Y/%m}/{uuid4().hex}{extension}"


def build_pm_import_source_blob_path(*, empresa_id: str, project_id: str, session_id: str) -> str:
    return f"{empresa_id}/pm/projects/{project_id}/budget-imports/{session_id}/source.xlsx"


def build_public_url(*, blob_path: str, default_url: str) -> str:
    settings = get_settings()
    custom_base = (settings.azure_storage_public_base_url or "").strip().rstrip("/")
    if custom_base:
        return f"{custom_base}/{blob_path}"
    return default_url


async def validate_image_file(file: UploadFile) -> tuple[bytes, str]:
    content_type = validate_image_content_type(file.content_type)
    data = await file.read(MAX_IMAGE_SIZE_BYTES + 1)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes seleccionar una imagen.",
        )
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen excede el tamaño máximo de 5 MB.",
        )
    return data, content_type


async def validate_pm_document_file(file: UploadFile) -> tuple[bytes, str]:
    content_type = validate_pm_document_content_type(file.content_type)
    data = await file.read(MAX_PM_DOCUMENT_SIZE_BYTES + 1)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes seleccionar un documento.",
        )
    if len(data) > MAX_PM_DOCUMENT_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El documento excede el tamaño máximo de 15 MB.",
        )
    return data, content_type


def get_blob_service_client() -> BlobServiceClient:
    settings = get_settings()
    connection_string = (settings.azure_storage_connection_string or "").strip()

    if not connection_string:
        raise StorageConfigurationError("El almacenamiento de imágenes no está configurado.")

    if BlobServiceClient is None or ContentSettings is None:
        raise StorageConfigurationError("El almacenamiento de imágenes no está configurado.")

    return BlobServiceClient.from_connection_string(connection_string)


def _blob_container_name(*, private: bool) -> str:
    settings = get_settings()
    container = (settings.azure_storage_private_container if private else settings.azure_storage_container) or ""
    if not container.strip():
        if private:
            raise StorageConfigurationError("El almacenamiento privado de documentos no está configurado.")
        raise StorageConfigurationError("El almacenamiento de documentos no está configurado.")
    container = container.strip()
    if private and container.casefold() == (settings.azure_storage_container or "").strip().casefold():
        raise StorageConfigurationError("El contenedor de archivos privados debe ser distinto al contenedor público.")
    return container


def _get_pm_blob_client(*, blob_path: str, private: bool, require_private_access: bool = False):
    service = get_blob_service_client()
    container_name = _blob_container_name(private=private)
    if private or require_private_access:
        properties = service.get_container_client(container_name).get_container_properties()
        if getattr(properties, "public_access", None):
            raise StorageConfigurationError("El contenedor de documentos tiene acceso público habilitado.")
    return service.get_blob_client(container=container_name, blob=blob_path)


def upload_private_pm_import_file(*, empresa_id: str, project_id: str, session_id: str, data: bytes, filename: str, content_type: str) -> str:
    blob_path = build_pm_import_source_blob_path(empresa_id=empresa_id, project_id=project_id, session_id=session_id)
    safe_filename = Path(filename).name.replace('"', "")[:255] or "presupuesto.xlsx"
    try:
        blob_client = _get_pm_blob_client(blob_path=blob_path, private=True)
        blob_client.upload_blob(
            data,
            overwrite=False,
            content_settings=ContentSettings(
                content_type=content_type,
                content_disposition=f'attachment; filename="{safe_filename}"',
            ),
        )
        return blob_path
    except StorageConfigurationError:
        raise
    except AzureError as exc:
        raise StorageOperationError("No se pudo guardar el archivo de origen.") from exc


def read_pm_blob(*, blob_path: str, private: bool = False, require_private_access: bool = False) -> bytes:
    try:
        blob_client = _get_pm_blob_client(
            blob_path=blob_path, private=private, require_private_access=require_private_access,
        )
        return blob_client.download_blob().readall()
    except StorageConfigurationError:
        raise
    except ResourceNotFoundError as exc:
        raise StorageBlobNotFoundError("El archivo solicitado no existe.") from exc
    except AzureError as exc:
        raise StorageOperationError("No se pudo recuperar el documento.") from exc


def delete_pm_blob(*, blob_path: str, private: bool = False) -> tuple[bool, bytes | None]:
    try:
        blob_client = _get_pm_blob_client(blob_path=blob_path, private=private)
        if not blob_client.exists():
            return False, None
        backup = blob_client.download_blob().readall()
        blob_client.delete_blob(delete_snapshots="include")
        return True, backup
    except StorageConfigurationError:
        raise
    except AzureError as exc:
        raise StorageOperationError("No se pudo eliminar el archivo almacenado.") from exc


def restore_pm_blob(*, blob_path: str, data: bytes, private: bool = False, content_type: str = "application/octet-stream") -> None:
    try:
        blob_client = _get_pm_blob_client(blob_path=blob_path, private=private)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
    except (StorageConfigurationError, AzureError) as exc:
        raise StorageOperationError("No se pudo restaurar el documento almacenado.") from exc


async def upload_material_image(file: UploadFile, empresa_id: str) -> UploadedMaterialImage:
    settings = get_settings()
    container = (settings.azure_storage_container or "").strip()
    if not container:
        raise StorageConfigurationError("El almacenamiento de imágenes no está configurado.")

    data, content_type = await validate_image_file(file)
    extension = ALLOWED_IMAGE_CONTENT_TYPES[content_type]
    blob_path = build_material_blob_path(empresa_id=empresa_id, extension=extension)
    filename = Path(blob_path).name

    try:
        blob_service = get_blob_service_client()
        blob_client = blob_service.get_blob_client(container=container, blob=blob_path)
        blob_client.upload_blob(
            data,
            overwrite=False,
            content_settings=ContentSettings(content_type=content_type),
        )
    except StorageConfigurationError:
        raise
    except AzureError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo almacenar la imagen del material.",
        ) from exc

    return UploadedMaterialImage(
        imagen_url=build_public_url(blob_path=blob_path, default_url=blob_client.url),
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
    )


async def upload_company_logo(file: UploadFile, empresa_id: str) -> UploadedCompanyLogo:
    settings = get_settings()
    container = (settings.azure_storage_container or "").strip()
    if not container:
        raise StorageConfigurationError("El almacenamiento de imagenes no esta configurado.")

    data, content_type = await validate_image_file(file)
    extension = ALLOWED_IMAGE_CONTENT_TYPES[content_type]
    blob_path = build_company_logo_blob_path(empresa_id=empresa_id, extension=extension)
    filename = Path(blob_path).name

    try:
        blob_service = get_blob_service_client()
        blob_client = blob_service.get_blob_client(container=container, blob=blob_path)
        blob_client.upload_blob(
            data,
            overwrite=False,
            content_settings=ContentSettings(content_type=content_type),
        )
    except StorageConfigurationError:
        raise
    except AzureError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo almacenar el logo de la empresa.",
        ) from exc

    return UploadedCompanyLogo(
        logo_url=build_public_url(blob_path=blob_path, default_url=blob_client.url),
        blob_path=blob_path,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
    )


async def upload_pm_document(file: UploadFile, empresa_id: str, project_id: str) -> UploadedProjectDocument:
    settings = get_settings()
    container = (settings.azure_storage_container or "").strip()
    if not container:
        raise StorageConfigurationError("El almacenamiento de documentos no está configurado.")

    data, content_type = await validate_pm_document_file(file)
    extension = ALLOWED_PM_DOCUMENT_CONTENT_TYPES[content_type]
    blob_path = build_pm_document_blob_path(empresa_id=empresa_id, project_id=project_id, extension=extension)
    filename = Path(blob_path).name

    try:
        blob_service = get_blob_service_client()
        blob_client = blob_service.get_blob_client(container=container, blob=blob_path)
        blob_client.upload_blob(
            data,
            overwrite=False,
            content_settings=ContentSettings(content_type=content_type),
        )
    except StorageConfigurationError as exc:
        raise StorageConfigurationError("El almacenamiento de documentos no está configurado.") from exc
    except AzureError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo almacenar el documento del proyecto.",
        ) from exc

    return UploadedProjectDocument(
        archivo_url=build_public_url(blob_path=blob_path, default_url=blob_client.url),
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        blob_path=blob_path,
    )


async def upload_pm_evidence_image(file: UploadFile, empresa_id: str, project_id: str) -> UploadedProjectDocument:
    content_type = (file.content_type or "").strip().lower()
    extensions = {"image/jpeg": ".jpg", "image/png": ".png"}
    if content_type not in extensions:
        raise HTTPException(status_code=400, detail="Solo se aceptan fotografías JPG o PNG.")
    data = await file.read(MAX_PM_EVIDENCE_SIZE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Selecciona una fotografía.")
    if len(data) > MAX_PM_EVIDENCE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="La fotografía no puede superar 5 MB.")
    is_jpeg = data.startswith(b"\xff\xd8\xff")
    is_png = data.startswith(b"\x89PNG\r\n\x1a\n")
    if not ((content_type == "image/jpeg" and is_jpeg) or (content_type == "image/png" and is_png)):
        raise HTTPException(status_code=400, detail="El contenido del archivo no coincide con una imagen JPG o PNG válida.")
    settings = get_settings()
    container = (settings.azure_storage_container or "").strip()
    if not container:
        raise StorageConfigurationError("El almacenamiento de documentos no está configurado.")
    blob_path = build_pm_document_blob_path(empresa_id=empresa_id, project_id=project_id, extension=extensions[content_type])
    filename = Path(blob_path).name
    try:
        blob_service = get_blob_service_client()
        blob_client = blob_service.get_blob_client(container=container, blob=blob_path)
        blob_client.upload_blob(data, overwrite=False, content_settings=ContentSettings(content_type=content_type))
    except StorageConfigurationError:
        raise
    except AzureError as exc:
        raise HTTPException(status_code=500, detail="No se pudo almacenar la fotografía.") from exc
    return UploadedProjectDocument(
        archivo_url=build_public_url(blob_path=blob_path, default_url=blob_client.url),
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        blob_path=blob_path,
    )
