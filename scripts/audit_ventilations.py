"""
Audit systematique du chemin chiffre (13/10/2026), en lecture seule.

Contexte : le 23/09 un bug reel a ete trouve par hasard (voir src/lookup_structure.py,
`_resoudre_ventilation`) -- "population des femmes" renvoyait la population TOTALE parce
que la dimension demandee ("femmes") n'existait pas dans l'indicateur retenu et etait
ignoree en silence. Question laissee ouverte : combien d'autres cas du meme type ?

Methode : pour chaque indicateur reellement present dans la base et chaque dimension
reconnue par SYNONYMES_DIMENSIONS (sexe, milieu), on genere la question
"<nom de l'indicateur> <terme de la dimension>" et on classe le resultat :

  CORRECT          une valeur est renvoyee ET sa ventilation contient bien la dimension
                   demandee ;
  REFUS_JUSTIFIE   refus (None) alors que l'indicateur ne publie pas cette dimension ;
  REFUS_EXCESSIF   refus (None) alors que l'indicateur publie bien cette dimension
                   (perte de rappel, pas d'erreur -- le cas est sur) ;
  FAUX_SILENCIEUX  une valeur est renvoyee mais SA VENTILATION NE CONTIENT PAS la
                   dimension demandee -- la categorie dangereuse (chiffre confiant,
                   mais qui ne repond pas a la question posee).

Seul FAUX_SILENCIEUX est un defaut de fiabilite ; REFUS_EXCESSIF est un compromis assume
(refuser plutot que deviner). Les questions sont generees mecaniquement a partir des
noms de la base, pas ecrites a la main pour passer.

Usage : python -m scripts.audit_ventilations [chemin_db]
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from src.base_donnees import connecter
from src.lookup_structure import LookupStructure, _normaliser_accents

# (terme employe dans la question, label canonique attendu dans indicateur.region)
DIMENSIONS_TESTEES = [
    ("des femmes", "Féminin"), ("des hommes", "Masculin"),
    ("en milieu urbain", "Urbain"), ("en milieu rural", "Rural"),
]


def _tokens_region(region: Optional[str]) -> set[str]:
    if not region:
        return set()
    return {_normaliser_accents(t.strip().lower()) for t in region.split(",")}


def main(chemin_db: Optional[Path] = None) -> None:
    conn = connecter(chemin_db)
    lookup = LookupStructure(conn)

    groupes = conn.execute(
        "SELECT code_bds, nom FROM indicateur GROUP BY code_bds, nom ORDER BY code_bds, nom"
    ).fetchall()

    compteurs: Counter[str] = Counter()
    problemes: list[str] = []

    for code, nom in groupes:
        regions_dispo: set[str] = set()
        for (region,) in conn.execute(
            "SELECT DISTINCT region FROM indicateur WHERE nom = ? AND code_bds IS ?", (nom, code)
        ):
            regions_dispo |= _tokens_region(region)

        for terme, canonique in DIMENSIONS_TESTEES:
            attendu = _normaliser_accents(canonique.lower())
            question = f"{nom} {terme}"
            res = lookup.rechercher_indicateur(question)
            if res is None:
                verdict = "REFUS_EXCESSIF" if attendu in regions_dispo else "REFUS_JUSTIFIE"
            elif attendu in _tokens_region(res.region):
                verdict = "CORRECT"
            else:
                verdict = "FAUX_SILENCIEUX"
                problemes.append(
                    f"  question={question[:70]!r}\n    -> {res.nom[:60]!r} region={res.region!r} valeur={res.valeur}"
                )
            compteurs[verdict] += 1

    total = sum(compteurs.values())
    print(f"{len(groupes)} indicateurs x {len(DIMENSIONS_TESTEES)} dimensions = {total} questions generees\n")
    for verdict in ("CORRECT", "REFUS_JUSTIFIE", "REFUS_EXCESSIF", "FAUX_SILENCIEUX"):
        n = compteurs[verdict]
        print(f"  {verdict:16} {n:3}  ({100 * n / total:5.1f}%)")
    if problemes:
        print("\nFAUX_SILENCIEUX -- a examiner :")
        print("\n".join(problemes))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
