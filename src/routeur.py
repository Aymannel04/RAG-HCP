"""
Module Routeur — module 5 de l'architecture.
Rôle : classifier chaque question (chiffre précis vs notion/narratif) et aiguiller
vers LookupStructure ou RetrievalReranker.
Voir les deux scénarios formalisés dans docs/conception_uml_v3.pdf, figures 5 et 6.

Statut : squelette. Implémentation prévue semaine 3 (classification via prompt LLM simple).
"""
from __future__ import annotations

from enum import Enum


class TypeQuestion(Enum):
    CHIFFRE = "chiffre"
    NOTION = "notion"


class Routeur:
    """Classifie une question pour décider du chemin de traitement."""

    def classifier(self, question: str) -> TypeQuestion:
        """Retourne TypeQuestion.CHIFFRE si la question porte sur une valeur précise
        (indicateur, statistique), TypeQuestion.NOTION sinon (explication, méthodologie,
        rapport). V1 : appel LLM avec un prompt de classification court.
        """
        raise NotImplementedError("A implementer semaine 3")
