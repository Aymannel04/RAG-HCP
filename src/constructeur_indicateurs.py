"""
Module ConstructeurIndicateurs — module 4 de l'architecture.
Rôle : structurer les indicateurs chiffrés en lignes prêtes pour la table `indicateur`.

Deux sources possibles, voir ADR 0004 (docs/adr/0004-api-bds-pour-les-indicateurs.md) et
son complément (docs/complement_conception_bds.pdf) :
- `structurer_depuis_bds` : source primaire pour Économie / Marché du travail / Population,
  à partir d'un indicateur récupéré via `src/bds_client.py`.
- `structurer` : repli PDF/XLSX pour le texte hors catalogue BDS. Non prioritaire depuis
  que l'API BDS couvre la majorité des indicateurs des 3 catégories ciblées (voir
  TODO.md).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import Document, Indicateur


class ConstructeurIndicateurs:
    """Transforme des données chiffrées brutes (API BDS ou tableaux PDF/XLSX) en
    `Indicateur` structurés, prêts à insérer dans la table `indicateur`."""

    def structurer(self, id_document: int, tableaux: list[list[list[str]]]) -> list[Indicateur]:
        """Repli PDF/XLSX : retourne la liste des Indicateur identifiés dans `tableaux`.

        Non implémenté : depuis l'ADR 0004, l'API BDS couvre la majorité des
        indicateurs des 3 catégories ciblées (voir `structurer_depuis_bds`), ce qui rend
        ce chemin moins prioritaire. Reste nécessaire pour les publications hors
        catalogue BDS (voir ADR 0003).
        """
        raise NotImplementedError("Repli PDF/XLSX hors périmètre V1, voir TODO.md")

    def structurer_depuis_bds(self, indicateur_json: dict, id_document: int) -> list[Indicateur]:
        """Transforme la réponse de `bds_client.recuperer_indicateur(code)` en une liste
        d'`Indicateur`, un par (période, ventilation).

        Forme réelle de `indicateur_json` renvoyée par l'API BDS (vérifiée en
        conditions réelles sur I4001) :
        {
          "code": "I4001", "label": "...",
          "metaData": {"unit": "%", ...},
          "periods": ["2025", ...],
          "dimensions": [
            {"id": 3, "label": "Mileu", "modalites": [
                {"id": 11, "label": "National", "total": true},
                {"id": 12, "label": "Urbain", "total": false}, ...]},
            {"id": 5, "label": "Sexe", "modalites": [
                {"id": 19, "label": "Total", "total": true},
                {"id": 21, "label": "Feminin", "total": false}, ...]}
          ],
          "data": {"11.14.21_2014": {"value": "13.3", "footNote": None}, ...}
        }
        La clé de `data` est soit juste une période (indicateur sans ventilation), soit
        `{prefixe}_{periode}` où `prefixe` est un ou plusieurs ids de modalité joints
        par un POINT (une par dimension croisée, ex. "11.14.21" = milieu.âge.sexe) --
        jamais joints par "_", qui ne sépare que le prefixe de la période elle-même.
        Chaque dimension a une modalité marquée `"total": true` (l'agrégat de CETTE
        dimension, ex. "National" pour Milieu, "15 ans et plus" pour Âge, "Total" pour
        Sexe -- le libellé varie, pas de convention de nommage fiable). Ces modalités
        agrégées sont volontairement EXCLUES de `region` : une ligne où seule la
        dimension Sexe est spécifique (Féminin) et Milieu/Âge sont à leur modalité
        "total" donne `region="Féminin"`, pas `region="Féminin, National, 15 ans et
        plus"` -- ça permet à `LookupStructure` de retrouver directement "le taux
        féminin toutes catégories confondues" par un simple label, sans avoir besoin de
        deviner quels libellés représentent un agrégat (voir son docstring, section
        "Ventilation"). Une ligne où TOUTES les dimensions sont à leur modalité "total"
        obtient `region=None`, cohérent avec la convention déjà utilisée pour les
        indicateurs sans ventilation du tout.
        """
        code = indicateur_json["code"]
        nom = indicateur_json["label"].strip()
        # `dict.get(cle, defaut)` ne retombe sur `defaut` que si la clé est ABSENTE.
        # Or l'API renvoie parfois explicitement `null` pour "dimensions" (indicateur
        # sans ventilation, ex. I2790 "Taux d'urbanisation") — la clé existe, sa valeur
        # est None, donc `.get("dimensions", [])` renvoie None et non []. D'où le
        # `or` après chaque `.get(...)` ci-dessous : il rattrape aussi bien la clé
        # absente que la clé présente avec une valeur null.
        unite = (indicateur_json.get("metaData") or {}).get("unit")
        periodes_valides = set(indicateur_json.get("periods") or [])

        # id de modalité -> label, toutes dimensions confondues (une seule table de
        # correspondance suffit : les id de modalité sont uniques par indicateur).
        # `ids_agregat` retient les modalités marquées "total": true par l'API, une par
        # dimension -- exclues de `region` (voir docstring ci-dessus).
        labels_modalite: dict[int, str] = {}
        ids_agregat: set[int] = set()
        for dimension in indicateur_json.get("dimensions") or []:
            for modalite in dimension.get("modalites") or []:
                labels_modalite[modalite["id"]] = modalite["label"].strip()
                if modalite.get("total"):
                    ids_agregat.add(modalite["id"])

        indicateurs: list[Indicateur] = []
        for cle, entree in (indicateur_json.get("data") or {}).items():
            valeur_brute = entree.get("value")
            if valeur_brute in (None, "", "ND", "NS"):
                continue
            try:
                valeur = float(str(valeur_brute).replace(",", "."))
            except ValueError:
                continue

            # Le prefixe (ids de modalite) et la periode ne sont separes que par le
            # DERNIER "_" -- rsplit(1) plutot que split, pour ne pas casser sur un "_"
            # qui apparaitrait a l'interieur du prefixe (jamais observe en reel, mais
            # plus sur que de supposer un seul "_" dans la cle entiere).
            if "_" in cle:
                prefixe, periode = cle.rsplit("_", 1)
            else:
                prefixe, periode = "", cle
            if periode not in periodes_valides:
                continue  # clé de forme inattendue : on ignore plutôt que de mal l'interpréter

            # Ids de modalite joints par un POINT a l'interieur du prefixe (ex.
            # "11.14.21" pour trois dimensions croisees) -- jamais par "_".
            ids_modalite = prefixe.split(".") if prefixe else []
            labels = [
                labels_modalite[int(mid)]
                for mid in ids_modalite
                if mid.isdigit() and int(mid) in labels_modalite and int(mid) not in ids_agregat
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
        """Construit le `Document` synthétique associé à un indicateur BDS (voir ADR 0004 :
        `type="api"`, `url` = fiche BDS, `titre` = libellé de l'indicateur). Sert de
        source citable pour la traçabilité (NF3), même si aucun fichier n'a réellement
        été téléchargé.
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
