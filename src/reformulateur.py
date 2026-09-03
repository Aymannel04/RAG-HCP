"""
Module Reformulateur — mémoire conversationnelle. N'existait pas dans la conception
d'origine (les 9 modules numérotés) : ajouté pour un besoin réel découvert en testant
l'interface Streamlit en conditions réelles, comme `src/cache_redis.py`.

Problème traité : `Routeur`/`LookupStructure`/`RetrievalReranker` classifient et
cherchent uniquement sur le texte brut de LA question posée, sans jamais tenir compte
des échanges précédents. Une vraie conversation contient forcément des questions de
suivi qui ne se comprennent qu'avec ce contexte -- ex. "explique ce chiffre" après une
réponse chiffrée, ou "et pour l'année dernière ?" après une question sur la population.
Sans reformuler ces questions en version autonome, la recherche part sur un texte qui
ne veut rien dire tout seul et ne trouve rien de pertinent.

Décision retenue : plutôt que d'essayer de DEVINER si une question a besoin de contexte
à partir de son seul texte (une heuristique de mots-clés a été essayée puis abandonnée
-- structurellement incapable de couvrir toutes les formulations possibles d'une
question de suivi en français), on se fie au seul fait fiable à 100 % : un historique
existe-t-il déjà pour cette session ? Si oui, la question est SYSTÉMATIQUEMENT
reformulée en tenant compte des derniers échanges avant classification/recherche. Si
c'est la première question, rien à reformuler, aucun coût ajouté sur le premier tour.
Compromis assumé : à partir du 2e tour, une question déjà autonome paie quand même un
appel LLM (qui la renverra alors quasiment inchangée) -- moins économique qu'un bon
filtre heuristique, mais fiable à 100 %. Tier gratuit Mistral (voir
src/llm_mistral.py) : coût réel négligeable pour ce projet.

Ce que ce module NE fait PAS : il ne touche jamais à `HistoriqueConversation` (stockage
inchangé, toujours indexé sous la question originale telle que tapée par
l'utilisateur) -- seule la question envoyée au Routeur/LookupStructure/
RetrievalReranker/Generateur est éventuellement remplacée par sa version reformulée,
jamais ce qui est affiché ou journalisé.
"""
from __future__ import annotations

from typing import Callable, Optional

from .routeur import Routeur, TypeQuestion

TypeFonctionReformulation = Callable[[str, str], str]  # (question, historique_texte) -> question reformulee

# Instance sans fonction_classification_llm : le filtre ci-dessous ne doit jamais
# declencher d'appel reseau, seulement la couche heuristique deterministe (voir
# Routeur.classifier -- sans fonction LLM injectee, le repli en dernier recours est
# simplement ignore, comportement documente dans src/routeur.py).
_ROUTEUR_FILTRAGE = Routeur()


def _filtrer_salutations(entrees_historique: list[dict]) -> list[dict]:
    """Ecarte les echanges dont la question a ete classee SALUTATION avant de
    construire le contexte envoye au LLM de reformulation.

    Le message d'accueil canned (MESSAGE_ACCUEIL, voir scripts/poser_question.py) cite
    en exemple des mots comme "taux de chomage" et "population". Une session qui
    commence par "hello" stocke cet echange dans l'historique
    (HistoriqueConversation.ajouter enregistre TOUT, salutations comprises --
    necessaire pour l'affichage fidele dans l'interface). Sans ce filtre, la toute
    PREMIERE vraie question de la session (ex. "c quoi rghp") se voit reformulee avec
    cet echange "hello" comme "historique" -- et le LLM de reformulation, invite a
    remplacer les sujets sous-entendus par ce qu'ils designent "dans l'historique",
    peut prendre les exemples du message d'accueil au pied de la lettre et fabriquer
    une question totalement hors-sujet. Une salutation ne porte aucun contenu
    conversationnel reel : l'exclure ici revient a la traiter comme si elle n'existait
    pas pour cet usage precis -- toujours visible dans Redis/l'interface, juste jamais
    montree au LLM de reformulation.

    Reutilise `Routeur.classifier` plutot qu'un simple test sur le texte (ex.
    PATTERN_SALUTATION seul) : une question comme "Bonjour, quel est le taux de
    chomage ?" contient bien "bonjour", mais `classifier` la classe CHIFFRE (le signal
    chiffre l'emporte, voir docstring de Routeur) -- un test naif sur le texte l'aurait
    a tort exclue du contexte alors qu'elle porte un vrai contenu utile a une
    reformulation future.
    """
    return [
        entree for entree in entrees_historique
        if _ROUTEUR_FILTRAGE.classifier(entree["question"]) != TypeQuestion.SALUTATION
    ]


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
    ORIGINALE si aucune reformulation n'est possible ou necessaire, sinon la version
    reformulee par `fonction_reformulation`.

    Ne reformule QUE si les deux conditions sont reunies (voir docstring de module,
    section "Decision retenue") :
    - un historique REEL existe deja pour cette session, une fois les salutations
      ecartees (voir `_filtrer_salutations`) -- une session qui n'a encore echange que
      des politesses ("hello") est traitee comme si elle n'avait aucun historique ;
    - une fonction de reformulation est injectee (comportement par defaut inchange si
      absente, meme patron que cache/historique/classification LLM ailleurs).

    Aucune tentative de deviner si LA question precise en a "besoin" -- voir docstring
    de module : une heuristique de mots-cles a ete essayee et abandonnee car peu
    fiable.

    Degradation propre : toute exception levee par `fonction_reformulation` (reseau,
    cle API absente, etc.) ou une reponse vide fait retomber sur la question originale,
    jamais d'echec de tout le pipeline pour ce module optionnel.
    """
    entrees_reelles = _filtrer_salutations(entrees_historique)
    if not entrees_reelles or fonction_reformulation is None:
        return question

    historique_texte = _formater_historique(entrees_reelles)
    try:
        reformulee = fonction_reformulation(question, historique_texte)
    except Exception:
        return question

    reformulee = (reformulee or "").strip()
    return reformulee if reformulee else question
