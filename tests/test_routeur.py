"""Tests de Routeur.classifier (heuristique, voir src/routeur.py) : pas de dependance
externe necessaire, la fonction est pure."""
import pytest

from src.routeur import Routeur, TypeQuestion


@pytest.fixture
def routeur():
    return Routeur()


@pytest.mark.parametrize("question", [
    "Quel est le taux de chômage actuel ?",
    "Combien y a-t-il de chômeurs au Maroc ?",
    "Quelle est la valeur du PIB en 2023 ?",
    "Quel est le taux d'urbanisation en 2024T2 ?",
])
def test_classifier_questions_chiffrees(routeur, question):
    assert routeur.classifier(question) == TypeQuestion.CHIFFRE


@pytest.mark.parametrize("question", [
    "C'est quoi le RGPH ?",
    "Pourquoi le chômage a-t-il augmenté ces derniers trimestres ?",
    "Comment est calculé l'indice des prix à la consommation ?",
    "Peux-tu m'expliquer la méthodologie du recensement ?",
    "Quelle est la différence entre taux d'activité et taux d'emploi ?",
])
def test_classifier_questions_notion(routeur, question):
    assert routeur.classifier(question) == TypeQuestion.NOTION


def test_classifier_signal_narratif_prioritaire_sur_signal_chiffre(routeur):
    # Cas cite dans docs/note_stockage_routage_benchmark.pdf : la question a les deux
    # composantes, mais seul RetrievalReranker peut repondre au "pourquoi".
    question = "Pourquoi le taux de chômage a-t-il augmenté en 2024 ?"
    assert routeur.classifier(question) == TypeQuestion.NOTION


def test_classifier_question_ambigue_sans_mot_cle_retombe_sur_notion(routeur):
    assert routeur.classifier("Le Maroc") == TypeQuestion.NOTION
