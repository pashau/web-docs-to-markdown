from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageDocument:
    id: str
    source_url: str
    final_url: str
    title: str | None
    markdown: str
    depth: int
    status_code: int
    content_type: str
    crawled_at: str
    sha256: str
    word_count: int
    char_count: int


@dataclass
class CrawlStats:
    discovered: int = 0
    fetched: int = 0
    saved: int = 0
    skipped: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors += 1
        self.error_messages.append(message)