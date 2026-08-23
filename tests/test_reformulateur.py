"""Tests de src/reformulateur.py : l'heuristique `ressemble_a_un_followup` est pure
(pas de dependance externe), `reformuler_si_necessaire` est testee avec des fonctions de
reformulation factices (meme esprit que les fonctions embedding/reranking/generation
factices ailleurs dans le projet)."""
import pytest

from src.reformulateur import reformuler_si_necessaire, ressemble_a_un_followup


# --- ressemble_a_un_followup ----------------------------------------------------------

@pytest.mark.parametrize("question", [
    "explique",
    "explique ça",
    "comment ça",
    "et pour 2023 ?",
    "et en 2023 ?",
    "pourquoi ce chiffre ?",
    "tu as dit 43562, comment ça ?",
    "meme chose pour les femmes ?",
])
def test_ressemble_a_un_followup_positifs(question):
    assert ressemble_a_un_followup(question) is True


@pytest.mark.parametrize("question", [
    "Quel est le taux de chômage actuel ?",
    "C'est quoi le RGPH ?",
    "Quelle est la population du Maroc ?",
    "Pourquoi le chômage a-t-il augmenté ces derniers trimestres ?",
    "Quelle est la différence entre taux d'activité et taux d'emploi ?",
])
def test_ressemble_a_un_followup_negatifs_questions_autonomes(question):
    assert ressemble_a_un_followup(question) is False


def test_ressemble_a_un_followup_question_tres_courte_sans_mot_cle():
    # Aucun mot de MOTS_FOLLOWUP, mais une fois les mots-outils retires il ne reste
    # qu'un seul mot de contenu ("population") -- trop vague pour etre autonome.
    assert ressemble_a_un_followup("la population ?") is True


# --- reformuler_si_necessaire ---------------------------------------------------------

def _historique_factice():
    return [
        {
            "question": "population de maroc",
            "reponse": {"texte": "D'après les données du HCP, ... s'élève à 43562 ... pour la période 2050."},
        },
    ]


def test_reformuler_si_necessaire_sans_historique_renvoie_la_question_originale():
    resultat = reformuler_si_necessaire(
        "explique", entrees_historique=[], fonction_reformulation=lambda q, h: "PEU IMPORTE",
    )
    assert resultat == "explique"


def test_reformuler_si_necessaire_sans_fonction_injectee_renvoie_la_question_originale():
    resultat = reformuler_si_necessaire(
        "explique", entrees_historique=_historique_factice(), fonction_reformulation=None,
    )
    assert resultat == "explique"


def test_reformuler_si_necessaire_question_autonome_najamais_appelle_la_fonction():
    # Coeur de l'Option C : pas d'appel LLM sur une question deja autonome, meme si un
    # historique existe et qu'une fonction est injectee.
    def fonction_qui_ne_doit_jamais_etre_appelee(question, historique_texte):
        raise AssertionError("ne doit pas etre appelee pour une question autonome")

    resultat = reformuler_si_necessaire(
        "Quel est le taux de chômage actuel ?",
        entrees_historique=_historique_factice(),
        fonction_reformulation=fonction_qui_ne_doit_jamais_etre_appelee,
    )
    assert resultat == "Quel est le taux de chômage actuel ?"


def test_reformuler_si_necessaire_followup_avec_historique_appelle_la_fonction():
    appels = []

    def fonction_reformulation(question, historique_texte):
        appels.append((question, historique_texte))
        return "Pourquoi la population projetée du Maroc en 2050 est-elle de 43562 milliers ?"

    resultat = reformuler_si_necessaire(
        "comment t'as dit 43562, explique",
        entrees_historique=_historique_factice(),
        fonction_reformulation=fonction_reformulation,
    )

    assert resultat == "Pourquoi la population projetée du Maroc en 2050 est-elle de 43562 milliers ?"
    assert len(appels) == 1
    question_envoyee, historique_envoye = appels[0]
    assert question_envoyee == "comment t'as dit 43562, explique"
    assert "population de maroc" in historique_envoye
    assert "43562" in historique_envoye


def test_reformuler_si_necessaire_exception_retombe_sur_la_question_originale():
    def fonction_qui_plante(question, historique_texte):
        raise RuntimeError("MISTRAL_API_KEY manquante")

    resultat = reformuler_si_necessaire(
        "explique ça", entrees_historique=_historique_factice(), fonction_reformulation=fonction_qui_plante,
    )
    assert resultat == "explique ça"


def test_reformuler_si_necessaire_reponse_vide_retombe_sur_la_question_originale():
    resultat = reformuler_si_necessaire(
        "explique ça", entrees_historique=_historique_factice(), fonction_reformulation=lambda q, h: "   ",
    )
    assert resultat == "explique ça"
