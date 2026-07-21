"""
Module RetrievalReranker — module 6 de l'architecture.
Rôle : recherche hybride (dense + BM25) puis reranking pour ne garder que les
passages les plus pertinents, dans le cas d'une question conceptuelle/narrative
(voir docs/conception_uml_v3.pdf, figure 6).

Décision d'implémentation (Sprint 3, 21 juillet 2026, voir ADR 0007) : reranking par
cross-encoder BAAI/bge-reranker-v2-m3 (via sentence-transformers), même famille que
BGE-M3 déjà retenu pour les embeddings (ADR 0002) -- cohérent, multilingue, open source,
hébergeable localement. Fonction de reranking injectable au constructeur, même patron
que `IndexeurTexte._embarquer` : évite de télécharger le modèle (~600 Mo) dans les tests.

Statut : implémenté, testé avec une fonction de reranking factice. PAS ENCORE validé
avec le vrai modèle (même limite que BGE-M3 en Sprint 2 : pas d'accès réseau dans le
bac à sable de développement) -- à valider sur la machine d'Ayman.
"""
from __future__ import annotations

from typing import Callable, Optional

from .indexeur_texte import IndexeurTexte
from .models import Chunk

NOM_MODELE_RERANKER = "BAAI/bge-reranker-v2-m3"

TypeFonctionReranking = Callable[[str, list[str]], list[float]]


class RetrievalReranker:
    """Recherche hybride + reranking des passages pertinents pour une question."""

    def __init__(
        self,
        indexeur: IndexeurTexte,
        fonction_reranking: Optional[TypeFonctionReranking] = None,
    ):
        """
        `indexeur` : instance déjà construite d'`IndexeurTexte` (Sprint 2), réutilisée
        pour la recherche hybride en amont du reranking.
        `fonction_reranking` : injectable pour les tests (voir docstring de module).
        """
        self._indexeur = indexeur
        self._fonction_reranking = fonction_reranking
        self._modele = None  # chargé paresseusement, voir _reranker

    def rechercher_et_trier(self, question: str, top_k: int = 5) -> list[Chunk]:
        """Retourne les `top_k` chunks les plus pertinents pour `question`, après
        recherche hybride (IndexeurTexte.rechercher) et reranking par cross-encoder.
        """
        marge = max(top_k * 4, 20)  # meme marge que la fusion RRF de Sprint 2
        candidats = self._indexeur.rechercher(question, top_k=marge)
        if not candidats:
            return []

        scores = self._reranker(question, [c.texte for c in candidats])
        classement = sorted(zip(candidats, scores), key=lambda paire: paire[1], reverse=True)
        return [chunk for chunk, _ in classement[:top_k]]

    def _reranker(self, question: str, textes: list[str]) -> list[float]:
        if self._fonction_reranking is not None:
            return self._fonction_reranking(question, textes)

        if self._modele is None:
            # Import local : sentence-transformers + le telechargement du modele
            # (~600 Mo) ne doivent se declencher que si on n'a pas injecte de fonction
            # de test (voir docstring du constructeur).
            from sentence_transformers import CrossEncoder

            self._modele = CrossEncoder(NOM_MODELE_RERANKER)

        paires = [[question, texte] for texte in textes]
        return self._modele.predict(paires).tolist()
