from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class HTTPConfig:
    user_agent: str = "web-docs-to-markdown/1.0"
    timeout_seconds: float = 30.0
    max_retries: int = 2


@dataclass
class BrowserConfig:
    enabled: bool = False
    headless: bool = True
    wait_until: str = "networkidle"
    extra_wait_ms: int = 1000
    wait_for_selector: str = ""
    block_resources: bool = True
    blocked_resource_types: list[str] = field(default_factory=lambda: ["image", "media", "font"])


@dataclass
class CrawlConfig:
    respect_robots_txt: bool = True
    same_domain_only: bool = True
    max_depth: int = 2
    max_pages: int = 100
    request_delay_seconds: float = 0.25
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    link_exclude_selectors: list[str] = field(default_factory=list)


@dataclass
class MarkdownConfig:
    min_content_chars: int = 200
    include_frontmatter: bool = True
    remove_selectors: list[str] = field(default_factory=list)


@dataclass
class StorageConfig:
    overwrite: bool = True

    # "auto"  => creates output/<domain>-<optional-path>-<timestamp>/
    # "none"  => writes directly into output_dir
    # custom  => creates output/<custom-name>/
    output_name: str = "auto"


@dataclass
class AppConfig:
    seeds: list[str]
    output_dir: Path = Path("output")
    http: HTTPConfig = field(default_factory=HTTPConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    crawl: CrawlConfig = field(default_factory=CrawlConfig)
    markdown: MarkdownConfig = field(default_factory=MarkdownConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise ValueError("Expected a list.")

    return [str(item) for item in value]


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ValueError("Configuration file must contain a YAML mapping/object.")

    seeds = raw.get("seeds") or []
    if not isinstance(seeds, list) or not all(isinstance(seed, str) for seed in seeds):
        raise ValueError("'seeds' must be a list of URL strings.")

    seeds = [seed.strip() for seed in seeds if seed.strip()]
    if not seeds:
        raise ValueError("At least one seed URL is required.")

    http_raw = _dict_or_empty(raw.get("http"))
    browser_raw = _dict_or_empty(raw.get("browser"))
    crawl_raw = _dict_or_empty(raw.get("crawl"))
    markdown_raw = _dict_or_empty(raw.get("markdown"))
    storage_raw = _dict_or_empty(raw.get("storage"))

    config = AppConfig(
        seeds=seeds,
        output_dir=Path(raw.get("output_dir", "output")),
        http=HTTPConfig(
            user_agent=str(http_raw.get("user_agent", "web-docs-to-markdown/1.0")),
            timeout_seconds=float(http_raw.get("timeout_seconds", 30.0)),
            max_retries=int(http_raw.get("max_retries", 2)),
        ),
        browser=BrowserConfig(
            enabled=bool(browser_raw.get("enabled", False)),
            headless=bool(browser_raw.get("headless", True)),
            wait_until=str(browser_raw.get("wait_until", "networkidle")),
            extra_wait_ms=int(browser_raw.get("extra_wait_ms", 1000)),
            wait_for_selector=str(browser_raw.get("wait_for_selector", "") or ""),
            block_resources=bool(browser_raw.get("block_resources", True)),
            blocked_resource_types=_str_list(
                browser_raw.get("blocked_resource_types", ["image", "media", "font"])
            ),
        ),
        crawl=CrawlConfig(
            respect_robots_txt=bool(crawl_raw.get("respect_robots_txt", True)),
            same_domain_only=bool(crawl_raw.get("same_domain_only", True)),
            max_depth=int(crawl_raw.get("max_depth", 2)),
            max_pages=int(crawl_raw.get("max_pages", 100)),
            request_delay_seconds=float(crawl_raw.get("request_delay_seconds", 0.25)),
            include_patterns=_str_list(crawl_raw.get("include_patterns") or []),
            exclude_patterns=_str_list(crawl_raw.get("exclude_patterns") or []),
            link_exclude_selectors=_str_list(crawl_raw.get("link_exclude_selectors") or []),
        ),
        markdown=MarkdownConfig(
            min_content_chars=int(markdown_raw.get("min_content_chars", 200)),
            include_frontmatter=bool(markdown_raw.get("include_frontmatter", True)),
            remove_selectors=_str_list(markdown_raw.get("remove_selectors") or []),
        ),
        storage=StorageConfig(
            overwrite=bool(storage_raw.get("overwrite", True)),
            output_name=str(storage_raw.get("output_name", "auto") or "auto"),
        ),
    )

    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    if config.http.timeout_seconds <= 0:
        raise ValueError("http.timeout_seconds must be greater than zero.")

    if config.http.max_retries < 0:
        raise ValueError("http.max_retries must be zero or greater.")

    if config.browser.wait_until not in {
        "commit",
        "domcontentloaded",
        "load",
        "networkidle",
    }:
        raise ValueError(
            "browser.wait_until must be one of: commit, domcontentloaded, load, networkidle."
        )

    if config.browser.extra_wait_ms < 0:
        raise ValueError("browser.extra_wait_ms must be zero or greater.")

    if config.crawl.max_depth < 0:
        raise ValueError("crawl.max_depth must be zero or greater.")

    if config.crawl.max_pages <= 0:
        raise ValueError("crawl.max_pages must be greater than zero.")

    if config.crawl.request_delay_seconds < 0:
        raise ValueError("crawl.request_delay_seconds must be zero or greater.")

    if config.markdown.min_content_chars < 0:
        raise ValueError("markdown.min_content_chars must be zero or greater.")
