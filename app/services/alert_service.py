"""Persist alerts and notify stakeholders."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.email_service import EmailService
from app.observability import log_event
from app.services.client_service import collect_client_emails, dispatch_email_to_clients, get_active_clients

_ALERT_LOGGER = logging.getLogger("alerts")


class AlertService:
    """Create alert records and dispatch notifications."""

    def __init__(self, session: Session, run: models.SyncRun) -> None:
        self._session = session
        self._run = run
        self._email_service = EmailService()

    def create_google_alerts(self, establishments: Sequence[models.Establishment]) -> list[models.Alert]:
        if not establishments:
            return []

        alerts: list[models.Alert] = []
        for establishment in establishments:
            payload = self._build_payload(establishment)
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

        message_lines = [
            "Pages Google My Business associées détectées:",
            "",
        ]
        for establishment in establishments:
            message_lines.extend(self._format_lines(establishment, include_google=True))
            message_lines.append("")

        message = "\n".join(message_lines).strip()
        _ALERT_LOGGER.info(message)

        email_enabled = self._email_service.is_enabled()
        email_configured = self._email_service.is_configured()
        has_previous_success = self._has_previous_successful_run()
        active_clients = get_active_clients(self._session)
        eligible_clients = [client for client in active_clients if any(recipient.email for recipient in client.recipients)]

        all_recipient_addresses = collect_client_emails(eligible_clients)
        for alert in alerts:
            alert.recipients = all_recipient_addresses

        if not email_enabled:
            reason = "email_disabled"
        elif not email_configured:
            reason = "email_not_configured"
        elif not has_previous_success:
            reason = "initial_sync"
        elif not active_clients:
            reason = "no_clients"
        elif not eligible_clients:
            reason = "no_active_recipients"
        else:
            subject = f"[{self._run.scope_key}] {len(establishments)} page(s) Google My Business détectée(s)"
            dispatch_result = dispatch_email_to_clients(self._email_service, eligible_clients, subject, message)

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
                    recipient_count=len(all_recipient_addresses),
                    clients=[str(client.id) for client in dispatch_result.delivered],
                    failures=[
                        {"client_id": str(client.id), "error": str(exc)}
                        for client, exc in dispatch_result.failed
                    ],
                )
                return alerts

            for client, exc in dispatch_result.failed:
                _ALERT_LOGGER.warning("Échec de l'envoi pour le client %s: %s", client.name, exc)
                log_event(
                    "alerts.email.error",
                    run_id=str(self._run.id),
                    scope_key=self._run.scope_key,
                    client_id=str(client.id),
                    error={"type": type(exc).__name__, "message": str(exc)},
                )

            reason = "send_error"
            log_event(
                "alerts.email.skipped",
                run_id=str(self._run.id),
                scope_key=self._run.scope_key,
                reason=reason,
                recipient_count=len(all_recipient_addresses),
                failures=[
                    {"client_id": str(client.id), "error": str(exc)}
                    for client, exc in dispatch_result.failed
                ],
            )
            return alerts

        log_event(
            "alerts.email.skipped",
            run_id=str(self._run.id),
            scope_key=self._run.scope_key,
            reason=reason,
            recipient_count=len(all_recipient_addresses),
        )
        return alerts

    def _build_payload(self, establishment: models.Establishment) -> dict[str, object]:
        return {
            "siret": establishment.siret,
            "siren": establishment.siren,
            "name": establishment.name,
            "naf_code": establishment.naf_code,
            "naf_libelle": establishment.naf_libelle,
            "date_creation": establishment.date_creation.isoformat() if establishment.date_creation else None,
            "adresse": {
                "numero_voie": establishment.numero_voie,
                "type_voie": establishment.type_voie,
                "libelle_voie": establishment.libelle_voie,
                "complement": establishment.complement_adresse,
                "code_postal": establishment.code_postal,
                "commune": establishment.libelle_commune,
                "code_commune": establishment.code_commune,
                "code_pays": establishment.code_pays,
                "libelle_pays": establishment.libelle_pays,
            },
            "date_dernier_traitement_etablissement": establishment.date_dernier_traitement_etablissement.isoformat()
            if establishment.date_dernier_traitement_etablissement
            else None,
        }

    def _format_lines(self, establishment: models.Establishment, *, include_google: bool = False) -> list[str]:
        lines = [
            f"- {establishment.name or '(nom indisponible)'}",
            f"  SIRET: {establishment.siret} | NAF: {establishment.naf_code or 'N/A'}",
        ]
        address_parts = [
            element
            for element in [
                establishment.numero_voie,
                establishment.type_voie,
                establishment.libelle_voie,
            ]
            if element
        ]
        commune_parts = [
            part
            for part in [
                establishment.code_postal,
                establishment.libelle_commune or establishment.libelle_commune_etranger,
            ]
            if part
        ]
        lines.append(f"  Adresse: {' '.join(address_parts)}")
        lines.append(f"           {' '.join(commune_parts)}")
        if establishment.date_creation:
            lines.append(f"  Création: {establishment.date_creation.isoformat()}")
        if include_google and establishment.google_place_url:
            lines.append(f"  Google: {establishment.google_place_url}")
        return lines

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
