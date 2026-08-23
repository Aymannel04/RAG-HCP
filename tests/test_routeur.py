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


def test_classifier_signal_narratif_combinable_et_chiffre_donne_mixte(routeur):
    # Cas mixte resolu le 28/07 (cite dans docs/note_stockage_routage_benchmark.pdf,
    # Q4) : la question a les deux composantes (pourquoi + taux de + annee), les deux
    # chemins doivent maintenant etre sollicites et fusionnes (voir
    # scripts/poser_question.py / Generateur.ContexteMixte), plutot que de tout miser
    # sur RetrievalReranker seul comme avant.
    question = "Pourquoi le taux de chômage a-t-il augmenté en 2024 ?"
    assert routeur.classifier(question) == TypeQuestion.MIXTE


@pytest.mark.parametrize("question", [
    # "pourquoi" seul, sans aucun signal chiffre -- doit rester NOTION pur (le
    # croisement narratif combinable + chiffre est necessaire, pas narratif seul).
    "Pourquoi le chômage a-t-il augmenté ces derniers trimestres ?",
    "Pourquoi la population marocaine vieillit-elle ?",
])
def test_classifier_narratif_combinable_sans_signal_chiffre_reste_notion(routeur, question):
    assert routeur.classifier(question) == TypeQuestion.NOTION


@pytest.mark.parametrize("question", [
    # Mots narratifs PUREMENT definitionnels/methodologiques : restent NOTION meme
    # combines a un signal chiffre litteral (ex. "indice des"), parce que la question
    # ne demande aucune valeur -- piege explicitement evite, voir docstring de module.
    "Comment est calculé l'indice des prix à la consommation ?",
    "Peux-tu m'expliquer la méthodologie du taux de chômage ?",
    "Quelle est la différence entre taux d'activité et taux d'emploi ?",
])
def test_classifier_narratif_non_combinable_reste_notion_meme_avec_signal_chiffre(routeur, question):
    assert routeur.classifier(question) == TypeQuestion.NOTION


def test_classifier_question_ambigue_sans_mot_cle_retombe_sur_notion(routeur):
    assert routeur.classifier("Le Maroc") == TypeQuestion.NOTION


# --- Salutation / small talk -- ajoute le 23/08, voir docstring de PATTERN_SALUTATION.

@pytest.mark.parametrize("question", [
    "Bonjour",
    "bonjour !",
    "Salut",
    "Salam",
    "slm",
    "Hello",
    "hi",
    "Hey !",
    "Coucou",
    "Bonsoir",
    "Merci",
    "Merci beaucoup",
    "Au revoir",
    "à bientôt",
    "ça va ?",
])
def test_classifier_salutations(routeur, question):
    assert routeur.classifier(question) == TypeQuestion.SALUTATION


@pytest.mark.parametrize("question, type_attendu", [
    # Une salutation combinee a une vraie question ne doit JAMAIS etre avalee par la
    # politesse d'ouverture -- la vraie question l'emporte (voir docstring de
    # `classifier`, ordre de decision : notion/chiffre verifies avant salutation).
    ("Bonjour, quel est le taux de chômage ?", TypeQuestion.CHIFFRE),
    ("Salut, c'est quoi le RGPH ?", TypeQuestion.NOTION),
])
def test_classifier_salutation_combinee_a_une_vraie_question_ignore_la_politesse(routeur, question, type_attendu):
    assert routeur.classifier(question) == type_attendu


def test_classifier_ne_declenche_pas_salutation_sur_un_mot_qui_contient_hi_en_substring(routeur):
    # Piege evite (voir docstring de PATTERN_SALUTATION) : "chiffre" contient "hi" en
    # substring nu -- \b dans le regex doit empecher tout faux positif ici.
    assert routeur.classifier("chiffre") != TypeQuestion.SALUTATION


# --- Fallback LLM (dernier recours) -- ajoute le 28/07, voir docstring de module. ---

QUESTION_SANS_MOT_CLE = "Le Maroc"  # ne matche ni MOTS_NOTION, ni MOTS_CHIFFRE, ni une periode


def test_classifier_appelle_le_llm_en_dernier_recours_si_injecte():
    routeur = Routeur(fonction_classification_llm=lambda q: "CHIFFRE")
    assert routeur.classifier(QUESTION_SANS_MOT_CLE) == TypeQuestion.CHIFFRE


def test_classifier_llm_peut_aussi_confirmer_notion():
    routeur = Routeur(fonction_classification_llm=lambda q: "NOTION")
    assert routeur.classifier(QUESTION_SANS_MOT_CLE) == TypeQuestion.NOTION


def test_classifier_llm_peut_aussi_renvoyer_mixte():
    routeur = Routeur(fonction_classification_llm=lambda q: "MIXTE")
    assert routeur.classifier(QUESTION_SANS_MOT_CLE) == TypeQuestion.MIXTE


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
