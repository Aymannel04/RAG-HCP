"""
Tests du module ConstructeurIndicateurs (chemin API BDS). Le JSON mock ci-dessous
reproduit en miniature la forme réelle observée sur `GET /api/v1/indicators/I3181`
(vérifiée par appel réel le 16-17 juillet 2026, voir docs/adr/0004-*.md) : deux
modalités de ventilation, deux périodes, une valeur manquante ("ND") à ignorer.
"""
from src.constructeur_indicateurs import ConstructeurIndicateurs

INDICATEUR_JSON_MOCK = {
    "code": "I9999",
    "label": "Indicateur de test ",
    "metaData": {"unit": "En millions de dhs"},
    "periods": ["2020T1", "2020T2"],
    "dimensions": [
        {
            "id": 1,
            "label": "Branche d'activité",
            "modalites": [
                {"id": 10, "label": "Agriculture", "total": False},
                {"id": 11, "label": "Industrie", "total": False},
            ],
        }
    ],
    "data": {
        "10_2020T1": {"value": "100", "footNote": None},
        "10_2020T2": {"value": "110", "footNote": None},
        "11_2020T1": {"value": "200", "footNote": None},
        "11_2020T2": {"value": "ND", "footNote": None},  # doit etre ignore
    },
    "updatingDate": 1671089400000,  # 2022-12-15
}


def test_structurer_depuis_bds_construit_une_ligne_par_periode_et_ventilation():
    resultats = ConstructeurIndicateurs().structurer_depuis_bds(
        INDICATEUR_JSON_MOCK, id_document=42
    )

    # 4 entrees dans data, 1 valeur invalide ("ND") -> 3 lignes attendues
    assert len(resultats) == 3

    par_cle = {(r.region, r.periode): r for r in resultats}
    assert par_cle[("Agriculture", "2020T1")].valeur == 100.0
    assert par_cle[("Agriculture", "2020T2")].valeur == 110.0
    assert par_cle[("Industrie", "2020T1")].valeur == 200.0
    assert ("Industrie", "2020T2") not in par_cle  # la valeur "ND" a bien ete filtree

    for r in resultats:
        assert r.unite == "En millions de dhs"
        assert r.id_document == 42
        assert r.code_bds == "I9999"
        assert r.nom == "Indicateur de test"  # espace de fin nettoye


def test_structurer_depuis_bds_sans_dimension_utilise_juste_la_periode():
    json_simple = {
        "code": "I0001",
        "label": "Indicateur sans ventilation",
        "metaData": {"unit": "%"},
        "periods": ["2020T1"],
        "dimensions": [],
        "data": {"2020T1": {"value": "5.4", "footNote": None}},
    }

    resultats = ConstructeurIndicateurs().structurer_depuis_bds(json_simple, id_document=1)

    assert len(resultats) == 1
    assert resultats[0].region is None
    assert resultats[0].periode == "2020T1"
    assert resultats[0].valeur == 5.4


def test_construire_document_synthetique():
    doc = ConstructeurIndicateurs.construire_document_synthetique(INDICATEUR_JSON_MOCK)

    assert doc.url == "https://bds.hcp.ma/main/indicators/I9999"
    assert doc.titre == "Indicateur de test"
    assert doc.type == "api"
    assert doc.langue == "fr"
    assert doc.date_publication == "2022-12-15"
