# web-docs-to-markdown

`web-docs-to-markdown` is a dockerized Python 3.13 CLI tool for crawling external documentation websites and saving cleaned pages as Markdown files.

The generated output is designed to be useful as a knowledge source for RAG systems such as:

- LlamaIndex
- LangChain
- OpenAI Vector Stores
- Other vector database ingestion pipelines

## Features

- Python 3.13
- Docker and Docker Compose support
- YAML-based configuration
- CLI using `argparse`
- HTTP client with:
  - configurable User-Agent
  - request timeouts
  - simple retry handling
- Optional JavaScript rendering with Playwright and Chromium
- Respects `robots.txt`
- Optional same-domain-only crawling
- Configurable maximum crawl depth
- Configurable maximum number of pages
- Include/exclude regex URL filters
- URL normalization
- Removes tracking query parameters:
  - `utm_*`
  - `fbclid`
  - `gclid`
  - `msclkid`
  - and other common tracking parameters
- Extracts main page content where possible
- Removes navigation/footer/sidebar/header content where possible
- Can exclude links from menus, navigation, sidebars, breadcrumbs, TOCs, and footers
- Converts HTML to Markdown
- Saves Markdown files with YAML frontmatter
- Generates:
  - `manifest.jsonl`
  - `llamaindex_documents.jsonl`
- Supports automatic or custom output folder names
- Robust error handling and useful logs

## LlamaIndex vs LangChain

For this use case, **LlamaIndex is more suitable**.

This project focuses on preparing clean document-like records for later indexing and retrieval. LlamaIndex is particularly strong for document ingestion, indexing, metadata-aware retrieval, and RAG-oriented document abstractions.

LangChain is excellent for chain orchestration, tools, agents, and application workflows, but for producing and ingesting document corpora, LlamaIndex is usually the more direct fit.

This project therefore emits a LlamaIndex-compatible JSONL file in addition to Markdown and a manifest.

## Quick start with Docker Compose

Copy the example config into the project folder:

```bash
cd web-docs-to-markdown
cp config.example.yml config.yml
```

Edit `config.yml` and set your documentation URL or URLs:

```yaml
seeds:
  - "https://docs.example.com/guide/getting-started"
```

Run:

```bash
docker compose up --build
```

By default, output will be written to a useful automatically named subfolder:

```text
output/
└── docs-example-com-getting-started-20260728-081419/
    ├── manifest.jsonl
    ├── llamaindex_documents.jsonl
    └── markdown/
```

The exact timestamp will differ.

## Run locally without Docker

Requires Python 3.13.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m playwright install chromium

cp config.example.yml config.yml
python -m web_docs_to_markdown --config config.yml
```

If you do not use JavaScript rendering, you can set:

```yaml
browser:
  enabled: false
```

In that case, Playwright is not used at runtime.

## CLI usage

```bash
python -m web_docs_to_markdown --config config.yml
```

Options:

```bash
python -m web_docs_to_markdown --help
```

Example with verbose logging:

```bash
python -m web_docs_to_markdown \
  --config config.yml \
  --verbose
```

Example with a custom output base directory:

```bash
python -m web_docs_to_markdown \
  --config config.yml \
  --output-dir output
```

Example with a custom output run folder name:

```bash
python -m web_docs_to_markdown \
  --config config.yml \
  --output-name my-docs-crawl
```

This writes to:

```text
output/my-docs-crawl/
```

Example without a run subfolder:

```bash
python -m web_docs_to_markdown \
  --config config.yml \
  --output-name none
```

This writes directly to:

```text
output/
```

## Docker Compose usage

The default `docker-compose.yml` mounts:

```yaml
volumes:
  - ./config.yml:/app/config.yml:ro
  - ./output:/app/output
```

Therefore `config.yml` should be located directly inside the project folder:

```text
web-docs-to-markdown/
├── config.yml
├── config.example.yml
├── docker-compose.yml
└── ...
```

Run:

```bash
docker compose up --build
```

To enable verbose logs, adjust the command in `docker-compose.yml`:

```yaml
command:
  - python
  - -m
  - web_docs_to_markdown
  - --config
  - /app/config.yml
  - --verbose
```

To set a custom output name via Docker Compose:

```yaml
command:
  - python
  - -m
  - web_docs_to_markdown
  - --config
  - /app/config.yml
  - --output-name
  - my-docs-crawl
```

## Configuration

Example:

```yaml
seeds:
  - "https://docs.example.com/guide/getting-started"

output_dir: "output"

http:
  user_agent: "web-docs-to-markdown/1.0 (+https://example.com/bot)"
  timeout_seconds: 30
  max_retries: 2

browser:
  enabled: true
  headless: true
  wait_until: "networkidle"
  extra_wait_ms: 1500
  wait_for_selector: ""
  block_resources: true
  blocked_resource_types:
    - "image"
    - "media"
    - "font"

crawl:
  respect_robots_txt: true
  same_domain_only: true
  max_depth: 1
  max_pages: 20
  request_delay_seconds: 0.5

  include_patterns: []
  exclude_patterns:
    - "/search"
    - "/login"
    - "\\.pdf$"

  link_exclude_selectors:
    - "header"
    - "nav"
    - "footer"
    - "aside"
    - "[role='navigation']"
    - ".sidebar"
    - ".toc"
    - ".breadcrumb"
    - ".breadcrumbs"

markdown:
  min_content_chars: 100
  include_frontmatter: true

  remove_selectors:
    - "script"
    - "style"
    - "noscript"
    - "header"
    - "nav"
    - "footer"
    - "aside"
    - "[role='navigation']"
    - ".sidebar"
    - ".toc"
    - ".breadcrumb"
    - ".breadcrumbs"

storage:
  overwrite: true
  output_name: "auto"
```

## Output folder naming

The project supports automatic, custom, or flat output paths.

### Automatic output name

Default:

```yaml
storage:
  output_name: "auto"
```

Example result:

```text
output/docs-example-com-getting-started-20260728-081419/
```

The generated name is based on:

- the seed domain
- the last meaningful URL path segment
- a timestamp

### Custom output name

```yaml
storage:
  output_name: "my-docs-crawl"
```

Example result:

```text
output/my-docs-crawl/
```

You can also override this from the CLI:

```bash
python -m web_docs_to_markdown \
  --config config.yml \
  --output-name my-docs-crawl
```

### No output subfolder

```yaml
storage:
  output_name: "none"
```

Example result:

```text
output/
├── manifest.jsonl
├── llamaindex_documents.jsonl
└── markdown/
```

This is useful if you want the old flat output behavior.

## JavaScript rendering with Playwright

Some documentation sites render their main content with JavaScript. This is common for:

- SPA-based documentation
- Confluence-like documentation
- React/Vue/Angular documentation
- docs with client-side routing
- docs where the HTML returned by `requests` contains little or no page content

For these pages, enable Playwright:

```yaml
browser:
  enabled: true
  headless: true
  wait_until: "networkidle"
  extra_wait_ms: 1500
```

When using Docker, Chromium is installed automatically during the image build.

When running locally, install the browser once:

```bash
python -m playwright install chromium
```

For some pages, `networkidle` can be slow. If pages load reliably, you can switch to:

```yaml
browser:
  wait_until: "domcontentloaded"
```

If content appears late, increase:

```yaml
browser:
  extra_wait_ms: 3000
```

If you know a stable selector for the main content area, use:

```yaml
browser:
  wait_for_selector: "main"
```

or:

```yaml
browser:
  wait_for_selector: "[role='main']"
```

## Excluding navigation, menus, headers, footers, and sidebars

The project supports two separate selector lists:

### `markdown.remove_selectors`

These selectors are removed before HTML is converted to Markdown.

Use this to remove unwanted content from the final Markdown files.

Example:

```yaml
markdown:
  remove_selectors:
    - "header"
    - "nav"
    - "footer"
    - "aside"
    - "[role='navigation']"
    - ".sidebar"
    - ".toc"
    - ".breadcrumb"
    - ".breadcrumbs"
```

### `crawl.link_exclude_selectors`

These selectors are removed before links are collected for crawling.

Use this to prevent links from menus, sidebars, breadcrumbs, footers, pagination, or table-of-contents blocks from being added to the crawl queue.

Example:

```yaml
crawl:
  link_exclude_selectors:
    - "header"
    - "nav"
    - "footer"
    - "aside"
    - "[role='navigation']"
    - ".sidebar"
    - ".toc"
    - ".breadcrumb"
    - ".breadcrumbs"
    - ".pagination"
```

This is especially useful when you only want to crawl documentation pages linked from the actual page body, not the whole site navigation.

## CSS selectors vs XPath

The project currently uses BeautifulSoup CSS selectors.

That means you should use **CSS selectors**, not XPath.

Examples:

| Goal | CSS selector |
|---|---|
| Remove all `<header>` elements | `header` |
| Remove all `<nav>` elements | `nav` |
| Remove all `<footer>` elements | `footer` |
| Remove all `<aside>` elements | `aside` |
| Remove elements with `role="navigation"` | `[role='navigation']` |
| Remove element with ID `content` | `#content` |
| Remove elements with class `sidebar` | `.sidebar` |
| Remove elements where class contains `sidebar` | `[class*='sidebar']` |
| Remove elements where class contains `toc` | `[class*='toc']` |
| Remove elements with test id | `[data-testid='page-tree']` |

XPath examples and their CSS equivalents:

| XPath | CSS equivalent |
|---|---|
| `//header` | `header` |
| `//nav` | `nav` |
| `//*[@role='navigation']` | `[role='navigation']` |
| `//*[@id='content']` | `#content` |
| `//*[contains(@class, 'sidebar')]` | `[class*='sidebar']` |

## Include and exclude URL patterns

URL include and exclude patterns are regular expressions.

Example: only crawl docs below `/guide/`:

```yaml
crawl:
  include_patterns:
    - "https://docs\\.example\\.com/guide/"
```

Example: exclude login, search, and binary files:

```yaml
crawl:
  exclude_patterns:
    - "/search"
    - "/login"
    - "\\.pdf$"
    - "\\.zip$"
    - "\\.png$"
    - "\\.jpg$"
```

If `include_patterns` is empty, URLs are allowed unless rejected by:

- `same_domain_only`
- `exclude_patterns`
- `robots.txt`
- non-HTML URL filtering

## Output files

Each run folder contains:

```text
manifest.jsonl
llamaindex_documents.jsonl
markdown/
```

Example:

```text
output/my-docs-crawl/
├── manifest.jsonl
├── llamaindex_documents.jsonl
└── markdown/
    └── docs-example-com/
        └── getting-started-a1b2c3d4e5.md
```

### Markdown files

Markdown files are written under:

```text
output/<run-name>/markdown/<domain>/
```

Each file includes YAML frontmatter:

```yaml
---
id: "..."
source_url: "https://docs.example.com/guide/getting-started"
final_url: "https://docs.example.com/guide/getting-started"
title: "Getting started"
crawled_at: "2026-07-28T12:00:00Z"
depth: 0
status_code: 200
content_type: "text/html"
sha256: "..."
word_count: 1234
char_count: 5678
markdown_path: "markdown/docs-example-com/getting-started-a1b2c3d4e5.md"
---
```

### `manifest.jsonl`

One JSON object per saved page.

Useful for:

- auditability
- debugging
- ingestion tracking
- incremental processing
- identifying source URLs and output paths

### `llamaindex_documents.jsonl`

One JSON object per saved page in a simple LlamaIndex-friendly format:

```json
{
  "id_": "abc123",
  "text": "Markdown content...",
  "metadata": {
    "source_url": "https://docs.example.com/guide/getting-started",
    "title": "Getting started"
  }
}
```

You can ingest this file with a custom JSONL reader or load it into your own ingestion pipeline and create LlamaIndex `Document` objects.

Example:

```python
import json
from llama_index.core import Document

documents = []

with open("output/my-docs-crawl/llamaindex_documents.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        documents.append(
            Document(
                id_=row["id_"],
                text=row["text"],
                metadata=row["metadata"],
            )
        )
```

## Troubleshooting

### No Markdown files are generated

Run with verbose logging:

```bash
python -m web_docs_to_markdown \
  --config config.yml \
  --verbose
```

With Docker Compose, add `--verbose` to the command.

Common reasons:

- the page is blocked by `robots.txt`
- the page is outside the allowed domain
- the URL matches an exclude pattern
- the response is not HTML
- the extracted content is shorter than `markdown.min_content_chars`
- JavaScript rendering is required but disabled

For debugging, temporarily set:

```yaml
crawl:
  max_depth: 0
  max_pages: 1

markdown:
  min_content_chars: 0
```

### JavaScript page still has little content

Try:

```yaml
browser:
  enabled: true
  wait_until: "networkidle"
  extra_wait_ms: 3000
```

Or wait for a known content selector:

```yaml
browser:
  wait_for_selector: "main"
```

### Too many irrelevant pages are crawled

Use a stricter include pattern:

```yaml
crawl:
  include_patterns:
    - "https://docs\\.example\\.com/guide/"
```

Also add menu/sidebar selectors to:

```yaml
crawl:
  link_exclude_selectors:
    - "header"
    - "nav"
    - "footer"
    - "aside"
    - ".sidebar"
    - ".toc"
```

### Markdown contains navigation or footer content

Add selectors to:

```yaml
markdown:
  remove_selectors:
    - "header"
    - "nav"
    - "footer"
    - "aside"
    - ".sidebar"
```

Use your browser's Inspect tool to find stable selectors.

Prefer stable selectors like:

```css
main
article
[role='main']
[role='navigation']
[data-testid='page-tree']
```

Avoid dynamic generated class names like:

```css
.css-1abc23x
```

because they may change between deployments.

## Notes on responsible crawling

Please crawl responsibly:

- Keep `respect_robots_txt: true`
- Use a clear User-Agent
- Use conservative `max_pages`
- Use a non-zero `request_delay_seconds`
- Avoid crawling sites without permission when unsure