from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routers import public_router as public
from app.api.schemas import PublicStripeCheckoutRequest, PublicStripePortalRequest, PublicStripeUpdateRequest


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_list_public_naf_categories_returns_payload(monkeypatch):
    expected = [SimpleNamespace(id=uuid4(), name="Cat", description=None, active_subcategory_count=2)]
    monkeypatch.setattr(public, "list_public_categories", lambda session: expected)

    result = public.list_public_naf_categories(session=SimpleNamespace())

    assert result == expected


def test_create_stripe_checkout_returns_url(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(public, "create_checkout_session", lambda session, settings, payload: "https://checkout")

    payload = PublicStripeCheckoutRequest(
        plan_key="starter",
        category_ids=[uuid4()],
        contact_name="Jean",
        company_name="ACME",
        email="jean@example.com",
    )

    result = public.create_stripe_checkout(payload=payload, session=SimpleNamespace())

    assert result.url == "https://checkout"


def test_create_stripe_portal_returns_url(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(public, "create_portal_session", lambda session, settings, email: "https://portal")

    payload = PublicStripePortalRequest(email="jean@example.com")
    result = public.create_stripe_portal(payload=payload, session=SimpleNamespace())

    assert result.url == "https://portal"


def test_update_stripe_subscription_returns_url(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(public, "update_subscription", lambda session, settings, payload: "https://invoice")

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[uuid4()],
        email="jean@example.com",
    )

    result = public.update_stripe_subscription(payload=payload, session=SimpleNamespace())
    assert result.payment_url == "https://invoice"


@pytest.mark.anyio
async def test_stripe_webhook_requires_secret(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(stripe=SimpleNamespace(webhook_secret=None)))

    class DummyRequest:
        headers = {}

        async def body(self):
            return b"{}"

    with pytest.raises(HTTPException) as exc:
        await public.stripe_webhook(request=DummyRequest(), session=SimpleNamespace())
    assert exc.value.status_code == 503


@pytest.mark.anyio
async def test_stripe_webhook_requires_signature(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(stripe=SimpleNamespace(webhook_secret="whsec")))

    class DummyRequest:
        headers = {}

        async def body(self):
            return b"{}"

    with pytest.raises(HTTPException) as exc:
        await public.stripe_webhook(request=DummyRequest(), session=SimpleNamespace())
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_stripe_webhook_dispatches(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(stripe=SimpleNamespace(webhook_secret="whsec")))
    called = {}

    class DummyRequest:
        headers = {"stripe-signature": "sig"}

        async def body(self):
            return b"{}"

    monkeypatch.setattr(public.stripe.Webhook, "construct_event", lambda payload, sig, secret: {"type": "checkout.session.completed", "data": {"object": {}}})
    monkeypatch.setattr(public, "handle_stripe_webhook", lambda session, settings, event: called.setdefault("ok", True))

    result = await public.stripe_webhook(request=DummyRequest(), session=SimpleNamespace())

    assert result["received"] is True
    assert called.get("ok") is True


@pytest.mark.anyio
async def test_stripe_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace(stripe=SimpleNamespace(webhook_secret="whsec")))

    class DummyRequest:
        headers = {"stripe-signature": "sig"}

        async def body(self):
            return b"{}"

    def _raise_signature(*_args, **_kwargs):
        raise public.stripe.error.SignatureVerificationError("bad", "sig")

    monkeypatch.setattr(public.stripe.Webhook, "construct_event", _raise_signature)

    with pytest.raises(HTTPException) as exc:
        await public.stripe_webhook(request=DummyRequest(), session=SimpleNamespace())
    assert exc.value.status_code == 400
