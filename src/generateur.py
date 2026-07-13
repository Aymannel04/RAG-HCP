"""
Module Generateur — module 8 de l'architecture.
Rôle : rédiger la réponse en langage naturel, toujours accompagnée de sa source
(document, date, lien) — grounding strict, jamais de chiffre hors contexte fourni.

Statut : squelette. Implémentation prévue semaines 3-4.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .models import Chunk, Indicateur


@dataclass
class Reponse:
    texte: str
    source_url: str
    source_titre: str
    source_date: Optional[str] = None


class Generateur:
    """Génère la réponse finale à partir du contexte récupéré (chunks ou indicateur)."""

    def generer_reponse(self, contexte: Union[list[Chunk], Indicateur, None]) -> Reponse:
        """Rédige une réponse sourcée à partir du contexte fourni.

        Contrainte de grounding strict : si `contexte` est vide/None, la réponse doit
        être explicite sur l'absence d'information plutôt que d'inventer une réponse
        (voir docs/fiche_cadrage_v4.pdf, section 8.5 - points de robustesse).
        """
        raise NotImplementedError("A implementer semaines 3-4")
