"""
Pages listing (archives paginees) de hcp.ma, utilisees par Scraper.collecter_depuis_listing
/ decouvrir_urls_liste pour trouver automatiquement les URLs d'articles a collecter, plutot
que de maintenir une liste d'articles a la main (voir ADR 0006,
docs/adr/0006-decouverte-automatique-publications.md).

Different de data/seed_urls.py : seed_urls.py liste des URLS D'ARTICLES precises (pour un
test rapide et cible) ; ce fichier liste des URLS DE LISTING (des pages qui, elles,
contiennent des liens vers de nombreux articles, avec pagination).

Verifie en reel le 20 juillet 2026 :
    https://www.hcp.ma/Publications-Marche-du-travail_r425.html
        -> 50 publications, 10 pages de 5 (pagination ?start=0..45)

Point ouvert (voir ADR 0006, section Consequences) : Economie et Population & demographie
sont decoupees en sous-themes sur hcp.ma (ex. Population : Recensement, Naissances et
fecondite, Mortalite...) et une seule page listing par categorie n'a pas ete confirmee
pour l'instant. Les entrees ci-dessous pour ces 2 categories sont donc partielles /
a completer -- le mecanisme de decouverte (src/scraper.py) fonctionne deja sur n'importe
laquelle de ces pages, il ne manque que l'inventaire complet des listings a lui donner.

Usage prevu (a executer sur le PC, pas dans ce sandbox qui n'a pas d'acces reseau vers
hcp.ma) :

    from data.listing_urls import URLS_LISTING_PAR_CATEGORIE
    from src.scraper import Scraper

    scraper = Scraper()
    tous_documents = []
    for categorie, listings in URLS_LISTING_PAR_CATEGORIE.items():
        for url_listing in listings:
            tous_documents += scraper.collecter_depuis_listing(url_listing, categorie=categorie)
"""

URLS_LISTING_ECONOMIE = [
    # "Etudes economiques" : 25 publications sur 5 pages, verifie le 20 juillet 2026.
    # Ne couvre a priori que les etudes, pas toutes les actualites/publications
    # (conjoncture, indices...) -- a completer : chercher l'equivalent de
    # "Publications-Marche-du-travail" pour Economie (page non trouvee lors de la
    # verification du 20 juillet, la page Economie_r327.html n'affichait qu'un extrait).
    "https://www.hcp.ma/Etudes-economiques_r650.html",
]

URLS_LISTING_MARCHE_DU_TRAVAIL = [
    # Confirme le 20 juillet 2026 : couvre a elle seule les 3 sous-themes (Activite,
    # Emploi, Chomage) -- 50 publications, 10 pages.
    "https://www.hcp.ma/Publications-Marche-du-travail_r425.html",
]

URLS_LISTING_POPULATION_DEMOGRAPHIE = [
    # Aucune page listing agregee trouvee le 20 juillet 2026 pour Population &
    # demographie (contrairement a Marche du travail) : la categorie est decoupee en
    # 10 sous-themes (Recensement, Structure de la population, Naissances et fecondite,
    # Mortalite et esperance de vie, Couples et familles, Vieillissement, Immigration et
    # mobilite spatiale, Genre, Education et formation, Sante). A completer : verifier
    # pour chacun s'il existe une page "Publications-<sous-theme>" du meme type que celle
    # de Marche du travail.
]

URLS_LISTING_PAR_CATEGORIE = {
    "Economie": URLS_LISTING_ECONOMIE,
    "Marche du travail": URLS_LISTING_MARCHE_DU_TRAVAIL,
    "Population et demographie": URLS_LISTING_POPULATION_DEMOGRAPHIE,
}

if __name__ == "__main__":
    total = sum(len(v) for v in URLS_LISTING_PAR_CATEGORIE.values())
    for cat, listings in URLS_LISTING_PAR_CATEGORIE.items():
        print(f"{cat}: {len(listings)} page(s) listing")
    print(f"Total : {total} page(s) listing (inventaire encore partiel, voir ADR 0006)")
