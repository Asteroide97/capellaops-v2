import re


class PhoneValidationError(Exception):
    pass


E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def _clean_country_code(country_code: str) -> str:
    value = country_code.strip().replace(" ", "")
    if not value.startswith("+"):
        raise PhoneValidationError("Numero de telefono invalido.")

    digits = re.sub(r"\D", "", value)
    if not digits:
        raise PhoneValidationError("Numero de telefono invalido.")

    return f"+{digits}"


def _clean_phone_number(phone_number: str) -> str:
    digits = re.sub(r"\D", "", phone_number or "")
    if not digits:
        raise PhoneValidationError("Numero de telefono invalido.")
    return digits


def validate_phone_e164(phone_e164: str) -> bool:
    return bool(E164_PATTERN.fullmatch(phone_e164))


def normalize_phone(country_code: str, phone_number: str) -> dict[str, str]:
    clean_country_code = _clean_country_code(country_code)
    clean_phone_number = _clean_phone_number(phone_number)
    phone_e164 = f"{clean_country_code}{clean_phone_number}"

    total_digits = len(phone_e164) - 1
    if total_digits < 8 or total_digits > 15 or not validate_phone_e164(phone_e164):
        raise PhoneValidationError("Numero de telefono invalido.")

    return {
        "country_code": clean_country_code,
        "phone_number": clean_phone_number,
        "phone_e164": phone_e164,
    }


def normalize_phone_e164(phone: str) -> dict[str, str]:
    raw_value = (phone or "").strip().replace(" ", "")
    if not raw_value:
        raise PhoneValidationError("Numero de telefono invalido.")

    digits = re.sub(r"\D", "", raw_value)
    phone_e164 = f"+{digits}"

    total_digits = len(phone_e164) - 1
    if total_digits < 8 or total_digits > 15 or not validate_phone_e164(phone_e164):
        raise PhoneValidationError("Numero de telefono invalido.")

    return {"phone_e164": phone_e164}


def mask_phone(phone_e164: str, country_code: str | None = None) -> str:
    if not phone_e164:
        return ""

    prefix = country_code if country_code else "+"
    local_digits = phone_e164[len(prefix) :] if country_code and phone_e164.startswith(country_code) else phone_e164[1:]
    if len(local_digits) <= 4:
        masked_local = "*" * len(local_digits)
    else:
        masked_local = "*" * (len(local_digits) - 4) + local_digits[-4:]
    return f"{prefix}{masked_local}"
