from __future__ import annotations

from app.utils.regions import (
    get_all_department_codes,
    get_all_region_codes,
    get_department_codes_for_region_codes,
    normalize_department_codes,
    get_region_definitions,
    resolve_department_code,
    resolve_region_code,
)


def test_resolve_department_code_prefers_commune():
    assert resolve_department_code("75101", "33000") == "75"


def test_resolve_department_code_handles_overseas_and_corsica():
    assert resolve_department_code("97302", None) == "973"
    assert resolve_department_code(None, "20000") == "20"


def test_resolve_region_code_matches_postal():
    assert resolve_region_code(None, "75001") == "IDF"
    assert resolve_region_code(None, "33000") == "NAQ"


def test_resolve_region_code_unknown_returns_none():
    assert resolve_region_code(None, "99999") is None


def test_get_department_codes_for_region_codes_returns_departments():
    codes = get_department_codes_for_region_codes(["IDF", "COR"])
    assert "75" in codes
    assert "77" in codes
    assert "2A" in codes
    assert "2B" in codes


def test_get_department_codes_for_region_codes_ignores_empty():
    codes = get_department_codes_for_region_codes(["", " ", None, "IDF"])
    assert "75" in codes


def test_get_department_codes_for_region_codes_deduplicates():
    codes = get_department_codes_for_region_codes(["IDF", "IDF"])
    assert codes.count("75") == 1


def test_get_department_codes_for_region_codes_empty_returns_empty():
    assert get_department_codes_for_region_codes([]) == []


def test_get_all_region_codes_contains_idf():
    assert "IDF" in get_all_region_codes()


def test_get_region_definitions_includes_idf():
    definitions = list(get_region_definitions())
    assert any(definition.code == "IDF" for definition in definitions)


def test_normalize_department_codes_expands_corsica_alias():
    codes = normalize_department_codes(["2A", "75"])
    assert "2A" in codes
    assert "75" in codes
    assert "20" in codes


def test_normalize_department_codes_keeps_existing_corsica_alias():
    codes = normalize_department_codes(["2B", "20", "2B", " ", None])
    assert codes.count("2B") == 1
    assert "20" in codes


def test_normalize_department_codes_no_corsica_alias_when_absent():
    codes = normalize_department_codes(["75", "75", " "])
    assert codes == ["75"]


def test_resolve_department_code_handles_corsica_prefix():
    assert resolve_department_code("2B123", None) == "2B"


def test_resolve_department_code_handles_overseas_98():
    assert resolve_department_code(None, "98800") == "988"


def test_resolve_department_code_returns_none_when_missing():
    assert resolve_department_code(None, None) is None


def test_get_all_department_codes_contains_paris():
    assert "75" in get_all_department_codes()
