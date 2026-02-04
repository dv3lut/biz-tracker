from __future__ import annotations

from datetime import date

from app.api.routers.admin.establishments_router import list_establishments


class _FakeQuery:
    def __init__(self) -> None:
        self.filters = []
        self._ordered = False
        self._offset = None
        self._limit = None

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def order_by(self, *args, **kwargs):
        self._ordered = True
        return self

    def offset(self, value):
        self._offset = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def all(self):
        return []


class _FakeSession:
    def __init__(self) -> None:
        self.query_obj = _FakeQuery()

    def query(self, *args, **kwargs):
        return self.query_obj


def _extract_filter_values(query: _FakeQuery) -> list[object]:
    values = []
    for criterion in query.filters:
        right = getattr(criterion, "right", None)
        if right is not None and hasattr(right, "value"):
            value = right.value
            if isinstance(value, (list, tuple, set)):
                values.extend(list(value))
            else:
                values.append(value)
    return values


def test_list_establishments_applies_naf_filter():
    session = _FakeSession()

    list_establishments(
        limit=10,
        offset=0,
        search=None,
        naf_code="56.10a",
        naf_codes=None,
        department_codes=None,
        region_codes=None,
        added_from=None,
        added_to=None,
        google_check_status=None,
        is_individual=None,
        session=session,  # type: ignore[arg-type]
    )

    rendered = "\n".join(str(item) for item in session.query_obj.filters)
    assert "naf_code" in rendered
    assert "replace" in rendered.lower()

    values = _extract_filter_values(session.query_obj)
    assert "5610A" in values


def test_list_establishments_applies_added_date_range():
    session = _FakeSession()

    list_establishments(
        limit=10,
        offset=0,
        search=None,
        naf_code=None,
        naf_codes=None,
        department_codes=None,
        region_codes=None,
        added_from=date(2024, 1, 10),
        added_to=date(2024, 1, 12),
        google_check_status=None,
        is_individual=None,
        session=session,  # type: ignore[arg-type]
    )

    rendered = "\n".join(str(item) for item in session.query_obj.filters)
    assert "first_seen_at" in rendered

    values = _extract_filter_values(session.query_obj)
    # On attend deux bornes datetime (>= start, < end_exclusive)
    assert len([value for value in values if hasattr(value, "year")]) >= 2


def test_list_establishments_ignores_blank_naf_code():
    session = _FakeSession()

    list_establishments(
        limit=10,
        offset=0,
        search=None,
        naf_code="   ",
        naf_codes=None,
        department_codes=None,
        region_codes=None,
        added_from=None,
        added_to=None,
        google_check_status=None,
        is_individual=None,
        session=session,  # type: ignore[arg-type]
    )

    rendered = "\n".join(str(item) for item in session.query_obj.filters)
    assert "naf_code" not in rendered


def test_list_establishments_applies_multi_naf_filter():
    session = _FakeSession()

    list_establishments(
        limit=10,
        offset=0,
        search=None,
        naf_code=None,
        naf_codes=["56.10A", "47 11d"],
        department_codes=None,
        region_codes=None,
        added_from=None,
        added_to=None,
        google_check_status=None,
        is_individual=None,
        session=session,  # type: ignore[arg-type]
    )

    rendered = "\n".join(str(item) for item in session.query_obj.filters)
    assert "naf_code" in rendered
    assert "replace" in rendered.lower()
    assert " in " in rendered.lower() or "IN" in rendered

    values = _extract_filter_values(session.query_obj)
    assert "5610A" in values
    assert "4711D" in values


def test_list_establishments_applies_google_check_status_filter():
    session = _FakeSession()

    list_establishments(
        limit=10,
        offset=0,
        search=None,
        naf_code=None,
        naf_codes=None,
        department_codes=None,
        region_codes=None,
        added_from=None,
        added_to=None,
        google_check_status="not_found",
        is_individual=None,
        session=session,  # type: ignore[arg-type]
    )

    rendered = "\n".join(str(item) for item in session.query_obj.filters)
    assert "google_check_status" in rendered


def test_list_establishments_applies_google_check_status_other_filter():
    session = _FakeSession()

    list_establishments(
        limit=10,
        offset=0,
        search=None,
        naf_code=None,
        naf_codes=None,
        department_codes=None,
        region_codes=None,
        added_from=None,
        added_to=None,
        google_check_status="other",
        is_individual=None,
        session=session,  # type: ignore[arg-type]
    )

    rendered = "\n".join(str(item) for item in session.query_obj.filters)
    assert "google_check_status" in rendered
    assert "not in" in rendered.lower()


def test_list_establishments_applies_department_filter():
    session = _FakeSession()

    list_establishments(
        limit=10,
        offset=0,
        search=None,
        naf_code=None,
        naf_codes=None,
        department_codes=["75"],
        region_codes=None,
        added_from=None,
        added_to=None,
        google_check_status=None,
        is_individual=None,
        session=session,  # type: ignore[arg-type]
    )

    rendered = "\n".join(str(item) for item in session.query_obj.filters)
    assert "code_commune" in rendered or "code_postal" in rendered
