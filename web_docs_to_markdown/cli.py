import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from web_docs_to_markdown.config import AppConfig, load_config
from web_docs_to_markdown.crawler import Crawler
from web_docs_to_markdown.logging_config import configure_logging
from web_docs_to_markdown.utils import get_domain, normalize_url, slugify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="web-docs-to-markdown",
        description="Crawl documentation websites and save cleaned Markdown files.",
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to YAML configuration file.",
    )

    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Override base output directory from YAML configuration. "
            "Example: --output-dir output"
        ),
    )

    parser.add_argument(
        "--output-name",
        default=None,
        help=(
            "Set output run folder name below output_dir. "
            "Use 'auto' for an automatic name, 'none' for no subfolder, "
            "or a custom value like 'xray-template-building'."
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    try:
        config = load_config(Path(args.config))

        resolve_output_dir(
            config=config,
            output_dir_override=args.output_dir,
            output_name_override=args.output_name,
        )

        logger.info("Starting crawl")
        logger.info("Seeds: %s", ", ".join(config.seeds))
        logger.info("Output directory: %s", config.output_dir)

        crawler = Crawler(config)
        stats = crawler.run()

        logger.info(
            "Finished crawl: discovered=%s fetched=%s saved=%s skipped=%s errors=%s",
            stats.discovered,
            stats.fetched,
            stats.saved,
            stats.skipped,
            stats.errors,
        )

        return 0 if stats.errors == 0 else 2

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception:
        logger.exception("Fatal error")
        return 1


def resolve_output_dir(
    config: AppConfig,
    output_dir_override: str | None = None,
    output_name_override: str | None = None,
) -> None:
    base_output_dir = Path(output_dir_override) if output_dir_override else config.output_dir

    output_name = (
        output_name_override
        if output_name_override is not None
        else config.storage.output_name
    )

    output_name = str(output_name or "auto").strip()

    if output_name.lower() in {"none", "flat", "."}:
        config.output_dir = base_output_dir
        return

    if output_name.lower() == "auto":
        config.output_dir = base_output_dir / build_default_output_name(config)
        return

    config.output_dir = base_output_dir / slugify(output_name, max_length=120)


def build_default_output_name(config: AppConfig) -> str:
    first_seed = config.seeds[0]
    normalized_seed = normalize_url(first_seed) or first_seed

    domain = get_domain(normalized_seed)
    domain_slug = slugify(domain or "crawl", max_length=70)

    path_slug = build_path_slug(normalized_seed)

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")

    if path_slug:
        name = f"{domain_slug}-{path_slug}-{timestamp}"
    else:
        name = f"{domain_slug}-{timestamp}"

    return slugify(name, max_length=140)


def build_path_slug(url: str) -> str:
    parsed = urlparse(url)
    path = unquote(parsed.path or "").strip("/")

    if not path:
        return ""

    parts = [part for part in path.split("/") if part]

    if not parts:
        return ""

    # Prefer the last meaningful path segment.
    # Example:
    # /space/XRAY/301504485/Template+Building
    # -> template-building
    last_part = parts[-1]

    # Ignore generic index-like endings.
    if last_part.lower() in {"index", "index.html", "home", "docs"} and len(parts) > 1:
        last_part = parts[-2]

    return slugify(last_part, max_length=50)


if __name__ == "__main__":
    raise SystemExit(main())