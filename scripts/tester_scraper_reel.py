"""
Script de test du Scraper en conditions reelles (Sprint 1, TODO.md).

A executer depuis la racine du projet, sur ta machine (pas dans le sandbox Claude qui
n'a pas acces reseau vers hcp.ma) :

    python -m scripts.tester_scraper_reel

Ce script :
1. Recupere les 27 URLs de data/seed_urls.py.
2. Les fait passer par Scraper.collecter (une vraie requete HTTP par page).
3. Affiche un resume (succes / echecs) et sauvegarde le detail dans
   scripts/resultats_test_scraper.json pour inspection.

Ca ne teste QUE le Scraper (etape 1 du pipeline), pas encore l'Extracteur ni la suite.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.seed_urls import URLS_PAR_CATEGORIE
from src.scraper import Scraper


def main() -> None:
    scraper = Scraper(delay=1.0)
    resultats = []
    total_urls = sum(len(v) for v in URLS_PAR_CATEGORIE.values())
    print(f"Test sur {total_urls} URLs reparties en {len(URLS_PAR_CATEGORIE)} categories...\n")

    for categorie, urls in URLS_PAR_CATEGORIE.items():
        print(f"--- {categorie} ({len(urls)} urls) ---")
        documents = scraper.collecter(urls, categorie=categorie)
        echecs = len(urls) - len(documents)
        print(f"  -> {len(documents)} recuperees, {echecs} echec(s)\n")

        for doc in documents:
            resultats.append(
                {
                    "categorie": categorie,
                    "url": doc.url,
                    "titre": doc.titre,
                    "date_publication": doc.date_publication,
                    "titre_vide": doc.titre == "",
                    "date_manquante": doc.date_publication is None,
                    "longueur_html": len(doc.texte_brut or ""),
                }
            )

    sorties = Path(__file__).resolve().parent / "resultats_test_scraper.json"
    sorties.write_text(json.dumps(resultats, ensure_ascii=False, indent=2), encoding="utf-8")

    titres_vides = sum(1 for r in resultats if r["titre_vide"])
    dates_manquantes = sum(1 for r in resultats if r["date_manquante"])

    print("=== Resume ===")
    print(f"Documents recuperes : {len(resultats)} / {total_urls}")
    print(f"Titres vides (a corriger dans _extraire_titre) : {titres_vides}")
    print(f"Dates manquantes (a corriger dans _extraire_date) : {dates_manquantes}")
    print(f"Detail complet -> {sorties}")


if __name__ == "__main__":
    main()
