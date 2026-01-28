"""Persist alerts and notify stakeholders."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Mapping, Sequence
from uuid import UUID

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
    summarize_client_filters,
)
from app.services.email_service import EmailService
from app.services.export_service import build_alerts_client_csv, build_alerts_csv
from app.utils.dates import utcnow

_ALERT_LOGGER = logging.getLogger("alerts")


def _sanitize_filename_token(value: object | None) -> str:
    token = str(value or "").strip()
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", token)
    return token.strip("_-") or "export"


class AlertService:
    """Create alert records and dispatch notifications."""

    def __init__(
        self,
        session: Session,
        run: models.SyncRun,
        *,
        client_notifications_enabled: bool = True,
        admin_notifications_enabled: bool = True,
        target_client_ids: Sequence[UUID] | None = None,
    ) -> None:
        self._session = session
        self._run = run
        self._email_service = EmailService()
        self._formatter = EstablishmentFormatter(session)
        self._client_notifications_enabled = client_notifications_enabled
        self._admin_notifications_enabled = admin_notifications_enabled
        self._target_client_ids = tuple(str(value) for value in (target_client_ids or []))

    def create_google_alerts(self, establishments: Sequence[models.Establishment]) -> list[models.Alert]:
        filtered_establishments = [
            item for item in establishments if (item.google_check_status or "").lower() == "found"
        ]
        alerts: list[models.Alert] = []
        if filtered_establishments:
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

            alerts_by_siret: dict[str, models.Alert] = {alert.siret: alert for alert in alerts}

            message_lines = ["Pages Google My Business associées détectées:", ""]
            for establishment in filtered_establishments:
                message_lines.extend(self._formatter.format_lines(establishment, include_google=True))
                message_lines.append("")
            _ALERT_LOGGER.info("\n".join(message_lines).strip())
        else:
            _ALERT_LOGGER.info("Aucune fiche Google détectée pour le run %s", self._run.id)
            alerts_by_siret = {}

        email_enabled = self._email_service.is_enabled()
        email_configured = self._email_service.is_configured()
        has_previous_success = self._has_previous_successful_run()
        admin_recipients = get_admin_emails(self._session) if self._admin_notifications_enabled else []

        if self._client_notifications_enabled:
            plan, client_skip_reason = self._prepare_client_dispatch(
                filtered_establishments,
                alerts_by_siret,
                admin_recipients,
                email_enabled=email_enabled,
                email_configured=email_configured,
                has_previous_success=has_previous_success,
                target_client_ids=self._target_client_ids,
            )
        else:
            plan = None
            client_skip_reason = "client_notifications_disabled"
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

        if filtered_establishments and self._admin_notifications_enabled:
            count = len(filtered_establishments)
            fiche_plural = "fiches" if count > 1 else "fiche"
            base_client_subject = (
                f"Business tracker · {count} {fiche_plural} Google détectée{'s' if count > 1 else ''}"
            )
            admin_subject = f"{base_client_subject} - administration"
            admin_text_body, admin_html_body = render_admin_email(self._formatter, filtered_establishments)

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
                    establishments_by_siret = {item.siret: item for item in filtered_establishments}
                    attachments = [
                        (
                            f"biz-tracker-alertes-{_sanitize_filename_token(self._run.scope_key)}-{utcnow().date().isoformat()}.csv",
                            build_alerts_csv(
                                alerts,
                                establishments_by_siret=establishments_by_siret,
                                scope_key=self._run.scope_key,
                            ),
                            "text/csv",
                        )
                    ]
                    self._email_service.send(
                        admin_subject,
                        admin_text_body,
                        admin_recipients,
                        html_body=admin_html_body,
                        attachments=attachments,
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
                    admin_sent_at = utcnow()
                    for alert in alerts:
                        if alert.sent_at is None:
                            alert.sent_at = admin_sent_at
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

        return alerts

    def _prepare_client_dispatch(
        self,
        establishments: Sequence[models.Establishment],
        alerts_by_siret: Mapping[str, models.Alert],
        admin_recipients: Sequence[str],
        *,
        email_enabled: bool,
        email_configured: bool,
        has_previous_success: bool,
        target_client_ids: Sequence[str] | None = None,
    ) -> tuple[ClientDispatchPlan | None, str | None]:
        if not email_enabled:
            return None, "email_disabled"

        if not email_configured:
            return None, "email_not_configured"

        if not has_previous_success:
            return None, "initial_sync"

        clients = get_active_clients(self._session)
        if target_client_ids:
            target_ids = {str(value) for value in target_client_ids}
            clients = [client for client in clients if str(client.id) in target_ids]
            if not clients:
                return None, "no_targeted_clients"
        if not clients:
            return None, "no_clients"

        has_recipients = any(
            recipient.email
            for client in clients
            for recipient in client.recipients
        )
        if not has_recipients:
            return None, "no_active_recipients"

        assignments: dict[object, list[models.Establishment]] = {}
        filters_configured = False
        if establishments:
            assignments, filters_configured = assign_establishments_to_clients(clients, establishments)
            if not assignments:
                if filters_configured and not target_client_ids:
                    return None, "no_matching_filters"
                if not filters_configured and not target_client_ids:
                    return None, "no_assignments"
        else:
            assignments = {client.id: [] for client in clients}

        payloads: list[ClientEmailPayload] = []
        unique_recipients = set(admin_recipients)
        for client in clients:
            client_establishments = assignments.get(client.id, [])
            client_alerts = [
                alerts_by_siret[item.siret]
                for item in client_establishments
                if item.siret in alerts_by_siret
            ]
            subject = self._build_client_subject(len(client_establishments))
            filters = summarize_client_filters(client)
            text_body, html_body = render_client_email(
                self._formatter,
                client_establishments,
                filters=filters,
            )
            payloads.append(
                ClientEmailPayload(
                    client=client,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                    establishments=client_establishments,
                    filters=filters,
                    attachments=[
                        (
                            f"biz-tracker-alertes-{_sanitize_filename_token(client.name)}-{utcnow().date().isoformat()}.csv",
                            build_alerts_client_csv(
                                client_alerts,
                                establishments_by_siret={
                                    item.siret: item for item in client_establishments if getattr(item, "siret", None)
                                },
                            ),
                            "text/csv",
                        )
                    ],
                )
            )
            for recipient in client.recipients:
                if recipient.email:
                    unique_recipients.add(recipient.email)

        if not payloads:
            return None, "no_payloads"

        targeted_recipient_addresses = collect_client_emails(clients)
        combined_recipient_addresses = sorted(unique_recipients)
        return (
            ClientDispatchPlan(
                client_payloads=payloads,
                targeted_clients=[payload.client for payload in payloads],
                targeted_recipient_addresses=targeted_recipient_addresses,
                combined_recipient_addresses=combined_recipient_addresses,
            ),
            None,
        )

    @staticmethod
    def _build_client_subject(match_count: int) -> str:
        fiche_plural = "fiches" if match_count > 1 else "fiche"
        suffix = "s" if match_count > 1 else ""
        return f"Business tracker · {match_count} {fiche_plural} Google détectée{suffix}"

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
