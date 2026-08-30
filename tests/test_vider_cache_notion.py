"""
Tests de scripts/vider_cache_notion.py::vider (fakeredis, meme patron que
tests/test_cache_redis.py).
"""
import fakeredis
import pytest

from src.cache_redis import CacheReponses, HistoriqueConversation
from src.generateur import Reponse
from scripts.vider_cache_notion import vider


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


def test_vider_sans_client_renvoie_zero():
    assert vider(None) == 0


def test_vider_cache_vide_renvoie_zero(client_redis):
    assert vider(client_redis) == 0


def test_vider_supprime_toutes_les_entrees_du_cache(client_redis):
    cache = CacheReponses(client_redis)
    cache.enregistrer("Quel est le taux de chomage ?", _reponse_notion())
    cache.enregistrer("Quelle est la population ?", _reponse_notion())

    nombre = vider(client_redis)

    assert nombre == 2
    assert cache.obtenir("Quel est le taux de chomage ?") is None
    assert cache.obtenir("Quelle est la population ?") is None


def test_vider_ne_touche_pas_a_lhistorique(client_redis):
    """L'historique de conversation doit survivre au nettoyage du cache -- seul le
    prefixe cache_notion est vise (voir docstring de module)."""
    cache = CacheReponses(client_redis)
    historique = HistoriqueConversation(client_redis)
    cache.enregistrer("Quel est le taux de chomage ?", _reponse_notion())
    historique.ajouter("session-1", "Quel est le taux de chomage ?", _reponse_notion())

    vider(client_redis)

    assert historique.recuperer("session-1") != []
