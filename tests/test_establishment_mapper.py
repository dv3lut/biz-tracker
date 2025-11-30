from __future__ import annotations

from app.services import establishment_mapper as mapper


def _build_payload(**overrides):
    payload = {
        "siret": "12345678901234",
        "siren": "123456789",
        "nic": "00012",
        "dateCreationEtablissement": "2023-12-15",
        "dateDernierTraitementEtablissement": "2024-01-05T10:30:00",
        "activitePrincipaleEtablissement": None,
        "libelleActivitePrincipaleEtablissement": None,
        "periodesEtablissement": [
            {
                "dateDebut": "2023-01-01",
                "dateFin": "2023-06-30",
                "enseigne1Etablissement": "Ancienne enseigne",
                "libelleActivitePrincipaleEtablissement": "Ancienne activite",
            },
            {
                "dateDebut": "2023-07-01",
                "dateFin": None,
                "denominationUsuelleEtablissement": "Nom public",
                "enseigne1Etablissement": "Nouvelle enseigne",
                "activitePrincipaleEtablissement": "56.10A",
                "libelleActivitePrincipaleEtablissement": "Restauration",
                "etatAdministratifEtablissement": "A",
            },
        ],
        "uniteLegale": {
            "categorieEntreprise": "PME",
            "categorieJuridiqueUniteLegale": "005498",
            "trancheEffectifsUniteLegale": "01",
            "anneeEffectifsUniteLegale": "2022",
            "nomUsageUniteLegale": "Nom Usage",
            "nomUniteLegale": "DUPONT",
            "prenom1UniteLegale": "Alice",
            "prenom2UniteLegale": "",
            "prenom3UniteLegale": None,
            "prenom4UniteLegale": None,
            "prenomUsuelUniteLegale": "Alice",
            "pseudonymeUniteLegale": None,
            "sexeUniteLegale": "F",
            "denominationUniteLegale": "SARL DU TEST",
            "denominationUsuelle1UniteLegale": "",
            "periodesUniteLegale": [
                {"dateFin": "2020-12-31", "categorieJuridiqueUniteLegale": "000000"},
                {"dateFin": None, "categorieJuridiqueUniteLegale": "005498"},
            ],
        },
        "adresseEtablissement": {
            "complementAdresseEtablissement": "NDND",
            "numeroVoieEtablissement": "10",
            "indiceRepetitionEtablissement": " ",
            "typeVoieEtablissement": "Rue",
            "libelleVoieEtablissement": "des Lilas",
            "distributionSpecialeEtablissement": None,
            "codePostalEtablissement": "75000",
            "libelleCommuneEtablissement": "Paris",
            "libelleCommuneEtrangerEtablissement": None,
            "codeCommuneEtablissement": "75101",
            "codeCedexEtablissement": "",
            "libelleCedexEtablissement": "",
            "codePaysEtrangerEtablissement": "FR",
            "libellePaysEtrangerEtablissement": "France",
        },
    }
    payload.update(overrides)
    return payload


def test_extract_name_prefers_current_period_over_legacy_values():
    payload = _build_payload()

    result = mapper.extract_name(payload)

    assert result == "Nom public"


def test_extract_name_falls_back_to_person_name_when_needed():
    payload = _build_payload(
        periodesEtablissement=[{"dateDebut": "2023-01-01", "dateFin": None}],
        uniteLegale={
            "nomUniteLegale": "DURAND",
            "prenom1UniteLegale": "Paul",
            "periodesUniteLegale": [],
        },
    )

    result = mapper.extract_name(payload)

    assert result == "Paul DURAND"


def test_extract_name_falls_back_to_nom_only():
    payload = _build_payload(
        periodesEtablissement=[{"dateDebut": "2023-01-01", "dateFin": None}],
        uniteLegale={
            "nomUniteLegale": "DURAND",
            "periodesUniteLegale": [],
        },
    )

    assert mapper.extract_name(payload) == "DURAND"


def test_extract_name_returns_none_when_all_candidates_blank():
    payload = _build_payload(
        periodesEtablissement=[{"dateDebut": "2023-01-01", "dateFin": None}],
        uniteLegale={"periodesUniteLegale": []},
    )

    assert mapper.extract_name(payload) is None


def test_extract_fields_normalizes_dates_and_codes():
    payload = _build_payload()

    fields = mapper.extract_fields(payload)

    assert fields["naf_code"] == "56.10A"
    assert fields["naf_libelle"] == "Restauration"
    assert fields["etat_administratif"] == "A"
    assert str(fields["date_creation"]) == "2023-12-15"
    assert str(fields["date_debut_activite"]) == "2023-07-01"
    assert fields["denomination_usuelle_etablissement"] == "Nom public"
    assert fields["categorie_juridique"] == "005498"
    assert fields["annee_effectifs"] == 2022
    assert fields["complement_adresse"] is None
    assert fields["numero_voie"] == "10"
    assert fields["code_commune"] == "75101"
    assert fields["libelle_pays"] == "France"


def test_select_current_period_falls_back_to_first_entry():
    periods = [
        {"dateFin": "2022-12-31", "enseigne1Etablissement": "Ancienne"},
        {"dateFin": "", "enseigne1Etablissement": "Courante"},
    ]

    assert mapper._select_current_period(periods)["enseigne1Etablissement"] == "Courante"
    assert mapper._select_current_period([]) == {}


def test_clean_discards_placeholder_tokens():
    assert mapper._clean("ND") is None
    assert mapper._clean("ND ND") is None
    assert mapper._clean(" Rue des Lilas ") == "Rue des Lilas"


def test_clean_discards_symbols_only():
    assert mapper._clean("***") is None


def test_parse_int_handles_invalid_values():
    assert mapper._parse_int(None) is None
    assert mapper._parse_int("invalid") is None
    assert mapper._parse_int("12") == 12