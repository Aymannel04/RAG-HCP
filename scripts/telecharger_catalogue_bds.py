"""
Telecharge le catalogue complet de la BDS (bds.hcp.ma) et le sauvegarde localement.

A executer depuis la racine du projet, sur ta machine :

    python -m scripts.telecharger_catalogue_bds

Sauvegarde data/bds_catalogue.json (liste plate de tous les indicateurs, avec leur
theme/sujet d'origine) — sert de reference pour choisir quels indicateurs interroger
dans ConstructeurIndicateurs/LookupStructure (Sprint 2/3), sans avoir a re-parcourir
l'arborescence a chaque fois.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bds_client import aplatir_catalogue, recuperer_catalogue


def main() -> None:
    print("Telechargement du catalogue BDS...")
    catalogue = recuperer_catalogue()
    indicateurs = aplatir_catalogue(catalogue)

    sortie = Path(__file__).resolve().parent.parent / "data" / "bds_catalogue.json"
    sortie.write_text(json.dumps(indicateurs, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(indicateurs)} indicateurs sauvegardes dans {sortie}")

    par_theme: dict[str, int] = {}
    for ind in indicateurs:
        par_theme[ind["theme_label"]] = par_theme.get(ind["theme_label"], 0) + 1
    print("\nRepartition par theme :")
    for theme, n in sorted(par_theme.items(), key=lambda x: -x[1]):
        print(f"  {theme} : {n}")


if __name__ == "__main__":
    main()
