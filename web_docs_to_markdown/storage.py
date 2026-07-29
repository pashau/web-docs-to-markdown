from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import yaml

from web_docs_to_markdown.config import AppConfig
from web_docs_to_markdown.models import PageDocument
from web_docs_to_markdown.utils import slugify, stable_id

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.markdown_dir = self.output_dir / "markdown"
        self.manifest_path = self.output_dir / "manifest.jsonl"
        self.llamaindex_path = self.output_dir / "llamaindex_documents.jsonl"

    def prepare(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

        if self.config.storage.overwrite:
            for path in [self.manifest_path, self.llamaindex_path]:
                if path.exists():
                    path.unlink()

    def save(self, document: PageDocument) -> Path:
        markdown_path = self._markdown_path(document)

        markdown_path.parent.mkdir(parents=True, exist_ok=True)

        metadata = self._metadata(document, markdown_path)

        if self.config.markdown.include_frontmatter:
            frontmatter = yaml.safe_dump(
                metadata,
                sort_keys=False,
                allow_unicode=True,
                width=1000,
            ).strip()
            markdown_text = f"---\n{frontmatter}\n---\n\n{document.markdown}"
        else:
            markdown_text = document.markdown

        markdown_path.write_text(markdown_text, encoding="utf-8")

        self._append_manifest(document, markdown_path, metadata)
        self._append_llamaindex_document(document, markdown_path, metadata)

        logger.debug("Saved %s", markdown_path)
        return markdown_path

    def _markdown_path(self, document: PageDocument) -> Path:
        parsed = urlparse(document.final_url)
        domain = slugify(parsed.netloc, max_length=120)

        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            base = "-".join(path_parts)
        else:
            base = "index"

        slug = slugify(base, max_length=100)
        unique_suffix = stable_id(document.final_url, length=10)

        filename = f"{slug}-{unique_suffix}.md"

        return self.markdown_dir / domain / filename

    def _metadata(self, document: PageDocument, markdown_path: Path) -> dict:
        return {
            "id": document.id,
            "source_url": document.source_url,
            "final_url": document.final_url,
            "title": document.title,
            "crawled_at": document.crawled_at,
            "depth": document.depth,
            "status_code": document.status_code,
            "content_type": document.content_type,
            "sha256": document.sha256,
            "word_count": document.word_count,
            "char_count": document.char_count,
            "markdown_path": str(markdown_path.relative_to(self.output_dir)),
        }

    def _append_manifest(
        self,
        document: PageDocument,
        markdown_path: Path,
        metadata: dict,
    ) -> None:
        row = {
            **metadata,
            "markdown_path": str(markdown_path.relative_to(self.output_dir)),
        }

        with self.manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _append_llamaindex_document(
        self,
        document: PageDocument,
        markdown_path: Path,
        metadata: dict,
    ) -> None:
        llamaindex_row = {
            "id_": document.id,
            "text": document.markdown,
            "metadata": {
                **metadata,
                "source": document.final_url,
                "file_path": str(markdown_path.relative_to(self.output_dir)),
            },
            "excluded_embed_metadata_keys": [],
            "excluded_llm_metadata_keys": [],
            "relationships": {},
        }

        with self.llamaindex_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(llamaindex_row, ensure_ascii=False) + "\n")