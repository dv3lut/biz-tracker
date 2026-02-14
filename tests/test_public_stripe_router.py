from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routers import public_router as public
from app.api.schemas import (
    PublicStripeCheckoutRequest,
    PublicStripePortalRequest,
    PublicStripePortalSessionRequest,
    PublicStripeSubscriptionInfoRequest,
    PublicStripeUpdatePreviewRequest,
    PublicStripeUpdateRequest,
)


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
    sent = {}
    monkeypatch.setattr(public, "send_portal_access_email", lambda session, settings, email: sent.setdefault("ok", True))

    payload = PublicStripePortalRequest(email="jean@example.com")
    result = public.create_stripe_portal(payload=payload, session=SimpleNamespace())

    assert result.sent is True
    assert sent.get("ok") is True


def test_create_stripe_portal_session_returns_url(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        public,
        "create_portal_session_for_access_token",
        lambda session, settings, access_token: "https://portal.example.com",
    )

    payload = PublicStripePortalSessionRequest(access_token="token_123456")
    result = public.create_stripe_portal_session(payload=payload, session=SimpleNamespace())

    assert result.url == "https://portal.example.com"


def test_update_stripe_subscription_returns_url(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        public,
        "update_subscription",
        lambda session, settings, payload: SimpleNamespace(
            payment_url="https://invoice",
            action="upgrade",
            effective_at=None,
        ),
    )

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[uuid4()],
        access_token="token_123456",
    )

    result = public.update_stripe_subscription(payload=payload, session=SimpleNamespace())
    assert result.payment_url == "https://invoice"
    assert result.action == "upgrade"


def test_preview_stripe_subscription_update_returns_payload(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        public,
        "get_subscription_update_preview",
        lambda session, settings, payload: SimpleNamespace(
            amount_due=1200,
            currency="eur",
            is_upgrade=True,
            is_trial=False,
            has_payment_method=True,
        ),
    )

    payload = PublicStripeUpdatePreviewRequest(
        plan_key="business",
        category_ids=[uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    result = public.preview_stripe_subscription_update(payload=payload, session=SimpleNamespace())
    assert result.amount_due == 1200
    assert result.currency == "eur"
    assert result.is_upgrade is True
    assert result.is_trial is False
    assert result.has_payment_method is True


def test_get_stripe_subscription_info_returns_payload(monkeypatch):
    monkeypatch.setattr(public, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        public,
        "get_subscription_info",
        lambda session, settings, access_token: SimpleNamespace(
            plan_key="starter",
            status="active",
            current_period_end=None,
            cancel_at=None,
            contact_name="Jean Dupont",
            contact_email="jean@example.com",
            categories=[{"id": uuid4(), "name": "Restauration"}],
            departments=[{"id": uuid4(), "code": "13", "name": "Bouches-du-Rhône"}],
            all_departments=False,
        ),
    )

    payload = PublicStripeSubscriptionInfoRequest(access_token="token_123456")
    result = public.get_stripe_subscription_info(payload=payload, session=SimpleNamespace())

    assert result.plan_key == "starter"
    assert result.status == "active"
    assert result.contact_name == "Jean Dupont"
    assert result.contact_email == "jean@example.com"
    assert result.categories
    assert result.departments
    assert result.all_departments is False


def test_get_public_stripe_settings_returns_trial_days(monkeypatch):
    monkeypatch.setattr(public, "get_billing_settings", lambda session: SimpleNamespace(trial_period_days=14))

    result = public.get_public_stripe_settings(session=SimpleNamespace())

    assert result.trial_period_days == 14


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
