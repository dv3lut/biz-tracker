from __future__ import annotations

from types import SimpleNamespace

from app.services.google_business.google_match_rules import evaluate_candidate_match


def _est(
    *,
    name: str,
    code_postal: str,
    commune: str,
    numero_voie: str | None = None,
    indice_repetition: str | None = None,
    type_voie: str | None = None,
    libelle_voie: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        code_postal=code_postal,
        libelle_commune=commune,
        libelle_commune_etranger=None,
        numero_voie=numero_voie,
        indice_repetition=indice_repetition,
        type_voie=type_voie,
        libelle_voie=libelle_voie,
    )


def test_case_chez_simone_vs_chez_sylvia_is_false() -> None:
    est = _est(
        name="CHEZ SIMONE",
        code_postal="83230",
        commune="BORMES-LES-MIMOSAS",
        numero_voie="43",
        type_voie="RUE",
        libelle_voie="CARNOT",
    )
    decision = evaluate_candidate_match(
        est,
        "Chez Sylvia",
        "872 Av. lou Mistraou, 83230 Bormes-les-Mimosas",
    )
    assert decision.accept is False


def test_case_delices_chrislie_vs_delices_mimi_is_false() -> None:
    est = _est(
        name="LES DELICES DE CHRISLIE",
        code_postal="97128",
        commune="GOYAVE",
    )
    decision = evaluate_candidate_match(
        est,
        "LES DÉLICES DE MIMI",
        "97128 Rue des Ecoles, Goyave 97128, Guadeloupe",
    )
    assert decision.accept is False


def test_case_crousty_house_vs_ocrousty_is_false() -> None:
    est = _est(
        name="CROUSTY HOUSE",
        code_postal="76220",
        commune="GOURNAY-EN-BRAY",
        numero_voie="6",
        type_voie="PLACE",
        libelle_voie="DE LA LIBERATION",
    )
    decision = evaluate_candidate_match(
        est,
        "O'crousty",
        "12 Rue Notre Dame, 76220 Gournay-en-Bray",
    )
    assert decision.accept is False


def test_case_yapizza_is_true() -> None:
    est = _est(
        name="YA'PIZZA",
        code_postal="49420",
        commune="OMBREE D'ANJOU",
        numero_voie="701",
        libelle_voie="LA JONCHERE",
    )
    decision = evaluate_candidate_match(
        est,
        "ya'pizza",
        "701 la jonchére, 49420 Ombrée d'Anjou",
    )
    assert decision.accept is True


def test_case_auberge_de_cindre_is_true() -> None:
    est = _est(
        name="AUBERGE DE CINDRE",
        code_postal="03220",
        commune="CINDRE",
        numero_voie="55",
        type_voie="RUE",
        libelle_voie="DE TREZELLES",
    )
    decision = evaluate_candidate_match(
        est,
        "Auberge de Cindré",
        "55 Rue de Trézelles, 03220 Cindré",
    )
    assert decision.accept is True


def test_case_crousty_crispy_vs_crousty_factory_is_false() -> None:
    est = _est(
        name="CROUSTY CRISPY",
        code_postal="94500",
        commune="CHAMPIGNY-SUR-MARNE",
        numero_voie="23",
        type_voie="RUE",
        libelle_voie="JEAN JAURES",
    )
    decision = evaluate_candidate_match(
        est,
        "Crousty Factory",
        "44bis Av. de la République, 94500 Champigny-sur-Marne",
    )
    assert decision.accept is False


def test_case_cafe_du_centre_is_true() -> None:
    est = _est(
        name="CAFE DU CENTRE",
        code_postal="37380",
        commune="MONNAIE",
        numero_voie="1",
        type_voie="PLACE",
        libelle_voie="JEAN BAPTISTE MOREAU",
    )
    decision = evaluate_candidate_match(
        est,
        "Café du centre",
        "1 pl Jean Baptiste Moreau, 37380 Monnaie",
    )
    assert decision.accept is True


def test_case_kenavo_crepes_is_true() -> None:
    est = _est(
        name="KENAVO - LES CREPES DE MARIE",
        code_postal="24660",
        commune="COULOUNIEIX-CHAMIERS",
        type_voie="AVENUE",
        libelle_voie="DU MARECHAL FOCH",
    )
    decision = evaluate_candidate_match(
        est,
        "Kenavo Crêpes",
        "Le Bourg, 24660, Coulounieix-Chamiers",
    )
    assert decision.accept is True


def test_case_lencrier_is_true() -> None:
    est = _est(
        name="L'ENCRIER",
        code_postal="63980",
        commune="AIX-LA-FAYETTE",
        numero_voie="5",
        type_voie="IMPASSE",
        libelle_voie="DE L'EGLISE",
    )
    decision = evaluate_candidate_match(
        est,
        "Restaurant l'encrier",
        "5 impasse de l'église, 63980 Aix-la-Fayette",
    )
    assert decision.accept is True


def test_distance_fallback_allows_close_addresses() -> None:
    est = _est(
        name="FRICHTI KIOSQUE",
        code_postal="75002",
        commune="PARIS",
        numero_voie="14",
        type_voie="RUE",
        libelle_voie="DES JEUNEURS",
    )

    base = evaluate_candidate_match(
        est,
        "Frichti Kiosque - Caire",
        "42 Rue du Caire, 75002 Paris",
    )
    assert base.accept is False
    assert base.needs_distance_check is True

    accepted = evaluate_candidate_match(
        est,
        "Frichti Kiosque - Caire",
        "42 Rue du Caire, 75002 Paris",
        distance_m=420.0,
    )
    assert accepted.accept is True

    rejected = evaluate_candidate_match(
        est,
        "Frichti Kiosque - Caire",
        "42 Rue du Caire, 75002 Paris",
        distance_m=900.0,
    )
    assert rejected.accept is False
