"""
Script de test Scraper + Extracteur en conditions reelles (suite de tester_scraper_reel.py).

A executer depuis la racine du projet, sur ta machine :

    python -m scripts.tester_extraction_reelle

Pour chacune des 27 URLs de data/seed_urls.py :
1. Le Scraper recupere la page HTML ET detecte/telecharge les pieces jointes PDF/XLSX
   qu'elle reference (voir ADR 0003 : le RAG s'indexe uniquement sur les PDF/XLSX, le
   HTML ne sert qu'a les decouvrir).
2. L'Extracteur en sort le texte propre + les tableaux, pour chaque document (la page
   HTML elle-meme ET chaque piece jointe).

Resultat : un fichier .txt lisible par document dans scripts/extraits/ (un nom de
fichier distinct par document, meme si plusieurs partagent le titre de la page parente —
un PDF et sa page HTML parente ne doivent pas s'ecraser l'un l'autre en recevant le
meme nom de fichier).

A la fin : un resume par type (html/pdf/xlsx) pour voir d'un coup d'oeil combien de
pieces jointes ont ete trouvees et avec quel contenu.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.seed_urls import URLS_PAR_CATEGORIE
from src.extracteur import Extracteur
from src.scraper import Scraper


def nom_fichier_sûr(titre: str, secours: str) -> str:
    base = titre.strip() or secours
    base = re.sub(r"[^\w\- ]", "", base)[:60].strip().replace(" ", "_")
    return base or secours


def main() -> None:
    scraper = Scraper(delay=1.0)
    extracteur = Extracteur()

    dossier_sortie = Path(__file__).resolve().parent / "extraits"
    dossier_sortie.mkdir(exist_ok=True)

    compteur_par_type = Counter()
    longueur_par_type = Counter()
    total = 0

    for categorie, urls in URLS_PAR_CATEGORIE.items():
        print(f"--- {categorie} ---")
        documents = scraper.collecter(urls, categorie=categorie)

        # Regroupe par URL de page parente pour afficher clairement combien de pieces
        # jointes ont ete trouvees pour chaque page (0 est un resultat valide a voir).
        par_page: dict[str, int] = {}

        for doc in documents:
            total += 1
            compteur_par_type[doc.type] += 1

            try:
                texte_propre, tableaux = extracteur.extraire(doc)
            except Exception as e:  # noqa: BLE001 - un document casse ne doit pas arreter le run
                print(f"  [!] echec extraction sur {doc.url} ({doc.type}) : {e}")
                continue
            longueur_par_type[doc.type] += len(texte_propre)

            nom = nom_fichier_sûr(doc.titre, f"doc_{total}")
            # Suffixe par type + index global : evite qu'un PDF et sa page HTML parente
            # (meme titre herite) s'ecrasent dans scripts/extraits/.
            chemin = dossier_sortie / f"{nom}__{doc.type}_{total}.txt"

            lignes = [
                f"URL : {doc.url}",
                f"Type : {doc.type}",
                f"Langue : {doc.langue}",
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
            print(f"  -> [{doc.type}] {chemin.name} ({len(texte_propre)} caracteres, {len(tableaux)} tableau(x))")

            if doc.type == "html":
                par_page[doc.url] = 0
            else:
                # Rattache naivement a la derniere page html vue dans cette boucle
                # (suffisant ici car collecter() garde l'ordre page -> ses pieces jointes).
                for url_page in reversed(list(par_page)):
                    par_page[url_page] += 1
                    break

        for url_page, nb_pieces in par_page.items():
            if nb_pieces == 0:
                print(f"  [!] aucune piece jointe PDF/XLSX detectee sur {url_page}")

    print(f"\n=== Resume ({total} documents) ===")
    for type_doc in ("html", "pdf", "xlsx"):
        n = compteur_par_type.get(type_doc, 0)
        if n:
            print(f"{type_doc:5s} : {n:2d} document(s), {longueur_par_type[type_doc]:6d} caracteres de texte au total")
    print(f"\nDetail complet -> {dossier_sortie}")
    print("Regarde aussi les lignes [Scraper] ci-dessus (echecs, pieces arabes ignorees).")


if __name__ == "__main__":
    main()
