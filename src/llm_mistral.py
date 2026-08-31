"""
Client Mistral pour le chemin "notion" de Generateur (voir src/generateur.py,
`TypeFonctionGeneration`).

LLM de production choisi pour la phase prototype (voir ADR 0002) : Mistral, retenu
parmi les options gratuites (Google Gemini, Groq, Mistral) pour la qualité du français
(acteur français, entraînement fortement francophone -- pertinent pour restituer des
publications administratives/statistiques marocaines en français). Tier gratuit
"Experiment" (~1 milliard de tokens/mois) en échange d'un opt-in à l'entraînement,
acceptable ici car les documents indexés sont déjà des publications publiques du HCP.

Nécessite une clé API gratuite (https://console.mistral.ai/), à placer dans un fichier
`.env` à la racine du projet (jamais commité, voir .gitignore) :

    MISTRAL_API_KEY=...
"""
from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()

URL_API = "https://api.mistral.ai/v1/chat/completions"
MODELE = "mistral-small-latest"

PROMPT_SYSTEME = (
    "Tu es un assistant du Haut-Commissariat au Plan (HCP) qui répond à des questions "
    "sur les publications statistiques du Maroc. Règles strictes : réponds "
    "UNIQUEMENT à partir du contexte fourni ci-dessous, en français, de manière "
    "concise et factuelle. Si le contexte ne permet pas de répondre, dis-le "
    "explicitement plutôt que d'inventer une réponse. N'ajoute aucun chiffre qui ne "
    "figure pas littéralement dans le contexte."
)


def generer(question: str, texte_contexte: str) -> str:
    """Fonction de génération compatible avec Generateur (voir
    src/generateur.py::TypeFonctionGeneration) : (question, texte_contexte) -> str.

    À injecter tel quel : `Generateur(conn, fonction_generation=generer)`.
    """
    cle_api = os.environ.get("MISTRAL_API_KEY")
    if not cle_api:
        raise RuntimeError(
            "MISTRAL_API_KEY manquante. Cree un compte gratuit sur "
            "https://console.mistral.ai/, genere une cle API (section API Keys), "
            "et ajoute-la dans un fichier .env a la racine du projet : "
            "MISTRAL_API_KEY=ta_cle_ici"
        )

    reponse = requests.post(
        URL_API,
        headers={"Authorization": f"Bearer {cle_api}", "Content-Type": "application/json"},
        json={
            "model": MODELE,
            "messages": [
                {"role": "system", "content": PROMPT_SYSTEME},
                {"role": "user", "content": f"Contexte :\n{texte_contexte}\n\nQuestion : {question}"},
            ],
            "temperature": 0.2,  # factuel, pas creatif -- coherent avec le grounding strict
        },
        timeout=30,
    )
    reponse.raise_for_status()
    return reponse.json()["choices"][0]["message"]["content"].strip()


PROMPT_SYSTEME_CLASSIFICATION = (
    "Tu classes une question posee a un systeme de questions-reponses sur les "
    "statistiques publiques du Maroc (HCP). Reponds UNIQUEMENT par le mot CHIFFRE si "
    "la question demande une valeur, un chiffre, une statistique precise, sans rien "
    "demander d'autre -- meme formulee sans les mots 'taux' ou 'nombre' (ex. structure, "
    "repartition, part, effectif). Reponds UNIQUEMENT par le mot MIXTE si la question "
    "demande A LA FOIS une valeur chiffree ET une explication de son evolution ou de sa "
    "cause (ex. 'pourquoi le chomage a-t-il augmente ?'). Reponds UNIQUEMENT par le mot "
    "NOTION si la question porte sur une explication, une definition, une methodologie, "
    "ou une difference entre deux notions, SANS demander de valeur chiffree precise "
    "(ex. 'comment est calcule l'indice des prix ?' reste NOTION meme si elle cite un "
    "nom d'indicateur). Ne reponds rien d'autre que CHIFFRE, MIXTE ou NOTION, aucune "
    "ponctuation, aucune explication."
)


PROMPT_SYSTEME_REFORMULATION = (
    "Tu recois une question de suivi posee a un systeme de questions-reponses sur les "
    "statistiques publiques du Maroc (HCP), ainsi que les derniers echanges de la "
    "conversation. Ta seule tache : decider si cette question a BESOIN du contexte de "
    "la conversation pour etre comprise, et la reecrire seulement si oui.\n\n"
    "Cas 1 -- la question contient un mot vague ou une reference implicite ('ça', 'ce "
    "chiffre', 'cette periode', 'et pour...', 'et en...') qui ne se comprend qu'avec "
    "l'historique : remplace UNIQUEMENT ce mot ou cette reference par ce qu'il designe "
    "reellement dans l'historique, sans rien ajouter d'autre.\n"
    "Cas 2 -- la question est deja comprehensible toute seule, meme si elle change "
    "completement de sujet par rapport a l'historique (ex. l'historique parle de "
    "population et la question de suivi demande un taux d'urbanisation) : renvoie-la "
    "EXACTEMENT telle quelle, sans y ajouter aucun mot, aucun sujet, aucune annee "
    "venant de l'historique. Un changement de sujet n'est PAS une raison de "
    "reformuler.\n\n"
    "Ne reponds JAMAIS a la question, ne devine jamais une information absente de la "
    "question et de l'historique. Reponds UNIQUEMENT par la question (reformulee ou "
    "inchangee), en francais, sans aucun commentaire ni guillemets."
)


def reformuler_question(question: str, historique_texte: str) -> str:
    """Fonction de reformulation compatible avec `src/reformulateur.py`
    (TypeFonctionReformulation) : (question, historique_texte) -> question autonome.

    Appelee des qu'un historique REEL existe pour la session (voir
    `src/reformulateur.py::reformuler_si_necessaire` -- l'heuristique de detection de
    follow-up ambigu, evoquee ici a l'origine, a ete essayee puis abandonnee le 23/08,
    peu fiable en conditions reelles). "Reel" depuis le 30/08 : les echanges de simple
    salutation sont ecartes de l'historique avant reformulation (voir
    `src/reformulateur.py::_filtrer_salutations`).

    PROMPT_SYSTEME_REFORMULATION durci le 30/08 (bug reel observe en conditions
    reelles, voir JOURNAL.md) : une question deja autonome et SANS RAPPORT avec le
    sujet de l'historique ("donne taux d'urbanisation" apres une conversation sur la
    population) se faisait quand meme enrichir de details de l'historique ("...de la
    population du Maroc pour l'annee 2026...") -- la premiere version du prompt
    autorisait explicitement a puiser des informations "dans l'historique fourni",
    sans jamais dire de s'abstenir quand la question n'en a pas besoin. Le prompt
    distingue desormais explicitement deux cas (reference vague a resoudre vs question
    deja autonome meme si elle change de sujet) avec un exemple concret de ce dernier
    cas, plutot qu'une regle generale ambigue.

    À injecter tel quel : `poser_question(..., fonction_reformulation=reformuler_question)`.
    """
    cle_api = os.environ.get("MISTRAL_API_KEY")
    if not cle_api:
        raise RuntimeError(
            "MISTRAL_API_KEY manquante. Cree un compte gratuit sur "
            "https://console.mistral.ai/, genere une cle API (section API Keys), "
            "et ajoute-la dans un fichier .env a la racine du projet : "
            "MISTRAL_API_KEY=ta_cle_ici"
        )

    reponse = requests.post(
        URL_API,
        headers={"Authorization": f"Bearer {cle_api}", "Content-Type": "application/json"},
        json={
            "model": MODELE,
            "messages": [
                {"role": "system", "content": PROMPT_SYSTEME_REFORMULATION},
                {
                    "role": "user",
                    "content": (
                        f"Historique recent :\n{historique_texte}\n\n"
                        f"Question de suivi : {question}"
                    ),
                },
            ],
            "temperature": 0.0,  # reformulation : aucune creativite souhaitee
        },
        timeout=15,
    )
    reponse.raise_for_status()
    return reponse.json()["choices"][0]["message"]["content"].strip()


def classifier_question(question: str) -> str:
    """Fonction de classification compatible avec Routeur (voir
    src/routeur.py::TypeFonctionClassification) : dernier recours seulement, appelee
    uniquement quand aucune regle par mots-cles n'a permis de trancher (voir docstring
    de Routeur, section "V2 ajoutee le 28/07"). Renvoie la chaine brute renvoyee par le
    modele ("CHIFFRE"/"NOTION" attendus) -- c'est Routeur qui valide/normalise et
    retombe sur son comportement par defaut si la reponse est inattendue.

    À injecter tel quel : `Routeur(fonction_classification_llm=classifier_question)`.
    """
    cle_api = os.environ.get("MISTRAL_API_KEY")
    if not cle_api:
        raise RuntimeError(
            "MISTRAL_API_KEY manquante. Cree un compte gratuit sur "
            "https://console.mistral.ai/, genere une cle API (section API Keys), "
            "et ajoute-la dans un fichier .env a la racine du projet : "
            "MISTRAL_API_KEY=ta_cle_ici"
        )

    reponse = requests.post(
        URL_API,
        headers={"Authorization": f"Bearer {cle_api}", "Content-Type": "application/json"},
        json={
            "model": MODELE,
            "messages": [
                {"role": "system", "content": PROMPT_SYSTEME_CLASSIFICATION},
                {"role": "user", "content": question},
            ],
            "temperature": 0.0,  # classification : aucune creativite souhaitee
        },
        timeout=15,  # plus court que generer() : reponse attendue en un seul mot
    )
    reponse.raise_for_status()
    return reponse.json()["choices"][0]["message"]["content"].strip()
