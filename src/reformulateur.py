"""
Module Reformulateur — ajouté le 23/08, pour la mémoire conversationnelle (voir
JOURNAL.md et discussion avec Ayman, 23/08). N'existait pas dans la conception
d'origine (les 9 modules de docs/conception_uml_v3.pdf) : ajouté pour la même raison
que src/cache_redis.py -- un besoin réel découvert en testant l'interface Streamlit en
conditions réelles, pas anticipé au départ.

Problème observé : `Routeur`/`LookupStructure`/`RetrievalReranker` classifient et
cherchent uniquement sur le texte brut de LA question posée, sans jamais tenir compte
des échanges précédents. Une vraie conversation contient forcément des questions de
suivi qui ne se comprennent qu'avec ce contexte -- ex. "explique ce chiffre" après une
réponse chiffrée, ou "du derniere annee ?" après une question sur la population. Sans
reformuler ces questions en version autonome, la recherche part sur un texte qui ne veut
rien dire tout seul et ne trouve rien de pertinent.

Historique de la decision (voir JOURNAL.md, 23/08) : une premiere version (Option C)
essayait de deviner, via une heuristique de mots-cles (`ressemble_a_un_followup`), si
UNE question donnee ressemblait a un follow-up ambigu avant de declencher la
reformulation. Abandonnee le jour meme : testee en conditions reelles, "du derniere
annee ?" n'a matche AUCUN mot-cle de la liste et a ete envoyee telle quelle au Routeur,
qui est parti chercher un texte incomprehensible dans les documents. Objection d'Ayman,
fondee : une liste de mots-cles ne peut structurellement pas couvrir toutes les
formulations possibles d'une question de suivi en francais -- le meme bug reapparaitrait
sous une autre formulation a chaque fois, un jeu du chat et de la souris sans fin.

Decision retenue : abandonner toute tentative de DEVINER si une question a besoin de
contexte a partir de son seul texte. A la place, se fier au seul fait fiable a 100% --
un historique existe-t-il deja pour cette session ? Si oui (ce n'est pas la premiere
question de la conversation), la question est SYSTEMATIQUEMENT reformulee en tenant
compte des derniers echanges avant classification/recherche. Si c'est la premiere
question (aucun historique), rien a reformuler, donc aucun cout ajoute sur le premier
tour de toute facon. Compromis assume : a partir du 2e tour, une question deja autonome
paie quand meme un appel LLM (qui la renverra alors quasiment inchangee) -- moins
economique qu'un bon filtre heuristique, mais fiable a 100%, contrairement a une liste
de mots-cles qui aura toujours un angle mort. Tier gratuit Mistral (~1 milliard de
tokens/mois, voir src/llm_mistral.py) : cout reel negligeable pour ce projet.

Ce que ce module NE fait PAS : il ne touche jamais à `HistoriqueConversation` (stockage
inchangé, toujours indexé sous la question originale telle que tapée par l'utilisateur,
voir scripts/poser_question.py) -- seule la question envoyée au Routeur/LookupStructure/
RetrievalReranker/Generateur est éventuellement remplacée par sa version reformulée,
jamais ce qui est affiché ou journalisé.
"""
from __future__ import annotations

from typing import Callable, Optional

TypeFonctionReformulation = Callable[[str, str], str]  # (question, historique_texte) -> question reformulee


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
    - un historique existe deja pour cette session (sinon rien a reformuler a partir
      de -- c'est la premiere question, aucun cout ajoute) ;
    - une fonction de reformulation est injectee (comportement par defaut inchange si
      absente, meme patron que cache/historique/classification LLM ailleurs).

    Aucune tentative de deviner si LA question precise en a "besoin" -- voir
    l'historique de la decision dans le docstring de module : une heuristique de
    mots-cles a ete essayee et abandonnee car peu fiable.

    Degradation propre : toute exception levee par `fonction_reformulation` (reseau,
    cle API absente, etc.) ou une reponse vide fait retomber sur la question originale,
    jamais d'echec de tout le pipeline pour ce module optionnel.
    """
    if not entrees_historique or fonction_reformulation is None:
        return question

    historique_texte = _formater_historique(entrees_historique)
    try:
        reformulee = fonction_reformulation(question, historique_texte)
    except Exception:
        return question

    reformulee = (reformulee or "").strip()
    return reformulee if reformulee else question
