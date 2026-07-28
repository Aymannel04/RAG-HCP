"""
Module Routeur — module 5 de l'architecture.
Rôle : classifier chaque question (chiffre précis vs notion/narratif) et aiguiller
vers LookupStructure ou RetrievalReranker.
Voir les deux scénarios formalisés dans docs/conception_uml_v3.pdf, figures 5 et 6
(exemples de référence : "Quel est le taux de chômage actuel ?" -> CHIFFRE,
"C'est quoi le RGPH ?" -> NOTION).

Décision d'implémentation : classification par heuristique de mots-clés en chemin
principal, plutôt que par appel LLM systématique, contrairement à ce qu'envisageait le
docstring d'origine ("V1 : appel LLM"). Deux raisons :
1. Cette approche était déjà celle proposée à l'encadrante dans
   docs/note_stockage_routage_benchmark.pdf (section routage) comme option V1, l'appel
   LLM étant explicitement repoussé en V2 dans ce même document.
2. Un classifieur qui ne dépend d'aucun LLM reste un choix défendable en soi (rapide,
   gratuit, déterministe, donc plus facile à tester et déboguer qu'un appel LLM pour
   une tâche aussi simple qu'une classification binaire), et découple ce module du
   choix du LLM de génération (voir ADR 0002).

V2 ajoutée le 28/07 (celle évoquée dans note_stockage_routage_benchmark.pdf, jamais
implémentée jusqu'ici) : `fonction_classification_llm` optionnelle, appelée en DERNIER
RECOURS seulement, quand ni `MOTS_NOTION`, ni `MOTS_CHIFFRE`, ni `PATTERN_PERIODE` n'ont
permis de trancher. Déclenchée par un cas réel observé en test (voir TODO.md) : une
question chiffrée légitime formulée avec un vocabulaire absent des deux listes tombe
par défaut sur NOTION -- dégradation propre (RetrievalReranker reste capable de
répondre) mais pas idéale. Complèter `MOTS_CHIFFRE` à la main marche mais ne suivra
jamais toutes les formulations possibles. L'heuristique reste le chemin principal
(rapide, gratuit, déterministe) : le LLM n'est qu'un filet de sécurité pour les cas
vraiment ambigus, pas un remplacement. Toute erreur (réseau, clé API absente, réponse
inattendue) est rattrapée et traitée comme "ne sait pas" -- ne fait jamais planter la
classification, se contente de retomber sur le même défaut NOTION qu'avant.
Injectable au constructeur (même patron que `fonction_generation` de `Generateur`) :
`llm_mistral.classifier_question` en production, une fonction factice dans les tests.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Callable, Optional


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
#
# Complete le 28/07 (limite trouvee en conditions reelles, voir TODO.md) : la liste
# d'origine ne couvrait que "taux"/"nombre"/"valeur"/"indice"/"pourcentage", ce qui
# faisait tomber par defaut sur NOTION toute question chiffree formulee autrement --
# ex. "Quelle est la structure des actifs occupés sans diplôme ?" ne matchait AUCUN
# mot-cle des deux listes, et atterrissait sur RetrievalReranker au lieu de
# LookupStructure (repli honnete grace au comportement par defaut deja documente, mais
# qui privait la question du chemin chiffre exact). Ajouts choisis en reprenant les
# formulations reelles des noms d'indicateurs cures (voir data/indicateurs_cures.py :
# "Structure des actifs occupés", "Effectif des chômeurs", "Espérance de vie...",
# "Valeurs ajoutées...", "Population...") plus quelques tournures naturelles
# equivalentes ("répartition", "part de", "proportion de") pour les questions sur une
# ventilation (sexe/milieu/diplome/branche, voir src/lookup_structure.py) qui ne
# citent pas forcement le mot "taux".
MOTS_CHIFFRE = [
    "combien", "quel est le taux", "quelle est le taux", "quel est le nombre",
    "quelle est la valeur", "quel est le pourcentage", "en pourcentage",
    "quel pourcentage", "taux de", "taux d'", "nombre de", "valeur de", "chiffre de",
    "indice de", "indice des", "statistique",
    "structure de", "structure des", "répartition de", "répartition des",
    "part de", "part des", "proportion de", "proportion des",
    "effectif de", "effectif des", "espérance de vie", "valeurs ajoutées",
    "population de", "population du",
]

# Question chiffrée sans mot-outil explicite mais avec une année/période -- signal plus
# faible (une question narrative peut aussi citer une année), donc utilisé seulement en
# renfort si aucun des deux dictionnaires ci-dessus n'a tranché.
PATTERN_PERIODE = re.compile(r"\b(19|20)\d{2}\b|\bT[1-4]\b")

# (question) -> "CHIFFRE" ou "NOTION" (toute autre valeur est traitee comme "ne sait
# pas"). Voir docstring de module, section "V2 ajoutee le 28/07".
TypeFonctionClassification = Callable[[str], str]


class Routeur:
    """Classifie une question pour décider du chemin de traitement."""

    def __init__(self, fonction_classification_llm: Optional[TypeFonctionClassification] = None):
        """
        `fonction_classification_llm` : optionnelle, dernier recours seulement (voir
        docstring de module) -- jamais appelée si l'heuristique par mots-clés a déjà
        tranché. Absente par défaut : comportement inchangé (repli NOTION), aucune
        régression si rien n'est branché.
        """
        self._fonction_classification_llm = fonction_classification_llm

    def classifier(self, question: str) -> TypeQuestion:
        """Retourne TypeQuestion.CHIFFRE si la question porte sur une valeur précise
        (indicateur, statistique), TypeQuestion.NOTION sinon (explication, méthodologie,
        rapport).

        Ordre de décision : signal narratif d'abord (prioritaire, voir docstring de
        module), puis signal chiffré, puis repli sur la présence d'une période
        (signal faible), puis appel LLM en dernier recours si injecté (voir
        `_fonction_classification_llm`), puis NOTION par défaut -- un faux négatif sur
        NOTION bascule vers RetrievalReranker qui reste capable de faire remonter un
        chiffre s'il apparaît dans le texte d'un rapport, alors qu'un faux négatif sur
        CHIFFRE renverrait "indicateur non trouvé" sans aucune tentative de réponse.
        """
        signal = question.lower().strip()

        if any(mot in signal for mot in MOTS_NOTION):
            return TypeQuestion.NOTION

        if any(mot in signal for mot in MOTS_CHIFFRE):
            return TypeQuestion.CHIFFRE

        if PATTERN_PERIODE.search(signal):
            return TypeQuestion.CHIFFRE

        if self._fonction_classification_llm is not None:
            resultat = self._classifier_via_llm(question)
            if resultat is not None:
                return resultat

        return TypeQuestion.NOTION

    def _classifier_via_llm(self, question: str) -> Optional[TypeQuestion]:
        """Dernier recours, appel défensif : toute exception (réseau, clé API absente,
        timeout) ou réponse inattendue (ni "CHIFFRE" ni "NOTION") est traitée comme
        "ne sait pas" -- ne fait jamais planter `classifier`, se contente de laisser
        le repli NOTION habituel s'appliquer."""
        try:
            resultat = self._fonction_classification_llm(question)
        except Exception:
            return None
        resultat_normalise = (resultat or "").strip().upper()
        if resultat_normalise == "CHIFFRE":
            return TypeQuestion.CHIFFRE
        if resultat_normalise == "NOTION":
            return TypeQuestion.NOTION
        return None
