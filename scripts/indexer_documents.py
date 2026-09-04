"""
Script d'indexation des documents collectés (PDF/XLSX/DOCX) : Extracteur -> insertion
SQLite (`document`) -> IndexeurTexte (chunking + embeddings + Chroma/BM25) -> insertion
SQLite (`chunk`). Les documents HTML ne sont jamais indexés (ADR 0003 : le RAG s'appuie
uniquement sur les pièces jointes téléchargeables, jamais sur le HTML de la page —
`indexer_document` filtre `type == "html"` explicitement, voir TODO.md Sprint 2).

Les indicateurs extraits de tableaux PDF/XLSX (`ConstructeurIndicateurs.structurer`)
sont aussi insérés ici, en plus du texte narratif -- `structurer` ne reconnaît qu'un
motif précis (dictionnaire Code/Nom/Unité + table de données, voir sa docstring) et
renvoie [] pour tout le reste, donc l'appeler systématiquement sur chaque document est
sans risque : la plupart des PDF/XLSX ne produiront simplement aucun indicateur par ce
chemin, l'API BDS (ADR 0004) restant la source primaire pour les 3 catégories ciblées.

Usage prévu (à exécuter sur le PC, ce sandbox n'a pas d'accès réseau vers hcp.ma) :

    python -m scripts.indexer_documents                  # tout indexer
    python -m scripts.indexer_documents --limite 3        # test rapide, 3 documents
    python -m scripts.indexer_documents --db chemin.db    # base personnalisée

Collecte via `data/listing_urls.py` (ADR 0006, `Scraper.collecter_depuis_listing`,
`max_pages=1` — portée "fraîcheur" par défaut ; passer `max_pages=None` dans le code
pour une collecte historique complète) puis indexe chaque `Document` brut retourné.

Depuis le 30/08, une 2e source est aussi couverte : `URL_DERNIERES_PARUTIONS` (flux
transversal hcp.ma/downloads/?tag=Dernières+parutions, `Scraper.collecter_depuis_
telechargements`) — capture les publications qui ne sont rattachées à aucun sous-thème
des 3 catégories ci-dessus (ex. "Chiffres clés"), voir commentaire dans
`data/listing_urls.py`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.base_donnees import connecter, inserer_chunk, inserer_document, inserer_indicateur
from src.constructeur_indicateurs import ConstructeurIndicateurs
from src.extracteur import Extracteur
from src.indexeur_texte import IndexeurTexte
from src.models import Document


def indexer_document(
    conn, extracteur: Extracteur, indexeur: IndexeurTexte, document: Document,
    constructeur: Optional[ConstructeurIndicateurs] = None,
) -> dict:
    """Traite un `Document` brut déjà collecté par le Scraper : extraction, insertion
    SQLite, chunking + embeddings + indexation vectorielle/BM25, et indicateurs
    structurés si `ConstructeurIndicateurs.structurer` reconnaît un motif exploitable
    dans les tableaux extraits. Retourne un petit résumé (nombre de chunks, etc.)
    plutôt que de lever en cas de document HTML/vide, pour que l'appelant puisse
    boucler sur un lot sans tout interrompre.

    `constructeur` optionnel (instancié par défaut si absent, même patron
    qu'`extracteur`/`indexeur`) : simple point d'injection pour les tests.
    """
    if document.type == "html":
        # Jamais indexé (ADR 0003) : la page HTML "vitrine" ne contient pas le vrai
        # contenu, on l'écarte ici avant tout traitement inutile.
        return {"statut": "ignore_html", "chunks": 0, "tableaux": 0, "indicateurs": 0, "id_document": None}

    # Rafraichissement incremental (bug trouve le 27/08 -- voir JOURNAL.md) :
    # `main()` reinterroge systematiquement la page 1 de chaque listing a chaque
    # execution (portee "fraicheur", voir docstring de module), donc la plupart des
    # documents rencontres sont deja connus, pas de vraies nouveautes. Avant ce
    # correctif, on refaisait quand meme extraction + chunking + embeddings pour
    # CHAQUE document deja indexe, et on reinserait des chunks en double (seul
    # `document.url` a une contrainte UNIQUE, pas `chunk`) -- couteux et ca polluait
    # l'index avec des doublons a chaque relance. On verifie ici, AVANT tout travail
    # couteux, si l'URL est deja en base ; si oui on s'arrete net.
    deja_connu = conn.execute(
        "SELECT id_document FROM document WHERE url = ?", (document.url,)
    ).fetchone()
    if deja_connu is not None:
        return {"statut": "deja_indexe", "chunks": 0, "tableaux": 0, "indicateurs": 0, "id_document": deja_connu[0]}

    texte, tableaux = extracteur.extraire(document)

    id_document = inserer_document(conn, document)
    document.id_document = id_document

    chunks_inseres = 0
    if texte.strip():
        chunks = indexeur.indexer(document, texte)
        for chunk in chunks:
            inserer_chunk(conn, chunk)
        chunks_inseres = len(chunks)

    indicateurs_inseres = 0
    if tableaux:
        constructeur = constructeur or ConstructeurIndicateurs()
        indicateurs = constructeur.structurer(id_document, tableaux)
        for indicateur in indicateurs:
            inserer_indicateur(conn, indicateur)
        indicateurs_inseres = len(indicateurs)

    return {
        "statut": "ok",
        "chunks": chunks_inseres,
        "tableaux": len(tableaux),
        "indicateurs": indicateurs_inseres,
        "id_document": id_document,
    }


def main(chemin_db: Optional[Path] = None, limite: Optional[int] = None) -> int:
    """Renvoie le nombre de VRAIES nouveautes indexees ce run (statut "ok", voir
    `indexer_document`) -- distinct de `total_documents` ci-dessous, qui compte
    aussi les documents deja connus rencontres au passage. Utilise par
    `scripts/rafraichir_corpus.py` pour decider si le cache NOTION doit etre vide
    (voir docstring de ce module -- inutile de le vider une nuit sans nouveaute)."""
    # Imports locaux : evite de charger Scraper/requests pour les tests qui n'utilisent
    # que `indexer_document` (celui-ci n'a besoin d'aucun acces reseau).
    from data.listing_urls import URL_DERNIERES_PARUTIONS, URLS_LISTING_PAR_CATEGORIE
    from src.scraper import Scraper

    conn = connecter(chemin_db)
    extracteur = Extracteur()
    indexeur = IndexeurTexte()
    scraper = Scraper()

    total_documents = 0
    total_chunks = 0
    total_indicateurs = 0
    nouveaux_documents = 0

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
                    total_indicateurs += resume["indicateurs"]
                    if resume["statut"] == "ok":
                        nouveaux_documents += 1
                    print(
                        f"{document.type:5} | {resume['statut']:12} | "
                        f"{resume['chunks']:3} chunks | {resume['indicateurs']:4} indicateurs | {document.titre[:60]}"
                    )

        # Flux transversal (voir data/listing_urls.py, URL_DERNIERES_PARUTIONS) : capture
        # les nouveautes hors des 3 categories ci-dessus (ex. "Chiffres cles", brochures
        # generales, non rattachees a un seul sous-theme). Methode de collecte differente
        # (Scraper.collecter_depuis_telechargements) : chaque entree pointe deja vers le
        # fichier telechargeable, pas de page article HTML intermediaire.
        if limite is None or total_documents < limite:
            documents = scraper.collecter_depuis_telechargements(
                URL_DERNIERES_PARUTIONS, categorie="Publications generales", max_pages=1
            )
            for document in documents:
                if limite is not None and total_documents >= limite:
                    break
                resume = indexer_document(conn, extracteur, indexeur, document)
                total_documents += 1
                total_chunks += resume["chunks"]
                if resume["statut"] == "ok":
                    nouveaux_documents += 1
                print(
                    f"{document.type:5} | {resume['statut']:12} | "
                    f"{resume['chunks']:3} chunks | {document.titre[:60]}"
                )
    finally:
        conn.close()

    print()
    print(f"Total : {total_documents} document(s) traite(s), {total_chunks} chunk(s) indexe(s), "
          f"{total_indicateurs} indicateur(s) structure(s), {nouveaux_documents} nouveaute(s).")
    return nouveaux_documents


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
