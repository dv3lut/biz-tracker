"""Weekly Stripe reporting utilities for admins."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import models
from app.observability import log_event
from app.services.client_service import get_admin_emails
from app.services.email_service import EmailService
from app.utils.dates import utcnow

WEEKLY_SUMMARY_WEEKDAY = 0  # Monday
WEEKLY_SUMMARY_HOUR = 8
SUMMARY_LOOKAHEAD_DAYS = 7


def send_weekly_stripe_summary_if_due(session: Session, settings: Settings) -> bool:
    if not _is_weekly_summary_due(session):
        return False

    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        return False

    recipients = get_admin_emails(session)
    if not recipients:
        return False

    summary = _build_weekly_summary(session)
    email_service.send(
        subject="[Stripe] Récap hebdo abonnements",
        body=summary,
        recipients=recipients,
    )

    settings_row = _get_billing_settings(session)
    settings_row.last_weekly_summary_at = utcnow()
    session.flush()

    log_event("stripe.weekly_summary.sent", recipients=len(recipients))
    return True


def _is_weekly_summary_due(session: Session) -> bool:
    now = utcnow()
    if now.weekday() != WEEKLY_SUMMARY_WEEKDAY or now.hour < WEEKLY_SUMMARY_HOUR:
        return False
    settings = _get_billing_settings(session)
    last_sent = settings.last_weekly_summary_at
    if not last_sent:
        return True
    return last_sent.date() < now.date()


def _get_billing_settings(session: Session) -> models.StripeBillingSettings:
    settings = session.execute(select(models.StripeBillingSettings)).scalar_one_or_none()
    if settings is None:
        settings = models.StripeBillingSettings(trial_period_days=14)
        session.add(settings)
        session.flush()
    return settings


def _build_weekly_summary(session: Session) -> str:
    now = utcnow()
    horizon = now + timedelta(days=SUMMARY_LOOKAHEAD_DAYS)

    subscriptions = session.execute(select(models.ClientStripeSubscription)).scalars().all()
    total = len(subscriptions)

    status_counts: dict[str, int] = {}
    for sub in subscriptions:
        status = sub.status or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    upcoming_payments = [
        sub
        for sub in subscriptions
        if sub.current_period_end
        and now <= sub.current_period_end <= horizon
        and (sub.status in {"active", "trialing"})
    ]

    upcoming_trials = [
        sub
        for sub in subscriptions
        if sub.trial_end_at and now <= sub.trial_end_at <= horizon
    ]

    lines = [
        "Récapitulatif Stripe (hebdomadaire)",
        "",
        f"Abonnements suivis: {total}",
        "Statuts:",
    ]

    for status, count in sorted(status_counts.items(), key=lambda item: item[0]):
        lines.append(f"- {status}: {count}")

    lines.append("")
    lines.append(f"Paiements à venir (<= {SUMMARY_LOOKAHEAD_DAYS} jours): {len(upcoming_payments)}")
    for sub in _limit_items(upcoming_payments, 10):
        client_label = _client_label(session, sub.client_id)
        lines.append(
            f"- {client_label} · {sub.plan_key or 'plan?'} · fin période {sub.current_period_end:%Y-%m-%d}"
        )

    lines.append("")
    lines.append(f"Fins d'essai à venir (<= {SUMMARY_LOOKAHEAD_DAYS} jours): {len(upcoming_trials)}")
    for sub in _limit_items(upcoming_trials, 10):
        client_label = _client_label(session, sub.client_id)
        lines.append(
            f"- {client_label} · {sub.plan_key or 'plan?'} · fin essai {sub.trial_end_at:%Y-%m-%d}"
        )

    lines.append("")
    lines.append("Astuce: consultez le tableau Clients pour le détail des dates d'achat et de démarrage payant.")

    return "\n".join(lines)


def _client_label(session: Session, client_id) -> str:
    client = session.get(models.Client, client_id)
    if not client:
        return "Client inconnu"
    return f"{client.name}"


def _limit_items(items: Iterable[models.ClientStripeSubscription], limit: int) -> list[models.ClientStripeSubscription]:
    return list(items)[:limit]
