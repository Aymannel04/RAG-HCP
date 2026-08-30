"""
Tests de src/cache_redis.py avec fakeredis (faux serveur Redis en memoire, meme API
que le vrai client `redis` -- voir docstring de src/cache_redis.py). Aucun serveur
Redis reel necessaire pour ces tests ; la validation en conditions reelles (vrai
serveur Redis sur la machine d'Ayman) reste a faire separement, meme principe que pour
BGE-M3/Mistral ailleurs dans le projet.
"""
import fakeredis
import pytest

from src.cache_redis import (
    TTL_CACHE_NOTION,
    TTL_HISTORIQUE,
    CacheReponses,
    HistoriqueConversation,
    normaliser_question,
)
from src.generateur import Reponse


@pytest.fixture
def client_redis():
    return fakeredis.FakeRedis(decode_responses=True)


def _reponse_notion():
    return Reponse(
        texte="D'apres le HCP, le taux de chomage...",
        source_url="https://bds.hcp.ma/main/indicators/I4001",
        source_titre="Taux de chomage",
        source_date="2026-06-01",
    )


def test_normaliser_question_reduit_espaces_et_casse():
    assert normaliser_question("  Quel   Est le TAUX ?  ") == "quel est le taux ?"


def test_cache_sans_client_renvoie_toujours_none():
    cache = CacheReponses(client_redis=None)
    assert cache.obtenir("Quel est le taux de chomage ?") is None


def test_cache_sans_client_enregistrer_ne_leve_pas_erreur():
    cache = CacheReponses(client_redis=None)
    cache.enregistrer("Quel est le taux de chomage ?", _reponse_notion())  # ne doit pas lever


def test_cache_question_jamais_posee_renvoie_none(client_redis):
    cache = CacheReponses(client_redis)
    assert cache.obtenir("Question jamais posee ?") is None


def test_cache_enregistrer_puis_obtenir_renvoie_la_meme_reponse(client_redis):
    cache = CacheReponses(client_redis)
    reponse = _reponse_notion()
    cache.enregistrer("Quel est le taux de chomage ?", reponse)
    recuperee = cache.obtenir("Quel est le taux de chomage ?")
    assert recuperee == reponse


def test_cache_correspondance_est_insensible_a_la_casse_et_aux_espaces(client_redis):
    cache = CacheReponses(client_redis)
    reponse = _reponse_notion()
    cache.enregistrer("Quel est le taux de chomage ?", reponse)
    assert cache.obtenir("  quel   est LE taux de chomage ?  ") == reponse


def test_cache_questions_differentes_ne_se_confondent_pas(client_redis):
    cache = CacheReponses(client_redis)
    reponse = _reponse_notion()
    cache.enregistrer("Quel est le taux de chomage ?", reponse)
    assert cache.obtenir("Quel est le taux de pauvrete ?") is None


def test_cache_pose_un_ttl_de_24h(client_redis):
    cache = CacheReponses(client_redis)
    cache.enregistrer("Quel est le taux de chomage ?", _reponse_notion())
    cle = "rag_hcp:cache_notion:" + normaliser_question("Quel est le taux de chomage ?")
    ttl = client_redis.ttl(cle)
    assert 0 < ttl <= TTL_CACHE_NOTION


def test_historique_sans_client_recuperer_renvoie_liste_vide():
    historique = HistoriqueConversation(client_redis=None)
    assert historique.recuperer("session-1") == []


def test_historique_sans_client_ajouter_ne_leve_pas_erreur():
    historique = HistoriqueConversation(client_redis=None)
    historique.ajouter("session-1", "Quel est le taux de chomage ?", _reponse_notion())  # ne doit pas lever


def test_historique_ajouter_puis_recuperer_conserve_lordre(client_redis):
    historique = HistoriqueConversation(client_redis)
    historique.ajouter("session-1", "Question 1 ?", _reponse_notion())
    historique.ajouter("session-1", "Question 2 ?", _reponse_notion())
    entrees = historique.recuperer("session-1")
    assert [e["question"] for e in entrees] == ["Question 1 ?", "Question 2 ?"]
    assert entrees[0]["reponse"]["texte"] == _reponse_notion().texte


def test_historique_sessions_distinctes_sont_isolees(client_redis):
    historique = HistoriqueConversation(client_redis)
    historique.ajouter("session-1", "Question A ?", _reponse_notion())
    historique.ajouter("session-2", "Question B ?", _reponse_notion())
    assert [e["question"] for e in historique.recuperer("session-1")] == ["Question A ?"]
    assert [e["question"] for e in historique.recuperer("session-2")] == ["Question B ?"]


def test_historique_session_inconnue_renvoie_liste_vide(client_redis):
    historique = HistoriqueConversation(client_redis)
    assert historique.recuperer("session-inconnue") == []


def test_historique_pose_un_ttl_de_24h(client_redis):
    """Regression du bug trouve le 27/08 (voir JOURNAL.md) : la cle d'historique
    n'avait auparavant aucune expiration (TTL -1, confirme en conditions reelles
    via redis-cli), elle s'accumulait indefiniment."""
    historique = HistoriqueConversation(client_redis)
    historique.ajouter("session-1", "Question 1 ?", _reponse_notion())
    cle = "rag_hcp:historique:session-1"
    ttl = client_redis.ttl(cle)
    assert 0 < ttl <= TTL_HISTORIQUE


def test_historique_ttl_est_repousse_a_chaque_nouvel_ajout(client_redis):
    """Le TTL est glissant : un deuxieme message dans la meme session ne doit
    jamais faire baisser le TTL en dessous de ce qu'il etait juste apres le
    premier -- une conversation active ne doit jamais expirer en cours de route."""
    historique = HistoriqueConversation(client_redis)
    historique.ajouter("session-1", "Question 1 ?", _reponse_notion())
    cle = "rag_hcp:historique:session-1"
    client_redis.expire(cle, 10)  # simule un TTL presque expire
    historique.ajouter("session-1", "Question 2 ?", _reponse_notion())
    assert client_redis.ttl(cle) > 10
