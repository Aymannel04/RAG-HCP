"""
Tests de Generateur avec une vraie base SQLite temporaire. Le chemin chiffre (gabarit,
voir docstring de module) est teste sans aucune dependance externe -- c'est le point
important valide ici, conformement a docs/conception_uml_v3.pdf (figure 5, "sans marge
d'interpretation sur le chiffre lui-meme"). Le chemin notion est teste avec une fonction
de generation factice (le vrai LLM reste a choisir, voir ADR 0002).
"""
import pytest

from src.base_donnees import connecter, inserer_document
from src.generateur import MESSAGE_SANS_INFORMATION, Generateur
from src.models import Chunk, Document, Indicateur


@pytest.fixture
def conn(tmp_path):
    connexion = connecter(tmp_path / "test.db")
    yield connexion
    connexion.close()


@pytest.fixture
def id_document(conn):
    return inserer_document(conn, Document(
        id_document=None, url="https://bds.hcp.ma/main/indicators/I4001",
        titre="Taux de chômage", date_publication="2026-06-01", langue="fr",
        categorie="Marche du travail", type="api",
    ))


def test_generer_reponse_contexte_none_renvoie_message_explicite(conn):
    generateur = Generateur(conn)
    reponse = generateur.generer_reponse("Quel est le taux de chômage ?", None)
    assert reponse.texte == MESSAGE_SANS_INFORMATION
    assert reponse.source_url == ""


def test_generer_reponse_liste_chunks_vide_renvoie_message_explicite(conn):
    generateur = Generateur(conn)
    reponse = generateur.generer_reponse("Question", [])
    assert reponse.texte == MESSAGE_SANS_INFORMATION


def test_generer_reponse_indicateur_ne_necessite_aucun_llm(conn, id_document):
    # Aucune fonction_generation injectee : le chemin chiffre doit fonctionner quand
    # meme, contrairement au chemin notion (voir test plus bas).
    generateur = Generateur(conn)
    indicateur = Indicateur(
        id_indicateur=1, nom="Taux de chômage", valeur=13.3, unite="%",
        periode="2024T2", region=None, id_document=id_document, code_bds="I4001",
    )
    reponse = generateur.generer_reponse("Quel est le taux de chômage ?", indicateur)

    assert "13.3" in reponse.texte
    assert "13.3%" in reponse.texte  # pas d'espace avant % (voir _unite_formatee)
    assert "Taux de chômage" in reponse.texte
    assert "2024T2" in reponse.texte
    assert reponse.source_url == "https://bds.hcp.ma/main/indicators/I4001"


def test_generer_reponse_indicateur_normalise_unite_pourcentage_en_majuscules(conn, id_document):
    # Regression : bug reel trouve le 21 juillet 2026 sur I4001 -- l'API BDS renvoie
    # parfois l'unite en toutes lettres et en majuscules ("POURCENTAGE"), ce qui
    # donnait "9 POURCENTAGE" au lieu de "9%" avant la correction.
    generateur = Generateur(conn)
    indicateur = Indicateur(
        id_indicateur=1, nom="Taux de chômage", valeur=9.0, unite="POURCENTAGE",
        periode="2025", region=None, id_document=id_document, code_bds="I4001",
    )
    reponse = generateur.generer_reponse("Quel est le taux de chômage ?", indicateur)

    assert "9%" in reponse.texte
    assert "POURCENTAGE" not in reponse.texte


def test_generer_reponse_indicateur_unite_longue_est_mise_en_minuscules(conn, id_document):
    generateur = Generateur(conn)
    indicateur = Indicateur(
        id_indicateur=1, nom="Population", valeur=37000.0, unite="MILLIERS",
        periode="2024", region=None, id_document=id_document,
    )
    reponse = generateur.generer_reponse("Question", indicateur)
    assert "37000 milliers" in reponse.texte
    assert "MILLIERS" not in reponse.texte


def test_generer_reponse_indicateur_unite_code_court_reste_telle_quelle(conn, id_document):
    generateur = Generateur(conn)
    indicateur = Indicateur(
        id_indicateur=1, nom="Test", valeur=1.0, unite="MAD",
        periode="2024", region=None, id_document=id_document,
    )
    reponse = generateur.generer_reponse("Question", indicateur)
    assert "1 MAD" in reponse.texte
    assert reponse.source_titre == "Taux de chômage"
    assert reponse.source_date == "2026-06-01"


def test_generer_reponse_indicateur_avec_region_mentionnee_dans_le_texte(conn, id_document):
    generateur = Generateur(conn)
    indicateur = Indicateur(
        id_indicateur=1, nom="Taux de chômage par région", valeur=21.4, unite="%",
        periode="2024T2", region="Rabat-Salé-Kénitra", id_document=id_document,
    )
    reponse = generateur.generer_reponse("Question", indicateur)
    assert "Rabat-Salé-Kénitra" in reponse.texte


def test_generer_reponse_notion_sans_fonction_generation_leve_une_erreur_explicite(conn, id_document):
    generateur = Generateur(conn)  # pas de fonction_generation injectee
    chunks = [Chunk(id_chunk=None, id_document=id_document, texte="Un passage.", position=0)]

    with pytest.raises(NotImplementedError, match="LLM"):
        generateur.generer_reponse("C'est quoi le RGPH ?", chunks)


def test_generer_reponse_notion_avec_fonction_generation_injectee(conn, id_document):
    appels = []

    def fausse_generation(question: str, texte_contexte: str) -> str:
        appels.append((question, texte_contexte))
        return "Reponse synthetisee a partir du contexte."

    generateur = Generateur(conn, fonction_generation=fausse_generation)
    chunks = [
        Chunk(id_chunk=None, id_document=id_document, texte="Le RGPH est un recensement.", position=0),
        Chunk(id_chunk=None, id_document=id_document, texte="Il a lieu tous les 10 ans.", position=1),
    ]

    reponse = generateur.generer_reponse("C'est quoi le RGPH ?", chunks)

    assert reponse.texte == "Reponse synthetisee a partir du contexte."
    assert reponse.source_url == "https://bds.hcp.ma/main/indicators/I4001"
    assert len(appels) == 1
    question_envoyee, contexte_envoye = appels[0]
    assert question_envoyee == "C'est quoi le RGPH ?"
    assert "recensement" in contexte_envoye
    assert "10 ans" in contexte_envoye


def test_generer_reponse_document_source_inconnu_ne_plante_pas(conn):
    generateur = Generateur(conn)
    indicateur = Indicateur(
        id_indicateur=1, nom="Test", valeur=1.0, unite=None, periode="2024",
        region=None, id_document=999999,  # id_document inexistant
    )
    reponse = generateur.generer_reponse("Question", indicateur)
    assert reponse.source_url == ""
