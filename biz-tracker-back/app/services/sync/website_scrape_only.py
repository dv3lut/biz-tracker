"""Helpers for website-scrape-only sync modes."""
from __future__ import annotations

import logging
import time
from typing import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event
from app.services.website_scraper.scraper_service import WebsiteScrapingResult, scrape_website
from app.services.google_business.google_business_service import _persist_scraped_contacts
from app.utils.dates import utcnow

from .context import SyncContext, SyncResult
from .mode import SyncMode

_LOGGER = logging.getLogger(__name__)

LogAlertsFn = Callable[[models.SyncRun, Sequence[models.Alert]], list[dict[str, object]]]


def load_website_scrape_targets(
    session: Session,
    target_naf_codes: Sequence[str] | None = None,
    *,
    website_statuses: Sequence[str] | None = None,
) -> list[models.Establishment]:
    """Load establishments that have a website URL and match the requested scrape status.

    *website_statuses* accepted values:
    - ``"not_scraped"`` – establishments where ``website_scraped_at IS NULL``
    - ``"scraped"`` – establishments where ``website_scraped_at IS NOT NULL``
    If empty or ``None``, defaults to ``["not_scraped"]`` (only unscrapped sites).
    """

    stmt = (
        select(models.Establishment)
        .where(models.Establishment.google_contact_website.is_not(None))
        .where(models.Establishment.google_contact_website != "")
        .order_by(models.Establishment.first_seen_at.asc())
    )

    cleaned_statuses = [s.strip().lower() for s in (website_statuses or []) if s and s.strip()]
    if not cleaned_statuses:
        cleaned_statuses = ["not_scraped"]

    has_scraped = "scraped" in cleaned_statuses
    has_not_scraped = "not_scraped" in cleaned_statuses

    if has_scraped and not has_not_scraped:
        stmt = stmt.where(models.Establishment.website_scraped_at.is_not(None))
    elif has_not_scraped and not has_scraped:
        stmt = stmt.where(models.Establishment.website_scraped_at.is_(None))
    # If both statuses are selected, no additional filter needed (all with a website).

    if target_naf_codes:
        stmt = stmt.where(models.Establishment.naf_code.in_(target_naf_codes))

    return session.execute(stmt).scalars().all()


def collect_website_scrape_only(
    context: SyncContext,
    targets: Sequence[models.Establishment],
    *,
    log_alerts: LogAlertsFn,
) -> SyncResult:
    """Iterate over *targets* and scrape their ``google_contact_website``."""

    started_at = time.perf_counter()
    session = context.session
    run = context.run
    mode = context.mode
    now = utcnow()

    scrape_count = 0
    scrape_success_count = 0

    if not targets:
        log_event(
            "sync.website_scrape.skipped",
            run_id=str(run.id),
            scope_key=run.scope_key,
            mode=mode.value,
            reason="no_targets",
        )
        run.website_scrape_count = 0
        run.website_scrape_success_count = 0
        session.commit()
    else:
        log_event(
            "sync.website_scrape.started",
            run_id=str(run.id),
            scope_key=run.scope_key,
            mode=mode.value,
            target_count=len(targets),
        )

        for establishment in targets:
            website_url = establishment.google_contact_website
            if not website_url:
                continue
            scrape_count += 1
            label = establishment.name or establishment.siret or "Inconnu"

            try:
                result: WebsiteScrapingResult = scrape_website(website_url, label=label)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning(
                    "Scraping échoué pour %s (%s): %s",
                    establishment.siret,
                    website_url,
                    exc,
                )
                log_event(
                    "sync.website_scrape.error",
                    run_id=str(run.id),
                    siret=establishment.siret,
                    website_url=website_url,
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
                continue

            establishment.website_scraped_at = now
            establishment.website_scraped_mobile_phones = result.mobile_phones_str
            establishment.website_scraped_national_phones = result.national_phones_str
            establishment.website_scraped_emails = result.emails_str
            establishment.website_scraped_facebook = result.facebook
            establishment.website_scraped_instagram = result.instagram
            establishment.website_scraped_twitter = result.twitter
            establishment.website_scraped_linkedin = result.linkedin

            # Persist structured contacts to the dedicated table.
            _persist_scraped_contacts(session, establishment.siret, result, now)

            has_data = bool(
                result.mobile_phones
                or result.national_phones
                or result.emails
                or result.facebook
                or result.instagram
                or result.twitter
                or result.linkedin
            )
            if has_data:
                scrape_success_count += 1

            log_event(
                "sync.website_scrape.done",
                run_id=str(run.id),
                siret=establishment.siret,
                website_url=website_url,
                has_data=has_data,
            )

        run.website_scrape_count = scrape_count
        run.website_scrape_success_count = scrape_success_count

        log_event(
            "sync.website_scrape.summary",
            run_id=str(run.id),
            scope_key=run.scope_key,
            mode=mode.value,
            scrape_count=scrape_count,
            scrape_success_count=scrape_success_count,
            target_count=len(targets),
        )

        session.commit()

    # No alerts for website-only scraping.
    alerts_payload = log_alerts(run, [])
    duration = time.perf_counter() - started_at

    return SyncResult(
        mode=mode,
        last_treated=None,
        new_establishments=[],
        new_establishment_payloads=[],
        updated_establishments=[],
        updated_payloads=[],
        google_immediate_matches=[],
        google_late_matches=[],
        google_match_payloads=[],
        alerts=[],
        alert_payloads=alerts_payload,
        page_count=0,
        duration_seconds=duration,
        max_creation_date=None,
        google_queue_count=0,
        google_eligible_count=0,
        google_matched_count=0,
        google_pending_count=0,
        google_api_call_count=0,
        google_api_error_count=0,
        alerts_sent_count=0,
    )
