from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.db import models
from app.services.regions_service import list_departments, list_regions
from app.utils.regions import DEPARTMENT_DEFINITIONS, REGION_DEFINITIONS


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class _SessionStub:
    def __init__(self, regions=None, departments=None):
        self.regions = list(regions or [])
        self.departments = list(departments or [])
        self.added = []

    def execute(self, stmt):  # noqa: ARG002 - stmt not used in stub
        stmt_text = str(stmt)
        if "departments" in stmt_text:
            ordered = sorted(self.departments, key=lambda item: (item.order_index, item.name))
            return _Result(ordered)
        ordered = sorted(self.regions, key=lambda item: (item.order_index, item.name))
        return _Result(ordered)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, models.Department):
            self.departments.append(obj)
        else:
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


def test_list_regions_include_departments_executes_option():
    session = _SessionStub()

    regions = list_regions(session, include_departments=True)

    assert len(regions) == len(REGION_DEFINITIONS)


def test_list_regions_no_creation_returns_existing_only():
    session = _SessionStub(regions=[])

    regions = list_regions(session, create_if_missing=False)

    assert regions == []
    assert session.added == []


def test_list_departments_seeds_defaults_when_empty():
    session = _SessionStub()

    departments = list_departments(session)

    assert len(departments) == len(DEPARTMENT_DEFINITIONS)
    codes = {department.code for department in departments}
    expected = {definition.code for definition in DEPARTMENT_DEFINITIONS}
    assert codes == expected


def test_list_departments_keeps_existing_entries():
    existing = models.Department(code="75", name="Paris", order_index=1, region_id=uuid4())
    session = _SessionStub(departments=[existing])

    departments = list_departments(session)

    assert existing in departments
    assert len(departments) == len(DEPARTMENT_DEFINITIONS)


def test_list_departments_skips_unknown_region(monkeypatch):
    session = _SessionStub()
    fake_definition = SimpleNamespace(
        code="XX",
        name="Test Dept",
        order_index=1,
        region_code="UNKNOWN",
    )
    monkeypatch.setattr(
        "app.services.regions_service.get_department_definitions",
        lambda: [fake_definition],
    )

    departments = list_departments(session)

    assert departments == []
    assert not any(isinstance(item, models.Department) for item in session.added)


def test_list_departments_no_creation_returns_existing_only():
    session = _SessionStub(departments=[])

    departments = list_departments(session, create_if_missing=False)

    assert departments == []
    assert session.added == []
