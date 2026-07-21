"""
Tests de LookupStructure avec une vraie base SQLite temporaire (meme esprit que
tests/test_base_donnees.py), peuplee avec des noms d'indicateurs realistes (memes
libelles que ceux vraiment renvoyes par l'API BDS, voir data/indicateurs_cures.py).
"""
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


def test_rechercher_indicateur_discrimine_activite_vs_emploi(conn):
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Quel est le taux net d'activité ?")
    assert resultat.nom == "Taux net d'activité"


def test_rechercher_indicateur_match_ambigu_sur_taux_seul_renvoie_none(conn):
    # Regression : bug reel du 21 juillet 2026, "Quel est le taux de travail ?" ne
    # partage que le mot "taux" avec presque tous les indicateurs de la base --
    # aucun n'est assez distinctif pour etre choisi avec confiance.
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Quel est le taux de travail ?")
    assert resultat is None


def test_rechercher_indicateur_mot_distinctif_unique_reste_accepte(conn):
    # Un score de 1 n'est pas rejete s'il n'y a pas d'ambiguite (un seul candidat
    # contient ce mot) : "urbanisation" seul suffit a identifier l'indicateur.
    _peupler_indicateurs_realistes(conn)
    resultat = LookupStructure(conn).rechercher_indicateur("Urbanisation ?")
    assert resultat.nom == "Taux d'urbanisation"


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
