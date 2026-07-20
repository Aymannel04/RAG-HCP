"""
Script d'indexation des documents collectés (PDF/XLSX/DOCX) : Extracteur -> insertion
SQLite (`document`) -> IndexeurTexte (chunking + embeddings + Chroma/BM25) -> insertion
SQLite (`chunk`). Les documents HTML ne sont jamais indexés (ADR 0003 : le RAG s'appuie
uniquement sur les pièces jointes téléchargeables, jamais sur le HTML de la page —
`indexer_document` filtre `type == "html"` explicitement, voir TODO.md Sprint 2).

Les indicateurs extraits de tableaux PDF/XLSX (`ConstructeurIndicateurs.structurer`)
restent hors périmètre de ce script : cette méthode n'est pas encore implémentée (voir
TODO.md, Sprint 2 — repli PDF/XLSX, priorité plus basse depuis que l'ADR 0004 couvre la
majorité des indicateurs via l'API BDS). Une fois disponible, la brancher ici de la même
façon que `scripts/preremplir_indicateurs_bds.py` le fait pour la source BDS.

Usage prévu (à exécuter sur le PC, ce sandbox n'a pas d'accès réseau vers hcp.ma) :

    python -m scripts.indexer_documents                  # tout indexer
    python -m scripts.indexer_documents --limite 3        # test rapide, 3 documents
    python -m scripts.indexer_documents --db chemin.db    # base personnalisée

Collecte via `data/listing_urls.py` (ADR 0006, `Scraper.collecter_depuis_listing`,
`max_pages=1` — portée "fraîcheur" par défaut ; passer `max_pages=None` dans le code
pour une collecte historique complète) puis indexe chaque `Document` brut retourné.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.base_donnees import connecter, inserer_chunk, inserer_document
from src.extracteur import Extracteur
from src.indexeur_texte import IndexeurTexte
from src.models import Document


def indexer_document(conn, extracteur: Extracteur, indexeur: IndexeurTexte, document: Document) -> dict:
    """Traite un `Document` brut déjà collecté par le Scraper : extraction, insertion
    SQLite, chunking + embeddings + indexation vectorielle/BM25. Retourne un petit
    résumé (nombre de chunks, etc.) plutôt que de lever en cas de document HTML/vide,
    pour que l'appelant puisse boucler sur un lot sans tout interrompre.
    """
    if document.type == "html":
        # Jamais indexé (ADR 0003) : la page HTML "vitrine" ne contient pas le vrai
        # contenu, on l'écarte ici avant tout traitement inutile.
        return {"statut": "ignore_html", "chunks": 0, "tableaux": 0, "id_document": None}

    texte, tableaux = extracteur.extraire(document)

    id_document = inserer_document(conn, document)
    document.id_document = id_document

    chunks_inseres = 0
    if texte.strip():
        chunks = indexeur.indexer(document, texte)
        for chunk in chunks:
            inserer_chunk(conn, chunk)
        chunks_inseres = len(chunks)

    return {
        "statut": "ok",
        "chunks": chunks_inseres,
        "tableaux": len(tableaux),
        "id_document": id_document,
    }


def main(chemin_db: Optional[Path] = None, limite: Optional[int] = None) -> None:
    # Imports locaux : evite de charger Scraper/requests pour les tests qui n'utilisent
    # que `indexer_document` (celui-ci n'a besoin d'aucun acces reseau).
    from data.listing_urls import URLS_LISTING_PAR_CATEGORIE
    from src.scraper import Scraper

    conn = connecter(chemin_db)
    extracteur = Extracteur()
    indexeur = IndexeurTexte()
    scraper = Scraper()

    total_documents = 0
    total_chunks = 0

    try:
        for categorie, listings in URLS_LISTING_PAR_CATEGORIE.items():
            for url_listing in listings:
                if limite is not None and total_documents >= limite:
                    break
                documents = scraper.collecter_depuis_listing(
                    url_listing, categorie=categorie, max_pages=1
                )
                for document in documents:
                    if limite is not None and total_documents >= limite:
                        break
                    resume = indexer_document(conn, extracteur, indexeur, document)
                    total_documents += 1
                    total_chunks += resume["chunks"]
                    print(
                        f"{document.type:5} | {resume['statut']:12} | "
                        f"{resume['chunks']:3} chunks | {document.titre[:60]}"
                    )
    finally:
        conn.close()

    print()
    print(f"Total : {total_documents} document(s) traite(s), {total_chunks} chunk(s) indexe(s).")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None, help="chemin de la base SQLite")
    parser.add_argument(
        "--limite", type=int, default=None,
        help="arrete apres N documents traites (utile pour un premier test rapide)",
    )
    args = parser.parse_args()
    main(chemin_db=args.db, limite=args.limite)
