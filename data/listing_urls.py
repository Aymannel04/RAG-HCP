"""
URLs de collecte pour les 3 categories ciblees (Economie, Marche du travail, Population
et demographie) ainsi que pour le flux transversal "Dernieres parutions".

Historique (voir docs/adr/0006-decouverte-automatique-publications.md) : ce fichier
listait a l'origine des pages "listing" HTML paginees par sous-theme
(hcp.ma/Publications-<sous-theme>_rXXX.html), decouvertes via
Scraper.collecter_depuis_listing / decouvrir_urls_liste. Ce mecanisme necessitait de
visiter chaque page article individuellement pour y trouver la piece jointe.

Changement du 08/09 (demande de l'encadrante, suite a relecture du rapport) : les 3
categories utilisent desormais le systeme hcp.ma/downloads/?tag=<categorie> -- la meme
base de telechargements deja utilisee pour le flux "Dernieres parutions" (trouve le
30/08, voir plus bas), qui donne un lien DIRECT vers le fichier telechargeable sans
passer par une page article HTML intermediaire. Un seul point d'entree par categorie
remplace donc la liste de pages par sous-theme ci-dessous (Marche du travail passait
deja par un point d'entree unique ; Economie et Population/demographie en avaient
plusieurs).

Usage prevu (a executer sur le PC, pas dans ce sandbox qui n'a pas d'acces reseau vers
hcp.ma) :

    from data.listing_urls import URLS_TELECHARGEMENTS_PAR_CATEGORIE
    from src.scraper import Scraper

    scraper = Scraper()
    tous_documents = []
    for categorie, url_tag in URLS_TELECHARGEMENTS_PAR_CATEGORIE.items():
        tous_documents += scraper.collecter_depuis_telechargements(url_tag, categorie=categorie)

Compatibilite ascendante : les anciennes URLs de listing (URLS_LISTING_ECONOMIE,
URLS_LISTING_MARCHE_DU_TRAVAIL, URLS_LISTING_POPULATION_DEMOGRAPHIE) sont conservees
ci-dessous en reference -- elles ne sont plus appelees par scripts/indexer_documents.py
ni scripts/decouverte_publications.py depuis ce changement, mais restent documentees
au cas ou le mecanisme par tag se revelerait insuffisant en couverture ou fiabilite a
l'usage (pagination non encore stress-testee sur un tres grand volume, voir note
historique ci-dessous) et qu'un retour arriere partiel soit necessaire.
"""

# --- Categories ciblees, systeme hcp.ma/downloads/?tag=... (depuis le 08/09) -----------
# URLs fournies telles quelles par l'encadrante (email du 08/09) : le tag "Economie"
# n'a pas besoin d'encodage particulier, "Marche du travail" et "Population et
# demographie" contiennent des caracteres accentues et un espace, encodes ici en
# URL-encoding standard (%C3%A9 = e accent aigu UTF-8, + = espace).
URL_TAG_ECONOMIE = "https://www.hcp.ma/downloads/?tag=Economie"
URL_TAG_MARCHE_DU_TRAVAIL = "https://www.hcp.ma/downloads/?tag=March%C3%A9+du+travail"
URL_TAG_DEMOGRAPHIE = "https://www.hcp.ma/downloads/?tag=Population+et+d%C3%A9mographie"

URLS_TELECHARGEMENTS_PAR_CATEGORIE = {
    "Economie": URL_TAG_ECONOMIE,
    "Marche du travail": URL_TAG_MARCHE_DU_TRAVAIL,
    "Population et demographie": URL_TAG_DEMOGRAPHIE,
}

# --- Flux transversal "Dernieres parutions" ---------------------------------------------
# Trouve le 30/08 en diagnostiquant l'absence d'un document ("Chiffres cles 2026") pourtant
# publie depuis plusieurs semaines : aucune des 3 categories ci-dessus ne le referencait,
# car "Chiffres cles" est une publication transversale (tag "Publications generales" sur
# hcp.ma), pas rattachee a un seul sous-theme.
#
# hcp.ma/downloads/?tag=... a sa propre structure HTML et son propre systeme de
# pagination (&p=N, pas ?start=N) -- voir Scraper.collecter_depuis_telechargements,
# desormais le mecanisme commun aux 3 categories ci-dessus ET a ce flux transversal.
# Le tag "Dernieres parutions" liste TOUTES les nouvelles publications, tous themes
# confondus, avec un lien DIRECT vers le fichier telechargeable (/file/XXXXXX/).
URL_DERNIERES_PARUTIONS = "https://www.hcp.ma/downloads/?tag=Dernières+parutions"


# --- Anciennes URLs de listing HTML (conservees en reference, plus utilisees) ----------
#
# Inventaire etabli en parcourant les pages de rubrique reelles de hcp.ma (breadcrumb
# "Publications" de chaque sous-theme). Different de data/seed_urls.py : seed_urls.py
# liste des URLS D'ARTICLES precises (pour un test rapide et cible) ; ces listes-ci
# listaient des URLS DE LISTING (des pages qui, elles, contenaient des liens vers de
# nombreux articles, avec pagination), utilisees via
# Scraper.collecter_depuis_listing / decouvrir_urls_liste (voir ADR 0006).

URLS_LISTING_ECONOMIE = [
    "https://www.hcp.ma/Publications-Comptes-nationaux_r340.html",
    "https://www.hcp.ma/Publications-Conjoncture-et-prevision-economique_r330.html",
    "https://www.hcp.ma/Publications-Conjoncture-entreprise_r622.html",
    "https://www.hcp.ma/Etudes-economiques_r650.html",
]

URLS_LISTING_MARCHE_DU_TRAVAIL = [
    "https://www.hcp.ma/Publications-Marche-du-travail_r425.html",
]

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
    print("Categories -> systeme de telechargements par tag (mecanisme actuel) :")
    for cat, url in URLS_TELECHARGEMENTS_PAR_CATEGORIE.items():
        print(f"  {cat}: {url}")
    total_ancien = sum(len(v) for v in URLS_LISTING_PAR_CATEGORIE.values())
    print(f"\n(Reference) Ancien mecanisme listing HTML : {total_ancien} page(s) au total, plus utilise.")
