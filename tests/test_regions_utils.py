from __future__ import annotations

from app.utils.regions import resolve_department_code, resolve_region_code


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
