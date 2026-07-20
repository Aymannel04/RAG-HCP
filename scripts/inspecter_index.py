"""
Script d'inspection de l'index (base SQLite + Chroma) : affiche un résumé lisible de
ce qui a été indexé — pensé pour montrer un résultat concret (à l'encadrante ou pour
se rassurer soi-même) plutôt que d'expliquer le pipeline sans rien à l'écran.

Usage :
    python -m scripts.inspecter_index                       # résumé de l'index
    python -m scripts.inspecter_index --recherche "question" # + une recherche réelle

Nécessite que `scripts/indexer_documents.py` ait déjà tourné (voir TODO.md, Sprint 2) :
sans ça, la base et l'index sont vides et ce script l'affichera clairement plutôt que
de planter.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from src.base_donnees import blob_vers_embedding, connecter
from src.indexeur_texte import IndexeurTexte


def resume_base(chemin_db: Optional[Path] = None) -> None:
    conn = connecter(chemin_db)
    try:
        nb_documents = conn.execute("SELECT COUNT(*) FROM document").fetchone()[0]
        nb_chunks = conn.execute("SELECT COUNT(*) FROM chunk").fetchone()[0]
        nb_indicateurs = conn.execute("SELECT COUNT(*) FROM indicateur").fetchone()[0]

        print("=== Résumé de la base SQLite ===")
        print(f"Documents  : {nb_documents}")
        print(f"Chunks     : {nb_chunks}")
        print(f"Indicateurs: {nb_indicateurs}")
        print()

        if nb_documents == 0:
            print("Base vide : lance d'abord `python -m scripts.indexer_documents` "
                  "(et `python -m scripts.preremplir_indicateurs_bds` pour les indicateurs).")
            return

        print("=== Documents (5 premiers) ===")
        for id_doc, titre, categorie, type_doc in conn.execute(
            "SELECT id_document, titre, categorie, type FROM document LIMIT 5"
        ):
            nb_chunks_doc = conn.execute(
                "SELECT COUNT(*) FROM chunk WHERE id_document = ?", (id_doc,)
            ).fetchone()[0]
            print(f"  [{id_doc}] ({type_doc}, {categorie}) {titre[:60]} — {nb_chunks_doc} chunk(s)")
        print()

        print("=== Extraits de chunks (3 premiers) ===")
        for id_chunk, texte, position, embedding_blob in conn.execute(
            "SELECT id_chunk, texte, position, embedding FROM chunk LIMIT 3"
        ):
            dimension = len(blob_vers_embedding(embedding_blob)) if embedding_blob else 0
            extrait = texte[:200].replace("\n", " ")
            print(f"  chunk #{id_chunk} (position {position}, embedding de dimension {dimension}) :")
            print(f"    « {extrait}{'...' if len(texte) > 200 else ''} »")
        print()

        print("=== Exemples d'indicateurs (5 premiers) ===")
        for nom, valeur, unite, periode, region in conn.execute(
            "SELECT nom, valeur, unite, periode, region FROM indicateur LIMIT 5"
        ):
            region_txt = f" ({region})" if region else ""
            print(f"  {nom}{region_txt} : {valeur} {unite or ''} — {periode}")
    finally:
        conn.close()


def demonstration_recherche(question: str, chemin_db: Optional[Path] = None) -> None:
    print()
    print(f"=== Recherche de démonstration : « {question} » ===")
    print("(charge le vrai modèle BGE-M3 — peut prendre du temps au premier lancement)")
    indexeur = IndexeurTexte()
    resultats = indexeur.rechercher(question, top_k=5)

    if not resultats:
        print("Aucun résultat (index vide ou question sans rapport avec le contenu indexé).")
        return

    for rang, chunk in enumerate(resultats, start=1):
        extrait = chunk.texte[:200].replace("\n", " ")
        print(f"  {rang}. (document #{chunk.id_document}, position {chunk.position})")
        print(f"     « {extrait}{'...' if len(chunk.texte) > 200 else ''} »")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None, help="chemin de la base SQLite")
    parser.add_argument("--recherche", type=str, default=None, help="question de démonstration")
    args = parser.parse_args()

    resume_base(args.db)
    if args.recherche:
        demonstration_recherche(args.recherche, args.db)


if __name__ == "__main__":
    main()
