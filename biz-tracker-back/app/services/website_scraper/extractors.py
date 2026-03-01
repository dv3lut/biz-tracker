"""Extract phone numbers, emails and social-media links from raw text / HTML."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Label extraction helpers
# ---------------------------------------------------------------------------

_LABEL_MIN_LEN = 2
_LABEL_MAX_LEN = 80
_LABEL_SEPARATORS = ":.-–—•|/"

# Words too generic to be useful as standalone labels.
_GENERIC_WORDS = {
    "tel", "tél", "telephone", "téléphone", "phone", "fax",
    "email", "e-mail", "mail", "courriel", "adresse",
}


def _validate_label(candidate: str) -> bool:
    """Return ``True`` when *candidate* looks like a meaningful label."""

    if not candidate or len(candidate) < _LABEL_MIN_LEN or len(candidate) > _LABEL_MAX_LEN:
        return False
    # Must contain at least one letter.
    if not re.search(r"[a-zA-ZÀ-ÿ]", candidate):
        return False
    # Reject URLs.
    if re.match(r"https?://", candidate, re.IGNORECASE):
        return False
    # Reject email-like strings.
    if "@" in candidate:
        return False
    # Reject if more than 50 % digits.
    digits = sum(1 for c in candidate if c.isdigit())
    if digits > len(candidate) * 0.5:
        return False
    # Reject HTML tag artifacts.
    if "<" in candidate and ">" in candidate:
        return False
    # Reject single generic words (but allow them as part of a longer phrase).
    if candidate.lower().strip() in _GENERIC_WORDS:
        return False
    return True


def _extract_preceding_label(
    text: str,
    match_start: int,
    max_lookback: int = 150,
) -> str | None:
    """Extract a potential label from text preceding a matched value.

    Looks at the same line and, if empty, the previous line.
    """

    start = max(0, match_start - max_lookback)
    preceding = text[start:match_start]

    # Split by newlines — the last segment is on the same line as the match.
    lines = preceding.split("\n")

    # Try the same-line text first.
    same_line = lines[-1].strip() if lines else ""
    if same_line:
        candidate = same_line.rstrip(_LABEL_SEPARATORS + " \t").strip()
        # If very long, try to take only the last phrase.
        if len(candidate) > 60:
            for sep in (",", ";", "|", " - ", " – ", " — "):
                idx = candidate.rfind(sep)
                if idx > 0:
                    shorter = candidate[idx + len(sep):].strip()
                    if _validate_label(shorter):
                        return shorter
            return None
        if _validate_label(candidate):
            return candidate

    # Fallback: try the previous line (useful for <dt>/<dd> or heading layouts).
    if len(lines) >= 2:
        prev_line = lines[-2].strip()
        if prev_line:
            candidate = prev_line.rstrip(_LABEL_SEPARATORS + " \t").strip()
            if len(candidate) <= 60 and _validate_label(candidate):
                return candidate

    return None


# ---------------------------------------------------------------------------
# Phone extraction
# ---------------------------------------------------------------------------

def extract_phones(text: str) -> Tuple[List[str], List[str]]:
    """Return *(mobile_phones, national_phones)* found in *text*.

    Numbers are normalised to the international ``+33…`` format and
    deduplicated.  National phones already present in the mobile list are
    excluded automatically.
    """

    mobile_pattern = r'(?:\+33[\s.]?[67]|0[67])(?:[\s.]?\d{2}){4}'
    national_pattern = r'(?:\+33[\s.]?[1-59]|0[1-59])(?:[\s.]?\d{2}){4}'

    mobile_matches = re.findall(mobile_pattern, text)
    national_matches = re.findall(national_pattern, text)

    def _clean(phone: str) -> str:
        phone = re.sub(r'[\s.\-]', '', phone)
        if phone.startswith('+33'):
            return phone
        if phone.startswith('0'):
            return '+33' + phone[1:]
        return phone

    mobile_phones = [_clean(p) for p in mobile_matches]
    national_phones = [_clean(p) for p in national_matches]

    # Exclude national numbers that also appear as mobiles.
    national_phones = [p for p in national_phones if p not in mobile_phones]

    # Validate minimum digit count.
    mobile_phones = [p for p in mobile_phones if len(re.sub(r'[^\d]', '', p)) >= 11]
    national_phones = [p for p in national_phones if len(re.sub(r'[^\d]', '', p)) >= 11]

    return list(set(mobile_phones)), list(set(national_phones))


def extract_phones_with_labels(text: str) -> Tuple[List[Tuple[str, Optional[str]]], List[Tuple[str, Optional[str]]]]:
    """Return *(mobile_phones, national_phones)* as ``(value, label)`` tuples.

    The label is extracted from contextual text preceding the phone number.
    """

    mobile_pattern = r'(?:\+33[\s.]?[67]|0[67])(?:[\s.]?\d{2}){4}'
    national_pattern = r'(?:\+33[\s.]?[1-59]|0[1-59])(?:[\s.]?\d{2}){4}'

    def _clean(phone: str) -> str:
        phone = re.sub(r'[\s.\-]', '', phone)
        if phone.startswith('+33'):
            return phone
        if phone.startswith('0'):
            return '+33' + phone[1:]
        return phone

    mobile_dict: Dict[str, Optional[str]] = {}
    for match in re.finditer(mobile_pattern, text):
        cleaned = _clean(match.group())
        if len(re.sub(r'[^\d]', '', cleaned)) < 11:
            continue
        if cleaned not in mobile_dict:
            label = _extract_preceding_label(text, match.start())
            mobile_dict[cleaned] = label
        elif not mobile_dict[cleaned]:
            label = _extract_preceding_label(text, match.start())
            if label:
                mobile_dict[cleaned] = label

    national_dict: Dict[str, Optional[str]] = {}
    for match in re.finditer(national_pattern, text):
        cleaned = _clean(match.group())
        if len(re.sub(r'[^\d]', '', cleaned)) < 11:
            continue
        if cleaned in mobile_dict:
            continue
        if cleaned not in national_dict:
            label = _extract_preceding_label(text, match.start())
            national_dict[cleaned] = label
        elif not national_dict[cleaned]:
            label = _extract_preceding_label(text, match.start())
            if label:
                national_dict[cleaned] = label

    return (
        [(v, l) for v, l in mobile_dict.items()],
        [(v, l) for v, l in national_dict.items()],
    )


# ---------------------------------------------------------------------------
# Email extraction
# ---------------------------------------------------------------------------

def extract_emails(text: str) -> List[str]:
    """Return unique email addresses found in *text*."""

    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(pattern, text)))


def extract_emails_with_labels(text: str) -> List[Tuple[str, Optional[str]]]:
    """Return unique email addresses found in *text* as ``(value, label)`` tuples."""

    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_dict: Dict[str, Optional[str]] = {}
    for match in re.finditer(pattern, text):
        email = match.group()
        lower = email.lower()
        if lower not in email_dict:
            label = _extract_preceding_label(text, match.start())
            email_dict[lower] = label
        elif not email_dict[lower]:
            label = _extract_preceding_label(text, match.start())
            if label:
                email_dict[lower] = label
    return [(v, l) for v, l in email_dict.items()]


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
                social_links["facebook"] = valid[0]
                break

    for pattern in instagram_patterns:
        matches = re.findall(pattern, text)
        if matches:
            valid = [link for link in matches if "developers.facebook.com" not in link]
            if valid:
                social_links["instagram"] = valid[0]
                break

    for pattern in twitter_patterns:
        matches = re.findall(pattern, text)
        if matches:
            social_links["twitter"] = matches[0]
            break

    for pattern in linkedin_patterns:
        matches = re.findall(pattern, text)
        if matches:
            social_links["linkedin"] = matches[0]
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
