from __future__ import annotations

from datetime import date, datetime

from app.utils import dates, urls
from app.utils.hashing import sha256_digest


def test_parse_date_and_datetime_are_permissive():
    assert dates.parse_date("2024-05-01") == date(2024, 5, 1)
    assert dates.parse_date("invalid") is None

    assert dates.parse_datetime("2024-05-01T10:11:12") == datetime(2024, 5, 1, 10, 11, 12)
    assert dates.parse_datetime("2024-05-01 10:11:12") == datetime(2024, 5, 1, 10, 11, 12)
    assert dates.parse_datetime("oops") is None


def test_subtract_months_clamps_days():
    assert dates.subtract_months(date(2024, 3, 31), 6) == date(2023, 9, 30)
    assert dates.subtract_months(date(2024, 3, 15), 0) == date(2024, 3, 15)


def test_build_annuaire_url_validates_siret():
    assert urls.build_annuaire_etablissement_url("123 456 789 01234") == (
        f"{urls.ANNULAIRE_ETABLISSEMENT_BASE_URL}/12345678901234"
    )
    assert urls.build_annuaire_etablissement_url("123") is None
    assert urls.build_annuaire_etablissement_url(None) is None


def test_url_builder_rejects_non_numeric_characters():
    assert urls.build_annuaire_etablissement_url("1234567890123A") is None


def test_sha256_digest_is_deterministic():
    assert sha256_digest("hello") == sha256_digest("hello")
    assert sha256_digest("hello") != sha256_digest("HELLO")
