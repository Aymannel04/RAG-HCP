"""
Module ConstructeurIndicateurs — module 4 de l'architecture.
Rôle : structurer les indicateurs chiffrés en lignes prêtes pour la table `indicateur`.

Deux sources possibles, voir ADR 0004 (docs/adr/0004-api-bds-pour-les-indicateurs.md) et
son complément (docs/complement_conception_bds.pdf) :
- `structurer_depuis_bds` : source primaire pour Économie / Marché du travail / Population,
  à partir d'un indicateur récupéré via `src/bds_client.py`.
- `structurer` : repli PDF/XLSX pour les publications hors catalogue BDS. Reconnaît un
  motif précis rencontré en conditions réelles (ex. "Principaux indicateurs
  trimestriels rétropolés..., méthodologie EMO") plutôt que d'essayer d'interpréter un
  tableau quelconque : un classeur XLSX qui contient à la fois (a) une feuille
  dictionnaire à 3 colonnes "Code" / "Nom" / "Unité" et (b) une feuille de données au
  format large où chaque colonne est un code du dictionnaire et chaque ligne une
  période. Ce n'est pas une tentative de couvrir tout PDF/XLSX imaginable (portée
  volontairement restreinte) : si ce motif n'est pas reconnu, `structurer` renvoie une
  liste vide plutôt que d'inventer une interprétation, ce qui la rend sûre à appeler
  systématiquement dans le pipeline d'indexation, quel que soit le document.

  Généralisation à tout Excel du HCP envisagée puis abandonnée après vérification
  concrète (voir JOURNAL.md, 03/09) : il n'existe pas un format Excel unique chez le
  HCP. Ex. l'"Annuaire Statistique du Maroc" est une archive de 23 fichiers x jusqu'à
  34 feuilles, mise en page bilingue FR/AR pour l'impression, sans dictionnaire ni
  structure programmatique -- rien à voir avec le motif ci-dessus. Écrire un parseur
  générique universel risquerait une mauvaise lecture silencieuse sur ces formats,
  contraire au principe fondateur du projet (ADR 0001). Seul le format EMO est donc
  reconnu pour l'instant ; les autres renvoient [] plutôt qu'une tentative risquée.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timezone

from .models import Document, Indicateur

Tableau = list[list[str]]


def _normaliser(texte: str) -> str:
    forme_decomposee = unicodedata.normalize("NFD", texte)
    return "".join(c for c in forme_decomposee if unicodedata.category(c) != "Mn").strip().lower()


class ConstructeurIndicateurs:
    """Transforme des données chiffrées brutes (API BDS ou tableaux PDF/XLSX) en
    `Indicateur` structurés, prêts à insérer dans la table `indicateur`."""

    def structurer(self, id_document: int, tableaux: list[Tableau]) -> list[Indicateur]:
        """Repli PDF/XLSX : voir docstring de module pour le motif reconnu (dictionnaire
        Code/Nom/Unité + table de données au format large). Renvoie [] si ce motif
        n'est pas identifié dans `tableaux` -- jamais d'exception, jamais d'invention.

        Convention observée pour dériver la ventilation : le "Nom" du dictionnaire
        porte la dimension en suffixe après une virgule quand la colonne est ventilée
        (ex. "Taux de chômage strict, Urbain"), et rien quand c'est l'agrégat (ex.
        "Taux de chômage strict" seul). On sépare donc `nom`/`region` sur la DERNIÈRE
        virgule du "Nom" -- même convention `nom` stable / `region` variable
        qu'utilise `structurer_depuis_bds`, ce qui permet à `LookupStructure` de
        fonctionner sans distinction entre les deux sources.
        """
        dictionnaire, index_dictionnaire = self._extraire_dictionnaire(tableaux)
        if dictionnaire is None:
            return []

        donnees = self._trouver_table_donnees(tableaux, index_dictionnaire, dictionnaire)
        if donnees is None:
            return []

        entete = donnees[0]
        index_annee = self._trouver_colonne_par_nom(entete, dictionnaire, {"annee"})
        index_trimestre = self._trouver_colonne_par_nom(entete, dictionnaire, {"trimestre"})
        if index_annee is None:
            return []  # pas de colonne de periode identifiable : motif non reconnu

        indicateurs: list[Indicateur] = []
        for ligne in donnees[1:]:
            if index_annee >= len(ligne):
                continue
            annee = ligne[index_annee].strip()
            if not annee:
                continue
            trimestre = ""
            if index_trimestre is not None and index_trimestre < len(ligne):
                trimestre = ligne[index_trimestre].strip()
            periode = f"{annee}T{trimestre}" if trimestre else annee

            for index_colonne, code in enumerate(entete):
                if index_colonne in (index_annee, index_trimestre) or index_colonne >= len(ligne):
                    continue
                info = dictionnaire.get(code.strip())
                if info is None:
                    continue
                nom_complet, unite = info
                brut = ligne[index_colonne].strip()
                if not brut:
                    continue
                try:
                    valeur = float(brut.replace(",", "."))
                except ValueError:
                    continue

                if "," in nom_complet:
                    nom, region = (p.strip() for p in nom_complet.rsplit(",", 1))
                else:
                    nom, region = nom_complet, None

                indicateurs.append(Indicateur(
                    id_indicateur=None, nom=nom, valeur=valeur, unite=unite,
                    periode=periode, region=region, id_document=id_document, code_bds=None,
                ))

        return indicateurs

    @staticmethod
    def _extraire_dictionnaire(tableaux: list[Tableau]) -> tuple[dict[str, tuple[str, str]] | None, int | None]:
        """Repère la feuille dictionnaire (en-tête "Code"/"Nom"/"Unité", tolérant sur
        les accents/casse) et construit code -> (nom, unité)."""
        for index, tableau in enumerate(tableaux):
            if not tableau or len(tableau[0]) < 3:
                continue
            if [_normaliser(c) for c in tableau[0][:3]] != ["code", "nom", "unite"]:
                continue
            dictionnaire: dict[str, tuple[str, str]] = {}
            for ligne in tableau[1:]:
                if len(ligne) < 2:
                    continue
                code, nom = ligne[0].strip(), ligne[1].strip()
                unite = ligne[2].strip() if len(ligne) > 2 else ""
                if code and nom:
                    dictionnaire[code] = (nom, unite or None)
            if dictionnaire:
                return dictionnaire, index
        return None, None

    @staticmethod
    def _trouver_table_donnees(
        tableaux: list[Tableau], index_dictionnaire: int, dictionnaire: dict[str, tuple[str, str]],
    ) -> Tableau | None:
        """Parmi les autres tableaux, choisit celui dont le plus de colonnes
        correspondent à des codes connus du dictionnaire -- au moins la moitié de ses
        colonnes, sinon on considère qu'aucune table de données fiable n'a été
        trouvée plutôt que de mal interpréter un tableau sans rapport (ex. la feuille
        "Avis aux utilisateurs", une simple note de bas de page)."""
        meilleure: Tableau | None = None
        meilleur_score = 0
        for index, tableau in enumerate(tableaux):
            if index == index_dictionnaire or len(tableau) < 2:
                continue
            score = sum(1 for code in tableau[0] if code.strip() in dictionnaire)
            if score > meilleur_score:
                meilleur_score = score
                meilleure = tableau
        if meilleure is not None and meilleur_score >= len(meilleure[0]) / 2:
            return meilleure
        return None

    @staticmethod
    def _trouver_colonne_par_nom(
        entete: list[str], dictionnaire: dict[str, tuple[str, str]], noms_cibles_normalises: set[str],
    ) -> int | None:
        for index, code in enumerate(entete):
            info = dictionnaire.get(code.strip())
            if info and _normaliser(info[0]) in noms_cibles_normalises:
                return index
        return None

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
