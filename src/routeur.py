"""
Module Routeur — module 5 de l'architecture.
Rôle : classifier chaque question (chiffre précis vs notion/narratif) et aiguiller
vers LookupStructure ou RetrievalReranker (exemples de référence : "Quel est le taux
de chômage actuel ?" -> CHIFFRE, "C'est quoi le RGPH ?" -> NOTION).

Décision d'implémentation : classification par heuristique de mots-clés en chemin
principal, plutôt que par appel LLM systématique. Un classifieur qui ne dépend
d'aucun LLM reste un choix défendable en soi (rapide, gratuit, déterministe, donc plus
facile à tester et déboguer qu'un appel LLM pour une tâche aussi simple qu'une
classification binaire), et découple ce module du choix du LLM de génération (ADR
0002).

`fonction_classification_llm` optionnelle, appelée en DERNIER RECOURS seulement, quand
ni `MOTS_NOTION`, ni `MOTS_CHIFFRE`, ni `PATTERN_PERIODE` n'ont permis de trancher :
une question chiffrée légitime formulée avec un vocabulaire absent des deux listes
tombe par défaut sur NOTION -- dégradation propre (RetrievalReranker reste capable de
répondre) mais pas idéale. Complèter `MOTS_CHIFFRE` à la main marche mais ne suivra
jamais toutes les formulations possibles. L'heuristique reste le chemin principal
(rapide, gratuit, déterministe) : le LLM n'est qu'un filet de sécurité pour les cas
vraiment ambigus, pas un remplacement. Toute erreur (réseau, clé API absente, réponse
inattendue) est rattrapée et traitée comme "ne sait pas" -- ne fait jamais planter la
classification, se contente de retomber sur le même défaut NOTION qu'avant.
Injectable au constructeur (même patron que `fonction_generation` de `Generateur`) :
`llm_mistral.classifier_question` en production, une fonction factice dans les tests.

`TypeQuestion.MIXTE` est renvoyé quand un signal narratif ET un signal chiffré sont
TOUS LES DEUX présents (ex. "pourquoi le chômage a-t-il augmenté ?") --
`scripts/poser_question.py` interroge alors les deux chemins et `Generateur` fusionne
les deux résultats (voir `ContexteMixte`).

Piège évité : associer N'IMPORTE quel mot de `MOTS_NOTION` à un mot de `MOTS_CHIFFRE`
suffirait à declarer MIXTE, mais casserait des questions purement notionnelles qui
citent un nom d'indicateur sans rien demander de chiffré -- ex. "Comment est calculé
l'indice des prix à la consommation ?" contient "indice des" (signal chiffré) ET
"comment" (signal narratif), mais ne demande AUCUN chiffre, juste une méthodologie.
D'où `MOTS_NOTION_COMBINABLES` : seul un sous-ensemble de `MOTS_NOTION` (ceux qui
parlent d'évolution/cause d'une valeur, pas de définition/méthodologie) peut déclencher
MIXTE en présence d'un signal chiffré. Les autres mots narratifs (comment, expliquer,
définir, méthodologie, différence entre) gardent l'ancien comportement : NOTION pur,
quel que soit ce qui les accompagne.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Callable, Optional


class TypeQuestion(Enum):
    CHIFFRE = "chiffre"
    NOTION = "notion"
    MIXTE = "mixte"
    SALUTATION = "salutation"


# Signal narratif : présence d'une intention explicative (voir
# docs/note_stockage_routage_benchmark.pdf, tableau "signal narratif").
MOTS_NOTION = [
    "pourquoi", "comment", "expliquer", "expliqu", "definir", "définir", "definition",
    "définition", "tendance", "evolution", "évolution", "analyse", "cause", "raison",
    "c'est quoi", "qu'est-ce que", "qu'est ce que", "methodologie", "méthodologie",
    "difference entre", "différence entre",
]

# Sous-ensemble de MOTS_NOTION qui, combiné à un signal chiffré, déclenche MIXTE plutôt
# que NOTION pur (voir docstring de module, section "Cas mixte") -- uniquement les mots
# qui parlent d'évolution/cause d'une valeur dans le temps, jamais
# les mots purement définitionnels/méthodologiques (qui restent NOTION pur même s'ils
# citent un nom d'indicateur contenant un mot de MOTS_CHIFFRE).
MOTS_NOTION_COMBINABLES = {
    "pourquoi", "tendance", "evolution", "évolution", "analyse", "cause", "raison",
}

# Signal chiffré : la question porte sur une valeur précise, un indicateur, une
# statistique isolée -- typiquement une question courte avec un mot-outil de mesure.
#
# Volontairement large plutôt que limitée à "taux"/"nombre"/"valeur"/"indice"/
# "pourcentage" : une question chiffrée formulée autrement (ex. "Quelle est la
# structure des actifs occupés sans diplôme ?") doit aussi matcher, sous peine de
# retomber par défaut sur NOTION (repli honnête -- RetrievalReranker reste capable de
# répondre -- mais qui prive la question du chemin chiffré exact). Choix faits en
# reprenant les formulations réelles des noms d'indicateurs curés (voir
# data/indicateurs_cures.py) plus des tournures naturelles équivalentes
# ("répartition", "part de", "proportion de") pour les questions sur une ventilation
# (sexe/milieu/diplôme/branche, voir src/lookup_structure.py) qui ne citent pas
# forcément le mot "taux".
MOTS_CHIFFRE = [
    "combien", "quel est le taux", "quelle est le taux", "quel est le nombre",
    "quelle est la valeur", "quel est le pourcentage", "en pourcentage",
    "quel pourcentage", "taux de", "taux d'", "nombre de", "valeur de", "chiffre de",
    "indice de", "indice des", "statistique",
    "structure de", "structure des", "répartition de", "répartition des",
    "part de", "part des", "proportion de", "proportion des",
    "effectif de", "effectif des", "espérance de vie", "valeurs ajoutées",
    "population de", "population du",
    "indice synthétique", "produit intérieur brut", "exportations de",
    "exportations des", "importations", "taux net", "population urbaine",
    "population rurale", "valeur ajoutée",
]

# Question chiffrée sans mot-outil explicite mais avec une année/période -- signal plus
# faible (une question narrative peut aussi citer une année), donc utilisé seulement en
# renfort si aucun des deux dictionnaires ci-dessus n'a tranché.
PATTERN_PERIODE = re.compile(r"\b(19|20)\d{2}\b|\bT[1-4]\b")

# Salutation / small talk : une question comme "hello" ou "salut" ne matche aucun des
# deux dictionnaires ci-dessus, tombe par defaut sur NOTION, et part dans une vraie
# recherche semantique (RetrievalReranker + LLM) pour finir par un refus grounding
# correct mais peu naturel ("je ne trouve pas d'information pertinente"). Verifie en
# dernier (voir ordre dans `classifier`) : ne se declenche QUE si aucun signal
# notionnel/chiffre n'a deja tranche, donc "Bonjour, quel est le taux de chomage ?"
# continue de repondre a la vraie question (CHIFFRE l'emporte). Regex avec \b plutot
# qu'un simple `in` : "hi" ou "bye" en substring nu matcherait a tort des mots comme
# "chiffre" (qui contient "hi") -- \b force une frontiere de mot des deux cotes.
PATTERN_SALUTATION = re.compile(
    r"\b(bonjour|bonsoir|salut|salam|slm|hello|hi|hey|coucou|merci|au revoir|"
    r"a bientot|à bientôt|bye|ça va|ca va)\b",
    re.IGNORECASE,
)

# (question) -> "CHIFFRE", "NOTION" ou "MIXTE" (toute autre valeur est traitee comme "ne
# sait pas"). Voir docstring de module.
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
        """Retourne TypeQuestion.CHIFFRE si la question porte sur une valeur précise,
        TypeQuestion.NOTION si elle porte sur une explication/méthodologie, ou
        TypeQuestion.MIXTE si les deux signaux sont présents à la fois (voir docstring
        de module, section "Cas mixte").

        Ordre de décision : signal mixte d'abord (le plus spécifique -- narratif
        combinable ET chiffré tous les deux présents), puis narratif pur, puis chiffré
        pur, puis salutation/small talk (voir docstring de `PATTERN_SALUTATION`) --
        vérifiée seulement ici, APRES notion/chiffré, pour qu'une question comme
        "Bonjour, quel est le taux de chômage ?" reste bien classée CHIFFRE et ne soit
        jamais avalée par la politesse d'ouverture -- puis repli sur la présence d'une
        période (signal faible), puis appel LLM en dernier recours si injecté (voir
        `_fonction_classification_llm`), puis NOTION par défaut -- un faux négatif sur
        NOTION bascule vers RetrievalReranker qui reste capable de faire remonter un
        chiffre s'il apparaît dans le texte d'un rapport, alors qu'un faux négatif sur
        CHIFFRE renverrait "indicateur non trouvé" sans aucune tentative de réponse.
        """
        signal = question.lower().strip()

        a_signal_notion = any(mot in signal for mot in MOTS_NOTION)
        a_signal_notion_combinable = any(mot in signal for mot in MOTS_NOTION_COMBINABLES)
        a_signal_chiffre = any(mot in signal for mot in MOTS_CHIFFRE) or bool(PATTERN_PERIODE.search(signal))

        if a_signal_notion_combinable and a_signal_chiffre:
            return TypeQuestion.MIXTE

        if a_signal_notion:
            return TypeQuestion.NOTION

        if a_signal_chiffre:
            return TypeQuestion.CHIFFRE

        if PATTERN_SALUTATION.search(signal):
            return TypeQuestion.SALUTATION

        if self._fonction_classification_llm is not None:
            resultat = self._classifier_via_llm(question)
            if resultat is not None:
                return resultat

        return TypeQuestion.NOTION

    def _classifier_via_llm(self, question: str) -> Optional[TypeQuestion]:
        """Dernier recours, appel défensif : toute exception (réseau, clé API absente,
        timeout) ou réponse inattendue (ni "CHIFFRE", "NOTION" ni "MIXTE") est traitée
        comme "ne sait pas" -- ne fait jamais planter `classifier`, se contente de
        laisser le repli NOTION habituel s'appliquer."""
        try:
            resultat = self._fonction_classification_llm(question)
        except Exception:
            return None
        resultat_normalise = (resultat or "").strip().upper()
        if resultat_normalise == "CHIFFRE":
            return TypeQuestion.CHIFFRE
        if resultat_normalise == "NOTION":
            return TypeQuestion.NOTION
        if resultat_normalise == "MIXTE":
            return TypeQuestion.MIXTE
        return None
