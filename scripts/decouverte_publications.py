"""
Script de decouverte automatique des publications hcp.ma, a partir des pages listing
paginees (voir ADR 0006, docs/adr/0006-decouverte-automatique-publications.md) --
remplace le besoin de maintenir une liste d'URLs d'articles a la main
(data/seed_urls.py, garde pour des tests rapides et cibles).

Deux modes, meme mecanisme (Scraper.collecter_depuis_listing), portee differente :

    python -m scripts.decouverte_publications historique
        Parcourt TOUTES les pages de chaque listing (max_pages=None). A executer
        ponctuellement pour elargir la couverture du corpus aux publications anciennes.

    python -m scripts.decouverte_publications quotidien
        Parcourt seulement la 1ere page de chaque listing (max_pages=1). Pense pour une
        execution reguliere (tache planifiee, meme patron que le pre-remplissage nocturne
        des indicateurs BDS de l'ADR 0004) : hcp.ma trie ses listings du plus recent au
        plus ancien, donc toute nouvelle publication apparait forcement en page 1.

Dans les deux cas, aucune deduplication n'est geree ici : elle repose sur la contrainte
`document.url UNIQUE` de db/schema.sql au moment de l'insertion en base (voir
scripts/indexer_documents.py).

A executer sur le PC, pas dans le bac a sable de developpement (pas d'acces reseau vers
hcp.ma depuis ce sandbox) -- meme situation que scripts/valider_docx_reel.py.
"""
from __future__ import annotations

import sys

from data.listing_urls import URLS_LISTING_PAR_CATEGORIE
from src.scraper import Scraper


def decouvrir(mode: str) -> None:
    if mode not in ("historique", "quotidien"):
        raise ValueError('mode doit etre "historique" ou "quotidien"')

    max_pages = None if mode == "historique" else 1
    scraper = Scraper()

    total_urls = 0
    for categorie, listings in URLS_LISTING_PAR_CATEGORIE.items():
        if not listings:
            print(f"[!] {categorie} : aucune page listing configuree (voir data/listing_urls.py)")
            continue
        for url_listing in listings:
            try:
                urls = scraper.decouvrir_urls_liste(url_listing, max_pages=max_pages)
            except Exception as e:  # noqa: BLE001 - un echec par listing ne doit pas arreter le lot
                print(f"[!] echec sur {url_listing} : {e}")
                continue
            total_urls += len(urls)
            print(f"{categorie:24} | {url_listing}")
            print(f"{'':24} | {len(urls)} URL(s) d'article trouvee(s) (mode {mode})")
            for url in urls:
                print(f"{'':24}   - {url}")

    print()
    print(f"Total : {total_urls} URL(s) d'article decouverte(s) (mode {mode}).")
    print("Rappel : la deduplication des documents deja connus se fait a l'insertion en base "
          "(contrainte document.url UNIQUE), pas ici.")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "quotidien"
    decouvrir(mode)


if __name__ == "__main__":
    main()
