"""Extract phone numbers, emails and social-media links from raw text / HTML."""
from __future__ import annotations

import html
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Phone extraction
# ---------------------------------------------------------------------------

def extract_phones(text: str) -> Tuple[List[str], List[str], List[str]]:
    """Return *(mobile_phones, national_phones, international_phones)* found in *text*.

    Numbers are normalised to the international ``+33…`` format and
    deduplicated.  National phones already present in the mobile list are
    excluded automatically.
    """

    mobile_pattern = r'(?:\+33(?:\s*\(0\))?[\s.\-]?[67]|0[67])(?:[\s.\-]?\d{2}){4}'
    national_pattern = r'(?:\+33(?:\s*\(0\))?[\s.\-]?[1-59]|0[1-59])(?:[\s.\-]?\d{2}){4}'
    international_pattern = r'\+(?:\d[\s.\-]?){7,15}\d'

    mobile_matches = re.findall(mobile_pattern, text)
    national_matches = re.findall(national_pattern, text)
    international_matches = re.findall(international_pattern, text)

    def _clean(phone: str) -> str:
        phone = re.sub(r'[\s.\-\(\)]', '', phone)
        if phone.startswith('+330'):
            return '+33' + phone[4:]
        if phone.startswith('+33'):
            return phone
        if phone.startswith('0'):
            return '+33' + phone[1:]
        return phone

    mobile_phones = [_clean(p) for p in mobile_matches]
    national_phones = [_clean(p) for p in national_matches]
    international_phones = [
        re.sub(r'[\s.\-]', '', phone)
        for phone in international_matches
        if isinstance(phone, str) and phone.startswith("+")
    ]

    # Exclude national numbers that also appear as mobiles.
    national_phones = [p for p in national_phones if p not in mobile_phones]

    # Validate minimum digit count.
    mobile_phones = [p for p in mobile_phones if len(re.sub(r'[^\d]', '', p)) >= 11]
    national_phones = [p for p in national_phones if len(re.sub(r'[^\d]', '', p)) >= 11]
    international_phones = [
        p for p in international_phones if p.startswith("+") and 8 <= len(re.sub(r'[^\d]', '', p)) <= 15
    ]

    # Keep only non-FR international numbers in this bucket.
    international_phones = [
        p
        for p in international_phones
        if not p.startswith("+33")
    ]

    return list(set(mobile_phones)), list(set(national_phones)), list(set(international_phones))


# ---------------------------------------------------------------------------
# Email extraction
# ---------------------------------------------------------------------------

def extract_emails(text: str) -> List[str]:
    """Return unique email addresses found in *text*.

    Handles both normal cases (clear separator after the address) and common
    scraping artifacts where a word is glued right after a short TLD, e.g.
    ``name@example.comcookies``.

    Also strips leading digit fragments (telephone suffixes) that get
    concatenated to e-mail local parts when text is extracted from the DOM
    without proper whitespace separation.
    """

    common_short_tlds = ("com", "net", "org", "edu", "gov", "mil", "int", "info", "biz", "fr")
    strict_pattern = re.compile(
        r'(?<![\w.+-])([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.([a-zA-Z]{2,24}))(?=$|[^a-zA-Z])'
    )
    # Fallback for glued suffixes after common short TLDs.
    glued_suffix_pattern = re.compile(
        r'(?<![\w.+-])([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:com|net|org|edu|gov|mil|int|info|biz|fr))[a-z]{2,}(?=$|[^a-zA-Z])',
        re.IGNORECASE,
    )

    # Detect phone-number digits glued before the real local-part.
    # Matches 1-10 leading digits immediately followed by a letter.
    _phone_prefix_re = re.compile(r'^(\d{1,10})([a-zA-Z])')

    emails: set[str] = set()
    for match in strict_pattern.finditer(text):
        candidate = match.group(1).lower()
        tld = match.group(2).lower()
        is_glued_common_tld = any(
            tld.startswith(common_tld) and len(tld) > len(common_tld)
            for common_tld in common_short_tlds
        )
        if not is_glued_common_tld:
            emails.add(candidate)

    emails.update(match.group(1).lower() for match in glued_suffix_pattern.finditer(text))

    # Sanitise: strip leading digit fragments (phone-number suffixes).
    cleaned: set[str] = set()
    for email in emails:
        local, at_domain = email.split("@", maxsplit=1)
        prefix_match = _phone_prefix_re.match(local)
        if prefix_match:
            stripped_local = local[len(prefix_match.group(1)):]
            if stripped_local and "." not in prefix_match.group(1):
                email = f"{stripped_local}@{at_domain}"
        cleaned.add(email)
    return list(cleaned)


def extract_mailto_emails(html_content: str) -> List[str]:
    """Extract email addresses from ``mailto:`` links in *html_content*.

    These are considered high-confidence because the site author explicitly
    marked them as emails in an ``<a href="mailto:...">`` tag.
    """

    soup = BeautifulSoup(html_content, "html.parser")
    emails: set[str] = set()
    _email_re = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    for anchor in soup.find_all("a", href=True):
        href: str = anchor["href"]
        if not href.lower().startswith("mailto:"):
            continue
        # Strip mailto: prefix and optional query string (?subject=…)
        raw = href[7:].split("?", maxsplit=1)[0]
        decoded = html.unescape(unquote(raw))
        candidate = decoded.strip().lower()
        if _email_re.match(candidate):
            emails.add(candidate)

    return list(emails)


# ---------------------------------------------------------------------------
# Social-link extraction
# ---------------------------------------------------------------------------

_FACEBOOK_EXCLUSIONS = [
    "developers.facebook.com",
    "business.facebook.com",
    "www.facebook.com/policies",
    "www.facebook.com/privacy",
    "www.facebook.com/legal",
    "www.facebook.com/terms",
    "www.facebook.com/help",
    "www.facebook.com/about",
    "login.facebook.com",
    "www.facebook.com/login",
    "facebook.com/login",
    "m.facebook.com/login",
]

_FACEBOOK_INVALID_TOKENS = [
    "login",
    "login_attempt=",
    "login.php",
    "oauth",
    "sharer",
    "dialog",
    "/share",
    "/policy",
]


def _sanitize_social_link(value: str) -> str | None:
    """Return a cleaned social URL candidate or ``None`` when invalid."""

    raw = html.unescape(value or "").strip()
    if not raw:
        return None
    cleaned = re.split(r'["\'<>\s]', raw, maxsplit=1)[0].rstrip(",.;)")
    if not cleaned.startswith(("http://", "https://")):
        return None
    return cleaned


def extract_social_links(text: str) -> Dict[str, Optional[str]]:
    """Return a dict with keys *facebook*, *instagram*, *twitter*, *linkedin*.

    Only the first valid match for each network is retained.
    """

    social_links: Dict[str, Optional[str]] = {
        "facebook": None,
        "instagram": None,
        "twitter": None,
        "linkedin": None,
    }

    facebook_patterns = [
        r'https?://(?:[\w-]+\.)?facebook\.com/[a-zA-Z0-9.]+(?:[/?#][^"\'\s<>]*)?',
        r'https?://(?:[\w-]+\.)?fb\.com/[a-zA-Z0-9.]+(?:[/?#][^"\'\s<>]*)?',
    ]
    instagram_patterns = [
        r'https?://(?:[\w-]+\.)?instagram\.com/[a-zA-Z0-9_.]+(?:[/?#][^"\'\s<>]*)?',
    ]
    twitter_patterns = [
        r'https?://(?:[\w-]+\.)?twitter\.com/[a-zA-Z0-9_]+(?:[/?#][^"\'\s<>]*)?',
        r'https?://(?:[\w-]+\.)?x\.com/[a-zA-Z0-9_]+(?:[/?#][^"\'\s<>]*)?',
    ]
    linkedin_patterns = [
        r'https?://(?:[\w-]+\.)?linkedin\.com/(?:company|in|school|showcase)/[a-zA-Z0-9_-]+(?:[/?#][^"\'\s<>]*)?',
    ]

    for pattern in facebook_patterns:
        matches = re.findall(pattern, text)
        if matches:
            valid = [
                link
                for link in matches
                if not any(excl in link for excl in _FACEBOOK_EXCLUSIONS)
                and not any(token in link for token in _FACEBOOK_INVALID_TOKENS)
            ]
            if valid:
                sanitized = _sanitize_social_link(valid[0])
                if sanitized:
                    social_links["facebook"] = sanitized
                break

    for pattern in instagram_patterns:
        matches = re.findall(pattern, text)
        if matches:
            valid = [link for link in matches if "developers.facebook.com" not in link]
            if valid:
                sanitized = _sanitize_social_link(valid[0])
                if sanitized:
                    social_links["instagram"] = sanitized
                break

    for pattern in twitter_patterns:
        matches = re.findall(pattern, text)
        if matches:
            sanitized = _sanitize_social_link(matches[0])
            if sanitized:
                social_links["twitter"] = sanitized
            break

    for pattern in linkedin_patterns:
        matches = re.findall(pattern, text)
        if matches:
            sanitized = _sanitize_social_link(matches[0])
            if sanitized:
                social_links["linkedin"] = sanitized
            break

    return social_links


# ---------------------------------------------------------------------------
# JS-rendering detection
# ---------------------------------------------------------------------------

def needs_browser_rendering(html_content: str) -> bool:
    """Heuristic: return ``True`` when the page likely requires a real browser."""

    soup = BeautifulSoup(html_content, "html.parser")

    text_content = soup.get_text().strip()
    if len(text_content) < 200:
        return True

    links = soup.find_all("a", href=True)
    if len(links) < 3:
        return True

    js_frameworks = [
        "vue", "react", "angular", "ember", "backbone",
        "next", "nuxt", "gatsby", "svelte", "alpine", "stimulus",
    ]
    for framework in js_frameworks:
        if f"data-{framework}" in html_content or f"{framework}-app" in html_content:
            return True

    body_tag = soup.find("body")
    if body_tag and len(body_tag.find_all("script")) > 5:
        return True

    return False
