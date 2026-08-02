"""
Tests bout-en-bout de poser_question (Routeur -> LookupStructure/RetrievalReranker ->
Generateur, figures 5 et 6 de docs/conception_uml_v3.pdf), avec de vraies bases
SQLite/Chroma temporaires et des fonctions embedding/reranking/generation factices
(memes raisons qu'ailleurs dans le projet : les vrais modeles ne sont pas telechargeables
dans ce bac a sable de developpement, voir Sprint 2 et ADR 0007).
"""
import re

import fakeredis
import pytest

from scripts.poser_question import poser_question
from src.base_donnees import connecter, inserer_document, inserer_indicateur
from src.cache_redis import CacheReponses, HistoriqueConversation
from src.generateur import Generateur, Reponse
from src.indexeur_texte import IndexeurTexte
from src.models import Document, Indicateur
from src.retrieval_reranker import RetrievalReranker
from src.routeur import Routeur

VOCABULAIRE_TEST = ["chomage", "rgph", "recensement", "population"]


def _fausse_fonction_embedding(textes: list[str]) -> list[list[float]]:
    vecteurs = []
    for texte in textes:
        mots = set(re.findall(r"\w+", texte.lower()))
        vecteur = [1.0 if mot in mots else 0.0 for mot in VOCABULAIRE_TEST]
        if not any(vecteur):
            vecteur[0] = 0.01
        vecteurs.append(vecteur)
    return vecteurs


def _fausse_fonction_reranking(question: str, textes: list[str]) -> list[float]:
    mots_question = set(re.findall(r"\w+", question.lower()))
    return [float(len(mots_question & set(re.findall(r"\w+", t.lower())))) for t in textes]


def _fausse_fonction_generation(question: str, texte_contexte: str) -> str:
    return f"[reponse generee a partir de {len(texte_contexte)} caracteres de contexte]"


@pytest.fixture
def conn(tmp_path):
    connexion = connecter(tmp_path / "test.db")
    yield connexion
    connexion.close()


@pytest.fixture
def indexeur(tmp_path):
    return IndexeurTexte(dossier_chroma=tmp_path / "chroma", fonction_embedding=_fausse_fonction_embedding)


@pytest.fixture
def reranker(indexeur):
    return RetrievalReranker(indexeur, fonction_reranking=_fausse_fonction_reranking)


@pytest.fixture
def routeur():
    return Routeur()


def test_question_chiffree_avec_indicateur_en_base_utilise_lookup_structure(conn, reranker, routeur):
    id_document = inserer_document(conn, Document(
        id_document=None, url="https://bds.hcp.ma/main/indicators/I4001",
        titre="Taux de chômage", date_publication="2026-06-01", langue="fr",
        categorie="Marche du travail", type="api",
    ))
    inserer_indicateur(conn, Indicateur(
        id_indicateur=None, nom="Taux de chômage", valeur=13.3, unite="%",
        periode="2024T2", region=None, id_document=id_document, code_bds="I4001",
    ))
    generateur = Generateur(conn)  # aucun LLM injecte : le chemin chiffre n'en a pas besoin

    reponse = poser_question(conn, reranker, routeur, generateur, "Quel est le taux de chômage actuel ?")

    assert "13.3" in reponse.texte
    assert reponse.source_url == "https://bds.hcp.ma/main/indicators/I4001"


def test_question_chiffree_sans_indicateur_bascule_sur_retrieval_reranker(conn, indexeur, reranker, routeur):
    # Aucun indicateur en base : le repli documente doit chercher dans le texte indexe.
    id_document = inserer_document(conn, Document(
        id_document=None, url="https://www.hcp.ma/rapport.html", titre="Rapport chômage",
        date_publication="2026-06-01", langue="fr", categorie="Marche du travail", type="pdf",
    ))
    indexeur.indexer(
        Document(id_document=id_document, url="x", titre="x", date_publication=None,
                 langue="fr", categorie="", type="pdf"),
        "Le taux de chômage a recule ce trimestre selon les derniers chiffres du HCP.",
    )
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)

    reponse = poser_question(conn, reranker, routeur, generateur, "Quel est le taux de chômage actuel ?")

    assert "reponse generee" in reponse.texte
    assert reponse.source_url == "https://www.hcp.ma/rapport.html"


def test_question_notion_utilise_retrieval_reranker_et_generation(conn, indexeur, reranker, routeur):
    id_document = inserer_document(conn, Document(
        id_document=None, url="https://www.hcp.ma/rgph.html", titre="Le RGPH expliqué",
        date_publication="2026-06-01", langue="fr", categorie="Population et demographie", type="pdf",
    ))
    indexeur.indexer(
        Document(id_document=id_document, url="x", titre="x", date_publication=None,
                 langue="fr", categorie="", type="pdf"),
        "Le RGPH est le recensement general de la population et de l'habitat, mene tous les 10 ans.",
    )
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)

    reponse = poser_question(conn, reranker, routeur, generateur, "C'est quoi le RGPH ?")

    assert "reponse generee" in reponse.texte
    assert reponse.source_url == "https://www.hcp.ma/rgph.html"


def test_question_notion_sans_rien_en_index_renvoie_message_explicite(conn, reranker, routeur):
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)
    reponse = poser_question(conn, reranker, routeur, generateur, "C'est quoi le RGPH ?")
    assert "n'ai pas trouvé" in reponse.texte


# --- Cas mixte (ajoute le 28/07) : dispatch parallele LookupStructure +
# RetrievalReranker, fusion via Generateur.ContexteMixte. -----------------------------

def test_question_mixte_avec_indicateur_et_texte_fusionne_les_deux(conn, indexeur, reranker, routeur):
    id_document_indicateur = inserer_document(conn, Document(
        id_document=None, url="https://bds.hcp.ma/main/indicators/I4001",
        titre="Taux de chômage", date_publication="2026-06-01", langue="fr",
        categorie="Marche du travail", type="api",
    ))
    inserer_indicateur(conn, Indicateur(
        id_indicateur=None, nom="Taux de chômage", valeur=13.3, unite="%",
        periode="2024T2", region=None, id_document=id_document_indicateur, code_bds="I4001",
    ))
    id_document_rapport = inserer_document(conn, Document(
        id_document=None, url="https://www.hcp.ma/rapport-chomage.html",
        titre="Note de conjoncture emploi", date_publication="2026-05-01", langue="fr",
        categorie="Marche du travail", type="pdf",
    ))
    indexeur.indexer(
        Document(id_document=id_document_rapport, url="x", titre="x", date_publication=None,
                 langue="fr", categorie="", type="pdf"),
        "Le chômage a augmenté ce trimestre en raison d'un recul du secteur agricole.",
    )
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)

    reponse = poser_question(
        conn, reranker, routeur, generateur,
        "Pourquoi le taux de chômage a-t-il augmenté ?",
    )

    # Le chiffre exact (gabarit deterministe) ET l'explication generee sont presents.
    assert "13.3" in reponse.texte
    assert "reponse generee" in reponse.texte
    assert reponse.source_url == "https://bds.hcp.ma/main/indicators/I4001"
    assert reponse.source_url_secondaire == "https://www.hcp.ma/rapport-chomage.html"


def test_question_mixte_sans_indicateur_degrade_vers_notion_seul(conn, indexeur, reranker, routeur):
    # Question mixte mais aucun indicateur en base : repli propre vers le chemin
    # notion seul, comme documente dans poser_question.
    id_document = inserer_document(conn, Document(
        id_document=None, url="https://www.hcp.ma/rapport-chomage.html",
        titre="Note de conjoncture emploi", date_publication="2026-05-01", langue="fr",
        categorie="Marche du travail", type="pdf",
    ))
    indexeur.indexer(
        Document(id_document=id_document, url="x", titre="x", date_publication=None,
                 langue="fr", categorie="", type="pdf"),
        "Le chômage a augmenté ce trimestre en raison d'un recul du secteur agricole.",
    )
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)

    reponse = poser_question(
        conn, reranker, routeur, generateur,
        "Pourquoi le taux de chômage a-t-il augmenté ?",
    )

    assert "reponse generee" in reponse.texte
    assert reponse.source_url == "https://www.hcp.ma/rapport-chomage.html"
    assert reponse.source_url_secondaire is None


# --- Cache + historique (ajoutes le 28/07, voir src/cache_redis.py) : injectes via
# fakeredis, memes raisons que tests/test_cache_redis.py -- aucun serveur Redis reel
# necessaire pour valider la logique de branchement. -----------------------------------

class _RerankerInterdit:
    """Duck-type de RetrievalReranker qui echoue si on l'appelle -- sert a prouver
    qu'une reponse en cache court-circuite bien tout recalcul (chunks + generation)."""

    def rechercher_et_trier(self, question):
        raise AssertionError("le reranker ne doit pas etre appele : reponse deja en cache")


@pytest.fixture
def client_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def cache(client_redis):
    return CacheReponses(client_redis)


@pytest.fixture
def historique(client_redis):
    return HistoriqueConversation(client_redis)


def test_question_notion_avec_cache_hit_evite_le_reranker(conn, routeur, cache):
    reponse_en_cache = Reponse(
        texte="[reponse deja en cache]",
        source_url="https://www.hcp.ma/rgph.html",
        source_titre="Le RGPH expliqué",
        source_date="2026-06-01",
    )
    cache.enregistrer("C'est quoi le RGPH ?", reponse_en_cache)
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)

    reponse = poser_question(
        conn, _RerankerInterdit(), routeur, generateur, "C'est quoi le RGPH ?", cache=cache,
    )

    assert reponse == reponse_en_cache


def test_question_notion_sans_cache_hit_enregistre_la_reponse(conn, indexeur, reranker, routeur, cache):
    id_document = inserer_document(conn, Document(
        id_document=None, url="https://www.hcp.ma/rgph.html", titre="Le RGPH expliqué",
        date_publication="2026-06-01", langue="fr", categorie="Population et demographie", type="pdf",
    ))
    indexeur.indexer(
        Document(id_document=id_document, url="x", titre="x", date_publication=None,
                 langue="fr", categorie="", type="pdf"),
        "Le RGPH est le recensement general de la population et de l'habitat, mene tous les 10 ans.",
    )
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)
    assert cache.obtenir("C'est quoi le RGPH ?") is None

    reponse = poser_question(conn, reranker, routeur, generateur, "C'est quoi le RGPH ?", cache=cache)

    assert cache.obtenir("C'est quoi le RGPH ?") == reponse


def test_question_chiffree_ne_touche_pas_au_cache(conn, reranker, routeur, cache):
    id_document = inserer_document(conn, Document(
        id_document=None, url="https://bds.hcp.ma/main/indicators/I4001",
        titre="Taux de chômage", date_publication="2026-06-01", langue="fr",
        categorie="Marche du travail", type="api",
    ))
    inserer_indicateur(conn, Indicateur(
        id_indicateur=None, nom="Taux de chômage", valeur=13.3, unite="%",
        periode="2024T2", region=None, id_document=id_document, code_bds="I4001",
    ))
    generateur = Generateur(conn)

    poser_question(conn, reranker, routeur, generateur, "Quel est le taux de chômage actuel ?", cache=cache)

    assert cache.obtenir("Quel est le taux de chômage actuel ?") is None


def test_question_mixte_ne_touche_pas_au_cache(conn, indexeur, reranker, routeur, cache):
    # Exclusion volontaire (voir docstring de module) : le chiffre d'une reponse mixte
    # doit rester recalcule a chaque appel, jamais servi depuis un cache potentiellement
    # perime.
    id_document_indicateur = inserer_document(conn, Document(
        id_document=None, url="https://bds.hcp.ma/main/indicators/I4001",
        titre="Taux de chômage", date_publication="2026-06-01", langue="fr",
        categorie="Marche du travail", type="api",
    ))
    inserer_indicateur(conn, Indicateur(
        id_indicateur=None, nom="Taux de chômage", valeur=13.3, unite="%",
        periode="2024T2", region=None, id_document=id_document_indicateur, code_bds="I4001",
    ))
    id_document_rapport = inserer_document(conn, Document(
        id_document=None, url="https://www.hcp.ma/rapport-chomage.html",
        titre="Note de conjoncture emploi", date_publication="2026-05-01", langue="fr",
        categorie="Marche du travail", type="pdf",
    ))
    indexeur.indexer(
        Document(id_document=id_document_rapport, url="x", titre="x", date_publication=None,
                 langue="fr", categorie="", type="pdf"),
        "Le chômage a augmenté ce trimestre en raison d'un recul du secteur agricole.",
    )
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)

    poser_question(
        conn, reranker, routeur, generateur,
        "Pourquoi le taux de chômage a-t-il augmenté ?", cache=cache,
    )

    assert cache.obtenir("Pourquoi le taux de chômage a-t-il augmenté ?") is None


def test_historique_enregistre_une_question_chiffree(conn, reranker, routeur, historique):
    id_document = inserer_document(conn, Document(
        id_document=None, url="https://bds.hcp.ma/main/indicators/I4001",
        titre="Taux de chômage", date_publication="2026-06-01", langue="fr",
        categorie="Marche du travail", type="api",
    ))
    inserer_indicateur(conn, Indicateur(
        id_indicateur=None, nom="Taux de chômage", valeur=13.3, unite="%",
        periode="2024T2", region=None, id_document=id_document, code_bds="I4001",
    ))
    generateur = Generateur(conn)

    reponse = poser_question(
        conn, reranker, routeur, generateur, "Quel est le taux de chômage actuel ?",
        historique=historique, id_session="session-test",
    )

    entrees = historique.recuperer("session-test")
    assert len(entrees) == 1
    assert entrees[0]["question"] == "Quel est le taux de chômage actuel ?"
    assert entrees[0]["reponse"]["texte"] == reponse.texte


def test_historique_sans_id_session_ne_leve_pas_erreur_et_nenregistre_rien(conn, reranker, routeur, historique):
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)
    poser_question(conn, reranker, routeur, generateur, "C'est quoi le RGPH ?", historique=historique)
    # Aucune id_session fournie : rien a indexer, mais aucune erreur non plus.
    assert historique.recuperer("") == []


def test_sans_cache_ni_historique_le_comportement_est_inchange(conn, reranker, routeur):
    # Regression : les nouveaux parametres sont optionnels, defaut None -- appel
    # identique aux tests plus anciens de ce fichier, doit se comporter pareil.
    generateur = Generateur(conn, fonction_generation=_fausse_fonction_generation)
    reponse = poser_question(conn, reranker, routeur, generateur, "C'est quoi le RGPH ?")
    assert "n'ai pas trouvé" in reponse.texte
