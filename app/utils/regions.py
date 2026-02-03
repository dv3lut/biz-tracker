"""Region definitions and helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RegionDefinition:
    code: str
    name: str
    department_codes: tuple[str, ...]
    order_index: int


REGION_DEFINITIONS: tuple[RegionDefinition, ...] = (
    RegionDefinition(
        code="ARA",
        name="Auvergne-Rhône-Alpes",
        department_codes=("01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"),
        order_index=1,
    ),
    RegionDefinition(
        code="BFC",
        name="Bourgogne-Franche-Comté",
        department_codes=("21", "25", "39", "58", "70", "71", "89", "90"),
        order_index=2,
    ),
    RegionDefinition(
        code="BRE",
        name="Bretagne",
        department_codes=("22", "29", "35", "56"),
        order_index=3,
    ),
    RegionDefinition(
        code="CVL",
        name="Centre-Val de Loire",
        department_codes=("18", "28", "36", "37", "41", "45"),
        order_index=4,
    ),
    RegionDefinition(
        code="COR",
        name="Corse",
        department_codes=("2A", "2B", "20"),
        order_index=5,
    ),
    RegionDefinition(
        code="GES",
        name="Grand Est",
        department_codes=("08", "10", "51", "52", "54", "55", "57", "67", "68", "88"),
        order_index=6,
    ),
    RegionDefinition(
        code="HDF",
        name="Hauts-de-France",
        department_codes=("02", "59", "60", "62", "80"),
        order_index=7,
    ),
    RegionDefinition(
        code="IDF",
        name="Île-de-France",
        department_codes=("75", "77", "78", "91", "92", "93", "94", "95"),
        order_index=8,
    ),
    RegionDefinition(
        code="NOR",
        name="Normandie",
        department_codes=("14", "27", "50", "61", "76"),
        order_index=9,
    ),
    RegionDefinition(
        code="NAQ",
        name="Nouvelle-Aquitaine",
        department_codes=("16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"),
        order_index=10,
    ),
    RegionDefinition(
        code="OCC",
        name="Occitanie",
        department_codes=("09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"),
        order_index=11,
    ),
    RegionDefinition(
        code="PDL",
        name="Pays de la Loire",
        department_codes=("44", "49", "53", "72", "85"),
        order_index=12,
    ),
    RegionDefinition(
        code="PAC",
        name="Provence-Alpes-Côte d'Azur",
        department_codes=("04", "05", "06", "13", "83", "84"),
        order_index=13,
    ),
    RegionDefinition(
        code="GUA",
        name="Guadeloupe",
        department_codes=("971",),
        order_index=14,
    ),
    RegionDefinition(
        code="MTQ",
        name="Martinique",
        department_codes=("972",),
        order_index=15,
    ),
    RegionDefinition(
        code="GUY",
        name="Guyane",
        department_codes=("973",),
        order_index=16,
    ),
    RegionDefinition(
        code="LRE",
        name="La Réunion",
        department_codes=("974",),
        order_index=17,
    ),
    RegionDefinition(
        code="MAY",
        name="Mayotte",
        department_codes=("976",),
        order_index=18,
    ),
)

ALL_REGION_CODES: tuple[str, ...] = tuple(definition.code for definition in REGION_DEFINITIONS)

_DEPARTMENT_TO_REGION: dict[str, str] = {}
for _definition in REGION_DEFINITIONS:
    for _dept in _definition.department_codes:
        _DEPARTMENT_TO_REGION[_dept] = _definition.code


def get_region_definitions() -> Iterable[RegionDefinition]:
    return REGION_DEFINITIONS


def get_all_region_codes() -> list[str]:
    return list(ALL_REGION_CODES)


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
    "RegionDefinition",
    "get_all_region_codes",
    "get_region_definitions",
    "resolve_department_code",
    "resolve_region_code",
]
