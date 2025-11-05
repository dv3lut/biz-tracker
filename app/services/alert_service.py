"""Persist alerts and notify stakeholders."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Sequence

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import models
from app.services.email_service import EmailService

_ALERT_LOGGER = logging.getLogger("alerts")


class AlertService:
    """Create alert records and dispatch notifications."""

    def __init__(self, session: Session, run: models.SyncRun) -> None:
        self._session = session
        self._run = run
        self._settings = get_settings().email
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
                recipients=self._settings.recipients,
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

        if self._settings.recipients:
            subject = f"[{self._run.scope_key}] {len(establishments)} page(s) Google My Business détectée(s)"
            self._email_service.send(subject, message, self._settings.recipients)
            sent_at = datetime.utcnow()
            for alert in alerts:
                alert.sent_at = sent_at
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
