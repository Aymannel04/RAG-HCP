"""
Client pour l'API de la Base de Donnees Statistiques du HCP (bds.hcp.ma).
Voir ADR 0004 (docs/adr/0004-api-bds-pour-les-indicateurs.md).

API non documentee publiquement, structure identifiee par inspection reseau :

- GET https://bds.hcp.ma/api/v1/subject-groups
  Renvoie l'arborescence complete du catalogue : 7 themes, chacun avec ses sujets,
  sous-sujets, et indicateurs (code + label). 832 indicateurs au total, dont
  Population & demographie (49), Marche du travail (32), Economie (216) — les
  3 categories ciblees par le projet.

- GET https://bds.hcp.ma/api/v1/indicators/{code}
  Renvoie la serie complete d'un indicateur donne : label, unite, source,
  frequence, toutes les periodes disponibles, et les dimensions de ventilation
  (ex. par region, par sexe, par branche d'activite) avec leurs valeurs.
"""
from __future__ import annotations

import requests

BASE_URL = "https://bds.hcp.ma/api/v1"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; HCP-RAG-Stage/0.1; usage academique interne)"}


def recuperer_catalogue() -> list[dict]:
    """Recupere l'arborescence complete du catalogue BDS (7 themes -> sujets ->
    sous-sujets -> indicateurs). Un seul appel HTTP pour tout le catalogue.
    """
    resp = requests.get(f"{BASE_URL}/subject-groups", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def aplatir_catalogue(catalogue: list[dict]) -> list[dict]:
    """Transforme l'arborescence en une liste plate d'indicateurs, chacun avec
    son theme/sujet/sous-sujet d'origine — plus simple a filtrer/parcourir que
    l'arbre brut.

    Retourne une liste de dicts :
    {"theme_code", "theme_label", "sujet", "sous_sujet", "code", "label"}
    """
    indicateurs = []
    for theme in catalogue:
        for sujet in theme.get("subjects", []):
            for sous_sujet in sujet.get("subSubjects", []):
                for indicateur in sous_sujet.get("indicators", []):
                    indicateurs.append(
                        {
                            "theme_code": theme.get("code"),
                            "theme_label": theme.get("label"),
                            "sujet": sujet.get("label"),
                            "sous_sujet": sous_sujet.get("label"),
                            "code": indicateur.get("code"),
                            "label": indicateur.get("label"),
                        }
                    )
    return indicateurs


def recuperer_indicateur(code: str) -> dict:
    """Recupere la serie complete d'un indicateur (toutes periodes, toutes
    dimensions de ventilation). Exemple de code : "I3181", "I2818".
    """
    resp = requests.get(f"{BASE_URL}/indicators/{code}", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    # Exemple d'usage manuel : recupere le catalogue et affiche un resume par theme.
    catalogue = recuperer_catalogue()
    indicateurs = aplatir_catalogue(catalogue)
    print(f"{len(indicateurs)} indicateurs au total")

    par_theme: dict[str, int] = {}
    for ind in indicateurs:
        par_theme[ind["theme_label"]] = par_theme.get(ind["theme_label"], 0) + 1
    for theme, n in par_theme.items():
        print(f"  {theme} : {n}")
