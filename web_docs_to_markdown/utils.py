from __future__ import annotations

import hashlib
import posixpath
import re
from urllib.parse import (
    parse_qsl,
    quote,
    unquote,
    urlencode,
    urldefrag,
    urljoin,
    urlparse,
    urlunparse,
)


TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "dclid",
    "gbraid",
    "wbraid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "vero_id",
    "_hsenc",
    "_hsmi",
    "ref",
    "ref_src",
}


NON_HTML_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bmp",
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".eot",
    ".epub",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".map",
    ".mov",
    ".mp3",
    ".mp4",
    ".odp",
    ".ods",
    ".odt",
    ".otf",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".rss",
    ".svg",
    ".tar",
    ".tgz",
    ".tif",
    ".tiff",
    ".ttf",
    ".txt",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}


def stable_id(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def remove_tracking_query_params(query: str) -> str:
    pairs = parse_qsl(query, keep_blank_values=True)
    cleaned: list[tuple[str, str]] = []

    for key, value in pairs:
        lower_key = key.lower()
        if lower_key.startswith("utm_"):
            continue
        if lower_key in TRACKING_QUERY_PARAMS:
            continue
        cleaned.append((key, value))

    cleaned.sort(key=lambda item: (item[0], item[1]))
    return urlencode(cleaned, doseq=True)


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    if base_url:
        url = urljoin(base_url, url)

    url, _fragment = urldefrag(url)
    parsed = urlparse(url)

    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    if not parsed.netloc:
        return None

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""

    if not hostname:
        return None

    port = parsed.port
    netloc = hostname

    if port and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"

    raw_path = parsed.path or "/"
    decoded_path = unquote(raw_path)

    normalized_path = posixpath.normpath(decoded_path)
    if decoded_path.endswith("/") and not normalized_path.endswith("/"):
        normalized_path += "/"

    if not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path

    # Avoid turning the root path into "/."
    if normalized_path == "/.":
        normalized_path = "/"

    path = quote(normalized_path, safe="/-._~")

    query = remove_tracking_query_params(parsed.query)

    return urlunparse((scheme, netloc, path, "", query, ""))


def get_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()


def get_origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def is_probably_html_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return not any(path.endswith(ext) for ext in NON_HTML_EXTENSIONS)


def slugify(value: str, max_length: int = 90) -> str:
    value = unquote(value)
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    if not value:
        value = "index"
    return value[:max_length].strip("-") or "index"


def count_words(markdown: str) -> int:
    words = re.findall(r"\b\w+\b", markdown)
    return len(words)