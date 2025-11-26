"""Persist alerts and notify stakeholders."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event
from app.services.alerts.email_renderer import render_admin_email, render_client_email
from app.services.alerts.formatter import EstablishmentFormatter
from app.services.alerts.types import ClientDispatchPlan
from app.services.client_service import (
    ClientEmailPayload,
    assign_establishments_to_clients,
    collect_client_emails,
    dispatch_email_to_clients,
    get_active_clients,
    get_admin_emails,
)
from app.services.email_service import EmailService

_ALERT_LOGGER = logging.getLogger("alerts")


class AlertService:
    """Create alert records and dispatch notifications."""

    def __init__(self, session: Session, run: models.SyncRun) -> None:
        self._session = session
        self._run = run
        self._email_service = EmailService()
        self._formatter = EstablishmentFormatter(session)

    def create_google_alerts(self, establishments: Sequence[models.Establishment]) -> list[models.Alert]:
        if not establishments:
            return []

        filtered_establishments = [
            item for item in establishments if (item.google_check_status or "").lower() == "found"
        ]
        if not filtered_establishments:
            return []

        alerts: list[models.Alert] = []
        for establishment in filtered_establishments:
            payload = self._formatter.build_payload(establishment)
            payload["google_place_url"] = establishment.google_place_url
            payload["google_place_id"] = establishment.google_place_id
            alert = models.Alert(
                run_id=self._run.id,
                siret=establishment.siret,
                recipients=[],
                payload=payload,
            )
            alerts.append(alert)
            self._session.add(alert)

        self._session.flush()

        message_lines = ["Pages Google My Business associées détectées:", ""]
        for establishment in filtered_establishments:
            message_lines.extend(self._formatter.format_lines(establishment, include_google=True))
            message_lines.append("")
        _ALERT_LOGGER.info("\n".join(message_lines).strip())

        base_client_subject = f"[{self._run.scope_key}] {len(filtered_establishments)} fiche(s) Google détectée(s)"
        admin_subject = f"{base_client_subject} - administration"
        admin_text_body, admin_html_body = render_admin_email(self._formatter, filtered_establishments)

        email_enabled = self._email_service.is_enabled()
        email_configured = self._email_service.is_configured()
        has_previous_success = self._has_previous_successful_run()
        admin_recipients = get_admin_emails(self._session)

        plan, client_skip_reason = self._prepare_client_dispatch(
            filtered_establishments,
            admin_recipients,
            email_enabled=email_enabled,
            email_configured=email_configured,
            has_previous_success=has_previous_success,
        )
        targeted_recipient_addresses = plan.targeted_recipient_addresses if plan else []
        combined_recipient_addresses = plan.combined_recipient_addresses if plan else sorted(admin_recipients)
        for alert in alerts:
            alert.recipients = combined_recipient_addresses

        dispatch_result = None
        if plan is not None:
            dispatch_result = dispatch_email_to_clients(self._email_service, plan.client_payloads)
            if dispatch_result.delivered:
                if dispatch_result.sent_at:
                    for alert in alerts:
                        alert.sent_at = dispatch_result.sent_at
                for client, exc in dispatch_result.failed:
                    _ALERT_LOGGER.warning("Échec de l'envoi pour le client %s: %s", client.name, exc)
                    log_event(
                        "alerts.email.error",
                        run_id=str(self._run.id),
                        scope_key=self._run.scope_key,
                        client_id=str(client.id),
                        error={"type": type(exc).__name__, "message": str(exc)},
                    )
                log_event(
                    "alerts.email.sent",
                    run_id=str(self._run.id),
                    scope_key=self._run.scope_key,
                    recipient_count=len(targeted_recipient_addresses),
                    clients=[str(client.id) for client in dispatch_result.delivered],
                    failures=[
                        {"client_id": str(client.id), "error": str(exc)}
                        for client, exc in dispatch_result.failed
                    ],
                )
            else:
                client_skip_reason = "send_error"
                for client, exc in dispatch_result.failed:
                    _ALERT_LOGGER.warning("Échec de l'envoi pour le client %s: %s", client.name, exc)
                    log_event(
                        "alerts.email.error",
                        run_id=str(self._run.id),
                        scope_key=self._run.scope_key,
                        client_id=str(client.id),
                        error={"type": type(exc).__name__, "message": str(exc)},
                    )
                log_event(
                    "alerts.email.skipped",
                    run_id=str(self._run.id),
                    scope_key=self._run.scope_key,
                    reason=client_skip_reason,
                    recipient_count=len(targeted_recipient_addresses),
                    failures=[
                        {"client_id": str(client.id), "error": str(exc)}
                        for client, exc in dispatch_result.failed
                    ],
                )

        if client_skip_reason and client_skip_reason != "send_error":
            log_event(
                "alerts.email.skipped",
                run_id=str(self._run.id),
                scope_key=self._run.scope_key,
                reason=client_skip_reason,
                recipient_count=len(targeted_recipient_addresses),
            )

        admin_skip_reason: str | None = None
        admin_sent_at: datetime | None = None
        if not admin_recipients:
            admin_skip_reason = "no_admin_recipients"
        elif not email_enabled:
            admin_skip_reason = "email_disabled"
        elif not email_configured:
            admin_skip_reason = "email_not_configured"
        else:
            try:
                self._email_service.send(
                    admin_subject,
                    admin_text_body,
                    admin_recipients,
                    html_body=admin_html_body,
                )
            except Exception as exc:  # noqa: BLE001
                admin_skip_reason = "send_error"
                _ALERT_LOGGER.warning("Échec de l'envoi des alertes admin: %s", exc)
                log_event(
                    "alerts.email.admin_error",
                    run_id=str(self._run.id),
                    scope_key=self._run.scope_key,
                    recipients=admin_recipients,
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
            else:
                admin_sent_at = datetime.utcnow()
                log_event(
                    "alerts.email.admin_sent",
                    run_id=str(self._run.id),
                    scope_key=self._run.scope_key,
                    recipient_count=len(admin_recipients),
                    recipients=admin_recipients,
                )

        if admin_skip_reason and admin_skip_reason != "send_error":
            log_event(
                "alerts.email.admin_skipped",
                run_id=str(self._run.id),
                scope_key=self._run.scope_key,
                reason=admin_skip_reason,
                recipient_count=len(admin_recipients),
                recipients=admin_recipients,
            )

        if admin_sent_at:
            for alert in alerts:
                if alert.sent_at is None or alert.sent_at > admin_sent_at:
                    alert.sent_at = admin_sent_at

        return alerts

    def _prepare_client_dispatch(
        self,
        establishments: Sequence[models.Establishment],
        admin_recipients: Sequence[str],
        *,
        email_enabled: bool,
        email_configured: bool,
        has_previous_success: bool,
    ) -> tuple[ClientDispatchPlan | None, str | None]:
        if not email_enabled:
            return None, "email_disabled"
        if not email_configured:
            return None, "email_not_configured"
        if not has_previous_success:
            return None, "initial_sync"

        active_clients = get_active_clients(self._session)
        if not active_clients:
            return None, "no_clients"

        eligible_clients = [client for client in active_clients if any(recipient.email for recipient in client.recipients)]
        if not eligible_clients:
            return None, "no_active_recipients"

        assignment_map, filters_configured = assign_establishments_to_clients(eligible_clients, establishments)
        client_payloads: list[ClientEmailPayload] = []
        for client in eligible_clients:
            matches = assignment_map.get(client.id, [])
            if not matches and not filters_configured:
                matches = list(establishments)
            if not matches:
                continue
            subject = f"[{self._run.scope_key}] {len(matches)} fiche(s) Google détectée(s)"
            text_body, html_body = render_client_email(self._formatter, matches)
            client_payloads.append(
                ClientEmailPayload(
                    client=client,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                    establishments=matches,
                )
            )

        if not client_payloads:
            reason = "no_matching_filters" if filters_configured else "no_active_recipients"
            return None, reason

        targeted_clients = [payload.client for payload in client_payloads]
        targeted_recipient_addresses = collect_client_emails(targeted_clients)
        combined_recipient_addresses = sorted({*targeted_recipient_addresses, *admin_recipients})

        plan = ClientDispatchPlan(
            client_payloads=client_payloads,
            targeted_clients=targeted_clients,
            targeted_recipient_addresses=targeted_recipient_addresses,
            combined_recipient_addresses=combined_recipient_addresses,
        )
        return plan, None

    def _has_previous_successful_run(self) -> bool:
        stmt = (
            select(models.SyncRun.id)
            .where(
                models.SyncRun.scope_key == self._run.scope_key,
                models.SyncRun.status == "success",
                models.SyncRun.id != self._run.id,
            )
            .limit(1)
        )
        return self._session.execute(stmt).first() is not None
