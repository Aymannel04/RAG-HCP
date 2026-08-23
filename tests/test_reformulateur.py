"""Tests de src/reformulateur.py::reformuler_si_necessaire, avec des fonctions de
reformulation factices (meme esprit que les fonctions embedding/reranking/generation
factices ailleurs dans le projet).

Pas de test d'heuristique de detection de follow-up ici : une premiere version basee
sur des mots-cles (`ressemble_a_un_followup`) a ete essayee puis abandonnee le 23/08,
testee en conditions reelles ("du derniere annee ?" n'a matche aucun mot-cle) -- voir
docstring de module. La regle actuelle est purement structurelle (un historique
existe-t-il ?), donc rien a tester au niveau du contenu de la question elle-meme."""
import pytest

from src.reformulateur import reformuler_si_necessaire


def _historique_factice():
    return [
        {
            "question": "population de maroc",
            "reponse": {"texte": "D'après les données du HCP, ... s'élève à 38050 ... pour la période 2026."},
        },
    ]


def test_reformuler_si_necessaire_sans_historique_renvoie_la_question_originale():
    # Premiere question de la session : rien a reformuler a partir de, aucun cout ajoute.
    resultat = reformuler_si_necessaire(
        "Quel est le taux de chômage ?", entrees_historique=[], fonction_reformulation=lambda q, h: "PEU IMPORTE",
    )
    assert resultat == "Quel est le taux de chômage ?"


def test_reformuler_si_necessaire_sans_fonction_injectee_renvoie_la_question_originale():
    resultat = reformuler_si_necessaire(
        "du derniere annee ?", entrees_historique=_historique_factice(), fonction_reformulation=None,
    )
    assert resultat == "du derniere annee ?"


def test_reformuler_si_necessaire_avec_historique_appelle_toujours_la_fonction():
    # Coeur de la decision retenue (voir docstring de module) : aucune tentative de
    # deviner si CETTE question precise "ressemble" a un follow-up -- des qu'un
    # historique existe, la reformulation est systematique, quelle que soit la
    # formulation de la question (meme une question deja parfaitement autonome).
    appels = []

    def fonction_reformulation(question, historique_texte):
        appels.append((question, historique_texte))
        return "Quelle est la population du Maroc pour la derniere annee disponible ?"

    resultat = reformuler_si_necessaire(
        "du derniere annee ?",
        entrees_historique=_historique_factice(),
        fonction_reformulation=fonction_reformulation,
    )

    assert resultat == "Quelle est la population du Maroc pour la derniere annee disponible ?"
    assert len(appels) == 1
    question_envoyee, historique_envoye = appels[0]
    assert question_envoyee == "du derniere annee ?"
    assert "population de maroc" in historique_envoye
    assert "38050" in historique_envoye


def test_reformuler_si_necessaire_appelle_meme_pour_une_question_deja_autonome():
    # Meme une question parfaitement formee et autonome declenche l'appel des qu'un
    # historique existe -- c'est le compromis assume de la decision retenue (fiabilite
    # plutot qu'optimisation des couts, voir docstring de module).
    appels = []

    def fonction_reformulation(question, historique_texte):
        appels.append(question)
        return question  # deja autonome : le LLM la renvoie quasiment inchangee

    resultat = reformuler_si_necessaire(
        "Quel est le taux de chômage actuel ?",
        entrees_historique=_historique_factice(),
        fonction_reformulation=fonction_reformulation,
    )

    assert resultat == "Quel est le taux de chômage actuel ?"
    assert len(appels) == 1


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
