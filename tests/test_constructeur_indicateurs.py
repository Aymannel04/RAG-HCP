"""
Tests du module ConstructeurIndicateurs (chemin API BDS). Le JSON mock ci-dessous
reproduit en miniature la forme réelle observée sur `GET /api/v1/indicators/I3181`
(vérifiée par appel réel, voir docs/adr/0004-*.md) : deux modalités de ventilation,
deux périodes, une valeur manquante ("ND") à ignorer.
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


def test_structurer_depuis_bds_gere_dimensions_null():
    # Cas reel observe sur I2790 "Taux d'urbanisation" : l'API renvoie "dimensions": null
    # (pas []) quand l'indicateur n'a pas de ventilation. dict.get(cle, []) ne rattrape
    # pas ce cas car la cle EST presente (juste avec une valeur null).
    json_sans_dimension = {
        "code": "I2790",
        "label": "Taux d'urbanisation",
        "metaData": {"unit": "%"},
        "periods": ["2020"],
        "dimensions": None,
        "data": {"2020": {"value": "63.5", "footNote": None}},
    }

    resultats = ConstructeurIndicateurs().structurer_depuis_bds(json_sans_dimension, id_document=1)

    assert len(resultats) == 1
    assert resultats[0].region is None
    assert resultats[0].valeur == 63.5


# Reproduit (en miniature) la vraie reponse de GET /api/v1/indicators/I4001, obtenue
# le 28/07 via scripts/diagnostic_dimensions.py -- trois dimensions croisees, ids de
# modalite joints par un POINT dans la cle (jamais par "_", contrairement a
# l'hypothese initiale qui faisait echouer silencieusement tout indicateur
# multi-dimension, voir TODO.md/JOURNAL.md du 28/07). Chaque dimension a une modalite
# "total": true (l'agregat de cette dimension precise).
INDICATEUR_JSON_MULTI_DIMENSIONS_MOCK = {
    "code": "I4001",
    "label": "Taux de chômage selon le Milieu, le sexe et le groupe d'âges",
    "metaData": {"unit": "%"},
    "periods": ["2025"],
    "dimensions": [
        {
            "id": 3, "label": "Mileu",
            "modalites": [
                {"id": 11, "label": "National", "total": True},
                {"id": 12, "label": "Urbain", "total": False},
                {"id": 13, "label": "Rural", "total": False},
            ],
        },
        {
            "id": 4, "label": "Age",
            "modalites": [
                {"id": 14, "label": "15-24 ans", "total": False},
                {"id": 18, "label": "15 ans et plus", "total": True},
            ],
        },
        {
            "id": 5, "label": "Sexe",
            "modalites": [
                {"id": 19, "label": "Total", "total": True},
                {"id": 20, "label": "Masculin", "total": False},
                {"id": 21, "label": "Feminin", "total": False},
            ],
        },
    ],
    "data": {
        # Milieu, Age et Sexe tous a leur modalite "total" -> agregat national complet
        "11.18.19_2025": {"value": "9.0", "footNote": None},
        # Milieu et Age agreges, seul le Sexe est specifique -> ne garde que "Feminin"
        "11.18.21_2025": {"value": "14.6", "footNote": None},
        "11.18.20_2025": {"value": "6.5", "footNote": None},
        # Aucune dimension agregee -> les trois labels apparaissent
        "12.14.21_2025": {"value": "28.3", "footNote": None},
    },
}


def test_structurer_depuis_bds_ids_modalite_joints_par_point():
    # Regression du bug du 28/07 : cle.split("_") traitait "11.18.21" comme un seul id
    # non numerique (a cause des points) et le rejetait -> region=None pour toutes les
    # lignes d'un indicateur a plusieurs dimensions, meme quand une vraie ventilation
    # existait. Doit maintenant eclater le prefixe sur "." pour retrouver les ids.
    resultats = ConstructeurIndicateurs().structurer_depuis_bds(
        INDICATEUR_JSON_MULTI_DIMENSIONS_MOCK, id_document=1
    )
    par_region = {r.region: r.valeur for r in resultats}

    assert par_region[None] == 9.0  # toutes dimensions a leur modalite "total"
    assert par_region["Feminin"] == 14.6  # Milieu/Age agreges, seul Sexe reste (label BDS reel, sans accent)
    assert par_region["Masculin"] == 6.5
    assert par_region["Urbain, 15-24 ans, Feminin"] == 28.3  # aucune dimension agregee


# --- Chemin repli PDF/XLSX (ConstructeurIndicateurs.structurer) : motif dictionnaire
# Code/Nom/Unité + table de données au format large, voir docstring de module. Reproduit
# en miniature la structure réelle de data/raw/248688.xlsx ("Principaux indicateurs
# trimestriels rétropolés..., méthodologie EMO").

TABLEAU_DICTIONNAIRE = [
    ["Code", "Nom", "Unité"],
    ["AN", "Année", "-"],
    ["TRIM", "Trimestre", "-"],
    ["TX.CH.STR", "Taux de chômage strict", "%"],
    ["TX.CH.STR.U", "Taux de chômage strict, Urbain", "%"],
    ["TX.CH.STR.F", "Taux de chômage strict, Femmes", "%"],
]

TABLEAU_DONNEES = [
    ["AN", "TRIM", "TX.CH.STR", "TX.CH.STR.U", "TX.CH.STR.F"],
    ["2025", "3", "11.9", "15.8", "20.9"],
    ["2025", "4", "11.5", "15.3", "20.4"],
]


def test_structurer_reconnait_le_motif_dictionnaire_et_construit_les_indicateurs():
    resultats = ConstructeurIndicateurs().structurer(
        id_document=100, tableaux=[TABLEAU_DICTIONNAIRE, TABLEAU_DONNEES]
    )

    par_cle = {(r.nom, r.region, r.periode): r for r in resultats}
    assert par_cle[("Taux de chômage strict", None, "2025T4")].valeur == 11.5
    assert par_cle[("Taux de chômage strict", "Urbain", "2025T4")].valeur == 15.3
    assert par_cle[("Taux de chômage strict", "Femmes", "2025T4")].valeur == 20.4
    assert par_cle[("Taux de chômage strict", None, "2025T3")].valeur == 11.9

    for r in resultats:
        assert r.unite == "%"
        assert r.id_document == 100
        assert r.code_bds is None  # jamais issu de l'API BDS


def test_structurer_gere_une_periode_sans_trimestre():
    dictionnaire = [
        ["Code", "Nom", "Unité"],
        ["AN", "Année", "-"],
        ["POP", "Population du Maroc", "Millier"],
    ]
    donnees = [["AN", "POP"], ["2024", "37000"]]

    resultats = ConstructeurIndicateurs().structurer(id_document=1, tableaux=[dictionnaire, donnees])

    assert len(resultats) == 1
    assert resultats[0].periode == "2024"  # pas de "T..." si aucune colonne Trimestre
    assert resultats[0].valeur == 37000.0


def test_structurer_ignore_les_cellules_vides_ou_non_numeriques():
    donnees = [
        ["AN", "TRIM", "TX.CH.STR"],
        ["2025", "4", ""],  # cellule vide -> ignorée
        ["2025", "3", "ND"],  # non numérique -> ignorée
        ["2025", "2", "11.2"],  # valide
    ]

    resultats = ConstructeurIndicateurs().structurer(
        id_document=1, tableaux=[TABLEAU_DICTIONNAIRE, donnees]
    )

    assert len(resultats) == 1
    assert resultats[0].periode == "2025T2"
    assert resultats[0].valeur == 11.2


def test_structurer_renvoie_liste_vide_si_aucun_motif_dictionnaire_reconnu():
    # Un tableau "normal" (ex. extrait d'un PDF quelconque, ou la feuille "Avis aux
    # utilisateurs" d'un XLSX réel) ne doit jamais être mal interprété comme des
    # indicateurs -- structurer() doit renvoyer [] plutôt qu'inventer.
    tableau_quelconque = [["Année", "Remarque"], ["2025", "Note méthodologique"]]

    resultats = ConstructeurIndicateurs().structurer(id_document=1, tableaux=[tableau_quelconque])

    assert resultats == []


def test_structurer_renvoie_liste_vide_sur_tableaux_vides():
    assert ConstructeurIndicateurs().structurer(id_document=1, tableaux=[]) == []


def test_construire_document_synthetique():
    doc = ConstructeurIndicateurs.construire_document_synthetique(INDICATEUR_JSON_MOCK)

    assert doc.url == "https://bds.hcp.ma/main/indicators/I9999"
    assert doc.titre == "Indicateur de test"
    assert doc.type == "api"
    assert doc.langue == "fr"
    assert doc.date_publication == "2022-12-15"
