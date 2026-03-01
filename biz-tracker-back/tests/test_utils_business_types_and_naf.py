from __future__ import annotations

import pytest

from app.utils import business_types, naf


def test_normalize_legal_category_strips_leading_zeroes():
    assert business_types.normalize_legal_category("005498") == "5498"
    assert business_types.normalize_legal_category("   0000") == "0000"
    assert business_types.normalize_legal_category("   ") == ""
    assert business_types.normalize_legal_category(None) == ""


def test_individual_and_micro_company_detection():
    assert business_types.is_individual_company("1000") is True
    assert business_types.is_individual_company("0499") is False
    assert business_types.is_individual_company(" ") is False
    assert business_types.is_micro_company("me", None) is True
    assert business_types.is_micro_company("", "1999") is True
    assert business_types.is_micro_company(None, " ") is False


def test_normalize_naf_code_variations():
    assert naf.normalize_naf_code("5610a") == "56.10A"
    assert naf.normalize_naf_code("56.10A") == "56.10A"
    assert naf.normalize_naf_code("5610") is None
    assert naf.normalize_naf_code(" 5610 a ") == "56.10A"
    assert naf.normalize_naf_code(None) is None
    assert naf.normalize_naf_code("   ") is None


def test_ensure_valid_naf_code_raises_on_invalid():
    with pytest.raises(ValueError):
        naf.ensure_valid_naf_code("invalid")


def test_ensure_valid_naf_code_accepts_valid_input():
    assert naf.ensure_valid_naf_code("56.10A") == "56.10A"


def test_euro_cent_conversions_round_and_validate():
    assert naf.euros_to_cents(12.345) == 1235
    assert naf.cents_to_euros(1235) == pytest.approx(12.35)
    with pytest.raises(ValueError):
        naf.euros_to_cents(-1)
