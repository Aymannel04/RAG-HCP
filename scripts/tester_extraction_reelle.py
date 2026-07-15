"""
Script de test Scraper + Extracteur en conditions reelles (suite de tester_scraper_reel.py).

A executer depuis la racine du projet, sur ta machine :

    python -m scripts.tester_extraction_reelle

Pour chacune des 27 URLs de data/seed_urls.py :
1. Le Scraper recupere la page (HTML brut).
2. L'Extracteur en sort le texte propre (paragraphes) et les tableaux.

Resultat : un fichier .txt lisible par article dans scripts/extraits/, contenant le
texte propre + un apercu des tableaux trouves. Sert a juger si le contenu extrait est
vraiment exploitable pour le chunking/indexation (Sprint 2), pas seulement si le scraper
ne plante pas.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.seed_urls import URLS_PAR_CATEGORIE
from src.extracteur import Extracteur
from src.scraper import Scraper


def nom_fichier_sûr(titre: str, secours: str) -> str:
    base = titre.strip() or secours
    base = re.sub(r"[^\w\- ]", "", base)[:80].strip().replace(" ", "_")
    return base or secours


def main() -> None:
    scraper = Scraper(delay=1.0)
    extracteur = Extracteur()

    dossier_sortie = Path(__file__).resolve().parent / "extraits"
    dossier_sortie.mkdir(exist_ok=True)

    total = 0
    total_tableaux = 0
    for categorie, urls in URLS_PAR_CATEGORIE.items():
        print(f"--- {categorie} ---")
        documents = scraper.collecter(urls, categorie=categorie)

        for doc in documents:
            texte_propre, tableaux = extracteur.extraire(doc)
            total += 1
            total_tableaux += len(tableaux)

            nom = nom_fichier_sûr(doc.titre, f"doc_{total}")
            chemin = dossier_sortie / f"{nom}.txt"

            lignes = [
                f"URL : {doc.url}",
                f"Titre : {doc.titre}",
                f"Date : {doc.date_publication}",
                f"Categorie : {doc.categorie}",
                f"Longueur texte propre : {len(texte_propre)} caracteres",
                f"Nombre de tableaux trouves : {len(tableaux)}",
                "",
                "=== TEXTE PROPRE ===",
                texte_propre,
            ]
            if tableaux:
                lignes.append("\n=== APERCU DU PREMIER TABLEAU ===")
                for ligne in tableaux[0][:5]:
                    lignes.append(" | ".join(ligne))

            chemin.write_text("\n".join(lignes), encoding="utf-8")
            print(f"  -> {chemin.name} ({len(texte_propre)} caracteres, {len(tableaux)} tableau(x))")

    print(f"\n{total} articles extraits dans {dossier_sortie}")
    print(f"{total_tableaux} tableaux trouves au total")


if __name__ == "__main__":
    main()
