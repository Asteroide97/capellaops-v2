import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import get_settings


RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
logger = logging.getLogger("uvicorn.error")


class RecaptchaValidationError(Exception):
    pass


class RecaptchaConfigurationError(Exception):
    pass


class RecaptchaServiceError(Exception):
    pass


def verify_recaptcha_token(
    token: str | None,
    *,
    remote_ip: str | None = None,
    expected_action: str = "register_start",
) -> dict:
    settings = get_settings()
    token_present = isinstance(token, str) and len(token.strip()) > 0
    score = None
    action = None

    logger.info(
        "recaptcha_validation recaptcha_enabled=%s token_present=%s validation_success=%s score=%s action=%s",
        settings.recaptcha_enabled,
        token_present,
        False,
        score,
        action,
    )

    if not settings.recaptcha_enabled:
        logger.info(
            "recaptcha_validation recaptcha_enabled=%s token_present=%s validation_success=%s score=%s action=%s",
            settings.recaptcha_enabled,
            token_present,
            True,
            score,
            action,
        )
        return {"success": True, "disabled": True}

    if not settings.recaptcha_secret_key:
        raise RecaptchaConfigurationError("reCAPTCHA no esta configurado en el backend.")

    if not token_present:
        raise RecaptchaValidationError("reCAPTCHA token ausente")

    payload = {
        "secret": settings.recaptcha_secret_key,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    request = Request(
        RECAPTCHA_VERIFY_URL,
        data=urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RecaptchaServiceError("No se pudo validar reCAPTCHA en este momento.") from exc
    except URLError as exc:
        raise RecaptchaServiceError("No se pudo conectar con el servicio de reCAPTCHA.") from exc

    score = result.get("score")
    action = result.get("action")

    if not result.get("success"):
        logger.info(
            "recaptcha_validation recaptcha_enabled=%s token_present=%s validation_success=%s score=%s action=%s",
            settings.recaptcha_enabled,
            token_present,
            False,
            score,
            action,
        )
        raise RecaptchaValidationError("reCAPTCHA invalido")

    if action and action != expected_action:
        logger.info(
            "recaptcha_validation recaptcha_enabled=%s token_present=%s validation_success=%s score=%s action=%s",
            settings.recaptcha_enabled,
            token_present,
            False,
            score,
            action,
        )
        raise RecaptchaValidationError("reCAPTCHA action invalida")

    if score is not None and score < settings.recaptcha_min_score:
        logger.info(
            "recaptcha_validation recaptcha_enabled=%s token_present=%s validation_success=%s score=%s action=%s",
            settings.recaptcha_enabled,
            token_present,
            False,
            score,
            action,
        )
        raise RecaptchaValidationError("reCAPTCHA score bajo")

    logger.info(
        "recaptcha_validation recaptcha_enabled=%s token_present=%s validation_success=%s score=%s action=%s",
        settings.recaptcha_enabled,
        token_present,
        True,
        score,
        action,
    )

    return result
