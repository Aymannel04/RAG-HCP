"""
Tests de src/llm_mistral.py::generer avec requests.post simule (meme patron que
tests/test_scraper.py) -- pas d'appel reseau reel possible dans ce bac a sable
(voir docstring du module).
"""
from unittest.mock import MagicMock, patch

import pytest

from src.llm_mistral import PROMPT_SYSTEME_REFORMULATION, generer, reformuler_question


def test_generer_leve_une_erreur_claire_si_cle_api_absente(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        generer("Question ?", "Contexte.")


@patch("src.llm_mistral.requests.post")
def test_generer_envoie_le_contexte_et_la_question_dans_le_prompt(mock_post, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fausse-cle-de-test")

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "  Le RGPH est un recensement.  "}}]
    }
    mock_post.return_value = mock_resp

    resultat = generer("C'est quoi le RGPH ?", "Le RGPH est mene tous les 10 ans.")

    assert resultat == "Le RGPH est un recensement."  # strip() applique

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer fausse-cle-de-test"
    corps = kwargs["json"]
    assert corps["model"] == "mistral-small-latest"
    messages = corps["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "C'est quoi le RGPH ?" in messages[1]["content"]
    assert "mene tous les 10 ans" in messages[1]["content"]


@patch("src.llm_mistral.requests.post")
def test_generer_propage_les_erreurs_http(mock_post, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fausse-cle-de-test")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("HTTP 401")
    mock_post.return_value = mock_resp

    with pytest.raises(Exception, match="HTTP 401"):
        generer("Question ?", "Contexte.")


# --- reformuler_question (ajoutee le 23/08, voir src/reformulateur.py) ---------------

def test_reformuler_question_leve_une_erreur_claire_si_cle_api_absente(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        reformuler_question("explique ça", "Q: population de maroc\nR: ...43562...2050.")


@patch("src.llm_mistral.requests.post")
def test_reformuler_question_envoie_la_question_et_lhistorique_dans_le_prompt(mock_post, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fausse-cle-de-test")

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "  Pourquoi la population est-elle de 43562 en 2050 ?  "}}]
    }
    mock_post.return_value = mock_resp

    resultat = reformuler_question("explique ça", "Q: population de maroc\nR: ...43562...2050.")

    assert resultat == "Pourquoi la population est-elle de 43562 en 2050 ?"  # strip() applique

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer fausse-cle-de-test"
    corps = kwargs["json"]
    assert corps["temperature"] == 0.0
    messages = corps["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "explique ça" in messages[1]["content"]
    assert "population de maroc" in messages[1]["content"]
    assert "43562" in messages[1]["content"]


@patch("src.llm_mistral.requests.post")
def test_reformuler_question_propage_les_erreurs_http(mock_post, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fausse-cle-de-test")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("HTTP 401")
    mock_post.return_value = mock_resp

    with pytest.raises(Exception, match="HTTP 401"):
        reformuler_question("explique ça", "Q: x\nR: y")


# --- Regression reelle du 30/08 : prompt durci contre la contamination hors-sujet -----
#
# Bug observe en conditions reelles (voir JOURNAL.md) : une question deja autonome et
# sans rapport avec le sujet de l'historique se faisait quand meme enrichir de details
# venant de l'historique. La qualite reelle de la reformulation ne peut se verifier
# qu'en conditions reelles (vrai appel Mistral, voir echange avec Ayman) -- ce test se
# contente de verifier que le prompt envoye au modele contient bien la nouvelle regle
# explicite, pas que le modele la respecte a 100% (impossible a garantir sans reseau).

def test_prompt_reformulation_interdit_explicitement_le_changement_de_sujet():
    assert "change" in PROMPT_SYSTEME_REFORMULATION.lower()
    assert "exactement telle quelle" in PROMPT_SYSTEME_REFORMULATION.lower()
    assert "n'est pas une raison de" in PROMPT_SYSTEME_REFORMULATION.lower()
