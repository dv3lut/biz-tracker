"""Website crawlers — HTTP (requests + BeautifulSoup) and optional Playwright."""
from __future__ import annotations

import asyncio
import concurrent.futures
import heapq
import logging
from typing import Dict, List, Set

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from app.services.website_scraper.browser_pool import browser_pool, is_playwright_available
from app.services.website_scraper.extractors import (
    extract_emails,
    extract_phones,
    extract_social_links,
    needs_browser_rendering,
)
from app.services.website_scraper.url_utils import (
    get_url_priority,
    is_same_domain,
    is_valid_url,
    normalize_url,
)

_LOGGER = logging.getLogger(__name__)

_EMPTY_RESULT: Dict = {
    "mobile_phones": [],
    "national_phones": [],
    "international_phones": [],
    "emails": [],
    "facebook": None,
    "instagram": None,
    "twitter": None,
    "linkedin": None,
}

def _merge_contacts(target: set[str], items: list[str]) -> None:
    """Merge *items* into *target* (set-based deduplication)."""

    target.update(items)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get_requests_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504, 404],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _safe_get(session: requests.Session, url: str, timeout: int = 20) -> requests.Response | None:
    """GET with a strict hard timeout via a thread-pool executor."""

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                session.get,
                url,
                timeout=timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
                    ),
                },
            )
            return future.result(timeout=timeout + 5)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("[SAFE_GET] Exception lors du GET %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Playwright-based crawler
# ---------------------------------------------------------------------------

async def crawl_with_browser(
    url: str,
    max_pages: int = 3,
    max_depth: int = 1,
    label: str = "Inconnu",
) -> Dict:
    """Crawl *url* using a headless Chromium browser (Playwright)."""

    _LOGGER.info("[%s] Démarrage du crawl Playwright pour %s", label, url)

    all_mobiles: set[str] = set()
    all_nationals: set[str] = set()
    all_internationals: set[str] = set()
    all_emails: set[str] = set()
    social_links = {"facebook": None, "instagram": None, "twitter": None, "linkedin": None}
    visited_urls: Set[str] = set()
    counter = 0
    to_visit: list = [(get_url_priority(url), counter, url, 0)]
    heapq.heapify(to_visit)

    try:
        browser = await browser_pool.get_browser()
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            context.set_default_timeout(30_000)
            page_count = 0

            while to_visit and len(visited_urls) < max_pages:
                _, _, current_url, depth = heapq.heappop(to_visit)
                page_count += 1
                depth_max = 3 if depth == 0 else 2
                if current_url in visited_urls or depth > max_depth or page_count > depth_max:
                    continue

                _LOGGER.debug("[%s] Playwright page %d — %s", label, page_count, current_url)
                visited_urls.add(current_url)

                try:
                    page = await context.new_page()
                    await page.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())
                    await page.route("**/*.{css,woff,woff2,ttf,otf,eot}", lambda route: route.abort())

                    try:
                        await page.goto(current_url, wait_until="domcontentloaded", timeout=20_000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10_000)
                        except Exception:  # noqa: BLE001
                            pass

                        await page.evaluate("""
                            async () => {
                                const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                                const height = document.body.scrollHeight;
                                const steps = 3;
                                for (let i = 0; i <= steps; i++) {
                                    window.scrollTo(0, (height / steps) * i);
                                    await delay(300);
                                }
                                window.scrollTo(0, 0);
                            }
                        """)
                        await asyncio.sleep(3)

                        page_content = await page.content()
                        page_text = await page.evaluate("() => document.body.innerText")

                        mobiles, nationals, internationals = extract_phones(page_text)
                        emails = extract_emails(page_text)
                        socials = extract_social_links(page_content)

                        _merge_contacts(all_mobiles, mobiles)
                        _merge_contacts(all_nationals, nationals)
                        _merge_contacts(all_internationals, internationals)
                        _merge_contacts(all_emails, emails)
                        for network, link in socials.items():
                            if link and not social_links[network]:
                                social_links[network] = link

                        if depth < max_depth:
                            links = await page.evaluate(
                                "() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href)"
                            )
                            for href in links:
                                normalized = normalize_url(current_url, href)
                                if normalized and is_same_domain(url, normalized) and normalized not in visited_urls:
                                    counter += 1
                                    heapq.heappush(to_visit, (get_url_priority(normalized), counter, normalized, depth + 1))

                        await page.close()
                    except Exception as exc:  # noqa: BLE001
                        _LOGGER.warning("[%s] Playwright erreur page %s: %s", label, current_url, exc)
                        await page.close()
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.warning("[%s] Playwright erreur context %s: %s", label, current_url, exc)

            await context.close()
        finally:
            await browser_pool.release_browser(browser)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("[%s] Erreur Playwright générale: %s", label, exc)

    return {
        "mobile_phones": sorted(all_mobiles),
        "national_phones": sorted(all_nationals),
        "international_phones": sorted(all_internationals),
        "emails": sorted(all_emails),
        **social_links,
    }


# ---------------------------------------------------------------------------
# HTTP-only crawler (synchronous)
# ---------------------------------------------------------------------------

def crawl_website(
    start_url: str,
    max_pages: int = 10,
    max_depth: int = 1,
    label: str = "Inconnu",
) -> Dict:
    """Crawl *start_url* using plain HTTP requests + BeautifulSoup."""

    _LOGGER.info("[%s] Démarrage du crawl HTTP pour %s", label, start_url)

    if not is_valid_url(start_url):
        _LOGGER.warning("[%s] URL invalide: %s", label, start_url)
        return dict(_EMPTY_RESULT)

    visited_urls: Set[str] = set()
    counter = 0
    to_visit: list = [(get_url_priority(start_url), counter, start_url, 0)]
    heapq.heapify(to_visit)

    all_mobiles: set[str] = set()
    all_nationals: set[str] = set()
    all_internationals: set[str] = set()
    all_emails: set[str] = set()
    social_links = {"facebook": None, "instagram": None, "twitter": None, "linkedin": None}

    page_count = 0

    while to_visit and len(visited_urls) < max_pages:
        _, _, current_url, depth = heapq.heappop(to_visit)
        page_count += 1
        depth_max = 10 if depth == 0 else 5
        if current_url in visited_urls or depth > max_depth or page_count > depth_max:
            continue

        _LOGGER.debug("[%s] HTTP page %d — %s", label, page_count, current_url)
        visited_urls.add(current_url)

        try:
            session = _get_requests_session()
            response = _safe_get(session, current_url, timeout=20)
            if response is None or not response.ok:
                continue
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            page_text = soup.get_text()
            page_html = str(soup)

            mobiles, nationals, internationals = extract_phones(page_text)
            emails = extract_emails(page_text)
            socials = extract_social_links(page_html)

            _merge_contacts(all_mobiles, mobiles)
            _merge_contacts(all_nationals, nationals)
            _merge_contacts(all_internationals, internationals)
            _merge_contacts(all_emails, emails)
            for network, link in socials.items():
                if link and not social_links[network]:
                    social_links[network] = link

            if depth < max_depth:
                for anchor in soup.find_all("a", href=True):
                    normalized = normalize_url(current_url, anchor["href"])
                    if normalized and is_same_domain(start_url, normalized) and normalized not in visited_urls:
                        counter += 1
                        heapq.heappush(to_visit, (get_url_priority(normalized), counter, normalized, depth + 1))
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("[%s] Erreur HTTP sur %s: %s", label, current_url, exc)

    _LOGGER.info(
        "[%s] Crawl terminé — %d mobiles, %d fixes, %d emails",
        label,
        len(all_mobiles),
        len(all_nationals),
        len(all_emails),
    )

    return {
        "mobile_phones": sorted(all_mobiles),
        "national_phones": sorted(all_nationals),
        "international_phones": sorted(all_internationals),
        "emails": sorted(all_emails),
        **social_links,
    }


# ---------------------------------------------------------------------------
# Async dispatcher (HTTP first, Playwright fallback)
# ---------------------------------------------------------------------------

async def crawl_website_async(
    start_url: str,
    max_pages: int = 5,
    max_depth: int = 1,
    label: str = "Inconnu",
) -> Dict:
    """Try a plain GET; fall back to Playwright only if JS rendering is detected."""

    if not is_valid_url(start_url):
        return dict(_EMPTY_RESULT)

    try:
        session = _get_requests_session()
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: _safe_get(session, start_url, timeout=20))
        if response and response.ok and "text/html" in response.headers.get("Content-Type", ""):
            if not needs_browser_rendering(response.text):
                return crawl_website(start_url, max_pages, max_depth, label)
            _LOGGER.info("[%s] JS rendering détecté pour %s", label, start_url)
        else:
            return dict(_EMPTY_RESULT)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("[%s] GET échoué pour %s: %s", label, start_url, exc)
        return dict(_EMPTY_RESULT)

    if is_playwright_available():
        return await crawl_with_browser(start_url, max_pages, max_depth, label)

    _LOGGER.info("[%s] Playwright non disponible, fallback HTTP pour %s", label, start_url)
    return crawl_website(start_url, max_pages, max_depth, label)
