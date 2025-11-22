"""Persist alerts and notify stakeholders."""
from __future__ import annotations

import logging
from datetime import datetime
from html import escape
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.email_service import EmailService
from app.observability import log_event
from app.services.client_service import (
    ClientEmailPayload,
    assign_establishments_to_clients,
    collect_client_emails,
    dispatch_email_to_clients,
    get_active_clients,
    get_admin_emails,
)
from app.utils.google_listing import describe_listing_age_status
from app.utils.urls import build_annuaire_etablissement_url

_ALERT_LOGGER = logging.getLogger("alerts")


class AlertService:
    """Create alert records and dispatch notifications."""

    def __init__(self, session: Session, run: models.SyncRun) -> None:
        self._session = session
        self._run = run
        self._email_service = EmailService()
        self._subcategory_lookup: dict[str, tuple[str | None, str | None]] | None = None

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

        base_client_subject = f"[{self._run.scope_key}] {len(establishments)} fiche(s) Google détectée(s)"
        admin_subject = f"{base_client_subject} - administration"
        admin_text_body, admin_html_body = self._render_admin_email(establishments)

        email_enabled = self._email_service.is_enabled()
        email_configured = self._email_service.is_configured()
        has_previous_success = self._has_previous_successful_run()
        active_clients = get_active_clients(self._session)
        eligible_clients = [client for client in active_clients if any(recipient.email for recipient in client.recipients)]
        admin_recipients = get_admin_emails(self._session)

        assignment_map, filtering_applied = assign_establishments_to_clients(eligible_clients, establishments)
        client_payloads: list[ClientEmailPayload] = []
        for client in eligible_clients:
            matches = assignment_map.get(client.id, [])
            if not matches and not filtering_applied:
                matches = list(establishments)
            if not matches:
                continue
            subject = f"[{self._run.scope_key}] {len(matches)} fiche(s) Google détectée(s)"
            text_body, html_body = self._render_client_email(matches)
            client_payloads.append(
                ClientEmailPayload(
                    client=client,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                    establishments=matches,
                )
            )

        targeted_clients = [payload.client for payload in client_payloads]
        targeted_recipient_addresses = collect_client_emails(targeted_clients)
        combined_recipient_addresses = sorted({*targeted_recipient_addresses, *admin_recipients})
        for alert in alerts:
            alert.recipients = combined_recipient_addresses

        client_skip_reason: str | None = None
        dispatch_result = None

        if not email_enabled:
            client_skip_reason = "email_disabled"
        elif not email_configured:
            client_skip_reason = "email_not_configured"
        elif not has_previous_success:
            client_skip_reason = "initial_sync"
        elif not active_clients:
            client_skip_reason = "no_clients"
        elif not eligible_clients:
            client_skip_reason = "no_active_recipients"
        elif not client_payloads:
            client_skip_reason = "no_matching_subscriptions" if filtering_applied else "no_active_recipients"
        else:
            dispatch_result = dispatch_email_to_clients(
                self._email_service,
                client_payloads,
            )

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
                if dispatch_result:
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
            except Exception as exc:  # noqa: BLE001 - log and move on
                admin_skip_reason = "send_error"
                _ALERT_LOGGER.warning(
                    "Échec de l'envoi des alertes admin: %s", exc,
                )
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

    def _build_payload(self, establishment: models.Establishment) -> dict[str, object]:
        return {
            "siret": establishment.siret,
            "siren": establishment.siren,
            "name": establishment.name,
            "naf_code": establishment.naf_code,
            "naf_libelle": establishment.naf_libelle,
            "date_creation": establishment.date_creation.isoformat() if establishment.date_creation else None,
            "google_listing_origin_at": establishment.google_listing_origin_at.isoformat()
            if establishment.google_listing_origin_at
            else None,
            "google_listing_age_status": establishment.google_listing_age_status,
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
        siret_display, siret_url = self._get_siret_display_and_url(establishment.siret)
        siret_line = f"  SIRET: {siret_display}"
        if siret_url:
            siret_line += f" ({siret_url})"
        naf_code = establishment.naf_code or "N/A"

        lines = [
            f"- {establishment.name or '(nom indisponible)'}",
            f"{siret_line} | NAF: {naf_code}",
        ]
        subcategory_label = self._format_subcategory_label(establishment.naf_code)
        if subcategory_label:
            lines.append(f"  Catégorie : {subcategory_label}")
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
        if establishment.google_place_url:
            status_label, origin = self._describe_listing_age(establishment)
            if origin:
                lines.append(f"  Statut fiche Google : {status_label} (origine {origin})")
            else:
                lines.append(f"  Statut fiche Google : {status_label}")
        return lines

    def _format_address_lines(self, establishment: models.Establishment) -> tuple[str | None, str | None]:
        street_parts = [
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
        street_line = " ".join(street_parts) or None
        commune_line = " ".join(commune_parts) or None
        return street_line, commune_line

    def _get_siret_display_and_url(self, siret: str | None) -> tuple[str, str | None]:
        siret_display = siret or "N/A"
        return siret_display, build_annuaire_etablissement_url(siret)

    def _describe_listing_age(self, establishment: models.Establishment) -> tuple[str, str | None]:
        label = describe_listing_age_status(establishment.google_listing_age_status)
        origin = (
            establishment.google_listing_origin_at.isoformat() if establishment.google_listing_origin_at else None
        )
        return label, origin

    def _render_client_email(self, establishments: Sequence[models.Establishment]) -> tuple[str, str]:
        lines: list[str] = [
            "Bonjour,",
            "",
            "Nous avons identifié de nouvelles fiches Google My Business pour vos établissements :",
            "",
        ]

        html_parts: list[str] = [
            "<html>",
            "<body style=\"font-family:'Helvetica Neue',Arial,sans-serif;color:#111827;line-height:1.5;\">",
            "<p>Bonjour,</p>",
            "<p>Nous avons identifié de nouvelles fiches Google My Business pour vos établissements :</p>",
            "<ul style=\"padding-left:18px;margin:0;\">",
        ]

        for establishment in establishments:
            name = establishment.name or "(nom indisponible)"
            street_line, commune_line = self._format_address_lines(establishment)
            google_url = establishment.google_place_url
            subcategory_label = self._format_subcategory_label(establishment.naf_code)

            lines.append(f"- {name}")
            if street_line:
                lines.append(f"  {street_line}")
            if commune_line:
                lines.append(f"  {commune_line}")
            if subcategory_label:
                lines.append(f"  Catégorie : {subcategory_label}")
            if google_url:
                lines.append(f"  Fiche Google : {google_url}")
            else:
                lines.append("  Fiche Google : en cours de disponibilité")
            status_label, origin = self._describe_listing_age(establishment)
            if google_url:
                if origin:
                    lines.append(f"  Statut fiche Google : {status_label} (origine {origin})")
                else:
                    lines.append(f"  Statut fiche Google : {status_label}")
            lines.append("")

            item_html = [
                f"<strong>{escape(name)}</strong>",
            ]
            if street_line:
                item_html.append(f"<div>{escape(street_line)}</div>")
            if commune_line:
                item_html.append(f"<div>{escape(commune_line)}</div>")
            if subcategory_label:
                item_html.append(
                    f"<div style=\"color:#93c5fd;\">Sous-catégorie : {escape(subcategory_label)}</div>"
                )
            if google_url:
                link = escape(google_url)
                item_html.append(
                    f"<div><a href=\"{link}\" style=\"color:#2563eb;text-decoration:none;\">Voir la fiche Google</a></div>"
                )
            else:
                item_html.append(
                    "<div style=\"color:#6b7280;\">Lien Google indisponible pour le moment</div>"
                )
            status_label, origin = self._describe_listing_age(establishment)
            status_parts = [f"Statut fiche Google : {escape(status_label)}"]
            if origin:
                status_parts.append(f"<span style=\"color:#9ca3af;\">(origine {escape(origin)})</span>")
            item_html.append(f"<div>{' '.join(status_parts)}</div>")
            html_parts.append(
                "<li style=\"margin-bottom:16px;\">" + "".join(item_html) + "</li>"
            )

        lines.extend([
            "Cordialement,",
            "L'équipe Biz Tracker",
        ])

        html_parts.extend([
            "</ul>",
            "<p style=\"margin-top:24px;\">Cordialement,<br/>L'équipe Biz Tracker</p>",
            "</body>",
            "</html>",
        ])

        text_body = "\n".join(lines).strip()
        html_body = "\n".join(html_parts)
        return text_body, html_body

    def _render_admin_email(self, establishments: Sequence[models.Establishment]) -> tuple[str, str]:
        lines: list[str] = [
            "Bonjour,",
            "",
            "Résumé détaillé des fiches Google détectées :",
            "",
        ]

        html_parts: list[str] = [
            "<html>",
            "<body style=\"font-family:'Helvetica Neue',Arial,sans-serif;color:#111827;line-height:1.5;\">",
            "<p>Bonjour,</p>",
            "<p>Résumé détaillé des fiches Google détectées :</p>",
            "<table style=\"width:100%;border-collapse:collapse;margin-top:8px;\">",
            "<thead>",
            "<tr>",
            "<th style=\"text-align:left;padding:12px;border-bottom:1px solid #e5e7eb;\">Établissement</th>",
            "<th style=\"text-align:left;padding:12px;border-bottom:1px solid #e5e7eb;\">Identifiants</th>",
            "<th style=\"text-align:left;padding:12px;border-bottom:1px solid #e5e7eb;\">Google</th>",
            "</tr>",
            "</thead>",
            "<tbody>",
        ]

        for establishment in establishments:
            lines.extend(self._format_lines(establishment, include_google=True))
            lines.append("")

            name = establishment.name or "(nom indisponible)"
            street_line, commune_line = self._format_address_lines(establishment)
            siret_display, siret_url = self._get_siret_display_and_url(establishment.siret)
            naf_code = establishment.naf_code or "N/A"
            naf_label = establishment.naf_libelle or ""
            creation_date = (
                establishment.date_creation.isoformat() if establishment.date_creation else "N/A"
            )
            google_url = establishment.google_place_url
            google_id = establishment.google_place_id or ""
            subcategory_label = self._format_subcategory_label(establishment.naf_code)

            address_section = [f"<strong>{escape(name)}</strong>"]
            if street_line:
                address_section.append(f"<div>{escape(street_line)}</div>")
            if commune_line:
                address_section.append(f"<div>{escape(commune_line)}</div>")

            if siret_url:
                ident_section = [
                    f"SIRET&nbsp;: <a href=\"{escape(siret_url)}\" style=\"color:#2563eb;text-decoration:none;\">{escape(siret_display)}</a>"
                ]
            else:
                ident_section = [f"SIRET&nbsp;: {escape(siret_display)}"]
            ident_section.append(f"NAF&nbsp;: {escape(naf_code)}")
            if naf_label:
                ident_section.append(escape(naf_label))
            if subcategory_label:
                ident_section.append(f"Catégorie&nbsp;: {escape(subcategory_label)}")
            ident_section.append(f"Création&nbsp;: {escape(creation_date)}")

            google_section: list[str] = []
            if google_url:
                link = escape(google_url)
                google_section.append(
                    f"<a href=\"{link}\" style=\"color:#2563eb;text-decoration:none;\">Ouvrir la fiche</a>"
                )
            else:
                google_section.append("Lien indisponible")
            if google_id:
                google_section.append(f"ID&nbsp;: {escape(google_id)}")
            status_label, origin = self._describe_listing_age(establishment)
            status_line = f"Statut&nbsp;: {escape(status_label)}"
            if origin:
                status_line += f" (origine {escape(origin)})"
            google_section.append(status_line)

            html_parts.append(
                "<tr>"
                + "<td style=\"vertical-align:top;padding:12px;border-bottom:1px solid #f3f4f6;\">"
                + "".join(address_section)
                + "</td>"
                + "<td style=\"vertical-align:top;padding:12px;border-bottom:1px solid #f3f4f6;\">"
                + "<br/>".join(ident_section)
                + "</td>"
                + "<td style=\"vertical-align:top;padding:12px;border-bottom:1px solid #f3f4f6;\">"
                + "<br/>".join(google_section)
                + "</td>"
                + "</tr>"
            )

        lines.extend([
            "Bien à vous,",
            "L'équipe Biz Tracker",
        ])

        html_parts.extend([
            "</tbody>",
            "</table>",
            "<p style=\"margin-top:24px;\">Bien à vous,<br/>L'équipe Biz Tracker</p>",
            "</body>",
            "</html>",
        ])

        text_body = "\n".join(lines).strip()
        html_body = "\n".join(html_parts)
        return text_body, html_body

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

    def _get_subcategory_lookup(self) -> dict[str, tuple[str | None, str | None]]:
        if self._subcategory_lookup is not None:
            return self._subcategory_lookup

        rows = (
            self._session.execute(
                select(
                    models.NafSubCategory.naf_code,
                    models.NafSubCategory.name,
                    models.NafCategory.name,
                )
                .join(models.NafCategory, models.NafCategory.id == models.NafSubCategory.category_id)
                .where(models.NafSubCategory.is_active.is_(True))
            ).all()
        )
        lookup: dict[str, tuple[str | None, str | None]] = {}
        for naf_code, sub_name, category_name in rows:
            if not naf_code:
                continue
            lookup[naf_code.strip().upper()] = (category_name, sub_name)
        self._subcategory_lookup = lookup
        return lookup

    def _resolve_subcategory_info(self, naf_code: str | None) -> tuple[str | None, str | None]:
        if not naf_code:
            return None, None
        key = naf_code.strip().upper()
        if not key:
            return None, None
        lookup = self._get_subcategory_lookup()
        return lookup.get(key, (None, None))

    def _format_subcategory_label(self, naf_code: str | None) -> str | None:
        category_name, subcategory_name = self._resolve_subcategory_info(naf_code)
        if subcategory_name and category_name and category_name != subcategory_name:
            return f"{subcategory_name} ({category_name})"
        return subcategory_name or category_name
