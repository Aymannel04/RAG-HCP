"""
Client Mistral pour le chemin "notion" de Generateur (voir src/generateur.py,
`TypeFonctionGeneration`).

Choix du LLM de production (Sprint 3, 21 juillet 2026) : l'encadrante a validé
« n'importe quel LLM gratuit qui fait le travail » pour la phase prototype -- ce qui
lève le point bloquant de l'ADR 0002. Mistral retenu parmi les options gratuites
comparées (Google Gemini, Groq, Mistral) pour deux raisons : qualité du français
(acteur français, entraînement fortement francophone -- pertinent pour restituer des
publications administratives/statistiques marocaines en français) et cohérence (un
choix plus simple à justifier auprès de l'encadrante qu'un modèle généraliste
anglophone quelconque). Tier gratuit "Experiment" (~1 milliard de tokens/mois) en
échange d'un opt-in à l'entraînement -- accepté explicitement par Ayman le 21 juillet
car les documents indexés sont déjà des publications publiques du HCP, aucune donnée
sensible n'est en jeu.

Nécessite une clé API gratuite (https://console.mistral.ai/), à placer dans un fichier
`.env` à la racine du projet (jamais commité, voir .gitignore) :

    MISTRAL_API_KEY=...

Statut : implémenté. PAS ENCORE testé contre la vraie API (pas d'accès réseau dans ce
bac à sable de développement, même limite que hcp.ma/BDS/BGE-M3) -- testé avec
`requests.post` simulé (voir tests/test_llm_mistral.py, même patron que
tests/test_scraper.py). À valider sur la machine d'Ayman une fois la clé API créée.
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
