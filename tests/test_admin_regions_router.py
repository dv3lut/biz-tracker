from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.api.routers.admin import regions_router


def test_list_regions_endpoint_includes_departments(monkeypatch):
    region_id = uuid4()
    department = SimpleNamespace(
        id=uuid4(),
        code="75",
        name="Paris",
        order_index=1,
        region_id=region_id,
    )
    region = SimpleNamespace(
        id=region_id,
        code="IDF",
        name="Île-de-France",
        order_index=8,
        departments=[department],
    )

    monkeypatch.setattr(regions_router, "list_departments", lambda session: [department])
    monkeypatch.setattr(regions_router, "list_regions", lambda session, include_departments=False: [region])

    response = regions_router.list_regions_endpoint(SimpleNamespace())

    assert response[0].code == "IDF"
    assert response[0].departments[0].code == "75"
