from __future__ import annotations

import logging
import re
import time
from collections import deque
from datetime import UTC, datetime
from typing import Deque
from urllib.robotparser import RobotFileParser

import requests

from web_docs_to_markdown.config import AppConfig
from web_docs_to_markdown.extractor import ContentExtractor
from web_docs_to_markdown.models import CrawlStats, PageDocument
from web_docs_to_markdown.renderer import BrowserRenderer, FetchResult
from web_docs_to_markdown.storage import Storage
from web_docs_to_markdown.utils import (
    count_words,
    get_domain,
    get_origin,
    is_probably_html_url,
    normalize_url,
    sha256_text,
    stable_id,
)

logger = logging.getLogger(__name__)


class Crawler:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.stats = CrawlStats()

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.config.http.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en;q=0.9,*;q=0.5",
            }
        )

        self.renderer = BrowserRenderer(config) if config.browser.enabled else None

        self.extractor = ContentExtractor(
            remove_selectors=self.config.markdown.remove_selectors,
            link_exclude_selectors=self.config.crawl.link_exclude_selectors,
        )
        self.storage = Storage(config)

        self.include_patterns = [
            re.compile(pattern) for pattern in self.config.crawl.include_patterns
        ]
        self.exclude_patterns = [
            re.compile(pattern) for pattern in self.config.crawl.exclude_patterns
        ]

        normalized_seeds = [normalize_url(seed) for seed in config.seeds]
        self.seeds = [seed for seed in normalized_seeds if seed]

        if not self.seeds:
            raise ValueError("No valid HTTP/HTTPS seed URLs were provided.")

        self.seed_domains = {get_domain(seed) for seed in self.seeds}
        self.robots_cache: dict[str, RobotFileParser] = {}

    def run(self) -> CrawlStats:
        try:
            return self._run()
        finally:
            if self.renderer is not None:
                self.renderer.close()

    def _run(self) -> CrawlStats:
        self.storage.prepare()

        queue: Deque[tuple[str, int, str]] = deque()
        seen: set[str] = set()

        for seed in self.seeds:
            queue.append((seed, 0, seed))
            seen.add(seed)
            self.stats.discovered += 1

        processed_pages = 0

        while queue and processed_pages < self.config.crawl.max_pages:
            url, depth, source_url = queue.popleft()

            if not self._is_allowed_url(url):
                self._skip("URL not allowed by domain or pattern filters", url)
                continue

            if self.config.crawl.respect_robots_txt and not self._is_allowed_by_robots(url):
                self._skip("URL disallowed by robots.txt", url)
                continue

            if not is_probably_html_url(url):
                self._skip("URL does not look like HTML", url)
                continue

            response = self._fetch(url)
            if response is None:
                continue

            final_url = normalize_url(response.url) or url

            if final_url != url:
                if not self._is_allowed_url(final_url):
                    self._skip("Redirect target not allowed", final_url)
                    continue

            content_type = self._get_content_type(response.headers)

            if not self._is_html_response(content_type):
                self._skip(f"Non-HTML content type: {content_type}", final_url)
                continue

            processed_pages += 1

            html = response.text

            try:
                extracted = self.extractor.extract(html, final_url)
            except Exception as exc:
                self._error(f"Failed to extract content from {final_url}: {exc}")
                continue

            if len(extracted.markdown.strip()) < self.config.markdown.min_content_chars:
                self._skip("Extracted content below minimum character threshold", final_url)
            else:
                document = self._build_document(
                    source_url=source_url,
                    final_url=final_url,
                    title=extracted.title,
                    markdown=extracted.markdown,
                    depth=depth,
                    status_code=response.status_code,
                    content_type=content_type or "text/html",
                )

                try:
                    self.storage.save(document)
                    self.stats.saved += 1
                    logger.info("Saved depth=%s %s", depth, final_url)
                except Exception as exc:
                    self._error(f"Failed to save {final_url}: {exc}")

            if depth < self.config.crawl.max_depth:
                try:
                    raw_links = self.extractor.extract_links(html, final_url)
                    for raw_link in raw_links:
                        normalized_link = normalize_url(raw_link, base_url=final_url)
                        if not normalized_link:
                            continue

                        if normalized_link in seen:
                            continue

                        if not self._is_allowed_url(normalized_link):
                            continue

                        if not is_probably_html_url(normalized_link):
                            continue

                        seen.add(normalized_link)
                        queue.append((normalized_link, depth + 1, normalized_link))
                        self.stats.discovered += 1

                except Exception as exc:
                    self._error(f"Failed to extract links from {final_url}: {exc}")

            if self.config.crawl.request_delay_seconds > 0:
                time.sleep(self.config.crawl.request_delay_seconds)

        if processed_pages >= self.config.crawl.max_pages:
            logger.info("Reached max_pages=%s", self.config.crawl.max_pages)

        return self.stats

    def _fetch(self, url: str) -> FetchResult | None:
        last_exception: Exception | None = None
        attempts = self.config.http.max_retries + 1

        for attempt in range(1, attempts + 1):
            try:
                logger.debug("Fetching attempt=%s url=%s", attempt, url)

                if self.renderer is not None:
                    result = self.renderer.fetch(url)
                else:
                    response = self.session.get(
                        url,
                        timeout=self.config.http.timeout_seconds,
                        allow_redirects=True,
                    )

                    result = FetchResult(
                        url=response.url,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        text=response.text,
                    )

                self.stats.fetched += 1

                if result.status_code >= 400:
                    self._skip(f"HTTP status {result.status_code}", url)
                    return None

                return result

            except Exception as exc:
                last_exception = exc
                logger.warning("Request failed attempt=%s url=%s error=%s", attempt, url, exc)

                if attempt < attempts:
                    sleep_seconds = min(2 ** (attempt - 1), 8)
                    time.sleep(sleep_seconds)

        self._error(f"Failed to fetch {url}: {last_exception}")
        return None

    def _get_content_type(self, headers: dict[str, str]) -> str:
        for key, value in headers.items():
            if key.lower() == "content-type":
                return value.split(";")[0].strip().lower()

        # Browser-rendered Seiten liefern manchmal keinen Content-Type mehr zurück.
        # In diesem Fall behandeln wir die Antwort als HTML.
        return "text/html"

    def _is_html_response(self, content_type: str) -> bool:
        if not content_type:
            return True

        content_type = content_type.lower()
        return content_type in {
            "text/html",
            "application/xhtml+xml",
        }

    def _is_allowed_url(self, url: str) -> bool:
        if self.config.crawl.same_domain_only and get_domain(url) not in self.seed_domains:
            return False

        for pattern in self.exclude_patterns:
            if pattern.search(url):
                return False

        if self.include_patterns:
            return any(pattern.search(url) for pattern in self.include_patterns)

        return True

    def _is_allowed_by_robots(self, url: str) -> bool:
        origin = get_origin(url)

        if origin not in self.robots_cache:
            self.robots_cache[origin] = self._load_robots(origin)

        parser = self.robots_cache[origin]

        try:
            return parser.can_fetch(self.config.http.user_agent, url)
        except Exception as exc:
            logger.warning("robots.txt check failed for %s: %s; allowing URL", url, exc)
            return True

    def _load_robots(self, origin: str) -> RobotFileParser:
        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            logger.debug("Fetching robots.txt: %s", robots_url)
            response = self.session.get(
                robots_url,
                timeout=self.config.http.timeout_seconds,
                allow_redirects=True,
            )

            if response.status_code == 200:
                parser.parse(response.text.splitlines())
                logger.debug("Loaded robots.txt: %s", robots_url)
            else:
                parser.parse([])
                logger.debug(
                    "robots.txt unavailable status=%s url=%s; allowing all",
                    response.status_code,
                    robots_url,
                )

        except requests.RequestException as exc:
            parser.parse([])
            logger.warning("Could not fetch robots.txt %s: %s; allowing all", robots_url, exc)

        return parser

    def _build_document(
        self,
        source_url: str,
        final_url: str,
        title: str | None,
        markdown: str,
        depth: int,
        status_code: int,
        content_type: str,
    ) -> PageDocument:
        now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        checksum = sha256_text(markdown)

        return PageDocument(
            id=stable_id(final_url, length=16),
            source_url=source_url,
            final_url=final_url,
            title=title,
            markdown=markdown,
            depth=depth,
            status_code=status_code,
            content_type=content_type,
            crawled_at=now,
            sha256=checksum,
            word_count=count_words(markdown),
            char_count=len(markdown),
        )

    def _skip(self, reason: str, url: str) -> None:
        self.stats.skipped += 1
        logger.debug("Skipped %s: %s", url, reason)

    def _error(self, message: str) -> None:
        self.stats.add_error(message)
        logger.error(message)