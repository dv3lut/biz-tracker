"""Region and department definitions and helpers."""
from __future__ import annotations

from typing import Iterable

from app.utils.regions_data import DEPARTMENT_DEFINITIONS, REGION_DEFINITIONS, DepartmentDefinition, RegionDefinition


ALL_REGION_CODES: tuple[str, ...] = tuple(definition.code for definition in REGION_DEFINITIONS)
ALL_DEPARTMENT_CODES: tuple[str, ...] = tuple(definition.code for definition in DEPARTMENT_DEFINITIONS)

_DEPARTMENT_TO_REGION: dict[str, str] = {}
_REGION_TO_DEPARTMENTS: dict[str, list[str]] = {}
for _definition in DEPARTMENT_DEFINITIONS:
    _DEPARTMENT_TO_REGION[_definition.code] = _definition.region_code
    _REGION_TO_DEPARTMENTS.setdefault(_definition.region_code, []).append(_definition.code)
if "COR" in _REGION_TO_DEPARTMENTS:
    _DEPARTMENT_TO_REGION.setdefault("20", "COR")


def get_region_definitions() -> Iterable[RegionDefinition]:
    return REGION_DEFINITIONS


def get_all_region_codes() -> list[str]:
    return list(ALL_REGION_CODES)


def get_all_department_codes() -> list[str]:
    return list(ALL_DEPARTMENT_CODES)


def get_department_definitions() -> Iterable[DepartmentDefinition]:
    return DEPARTMENT_DEFINITIONS


def get_department_codes_for_region_codes(region_codes: Iterable[str]) -> list[str]:
    normalized = {str(code).strip().upper() for code in region_codes if code}
    if not normalized:
        return []
    department_codes: list[str] = []
    seen: set[str] = set()
    for region_code in normalized:
        for dept in _REGION_TO_DEPARTMENTS.get(region_code, []):
            if dept in seen:
                continue
            seen.add(dept)
            department_codes.append(dept)
    return department_codes


def normalize_department_codes(codes: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in codes:
        if not raw:
            continue
        token = str(raw).strip().upper()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    if "2A" in seen or "2B" in seen:
        if "20" not in seen:
            normalized.append("20")
    return normalized


def resolve_department_code(code_commune: str | None, code_postal: str | None) -> str | None:
    for value in (code_commune, code_postal):
        if not value:
            continue
        token = str(value).strip().upper().replace(" ", "")
        if len(token) >= 2 and token[:2] in {"2A", "2B"}:
            return token[:2]
        if len(token) >= 3 and token[:2] in {"97", "98"}:
            return token[:3]
        if token.startswith("20"):
            return "20"
        if len(token) >= 2 and token[:2].isdigit():
            return token[:2]
    return None


def resolve_region_code(code_commune: str | None, code_postal: str | None) -> str | None:
    department_code = resolve_department_code(code_commune, code_postal)
    if not department_code:
        return None
    return _DEPARTMENT_TO_REGION.get(department_code)


__all__ = [
    "ALL_REGION_CODES",
    "ALL_DEPARTMENT_CODES",
    "DepartmentDefinition",
    "RegionDefinition",
    "get_department_definitions",
    "get_department_codes_for_region_codes",
    "get_all_department_codes",
    "get_all_region_codes",
    "get_region_definitions",
    "normalize_department_codes",
    "resolve_department_code",
    "resolve_region_code",
]
