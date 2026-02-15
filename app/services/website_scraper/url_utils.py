"""URL validation, normalisation and priority helpers for the website crawler."""
from __future__ import annotations

from typing import Optional
from urllib.parse import urljoin, urlparse


def is_valid_url(url: str) -> bool:
    """Return ``True`` when *url* uses an ``http`` or ``https`` scheme."""

    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ("http", "https")
    except ValueError:
        return False


def is_same_domain(base_url: str, url: str) -> bool:
    """Return ``True`` when *url* shares the same netloc as *base_url*."""

    try:
        return urlparse(base_url).netloc == urlparse(url).netloc
    except ValueError:
        return False


_MEDIA_EXTENSIONS = frozenset([
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico",
    ".mp4", ".webm", ".ogg", ".mp3", ".wav", ".flac", ".avi", ".mov",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".tar", ".gz", ".7z",
    ".css", ".js", ".json", ".xml",
])


def is_media_file(url: str) -> bool:
    """Return ``True`` when the URL path ends with a known media extension."""

    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in _MEDIA_EXTENSIONS)


_CONTACT_KEYWORDS = [
    "contact", "nous-contacter", "contactez-nous", "contactez",
    "about-us", "a-propos", "about", "qui-sommes-nous",
    "equipe", "team", "info", "mention", "legal", "coordonnee",
]


def get_url_priority(url: str) -> int:
    """Lower return value ⇒ higher crawl priority.

    Contact-like pages get the highest priority, the homepage a medium one,
    all other pages the lowest.
    """

    path = urlparse(url).path.lower()
    for idx, keyword in enumerate(_CONTACT_KEYWORDS):
        if keyword in path:
            return idx
    if path in ("/", "", "/index.html", "/index.php"):
        return 10
    return 20


def normalize_url(base_url: str, url: str) -> Optional[str]:
    """Resolve *url* against *base_url*, stripping fragments and media links."""

    if not url or url.startswith("#") or url.startswith("mailto:") or url.startswith("tel:"):
        return None
    try:
        normalized = urljoin(base_url, url)
        if is_valid_url(normalized) and not is_media_file(normalized):
            return normalized.split("#")[0]
        return None
    except Exception:  # noqa: BLE001
        return None
