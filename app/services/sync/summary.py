"""Summary and notification helpers for synchronization runs."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event
from app.services.client_service import get_admin_emails
from app.services.email_service import EmailService
from app.services.sync.mode import SyncMode

from .context import SyncResult

_LOGGER = logging.getLogger(__name__)


class SyncSummaryMixin:
    """Provide helpers to build and dispatch run summaries."""

    def _build_run_summary_payload(self, run: models.SyncRun, result: SyncResult) -> dict[str, Any]:
        def summarize_establishment(establishment: models.Establishment) -> dict[str, Any]:
            return {
                "siret": establishment.siret,
                "name": establishment.name,
                "code_postal": establishment.code_postal,
                "libelle_commune": establishment.libelle_commune or establishment.libelle_commune_etranger,
                "naf_code": establishment.naf_code,
                "google_status": establishment.google_check_status,
                "google_place_url": establishment.google_place_url,
                "google_place_id": establishment.google_place_id,
                "google_match_confidence": establishment.google_match_confidence,
                "created_run_id": str(establishment.created_run_id) if establishment.created_run_id else None,
                "first_seen_at": establishment.first_seen_at.isoformat() if establishment.first_seen_at else None,
                "last_seen_at": establishment.last_seen_at.isoformat() if establishment.last_seen_at else None,
            }

        samples = {
            "new_establishments": [summarize_establishment(item) for item in result.new_establishments[:10]],
            "updated_establishments": [],
            "google_late_matches": [summarize_establishment(item) for item in result.google_late_matches[:10]],
            "google_immediate_matches": [summarize_establishment(item) for item in result.google_immediate_matches[:10]],
        }
        for info in result.updated_establishments[:10]:
            payload = summarize_establishment(info.establishment)
            payload["changed_fields"] = list(info.changed_fields)
            samples["updated_establishments"].append(payload)

        summary_stats = {
            "fetched_records": run.fetched_records,
            "created_records": run.created_records,
            "updated_records": run.updated_records,
            "api_call_count": run.api_call_count,
            "google": {
                "queue_count": run.google_queue_count,
                "eligible_count": run.google_eligible_count,
                "matched_count": run.google_matched_count,
                "immediate_matches": run.google_immediate_matched_count,
                "late_matches": run.google_late_matched_count,
                "pending_count": run.google_pending_count,
                "api_call_count": run.google_api_call_count,
            },
            "alerts": {
                "created": len(result.alerts),
                "sent": result.alerts_sent_count,
            },
        }
        summary_stats["mode"] = run.mode
        summary_stats["google"]["enabled"] = run.mode != SyncMode.SIRENE_ONLY

        return {
            "run": {
                "id": str(run.id),
                "scope_key": run.scope_key,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "duration_seconds": result.duration_seconds,
                "page_count": result.page_count,
                "mode": run.mode,
            },
            "stats": summary_stats,
            "samples": samples,
        }

    def _send_run_summary_email(self, session: Session, run: models.SyncRun, summary: dict[str, Any]) -> dict[str, Any]:
        email_service = EmailService()
        recipients = get_admin_emails(session)
        if not recipients:
            log_event(
                "sync.summary.email.skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="no_recipients",
            )
            return {"sent": False, "recipients": [], "subject": None, "reason": "no_recipients"}
        if not email_service.is_enabled():
            log_event(
                "sync.summary.email.skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="email_disabled",
            )
            return {"sent": False, "recipients": recipients, "subject": None, "reason": "email_disabled"}
        if not email_service.is_configured():
            log_event(
                "sync.summary.email.skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="email_not_configured",
            )
            return {"sent": False, "recipients": recipients, "subject": None, "reason": "email_not_configured"}

        started_at_display = run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "inconnu"
        subject = f"Business tracker · Synthese run {started_at_display}"
        body = self._render_run_summary_email(run, summary)

        try:
            email_service.send(subject, body, recipients)
        except Exception as exc:  # noqa: BLE001 - log and continue
            _LOGGER.warning("Échec de l'envoi de la synthèse du run %s: %s", run.id, exc)
            log_event(
                "sync.summary.email.error",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="send_error",
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            return {"sent": False, "recipients": recipients, "subject": subject, "reason": "send_error"}

        log_event(
            "sync.summary.email.sent",
            run_id=str(run.id),
            scope_key=run.scope_key,
            recipients=recipients,
            subject=subject,
        )
        return {"sent": True, "recipients": recipients, "subject": subject}

    def _render_run_summary_email(self, run: models.SyncRun, summary: dict[str, Any]) -> str:
        run_data = summary.get("run", {})
        stats = summary.get("stats", {})
        google_stats = stats.get("google", {})
        alerts_stats = stats.get("alerts", {})
        samples = summary.get("samples", {})
        google_enabled = bool(google_stats.get("enabled", True))
        mode_label = run_data.get("mode") or stats.get("mode") or "full"

        def format_sample(sample: dict[str, Any], *, include_changes: bool = False) -> str:
            name = sample.get("name") or "(nom indisponible)"
            siret = sample.get("siret") or "N/A"
            postal = sample.get("code_postal") or ""
            commune = sample.get("libelle_commune") or ""
            location = " ".join(part for part in [postal, commune] if part)
            google_status = sample.get("google_status") or "unknown"
            line = f"- {name} — {siret}"
            if location:
                line += f" ({location})"
            line += f" | Google: {google_status}"
            place_url = sample.get("google_place_url")
            if place_url:
                line += f" | {place_url}"
            match_confidence = sample.get("google_match_confidence")
            if match_confidence is not None:
                line += f" | score: {float(match_confidence):.2f}"
            if include_changes and sample.get("changed_fields"):
                changes = ", ".join(sample["changed_fields"])
                line += f" | champs: {changes}"
            return line

        lines = [
            f"Synthèse du run {run_data.get('id', run.id)} ({run.scope_key})",
            f"Statut: {run_data.get('status', run.status)}",
            f"Mode: {mode_label}",
            f"Début: {run_data.get('started_at')}",
            f"Fin: {run_data.get('finished_at')}",
            f"Durée: {run_data.get('duration_seconds')} s",
            f"Pages traitées: {run_data.get('page_count')}",
            "",
            "Statistiques:",
            f"- Enregistrements récupérés: {stats.get('fetched_records')}",
            f"- Nouveaux établissements: {stats.get('created_records')}",
            f"- Établissements mis à jour: {stats.get('updated_records')}",
            f"- Appels API: {stats.get('api_call_count')}",
            "",
            "Google Places:",
        ]
        if not google_enabled:
            lines.append("- Désactivé (mode Sirene-only)")
        else:
            lines.extend(
                [
                    f"- Appels API Google: {google_stats.get('api_call_count')}",
                    f"- Correspondances immédiates: {google_stats.get('immediate_matches')}",
                    f"- Correspondances tardives: {google_stats.get('late_matches')}",
                    f"- Total correspondances: {google_stats.get('matched_count')}",
                    f"- En file d'attente: {google_stats.get('pending_count')}",
                ]
            )
        lines.extend(
            [
                "",
                "Alertes:",
                f"- Créées: {alerts_stats.get('created')}",
                f"- Envoyées: {alerts_stats.get('sent')}",
            ]
        )

        new_samples = samples.get("new_establishments", [])
        if new_samples:
            lines.append("")
            lines.append("Nouveaux établissements (top 10):")
            for sample in new_samples:
                lines.append(format_sample(sample))

        updated_samples = samples.get("updated_establishments", [])
        if updated_samples:
            lines.append("")
            lines.append("Établissements mis à jour (top 10):")
            for sample in updated_samples:
                lines.append(format_sample(sample, include_changes=True))

        late_samples = samples.get("google_late_matches", [])
        if late_samples:
            lines.append("")
            lines.append("Correspondances Google tardives (top 10):")
            for sample in late_samples:
                lines.append(format_sample(sample))

        immediate_samples = samples.get("google_immediate_matches", [])
        if immediate_samples:
            lines.append("")
            lines.append("Correspondances Google immédiates (top 10):")
            for sample in immediate_samples:
                lines.append(format_sample(sample))

        return "\n".join(lines).strip()
