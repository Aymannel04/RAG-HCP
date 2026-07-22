"""
Pages listing (archives paginees) de hcp.ma, utilisees par Scraper.collecter_depuis_listing
/ decouvrir_urls_liste pour trouver automatiquement les URLs d'articles a collecter, plutot
que de maintenir une liste d'articles a la main (voir ADR 0006,
docs/adr/0006-decouverte-automatique-publications.md).

Different de data/seed_urls.py : seed_urls.py liste des URLS D'ARTICLES precises (pour un
test rapide et cible) ; ce fichier liste des URLS DE LISTING (des pages qui, elles,
contiennent des liens vers de nombreux articles, avec pagination).

Inventaire etabli en parcourant les pages de rubrique reelles de hcp.ma (breadcrumb
"Publications" de chaque sous-theme). Constat : chaque sous-theme (pas la categorie
mere) a sa propre page "Publications-<sous-theme>", sauf exception notee ci-dessous.

Usage prevu (a executer sur le PC, pas dans ce sandbox qui n'a pas d'acces reseau vers
hcp.ma) :

    from data.listing_urls import URLS_LISTING_PAR_CATEGORIE
    from src.scraper import Scraper

    scraper = Scraper()
    tous_documents = []
    for categorie, listings in URLS_LISTING_PAR_CATEGORIE.items():
        for url_listing in listings:
            tous_documents += scraper.collecter_depuis_listing(url_listing, categorie=categorie)

Autre piste identifiee mais volontairement pas utilisee ici (changement plus lourd,
a discuter avant d'y toucher) : hcp.ma/downloads/?tag=<categorie> est une
base de telechargements distincte, filtrable par tag, qui donne directement les liens de
fichiers (PDF/XLSX) avec titre/date, sans passer par la page HTML de l'article. Elle
pourrait remplacer tout ce mecanisme mais n'a pas ete validee (pagination, fiabilite) --
a explorer dans un ADR ulterieur si retenue.
"""

# --- Economie -------------------------------------------------------------------------
# 3 sous-themes sur 6 confirmes avec leur propre page "Publications-X". "Indices des
# prix et production" (r343) est lui-meme un regroupement de 4 sous-sous-themes (IPC,
# IPPI, IPI, ICE — voir ADR 0005, DOCX) sans page Publications a lui : chacun de ses
# 4 enfants a probablement sa propre page, pas encore verifiee. "Secteurs d'activite"
# et "Sphere informelle" pas encore verifies non plus.
URLS_LISTING_ECONOMIE = [
    "https://www.hcp.ma/Publications-Comptes-nationaux_r340.html",
    "https://www.hcp.ma/Publications-Conjoncture-et-prevision-economique_r330.html",
    "https://www.hcp.ma/Publications-Conjoncture-entreprise_r622.html",
    # "Etudes economiques" : page distincte (pas un sous-theme du menu), 25 publications
    # sur 5 pages. Gardee car elle couvre du contenu qui n'apparait dans aucun des
    # 3 listings ci-dessus.
    "https://www.hcp.ma/Etudes-economiques_r650.html",
    # A completer : Indices-des-prix-et-production (et ses 4 enfants IPC/IPPI/IPI/ICE),
    # Secteurs-d-activite_r363, Sphere-informelle_r418.
]

URLS_LISTING_MARCHE_DU_TRAVAIL = [
    # Couvre a elle seule les 3 sous-themes (Activite, Emploi, Chomage) -- 50
    # publications, 10 pages. Cas particulier : contrairement a Economie/Population,
    # Marche du travail a UNE SEULE page agregee pour toute la categorie plutot
    # qu'une page par sous-theme.
    "https://www.hcp.ma/Publications-Marche-du-travail_r425.html",
]

# --- Population & demographie ----------------------------------------------------------
# Inventaire complet (10/10 sous-themes). Contrairement a Marche du travail, il n'existe
# PAS de page "Publications-Population-demographie" agregee (verifie : la page existe
# mais est vide, r515.html) -- chaque sous-theme a sa propre page, il faut TOUTES les
# donner au Scraper pour couvrir la categorie.
URLS_LISTING_POPULATION_DEMOGRAPHIE = [
    "https://www.hcp.ma/Publications-Recensement-general-RGPH_r520.html",
    "https://www.hcp.ma/Publications-Structure-de-la-population_r525.html",
    "https://www.hcp.ma/Publications-Naissances-et-fecondite_r557.html",
    "https://www.hcp.ma/Publications-Mortalite-et-esperance-de-vie_r562.html",
    "https://www.hcp.ma/Publications-Couples-et-familles_r567.html",
    "https://www.hcp.ma/Publications-Vieillissement-de-la-population_r572.html",
    "https://www.hcp.ma/Publications-Immigration-mobilite-spatiale_r577.html",
    "https://www.hcp.ma/Publications-Genre_r582.html",
    "https://www.hcp.ma/Publications-Education-et-formation_r587.html",
    "https://www.hcp.ma/Publications-Sante-et-personnes-a-besoins-specifiques_r592.html",
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
    print(f"Total : {total} page(s) listing (Economie encore partielle, voir commentaires)")
