"""
Tests de LookupStructure avec une vraie base SQLite temporaire (meme esprit que
tests/test_base_donnees.py), peuplee avec des noms d'indicateurs realistes (memes
libelles que ceux vraiment renvoyes par l'API BDS, voir data/indicateurs_cures.py).
"""
import datetime

import pytest

from src.base_donnees import connecter, inserer_document, inserer_indicateur
from src.lookup_structure import LookupStructure
from src.models import Document, Indicateur


@pytest.fixture
def conn(tmp_path):
    connexion = connecter(tmp_path / "test.db")
    yield connexion
    connexion.close()


def _document_synthetique(conn, titre="Indicateur BDS", url="https://bds.hcp.ma/main/indicators/I1"):
    return inserer_document(conn, Document(
        id_document=None, url=url, titre=titre, date_publication="2026-06-01",
        langue="fr", categorie="Marche du travail", type="api",
    ))


def _peupler_indicateurs_realistes(conn):
    """Reproduit un extrait realiste de la table indicateur, avec plusieurs
    indicateurs partageant le mot "taux" pour tester la discrimination, plusieurs
    periodes pour tester le choix de la plus recente, et une ventilation regionale."""
    id_doc = _document_synthetique(conn)

    lignes = [
        ("Taux de chômage selon le Milieu, le sexe et le groupe d'âges", 13.3, "%", "2023T4", None, "I4001"),
        ("Taux de chômage selon le Milieu, le sexe et le groupe d'âges", 12.9, "%", "2024T1", None, "I4001"),
        ("Taux de chômage selon le Milieu, le sexe et le groupe d'âges", 13.0, "%", "2024T2", None, "I4001"),
        ("Taux net d'activité", 43.0, "%", "2024T2", None, "I40"),
        ("Taux d'emploi des 15 ans et plus", 39.5, "%", "2024T2", None, "I1465"),
        ("Taux de chômage par sexe et région", 21.4, "%", "2024T2", "Rabat-Salé-Kénitra", "I3287"),
        ("Taux de chômage par sexe et région", 9.8, "%", "2024T2", "Souss-Massa", "I3287"),
        ("Taux d'urbanisation", 63.9, "%", "2024", None, "I2790"),
    ]
    for nom, valeur, unite, periode, region, code in lignes:
        inserer_indicateur(conn, Indicateur(
            id_indicateur=None, nom=nom, valeur=valeur, unite=unite, periode=periode,
            region=region, id_document=id_doc, code_bds=code,
        ))
    return id_doc


def test_rechercher_indicateur_choisit_le_bon_nom_parmi_plusieurs_contenant_taux(conn):
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Quel est le taux de chômage actuel ?")
    assert resultat is not None
    assert resultat.nom == "Taux de chômage selon le Milieu, le sexe et le groupe d'âges"


def test_rechercher_indicateur_renvoie_la_periode_la_plus_recente_par_defaut(conn):
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Quel est le taux de chômage actuel ?")
    assert resultat.periode == "2024T2"


def test_rechercher_indicateur_avec_annee_explicite(conn):
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Quel était le taux de chômage en 2023 ?")
    assert resultat.periode == "2023T4"


# --- Series avec projections futures -- corrige le 23/08 suite a un cas reel (voir
# JOURNAL.md) : un indicateur comme "Population du Maroc...1960-2050" contient a la
# fois des donnees observees et des projections dans la meme serie. -------------------

def _peupler_serie_avec_projection(conn):
    """Reproduit le cas reel I1588 : une serie annuelle qui va au-dela de l'annee en
    cours (projection), sans distinction dans les donnees renvoyees par l'API BDS."""
    id_doc = _document_synthetique(conn)
    annee_courante = datetime.date.today().year
    annee_projection = annee_courante + 24  # ex. 2050 si on est en 2026, meme ecart que I1588
    lignes = [
        (str(annee_courante - 1), 36.5),
        (str(annee_courante), 37.0),
        (str(annee_projection), 43.562),
    ]
    for periode, valeur in lignes:
        inserer_indicateur(conn, Indicateur(
            id_indicateur=None, nom="Population du Maroc par annee civile", valeur=valeur,
            unite="milliers", periode=periode, region=None, id_document=id_doc, code_bds="I1588",
        ))
    return annee_courante, annee_projection


def test_rechercher_indicateur_sans_annee_ignore_les_projections_futures(conn):
    annee_courante, _ = _peupler_serie_avec_projection(conn)

    resultat = LookupStructure(conn).rechercher_indicateur("Quelle est la population du Maroc ?")

    assert resultat is not None
    # Doit renvoyer la derniere valeur REELLE (annee en cours), jamais la projection
    # lointaine -- avant le correctif, "ORDER BY periode DESC" sans filtre renvoyait a
    # tort la ligne de projection (chaine la plus grande, donc "la plus recente" au
    # sens du tri seul).
    assert resultat.periode == str(annee_courante)
    assert resultat.valeur == 37.0


def test_rechercher_indicateur_annee_future_explicite_reste_servie(conn):
    # Une projection reste accessible si explicitement demandee -- seul le comportement
    # PAR DEFAUT (sans annee) exclut les periodes futures.
    _, annee_projection = _peupler_serie_avec_projection(conn)

    resultat = LookupStructure(conn).rechercher_indicateur(
        f"Quelle est la population du Maroc en {annee_projection} ?"
    )

    assert resultat is not None
    assert resultat.periode == str(annee_projection)
    assert resultat.valeur == 43.562


def test_rechercher_indicateur_discrimine_activite_vs_emploi(conn):
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Quel est le taux net d'activité ?")
    assert resultat.nom == "Taux net d'activité"


def test_rechercher_indicateur_match_ambigu_sur_taux_seul_renvoie_none(conn):
    # Regression : "Quel est le taux de travail ?" ne partage que le mot "taux" avec
    # presque tous les indicateurs de la base -- aucun n'est assez distinctif pour
    # etre choisi avec confiance.
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Quel est le taux de travail ?")
    assert resultat is None


def test_rechercher_indicateur_mot_distinctif_unique_reste_accepte(conn):
    # Un score de 1 n'est pas rejete s'il n'y a pas d'ambiguite (un seul candidat
    # contient ce mot) : "urbanisation" seul suffit a identifier l'indicateur.
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Urbanisation ?")
    assert resultat.nom == "Taux d'urbanisation"


def test_rechercher_indicateur_match_ambigu_sur_2_mots_communs_entre_sujets_sans_rapport_renvoie_none(conn):
    # Regression reelle (30/08, voir JOURNAL.md) : une question reformulee de travers
    # par le LLM de reformulation a matche a EGALITE (score 2 chacun) deux indicateurs
    # totalement sans rapport -- "Taux de chomage..." (via "taux"+"chomage") et
    # "Population du Maroc..." (via "population"+"maroc"). Avant le correctif, le refus
    # d'ambiguite ne se declenchait que pour un score <= 1 : le code choisissait alors
    # silencieusement "Population du Maroc..." (premier insere) au lieu de refuser.
    _peupler_indicateurs_realistes(conn)
    _peupler_serie_avec_projection(conn)  # ajoute "Population du Maroc par annee civile"

    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quel est le taux de chômage au Maroc selon le Recensement Général de "
        "l'Habitat et de la Population (RGPH) ?"
    )

    assert resultat is None


def test_rechercher_indicateur_sans_accents_matche_quand_meme(conn):
    # Regression : "chomage" tape sans accent ne correspondait pas a "chômage" en
    # base -- faisait basculer a tort sur RetrievalReranker au lieu de la reponse
    # structuree exacte.
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Quel est le taux de chomage pour les femmes")
    assert resultat is not None
    assert resultat.nom == "Taux de chômage selon le Milieu, le sexe et le groupe d'âges"


def test_rechercher_indicateur_region_sans_accents_matche_quand_meme(conn):
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quel est le taux de chomage par region a Rabat-Sale-Kenitra ?"
    )
    assert resultat.region == "Rabat-Salé-Kénitra"


def test_rechercher_indicateur_avec_region_mentionnee(conn):
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quel est le taux de chômage par région à Rabat-Salé-Kénitra ?"
    )
    assert resultat.region == "Rabat-Salé-Kénitra"
    assert resultat.valeur == pytest.approx(21.4)


def test_rechercher_indicateur_sans_indicateur_connu_renvoie_none(conn):
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("C'est quoi le RGPH ?")
    assert resultat is None


def test_rechercher_indicateur_base_vide_renvoie_none(conn):
    resultat = LookupStructure(conn).rechercher_indicateur("Quel est le taux de chômage ?")
    assert resultat is None


# --- Ventilation par dimension (sexe/milieu/diplome/branche) -- resolu le 28/07,
# voir TODO.md et le docstring de src/lookup_structure.py section "Ventilation". ---

def _peupler_indicateurs_ventiles(conn):
    """Jeu de donnees dedie aux tests de ventilation, avec plusieurs formes reelles :
    croisement complet sans ligne marginale (aucun repli fiable possible), croisement
    avec ligne marginale par sexe (repli possible), dimension simple milieu avec label
    agregat "National", dimension simple diplome SANS label agregat (aucune ligne ne
    couvre toutes les categories), et branche d'activite (17 valeurs reelles, ici un
    sous-ensemble)."""
    id_doc = _document_synthetique(conn)

    lignes = [
        # Croisement sexe x milieu, AUCUNE ligne "Feminin" seule (le cas du monde reel
        # le plus defavorable, cf. TODO.md) -> doit refuser (ambigu) plutot que deviner.
        ("Taux d'activite par sexe et milieu", 45.2, "%", "2024", "Masculin, Urbain", "IX1"),
        ("Taux d'activite par sexe et milieu", 22.1, "%", "2024", "Féminin, Urbain", "IX1"),
        ("Taux d'activite par sexe et milieu", 50.3, "%", "2024", "Masculin, Rural", "IX1"),
        ("Taux d'activite par sexe et milieu", 28.7, "%", "2024", "Féminin, Rural", "IX1"),

        # Meme croisement, mais AVEC une ligne marginale par sexe (region = "Feminin,
        # National") -> doit la choisir de preference aux sous-groupes urbain/rural.
        ("Taux d'emploi par sexe et milieu", 60.0, "%", "2024", "Masculin, National", "IX2"),
        ("Taux d'emploi par sexe et milieu", 20.0, "%", "2024", "Féminin, National", "IX2"),
        ("Taux d'emploi par sexe et milieu", 65.0, "%", "2024", "Masculin, Urbain", "IX2"),
        ("Taux d'emploi par sexe et milieu", 18.0, "%", "2024", "Féminin, Urbain", "IX2"),

        # Dimension simple milieu, avec agregat "National".
        ("Indice synthétique de fécondité", 2.1, "enfants/femme", "2024", "National", "I2786"),
        ("Indice synthétique de fécondité", 1.8, "enfants/femme", "2024", "Urbain", "I2786"),
        ("Indice synthétique de fécondité", 2.6, "enfants/femme", "2024", "Rural", "I2786"),

        # Dimension simple diplome, SANS aucune ligne agregat -> pas de reponse fiable
        # si le diplome n'est pas precise (corrige un bug latent de l'ancien code).
        ("Structure des actifs occupés", 30.0, "%", "2024", "Sans diplôme", "I2863"),
        ("Structure des actifs occupés", 40.0, "%", "2024", "Niveau moyen", "I2863"),
        ("Structure des actifs occupés", 30.0, "%", "2024", "Niveau supérieur", "I2863"),

        # Branche d'activite (sous-ensemble des 17 valeurs reelles de I3181).
        ("Valeurs ajoutées par branche d'activité", 120.5, "Mrd DH", "2024", "Agriculture", "I3181"),
        ("Valeurs ajoutées par branche d'activité", 340.2, "Mrd DH", "2024", "Commerce", "I3181"),
        ("Valeurs ajoutées par branche d'activité", 980.0, "Mrd DH", "2024", "PIB", "I3181"),
    ]
    for nom, valeur, unite, periode, region, code in lignes:
        inserer_indicateur(conn, Indicateur(
            id_indicateur=None, nom=nom, valeur=valeur, unite=unite, periode=periode,
            region=region, id_document=id_doc, code_bds=code,
        ))
    return id_doc


def test_ventilation_sexe_sans_ligne_marginale_refuse_de_deviner(conn):
    # Aucune ligne "Feminin" seule n'existe (toujours croise avec le milieu) : deviner
    # entre "Feminin, Urbain" et "Feminin, Rural" serait exactement le risque documente
    # dans TODO.md -- LookupStructure doit renvoyer None plutot que trancher au hasard.
    _peupler_indicateurs_ventiles(conn)
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quel est le taux d'activité des femmes ?"
    )
    assert resultat is None


def test_ventilation_sexe_avec_ligne_marginale_est_choisie(conn):
    # Ici une ligne "Feminin, National" existe (aucun autre label que le sexe demande
    # + un label agregat) : c'est le meilleur candidat, sans ambiguite avec les
    # sous-groupes urbain/rural (qui ont un label "en trop" non-agregat).
    _peupler_indicateurs_ventiles(conn)
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quel est le taux d'emploi des femmes ?"
    )
    assert resultat is not None
    assert resultat.region == "Féminin, National"
    assert resultat.valeur == pytest.approx(20.0)


def test_ventilation_milieu_simple_avec_terme_naturel(conn):
    _peupler_indicateurs_ventiles(conn)
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quel est l'indice synthétique de fécondité en milieu urbain ?"
    )
    assert resultat is not None
    assert resultat.region == "Urbain"
    assert resultat.valeur == pytest.approx(1.8)


def test_ventilation_aucune_dimension_demandee_choisit_le_label_agregat(conn):
    # Aucun milieu mentionne -> doit choisir la ligne "National" (agregat), pas une
    # ligne arbitraire parmi Urbain/Rural/National.
    _peupler_indicateurs_ventiles(conn)
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quel est l'indice synthétique de fécondité ?"
    )
    assert resultat is not None
    assert resultat.region == "National"
    assert resultat.valeur == pytest.approx(2.1)


def test_ventilation_sans_label_agregat_disponible_renvoie_none(conn):
    # "Structure des actifs occupes" n'a que des lignes par diplome, aucune ligne
    # agregee toutes categories confondues -- corrige un bug latent ou l'ancien code
    # aurait renvoye une categorie arbitraire (ordre d'insertion) comme si elle
    # representait toute la population.
    _peupler_indicateurs_ventiles(conn)
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quelle est la structure des actifs occupés ?"
    )
    assert resultat is None


def test_ventilation_diplome_explicite_est_resolue(conn):
    _peupler_indicateurs_ventiles(conn)
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quelle est la part des actifs occupés sans diplôme ?"
    )
    assert resultat is not None
    assert resultat.region == "Sans diplôme"
    assert resultat.valeur == pytest.approx(30.0)


def test_ventilation_sexe_avec_label_bds_sans_accent(conn):
    # Regression du 28/07 : le vrai label BDS observe sur I4001 est "Feminin" SANS
    # accent (verifie via scripts/diagnostic_dimensions.py), alors que le dictionnaire
    # de synonymes est ecrit avec l'accent standard ("Féminin" -> ...). La
    # correspondance doit passer par une forme normalisee des deux cotes, pas par une
    # egalite stricte de chaine, sinon aucun synonyme ne matche jamais un vrai label.
    id_doc = _document_synthetique(conn)
    for valeur, region in [(9.5, "Total"), (14.6, "Feminin"), (6.5, "Masculin")]:
        inserer_indicateur(conn, Indicateur(
            id_indicateur=None, nom="Taux de chômage selon le sexe", valeur=valeur,
            unite="%", periode="2025", region=region, id_document=id_doc, code_bds="I4001",
        ))
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quel est le taux de chômage des femmes ?"
    )
    assert resultat is not None
    assert resultat.region == "Feminin"
    assert resultat.valeur == pytest.approx(14.6)


def test_ventilation_branche_activite_est_resolue(conn):
    _peupler_indicateurs_ventiles(conn)
    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quelles sont les valeurs ajoutées de la branche agriculture ?"
    )
    assert resultat is not None
    assert resultat.region == "Agriculture"
    assert resultat.valeur == pytest.approx(120.5)


# --- Ligne agregee ET lignes ventilees coexistent -- corrige le 31/08 (bug reel
# observe en conditions reelles, voir JOURNAL.md). ------------------------------------

def _peupler_indicateur_avec_agregat_et_ventilations(conn):
    """Reproduit le cas reel I4001 ("Taux de chomage selon le Milieu, le sexe et le
    groupe d'ages") : des lignes ventilees a un seul label (Urbain/Rural/Masculin/
    Feminin, jamais croisees entre elles dans ce sous-ensemble) COEXISTENT avec une
    vraie ligne agregee nationale (region IS NULL). Avant le correctif, une question
    sans dimension demandee matchait a egalite plusieurs de ces combinaisons a un seul
    label et etait donc refusee (None), sans jamais considerer la ligne agregee,
    pourtant la reponse correcte."""
    id_doc = _document_synthetique(conn)
    lignes = [
        ("Taux de chômage national", 13.3, "%", "2024", None),
        ("Taux de chômage national", 13.0, "%", "2023", None),
        ("Taux de chômage national", 12.9, "%", "2024", "Urbain"),
        ("Taux de chômage national", 9.5, "%", "2024", "Rural"),
        ("Taux de chômage national", 11.8, "%", "2024", "Masculin"),
        ("Taux de chômage national", 16.2, "%", "2024", "Féminin"),
    ]
    for nom, valeur, unite, periode, region in lignes:
        inserer_indicateur(conn, Indicateur(
            id_indicateur=None, nom=nom, valeur=valeur, unite=unite, periode=periode,
            region=region, id_document=id_doc, code_bds="I4001",
        ))
    return id_doc


def test_ventilation_aucune_dimension_avec_agregat_coexistant_choisit_lagregat(conn):
    _peupler_indicateur_avec_agregat_et_ventilations(conn)

    resultat = LookupStructure(conn).rechercher_indicateur("Quel est le taux de chômage ?")

    assert resultat is not None
    assert resultat.region is None
    assert resultat.valeur == pytest.approx(13.3)  # periode la plus recente (2024)


def test_ventilation_dimension_explicite_avec_agregat_coexistant_reste_ventilee(conn):
    # L'ajout de la ligne agregee comme candidate ne doit s'appliquer que quand AUCUNE
    # dimension n'est demandee -- une question qui precise "urbain" doit toujours
    # recevoir la ligne ventilee correspondante, pas l'agregat.
    _peupler_indicateur_avec_agregat_et_ventilations(conn)

    resultat = LookupStructure(conn).rechercher_indicateur(
        "Quel est le taux de chômage en milieu urbain ?"
    )

    assert resultat is not None
    assert resultat.region == "Urbain"
    assert resultat.valeur == pytest.approx(12.9)
