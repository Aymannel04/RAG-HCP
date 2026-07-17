"""
Module ConstructeurIndicateurs — module 4 de l'architecture.
Rôle : structurer les indicateurs chiffrés en lignes prêtes pour la table `indicateur`.

Deux sources possibles, voir ADR 0004 (docs/adr/0004-api-bds-pour-les-indicateurs.md) et
son complément (docs/complement_conception_bds.pdf) :
- `structurer_depuis_bds` : source primaire pour Économie / Marché du travail / Population,
  à partir d'un indicateur récupéré via `src/bds_client.py`. Implémenté et testé contre la
  forme réelle de l'API (vérifiée le 16-17 juillet 2026 sur les codes I3181, I2790, ...).
- `structurer` : repli PDF/XLSX pour le texte hors catalogue BDS. Pas encore implémenté
  (reste dans le backlog Sprint 2, voir TODO.md).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import Document, Indicateur


class ConstructeurIndicateurs:
    """Transforme des données chiffrées brutes (API BDS ou tableaux PDF/XLSX) en
    `Indicateur` structurés, prêts à insérer dans la table `indicateur`."""

    def structurer(self, id_document: int, tableaux: list[list[list[str]]]) -> list[Indicateur]:
        """Repli PDF/XLSX : retourne la liste des Indicateur identifiés dans `tableaux`.

        Pas encore implémenté : depuis l'ADR 0004, l'API BDS couvre la majorité des
        indicateurs des 3 catégories ciblées (voir `structurer_depuis_bds`), ce qui rend
        ce chemin moins prioritaire. Reste nécessaire pour les publications hors
        catalogue BDS (voir ADR 0003).
        """
        raise NotImplementedError("A implementer semaine 2, voir TODO.md")

    def structurer_depuis_bds(self, indicateur_json: dict, id_document: int) -> list[Indicateur]:
        """Transforme la réponse de `bds_client.recuperer_indicateur(code)` en une liste
        d'`Indicateur`, un par (période, ventilation).

        Forme réelle de `indicateur_json` (vérifiée en conditions réelles) :
        {
          "code": "I3181", "label": "...",
          "metaData": {"unit": "En millions de dhs", ...},
          "periods": ["2021T4", ...],
          "dimensions": [{"id": 51, "label": "Branche d'activité",
                           "modalites": [{"id": 250, "label": "Agriculture"}, ...]}],
          "data": {"250_2007T1": {"value": "5878", "footNote": None}, ...}
        }
        La clé de `data` est soit juste une période (indicateur sans ventilation), soit
        `{id_modalite}_{periode}` (une ventilation), soit `{id1}_{id2}_{periode}` (plusieurs
        dimensions croisées) — le code ci-dessous gère les trois cas de façon générique.
        """
        code = indicateur_json["code"]
        nom = indicateur_json["label"].strip()
        # `dict.get(cle, defaut)` ne retombe sur `defaut` que si la clé est ABSENTE.
        # Or l'API renvoie parfois explicitement `null` pour "dimensions" (indicateur
        # sans ventilation, ex. I2790 "Taux d'urbanisation") — la clé existe, sa valeur
        # est None, donc `.get("dimensions", [])` renvoie None et non []. D'où le
        # `or` après chaque `.get(...)` ci-dessous : il rattrape aussi bien la clé
        # absente que la clé présente avec une valeur null. Bug trouvé sur un vrai run
        # (voir échange du 17 juillet 2026, TypeError sur I2790).
        unite = (indicateur_json.get("metaData") or {}).get("unit")
        periodes_valides = set(indicateur_json.get("periods") or [])

        # id de modalité -> label, toutes dimensions confondues (une seule table de
        # correspondance suffit : les id de modalité sont uniques par indicateur).
        labels_modalite: dict[int, str] = {}
        for dimension in indicateur_json.get("dimensions") or []:
            for modalite in dimension.get("modalites") or []:
                labels_modalite[modalite["id"]] = modalite["label"].strip()

        indicateurs: list[Indicateur] = []
        for cle, entree in (indicateur_json.get("data") or {}).items():
            valeur_brute = entree.get("value")
            if valeur_brute in (None, "", "ND", "NS"):
                continue
            try:
                valeur = float(str(valeur_brute).replace(",", "."))
            except ValueError:
                continue

            parties = cle.split("_")
            periode = parties[-1]
            if periode not in periodes_valides:
                continue  # clé de forme inattendue : on ignore plutôt que de mal l'interpréter

            ids_modalite = parties[:-1]
            labels = [
                labels_modalite[int(mid)]
                for mid in ids_modalite
                if mid.isdigit() and int(mid) in labels_modalite
            ]
            region = ", ".join(labels) if labels else None

            indicateurs.append(
                Indicateur(
                    id_indicateur=None,
                    nom=nom,
                    valeur=valeur,
                    unite=unite,
                    periode=periode,
                    region=region,
                    id_document=id_document,
                    code_bds=code,
                )
            )
        return indicateurs

    @staticmethod
    def construire_document_synthetique(indicateur_json: dict) -> Document:
        """Construit le `Document` synthétique associé à un indicateur BDS (voir ADR 0004,
        section "Précisions du 15 juillet" : `type="api"`, `url` = fiche BDS, `titre` =
        libellé de l'indicateur). Sert de source citable pour la traçabilité (NF3), même si
        aucun fichier n'a réellement été téléchargé.
        """
        code = indicateur_json["code"]
        date_publication = None
        updating_date_ms = indicateur_json.get("updatingDate")
        if updating_date_ms:
            date_publication = datetime.fromtimestamp(
                updating_date_ms / 1000, tz=timezone.utc
            ).date().isoformat()

        return Document(
            id_document=None,
            url=f"https://bds.hcp.ma/main/indicators/{code}",
            titre=indicateur_json["label"].strip(),
            date_publication=date_publication,
            langue="fr",
            categorie="",  # renseignée par l'appelant selon le thème curé (voir data/indicateurs_cures.py)
            type="api",
        )
