"""
Module Reformulateur — ajouté le 23/08, pour la mémoire conversationnelle (voir
JOURNAL.md et discussion avec Ayman, 23/08). N'existait pas dans la conception
d'origine (les 9 modules de docs/conception_uml_v3.pdf) : ajouté pour la même raison
que src/cache_redis.py -- un besoin réel découvert en testant l'interface Streamlit
en conditions réelles, pas anticipé au départ.

Problème observé : `Routeur`/`LookupStructure`/`RetrievalReranker` classifient et
cherchent uniquement sur le texte brut de LA question posée, sans jamais tenir compte
des échanges précédents. Une vraie conversation contient forcément des questions de
suivi qui ne se comprennent qu'avec ce contexte -- ex. "explique ce chiffre" après une
réponse chiffrée, ou "et en 2023 ?" après une question sur le chômage. Sans reformuler
ces questions en version autonome, la recherche part sur un texte qui ne veut rien dire
tout seul et ne trouve rien de pertinent (cas réel observé le 23/08, voir JOURNAL.md).

Décision d'implémentation (Option C, choisie explicitement par Ayman après discussion
des compromis -- voir échange du 23/08) : approche HYBRIDE, pas une reformulation
systématique.

1. Une heuristique bon marché (`ressemble_a_un_followup`, aucun appel LLM) décide
   d'abord si la question RESSEMBLE à un follow-up ambigu -- mêmes principes que les
   heuristiques de `src/routeur.py` (mots-clés + repli sur un signal plus faible).
2. Seulement si cette heuristique se déclenche ET qu'un historique existe pour cette
   session, un appel LLM (`fonction_reformulation`, injectable comme partout ailleurs
   dans le projet -- `llm_mistral.reformuler_question` en production) réécrit la
   question en version autonome à partir des derniers échanges.
3. Toute question déjà autonome (la majorité) ne paie donc aucun coût supplémentaire :
   comportement inchangé, zéro appel LLM en plus -- même philosophie que le fallback
   LLM du Routeur ("heuristique d'abord, LLM seulement en dernier recours ciblé").
4. Défensif comme partout ailleurs (voir Routeur._classifier_via_llm) : toute exception
   (réseau, clé API absente, réponse vide) fait retomber sur la question ORIGINALE
   plutôt que de faire planter tout le pipeline -- dégradation propre, jamais pire que
   le comportement d'avant l'ajout de ce module.

Ce que ce module NE fait PAS : il ne touche jamais à `HistoriqueConversation` (stockage
inchangé, toujours indexé sous la question originale telle que tapée par l'utilisateur,
voir scripts/poser_question.py) -- seule la question envoyée au Routeur/LookupStructure/
RetrievalReranker/Generateur est éventuellement remplacée par sa version reformulée,
jamais ce qui est affiché ou journalisé.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Callable, Optional

TypeFonctionReformulation = Callable[[str, str], str]  # (question, historique_texte) -> question reformulee


def _normaliser(texte: str) -> str:
    forme_decomposee = unicodedata.normalize("NFD", texte)
    return "".join(c for c in forme_decomposee if unicodedata.category(c) != "Mn")


# Mots-outils exclus du comptage de "tokens de contenu" (voir `ressemble_a_un_followup`,
# signal 2) -- meme liste que src/lookup_structure.py::MOTS_OUTILS, dupliquee ici plutot
# que partagee pour garder les deux modules independants (aucune dependance croisee
# necessaire, chacun reste utilisable seul).
MOTS_OUTILS = {
    "le", "la", "les", "l", "un", "une", "des", "de", "du", "d", "et", "en", "au", "aux",
    "est", "sont", "quel", "quelle", "quels", "quelles", "ce", "cette", "ces", "pour",
    "sur", "dans", "actuel", "actuelle", "selon", "par", "j", "ai", "as", "a", "pas",
    "que", "qui", "tu", "t",
}

# Signal 1 : mots/expressions qui trahissent explicitement une reference au contexte
# precedent plutot qu'un sujet exprime en toutes lettres (liste volontairement courte,
# meme esprit que MOTS_NOTION/MOTS_CHIFFRE du Routeur -- affinable avec l'usage reel).
MOTS_FOLLOWUP = [
    "ça", "ca", "cela", "ce chiffre", "cette valeur", "ce nombre", "meme chose",
    "et pour", "et en", "et si", "et la", "explique", "pourquoi ce", "pourquoi cette",
    "comment ça", "comment ca", "qu'est-ce que ça veut dire", "tu as dit", "t'as dit",
    "comme tu as dit",
]


def ressemble_a_un_followup(question: str) -> bool:
    """Heuristique bon marche (aucun appel LLM) : la question a-t-elle des chances de
    ne pas se comprendre sans le contexte de la conversation precedente ?

    Deux signaux (voir docstring de module) :
    1. Un mot/expression explicitement referentiel (MOTS_FOLLOWUP) est present.
    2. Une fois les mots-outils retires, il reste au plus 1 mot de contenu -- la
       question est trop courte/vague pour porter un sujet complet a elle seule (ex.
       "explique" seul, ou "et en 2023 ?" qui ne contient qu'un chiffre d'annee).
    """
    signal = _normaliser(question.lower().strip())

    if any(mot in signal for mot in MOTS_FOLLOWUP):
        return True

    tokens = re.findall(r"\w+", signal)
    tokens_contenu = [t for t in tokens if t not in MOTS_OUTILS]
    return len(tokens_contenu) <= 1


def _formater_historique(entrees_historique: list[dict], max_echanges: int = 3) -> str:
    """Met en forme les derniers echanges (voir HistoriqueConversation.recuperer, meme
    forme de dict) en texte simple Q/R pour le prompt de reformulation."""
    recentes = entrees_historique[-max_echanges:]
    lignes = []
    for entree in recentes:
        lignes.append(f"Q: {entree['question']}")
        lignes.append(f"R: {entree['reponse']['texte']}")
    return "\n".join(lignes)


def reformuler_si_necessaire(
    question: str,
    entrees_historique: list[dict],
    fonction_reformulation: Optional[TypeFonctionReformulation],
) -> str:
    """Point d'entree unique utilise par scripts/poser_question.py : renvoie la
    question a utiliser pour la classification/recherche/generation -- la question
    ORIGINALE si aucune reformulation n'est necessaire ou possible, sinon la version
    reformulee par `fonction_reformulation`.

    Ne reformule JAMAIS si :
    - il n'y a aucun historique pour cette session (rien a reformuler a partir de) ;
    - aucune fonction de reformulation n'est injectee (comportement par defaut
      inchange, meme patron que cache/historique/classification LLM ailleurs) ;
    - la question ne ressemble pas a un follow-up ambigu (voir
      `ressemble_a_un_followup`) -- c'est le coeur de l'Option C : pas d'appel LLM sur
      une question deja autonome.

    Degradation propre : toute exception levee par `fonction_reformulation` (reseau,
    cle API absente, etc.) ou une reponse vide fait retomber sur la question originale,
    jamais d'echec de tout le pipeline pour ce module optionnel.
    """
    if not entrees_historique or fonction_reformulation is None:
        return question

    if not ressemble_a_un_followup(question):
        return question

    historique_texte = _formater_historique(entrees_historique)
    try:
        reformulee = fonction_reformulation(question, historique_texte)
    except Exception:
        return question

    reformulee = (reformulee or "").strip()
    return reformulee if reformulee else question
