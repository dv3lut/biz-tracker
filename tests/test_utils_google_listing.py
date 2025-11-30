from __future__ import annotations

import pytest

from app.utils import google_listing


def test_normalize_listing_status_filters_validates_and_orders():
    result = google_listing.normalize_listing_status_filters(
        ["not_recent_creation", "recent_creation", "recent_creation"]
    )

    assert result == ["recent_creation", "not_recent_creation"]


def test_normalize_listing_status_filters_invalid_value():
    with pytest.raises(ValueError):
        google_listing.normalize_listing_status_filters(["invalid"])


def test_normalize_listing_age_status_handles_aliases():
    assert google_listing.normalize_listing_age_status("buyback_suspected") == "not_recent_creation"
    assert google_listing.normalize_listing_age_status(None) == "unknown"


def test_describe_listing_age_status_returns_label():
    assert google_listing.describe_listing_age_status("recent_creation") == "Création récente"
    assert google_listing.describe_listing_age_status("missing") == "Non déterminé"
