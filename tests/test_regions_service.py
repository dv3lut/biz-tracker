from __future__ import annotations

from types import SimpleNamespace

from app.db import models
from app.services.regions_service import list_regions
from app.utils.regions import REGION_DEFINITIONS


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class _SessionStub:
    def __init__(self, regions=None):
        self.regions = list(regions or [])

    def execute(self, stmt):  # noqa: ARG002 - stmt not used in stub
        ordered = sorted(self.regions, key=lambda item: (item.order_index, item.name))
        return _Result(ordered)

    def add(self, obj):
        self.regions.append(obj)

    def flush(self):
        return None


def test_list_regions_seeds_defaults_when_empty():
    session = _SessionStub()

    regions = list_regions(session)

    assert len(regions) == len(REGION_DEFINITIONS)
    codes = {region.code for region in regions}
    expected = {definition.code for definition in REGION_DEFINITIONS}
    assert codes == expected


def test_list_regions_keeps_existing_entries():
    existing = models.Region(code="IDF", name="Île-de-France", order_index=8)
    session = _SessionStub(regions=[existing])

    regions = list_regions(session)

    assert existing in regions
    assert len(regions) == len(REGION_DEFINITIONS)
