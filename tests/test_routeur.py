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
    # Regression du 28/07 : questions chiffrees reelles qui ne matchaient aucun mot-cle
    # de l'ancienne liste (ni "taux", ni "nombre", ni "valeur", ni "indice",
    # ni "pourcentage") et tombaient a tort sur NOTION par defaut.
    "Quelle est la structure des actifs occupés sans diplôme ?",
    "Quelle est la répartition de la population par milieu ?",
    "Quelle est la part des femmes au chômage ?",
    "Quel est l'effectif des chômeurs ?",
    "Quelle est l'espérance de vie à la naissance ?",
    "Quelles sont les valeurs ajoutées du secteur agricole ?",
    "Quelle est la population du Maroc en 2024 ?",
])
def test_classifier_questions_chiffrees_formulations_completees_le_28_07(routeur, question):
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


# --- Fallback LLM (dernier recours) -- ajoute le 28/07, voir docstring de module. ---

QUESTION_SANS_MOT_CLE = "Le Maroc"  # ne matche ni MOTS_NOTION, ni MOTS_CHIFFRE, ni une periode


def test_classifier_appelle_le_llm_en_dernier_recours_si_injecte():
    routeur = Routeur(fonction_classification_llm=lambda q: "CHIFFRE")
    assert routeur.classifier(QUESTION_SANS_MOT_CLE) == TypeQuestion.CHIFFRE


def test_classifier_llm_peut_aussi_confirmer_notion():
    routeur = Routeur(fonction_classification_llm=lambda q: "NOTION")
    assert routeur.classifier(QUESTION_SANS_MOT_CLE) == TypeQuestion.NOTION


def test_classifier_llm_qui_leve_une_exception_retombe_sur_notion():
    def fonction_qui_plante(question):
        raise RuntimeError("MISTRAL_API_KEY manquante")

    routeur = Routeur(fonction_classification_llm=fonction_qui_plante)
    assert routeur.classifier(QUESTION_SANS_MOT_CLE) == TypeQuestion.NOTION


def test_classifier_llm_reponse_inattendue_retombe_sur_notion():
    routeur = Routeur(fonction_classification_llm=lambda q: "je ne sais pas")
    assert routeur.classifier(QUESTION_SANS_MOT_CLE) == TypeQuestion.NOTION


def test_classifier_llm_normalise_espaces_et_casse():
    routeur = Routeur(fonction_classification_llm=lambda q: "  chiffre  ")
    assert routeur.classifier(QUESTION_SANS_MOT_CLE) == TypeQuestion.CHIFFRE


def test_classifier_nappelle_jamais_le_llm_si_lheuristique_a_deja_tranche():
    # Le LLM ne doit etre sollicite qu'en dernier recours -- une question deja
    # classee par mot-cle ne doit jamais declencher l'appel (cout/latence evites).
    def fonction_qui_ne_doit_jamais_etre_appelee(question):
        raise AssertionError("le LLM ne doit pas etre appele si l'heuristique a tranche")

    routeur = Routeur(fonction_classification_llm=fonction_qui_ne_doit_jamais_etre_appelee)
    assert routeur.classifier("Quel est le taux de chômage actuel ?") == TypeQuestion.CHIFFRE
    assert routeur.classifier("C'est quoi le RGPH ?") == TypeQuestion.NOTION


def test_classifier_sans_fonction_llm_injectee_comportement_inchange():
    # Retro-compatibilite explicite : aucune regression si rien n'est branche.
    routeur = Routeur()
    assert routeur.classifier(QUESTION_SANS_MOT_CLE) == TypeQuestion.NOTION
