"""
Script de decouverte (apercu, sans telechargement) des publications hcp.ma pour les 3
categories ciblees, a partir du systeme de telechargements par tag
(hcp.ma/downloads/?tag=<categorie>, voir Scraper.collecter_depuis_telechargements).

Historique : ce script parcourait a l'origine les pages listing HTML paginees par
sous-theme (voir ADR 0006, docs/adr/0006-decouverte-automatique-publications.md),
remplacant le besoin de maintenir une liste d'URLs d'articles a la main
(data/seed_urls.py, garde pour des tests rapides et cibles). Depuis le 08/09 (demande
de l'encadrante), les 3 categories utilisent le systeme par tag plutot que les pages
listing (voir data/listing_urls.py) -- ce script est adapte en consequence : il liste
les entrees trouvees sous chaque tag SANS les telecharger (apercu uniquement), via le
meme mecanisme de decouverte que celui utilise en interne par
Scraper.collecter_depuis_telechargements.

Deux modes, meme mecanisme, portee differente :

    python -m scripts.decouverte_publications historique
        Parcourt TOUTES les pages de chaque tag (max_pages=None). A executer
        ponctuellement pour elargir la couverture du corpus aux publications anciennes.

    python -m scripts.decouverte_publications quotidien
        Parcourt seulement la 1ere page de chaque tag (max_pages=1). Pense pour une
        execution reguliere (tache planifiee, meme patron que le pre-remplissage nocturne
        des indicateurs BDS de l'ADR 0004) : hcp.ma trie ses telechargements du plus
        recent au plus ancien, donc toute nouvelle publication apparait forcement en
        page 1.

Dans les deux cas, aucune deduplication n'est geree ici : elle repose sur la contrainte
`document.url UNIQUE` de db/schema.sql au moment de l'insertion en base (voir
scripts/indexer_documents.py).

A executer sur le PC, pas dans le bac a sable de developpement (pas d'acces reseau vers
hcp.ma depuis ce sandbox) -- meme situation que scripts/valider_docx_reel.py.
"""
from __future__ import annotations

import sys

from data.listing_urls import URLS_TELECHARGEMENTS_PAR_CATEGORIE
from src.scraper import Scraper


def decouvrir(mode: str) -> None:
    if mode not in ("historique", "quotidien"):
        raise ValueError('mode doit etre "historique" ou "quotidien"')

    max_pages = None if mode == "historique" else 1
    scraper = Scraper()

    total_entrees = 0
    for categorie, url_tag in URLS_TELECHARGEMENTS_PAR_CATEGORIE.items():
        try:
            entrees = scraper._decouvrir_entrees_telechargements(url_tag, max_pages=max_pages)
        except Exception as e:  # noqa: BLE001 - un echec par categorie ne doit pas arreter le lot
            print(f"[!] echec sur {url_tag} : {e}")
            continue
        total_entrees += len(entrees)
        print(f"{categorie:24} | {url_tag}")
        print(f"{'':24} | {len(entrees)} entree(s) trouvee(s) (mode {mode})")
        for titre, href, type_fichier, date_publication, langue in entrees:
            print(f"{'':24}   - [{type_fichier:4} | {langue} | {date_publication or '?'}] {titre} ({href})")

    print()
    print(f"Total : {total_entrees} entree(s) decouverte(s) (mode {mode}).")
    print("Rappel : la deduplication des documents deja connus se fait a l'insertion en base "
          "(contrainte document.url UNIQUE), pas ici. Le filtrage par langue (arabe pur "
          "exclu, bilingue conserve, voir Scraper._detecter_langue) n'est applique qu'au "
          "moment de la collecte reelle (collecter_depuis_telechargements), pas dans cet "
          "apercu.")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "quotidien"
    decouvrir(mode)


if __name__ == "__main__":
    main()
