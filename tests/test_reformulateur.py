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


# --- Regression reelle du 30/08 : filtrage des salutations avant reformulation --------
#
# Bug observe en conditions reelles (voir JOURNAL.md) : une session qui commence par
# "hello" stocke cet echange dans l'historique -- le message d'accueil canned cite en
# exemple "taux de chomage, population...". Pour la question suivante ("c quoi rghp"),
# la reformulation systematique utilisait "hello" comme "historique", et le LLM a
# fabrique une question totalement hors-sujet en piochant dans ces exemples.

def _historique_salutation_seule():
    return [
        {
            "question": "hello",
            "reponse": {
                "texte": (
                    "Bonjour ! Je suis l'assistant du HCP. Posez-moi une question sur les "
                    "statistiques et publications du Haut-Commissariat au Plan (ex. taux de "
                    "chômage, population, indice des prix...)."
                ),
            },
        },
    ]


def test_reformuler_si_necessaire_historique_uniquement_salutation_ne_reformule_pas():
    # Traite comme "pas d'historique du tout" -- meme comportement que la toute
    # premiere question d'une session (voir test sans historique ci-dessus).
    appels = []

    def fonction_reformulation(question, historique_texte):
        appels.append(question)
        return "PEU IMPORTE, NE DOIT JAMAIS ETRE APPELE"

    resultat = reformuler_si_necessaire(
        "c quoi rghp",
        entrees_historique=_historique_salutation_seule(),
        fonction_reformulation=fonction_reformulation,
    )

    assert resultat == "c quoi rghp"
    assert appels == []  # la fonction de reformulation n'a jamais ete appelee


def test_reformuler_si_necessaire_salutation_puis_vraie_question_ne_montre_que_la_vraie_question():
    # Historique mixte (salutation + vraie question) : la salutation est ecartee du
    # contexte envoye au LLM, seule la vraie question reste visible.
    historique = _historique_salutation_seule() + _historique_factice()
    appels = []

    def fonction_reformulation(question, historique_texte):
        appels.append(historique_texte)
        return "Quelle est la population du Maroc pour la derniere annee disponible ?"

    reformuler_si_necessaire(
        "du derniere annee ?", entrees_historique=historique, fonction_reformulation=fonction_reformulation,
    )

    assert len(appels) == 1
    historique_envoye = appels[0]
    assert "hello" not in historique_envoye
    assert "taux de ch" not in historique_envoye.lower()  # ni "chômage" ni "chomage" du message d'accueil
    assert "population de maroc" in historique_envoye  # la vraie question, elle, reste presente


def test_reformuler_si_necessaire_salutation_de_cloture_est_aussi_filtree():
    # "merci"/"au revoir" sont aussi des salutations (voir PATTERN_SALUTATION dans
    # src/routeur.py) -- meme traitement que "hello".
    historique = [
        {"question": "merci", "reponse": {"texte": "Avec plaisir ! N'hésitez pas si vous avez d'autres questions."}},
    ]
    appels = []

    def fonction_reformulation(question, historique_texte):
        appels.append(question)
        return "PEU IMPORTE, NE DOIT JAMAIS ETRE APPELE"

    resultat = reformuler_si_necessaire(
        "et le taux d'urbanisation", entrees_historique=historique, fonction_reformulation=fonction_reformulation,
    )

    assert resultat == "et le taux d'urbanisation"
    assert appels == []


def test_reformuler_si_necessaire_question_avec_salutation_et_signal_chiffre_reste_utilisee():
    # Piege evite : "Bonjour, quel est le taux de chômage ?" contient bien "bonjour",
    # mais Routeur.classifier la classe CHIFFRE (le signal chiffre l'emporte, voir
    # src/routeur.py) -- ce n'est PAS une salutation pure, elle doit rester visible dans
    # le contexte de reformulation, contrairement a un simple test sur le mot "bonjour".
    historique = [
        {
            "question": "Bonjour, quel est le taux de chômage ?",
            "reponse": {"texte": "D'après les données du HCP, le taux de chômage est de 13.3%."},
        },
    ]
    appels = []

    def fonction_reformulation(question, historique_texte):
        appels.append(historique_texte)
        return "Quel est le taux de chômage pour les femmes ?"

    reformuler_si_necessaire(
        "et pour les femmes ?", entrees_historique=historique, fonction_reformulation=fonction_reformulation,
    )

    assert len(appels) == 1
    assert "taux de ch" in appels[0].lower()  # la question chiffree reste bien dans le contexte
