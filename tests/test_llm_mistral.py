"""
Tests de src/llm_mistral.py::generer avec requests.post simule (meme patron que
tests/test_scraper.py) -- pas d'appel reseau reel possible dans ce bac a sable
(voir docstring du module).
"""
from unittest.mock import MagicMock, patch

import pytest

from src.llm_mistral import generer


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
