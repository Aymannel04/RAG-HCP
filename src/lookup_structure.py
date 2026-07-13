"""
Module LookupStructure — module 7 de l'architecture.
Rôle : requête directe et exacte sur la table `indicateur`, dans le cas d'une
question chiffrée (voir docs/conception_uml_v3.pdf, figure 5).
C'est ce module qui élimine le risque d'hallucination sur les chiffres officiels
(voir docs/fiche_cadrage_v4.pdf, section 9 - analyse des risques).

Statut : squelette. Implémentation prévue semaine 3.
"""
from __future__ import annotations

from typing import Optional

from .models import Indicateur


class LookupStructure:
    """Récupère un indicateur exact par requête directe sur la base structurée."""

    def rechercher_indicateur(self, question: str) -> Optional[Indicateur]:
        """Identifie l'indicateur demandé (nom, période, région éventuelle) et
        exécute une requête SQL exacte sur la table `indicateur`. Retourne None
        si aucun indicateur correspondant n'est trouvé (le Routeur doit alors
        basculer sur RetrievalReranker, voir docs/fiche_cadrage_v4.pdf section 8.5).
        """
        raise NotImplementedError("A implementer semaine 3")
