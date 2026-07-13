"""
Module RetrievalReranker — module 6 de l'architecture.
Rôle : recherche hybride (dense + BM25) puis reranking pour ne garder que les
passages les plus pertinents, dans le cas d'une question conceptuelle/narrative
(voir docs/conception_uml_v3.pdf, figure 6).

Statut : squelette. Implémentation prévue semaine 3.
"""
from __future__ import annotations

from .models import Chunk


class RetrievalReranker:
    """Recherche hybride + reranking des passages pertinents pour une question."""

    def rechercher_et_trier(self, question: str, top_k: int = 5) -> list[Chunk]:
        """Retourne les `top_k` chunks les plus pertinents pour `question`, après
        recherche hybride (IndexeurTexte.rechercher) et reranking par cross-encoder.
        """
        raise NotImplementedError("A implementer semaine 3")
