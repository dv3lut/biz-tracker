"""High-level website scraping service.

Provides both a synchronous and an asynchronous entry-point.  The synchronous
``scrape_website`` wrapper creates a dedicated event-loop so that it can be
called safely from synchronous BizTracker code (SQLAlchemy sessions, CLI…).
"""
from __future__ import annotations

import asyncio
import gc
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.services.website_scraper.browser_pool import cleanup_browser_pool
from app.services.website_scraper.crawlers import crawl_website_async

_LOGGER = logging.getLogger(__name__)

# Maximum number of items kept per list (phones, emails…).
_MAX_ITEMS = 10

# Timeout for the whole scraping of a single website (seconds).
_GLOBAL_TIMEOUT = 90
_CRAWL_TIMEOUT = 80


@dataclass
class WebsiteScrapingResult:
    """Structured output of a website scraping pass."""

    mobile_phones: list[str] = field(default_factory=list)
    national_phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    facebook: str | None = None
    instagram: str | None = None
    twitter: str | None = None
    linkedin: str | None = None

    @property
    def has_data(self) -> bool:
        return bool(
            self.mobile_phones
            or self.national_phones
            or self.emails
            or self.facebook
            or self.instagram
            or self.twitter
            or self.linkedin
        )

    # Pipe-separated helpers matching the DB column format.
    @property
    def mobile_phones_str(self) -> str | None:
        return "|".join(self.mobile_phones) if self.mobile_phones else None

    @property
    def national_phones_str(self) -> str | None:
        return "|".join(self.national_phones) if self.national_phones else None

    @property
    def emails_str(self) -> str | None:
        return "|".join(self.emails) if self.emails else None


class _TimeoutHandler:
    """Async context-manager that cleans up the browser pool on timeout."""

    def __init__(self, seconds: int = _GLOBAL_TIMEOUT) -> None:
        self.seconds = seconds
        self._handle: asyncio.Task | None = None

    async def __aenter__(self) -> "_TimeoutHandler":
        self._handle = asyncio.create_task(self._timeout())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._handle:
            self._handle.cancel()

    async def _timeout(self) -> None:
        await asyncio.sleep(self.seconds)
        _LOGGER.warning("Timeout global de %ds dépassé — cleanup forcé", self.seconds)
        await cleanup_browser_pool()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scrape_website_async(website_url: str, label: str = "Inconnu") -> WebsiteScrapingResult:
    """Scrape *website_url* asynchronously and return a structured result."""

    if not website_url:
        return WebsiteScrapingResult()

    _LOGGER.info("[%s] Début scraping site web %s", label, website_url)

    async with _TimeoutHandler(seconds=_GLOBAL_TIMEOUT):
        try:
            raw = await asyncio.wait_for(
                crawl_website_async(website_url, max_pages=5, max_depth=1, label=label),
                timeout=_CRAWL_TIMEOUT,
            )

            result = WebsiteScrapingResult(
                mobile_phones=raw.get("mobile_phones", [])[:_MAX_ITEMS],
                national_phones=raw.get("national_phones", [])[:_MAX_ITEMS],
                emails=raw.get("emails", [])[:_MAX_ITEMS],
                facebook=raw.get("facebook"),
                instagram=raw.get("instagram"),
                twitter=raw.get("twitter"),
                linkedin=raw.get("linkedin"),
            )
            _LOGGER.info("[%s] Scraping terminé — %s", label, _summary(result))
            gc.collect()
            return result

        except asyncio.TimeoutError:
            _LOGGER.warning("[%s] Timeout scraping %s", label, website_url)
            return WebsiteScrapingResult()
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("[%s] Erreur scraping %s: %s", label, website_url, exc)
            return WebsiteScrapingResult()


def scrape_website(website_url: str, label: str = "Inconnu") -> WebsiteScrapingResult:
    """Synchronous entry-point — safe to call from non-async code.

    Creates a fresh event-loop internally so that the caller does not need
    to worry about an already-running loop.
    """

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(scrape_website_async(website_url, label))
    finally:
        loop.close()


def _summary(result: WebsiteScrapingResult) -> str:
    parts = []
    if result.mobile_phones:
        parts.append(f"{len(result.mobile_phones)} mobiles")
    if result.national_phones:
        parts.append(f"{len(result.national_phones)} fixes")
    if result.emails:
        parts.append(f"{len(result.emails)} emails")
    socials = sum(1 for s in (result.facebook, result.instagram, result.twitter, result.linkedin) if s)
    if socials:
        parts.append(f"{socials} réseaux sociaux")
    return ", ".join(parts) if parts else "aucune donnée"
