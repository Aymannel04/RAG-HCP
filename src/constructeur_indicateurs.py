"""
Module ConstructeurIndicateurs — module 4 de l'architecture.
Rôle : structurer les indicateurs chiffrés extraits des tableaux dans la table `indicateur`.

Statut : squelette. Pour la V1, viser une curation semi-manuelle sur les 15-20 indicateurs
clés retenus dans le périmètre (voir docs/fiche_cadrage_v4.pdf, section 2) plutôt qu'une
extraction 100% automatisée dès le départ — plus fiable, plus rapide à livrer.
"""
from __future__ import annotations

from .models import Indicateur


class ConstructeurIndicateurs:
    """Transforme les tableaux extraits en indicateurs structurés."""

    def structurer(self, id_document: int, tableaux: list[list[list[str]]]) -> list[Indicateur]:
        """Retourne la liste des Indicateur identifiés dans `tableaux`, prêts à insérer
        dans la table `indicateur` (voir db/schema.sql).
        """
        raise NotImplementedError("A implementer semaine 2, voir TODO.md")
