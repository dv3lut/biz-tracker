from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from app.services.stripe import stripe_upgrade_tokens


def _settings():
    return SimpleNamespace(stripe=SimpleNamespace(secret_key="sk_test_123", upgrade_url="https://app.example.com/upgrade"))


def test_build_upgrade_token_returns_value():
    settings = _settings()
    token = stripe_upgrade_tokens.build_upgrade_token(
        settings,
        customer_id="cus_123",
        subscription_id="sub_123",
        email="ops@example.com",
    )
    assert token
    assert "." in token


def test_build_upgrade_token_returns_none_without_identifiers():
    settings = _settings()
    token = stripe_upgrade_tokens.build_upgrade_token(
        settings,
        customer_id=None,
        subscription_id=None,
        email=None,
    )
    assert token is None


def test_parse_upgrade_token_roundtrip():
    settings = _settings()
    token = stripe_upgrade_tokens.build_upgrade_token(
        settings,
        customer_id="cus_123",
        subscription_id="sub_123",
        email="ops@example.com",
    )
    parsed = stripe_upgrade_tokens.parse_upgrade_token(settings, token)
    assert parsed.customer_id == "cus_123"
    assert parsed.subscription_id == "sub_123"
    assert parsed.email == "ops@example.com"
    assert parsed.issued_at > 0


def test_parse_upgrade_token_rejects_invalid_signature():
    settings = _settings()
    other_settings = SimpleNamespace(
        stripe=SimpleNamespace(secret_key="sk_other", upgrade_url="https://app.example.com/upgrade")
    )
    token = stripe_upgrade_tokens.build_upgrade_token(
        settings,
        customer_id="cus_123",
        subscription_id="sub_123",
        email="ops@example.com",
    )
    with pytest.raises(HTTPException) as exc:
        stripe_upgrade_tokens.parse_upgrade_token(other_settings, token)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_parse_upgrade_token_rejects_invalid():
    settings = _settings()
    with pytest.raises(HTTPException) as exc:
        stripe_upgrade_tokens.parse_upgrade_token(settings, "invalid")
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_parse_upgrade_token_rejects_invalid_payload():
    settings = _settings()
    raw_payload = stripe_upgrade_tokens._to_base64(b"not-json")
    signature = stripe_upgrade_tokens._to_base64(
        stripe_upgrade_tokens._sign_payload(settings.stripe.secret_key, b"not-json")
    )
    token = f"{raw_payload}.{signature}"
    with pytest.raises(HTTPException) as exc:
        stripe_upgrade_tokens.parse_upgrade_token(settings, token)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_parse_upgrade_token_rejects_non_dict_payload():
    settings = _settings()
    raw_payload = stripe_upgrade_tokens._to_base64(b"[]")
    signature = stripe_upgrade_tokens._to_base64(
        stripe_upgrade_tokens._sign_payload(settings.stripe.secret_key, b"[]")
    )
    token = f"{raw_payload}.{signature}"
    with pytest.raises(HTTPException) as exc:
        stripe_upgrade_tokens.parse_upgrade_token(settings, token)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_build_upgrade_url_adds_token_and_anchor():
    settings = _settings()
    url = stripe_upgrade_tokens.build_upgrade_url(settings, "token_123456", anchor="portal")
    assert url == "https://app.example.com/upgrade?token=token_123456#portal"


def test_build_upgrade_url_handles_query_string():
    settings = _settings()
    settings.stripe.upgrade_url = "https://app.example.com/upgrade?ref=mail"
    url = stripe_upgrade_tokens.build_upgrade_url(settings, "token_123456")
    assert url == "https://app.example.com/upgrade?ref=mail&token=token_123456"


def test_build_upgrade_url_returns_none_without_base_url():
    settings = _settings()
    settings.stripe.upgrade_url = ""
    assert stripe_upgrade_tokens.build_upgrade_url(settings, "token_123456") is None


def test_build_upgrade_url_returns_none_without_token():
    settings = _settings()
    assert stripe_upgrade_tokens.build_upgrade_url(settings, None) is None


def test_parse_upgrade_token_coerces_blank_email_to_none():
    settings = _settings()
    token = stripe_upgrade_tokens.build_upgrade_token(
        settings,
        customer_id="cus_123",
        subscription_id="sub_123",
        email="   ",
    )
    parsed = stripe_upgrade_tokens.parse_upgrade_token(settings, token)
    assert parsed.email is None


def test_parse_upgrade_token_keeps_none_email():
    settings = _settings()
    token = stripe_upgrade_tokens.build_upgrade_token(
        settings,
        customer_id="cus_123",
        subscription_id="sub_123",
        email=None,
    )
    parsed = stripe_upgrade_tokens.parse_upgrade_token(settings, token)
    assert parsed.email is None
