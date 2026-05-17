import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import get_settings


TWILIO_VERIFY_BASE_URL = "https://verify.twilio.com/v2/Services"


class TwilioVerifyConfigurationError(Exception):
    pass


class TwilioVerifyInvalidCodeError(Exception):
    pass


class TwilioVerifyServiceError(Exception):
    pass


def _get_twilio_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.twilio_verify_service_sid:
        raise TwilioVerifyConfigurationError("Twilio Verify SMS no esta configurado en el backend.")

    credentials = f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode("utf-8")
    token = base64.b64encode(credentials).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }


def _get_service_url(resource: str) -> str:
    settings = get_settings()
    if not settings.twilio_verify_service_sid:
        raise TwilioVerifyConfigurationError("Twilio Verify SMS no esta configurado en el backend.")
    return f"{TWILIO_VERIFY_BASE_URL}/{settings.twilio_verify_service_sid}/{resource}"


def _parse_twilio_error(exc: HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8"))
        return body.get("message") or "Twilio Verify devolvio un error."
    except Exception:
        return "Twilio Verify devolvio un error."


def _post_twilio_form(resource: str, payload: dict[str, str]) -> dict:
    request = Request(
        _get_service_url(resource),
        data=urlencode(payload).encode("utf-8"),
        headers=_get_twilio_headers(),
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = _parse_twilio_error(exc)
        if resource == "VerificationCheck" and exc.code in {400, 404}:
            raise TwilioVerifyInvalidCodeError("Codigo incorrecto.") from exc
        raise TwilioVerifyServiceError(message) from exc
    except URLError as exc:
        raise TwilioVerifyServiceError("No se pudo conectar con Twilio Verify.") from exc


def start_phone_verification(phone_e164: str) -> dict:
    settings = get_settings()

    if settings.verify_dev_mode:
        return {
            "status": "pending",
            "to": phone_e164,
            "channel": settings.twilio_verify_channel,
            "dev_mode": True,
        }

    payload = {
        "To": phone_e164,
        "Channel": settings.twilio_verify_channel,
    }
    result = _post_twilio_form("Verifications", payload)
    if result.get("status") != "pending":
        raise TwilioVerifyServiceError("No se pudo enviar el SMS.")
    return result


def check_phone_verification(phone_e164: str, code: str) -> bool:
    settings = get_settings()

    if settings.verify_dev_mode:
        return code == settings.verify_dev_code

    result = _post_twilio_form(
        "VerificationCheck",
        {
            "To": phone_e164,
            "Code": code,
        },
    )
    return result.get("status") == "approved"
