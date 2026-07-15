"""
Liste d'URLs de depart pour le premier test reel du Scraper (Sprint 1, TODO.md).

Compilee manuellement le 15 juillet 2026 en parcourant les pages de rubrique de hcp.ma
pour les 3 categories ciblees par la fiche de cadrage (docs/fiche_cadrage_v4.pdf, section 5) :
Economie, Marche du travail, Population & demographie.

Usage prevu (a executer sur le PC, pas dans ce sandbox qui n'a pas d'acces reseau vers
hcp.ma) :

    from data.seed_urls import URLS_PAR_CATEGORIE
    from src.scraper import Scraper

    scraper = Scraper()
    tous_documents = []
    for categorie, urls in URLS_PAR_CATEGORIE.items():
        tous_documents += scraper.collecter(urls, categorie=categorie)

Ces 27 URLs melangent actualites et publications, pages recentes (2026) et plus anciennes
(jusqu'a 2012), pour verifier que _extraire_titre/_extraire_date tiennent sur des gabarits
de page differents. A completer/elargir une fois le premier passage valide.
"""

URLS_ECONOMIE = [
    "https://www.hcp.ma/Situation-economique-nationale-au-premier-trimestre-2026_a4325.html",
    "https://www.hcp.ma/L-indice-des-prix-a-la-production-industrielle-energetique-et-miniere-IPPI-du-mois-de-Mai-2026_a4326.html",
    "https://www.hcp.ma/L-Indice-des-prix-a-la-consommation-IPC-du-mois-de-Mai-2026_a4322.html",
    "https://www.hcp.ma/Note-de-conjoncture-du-quatrieme-trimestre-2025-et-perspectives-pour-les-premier-et-deuxieme-trimestres-2026_a4296.html",
    "https://www.hcp.ma/Les-indices-du-commerce-exterieur-ICE-au-Maroc-premier-trimestre-2026_a4329.html",
    "https://www.hcp.ma/L-indice-de-la-production-industrielle-energetique-et-miniere-IPI--premier-trimestre-2026_a4321.html",
    "https://www.hcp.ma/Synthese-des-principaux-resultats-de-l-Enquete-Nationale-sur-les-unites-de-production-operant-dans-l-informel-2023-2024_a4109.html",
    "https://www.hcp.ma/Les-comptes-nationaux-provisoires-2025-Base-2014-Rapport-complet_a4318.html",
    "https://www.hcp.ma/Resultats-des-enquetes-trimestrielles-de-conjoncture-aupres-des-entreprises-2eme-trimestre-2026_a4316.html",
    "https://www.hcp.ma/Note-de-conjoncture-N-48-Avril-2026_a4298.html",
    "https://www.hcp.ma/Rapport-des-resultats-de-l-Enquete-Nationale-sur-le-Secteur-Informel-2023-2024-Mai-2025_a4110.html",
    "https://www.hcp.ma/Les-Cahiers-du-Plan-N-57-Juillet-2024_a4174.html",
]

URLS_MARCHE_DU_TRAVAIL = [
    "https://www.hcp.ma/Situation-du-marche-du-travail-au-Maroc-au-premier-trimestre-de-2026-a-partir-de-la-nouvelle-enquete-sur-la-main-d_a4309.html",
    "https://www.hcp.ma/Jeunes-NEET-au-Maroc-Profilage-statistique-au-profit-de-l-action-publique_a4302.html",
    "https://www.hcp.ma/Situation-du-marche-du-travail-en-2025_a4248.html",
    "https://www.hcp.ma/Activite-emploi-et-chomage-resultats-annuels-2025_a4310.html",
    "https://www.hcp.ma/Avant-propos-Comprendre-le-phenomene-des-jeunes-NEET-au-Maroc-par-M-Le-Haut-Commissaire-au-Plan_a4303.html",
    "https://www.hcp.ma/Activite-emploi-et-chomage-trimestriel--troisieme-trimestre-2025_a4238.html",
]

URLS_POPULATION_DEMOGRAPHIE = [
    "https://www.hcp.ma/L-UNFPA-et-le-HCP-explorent-les-enjeux-de-la-fecondite-a-l-occasion-de-la-Journee-mondiale-de-la-population_a4144.html",
    "https://www.hcp.ma/Note-d-information-a-l-occasion-de-la-Journee-Internationale-des-Femmes-2026_a4262.html",
    "https://www.hcp.ma/Synthese-des-premiers-resultats-de-l-enquete-Nationale-sur-la-Famille_a4289.html",
    "https://www.hcp.ma/RGPH-2024-caracteristiques-demographiques-et-socio-economiques-de-la-population-de-la-region-de-Rabat-Sale-Kenitra-et_a4319.html",
    "https://www.hcp.ma/Migration-interne-selon-les-resultats-du-recensement-general-de-la-population-et-de-l-habitat-de-2024-Octobre-2025_a4203.html",
    "https://www.hcp.ma/Les-provinces-du-Sud-du-Royaume-Donnees-demographiques-Septembre-2025_a4194.html",
    "https://www.hcp.ma/Conference-Debat-pour-la-presentation-des-principaux-resultats-de-l-ENF2025_a4293.html",
    "https://www.hcp.ma/Les-personnes-en-situation-de-handicap-au-Maroc-Analyse-issue-du-RGPH-de-2024-Mars-2026_a4269.html",
    "https://www.hcp.ma/Rapport-national-sur-la-population-et-developpement-au-Maroc-trente-ans-apres-la-conference-du-Caire-de-1994_a3854.html",
]

URLS_PAR_CATEGORIE = {
    "Economie": URLS_ECONOMIE,
    "Marche du travail": URLS_MARCHE_DU_TRAVAIL,
    "Population et demographie": URLS_POPULATION_DEMOGRAPHIE,
}

if __name__ == "__main__":
    total = sum(len(v) for v in URLS_PAR_CATEGORIE.values())
    for cat, urls in URLS_PAR_CATEGORIE.items():
        print(f"{cat}: {len(urls)} urls")
    print(f"Total: {total} urls")
