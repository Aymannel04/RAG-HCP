"""
Script de validation reelle du support DOCX (ADR 0005).

A lancer depuis la racine du repo, sur la machine d'Ayman (le sandbox n'a pas
d'acces reseau vers hcp.ma - voir data/seed_urls.py) :

    python -m scripts.valider_docx_reel

Ce script utilise le VRAI Scraper (detection + telechargement + validation des
pieces jointes) et le VRAI Extracteur (extraction texte/tableaux) sur les pages
IPC et IPPI de Mai 2026, qui ne publient leur note mensuelle qu'en .docx (voir
ADR 0005). Rien n'est reimplemente : c'est exactement le pipeline src/scraper.py +
src/extracteur.py utilise en production.

Aucune insertion en base ici (pas encore l'objet de ce script) - juste la preuve
que le pipeline DOCX marche de bout en bout sur un vrai fichier hcp.ma.
"""
from src.scraper import Scraper
from src.extracteur import Extracteur

URLS_TEST = [
    "https://www.hcp.ma/L-Indice-des-prix-a-la-consommation-IPC-du-mois-de-Mai-2026_a4322.html",
    "https://www.hcp.ma/L-indice-des-prix-a-la-production-industrielle-energetique-et-miniere-IPPI-du-mois-de-Mai-2026_a4326.html",
]


def main():
    scraper = Scraper()  # inclure_arabe=False par defaut : on ne veut que le FR
    extracteur = Extracteur()

    documents = scraper.collecter(URLS_TEST, categorie="Economie")

    docx_trouves = [d for d in documents if d.type == "docx"]
    print(f"\n{len(documents)} documents recuperes au total, dont {len(docx_trouves)} .docx\n")

    if not docx_trouves:
        print("AUCUN .docx recupere - verifier que le lien /attachment/.../ n'a pas change,")
        print("ou que _contenu_semble_valide n'a pas rejete le fichier a tort.")
        return

    for doc in docx_trouves:
        print("=" * 70)
        print(f"Document : {doc.titre}")
        print(f"URL      : {doc.url}")
        print(f"Fichier  : {doc.texte_brut}")
        print(f"Langue   : {doc.langue}")

        texte, tableaux = extracteur.extraire(doc)

        print(f"\n--- Texte extrait : {len(texte)} caracteres, "
              f"{texte.count(chr(10)) + 1 if texte else 0} lignes ---")
        print(texte[:600])
        if len(texte) > 600:
            print(f"... [{len(texte) - 600} caracteres restants]")

        print(f"\n--- Tableaux extraits : {len(tableaux)} ---")
        for i, tableau in enumerate(tableaux):
            nb_lignes = len(tableau)
            nb_colonnes = len(tableau[0]) if tableau else 0
            print(f"  Tableau {i + 1} : {nb_lignes} lignes x {nb_colonnes} colonnes")
            if tableau:
                print(f"    Premiere ligne  : {tableau[0]}")
            if nb_lignes > 1:
                print(f"    Derniere ligne  : {tableau[-1]}")
        print()

    print("=" * 70)
    print("Fin du test. Si aucune erreur/traceback n'est apparue ci-dessus,")
    print("le pipeline DOCX (Scraper + Extracteur) est valide en conditions reelles.")


if __name__ == "__main__":
    main()
