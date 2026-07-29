from __future__ import annotations

import logging
from dataclasses import dataclass

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from web_docs_to_markdown.config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    status_code: int
    headers: dict[str, str]
    text: str


class BrowserRenderer:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def start(self) -> None:
        if self._playwright is not None:
            return

        logger.info("Starting Playwright Chromium renderer")

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.config.browser.headless,
        )

        self._context = self._browser.new_context(
            user_agent=self.config.http.user_agent,
            java_script_enabled=True,
            ignore_https_errors=False,
            viewport={"width": 1440, "height": 1000},
        )

        if self.config.browser.block_resources:
            blocked_types = set(self.config.browser.blocked_resource_types)

            def route_handler(route):
                request = route.request
                if request.resource_type in blocked_types:
                    return route.abort()
                return route.continue_()

            self._context.route("**/*", route_handler)

    def close(self) -> None:
        logger.debug("Closing Playwright renderer")

        if self._context is not None:
            self._context.close()
            self._context = None

        if self._browser is not None:
            self._browser.close()
            self._browser = None

        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def fetch(self, url: str) -> FetchResult:
        self.start()

        if self._context is None:
            raise RuntimeError("Browser context was not initialized.")

        timeout_ms = int(self.config.http.timeout_seconds * 1000)

        page: Page = self._context.new_page()
        page.set_default_timeout(timeout_ms)
        page.set_default_navigation_timeout(timeout_ms)

        try:
            logger.debug("Rendering URL with Playwright: %s", url)

            response = page.goto(
                url,
                wait_until=self.config.browser.wait_until,
                timeout=timeout_ms,
            )

            if self.config.browser.wait_for_selector:
                selector = self.config.browser.wait_for_selector
                try:
                    logger.debug("Waiting for selector %s on %s", selector, url)
                    page.wait_for_selector(selector, timeout=timeout_ms)
                except PlaywrightTimeoutError:
                    logger.warning(
                        "Timed out waiting for selector %s on %s; continuing anyway",
                        selector,
                        url,
                    )

            if self.config.browser.extra_wait_ms > 0:
                page.wait_for_timeout(self.config.browser.extra_wait_ms)

            html = page.content()

            status_code = response.status if response is not None else 0
            headers = dict(response.headers) if response is not None else {}

            return FetchResult(
                url=page.url,
                status_code=status_code,
                headers=headers,
                text=html,
            )

        finally:
            page.close()
