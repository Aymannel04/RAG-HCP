"""
Script de diagnostic ponctuel (28/07) : affiche la reponse brute de l'API BDS pour un
code indicateur donne, pour verifier si `dimensions` est vraiment vide/null (limite de
donnees, pas de bug) ou si elle contient des modalites qui ne remontent pourtant pas
dans `indicateur.region` en base (bug de parsing dans
ConstructeurIndicateurs.structurer_depuis_bds -- voir TODO.md, limite du 28/07).

Usage :

    python -m scripts.diagnostic_dimensions I4001
"""
from __future__ import annotations

import json
import sys

from src.bds_client import recuperer_indicateur


def main(code: str) -> None:
    data = recuperer_indicateur(code)
    print(f"=== {code} : {data.get('label')} ===")
    print()
    print("dimensions :")
    print(json.dumps(data.get("dimensions"), ensure_ascii=False, indent=2))
    print()
    cles_data = list((data.get("data") or {}).keys())
    print(f"nb entrees data : {len(cles_data)}")
    print(f"exemples de cles : {cles_data[:10]}")


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "I4001"
    main(code)
