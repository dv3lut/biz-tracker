from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from app.services.alerts.formatter import EstablishmentFormatter


def _make_session(rows):
    class Result:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class Session:
        def execute(self, _):
            return Result(rows)

    return Session()


def _make_establishment(**overrides):
    base = dict(
        siret="12345678901234",
        name="Test",
        naf_code="5610A",
        google_listing_age_status="recent_creation",
        google_place_url="https://maps.google.com/?cid=1",
        google_place_id="place-1",
        google_match_confidence=0.95,
        numero_voie="10",
        type_voie="Rue",
        libelle_voie="des Tests",
        code_postal="75000",
        libelle_commune="Paris",
        libelle_commune_etranger=None,
        date_creation=date(2024, 1, 1),
        google_listing_origin_at=datetime(2024, 1, 2, 10, 0, 0),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_get_subcategory_lookup_caches_results():
    session = _make_session([("5610A", "Bistrot", "Restauration")])
    formatter = EstablishmentFormatter(session)

    label = formatter.format_subcategory_label("5610A")
    second = formatter.format_subcategory_label("5610A")

    assert label == "Bistrot (Restauration)"
    assert second == label


def test_format_subcategory_label_with_multiple_categories():
    session = _make_session(
        [
            ("56.10A", "Restauration rapide", "Restauration"),
            ("56.10A", "Restauration rapide", "Traiteur"),
        ]
    )
    formatter = EstablishmentFormatter(session)

    label = formatter.format_subcategory_label("56.10A")

    assert label == "Restauration rapide (Restauration, Traiteur)"


def test_format_subcategory_label_with_category_only():
    session = _make_session([("56.10A", None, "Traiteur")])
    formatter = EstablishmentFormatter(session)

    label = formatter.format_subcategory_label("56.10A")

    assert label == "Traiteur"


def test_resolve_category_and_subcategory_returns_first_entry():
    session = _make_session(
        [
            ("56.10A", "Sub1", "Cat1"),
            ("56.10A", "Sub2", "Cat2"),
        ]
    )
    formatter = EstablishmentFormatter(session)

    category, subcategory = formatter.resolve_category_and_subcategory("56.10A")

    assert category == "Cat1"
    assert subcategory == "Sub1"


def test_resolve_client_category_labels_from_subscriptions():
    session = _make_session([])
    formatter = EstablishmentFormatter(session)
    category_one = SimpleNamespace(name="Restauration")
    category_two = SimpleNamespace(name="Traiteur")
    subcategory_one = SimpleNamespace(
        name="Restauration rapide",
        naf_code="56.10A",
        is_active=True,
        categories=[category_one],
    )
    subcategory_two = SimpleNamespace(
        name="Restauration rapide",
        naf_code="56.10A",
        is_active=True,
        categories=[category_two],
    )
    client = SimpleNamespace(
        subscriptions=[
            SimpleNamespace(subcategory=subcategory_one),
            SimpleNamespace(subcategory=subcategory_two),
        ]
    )

    categories, subcategories = formatter.resolve_client_category_labels(client, "56.10A")

    assert categories == ["Restauration", "Traiteur"]
    assert subcategories == ["Restauration rapide"]


def test_resolve_client_category_labels_returns_empty_on_invalid_code():
    formatter = EstablishmentFormatter(_make_session([]))

    categories, subcategories = formatter.resolve_client_category_labels(SimpleNamespace(subscriptions=[]), None)

    assert categories == []
    assert subcategories == []


def test_resolve_client_category_labels_respects_client_categories():
    formatter = EstablishmentFormatter(_make_session([]))
    category_one = SimpleNamespace(id="cat-1", name="Restauration")
    category_two = SimpleNamespace(id="cat-2", name="Traiteur")
    subcategory = SimpleNamespace(
        name="Restauration rapide",
        naf_code="56.10A",
        is_active=True,
        categories=[category_one, category_two],
    )
    client = SimpleNamespace(
        category_ids=["cat-2"],
        subscriptions=[SimpleNamespace(subcategory=subcategory)],
    )

    categories, subcategories = formatter.resolve_client_category_labels(client, "56.10A")

    assert categories == ["Traiteur"]
    assert subcategories == ["Restauration rapide"]


def test_format_lines_includes_google_details():
    session = _make_session([])
    formatter = EstablishmentFormatter(session)
    establishment = _make_establishment()

    lines = formatter.format_lines(establishment, include_google=True)

    assert any("Statut fiche Google" in line for line in lines)
    assert any("Google:" in line for line in lines)


def test_describe_listing_age_returns_label_and_origin():
    session = _make_session([])
    formatter = EstablishmentFormatter(session)
    establishment = _make_establishment()

    label, origin = formatter.describe_listing_age(establishment)

    assert label.startswith("Création")
    assert origin == establishment.google_listing_origin_at.isoformat()


def test_format_address_lines_handles_missing_segments():
    session = _make_session([])
    formatter = EstablishmentFormatter(session)
    establishment = _make_establishment(numero_voie=None, type_voie=None, libelle_voie=None)

    street, commune = formatter.format_address_lines(establishment)

    assert street is None
    assert commune == "75000 Paris"


def test_get_siret_display_handles_missing_value():
    session = _make_session([])
    formatter = EstablishmentFormatter(session)

    display, url = formatter.get_siret_display_and_url(None)

    assert display == "N/A"
    assert url is None
