"""Per-NAF auto-email dispatch for newly created establishments."""
from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event, serialize_exception
from app.services.email_service import EmailService

_LOGGER = logging.getLogger(__name__)

_EMAIL_REGEX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def _extract_emails(value: str | None) -> list[str]:
    if not value:
        return []
    matches = _EMAIL_REGEX.findall(value)
    seen: set[str] = set()
    result: list[str] = []
    for raw in matches:
        normalized = raw.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _pick_recipient_emails(establishment: models.Establishment) -> list[str]:
    """Return all distinct candidate emails for an establishment, ordered by priority."""

    seen: set[str] = set()
    ordered: list[str] = []

    def add(candidates: Iterable[str]) -> None:
        for candidate in candidates:
            normalized = candidate.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)

    # Highest priority: emails extracted from website scraping (relational table).
    scraped_emails = [
        contact.value
        for contact in establishment.scraped_contacts or []
        if contact.contact_type == "email" and contact.value
    ]
    add(scraped_emails)
    # Legacy CSV column kept for back-compat.
    add(_extract_emails(establishment.website_scraped_emails))
    # Google contact fallback.
    if establishment.google_contact_email:
        add([establishment.google_contact_email])

    return ordered


def _leader_display_name(establishment: models.Establishment) -> str | None:
    directors = list(establishment.directors or [])
    if not directors:
        return None
    physical = next((d for d in directors if d.type_dirigeant == "personne physique"), None)
    chosen = physical or directors[0]
    parts: list[str] = []
    if chosen.first_names:
        first = chosen.first_names.strip().split()
        if first:
            parts.append(first[0].capitalize())
    if chosen.last_name:
        parts.append(chosen.last_name.strip().upper())
    if parts:
        return " ".join(parts)
    if chosen.denomination:
        return chosen.denomination.strip()
    return None


def _build_template_variables(establishment: models.Establishment, recipient_email: str) -> dict[str, str]:
    commune = establishment.libelle_commune or establishment.libelle_commune_etranger or ""
    return {
        "name": (establishment.name or "").strip(),
        "siret": establishment.siret or "",
        "naf_code": establishment.naf_code or "",
        "code_postal": establishment.code_postal or "",
        "commune": commune,
        "email": recipient_email,
        "leader_name": _leader_display_name(establishment) or "",
        "google_place_url": establishment.google_place_url or "",
        "legal_unit_name": establishment.legal_unit_name or "",
    }


class _SafeFormatDict(dict):
    """dict that returns an empty string for missing template variables."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        return ""


def _render_template(template: str, variables: dict[str, str]) -> str:
    try:
        return template.format_map(_SafeFormatDict(variables))
    except (IndexError, KeyError, ValueError):
        # Fallback: return the raw template if it contains malformed placeholders.
        return template


def _load_auto_email_configs(
    session: Session, naf_codes: Iterable[str]
) -> dict[str, models.NafSubCategory]:
    codes = sorted({code for code in naf_codes if code})
    if not codes:
        return {}
    stmt = select(models.NafSubCategory).where(
        models.NafSubCategory.naf_code.in_(codes),
        models.NafSubCategory.auto_email_enabled.is_(True),
    )
    rows = session.execute(stmt).scalars().all()
    return {row.naf_code: row for row in rows}


def dispatch_auto_emails(
    session: Session,
    run: models.SyncRun,
    new_establishments: list[models.Establishment],
) -> dict[str, Any]:
    """Send per-NAF auto-emails to newly created establishments with a known email.

    Returns a summary dict with per-NAF and per-establishment recipient details.
    """

    summary: dict[str, Any] = {
        "enabled_naf_codes": [],
        "attempted_count": 0,
        "sent_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
        "items": [],
        "reason": None,
    }

    if not new_establishments:
        summary["reason"] = "no_new_establishments"
        return summary

    configs = _load_auto_email_configs(
        session,
        (establishment.naf_code for establishment in new_establishments),
    )
    if not configs:
        summary["reason"] = "no_naf_with_auto_email"
        return summary

    summary["enabled_naf_codes"] = sorted(configs.keys())

    email_service = EmailService()
    settings = email_service.settings
    if not email_service.is_enabled() or not email_service.is_configured():
        summary["reason"] = "email_not_configured"
        log_event(
            "sync.auto_email.skipped",
            run_id=str(run.id),
            reason=summary["reason"],
        )
        return summary

    from_address = settings.from_address

    for establishment in new_establishments:
        config = configs.get(establishment.naf_code or "")
        if config is None:
            continue
        recipients = _pick_recipient_emails(establishment)
        item: dict[str, Any] = {
            "siret": establishment.siret,
            "name": establishment.name,
            "naf_code": establishment.naf_code,
            "subcategory_id": str(config.id),
            "subcategory_name": config.name,
            "recipients": [],
            "sent": False,
            "reason": None,
        }

        if not recipients:
            summary["skipped_count"] += 1
            item["reason"] = "no_email_found"
            summary["items"].append(item)
            continue

        subject_template = (config.auto_email_subject or "").strip()
        body_template = (config.auto_email_body or "").strip()
        if not subject_template or not body_template:
            summary["skipped_count"] += 1
            item["reason"] = "missing_template"
            summary["items"].append(item)
            continue

        recipient = recipients[0]
        variables = _build_template_variables(establishment, recipient)
        subject = _render_template(subject_template, variables)
        body = _render_template(body_template, variables)

        summary["attempted_count"] += 1
        try:
            email_service.send(
                subject,
                body,
                [recipient],
                reply_to=from_address,
            )
        except Exception as exc:  # noqa: BLE001 - log and continue
            summary["failed_count"] += 1
            item["reason"] = "send_error"
            item["error"] = serialize_exception(exc)
            log_event(
                "sync.auto_email.send_error",
                level=logging.WARNING,
                run_id=str(run.id),
                siret=establishment.siret,
                naf_code=establishment.naf_code,
                recipient=recipient,
                error=item["error"],
            )
        else:
            summary["sent_count"] += 1
            item["sent"] = True
            item["recipients"] = [recipient]
            log_event(
                "sync.auto_email.sent",
                run_id=str(run.id),
                siret=establishment.siret,
                naf_code=establishment.naf_code,
                recipient=recipient,
                subject=subject,
            )

        summary["items"].append(item)

    return summary


__all__ = ["dispatch_auto_emails"]
