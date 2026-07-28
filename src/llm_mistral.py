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
    "la question porte sur une valeur, un chiffre, une statistique precise -- meme "
    "formulee sans les mots 'taux' ou 'nombre' (ex. structure, repartition, part, "
    "effectif, evolution d'une valeur dans le temps). Reponds UNIQUEMENT par le mot "
    "NOTION si la question porte sur une explication, une definition, une "
    "methodologie, un pourquoi/comment, ou une analyse. Ne reponds rien d'autre que "
    "CHIFFRE ou NOTION, aucune ponctuation, aucune explication."
)


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
