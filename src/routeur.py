"""
Module Routeur — module 5 de l'architecture.
Rôle : classifier chaque question (chiffre précis vs notion/narratif) et aiguiller
vers LookupStructure ou RetrievalReranker.
Voir les deux scénarios formalisés dans docs/conception_uml_v3.pdf, figures 5 et 6
(exemples de référence : "Quel est le taux de chômage actuel ?" -> CHIFFRE,
"C'est quoi le RGPH ?" -> NOTION).

Décision d'implémentation (Sprint 3, 21 juillet 2026) : classification par heuristique
de mots-clés plutôt que par appel LLM, contrairement à ce qu'envisageait le docstring
d'origine ("V1 : appel LLM"). Deux raisons :
1. Cette approche était déjà celle proposée à l'encadrante dans
   docs/note_stockage_routage_benchmark.pdf (section routage) comme option V1, l'appel
   LLM étant explicitement repoussé en V2 dans ce même document.
2. Le choix du LLM de génération reste une décision ouverte (voir ADR 0002, "point
   réellement bloquant... doit être validé avec l'encadrante") : un classifieur qui ne
   dépend d'aucun LLM permet d'avancer le Sprint 3 sans attendre cette validation, et
   reste un choix défendable en soi (rapide, gratuit, déterministe, donc plus facile à
   tester et déboguer qu'un appel LLM pour une tâche aussi simple qu'une classification
   binaire).

Statut : implémenté (heuristique), testé.
"""
from __future__ import annotations

import re
from enum import Enum


class TypeQuestion(Enum):
    CHIFFRE = "chiffre"
    NOTION = "notion"


# Signal narratif : présence d'une intention explicative (voir
# docs/note_stockage_routage_benchmark.pdf, tableau "signal narratif"). Priorité sur le
# signal chiffré ci-dessous : une question comme "pourquoi le chômage a-t-il augmenté ?"
# a une composante chiffrée ET narrative, mais seul RetrievalReranker (recherche dans le
# texte des rapports) peut répondre à la partie "pourquoi" -- LookupStructure ne renvoie
# qu'une valeur brute, sans explication.
MOTS_NOTION = [
    "pourquoi", "comment", "expliquer", "expliqu", "definir", "définir", "definition",
    "définition", "tendance", "evolution", "évolution", "analyse", "cause", "raison",
    "c'est quoi", "qu'est-ce que", "qu'est ce que", "methodologie", "méthodologie",
    "difference entre", "différence entre",
]

# Signal chiffré : la question porte sur une valeur précise, un indicateur, une
# statistique isolée -- typiquement une question courte avec un mot-outil de mesure.
MOTS_CHIFFRE = [
    "combien", "quel est le taux", "quelle est le taux", "quel est le nombre",
    "quelle est la valeur", "quel est le pourcentage", "en pourcentage",
    "quel pourcentage", "taux de", "taux d'", "nombre de", "valeur de", "chiffre de",
    "indice de", "indice des", "statistique",
]

# Question chiffrée sans mot-outil explicite mais avec une année/période -- signal plus
# faible (une question narrative peut aussi citer une année), donc utilisé seulement en
# renfort si aucun des deux dictionnaires ci-dessus n'a tranché.
PATTERN_PERIODE = re.compile(r"\b(19|20)\d{2}\b|\bT[1-4]\b")


class Routeur:
    """Classifie une question pour décider du chemin de traitement."""

    def classifier(self, question: str) -> TypeQuestion:
        """Retourne TypeQuestion.CHIFFRE si la question porte sur une valeur précise
        (indicateur, statistique), TypeQuestion.NOTION sinon (explication, méthodologie,
        rapport).

        Ordre de décision : signal narratif d'abord (prioritaire, voir docstring de
        module), puis signal chiffré, puis repli sur la présence d'une période
        (signal faible), puis NOTION par défaut -- un faux négatif sur NOTION bascule
        vers RetrievalReranker qui reste capable de faire remonter un chiffre s'il
        apparaît dans le texte d'un rapport, alors qu'un faux négatif sur CHIFFRE
        renverrait "indicateur non trouvé" sans aucune tentative de réponse.
        """
        signal = question.lower().strip()

        if any(mot in signal for mot in MOTS_NOTION):
            return TypeQuestion.NOTION

        if any(mot in signal for mot in MOTS_CHIFFRE):
            return TypeQuestion.CHIFFRE

        if PATTERN_PERIODE.search(signal):
            return TypeQuestion.CHIFFRE

        return TypeQuestion.NOTION
