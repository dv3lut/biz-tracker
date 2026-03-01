"""Normalization helpers for NAF codes."""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

_NAF_PATTERN = re.compile(r"^\d{2}\.\d{2}[A-Z0-9]$")


def normalize_naf_code(value: str | None) -> str | None:
    """Return the canonical representation for a NAF code (e.g. 56.10A)."""

    if not value:
        return None
    token = value.strip().upper().replace(" ", "")
    if not token:
        return None
    if "." not in token:
        digits = token.replace(".", "")
        if len(digits) == 5 and digits[:4].isdigit():
            token = f"{digits[:2]}.{digits[2:]}"
    if not _NAF_PATTERN.match(token):
        return None
    return token


def ensure_valid_naf_code(value: str) -> str:
    """Validate and normalize a code, raising ValueError when invalid."""

    normalized = normalize_naf_code(value)
    if not normalized:
        raise ValueError("Code NAF invalide. Le format attendu est 00.00X.")
    return normalized


def euros_to_cents(amount: float | Decimal | int) -> int:
    """Convert a decimal euro amount into integer cents (>= 0)."""

    quantized = (Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if quantized < 0:
        raise ValueError("Le prix doit être positif.")
    cents = int((quantized * 100).to_integral_value(rounding=ROUND_HALF_UP))
    return cents


def cents_to_euros(amount: int | float | Decimal) -> float:
    """Return a float in euros from integer cents."""

    cents = Decimal(str(amount))
    return float((cents / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
