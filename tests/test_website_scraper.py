"""Tests for the website_scraper extractors and url_utils modules."""
from __future__ import annotations

import pytest

from app.services.website_scraper.extractors import (
    extract_emails,
    extract_phones,
    extract_social_links,
    needs_browser_rendering,
)
from app.services.website_scraper.url_utils import (
    get_url_priority,
    is_media_file,
    is_same_domain,
    is_valid_url,
    normalize_url,
)


# ──────────────────────────────────────────────────────────────────────────────
# extract_phones
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractPhones:
    def test_extracts_mobile_phones(self) -> None:
        text = "Appelez-nous au 06 12 34 56 78 ou au 07.98.76.54.32."
        mobiles, nationals = extract_phones(text)
        assert len(mobiles) == 2
        assert "+33612345678" in mobiles
        assert "+33798765432" in mobiles
        assert nationals == []

    def test_extracts_national_phones(self) -> None:
        text = "Standard : 01 23 45 67 89"
        mobiles, nationals = extract_phones(text)
        assert mobiles == []
        assert len(nationals) == 1
        assert "+33123456789" in nationals

    def test_international_format(self) -> None:
        text = "Tél : +33 6 12 34 56 78"
        mobiles, _ = extract_phones(text)
        assert "+33612345678" in mobiles

    def test_dedup(self) -> None:
        text = "06 12 34 56 78 et aussi 06 12 34 56 78"
        mobiles, _ = extract_phones(text)
        assert len(mobiles) == 1

    def test_national_excluded_when_also_mobile(self) -> None:
        # A number that somehow matches both patterns should not appear in both.
        text = "06 12 34 56 78"
        mobiles, nationals = extract_phones(text)
        assert "+33612345678" in mobiles
        assert "+33612345678" not in nationals

    def test_empty_text(self) -> None:
        mobiles, nationals = extract_phones("")
        assert mobiles == []
        assert nationals == []


# ──────────────────────────────────────────────────────────────────────────────
# extract_emails
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractEmails:
    def test_basic(self) -> None:
        text = "contact@example.com ou info@acme.fr"
        emails = extract_emails(text)
        assert set(emails) == {"contact@example.com", "info@acme.fr"}

    def test_dedup(self) -> None:
        text = "a@b.com a@b.com"
        assert extract_emails(text) == ["a@b.com"]

    def test_no_emails(self) -> None:
        assert extract_emails("pas d'adresse ici") == []


# ──────────────────────────────────────────────────────────────────────────────
# extract_social_links
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractSocialLinks:
    def test_facebook(self) -> None:
        html = '<a href="https://www.facebook.com/mybiz">FB</a>'
        result = extract_social_links(html)
        assert result["facebook"] is not None
        assert "facebook.com/mybiz" in result["facebook"]

    def test_facebook_exclusion(self) -> None:
        html = '<a href="https://developers.facebook.com/docs">Dev</a>'
        result = extract_social_links(html)
        assert result["facebook"] is None

    def test_facebook_login_excluded(self) -> None:
        html = '<a href="https://www.facebook.com/login.php">Log in</a>'
        result = extract_social_links(html)
        assert result["facebook"] is None

    def test_instagram(self) -> None:
        html = '<a href="https://www.instagram.com/mybiz">IG</a>'
        result = extract_social_links(html)
        assert result["instagram"] is not None
        assert "instagram.com/mybiz" in result["instagram"]

    def test_twitter_x_dot_com(self) -> None:
        html = '<a href="https://x.com/mybiz">X</a>'
        result = extract_social_links(html)
        assert result["twitter"] is not None

    def test_linkedin_company(self) -> None:
        html = '<a href="https://www.linkedin.com/company/mybiz">LI</a>'
        result = extract_social_links(html)
        assert result["linkedin"] is not None

    def test_no_links(self) -> None:
        result = extract_social_links("nothing here")
        assert all(v is None for v in result.values())


# ──────────────────────────────────────────────────────────────────────────────
# needs_browser_rendering
# ──────────────────────────────────────────────────────────────────────────────


class TestNeedsBrowserRendering:
    def test_minimal_content(self) -> None:
        assert needs_browser_rendering("<html><body>Hi</body></html>") is True

    def test_rich_content(self) -> None:
        links = "".join(f'<a href="/p{i}">link {i}</a>' for i in range(10))
        body = "A" * 300
        html = f"<html><body>{body}{links}</body></html>"
        assert needs_browser_rendering(html) is False

    def test_vue_framework_detected(self) -> None:
        html = '<html><body data-vue="true">' + "A" * 300 + "</body></html>"
        assert needs_browser_rendering(html) is True


# ──────────────────────────────────────────────────────────────────────────────
# URL utilities
# ──────────────────────────────────────────────────────────────────────────────


class TestIsValidUrl:
    def test_valid(self) -> None:
        assert is_valid_url("https://example.com") is True
        assert is_valid_url("http://localhost:8080/path") is True

    def test_invalid(self) -> None:
        assert is_valid_url("ftp://files.example.com") is False
        assert is_valid_url("not-a-url") is False
        assert is_valid_url("") is False


class TestIsSameDomain:
    def test_same(self) -> None:
        assert is_same_domain("https://example.com/a", "https://example.com/b") is True

    def test_different(self) -> None:
        assert is_same_domain("https://a.com/x", "https://b.com/y") is False


class TestIsMediaFile:
    def test_media(self) -> None:
        assert is_media_file("https://example.com/photo.jpg") is True
        assert is_media_file("https://example.com/style.css") is True

    def test_not_media(self) -> None:
        assert is_media_file("https://example.com/about") is False
        assert is_media_file("https://example.com/contact.html") is False


class TestGetUrlPriority:
    def test_contact_page(self) -> None:
        assert get_url_priority("https://example.com/contact") == 0

    def test_homepage(self) -> None:
        assert get_url_priority("https://example.com/") == 10

    def test_other_page(self) -> None:
        assert get_url_priority("https://example.com/products") == 20


class TestNormalizeUrl:
    def test_relative(self) -> None:
        assert normalize_url("https://example.com/a", "/b") == "https://example.com/b"

    def test_fragment_stripped(self) -> None:
        result = normalize_url("https://example.com", "https://example.com/page#section")
        assert result == "https://example.com/page"

    def test_mailto_ignored(self) -> None:
        assert normalize_url("https://example.com", "mailto:a@b.com") is None

    def test_tel_ignored(self) -> None:
        assert normalize_url("https://example.com", "tel:+33612345678") is None

    def test_media_ignored(self) -> None:
        assert normalize_url("https://example.com", "/assets/logo.png") is None
