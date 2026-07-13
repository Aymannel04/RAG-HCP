"""
Module IndexeurTexte — module 3 de l'architecture.
Rôle : chunking, calcul des embeddings, indexation vectorielle + BM25.

Statut : squelette. Implémentation prévue semaine 2 (chunking + embeddings + Chroma)
et semaine 3 (recherche hybride), voir TODO.md.
"""
from __future__ import annotations

from .models import Chunk


class IndexeurTexte:
    """Découpe le texte, calcule les embeddings, indexe (vectoriel + BM25)."""

    def indexer(self, id_document: int, texte: str) -> list[Chunk]:
        """Découpe `texte` en chunks par section, calcule un embedding par chunk,
        et les ajoute à l'index vectoriel et à l'index BM25.
        """
        raise NotImplementedError("A implementer semaine 2 : chunking + embeddings + index Chroma/BM25")

    def rechercher(self, question: str, top_k: int = 10) -> list[Chunk]:
        """Recherche hybride (dense + BM25) des chunks les plus proches de `question`,
        avant reranking (voir RetrievalReranker).
        """
        raise NotImplementedError("A implementer semaine 3 : recherche hybride")
