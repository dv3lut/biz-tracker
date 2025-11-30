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
