"""Exact quantities for inventory's four-decimal persistence contract."""
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import AfterValidator


QUANTITY_PRECISION_ERROR = "La cantidad admite como m\u00e1ximo 4 decimales."


def validate_quantity_precision(value: Decimal) -> Decimal:
    if isinstance(value, float):
        raise ValueError("Ingresa una cantidad decimal v\u00e1lida.")
    try:
        quantity = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Ingresa una cantidad decimal v\u00e1lida.") from exc
    if not quantity.is_finite():
        raise ValueError("Ingresa una cantidad decimal finita.")
    _, digits, exponent = quantity.as_tuple()
    # Ignore insignificant trailing zeros without rounding or allocating a huge quantized value.
    if exponent < -4 and any(digits[max(0, len(digits) + exponent + 4):]):
        raise ValueError(QUANTITY_PRECISION_ERROR)
    return quantity


Quantity4 = Annotated[Decimal, AfterValidator(validate_quantity_precision)]
