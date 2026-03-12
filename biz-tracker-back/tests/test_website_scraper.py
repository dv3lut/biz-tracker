"""Tests for the website_scraper extractors and url_utils modules."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.website_scraper.extractors import (
    extract_emails,
    extract_mailto_emails,
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
from app.services.website_scraper import crawlers


# ──────────────────────────────────────────────────────────────────────────────
# extract_phones
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractPhones:
    def test_extracts_mobile_phones(self) -> None:
        text = "Appelez-nous au 06 12 34 56 78 ou au 07.98.76.54.32."
        mobiles, nationals, internationals = extract_phones(text)
        assert len(mobiles) == 2
        assert "+33612345678" in mobiles
        assert "+33798765432" in mobiles
        assert nationals == []
        assert internationals == []

    def test_extracts_national_phones(self) -> None:
        text = "Standard : 01 23 45 67 89"
        mobiles, nationals, internationals = extract_phones(text)
        assert mobiles == []
        assert len(nationals) == 1
        assert "+33123456789" in nationals
        assert internationals == []

    def test_extracts_plus33_optional_zero_national(self) -> None:
        text = "Tél: +33 (0)2 35 59 83 63"
        mobiles, nationals, internationals = extract_phones(text)
        assert mobiles == []
        assert "+33235598363" in nationals
        assert internationals == []

    def test_international_format(self) -> None:
        text = "Tél : +33 6 12 34 56 78"
        mobiles, _, internationals = extract_phones(text)
        assert "+33612345678" in mobiles
        assert internationals == []

    def test_dedup(self) -> None:
        text = "06 12 34 56 78 et aussi 06 12 34 56 78"
        mobiles, _, _ = extract_phones(text)
        assert len(mobiles) == 1

    def test_national_excluded_when_also_mobile(self) -> None:
        # A number that somehow matches both patterns should not appear in both.
        text = "06 12 34 56 78"
        mobiles, nationals, internationals = extract_phones(text)
        assert "+33612345678" in mobiles
        assert "+33612345678" not in nationals
        assert internationals == []

    def test_empty_text(self) -> None:
        mobiles, nationals, internationals = extract_phones("")
        assert mobiles == []
        assert nationals == []
        assert internationals == []

    def test_hyphen_separators(self) -> None:
        text = "Mobile: 06-12-34-56-78 / Fixe: 01-23-45-67-89"
        mobiles, nationals, internationals = extract_phones(text)
        assert "+33612345678" in mobiles
        assert "+33123456789" in nationals
        assert internationals == []

    def test_mixed_separators(self) -> None:
        text = "06.12-34 56.78"
        mobiles, _, _ = extract_phones(text)
        assert mobiles == ["+33612345678"]

    def test_ignores_incomplete_numbers(self) -> None:
        text = "Appelez le 06 12 34 56"
        mobiles, nationals, internationals = extract_phones(text)
        assert mobiles == []
        assert nationals == []
        assert internationals == []

    def test_extracts_non_fr_international_numbers(self) -> None:
        text = "International: +44 20 1234 5678"
        mobiles, nationals, internationals = extract_phones(text)
        assert mobiles == []
        assert nationals == []
        assert internationals == ["+442012345678"]

    def test_extracts_multiple_lines(self) -> None:
        text = """\
Contact 1: 06 11 22 33 44
Contact 2: 07 55 66 77 88
Standard: 03 44 55 66 77
"""
        mobiles, nationals, internationals = extract_phones(text)
        assert set(mobiles) == {"+33611223344", "+33755667788"}
        assert nationals == ["+33344556677"]
        assert internationals == []

    def test_extracts_multiple_international_numbers(self) -> None:
        text = "US: +1 202 555 0182 / PT: +351 21 123 45 67"
        mobiles, nationals, internationals = extract_phones(text)
        assert mobiles == []
        assert nationals == []
        assert set(internationals) == {"+12025550182", "+351211234567"}


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

    def test_trims_glued_suffix_after_common_tld(self) -> None:
        text = "pizzagourmande38@gmail.comcookies et pizzagourmande38@gmail.comdirecteur"
        emails = extract_emails(text)
        assert emails == ["pizzagourmande38@gmail.com"]

    def test_trims_glued_suffix_after_fr_tld(self) -> None:
        text = "contact@restaurant.frreservation"
        emails = extract_emails(text)
        assert emails == ["contact@restaurant.fr"]

    def test_keeps_long_tlds(self) -> None:
        text = "hello@startup.technology et ops@infra.solutions"
        emails = extract_emails(text)
        assert set(emails) == {"hello@startup.technology", "ops@infra.solutions"}

    def test_handles_common_punctuation_around_email(self) -> None:
        text = "(contact@acme.fr), [support@acme.com];"
        emails = extract_emails(text)
        assert set(emails) == {"contact@acme.fr", "support@acme.com"}

    def test_lowercases_output(self) -> None:
        text = "SALES@ACME.FR"
        emails = extract_emails(text)
        assert emails == ["sales@acme.fr"]

    def test_rejects_missing_tld(self) -> None:
        text = "admin@localhost"
        assert extract_emails(text) == []

    def test_extracts_subdomain_email(self) -> None:
        text = "admin@mail.ops.example.com"
        emails = extract_emails(text)
        assert emails == ["admin@mail.ops.example.com"]

    def test_extracts_multi_level_tld(self) -> None:
        text = "team@example.co.uk"
        emails = extract_emails(text)
        assert emails == ["team@example.co.uk"]

    def test_trims_glued_suffix_after_net_tld(self) -> None:
        text = "owner@business.netpromo"
        emails = extract_emails(text)
        assert emails == ["owner@business.net"]

    def test_trims_glued_suffix_after_org_tld(self) -> None:
        text = "association@domain.orgbureau"
        emails = extract_emails(text)
        assert emails == ["association@domain.org"]

    def test_returns_unique_results_even_when_found_twice(self) -> None:
        text = "x@y.comcookies puis x@y.com"
        emails = extract_emails(text)
        assert emails == ["x@y.com"]

    def test_strips_phone_prefix_two_digits(self) -> None:
        text = "94contact@restaurant.fr"
        emails = extract_emails(text)
        assert emails == ["contact@restaurant.fr"]

    def test_strips_phone_prefix_three_digits(self) -> None:
        text = "007info@example.com"
        emails = extract_emails(text)
        assert emails == ["info@example.com"]

    def test_phone_number_concatenated_with_email(self) -> None:
        text = "06 12 34 56 78contact@boulangerie.fr"
        emails = extract_emails(text)
        assert emails == ["contact@boulangerie.fr"]

    def test_preserves_numeric_email_with_dot_separator(self) -> None:
        text = "42.info@example.com"
        emails = extract_emails(text)
        assert emails == ["42.info@example.com"]


# ──────────────────────────────────────────────────────────────────────────────
# extract_mailto_emails
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractMailtoEmails:
    def test_extracts_mailto_link(self) -> None:
        html = '<a href="mailto:contact@boulangerie.fr">Nous contacter</a>'
        emails = extract_mailto_emails(html)
        assert emails == ["contact@boulangerie.fr"]

    def test_ignores_non_mailto_links(self) -> None:
        html = '<a href="https://example.com">Site</a>'
        emails = extract_mailto_emails(html)
        assert emails == []

    def test_strips_query_params(self) -> None:
        html = '<a href="mailto:info@acme.fr?subject=Devis">Devis</a>'
        emails = extract_mailto_emails(html)
        assert emails == ["info@acme.fr"]

    def test_multiple_mailto_dedup(self) -> None:
        html = (
            '<a href="mailto:a@b.com">A</a> '
            '<a href="mailto:a@b.com">A2</a> '
            '<a href="mailto:c@d.fr">C</a>'
        )
        emails = extract_mailto_emails(html)
        assert set(emails) == {"a@b.com", "c@d.fr"}

    def test_rejects_invalid_mailto(self) -> None:
        html = '<a href="mailto:not-an-email">Bad</a>'
        emails = extract_mailto_emails(html)
        assert emails == []


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

    def test_linkedin_strips_encoded_trailing_blob(self) -> None:
        html = (
            "https://www.linkedin.com/in/alice-pouyet-facchinetti-4035231b5/&quot;"
            "}]]],&quot;mobile&quot;:[0,{&quot;top&quot;:[0,344]}"
        )
        result = extract_social_links(html)
        assert result["linkedin"] == "https://www.linkedin.com/in/alice-pouyet-facchinetti-4035231b5/"

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


class TestCrawlerDispatcher:
    def test_js_rendering_merges_playwright_and_http_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        response = SimpleNamespace(ok=True, headers={"Content-Type": "text/html"}, text="<html>js</html>")

        monkeypatch.setattr(crawlers, "_get_requests_session", lambda: object())
        monkeypatch.setattr(crawlers, "_safe_get", lambda _session, _url, timeout=20: response)
        monkeypatch.setattr(crawlers, "needs_browser_rendering", lambda _html: True)
        monkeypatch.setattr(crawlers, "is_playwright_available", lambda: True)
        monkeypatch.setattr(
            crawlers,
            "crawl_with_browser",
            lambda *_args, **_kwargs: _async_result(
                {
                    "mobile_phones": ["+33612345678"],
                    "national_phones": [],
                    "international_phones": [],
                    "emails": [],
                    "facebook": None,
                    "instagram": None,
                    "twitter": None,
                    "linkedin": "https://linkedin.com/company/acme",
                }
            ),
        )
        monkeypatch.setattr(
            crawlers,
            "crawl_website",
            lambda *_args, **_kwargs: {
                "mobile_phones": [],
                "national_phones": ["+33123456789"],
                "international_phones": [],
                "emails": ["contact@acme.fr"],
                "facebook": "https://facebook.com/acme",
                "instagram": None,
                "twitter": None,
                "linkedin": None,
            },
        )

        result = asyncio.run(crawlers.crawl_website_async("https://example.com", label="ACME"))

        assert result["mobile_phones"] == ["+33612345678"]
        assert result["national_phones"] == ["+33123456789"]
        assert result["emails"] == ["contact@acme.fr"]
        assert result["facebook"] == "https://facebook.com/acme"
        assert result["linkedin"] == "https://linkedin.com/company/acme"


async def _async_result(value):
    return value

    def test_tel_ignored(self) -> None:
        assert normalize_url("https://example.com", "tel:+33612345678") is None

    def test_media_ignored(self) -> None:
        assert normalize_url("https://example.com", "/assets/logo.png") is None
