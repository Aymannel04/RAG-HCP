"""
Module IndexeurTexte — module 3 de l'architecture.
Rôle : chunking, calcul des embeddings, indexation vectorielle + BM25, recherche hybride.

Décisions prises ici, non fixées dans les docs de conception (fiche_cadrage_v4.pdf §8.1 et
conception_uml_v3.pdf §8 demandent un chunking « respectant la structure des documents » et
une « recherche hybride dense + BM25 », sans donner de taille de chunk, d'overlap, ni de
formule de fusion des scores — vérifié le 20 juillet 2026 en relisant les deux documents) :

- Chunking par paragraphe avec empaquetage glouton (voir `_decouper_en_chunks`) : taille
  cible ~1500 caractères (~300-400 tokens en français), chevauchement ~200 caractères.
  Approximation par caractères plutôt que par tokens du vrai tokenizer BGE-M3 : évite de
  charger le modèle (lourd, ~2 Go) juste pour compter des tokens, et garde la logique de
  découpage testable sans dépendance réseau/GPU.
- Fusion hybride par Reciprocal Rank Fusion (RRF) plutôt qu'une moyenne pondérée des
  scores : les scores denses (similarité cosinus, 0-1) et BM25 (non bornés) ne sont pas
  sur la même échelle ; RRF ne s'appuie que sur le RANG de chaque résultat dans chaque
  liste, ce qui évite d'avoir à normaliser/pondérer arbitrairement. Le reranking final
  (RetrievalReranker, cross-encoder) sert d'arbitrage plus fin ensuite.

Statut : implémenté (chunking, embeddings via sentence-transformers/BGE-M3, indexation
Chroma persistante + BM25 en mémoire, recherche hybride RRF), testé avec des doublures
(chromadb et rank_bm25 réels, mais fonction d'embedding factice — voir tests). PAS ENCORE
validé avec le vrai modèle BGE-M3 (~2 Go, pas téléchargeable dans ce sandbox sans accès
réseau) : à valider sur la machine d'Ayman via `scripts/indexer_documents.py`.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from .models import Chunk, Document

# Dossier de persistance de l'index vectoriel Chroma. Volontairement hors du dépôt git
# (voir .gitignore : data/chroma/) — régénérable à partir des documents déjà en base,
# comme data/raw/ pour les fichiers bruts.
DOSSIER_CHROMA = Path(__file__).resolve().parent.parent / "data" / "chroma"
NOM_COLLECTION = "chunks_hcp"

# Modèle d'embedding retenu par l'ADR 0002 (multilingue, dense+sparse+ColBERT — voir
# docs/note_stockage_routage_benchmark.pdf, section benchmarking embeddings).
NOM_MODELE_EMBEDDING = "BAAI/bge-m3"

# Chunking : voir justification en tête de fichier.
TAILLE_CHUNK_CARACTERES = 1500
CHEVAUCHEMENT_CARACTERES = 200

TypeFonctionEmbedding = Callable[[list[str]], list[list[float]]]


class IndexeurTexte:
    """Découpe le texte, calcule les embeddings, indexe (vectoriel + BM25), recherche."""

    def __init__(
        self,
        dossier_chroma: Optional[Path] = None,
        fonction_embedding: Optional[TypeFonctionEmbedding] = None,
    ):
        """
        `fonction_embedding` : injectable pour les tests (évite de charger le vrai
        modèle BGE-M3, ~2 Go, et tout accès réseau pour le télécharger). Par défaut
        (None), charge paresseusement sentence-transformers/BAAI-bge-m3 au premier
        appel qui en a besoin.
        """
        import chromadb  # import local : dépendance lourde, uniquement nécessaire ici

        self._dossier_chroma = Path(dossier_chroma) if dossier_chroma else DOSSIER_CHROMA
        self._dossier_chroma.mkdir(parents=True, exist_ok=True)
        self._client_chroma = chromadb.PersistentClient(path=str(self._dossier_chroma))
        self._collection = self._client_chroma.get_or_create_collection(NOM_COLLECTION)

        self._fonction_embedding = fonction_embedding
        self._modele = None  # chargé paresseusement, voir _embarquer

        # Index BM25 en mémoire, reconstruit à la demande (voir _assurer_index_bm25) :
        # rank_bm25 n'a pas de persistance native, et un rebuild complet à chaque
        # recherche reste rapide à l'échelle du prototype (des centaines de chunks).
        self._bm25 = None
        self._bm25_ids: list[str] = []
        self._bm25_a_jour = False

    def indexer(self, document: Document, texte: str) -> list[Chunk]:
        """Découpe `texte` en chunks, calcule un embedding par chunk, et les ajoute à
        l'index vectoriel (Chroma) — l'index BM25 se reconstruit paresseusement au
        prochain appel à `rechercher`.

        `document.id_document` doit déjà être renseigné (la ligne `document` doit être
        insérée en base SQLite avant l'indexation, voir scripts/indexer_documents.py) :
        c'est cet id qui relie chunk -> document dans les métadonnées Chroma comme dans
        la table `chunk` (foreign key, voir db/schema.sql).

        Retourne les `Chunk` (avec embedding) prêts à être persistés en base SQLite par
        le script d'insertion — IndexeurTexte n'écrit jamais lui-même dans SQLite,
        conformément à la séparation des responsabilités du MLD (voir
        docs/conception_uml_v3.pdf, figure 3).
        """
        if document.id_document is None:
            raise ValueError(
                "document.id_document est requis (le document doit deja etre insere "
                "en base avant l'indexation, voir scripts/indexer_documents.py)"
            )

        morceaux = self._decouper_en_chunks(texte)
        if not morceaux:
            return []

        embeddings = self._embarquer(morceaux)

        chunks = [
            Chunk(
                id_chunk=None,
                id_document=document.id_document,
                texte=morceau,
                position=position,
                embedding=embedding,
            )
            for position, (morceau, embedding) in enumerate(zip(morceaux, embeddings))
        ]

        ids = [f"doc{document.id_document}_chunk{c.position}" for c in chunks]
        metadonnees = [
            {
                "id_document": document.id_document,
                "position": c.position,
                "categorie": document.categorie or "",
                "langue": document.langue,
                "date_publication": document.date_publication or "",
                "titre": document.titre,
                "url": document.url,
            }
            for c in chunks
        ]
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=morceaux,
            metadatas=metadonnees,
        )
        self._bm25_a_jour = False
        return chunks

    def rechercher(self, question: str, top_k: int = 10) -> list[Chunk]:
        """Recherche hybride (dense + BM25) des chunks les plus proches de `question`,
        fusionnés par Reciprocal Rank Fusion (voir justification en tête de fichier).
        """
        if self._collection.count() == 0:
            return []

        k_candidats = max(top_k * 4, 20)  # marge avant fusion, pratique standard RRF

        embedding_question = self._embarquer([question])[0]
        resultats_denses = self._collection.query(
            query_embeddings=[embedding_question],
            n_results=min(k_candidats, self._collection.count()),
        )
        ids_denses = resultats_denses["ids"][0]

        ids_bm25 = self._rechercher_bm25(question, k_candidats)

        ids_fusionnes = self._fusionner_rrf([ids_denses, ids_bm25], top_k)
        if not ids_fusionnes:
            return []

        resultats = self._collection.get(ids=ids_fusionnes, include=["documents", "metadatas"])
        chunks_par_id = {
            id_: Chunk(
                id_chunk=None,
                id_document=meta["id_document"],
                texte=doc,
                position=meta["position"],
            )
            for id_, doc, meta in zip(resultats["ids"], resultats["documents"], resultats["metadatas"])
        }
        # `get` ne garantit pas l'ordre des ids demandes : on re-ordonne selon le rang RRF.
        return [chunks_par_id[id_] for id_ in ids_fusionnes if id_ in chunks_par_id]

    # --- Chunking -------------------------------------------------------------------

    @staticmethod
    def _decouper_en_chunks(
        texte: str,
        taille_max: int = TAILLE_CHUNK_CARACTERES,
        chevauchement: int = CHEVAUCHEMENT_CARACTERES,
    ) -> list[str]:
        """Découpe par paragraphe (respecte la structure du document, voir
        fiche_cadrage_v4.pdf §7.2) avec empaquetage glouton : accumule des paragraphes
        entiers jusqu'à `taille_max`, puis démarre un nouveau chunk en reprenant la fin
        du précédent (`chevauchement` caractères) pour ne pas couper le contexte entre
        deux chunks consécutifs.

        Un paragraphe seul plus grand que `taille_max` (ex. tableau aplati en un bloc de
        texte) est tronçonné à la dure plutôt qu'ignoré, pour ne perdre aucun contenu.
        """
        paragraphes = [p.strip() for p in texte.split("\n") if p.strip()]
        if not paragraphes:
            return []

        chunks: list[str] = []
        courant = ""

        for paragraphe in paragraphes:
            if len(paragraphe) > taille_max:
                if courant:
                    chunks.append(courant)
                    courant = ""
                pas = max(taille_max - chevauchement, 1)
                for i in range(0, len(paragraphe), pas):
                    chunks.append(paragraphe[i : i + taille_max])
                continue

            candidat = f"{courant}\n{paragraphe}" if courant else paragraphe
            if len(candidat) <= taille_max:
                courant = candidat
            else:
                chunks.append(courant)
                amorce = courant[-chevauchement:] if chevauchement else ""
                courant = f"{amorce}\n{paragraphe}" if amorce else paragraphe

        if courant:
            chunks.append(courant)

        return chunks

    # --- Embeddings -------------------------------------------------------------------

    def _embarquer(self, textes: list[str]) -> list[list[float]]:
        if self._fonction_embedding is not None:
            return self._fonction_embedding(textes)

        if self._modele is None:
            # Import local : sentence-transformers + le telechargement du modele (~2 Go)
            # ne doivent se declencher que si on n'a pas injecte de fonction de test
            # (voir docstring du constructeur).
            from sentence_transformers import SentenceTransformer

            self._modele = SentenceTransformer(NOM_MODELE_EMBEDDING)

        return self._modele.encode(textes, normalize_embeddings=True).tolist()

    # --- BM25 ---------------------------------------------------------------------

    def _assurer_index_bm25(self) -> None:
        if self._bm25_a_jour:
            return

        from rank_bm25 import BM25Okapi

        tout = self._collection.get(include=["documents"])
        self._bm25_ids = tout["ids"]
        corpus_tokenise = [self._tokeniser(doc) for doc in tout["documents"]]
        self._bm25 = BM25Okapi(corpus_tokenise) if corpus_tokenise else None
        self._bm25_a_jour = True

    def _rechercher_bm25(self, question: str, k: int) -> list[str]:
        self._assurer_index_bm25()
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(self._tokeniser(question))
        classement = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self._bm25_ids[i] for i in classement[:k] if scores[i] > 0]

    @staticmethod
    def _tokeniser(texte: str) -> list[str]:
        return re.findall(r"\w+", texte.lower())

    # --- Fusion -------------------------------------------------------------------

    @staticmethod
    def _fusionner_rrf(listes_classees: list[list[str]], top_k: int, k_rrf: int = 60) -> list[str]:
        """Reciprocal Rank Fusion : score(id) = somme, sur les listes ou `id` apparait,
        de 1 / (k_rrf + rang). k_rrf=60 est la valeur usuelle de la litterature RRF
        (Cormack, Clarke & Buettcher, 2009), pas de raison de s'en ecarter ici.
        """
        scores: dict[str, float] = {}
        for liste in listes_classees:
            for rang, id_ in enumerate(liste):
                scores[id_] = scores.get(id_, 0.0) + 1.0 / (k_rrf + rang + 1)
        classement = sorted(scores.keys(), key=lambda id_: scores[id_], reverse=True)
        return classement[:top_k]
