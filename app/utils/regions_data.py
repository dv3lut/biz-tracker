"""Static region and department definitions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionDefinition:
    code: str
    name: str
    order_index: int


@dataclass(frozen=True)
class DepartmentDefinition:
    code: str
    name: str
    region_code: str
    order_index: int


REGION_DEFINITIONS: tuple[RegionDefinition, ...] = (
    RegionDefinition(code="ARA", name="Auvergne-Rhône-Alpes", order_index=1),
    RegionDefinition(code="BFC", name="Bourgogne-Franche-Comté", order_index=2),
    RegionDefinition(code="BRE", name="Bretagne", order_index=3),
    RegionDefinition(code="CVL", name="Centre-Val de Loire", order_index=4),
    RegionDefinition(code="COR", name="Corse", order_index=5),
    RegionDefinition(code="GES", name="Grand Est", order_index=6),
    RegionDefinition(code="HDF", name="Hauts-de-France", order_index=7),
    RegionDefinition(code="IDF", name="Île-de-France", order_index=8),
    RegionDefinition(code="NOR", name="Normandie", order_index=9),
    RegionDefinition(code="NAQ", name="Nouvelle-Aquitaine", order_index=10),
    RegionDefinition(code="OCC", name="Occitanie", order_index=11),
    RegionDefinition(code="PDL", name="Pays de la Loire", order_index=12),
    RegionDefinition(code="PAC", name="Provence-Alpes-Côte d'Azur", order_index=13),
    RegionDefinition(code="GUA", name="Guadeloupe", order_index=14),
    RegionDefinition(code="MTQ", name="Martinique", order_index=15),
    RegionDefinition(code="GUY", name="Guyane", order_index=16),
    RegionDefinition(code="LRE", name="La Réunion", order_index=17),
    RegionDefinition(code="MAY", name="Mayotte", order_index=18),
)


DEPARTMENT_DEFINITIONS: tuple[DepartmentDefinition, ...] = (
    DepartmentDefinition(code="01", name="Ain", region_code="ARA", order_index=1),
    DepartmentDefinition(code="03", name="Allier", region_code="ARA", order_index=2),
    DepartmentDefinition(code="07", name="Ardèche", region_code="ARA", order_index=3),
    DepartmentDefinition(code="15", name="Cantal", region_code="ARA", order_index=4),
    DepartmentDefinition(code="26", name="Drôme", region_code="ARA", order_index=5),
    DepartmentDefinition(code="38", name="Isère", region_code="ARA", order_index=6),
    DepartmentDefinition(code="42", name="Loire", region_code="ARA", order_index=7),
    DepartmentDefinition(code="43", name="Haute-Loire", region_code="ARA", order_index=8),
    DepartmentDefinition(code="63", name="Puy-de-Dôme", region_code="ARA", order_index=9),
    DepartmentDefinition(code="69", name="Rhône", region_code="ARA", order_index=10),
    DepartmentDefinition(code="73", name="Savoie", region_code="ARA", order_index=11),
    DepartmentDefinition(code="74", name="Haute-Savoie", region_code="ARA", order_index=12),
    DepartmentDefinition(code="21", name="Côte-d'Or", region_code="BFC", order_index=1),
    DepartmentDefinition(code="25", name="Doubs", region_code="BFC", order_index=2),
    DepartmentDefinition(code="39", name="Jura", region_code="BFC", order_index=3),
    DepartmentDefinition(code="58", name="Nièvre", region_code="BFC", order_index=4),
    DepartmentDefinition(code="70", name="Haute-Saône", region_code="BFC", order_index=5),
    DepartmentDefinition(code="71", name="Saône-et-Loire", region_code="BFC", order_index=6),
    DepartmentDefinition(code="89", name="Yonne", region_code="BFC", order_index=7),
    DepartmentDefinition(code="90", name="Territoire de Belfort", region_code="BFC", order_index=8),
    DepartmentDefinition(code="22", name="Côtes-d'Armor", region_code="BRE", order_index=1),
    DepartmentDefinition(code="29", name="Finistère", region_code="BRE", order_index=2),
    DepartmentDefinition(code="35", name="Ille-et-Vilaine", region_code="BRE", order_index=3),
    DepartmentDefinition(code="56", name="Morbihan", region_code="BRE", order_index=4),
    DepartmentDefinition(code="18", name="Cher", region_code="CVL", order_index=1),
    DepartmentDefinition(code="28", name="Eure-et-Loir", region_code="CVL", order_index=2),
    DepartmentDefinition(code="36", name="Indre", region_code="CVL", order_index=3),
    DepartmentDefinition(code="37", name="Indre-et-Loire", region_code="CVL", order_index=4),
    DepartmentDefinition(code="41", name="Loir-et-Cher", region_code="CVL", order_index=5),
    DepartmentDefinition(code="45", name="Loiret", region_code="CVL", order_index=6),
    DepartmentDefinition(code="2A", name="Corse-du-Sud", region_code="COR", order_index=1),
    DepartmentDefinition(code="2B", name="Haute-Corse", region_code="COR", order_index=2),
    DepartmentDefinition(code="08", name="Ardennes", region_code="GES", order_index=1),
    DepartmentDefinition(code="10", name="Aube", region_code="GES", order_index=2),
    DepartmentDefinition(code="51", name="Marne", region_code="GES", order_index=3),
    DepartmentDefinition(code="52", name="Haute-Marne", region_code="GES", order_index=4),
    DepartmentDefinition(code="54", name="Meurthe-et-Moselle", region_code="GES", order_index=5),
    DepartmentDefinition(code="55", name="Meuse", region_code="GES", order_index=6),
    DepartmentDefinition(code="57", name="Moselle", region_code="GES", order_index=7),
    DepartmentDefinition(code="67", name="Bas-Rhin", region_code="GES", order_index=8),
    DepartmentDefinition(code="68", name="Haut-Rhin", region_code="GES", order_index=9),
    DepartmentDefinition(code="88", name="Vosges", region_code="GES", order_index=10),
    DepartmentDefinition(code="02", name="Aisne", region_code="HDF", order_index=1),
    DepartmentDefinition(code="59", name="Nord", region_code="HDF", order_index=2),
    DepartmentDefinition(code="60", name="Oise", region_code="HDF", order_index=3),
    DepartmentDefinition(code="62", name="Pas-de-Calais", region_code="HDF", order_index=4),
    DepartmentDefinition(code="80", name="Somme", region_code="HDF", order_index=5),
    DepartmentDefinition(code="75", name="Paris", region_code="IDF", order_index=1),
    DepartmentDefinition(code="77", name="Seine-et-Marne", region_code="IDF", order_index=2),
    DepartmentDefinition(code="78", name="Yvelines", region_code="IDF", order_index=3),
    DepartmentDefinition(code="91", name="Essonne", region_code="IDF", order_index=4),
    DepartmentDefinition(code="92", name="Hauts-de-Seine", region_code="IDF", order_index=5),
    DepartmentDefinition(code="93", name="Seine-Saint-Denis", region_code="IDF", order_index=6),
    DepartmentDefinition(code="94", name="Val-de-Marne", region_code="IDF", order_index=7),
    DepartmentDefinition(code="95", name="Val-d'Oise", region_code="IDF", order_index=8),
    DepartmentDefinition(code="14", name="Calvados", region_code="NOR", order_index=1),
    DepartmentDefinition(code="27", name="Eure", region_code="NOR", order_index=2),
    DepartmentDefinition(code="50", name="Manche", region_code="NOR", order_index=3),
    DepartmentDefinition(code="61", name="Orne", region_code="NOR", order_index=4),
    DepartmentDefinition(code="76", name="Seine-Maritime", region_code="NOR", order_index=5),
    DepartmentDefinition(code="16", name="Charente", region_code="NAQ", order_index=1),
    DepartmentDefinition(code="17", name="Charente-Maritime", region_code="NAQ", order_index=2),
    DepartmentDefinition(code="19", name="Corrèze", region_code="NAQ", order_index=3),
    DepartmentDefinition(code="23", name="Creuse", region_code="NAQ", order_index=4),
    DepartmentDefinition(code="24", name="Dordogne", region_code="NAQ", order_index=5),
    DepartmentDefinition(code="33", name="Gironde", region_code="NAQ", order_index=6),
    DepartmentDefinition(code="40", name="Landes", region_code="NAQ", order_index=7),
    DepartmentDefinition(code="47", name="Lot-et-Garonne", region_code="NAQ", order_index=8),
    DepartmentDefinition(code="64", name="Pyrénées-Atlantiques", region_code="NAQ", order_index=9),
    DepartmentDefinition(code="79", name="Deux-Sèvres", region_code="NAQ", order_index=10),
    DepartmentDefinition(code="86", name="Vienne", region_code="NAQ", order_index=11),
    DepartmentDefinition(code="87", name="Haute-Vienne", region_code="NAQ", order_index=12),
    DepartmentDefinition(code="09", name="Ariège", region_code="OCC", order_index=1),
    DepartmentDefinition(code="11", name="Aude", region_code="OCC", order_index=2),
    DepartmentDefinition(code="12", name="Aveyron", region_code="OCC", order_index=3),
    DepartmentDefinition(code="30", name="Gard", region_code="OCC", order_index=4),
    DepartmentDefinition(code="31", name="Haute-Garonne", region_code="OCC", order_index=5),
    DepartmentDefinition(code="32", name="Gers", region_code="OCC", order_index=6),
    DepartmentDefinition(code="34", name="Hérault", region_code="OCC", order_index=7),
    DepartmentDefinition(code="46", name="Lot", region_code="OCC", order_index=8),
    DepartmentDefinition(code="48", name="Lozère", region_code="OCC", order_index=9),
    DepartmentDefinition(code="65", name="Hautes-Pyrénées", region_code="OCC", order_index=10),
    DepartmentDefinition(code="66", name="Pyrénées-Orientales", region_code="OCC", order_index=11),
    DepartmentDefinition(code="81", name="Tarn", region_code="OCC", order_index=12),
    DepartmentDefinition(code="82", name="Tarn-et-Garonne", region_code="OCC", order_index=13),
    DepartmentDefinition(code="44", name="Loire-Atlantique", region_code="PDL", order_index=1),
    DepartmentDefinition(code="49", name="Maine-et-Loire", region_code="PDL", order_index=2),
    DepartmentDefinition(code="53", name="Mayenne", region_code="PDL", order_index=3),
    DepartmentDefinition(code="72", name="Sarthe", region_code="PDL", order_index=4),
    DepartmentDefinition(code="85", name="Vendée", region_code="PDL", order_index=5),
    DepartmentDefinition(code="04", name="Alpes-de-Haute-Provence", region_code="PAC", order_index=1),
    DepartmentDefinition(code="05", name="Hautes-Alpes", region_code="PAC", order_index=2),
    DepartmentDefinition(code="06", name="Alpes-Maritimes", region_code="PAC", order_index=3),
    DepartmentDefinition(code="13", name="Bouches-du-Rhône", region_code="PAC", order_index=4),
    DepartmentDefinition(code="83", name="Var", region_code="PAC", order_index=5),
    DepartmentDefinition(code="84", name="Vaucluse", region_code="PAC", order_index=6),
    DepartmentDefinition(code="971", name="Guadeloupe", region_code="GUA", order_index=1),
    DepartmentDefinition(code="972", name="Martinique", region_code="MTQ", order_index=1),
    DepartmentDefinition(code="973", name="Guyane", region_code="GUY", order_index=1),
    DepartmentDefinition(code="974", name="La Réunion", region_code="LRE", order_index=1),
    DepartmentDefinition(code="976", name="Mayotte", region_code="MAY", order_index=1),
)


__all__ = [
    "DepartmentDefinition",
    "DEPARTMENT_DEFINITIONS",
    "RegionDefinition",
    "REGION_DEFINITIONS",
]
