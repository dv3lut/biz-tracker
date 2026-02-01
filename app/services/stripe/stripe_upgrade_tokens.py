"""Signed tokens for upgrade links."""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException, status

from app.config import Settings
from app.services.stripe.stripe_common import ensure_stripe_configured


@dataclass(frozen=True)
class UpgradeAccessToken:
    customer_id: str | None
    subscription_id: str | None
    email: str | None
    issued_at: int


def build_upgrade_token(
    settings: Settings,
    *,
    customer_id: str | None,
    subscription_id: str | None,
    email: str | None,
) -> str | None:
    if not (customer_id or subscription_id or email):
        return None
    stripe_config = ensure_stripe_configured(settings)
    payload = {
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "email": email,
        "issued_at": int(time.time()),
    }
    data = _encode_payload(payload)
    signature = _sign_payload(stripe_config.secret_key or "", data)
    return f"{_to_base64(data)}.{_to_base64(signature)}"


def parse_upgrade_token(settings: Settings, token: str) -> UpgradeAccessToken:
    if not token or "." not in token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Lien sécurisé invalide.")
    stripe_config = ensure_stripe_configured(settings)
    encoded_payload, encoded_signature = token.split(".", 1)
    payload_bytes = _from_base64(encoded_payload)
    signature = _from_base64(encoded_signature)
    expected = _sign_payload(stripe_config.secret_key or "", payload_bytes)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Lien sécurisé invalide.")

    payload = _decode_payload(payload_bytes)
    return UpgradeAccessToken(
        customer_id=_coerce_str(payload.get("customer_id")),
        subscription_id=_coerce_str(payload.get("subscription_id")),
        email=_coerce_str(payload.get("email")),
        issued_at=int(payload.get("issued_at") or 0),
    )


def build_upgrade_url(settings: Settings, access_token: str | None, *, anchor: str | None = None) -> str | None:
    base_url = (settings.stripe.upgrade_url or "").strip()
    if not base_url or not access_token:
        return None
    separator = "&" if "?" in base_url else "?"
    url = f"{base_url}{separator}token={quote(access_token)}"
    if anchor:
        return f"{url}#{anchor}"
    return url


def _encode_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _decode_payload(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Lien sécurisé invalide.") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Lien sécurisé invalide.")
    return data


def _sign_payload(secret: str, payload: bytes) -> bytes:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()


def _to_base64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _from_base64(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
