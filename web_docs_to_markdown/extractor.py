from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as html_to_markdown

logger = logging.getLogger(__name__)


DEFAULT_REMOVE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "nav",
    "footer",
    "aside",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "[aria-hidden='true']",
    ".sidebar",
    ".side-bar",
    ".toc",
    ".table-of-contents",
    ".breadcrumb",
    ".breadcrumbs",
    ".pagination",
    ".pager",
    ".page-footer",
    ".site-footer",
    ".navbar",
    ".nav",
    ".menu",
    ".cookie",
    ".cookie-banner",
    ".announcement",
    ".advertisement",
    ".ads",
]


DEFAULT_LINK_EXCLUDE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "header",
    "nav",
    "footer",
    "aside",
    "form",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".sidebar",
    ".side-bar",
    ".toc",
    ".table-of-contents",
    ".breadcrumb",
    ".breadcrumbs",
    ".pagination",
    ".pager",
    ".page-footer",
    ".site-footer",
    ".navbar",
    ".nav",
    ".menu",
    ".site-header",
    ".site-footer",
    ".page-tree",
    ".side-navigation",
    "[data-testid='side-navigation']",
    "[data-testid='page-tree']",
]


MAIN_CONTENT_SELECTORS = [
    "main",
    "article",
    "[role='main']",
    ".markdown-body",
    ".docs-content",
    ".doc-content",
    ".documentation",
    ".content",
    "#content",
    ".main-content",
    "#main-content",
    ".wiki-content",
    ".confluence-content",
    "#main-content",
    "#content-body",
]


@dataclass
class ExtractedContent:
    title: str | None
    markdown: str


class ContentExtractor:
    def __init__(
        self,
        remove_selectors: list[str] | None = None,
        link_exclude_selectors: list[str] | None = None,
    ) -> None:
        self.remove_selectors = self._dedupe_selectors(
            DEFAULT_REMOVE_SELECTORS + list(remove_selectors or [])
        )

        self.link_exclude_selectors = self._dedupe_selectors(
            DEFAULT_LINK_EXCLUDE_SELECTORS
            + self.remove_selectors
            + list(link_exclude_selectors or [])
        )

    def extract(self, html: str, url: str) -> ExtractedContent:
        soup = BeautifulSoup(html, "html.parser")

        title = self._extract_title(soup)

        self._remove_nodes(soup, self.remove_selectors)

        main_node = self._select_main_content(soup)

        if main_node is None:
            logger.debug("Could not identify main content for %s; using body", url)
            main_node = soup.body or soup

        markdown = html_to_markdown(
            str(main_node),
            heading_style="ATX",
            bullets="-",
            strip=["script", "style"],
        )

        markdown = self._clean_markdown(markdown)

        return ExtractedContent(
            title=title,
            markdown=markdown,
        )

    def extract_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")

        # Wichtig:
        # Vor dem Sammeln der Links entfernen wir Header, Nav, Sidebar, Footer etc.
        # Dadurch werden Menülinks nicht mehr in die Crawl-Queue aufgenommen.
        self._remove_nodes(soup, self.link_exclude_selectors)

        links: list[str] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not href:
                continue

            href = href.strip()
            if not href:
                continue

            lower = href.lower()
            if lower.startswith(("mailto:", "tel:", "javascript:", "data:")):
                continue

            links.append(href)

        return links

    def _remove_nodes(self, soup: BeautifulSoup, selectors: list[str]) -> None:
        for selector in selectors:
            try:
                nodes = soup.select(selector)
            except Exception as exc:
                logger.warning("Invalid CSS selector %r ignored: %s", selector, exc)
                continue

            for node in nodes:
                node.decompose()

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        candidates: list[str] = []

        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            candidates.append(str(og_title["content"]))

        twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
        if twitter_title and twitter_title.get("content"):
            candidates.append(str(twitter_title["content"]))

        if soup.title and soup.title.string:
            candidates.append(soup.title.string)

        h1 = soup.find("h1")
        if h1:
            candidates.append(h1.get_text(" ", strip=True))

        for candidate in candidates:
            cleaned = self._clean_text(candidate)
            if cleaned:
                return cleaned

        return None

    def _select_main_content(self, soup: BeautifulSoup) -> Tag | None:
        candidates: list[Tag] = []

        for selector in MAIN_CONTENT_SELECTORS:
            candidates.extend(
                node for node in soup.select(selector) if isinstance(node, Tag)
            )

        if not candidates and soup.body:
            direct_candidates = [
                child for child in soup.body.find_all(recursive=False) if isinstance(child, Tag)
            ]
            candidates.extend(direct_candidates)

        if not candidates:
            return None

        def score(node: Tag) -> int:
            text = node.get_text(" ", strip=True)
            paragraph_count = len(node.find_all("p"))
            heading_count = len(node.find_all(re.compile(r"^h[1-6]$")))
            code_count = len(node.find_all(["pre", "code"]))
            list_count = len(node.find_all(["ul", "ol"]))
            table_count = len(node.find_all("table"))

            return (
                len(text)
                + paragraph_count * 80
                + heading_count * 40
                + code_count * 50
                + list_count * 30
                + table_count * 60
            )

        return max(candidates, key=score)

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _clean_markdown(self, markdown: str) -> str:
        markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")

        lines = [line.rstrip() for line in markdown.split("\n")]

        cleaned_lines: list[str] = []
        blank_count = 0

        for line in lines:
            if line.strip():
                blank_count = 0
                cleaned_lines.append(line)
            else:
                blank_count += 1
                if blank_count <= 2:
                    cleaned_lines.append("")

        markdown = "\n".join(cleaned_lines).strip()
        markdown = re.sub(r"\n{4,}", "\n\n\n", markdown)

        return markdown + "\n" if markdown else ""

    def _dedupe_selectors(self, selectors: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for selector in selectors:
            selector = selector.strip()
            if not selector:
                continue

            if selector in seen:
                continue

            seen.add(selector)
            result.append(selector)

        return result