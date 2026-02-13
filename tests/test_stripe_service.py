from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.api.schemas import PublicStripeCheckoutRequest, PublicStripeUpdateRequest
from app.db import models
from app.services.stripe import (
    stripe_admin_notifications,
    stripe_checkout_service,
    stripe_portal_service,
    stripe_subscription_utils,
    stripe_webhook_service,
)
from app.services.stripe.stripe_common import ensure_stripe_configured, find_client_by_email


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


def _settings():
    return SimpleNamespace(
        stripe=SimpleNamespace(
            secret_key="sk_test_123",
            price_ids={"starter": "price_starter", "business": "price_business"},
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            portal_return_url="https://example.com/upgrade",
            upgrade_url="https://example.com/upgrade",
        )
    )


def test_normalize_category_ids_deduplicates():
    identifier = uuid4()
    other = uuid4()
    assert stripe_checkout_service._normalize_category_ids([identifier, identifier, other]) == [identifier, other]


def test_create_checkout_session_includes_referrer(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    captured = {}

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "get_trial_period_days", lambda session: 7)

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

    def _create_session(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout")

    monkeypatch.setattr(stripe_checkout_service.stripe.checkout.Session, "create", _create_session)

    payload = PublicStripeCheckoutRequest(
        plan_key="starter",
        category_ids=[category_id],
        contact_name="Jean",
        company_name="ACME",
        email="jean@example.com",
        referrer_name="Alice",
    )

    url = stripe_checkout_service.create_checkout_session(DummySession(), settings, payload)
    assert url == "https://checkout"
    assert captured.get("metadata", {}).get("referrer_name") == "Alice"


def test_validate_category_selection_rejects_wrong_count():
    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service._validate_category_selection([], 1)
    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_send_subscription_update_email_downgrade_mentions_auto_switch(monkeypatch):
    sent = {}

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["recipients"] = recipients

    monkeypatch.setattr(stripe_checkout_service, "EmailService", lambda: DummyEmail())

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    stripe_checkout_service._send_subscription_update_email(
        settings=_settings(),
        email="client@example.com",
        action="downgrade",
        effective_at=datetime(2026, 1, 31),
        payment_url=None,
        access_token="token_123",
    )

    assert "automatiquement" in (sent.get("body") or "")


def test_resolve_plan_config_requires_price_id():
    settings = SimpleNamespace(price_ids={"starter": "price_starter"})
    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service._resolve_plan_config(settings, "business")
    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_ensure_stripe_http_client_sets_default(monkeypatch):
    monkeypatch.setattr(
        stripe_checkout_service.stripe,
        "new_default_http_client",
        lambda timeout: SimpleNamespace(_timeout=timeout),
    )
    monkeypatch.setattr(stripe_checkout_service.stripe, "default_http_client", None)

    stripe_checkout_service._ensure_stripe_http_client()

    assert stripe_checkout_service.stripe.default_http_client is not None


def test_resolve_plan_config_requires_price_id():
    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service._resolve_plan_config(SimpleNamespace(price_ids={}), "starter")
    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_ensure_stripe_configured_requires_secret():
    settings = SimpleNamespace(stripe=SimpleNamespace(secret_key=None))
    with pytest.raises(HTTPException) as exc:
        ensure_stripe_configured(settings)
    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_list_public_categories_returns_rows():
    category = SimpleNamespace(id=uuid4(), name="Restauration", description="Desc")
    session = SimpleNamespace(execute=lambda stmt: _FakeResult([(category, 3)]))

    result = stripe_checkout_service.list_public_categories(session)

    assert len(result) == 1
    assert result[0].name == "Restauration"
    assert result[0].active_subcategory_count == 3


def test_create_checkout_session_returns_url(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    captured = {}

    def dummy_validate_categories(session, ids):
        assert ids == [category_id]

    class DummyStripeSession:
        url = "https://checkout.example.com"

    class DummyCheckout:
        @staticmethod
        def create(**_kwargs):
            captured.update(_kwargs)
            return DummyStripeSession()

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", dummy_validate_categories)
    monkeypatch.setattr(stripe_checkout_service, "get_trial_period_days", lambda session: 14)
    monkeypatch.setattr(stripe_checkout_service.stripe, "checkout", SimpleNamespace(Session=DummyCheckout))

    payload = PublicStripeCheckoutRequest(
        plan_key="starter",
        category_ids=[category_id],
        contact_name="Jean",
        company_name="ACME",
        email="jean@example.com",
    )

    url = stripe_checkout_service.create_checkout_session(SimpleNamespace(), settings, payload)
    assert url == "https://checkout.example.com"
    assert captured.get("locale") == "fr"


def test_create_checkout_session_raises_when_missing_url(monkeypatch):
    settings = _settings()
    category_id = uuid4()

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "get_trial_period_days", lambda session: 14)

    class DummyStripeSession:
        url = None

    class DummyCheckout:
        @staticmethod
        def create(**_kwargs):
            return DummyStripeSession()

    monkeypatch.setattr(stripe_checkout_service.stripe, "checkout", SimpleNamespace(Session=DummyCheckout))

    payload = PublicStripeCheckoutRequest(
        plan_key="starter",
        category_ids=[category_id],
        contact_name="Jean",
        company_name="ACME",
        email="jean@example.com",
    )

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service.create_checkout_session(SimpleNamespace(), settings, payload)
    assert exc.value.status_code == status.HTTP_502_BAD_GATEWAY


def test_create_portal_session_returns_url(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(stripe_customer_id="cus_123")
    monkeypatch.setattr(stripe_portal_service, "find_client_by_email", lambda session, email: client)
    captured = {}

    class DummyPortalSession:
        url = "https://portal.example.com"

    class DummyPortal:
        @staticmethod
        def create(**_kwargs):
            captured.update(_kwargs)
            return DummyPortalSession()

    monkeypatch.setattr(stripe_portal_service.stripe, "billing_portal", SimpleNamespace(Session=DummyPortal))

    url = stripe_portal_service.create_portal_session(SimpleNamespace(), settings, "ops@example.com")

    assert url == "https://portal.example.com"
    assert captured.get("locale") == "fr"


def test_create_portal_session_for_access_token_returns_url(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(stripe_customer_id="cus_123")
    monkeypatch.setattr(stripe_portal_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_portal_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="ops@example.com",
        ),
    )
    captured = {}

    class DummyPortalSession:
        url = "https://portal.example.com"

    class DummyPortal:
        @staticmethod
        def create(**_kwargs):
            captured.update(_kwargs)
            return DummyPortalSession()

    monkeypatch.setattr(stripe_portal_service.stripe, "billing_portal", SimpleNamespace(Session=DummyPortal))

    url = stripe_portal_service.create_portal_session_for_access_token(
        SimpleNamespace(),
        settings,
        "token_123456",
    )

    assert url == "https://portal.example.com"
    assert captured.get("locale") == "fr"


def test_create_portal_session_for_access_token_requires_client(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(stripe_portal_service, "find_client", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        stripe_portal_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="ops@example.com",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        stripe_portal_service.create_portal_session_for_access_token(
            SimpleNamespace(),
            settings,
            "token_123456",
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_create_portal_session_for_access_token_raises_when_missing_url(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(stripe_customer_id="cus_123")
    monkeypatch.setattr(stripe_portal_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_portal_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="ops@example.com",
        ),
    )

    class DummyPortalSession:
        url = None

    class DummyPortal:
        @staticmethod
        def create(**_kwargs):
            return DummyPortalSession()

    monkeypatch.setattr(stripe_portal_service.stripe, "billing_portal", SimpleNamespace(Session=DummyPortal))

    with pytest.raises(HTTPException) as exc:
        stripe_portal_service.create_portal_session_for_access_token(
            SimpleNamespace(),
            settings,
            "token_123456",
        )
    assert exc.value.status_code == status.HTTP_502_BAD_GATEWAY


def test_notify_admins_of_stripe_event_sends_email(monkeypatch):
    settings = _settings()
    sent = {}

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, *, html_body=None, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["html"] = html_body
            sent["recipients"] = recipients

    monkeypatch.setattr(stripe_admin_notifications, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_admin_notifications, "get_admin_emails", lambda session: ["ops@example.com"])
    monkeypatch.setattr(
        stripe_admin_notifications,
        "retrieve_subscription",
        lambda *_args, **_kwargs: {
            "status": "active",
            "items": {"data": [{"price": {"id": "price_starter"}}]},
            "metadata": {"plan_key": "starter", "referrer_name": "Alice Martin"},
        },
    )
    monkeypatch.setattr(
        stripe_admin_notifications,
        "find_client",
        lambda *args, **kwargs: SimpleNamespace(name="ACME", id=uuid4(), recipients=[]),
    )

    payload = {
        "subscription": "sub_123",
        "customer": "cus_123",
        "metadata": {"contact_email": "client@example.com", "referrer_name": "Alice Martin"},
    }

    stripe_admin_notifications.notify_admins_of_stripe_event(
        SimpleNamespace(),
        settings,
        "checkout.session.completed",
        payload,
    )

    assert sent.get("recipients") == ["ops@example.com"]
    assert "Checkout confirmé" in sent.get("subject", "")
    assert "Parrain: Alice Martin" in sent.get("body", "")
    assert "<strong>Alice Martin</strong>" in sent.get("html", "")


def test_notify_admins_of_stripe_event_skips_when_email_disabled(monkeypatch):
    settings = _settings()

    class DummyEmail:
        def is_enabled(self):
            return False

        def is_configured(self):
            return False

        def send(self, subject, body, recipients, *, html_body=None, **_kwargs):
            raise AssertionError("send should not be called")

    monkeypatch.setattr(stripe_admin_notifications, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_admin_notifications, "get_admin_emails", lambda session: ["ops@example.com"])

    stripe_admin_notifications.notify_admins_of_stripe_event(
        SimpleNamespace(),
        settings,
        "checkout.session.completed",
        {"subscription": "sub_123", "customer": "cus_123"},
    )


def test_notify_admins_of_stripe_event_skips_when_no_recipients(monkeypatch):
    settings = _settings()
    called = {}

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, *_args, **_kwargs):
            called["send"] = True

    monkeypatch.setattr(stripe_admin_notifications, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_admin_notifications, "get_admin_emails", lambda session: [])

    stripe_admin_notifications.notify_admins_of_stripe_event(
        SimpleNamespace(),
        settings,
        "checkout.session.completed",
        {"subscription": "sub_123", "customer": "cus_123"},
    )

    assert called == {}


def test_build_admin_event_subject_variants():
    assert (
        stripe_admin_notifications._build_admin_event_subject(
            event_type="customer.subscription.deleted",
            payload={},
            subscription=None,
        )
        == "[Stripe] Abonnement résilié"
    )
    assert (
        stripe_admin_notifications._build_admin_event_subject(
            event_type="customer.subscription.updated",
            payload={"cancel_at_period_end": True},
            subscription=None,
        )
        == "[Stripe] Annulation programmée"
    )
    assert (
        stripe_admin_notifications._build_admin_event_subject(
            event_type="customer.subscription.updated",
            payload={"cancel_at_period_end": False},
            subscription=None,
        )
        == "[Stripe] Abonnement mis à jour"
    )


def test_format_stripe_event_summary_includes_subscription_details():
    subscription = {
        "status": "active",
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "metadata": {"plan_key": "starter", "referrer_name": "Alice Martin"},
        "trial_end": 1700000000,
        "current_period_end": 1700600000,
        "cancel_at": 1701200000,
    }
    payload = {
        "id": "sub_123",
        "customer": "cus_123",
        "metadata": {"contact_email": "client@example.com"},
    }
    client = SimpleNamespace(name="ACME", id=uuid4(), recipients=[])

    summary = stripe_admin_notifications._format_stripe_event_summary(
        event_type="customer.subscription.updated",
        payload=payload,
        subscription=subscription,
        client=client,
    )

    assert "Statut: active" in summary
    assert "Price: price_starter" in summary
    assert "Plan: starter" in summary
    assert "Parrain: Alice Martin" in summary
    assert "Fin d'essai" in summary


def test_format_stripe_event_summary_html_bolds_referrer():
    subscription = {
        "status": "active",
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "metadata": {"plan_key": "starter", "referrer_name": "Alice Martin"},
    }
    payload = {
        "id": "sub_123",
        "customer": "cus_123",
        "metadata": {"contact_email": "client@example.com"},
    }
    client = SimpleNamespace(name="ACME", id=uuid4(), recipients=[])

    summary = stripe_admin_notifications._format_stripe_event_summary_html(
        event_type="customer.subscription.updated",
        payload=payload,
        subscription=subscription,
        client=client,
    )

    assert "<strong>Parrain:</strong> <strong>Alice Martin</strong>" in summary


def test_resolve_referrer_name_uses_payload_metadata():
    assert (
        stripe_admin_notifications._resolve_referrer_name(
            payload={"metadata": {"referrer_name": "  Bob Martin  "}},
            subscription=None,
        )
        == "Bob Martin"
    )


def test_resolve_referrer_name_returns_none_for_blank():
    assert (
        stripe_admin_notifications._resolve_referrer_name(
            payload={"metadata": {"referrer_name": "  "}},
            subscription=None,
        )
        is None
    )


def test_format_stripe_event_summary_html_includes_dates_and_reason():
    subscription = {
        "status": "active",
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "metadata": {"plan_key": "starter"},
        "trial_end": 1700000000,
        "current_period_end": 1700600000,
        "cancel_at": 1701200000,
        "cancellation_details": {"reason": "pricing"},
    }
    payload = {
        "id": "sub_123",
        "customer": "cus_123",
        "metadata": {},
    }
    client = SimpleNamespace(name="ACME", id=uuid4(), recipients=[SimpleNamespace(email="ops@example.com")])

    summary = stripe_admin_notifications._format_stripe_event_summary_html(
        event_type="customer.subscription.updated",
        payload=payload,
        subscription=subscription,
        client=client,
    )

    assert "<strong>Subscription:</strong> sub_123" in summary
    assert "<strong>Customer:</strong> cus_123" in summary
    assert "Fin d'essai" in summary
    assert "Fin de période" in summary
    assert "Résiliation planifiée" in summary
    assert "Raison d'annulation" in summary


def test_format_stripe_event_summary_uses_client_recipient():
    client = SimpleNamespace(name="ACME", id=uuid4(), recipients=[SimpleNamespace(email="ops@example.com")])
    summary = stripe_admin_notifications._format_stripe_event_summary(
        event_type="customer.subscription.updated",
        payload={},
        subscription=None,
        client=client,
    )
    assert "ops@example.com" in summary


def test_notify_admins_of_stripe_event_uses_subscription_payload(monkeypatch):
    settings = _settings()
    sent = {}

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["recipients"] = recipients

    monkeypatch.setattr(stripe_admin_notifications, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_admin_notifications, "get_admin_emails", lambda session: ["ops@example.com"])
    monkeypatch.setattr(
        stripe_admin_notifications,
        "find_client",
        lambda *args, **kwargs: SimpleNamespace(name="ACME", id=uuid4(), recipients=[]),
    )

    payload = {
        "object": "subscription",
        "id": "sub_123",
        "customer": "cus_123",
        "status": "active",
        "metadata": {"plan_key": "starter"},
    }

    stripe_admin_notifications.notify_admins_of_stripe_event(
        SimpleNamespace(),
        settings,
        "customer.subscription.updated",
        payload,
    )

    assert sent.get("recipients") == ["ops@example.com"]
    assert "Abonnement mis à jour" in sent.get("subject", "")


def test_extract_cancellation_reason_prefers_reason_then_comment():
    assert stripe_admin_notifications._extract_cancellation_reason({"reason": "pricing"}) == "pricing"
    assert stripe_admin_notifications._extract_cancellation_reason({"comment": "too expensive"}) == "too expensive"
    assert stripe_admin_notifications._extract_cancellation_reason("oops") is None


def test_create_portal_session_requires_customer_id(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(
        stripe_portal_service,
        "find_client_by_email",
        lambda session, email: SimpleNamespace(stripe_customer_id=None),
    )

    with pytest.raises(HTTPException) as exc:
        stripe_portal_service.create_portal_session(SimpleNamespace(), settings, "ops@example.com")
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_create_portal_session_raises_when_missing_url(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(stripe_customer_id="cus_123")
    monkeypatch.setattr(stripe_portal_service, "find_client_by_email", lambda session, email: client)

    class DummyPortalSession:
        url = None

    class DummyPortal:
        @staticmethod
        def create(**_kwargs):
            return DummyPortalSession()

    monkeypatch.setattr(stripe_portal_service.stripe, "billing_portal", SimpleNamespace(Session=DummyPortal))

    with pytest.raises(HTTPException) as exc:
        stripe_portal_service.create_portal_session(SimpleNamespace(), settings, "ops@example.com")
    assert exc.value.status_code == status.HTTP_502_BAD_GATEWAY


def test_send_portal_access_email_sends(monkeypatch):
    settings = _settings()
    sent = {}
    client = SimpleNamespace(stripe_customer_id="cus_123", stripe_subscription_id="sub_123")

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, *, html_body=None, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["recipients"] = recipients
            sent["html"] = html_body

    monkeypatch.setattr(stripe_portal_service, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_portal_service, "find_client_by_email", lambda session, email: client)
    monkeypatch.setattr(stripe_portal_service, "create_portal_session", lambda *_args, **_kwargs: "https://portal")

    stripe_portal_service.send_portal_access_email(SimpleNamespace(), settings, "ops@example.com")

    assert sent.get("recipients") == ["ops@example.com"]
    assert "portail" in sent.get("subject", "").lower()
    assert "https://portal" in sent.get("body", "")
    assert "business-tracker.fr" in sent.get("body", "")


def test_send_portal_access_email_requires_email_service(monkeypatch):
    settings = _settings()

    class DummyEmail:
        def is_enabled(self):
            return False

        def is_configured(self):
            return False

    monkeypatch.setattr(stripe_portal_service, "EmailService", lambda: DummyEmail())

    with pytest.raises(HTTPException) as exc:
        stripe_portal_service.send_portal_access_email(SimpleNamespace(), settings, "ops@example.com")
    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_update_subscription_charges_immediately(monkeypatch):
    settings = _settings()
    sent = {}
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(
        stripe_checkout_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        stripe_checkout_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(stripe_checkout_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {"items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]}}

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_business"}}]},
                "cancel_at_period_end": False,
                "trial_end": None,
                "latest_invoice": {
                    "id": "in_123",
                    "status": "open",
                    "hosted_invoice_url": "https://invoice.stripe.com/pay/in_123",
                },
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id):
            return {"invoice_settings": {"default_payment_method": "pm_123"}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    class DummyInvoice:
        @staticmethod
        def pay(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "paid",
            }

        @staticmethod
        def retrieve(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "open",
                "hosted_invoice_url": "https://invoice.stripe.com/pay/in_123",
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Invoice", DummyInvoice)

    class DummyInvoice:
        @staticmethod
        def create(**_kwargs):
            return {"id": "in_123"}

        @staticmethod
        def finalize_invoice(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "open",
            }

        @staticmethod
        def pay(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "paid",
            }

        @staticmethod
        def retrieve(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "paid",
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Invoice", DummyInvoice)

    class DummyInvoice:
        @staticmethod
        def create(**_kwargs):
            return {"id": "in_123"}

        @staticmethod
        def finalize_invoice(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "open",
            }

        @staticmethod
        def pay(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "paid",
            }

        @staticmethod
        def retrieve(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "paid",
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Invoice", DummyInvoice)

    def price_retrieve(price_id):
        return {"unit_amount": 5600}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["recipients"] = recipients

    monkeypatch.setattr(stripe_checkout_service, "EmailService", lambda: DummyEmail())

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    result = stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert result.payment_url is None
    assert result.action == "upgrade"
    assert result.effective_at is None
    assert sent.get("subject")
    assert "upgrade" in sent.get("body", "").lower()


def test_update_subscription_handles_cancel_at_period_end(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    sent = {}
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(stripe_checkout_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {"items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]}}

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_business"}}]},
                "latest_invoice": None,
                "cancel_at_period_end": True,
                "current_period_end": 1700000000,
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id):
            return {"invoice_settings": {"default_payment_method": "pm_123"}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    class DummyInvoice:
        @staticmethod
        def create(**_kwargs):
            return {"id": "in_123"}

        @staticmethod
        def finalize_invoice(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "open",
            }

        @staticmethod
        def pay(_invoice_id, **_kwargs):
            return {
                "id": _invoice_id,
                "status": "paid",
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Invoice", DummyInvoice)

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["recipients"] = recipients

    monkeypatch.setattr(stripe_checkout_service, "EmailService", lambda: DummyEmail())

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert client.end_date is not None


def test_preview_upgrade_amount(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {
                "items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]},
                "trial_end": None,
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyInvoice:
        @staticmethod
        def upcoming(**_kwargs):
            return {
                "amount_due": 20000,
                "currency": "eur",
                "lines": {
                    "data": [
                        {"amount": 12800, "proration": False},  # Nouveau plan
                        {"amount": 7200, "proration": True},    # Prorata upgrade
                        {"amount": -5600, "proration": True},   # Crédit plan précédent (optionnel)
                    ]
                }
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Invoice", DummyInvoice)

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id, **_kwargs):
            return {"invoice_settings": {"default_payment_method": "pm_123"}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    preview = stripe_checkout_service.get_subscription_update_preview(SimpleNamespace(), settings, payload)
    # Le prorata net est 7200 - 5600 = 1600 (lignes avec proration=True)
    assert preview.amount_due == 1600
    assert preview.currency == "eur"
    assert preview.is_upgrade is True
    assert preview.is_trial is False
    assert preview.has_payment_method is True


def test_preview_cancel_pending_downgrade_returns_zero(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {
                "items": {"data": [{"id": "si_123", "price": {"id": "price_business"}}]},
                "trial_end": None,
                "metadata": {
                    "plan_key": "business",
                    "pending_plan_key": "starter",
                },
                "currency": "eur",
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id, **_kwargs):
            return {"invoice_settings": {"default_payment_method": "pm_123"}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    def unexpected_upcoming(**_kwargs):
        raise AssertionError("Stripe.Invoice.upcoming ne doit pas être appelé")

    monkeypatch.setattr(
        stripe_checkout_service.stripe,
        "Invoice",
        SimpleNamespace(upcoming=unexpected_upcoming),
    )

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    preview = stripe_checkout_service.get_subscription_update_preview(SimpleNamespace(), settings, payload)
    assert preview.amount_due == 0
    assert preview.currency == "eur"
    assert preview.is_upgrade is False
    assert preview.is_trial is False
    assert preview.has_payment_method is True


def test_preview_upgrade_during_trial_returns_zero(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {
                "items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]},
                "trial_end": 4102444800,
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id, **_kwargs):
            return {"invoice_settings": {}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    preview = stripe_checkout_service.get_subscription_update_preview(SimpleNamespace(), settings, payload)
    assert preview.amount_due == 0
    assert preview.is_upgrade is True
    assert preview.is_trial is True
    assert preview.has_payment_method is False


def test_preview_upgrade_without_plan_change_returns_zero(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {
                "items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]},
                "trial_end": None,
                "currency": "eur",
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    def price_retrieve(price_id):
        return {"unit_amount": 5600}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id, **_kwargs):
            return {"invoice_settings": {"default_payment_method": "pm_456"}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[category_id],
        access_token="token_123456",
    )

    preview = stripe_checkout_service.get_subscription_update_preview(SimpleNamespace(), settings, payload)
    assert preview.amount_due == 0
    assert preview.is_upgrade is False
    assert preview.currency == "eur"
    assert preview.has_payment_method is True


def test_preview_subscription_requires_client(monkeypatch):
    settings = _settings()
    category_id = uuid4()

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[category_id],
        access_token="token_123456",
    )

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service.get_subscription_update_preview(SimpleNamespace(), settings, payload)
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_preview_subscription_requires_item(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {"items": {"data": []}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[category_id],
        access_token="token_123456",
    )

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service.get_subscription_update_preview(SimpleNamespace(), settings, payload)
    assert exc.value.status_code == status.HTTP_409_CONFLICT


def test_update_subscription_charge_fails(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(stripe_checkout_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {"items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]}}

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_business"}}]},
                "cancel_at_period_end": False,
                "trial_end": None,
                "latest_invoice": "in_123",
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id):
            return {"invoice_settings": {"default_payment_method": "pm_123"}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    class DummyInvoice:
        @staticmethod
        def retrieve(_invoice_id):
            return {"id": _invoice_id, "status": "open"}

        @staticmethod
        def pay(_invoice_id, **_kwargs):
            raise stripe_checkout_service.stripe.error.CardError(
                "Card declined",
                param=None,
                code="card_declined",
            )

    monkeypatch.setattr(stripe_checkout_service.stripe, "Invoice", DummyInvoice)

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert exc.value.status_code == status.HTTP_402_PAYMENT_REQUIRED


def test_update_subscription_charge_stripe_error(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(stripe_checkout_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {"items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]}}

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_business"}}]},
                "cancel_at_period_end": False,
                "trial_end": None,
                "latest_invoice": "in_123",
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id):
            return {"invoice_settings": {"default_payment_method": "pm_123"}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    class DummyInvoice:
        @staticmethod
        def retrieve(_invoice_id):
            return {"id": _invoice_id, "status": "open"}

        @staticmethod
        def pay(_invoice_id, **_kwargs):
            raise stripe_checkout_service.stripe.error.StripeError("boom")

    monkeypatch.setattr(stripe_checkout_service.stripe, "Invoice", DummyInvoice)

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert exc.value.status_code == status.HTTP_502_BAD_GATEWAY


def test_update_subscription_charge_unconfirmed(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(stripe_checkout_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {"items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]}}

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_business"}}]},
                "cancel_at_period_end": False,
                "trial_end": None,
                "latest_invoice": "in_123",
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id):
            return {"invoice_settings": {"default_payment_method": "pm_123"}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    class DummyInvoice:
        @staticmethod
        def retrieve(_invoice_id):
            return {"id": _invoice_id, "status": "open"}

        @staticmethod
        def pay(_invoice_id, **_kwargs):
            return {"id": _invoice_id, "status": "open"}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Invoice", DummyInvoice)

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert exc.value.status_code == status.HTTP_402_PAYMENT_REQUIRED


def test_ensure_stripe_http_client_resets_timeout(monkeypatch):
    monkeypatch.setattr(
        stripe_checkout_service.stripe,
        "new_default_http_client",
        lambda timeout: SimpleNamespace(_timeout=timeout),
    )
    monkeypatch.setattr(
        stripe_checkout_service.stripe,
        "default_http_client",
        SimpleNamespace(_timeout=5),
    )

    stripe_checkout_service._ensure_stripe_http_client()

    assert stripe_checkout_service.stripe.default_http_client._timeout == stripe_checkout_service.STRIPE_TIMEOUT_SECONDS


def test_update_subscription_requires_client(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[uuid4()],
        access_token="token_123456",
    )

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service.update_subscription(SimpleNamespace(), settings, payload)
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_update_subscription_requires_item(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {"items": {"data": []}}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[category_id],
        access_token="token_123456",
    )

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service.update_subscription(SimpleNamespace(flush=lambda: None), settings, payload)
    assert exc.value.status_code == status.HTTP_409_CONFLICT


def test_update_subscription_downgrade_has_no_proration(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    sent = {}
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    called = {}
    monkeypatch.setattr(
        stripe_checkout_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: called.setdefault("apply", True),
    )

    captured = {}

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {
                "items": {"data": [{"id": "si_123", "price": {"id": "price_business"}}]},
                "current_period_end": 1700000000,
            }

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            captured.update(_kwargs)
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_starter"}}]},
                "latest_invoice": None,
                "cancel_at_period_end": False,
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["recipients"] = recipients

    monkeypatch.setattr(stripe_checkout_service, "EmailService", lambda: DummyEmail())

    def price_retrieve(price_id):
        return {"unit_amount": 12800 if price_id == "price_business" else 5600}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[category_id],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    result = stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert captured.get("proration_behavior") == "none"
    assert called == {}
    assert captured.get("metadata", {}).get("pending_plan_key") == "starter"
    assert "pending_category_ids" in captured.get("metadata", {})
    assert "pending_effective_at" in captured.get("metadata", {})
    assert result.action == "downgrade"
    assert result.effective_at is not None
    assert "prochaine" in sent.get("body", "")


def test_update_subscription_cancel_pending_downgrade_keeps_no_proration(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
        stripe_plan_key="business",
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    monkeypatch.setattr(
        stripe_checkout_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: None,
    )

    captured = {}

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {
                "items": {"data": [{"id": "si_123", "price": {"id": "price_business"}}]},
                "metadata": {
                    "plan_key": "business",
                    "category_ids": f"[\"{category_id}\"]",
                    "pending_plan_key": "starter",
                    "pending_category_ids": f"[\"{uuid4()}\"]",
                    "pending_effective_at": "1700000000",
                },
                "latest_invoice": None,
                "cancel_at_period_end": False,
            }

        @staticmethod
        def modify(_subscription_id, **kwargs):
            captured.update(kwargs)
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "metadata": kwargs.get("metadata", {}),
                "cancel_at_period_end": False,
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            return None

    monkeypatch.setattr(stripe_checkout_service, "EmailService", lambda: DummyEmail())

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    result = stripe_checkout_service.update_subscription(DummySession(), settings, payload)

    assert captured.get("proration_behavior") == "none"
    assert "pending_plan_key" not in captured.get("metadata", {})
    assert "pending_category_ids" not in captured.get("metadata", {})
    assert "pending_effective_at" not in captured.get("metadata", {})
    assert result.action == "update"


def test_update_subscription_updates_categories_without_plan_change(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    sent = {}
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
        stripe_plan_key="starter",
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    applied = {}
    monkeypatch.setattr(
        stripe_checkout_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: applied.setdefault("ok", True),
    )

    captured = {}

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {"items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]}}

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            captured.update(_kwargs)
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_starter"}}]},
                "latest_invoice": {"hosted_invoice_url": "https://invoice.example.com"},
                "cancel_at_period_end": False,
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["recipients"] = recipients

    monkeypatch.setattr(stripe_checkout_service, "EmailService", lambda: DummyEmail())

    def price_retrieve(price_id):
        return {"unit_amount": 5600}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[category_id],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    result = stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert captured.get("proration_behavior") == "none"
    assert "items" not in captured
    assert applied.get("ok") is True
    assert result.action == "update"
    assert result.payment_url is None


def test_update_subscription_rejects_category_change_too_soon(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {
                "items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]},
                "metadata": {
                    "plan_key": "starter",
                    "category_ids": f"[\"{uuid4()}\"]",
                    "last_category_update_at": str(datetime.now(timezone.utc).timestamp()),
                },
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    def price_retrieve(price_id):
        return {"unit_amount": 5600}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[category_id],
        access_token="token_123456",
    )

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service.update_subscription(SimpleNamespace(), settings, payload)
    assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_update_subscription_allows_category_change_after_cooldown(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(stripe_checkout_service, "_get_price_amount", lambda *_args, **_kwargs: 5600)
    monkeypatch.setattr(stripe_checkout_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)

    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=31)).timestamp()

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {
                "items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]},
                "metadata": {
                    "plan_key": "starter",
                    "category_ids": f"[\"{uuid4()}\"]",
                    "last_category_update_at": str(old_timestamp),
                },
            }

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_starter"}}]},
                "latest_invoice": None,
                "cancel_at_period_end": False,
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            return None

    monkeypatch.setattr(stripe_checkout_service, "EmailService", lambda: DummyEmail())

    payload = PublicStripeUpdateRequest(
        plan_key="starter",
        category_ids=[category_id],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    result = stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert result.action == "update"


def test_update_subscription_upgrade_does_not_return_payment_url_during_trial(monkeypatch):
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(stripe_checkout_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)

    captured = {}

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {
                "items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]},
                "trial_end": 4102444800,
            }

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            captured.update(_kwargs)
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_business"}}]},
                "latest_invoice": {"hosted_invoice_url": "https://invoice.example.com"},
                "cancel_at_period_end": False,
                "trial_end": 4102444800,
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            return None

    monkeypatch.setattr(stripe_checkout_service, "EmailService", lambda: DummyEmail())

    def unexpected_invoice_retrieve(_invoice_id, **_kwargs):
        raise AssertionError("Stripe.Invoice.retrieve ne doit pas être appelé pendant l'essai")

    monkeypatch.setattr(
        stripe_checkout_service.stripe,
        "Invoice",
        SimpleNamespace(retrieve=unexpected_invoice_retrieve),
    )

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    result = stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert result.action == "upgrade"
    assert result.payment_url is None
    assert captured.get("proration_behavior") == "none"
    assert "expand" not in captured


def test_update_subscription_upgrade_returns_payment_url_when_no_payment_method(monkeypatch):
    """Test que l'upgrade sans moyen de paiement retourne une URL de facture au lieu d'une erreur 409."""
    settings = _settings()
    category_id = uuid4()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        subscriptions=[],
        end_date=None,
    )

    monkeypatch.setattr(stripe_checkout_service, "_validate_categories_exist", lambda session, ids: None)
    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(stripe_checkout_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)

    class DummySubscription:
        @staticmethod
        def retrieve(_subscription_id, **_kwargs):
            return {"items": {"data": [{"id": "si_123", "price": {"id": "price_starter"}}]}}

        @staticmethod
        def modify(_subscription_id, **_kwargs):
            return {
                "id": _subscription_id,
                "customer": "cus_123",
                "items": {"data": [{"price": {"id": "price_business"}}]},
                "cancel_at_period_end": False,
                "trial_end": None,
                "metadata": {},
                "latest_invoice": {
                    "id": "in_123",
                    "status": "open",
                    "hosted_invoice_url": "https://invoice.stripe.com/pay/in_123",
                },
            }

    monkeypatch.setattr(stripe_checkout_service.stripe, "Subscription", DummySubscription)

    class DummyCustomer:
        @staticmethod
        def retrieve(_customer_id):
            return {"invoice_settings": {}}  # Pas de moyen de paiement

    monkeypatch.setattr(stripe_checkout_service.stripe, "Customer", DummyCustomer)

    def price_retrieve(price_id):
        return {"unit_amount": 5600 if price_id == "price_starter" else 12800}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    class DummyEmail:
        def is_enabled(self):
            return False

        def is_configured(self):
            return False

        def send(self, subject, body, recipients, **_kwargs):
            return None

    monkeypatch.setattr(stripe_checkout_service, "EmailService", lambda: DummyEmail())

    payload = PublicStripeUpdateRequest(
        plan_key="business",
        category_ids=[category_id, uuid4(), uuid4(), uuid4(), uuid4()],
        access_token="token_123456",
    )

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    result = stripe_checkout_service.update_subscription(DummySession(), settings, payload)
    assert result.action == "upgrade"
    assert result.payment_url == "https://invoice.stripe.com/pay/in_123"


def test_get_subscription_info_returns_categories(monkeypatch):
    settings = _settings()
    category_a = SimpleNamespace(id=uuid4(), name="Restauration")
    category_b = SimpleNamespace(id=uuid4(), name="Commerce")
    sub_a = SimpleNamespace(category=category_a)
    sub_b = SimpleNamespace(category=category_b)
    client = SimpleNamespace(
        stripe_plan_key="starter",
        stripe_subscription_status="active",
        stripe_current_period_end=None,
        stripe_cancel_at=None,
        stripe_subscription_id="sub_123",
        subscriptions=[SimpleNamespace(subcategory=sub_a), SimpleNamespace(subcategory=sub_b)],
    )

    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(
        stripe_checkout_service,
        "retrieve_subscription",
        lambda settings, subscription_id: None,
    )

    result = stripe_checkout_service.get_subscription_info(SimpleNamespace(), settings, "token_123456")
    assert result.plan_key == "starter"
    assert result.status == "active"
    assert result.contact_email == "jean@example.com"
    assert result.contact_name is None
    assert len(result.categories) == 2


def test_get_subscription_info_falls_back_to_stripe_subscription(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(
        stripe_plan_key="starter",
        stripe_subscription_status="trialing",
        stripe_current_period_end=None,
        stripe_cancel_at=None,
        stripe_subscription_id="sub_123",
        subscriptions=[],
    )

    monkeypatch.setattr(stripe_checkout_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_checkout_service,
        "parse_upgrade_token",
        lambda settings, token: SimpleNamespace(
            customer_id="cus_123",
            subscription_id="sub_123",
            email="jean@example.com",
        ),
    )
    monkeypatch.setattr(
        stripe_checkout_service,
        "retrieve_subscription",
        lambda settings, subscription_id: {
            "current_period_end": 1700000000,
            "cancel_at": None,
            "metadata": {"contact_name": "Jean Dupont", "contact_email": "jean@example.com"},
        },
    )

    result = stripe_checkout_service.get_subscription_info(SimpleNamespace(), settings, "token_123456")
    assert result.current_period_end is not None
    assert result.contact_name == "Jean Dupont"
    assert result.contact_email == "jean@example.com"

def test_get_price_amount_uses_decimal(monkeypatch):
    def price_retrieve(_price_id):
        return {"unit_amount": None, "unit_amount_decimal": "5600.00"}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    assert stripe_checkout_service._get_price_amount("price_123") == Decimal("5600.00")

def test_get_price_amount_returns_none_for_invalid_decimal(monkeypatch):
    def price_retrieve(_price_id):
        return {"unit_amount": None, "unit_amount_decimal": "invalid"}

    monkeypatch.setattr(stripe_checkout_service.stripe, "Price", SimpleNamespace(retrieve=price_retrieve))

    assert stripe_checkout_service._get_price_amount("price_123") is None

def test_get_price_amount_returns_none_for_missing_id():
    assert stripe_checkout_service._get_price_amount(None) is None


def test_resolve_recipient_email_prefers_fallback():
    client = SimpleNamespace(recipients=[SimpleNamespace(email="client@example.com")])
    result = stripe_checkout_service._resolve_recipient_email(client, "fallback@example.com")
    assert result == "fallback@example.com"


def test_resolve_recipient_email_uses_client_recipients():
    client = SimpleNamespace(recipients=[SimpleNamespace(email="client@example.com")])
    result = stripe_checkout_service._resolve_recipient_email(client, None)
    assert result == "client@example.com"


def test_resolve_recipient_email_returns_none_without_match():
    client = SimpleNamespace(recipients=[])
    result = stripe_checkout_service._resolve_recipient_email(client, "   ")
    assert result is None

def test_is_upgrade_handles_downgrade():
    assert stripe_checkout_service._is_upgrade(current_amount=Decimal("100"), target_amount=Decimal("50")) is False

def test_build_post_purchase_email_html_contains_links():
    html = stripe_webhook_service._build_post_purchase_email_html(
        "https://stripe.example.com/portal",
        "https://app.example.com/upgrade#portal",
    )
    assert "https://stripe.example.com/portal" in html
    assert "https://app.example.com/upgrade#portal" in html
    assert "Conservez cet email" in html


def test_build_post_purchase_email_html_without_portal():
    html = stripe_webhook_service._build_post_purchase_email_html(
        None,
        "https://app.example.com/upgrade#portal",
    )
    assert "Changer de plan" in html


def test_validate_categories_exist_accepts_known_ids():
    category_id = uuid4()
    session = SimpleNamespace(execute=lambda stmt: _FakeResult([category_id]))

    stripe_checkout_service._validate_categories_exist(session, [category_id])


def test_validate_categories_exist_rejects_empty():
    session = SimpleNamespace(execute=lambda stmt: _FakeResult([]))
    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service._validate_categories_exist(session, [])
    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_find_client_by_email_returns_match():
    client = SimpleNamespace(id=uuid4())
    session = SimpleNamespace(execute=lambda stmt: _FakeResult(client))

    result = find_client_by_email(session, "ops@example.com")

    assert result is client


def test_find_client_prefers_customer_id_when_no_subscription():
    client = SimpleNamespace(id=uuid4())

    def execute(stmt):
        return _FakeResult(client)

    session = SimpleNamespace(execute=execute)
    result = stripe_subscription_utils.find_client(session, customer_id="cus", subscription_id=None, email=None)
    assert result is client


def test_validate_categories_exist_rejects_missing():
    category_id = uuid4()
    session = SimpleNamespace(execute=lambda stmt: _FakeResult([]))

    with pytest.raises(HTTPException) as exc:
        stripe_checkout_service._validate_categories_exist(session, [category_id])
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_find_client_prefers_subscription_id():
    client = SimpleNamespace(id=uuid4())
    session = SimpleNamespace(execute=lambda stmt: _FakeResult(client))

    result = stripe_subscription_utils.find_client(session, customer_id=None, subscription_id="sub", email=None)

    assert result is client


def test_find_client_falls_back_to_email(monkeypatch):
    session = SimpleNamespace(execute=lambda stmt: _FakeResult(None))
    fallback = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(stripe_subscription_utils, "find_client_by_email", lambda sess, email: fallback)

    result = stripe_subscription_utils.find_client(session, customer_id=None, subscription_id=None, email="ops@example.com")

    assert result is fallback


def test_ensure_recipient_adds_new_email():
    client = SimpleNamespace(recipients=[])
    stripe_subscription_utils.ensure_recipient(client, "ops@example.com")
    assert client.recipients[0].email == "ops@example.com"


def test_apply_subscriptions_from_categories_updates_client(monkeypatch):
    category_id = uuid4()
    subcategory = models.NafSubCategory(name="Cat", naf_code="5610A")
    session = SimpleNamespace(execute=lambda stmt: _FakeResult([subcategory]))
    existing = models.ClientSubscription(subcategory_id=subcategory.id, subcategory=subcategory)
    client = SimpleNamespace(subscriptions=[existing])

    stripe_subscription_utils.apply_subscriptions_from_categories(session, client, [category_id])

    assert client.subscriptions


def test_apply_subscriptions_from_categories_distinct_ordering_is_postgres_safe():
    from sqlalchemy.dialects import postgresql

    category_id = uuid4()
    captured: dict[str, str] = {}

    def execute(stmt):
        compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        captured["sql"] = str(compiled)
        return _FakeResult([])

    session = SimpleNamespace(execute=execute)
    client = SimpleNamespace(subscriptions=[])

    stripe_subscription_utils.apply_subscriptions_from_categories(session, client, [category_id])

    sql = captured.get("sql", "")
    assert "DISTINCT ON (naf_subcategories.id)" in sql
    assert "ORDER BY naf_subcategories.id, naf_subcategories.naf_code" in sql


def test_apply_stripe_fields_sets_plan_key_from_price(settings=None):
    settings = _settings()
    subscription = {
        "status": "active",
        "current_period_end": 1700000000,
        "cancel_at": None,
        "items": {"data": [{"price": {"id": "price_business"}}]},
    }
    client = SimpleNamespace(
        stripe_customer_id=None,
        stripe_subscription_id=None,
        stripe_subscription_status=None,
        stripe_current_period_end=None,
        stripe_cancel_at=None,
        stripe_plan_key=None,
        stripe_price_id=None,
    )

    stripe_subscription_utils.apply_stripe_fields(client, settings, subscription, "cus", "sub", None)

    assert client.stripe_plan_key == "business"
    assert client.stripe_subscription_status == "active"


def test_apply_stripe_fields_with_plan_key_overrides():
    settings = _settings()
    subscription = {
        "status": "active",
        "items": {"data": [{"price": {"id": "price_business"}}]},
    }
    client = SimpleNamespace(
        stripe_customer_id=None,
        stripe_subscription_id=None,
        stripe_subscription_status=None,
        stripe_current_period_end=None,
        stripe_cancel_at=None,
        stripe_plan_key=None,
        stripe_price_id=None,
    )

    stripe_subscription_utils.apply_stripe_fields(client, settings, subscription, "cus", "sub", "starter")
    assert client.stripe_plan_key == "starter"


def test_resolve_price_id_empty_returns_none():
    assert stripe_subscription_utils.resolve_price_id({"items": {"data": []}}) is None


def test_resolve_plan_key_returns_none_when_missing():
    settings = _settings()
    assert stripe_subscription_utils.resolve_plan_key(settings, "price_unknown") is None


def test_build_client_name_formats():
    name = stripe_subscription_utils.build_client_name("Jean", "ACME", "jean@example.com")
    assert name == "Jean / ACME"


def test_parse_category_ids_handles_invalid_json():
    assert stripe_subscription_utils.parse_category_ids("not-json") == []


def test_parse_category_ids_handles_valid_json():
    identifier = uuid4()
    data = stripe_subscription_utils.parse_category_ids(f"[\"{identifier}\"]")
    assert data == [identifier]


def test_parse_category_ids_handles_non_list_json():
    assert stripe_subscription_utils.parse_category_ids("{\"id\":1}") == []


def test_resolve_email_from_payload_prefers_metadata():
    email = stripe_subscription_utils.resolve_email_from_payload(
        {"customer_email": "fallback@example.com"},
        {"contact_email": "meta@example.com"},
    )
    assert email == "meta@example.com"


def test_resolve_email_from_payload_fallback_customer_email():
    email = stripe_subscription_utils.resolve_email_from_payload({"customer_email": "fallback@example.com"}, {})
    assert email == "fallback@example.com"


def test_resolve_start_and_end_dates():
    start = stripe_subscription_utils.resolve_start_date({"current_period_start": 1700000000})
    end = stripe_subscription_utils.resolve_end_date({"current_period_end": 1700000000})
    assert start is not None
    assert end is not None


def test_resolve_start_date_defaults_today():
    today = date.today()
    assert stripe_subscription_utils.resolve_start_date(None) == today


def test_resolve_end_date_defaults_none():
    assert stripe_subscription_utils.resolve_end_date(None) is None


def test_to_datetime_handles_none():
    assert stripe_subscription_utils.to_datetime(None) is None


def test_handle_checkout_completed_creates_client(monkeypatch):
    settings = _settings()
    added = []
    sent = {}

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            added.append(obj)

        def flush(self):
            return None

    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: None)
    monkeypatch.setattr(stripe_webhook_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        stripe_webhook_service,
        "_send_post_purchase_email",
        lambda *args, **kwargs: sent.setdefault("ok", True),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        stripe_webhook_service,
        "retrieve_subscription",
        lambda *args, **kwargs: {
            "status": "active",
            "current_period_end": 1700000000,
            "items": {"data": [{"price": {"id": "price_starter"}}]},
        },
    )

    payload = {
        "metadata": {
            "category_ids": "[]",
            "plan_key": "starter",
            "contact_name": "Jean",
            "company_name": "ACME",
            "contact_email": "jean@example.com",
        },
        "customer": "cus_123",
        "subscription": "sub_123",
        "customer_details": {"email": "jean@example.com"},
    }

    stripe_webhook_service._handle_checkout_completed(DummySession(), settings, payload)

    assert added
    assert sent.get("ok") is True


def test_handle_checkout_completed_applies_subscriptions(monkeypatch):
    settings = _settings()
    called = {}

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    monkeypatch.setattr(
        stripe_webhook_service,
        "find_client",
        lambda *args, **kwargs: SimpleNamespace(id=uuid4(), recipients=[], stripe_plan_key=None),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: called.setdefault("subs", True),
    )
    monkeypatch.setattr(stripe_webhook_service, "_send_post_purchase_email", lambda *args, **kwargs: None)
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        stripe_webhook_service,
        "retrieve_subscription",
        lambda *args, **kwargs: {
            "status": "active",
            "current_period_end": 1700000000,
            "items": {"data": [{"price": {"id": "price_starter"}}]},
        },
    )

    payload = {
        "metadata": {
            "category_ids": f"[\"{uuid4()}\"]",
            "plan_key": "starter",
            "contact_name": "Jean",
            "company_name": "ACME",
            "contact_email": "jean@example.com",
        },
        "customer": "cus_123",
        "subscription": "sub_123",
        "customer_details": {"email": "jean@example.com"},
    }

    stripe_webhook_service._handle_checkout_completed(DummySession(), settings, payload)
    assert called.get("subs") is True


def test_handle_subscription_updated_sets_end_date(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub",
        stripe_customer_id="cus",
        stripe_cancel_at=None,
        stripe_subscription_status="active",
    )

    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(stripe_webhook_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    payload = {
        "id": "sub",
        "customer": "cus",
        "metadata": {"category_ids": "[]", "plan_key": "starter"},
        "cancel_at_period_end": True,
        "current_period_end": 1700000000,
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "status": "active",
    }

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    stripe_webhook_service._handle_subscription_updated(DummySession(), settings, payload)
    assert client.end_date == date.fromtimestamp(1700000000)


def test_handle_subscription_updated_pending_downgrade_defers(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub",
        stripe_customer_id="cus",
        stripe_cancel_at=None,
        stripe_subscription_status="active",
    )
    called = {}

    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: called.setdefault("apply", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_stripe_fields",
        lambda _client, _settings, _payload, _customer, _subscription, plan_key: called.setdefault(
            "plan_key", plan_key
        ),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    payload = {
        "id": "sub",
        "customer": "cus",
        "metadata": {
            "category_ids": "[]",
            "plan_key": "business",
            "pending_plan_key": "starter",
            "pending_category_ids": f"[\"{uuid4()}\"]",
            "pending_effective_at": "1700000000",
        },
        "current_period_start": 1690000000,
        "current_period_end": 1700000000,
        "items": {"data": [{"price": {"id": "price_business"}}]},
        "status": "active",
    }

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    stripe_webhook_service._handle_subscription_updated(DummySession(), settings, payload)
    assert called == {}


def test_handle_subscription_updated_pending_downgrade_keeps_current_when_price_already_switched(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub",
        stripe_customer_id="cus",
        stripe_cancel_at=None,
        stripe_subscription_status="active",
        stripe_plan_key="business",
    )
    called = {}

    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: called.setdefault("apply", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_stripe_fields",
        lambda _client, _settings, _payload, _customer, _subscription, plan_key: called.setdefault(
            "plan_key", plan_key
        ),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    payload = {
        "id": "sub",
        "customer": "cus",
        "metadata": {
            "category_ids": "[]",
            "plan_key": "business",
            "pending_plan_key": "starter",
            "pending_effective_at": "1700000000",
        },
        "current_period_start": 1690000000,
        "current_period_end": 1702600000,
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "status": "active",
    }

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    stripe_webhook_service._handle_subscription_updated(DummySession(), settings, payload)
    assert called == {}


def test_handle_subscription_updated_applies_pending_when_no_effective_date(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub",
        stripe_customer_id="cus",
        stripe_cancel_at=None,
        stripe_subscription_status="active",
    )
    called = {}

    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_subscriptions_from_categories",
        lambda _session, _client, category_ids: called.setdefault("categories", category_ids),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_stripe_fields",
        lambda _client, _settings, _payload, _customer, _subscription, plan_key: called.setdefault(
            "plan_key", plan_key
        ),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    pending_category_id = uuid4()
    payload = {
        "id": "sub",
        "customer": "cus",
        "metadata": {
            "category_ids": "[]",
            "plan_key": "business",
            "pending_plan_key": "starter",
            "pending_category_ids": f"[\"{pending_category_id}\"]",
        },
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "status": "active",
    }

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    stripe_webhook_service._handle_subscription_updated(DummySession(), settings, payload)
    assert called.get("plan_key") == "starter"
    assert called.get("categories") == [pending_category_id]


def test_handle_invoice_payment_succeeded_sends_upgrade_email(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(stripe_customer_id="cus_123", stripe_subscription_id="sub_123", recipients=[])
    sent = {}

    monkeypatch.setattr(
        stripe_webhook_service,
        "retrieve_subscription",
        lambda settings, subscription_id: {
            "metadata": {"pending_upgrade_email": "1", "contact_email": "client@example.com"}
        },
    )
    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_webhook_service,
        "_send_subscription_update_email",
        lambda **kwargs: sent.setdefault("email", kwargs),
    )
    monkeypatch.setattr(
        stripe_webhook_service.stripe,
        "Subscription",
        SimpleNamespace(modify=lambda *args, **kwargs: sent.setdefault("cleared", True)),
    )

    payload = {
        "subscription": "sub_123",
        "customer": "cus_123",
        "customer_email": "client@example.com",
    }

    stripe_webhook_service._handle_invoice_payment_succeeded(SimpleNamespace(), settings, payload)

    assert sent.get("email") is not None
    assert sent.get("cleared") is True


def test_handle_invoice_payment_succeeded_applies_pending_downgrade(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        recipients=[],
    )
    called = {}

    subscription_payload = {
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "current_period_start": 1700000000,
        "metadata": {
            "plan_key": "business",
            "pending_plan_key": "starter",
            "pending_category_ids": f"[\"{uuid4()}\"]",
            "pending_effective_at": "1700000000",
        },
    }

    monkeypatch.setattr(
        stripe_webhook_service,
        "retrieve_subscription",
        lambda settings, subscription_id: subscription_payload,
    )
    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: called.setdefault("apply", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_stripe_fields",
        lambda _client, _settings, _payload, _customer, _subscription, plan_key: called.setdefault(
            "plan_key", plan_key
        ),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "upsert_subscription_history",
        lambda *args, **kwargs: called.setdefault("history", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service.stripe,
        "Subscription",
        SimpleNamespace(modify=lambda *args, **kwargs: called.setdefault("cleared", True)),
    )

    payload = {
        "subscription": "sub_123",
        "customer": "cus_123",
        "customer_email": "client@example.com",
    }

    stripe_webhook_service._handle_invoice_payment_succeeded(SimpleNamespace(flush=lambda: None), settings, payload)

    assert called.get("apply") is True
    assert called.get("plan_key") == "starter"
    assert called.get("history") is True
    assert called.get("cleared") is True


def test_handle_invoice_payment_succeeded_pending_downgrade_not_ready(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        recipients=[],
    )
    called = {}

    subscription_payload = {
        "items": {"data": [{"price": {"id": "price_business"}}]},
        "current_period_start": 1690000000,
        "metadata": {
            "plan_key": "business",
            "pending_plan_key": "starter",
            "pending_category_ids": f"[\"{uuid4()}\"]",
            "pending_effective_at": "1700000000",
        },
    }

    monkeypatch.setattr(
        stripe_webhook_service,
        "retrieve_subscription",
        lambda settings, subscription_id: subscription_payload,
    )
    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_subscriptions_from_categories",
        lambda *args, **kwargs: called.setdefault("apply", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_stripe_fields",
        lambda *args, **kwargs: called.setdefault("apply_fields", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "upsert_subscription_history",
        lambda *args, **kwargs: called.setdefault("history", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service.stripe,
        "Subscription",
        SimpleNamespace(modify=lambda *args, **kwargs: called.setdefault("cleared", True)),
    )

    payload = {
        "subscription": "sub_123",
        "customer": "cus_123",
        "customer_email": "client@example.com",
    }

    stripe_webhook_service._handle_invoice_payment_succeeded(SimpleNamespace(flush=lambda: None), settings, payload)

    assert called == {}


def test_handle_stripe_webhook_dispatches_invoice_payment(monkeypatch):
    settings = _settings()
    called = {}

    monkeypatch.setattr(stripe_webhook_service, "ensure_stripe_configured", lambda settings: settings.stripe)
    monkeypatch.setattr(
        stripe_webhook_service,
        "_handle_invoice_payment_succeeded",
        lambda *args, **kwargs: called.setdefault("ok", True),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    event = {
        "type": "invoice.payment_succeeded",
        "data": {"object": {}},
    }

    stripe_webhook_service.handle_stripe_webhook(SimpleNamespace(), settings, event)

    assert called.get("ok") is True


def test_handle_stripe_webhook_dispatches_checkout_completed(monkeypatch):
    settings = _settings()
    called = {}

    monkeypatch.setattr(stripe_webhook_service, "ensure_stripe_configured", lambda settings: settings.stripe)
    monkeypatch.setattr(
        stripe_webhook_service,
        "_handle_checkout_completed",
        lambda *args, **kwargs: called.setdefault("checkout", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "notify_admins_of_stripe_event",
        lambda *args, **kwargs: called.setdefault("notify", True),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {}},
    }

    stripe_webhook_service.handle_stripe_webhook(SimpleNamespace(), settings, event)

    assert called.get("checkout") is True
    assert called.get("notify") is True


def test_handle_stripe_webhook_dispatches_subscription_updated(monkeypatch):
    settings = _settings()
    called = {}

    monkeypatch.setattr(stripe_webhook_service, "ensure_stripe_configured", lambda settings: settings.stripe)
    monkeypatch.setattr(
        stripe_webhook_service,
        "_handle_subscription_updated",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "notify_admins_of_stripe_event",
        lambda *args, **kwargs: called.setdefault("notify", True),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    event = {
        "type": "customer.subscription.updated",
        "data": {"object": {}},
    }

    stripe_webhook_service.handle_stripe_webhook(SimpleNamespace(), settings, event)

    assert called.get("notify") is True


def test_send_post_purchase_email_uses_portal_url(monkeypatch):
    settings = _settings()
    sent = {}

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, *, html_body=None, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["html"] = html_body
            sent["recipients"] = recipients

    class DummyPortalSession:
        url = "https://portal.example.com"

    class DummyPortal:
        @staticmethod
        def create(**_kwargs):
            return DummyPortalSession()

    monkeypatch.setattr(stripe_webhook_service, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_webhook_service.stripe, "billing_portal", SimpleNamespace(Session=DummyPortal))

    stripe_webhook_service._send_post_purchase_email(settings, "cus_123", "sub_123", "ops@example.com")

    assert "https://portal.example.com" in (sent.get("body") or "")
    assert sent.get("recipients") == ["ops@example.com"]


def test_send_post_purchase_email_handles_portal_error(monkeypatch):
    settings = _settings()
    sent = {}

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, *, html_body=None, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["html"] = html_body
            sent["recipients"] = recipients

    class DummyPortal:
        @staticmethod
        def create(**_kwargs):
            raise stripe_webhook_service.stripe.error.StripeError("boom")

    monkeypatch.setattr(stripe_webhook_service, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_webhook_service.stripe, "billing_portal", SimpleNamespace(Session=DummyPortal))

    stripe_webhook_service._send_post_purchase_email(settings, "cus_123", "sub_123", "ops@example.com")

    assert "Accès via l'espace de gestion Business Tracker" in (sent.get("body") or "")


def test_handle_stripe_webhook_dispatches_subscription_deleted(monkeypatch):
    settings = _settings()
    called = {}

    monkeypatch.setattr(stripe_webhook_service, "ensure_stripe_configured", lambda settings: settings.stripe)
    monkeypatch.setattr(
        stripe_webhook_service,
        "_handle_subscription_deleted",
        lambda *args, **kwargs: called.setdefault("deleted", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "notify_admins_of_stripe_event",
        lambda *args, **kwargs: called.setdefault("notify", True),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {}},
    }

    stripe_webhook_service.handle_stripe_webhook(SimpleNamespace(), settings, event)

    assert called.get("deleted") is True
    assert called.get("notify") is True


def test_handle_invoice_payment_succeeded_skips_without_pending(monkeypatch):
    settings = _settings()

    monkeypatch.setattr(
        stripe_webhook_service,
        "retrieve_subscription",
        lambda settings, subscription_id: {"metadata": {}},
    )
    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: SimpleNamespace())

    payload = {
        "subscription": "sub_123",
        "customer": "cus_123",
        "customer_email": "client@example.com",
    }

    stripe_webhook_service._handle_invoice_payment_succeeded(SimpleNamespace(), settings, payload)


def test_handle_invoice_payment_succeeded_skips_without_subscription_id():
    settings = _settings()
    stripe_webhook_service._handle_invoice_payment_succeeded(SimpleNamespace(), settings, {})


def test_handle_invoice_payment_succeeded_skips_when_subscription_missing(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(stripe_webhook_service, "retrieve_subscription", lambda *args, **kwargs: None)

    payload = {
        "subscription": "sub_123",
        "customer": "cus_123",
    }

    stripe_webhook_service._handle_invoice_payment_succeeded(SimpleNamespace(), settings, payload)


def test_handle_subscription_updated_pending_downgrade_applies_on_renewal(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub",
        stripe_customer_id="cus",
        stripe_cancel_at=None,
        stripe_subscription_status="active",
    )
    called = {}

    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_subscriptions_from_categories",
        lambda _session, _client, category_ids: called.setdefault("categories", category_ids),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_stripe_fields",
        lambda _client, _settings, _payload, _customer, _subscription, plan_key: called.setdefault(
            "plan_key", plan_key
        ),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    captured = {}

    class DummySubscription:
        @staticmethod
        def modify(_subscription_id, **_kwargs):
            captured.update(_kwargs)
            return {}

    monkeypatch.setattr(stripe_webhook_service.stripe, "Subscription", DummySubscription)

    pending_category_id = uuid4()
    payload = {
        "id": "sub",
        "customer": "cus",
        "metadata": {
            "category_ids": "[]",
            "plan_key": "business",
            "pending_plan_key": "starter",
            "pending_category_ids": f"[\"{pending_category_id}\"]",
            "pending_effective_at": "1700000000",
        },
        "current_period_start": 1700000000,
        "current_period_end": 1702600000,
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "status": "active",
    }

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    stripe_webhook_service._handle_subscription_updated(DummySession(), settings, payload)
    assert called.get("plan_key") == "starter"
    assert called.get("categories") == [pending_category_id]
    assert captured.get("metadata", {}).get("pending_plan_key") is None


def test_handle_subscription_updated_uses_actual_plan_key(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(
        id=uuid4(),
        stripe_subscription_id="sub",
        stripe_customer_id="cus",
        stripe_cancel_at=None,
        stripe_subscription_status="active",
    )
    called = {}

    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(stripe_webhook_service, "apply_subscriptions_from_categories", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        stripe_webhook_service,
        "apply_stripe_fields",
        lambda _client, _settings, _payload, _customer, _subscription, plan_key: called.setdefault(
            "plan_key", plan_key
        ),
    )
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    payload = {
        "id": "sub",
        "customer": "cus",
        "metadata": {
            "category_ids": "[]",
            "plan_key": "business",
            "pending_plan_key": "starter",
            "pending_effective_at": "1690000000",
        },
        "current_period_start": 1700000000,
        "current_period_end": 1702600000,
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "status": "active",
    }

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    stripe_webhook_service._handle_subscription_updated(DummySession(), settings, payload)
    assert called.get("plan_key") == "starter"


def test_handle_subscription_deleted_sets_end_date(monkeypatch):
    settings = _settings()
    client = SimpleNamespace(id=uuid4(), stripe_subscription_id="sub", stripe_customer_id="cus")

    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(stripe_webhook_service, "log_event", lambda *args, **kwargs: None)

    payload = {
        "id": "sub",
        "customer": "cus",
        "ended_at": 1700000000,
        "items": {"data": [{"price": {"id": "price_starter"}}]},
        "status": "canceled",
    }

    class DummySession:
        def execute(self, stmt):
            return _FakeResult(None)

        def add(self, obj):
            return None

        def flush(self):
            return None

    stripe_webhook_service._handle_subscription_deleted(DummySession(), settings, payload)
    assert client.end_date == date.fromtimestamp(1700000000)


def test_handle_subscription_updated_returns_when_client_missing(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: None)
    stripe_webhook_service._handle_subscription_updated(SimpleNamespace(), settings, {"id": "sub", "customer": "cus"})


def test_handle_subscription_deleted_returns_when_client_missing(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(stripe_webhook_service, "find_client", lambda *args, **kwargs: None)
    stripe_webhook_service._handle_subscription_deleted(SimpleNamespace(), settings, {"id": "sub", "customer": "cus"})


def test_handle_stripe_webhook_dispatches(monkeypatch):
    settings = _settings()
    called = {}
    monkeypatch.setattr(
        stripe_webhook_service,
        "_handle_checkout_completed",
        lambda *args, **kwargs: called.setdefault("checkout", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "_handle_subscription_updated",
        lambda *args, **kwargs: called.setdefault("updated", True),
    )
    monkeypatch.setattr(
        stripe_webhook_service,
        "_handle_subscription_deleted",
        lambda *args, **kwargs: called.setdefault("deleted", True),
    )
    monkeypatch.setattr(stripe_webhook_service, "notify_admins_of_stripe_event", lambda *args, **kwargs: None)

    stripe_webhook_service.handle_stripe_webhook(
        SimpleNamespace(),
        settings,
        {"type": "checkout.session.completed", "data": {"object": {}}},
    )
    stripe_webhook_service.handle_stripe_webhook(
        SimpleNamespace(),
        settings,
        {"type": "customer.subscription.updated", "data": {"object": {}}},
    )
    stripe_webhook_service.handle_stripe_webhook(
        SimpleNamespace(),
        settings,
        {"type": "customer.subscription.deleted", "data": {"object": {}}},
    )

    assert called == {"checkout": True, "updated": True, "deleted": True}


def test_send_post_purchase_email_sends_message(monkeypatch):
    settings = _settings()
    sent = {}

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
            sent["subject"] = subject
            sent["body"] = body
            sent["html"] = html_body
            sent["recipients"] = recipients

    class DummyPortalSession:
        url = "https://portal.example.com"

    class DummyPortal:
        @staticmethod
        def create(**_kwargs):
            return DummyPortalSession()

    monkeypatch.setattr(stripe_webhook_service, "EmailService", DummyEmail)
    monkeypatch.setattr(stripe_webhook_service.stripe, "billing_portal", SimpleNamespace(Session=DummyPortal))

    stripe_webhook_service._send_post_purchase_email(settings, "cus_123", "sub_123", "ops@example.com")

    assert "Votre abonnement" in sent.get("subject", "")
    assert sent.get("recipients") == ["ops@example.com"]


def test_send_post_purchase_email_skips_without_email(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(
        stripe_webhook_service,
        "EmailService",
        lambda: SimpleNamespace(is_enabled=lambda: True, is_configured=lambda: True, send=lambda *args, **kwargs: None),
    )
    stripe_webhook_service._send_post_purchase_email(settings, "cus_123", "sub_123", None)


def test_send_post_purchase_email_skips_when_disabled(monkeypatch):
    settings = _settings()

    class DummyEmail:
        def is_enabled(self):
            return False

        def is_configured(self):
            return False

    monkeypatch.setattr(stripe_webhook_service, "EmailService", DummyEmail)
    stripe_webhook_service._send_post_purchase_email(settings, "cus_123", "sub_123", "ops@example.com")


def test_send_post_purchase_email_without_portal_urls(monkeypatch):
    settings = _settings()
    settings.stripe.upgrade_url = None
    sent = {}

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
            sent["body"] = body

    class DummyPortal:
        @staticmethod
        def create(**_kwargs):
            raise stripe_webhook_service.stripe.error.StripeError("boom")

    monkeypatch.setattr(stripe_webhook_service, "EmailService", DummyEmail)
    monkeypatch.setattr(stripe_webhook_service.stripe, "billing_portal", SimpleNamespace(Session=DummyPortal))

    stripe_webhook_service._send_post_purchase_email(settings, "cus_123", "sub_123", "ops@example.com")

    assert "Accès via l'espace de gestion" in sent.get("body", "")


def test_apply_stripe_fields_returns_when_subscription_none():
    settings = _settings()
    client = SimpleNamespace(stripe_customer_id=None, stripe_subscription_id=None)
    stripe_subscription_utils.apply_stripe_fields(client, settings, None, "cus", "sub", None)
    assert client.stripe_customer_id == "cus"
    assert client.stripe_subscription_id == "sub"


def test_retrieve_subscription_handles_missing_id():
    settings = _settings()
    assert stripe_subscription_utils.retrieve_subscription(settings, None) is None


def test_retrieve_subscription_returns_payload(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(
        stripe_subscription_utils.stripe,
        "Subscription",
        SimpleNamespace(retrieve=lambda sub_id: {"id": sub_id}),
    )
    result = stripe_subscription_utils.retrieve_subscription(settings, "sub_123")
    assert result == {"id": "sub_123"}


def test_ensure_recipient_skips_duplicate():
    recipient = models.ClientRecipient(email="ops@example.com")
    client = SimpleNamespace(recipients=[recipient])
    stripe_subscription_utils.ensure_recipient(client, "ops@example.com")
    assert client.recipients == [recipient]
