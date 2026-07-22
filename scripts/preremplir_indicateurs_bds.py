"""
Script de pré-remplissage des indicateurs curés depuis l'API BDS (figure B du
complément de conception, docs/complement_conception_bds.pdf : étape 1 de la
stratégie cache-aside décidée dans l'ADR 0004).

Fait le vrai upsert en base SQLite (voir src/base_donnees.py) : pour chaque code,
insère (ou retrouve) le document synthétique associé, puis upsert chaque ligne
d'indicateur sur (nom, periode, region, code_bds) — une ré-exécution (ex. tâche
planifiée nocturne, voir ADR 0004) met à jour les valeurs révisées plutôt que
d'empiler des doublons.

Usage : python -m scripts.preremplir_indicateurs_bds [chemin_db]
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from data.indicateurs_cures import INDICATEURS_CURES
from src.base_donnees import connecter, inserer_document, inserer_indicateur
from src.bds_client import recuperer_indicateur
from src.constructeur_indicateurs import ConstructeurIndicateurs


def main(chemin_db: Optional[Path] = None) -> None:
    conn = connecter(chemin_db)
    constructeur = ConstructeurIndicateurs()
    total_lignes = 0
    total_echecs = 0

    try:
        for code, categorie in INDICATEURS_CURES:
            try:
                indicateur_json = recuperer_indicateur(code)
            except Exception as e:  # noqa: BLE001 - un échec par code ne doit pas arrêter le lot
                print(f"[!] echec sur {code} ({categorie}) : {e}")
                total_echecs += 1
                continue

            document = ConstructeurIndicateurs.construire_document_synthetique(indicateur_json)
            document.categorie = categorie
            id_document = inserer_document(conn, document)

            lignes = constructeur.structurer_depuis_bds(indicateur_json, id_document=id_document)
            for ligne in lignes:
                inserer_indicateur(conn, ligne)
            total_lignes += len(lignes)

            periodes = sorted({l.periode for l in lignes})
            derniere_periode = periodes[-1] if periodes else "?"
            print(
                f"{code:8} | {categorie:24} | {len(lignes):5} lignes upsertees | "
                f"derniere periode {derniere_periode:8} | {document.titre[:60]}"
            )
    finally:
        conn.close()

    print()
    print(f"Total : {total_lignes} lignes d'indicateurs upsertees, "
          f"{total_echecs} echec(s) sur {len(INDICATEURS_CURES)} codes.")


if __name__ == "__main__":
    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    main(chemin)
