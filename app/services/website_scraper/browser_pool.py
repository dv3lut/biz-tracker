"""Playwright browser pool — optional dependency.

If ``playwright`` is not installed the pool silently degrades: ``get_browser``
raises ``RuntimeError`` and callers should fall back to HTTP-only crawling.
"""
from __future__ import annotations

import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, Browser  # noqa: F401

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PLAYWRIGHT_AVAILABLE = False


def is_playwright_available() -> bool:
    return _PLAYWRIGHT_AVAILABLE


class BrowserPool:
    """Manage a small pool of headless Chromium browsers."""

    def __init__(self, max_browsers: int = 3) -> None:
        self.max_browsers = max_browsers
        self.available_browsers: list = []
        self.active_browsers: set = set()
        self.playwright = None
        self.semaphore = asyncio.Semaphore(max_browsers)
        self.initialized = False
        self.browser_usage_count: dict[int, int] = {}

    async def initialize(self) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright is not installed — cannot initialise browser pool")
        if not self.initialized:
            self.playwright = await async_playwright().start()
            self.initialized = True

    async def get_browser(self):  # noqa: ANN201
        if not _PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright is not installed")
        await self.initialize()

        async with self.semaphore:
            browser = None
            if self.available_browsers:
                browser = self.available_browsers.pop()
                browser_id = id(browser)
                usage = self.browser_usage_count.get(browser_id, 0)
                if usage > 20:
                    _LOGGER.info("Recyclage du navigateur après %d utilisations", usage)
                    try:
                        await browser.close()
                    except Exception:  # noqa: BLE001
                        pass
                    browser = None

            if browser is None:
                browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--disable-setuid-sandbox",
                        "--no-sandbox",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--disable-web-security",
                        "--js-flags=--max-old-space-size=512",
                        "--single-process",
                        "--disable-extensions",
                        "--disable-sync",
                        "--disable-translate",
                    ],
                    timeout=30_000,
                )
                self.browser_usage_count[id(browser)] = 0

            self.browser_usage_count[id(browser)] = self.browser_usage_count.get(id(browser), 0) + 1
            self.active_browsers.add(browser)
            return browser

    async def release_browser(self, browser) -> None:  # noqa: ANN001
        if browser in self.active_browsers:
            self.active_browsers.remove(browser)
            browser_id = id(browser)
            if self.browser_usage_count.get(browser_id, 0) > 20:
                _LOGGER.info("Fermeture du navigateur après %d utilisations", self.browser_usage_count.get(browser_id))
                try:
                    await browser.close()
                except Exception:  # noqa: BLE001
                    pass
                self.browser_usage_count.pop(browser_id, None)
            else:
                self.available_browsers.append(browser)

    async def close_all(self) -> None:
        _LOGGER.info(
            "Fermeture de tous les navigateurs: %d actifs, %d disponibles",
            len(self.active_browsers),
            len(self.available_browsers),
        )
        for browser in list(self.active_browsers) + self.available_browsers:
            try:
                await browser.close()
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning("Erreur lors de la fermeture du navigateur: %s", exc)

        self.active_browsers.clear()
        self.available_browsers.clear()
        self.browser_usage_count.clear()

        if self.playwright and self.initialized:
            try:
                await self.playwright.stop()
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning("Erreur lors de l'arrêt de Playwright: %s", exc)
            self.initialized = False


# Global singleton — lazily initialised only when Playwright is actually used.
browser_pool = BrowserPool(max_browsers=3)


async def cleanup_browser_pool() -> None:
    await browser_pool.close_all()
