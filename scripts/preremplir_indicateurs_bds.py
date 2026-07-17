"""
Script de pré-remplissage des indicateurs curés depuis l'API BDS (figure B du
complément de conception, docs/complement_conception_bds.pdf : étape 1 de la
stratégie cache-aside décidée dans l'ADR 0004).

Ce script ne fait PAS encore l'upsert en base SQLite (la table `indicateur` gagnera
sa colonne `code_bds` mais le script d'insertion réel reste à écrire, voir TODO.md
Sprint 2 — "Script d'insertion en base"). Pour l'instant, il sert à valider de bout
en bout la chaîne bds_client -> ConstructeurIndicateurs sur les indicateurs curés
réels, et affiche un résumé exploitable tel quel.

Usage : python -m scripts.preremplir_indicateurs_bds
"""
from __future__ import annotations

from data.indicateurs_cures import INDICATEURS_CURES
from src.bds_client import recuperer_indicateur
from src.constructeur_indicateurs import ConstructeurIndicateurs


def main() -> None:
    constructeur = ConstructeurIndicateurs()
    total_lignes = 0
    total_echecs = 0

    for code, categorie in INDICATEURS_CURES:
        try:
            indicateur_json = recuperer_indicateur(code)
        except Exception as e:  # noqa: BLE001 - un échec par code ne doit pas arrêter le lot
            print(f"[!] echec sur {code} ({categorie}) : {e}")
            total_echecs += 1
            continue

        document = ConstructeurIndicateurs.construire_document_synthetique(indicateur_json)
        document.categorie = categorie

        # id_document=None ici : pas encore d'insertion en base réelle (voir docstring).
        lignes = constructeur.structurer_depuis_bds(indicateur_json, id_document=None)
        total_lignes += len(lignes)

        periodes = sorted({l.periode for l in lignes})
        derniere_periode = periodes[-1] if periodes else "?"
        print(
            f"{code:8} | {categorie:24} | {len(lignes):5} lignes | "
            f"derniere periode {derniere_periode:8} | {document.titre[:60]}"
        )

    print()
    print(f"Total : {total_lignes} lignes d'indicateurs construites, "
          f"{total_echecs} echec(s) sur {len(INDICATEURS_CURES)} codes.")


if __name__ == "__main__":
    main()
