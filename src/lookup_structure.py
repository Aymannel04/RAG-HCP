"""
Module LookupStructure — module 7 de l'architecture.
Rôle : requête directe et exacte sur la table `indicateur`, dans le cas d'une
question chiffrée (voir docs/conception_uml_v3.pdf, figure 5).
C'est ce module qui élimine le risque d'hallucination sur les chiffres officiels
(voir docs/fiche_cadrage_v4.pdf, section 9 - analyse des risques) : aucune génération
libre n'intervient ici, seulement une requête SQL exacte sur des données déjà en base
(pré-remplies par scripts/preremplir_indicateurs_bds.py, ADR 0004).

Décisions d'implémentation, aucune fixée dans les documents de conception (qui décrivent
la responsabilité du module mais pas l'algorithme de correspondance question -> indicateur) :

- Correspondance par recouvrement de tokens entre la question et les valeurs distinctes
  de `indicateur.nom` déjà en base (même famille de technique que la tokenisation BM25
  de `IndexeurTexte._tokeniser`, réutilisée ici) : le nom en base est la vraie chaîne
  renvoyée par l'API BDS (ex. "Taux de chômage selon le Milieu, le sexe et le groupe
  d'âges", voir `ConstructeurIndicateurs.structurer_depuis_bds`), donc jamais formulée
  comme une question -- une correspondance exacte ou par sous-chaîne échouerait presque
  toujours. Une petite liste de mots-outils français est exclue du calcul (sinon "le",
  "de", "est" gonfleraient artificiellement le score de n'importe quel indicateur).
- Aucun appel LLM : cohérent avec la même décision prise pour `Routeur` (voir son
  docstring) -- le choix du LLM de génération reste ouvert (ADR 0002), et une requête
  structurée n'en a de toute façon pas besoin.
- Période extraite de la question par un même principe de correspondance simple (une
  année/trimestre explicite) plutôt que par NER -- limite connue, documentée dans
  TODO.md, acceptable pour la V1 vu le nombre restreint d'indicateurs curés (une
  vingtaine, voir data/indicateurs_cures.py).

Ventilation (colonne `region`) — résolu le 28/07 (limite documentée dans TODO.md depuis
le 21/07) :

La colonne `region` ne contient pas que des noms de région administrative : c'est le
champ générique où `ConstructeurIndicateurs.structurer_depuis_bds` stocke la
concaténation (", ".join) des labels de TOUTES les modalités de ventilation renvoyées
par l'API BDS pour une ligne donnée -- selon l'indicateur, ça peut être un milieu
(Urbain/Rural), un sexe (Masculin/Féminin), un niveau de diplôme (Sans diplôme/Niveau
moyen/Niveau supérieur), une branche d'activité (Agriculture, Commerce, ...), une vraie
région administrative, ou plusieurs de ces dimensions croisées à la fois (ex. "Masculin,
Urbain"). La première version de `_extraire_region` ne gérait que le cas région
administrative (comparaison littérale de la question contre la chaîne région entière) --
d'où la limite : une question comme "taux de chômage pour les femmes" ne correspondait
jamais littéralement à un `region` du type "Masculin, Urbain, 15-24 ans", et l'algorithme
retombait sur la ligne agrégée (region IS NULL) sans le signaler.

Nouvelle approche, générique par catégorie de dimension plutôt que limitée à
sexe/milieu/âge (voir `SYNONYMES_DIMENSIONS`, couvre aussi niveau de diplôme et branche
d'activité économique, les deux autres dimensions réellement rencontrées dans les
indicateurs curés -- voir data/indicateurs_cures.py) :

1. Chaque valeur distincte de `region` pour l'indicateur ciblé est éclatée en labels
   individuels (split sur ", ").
2. Les labels explicitement demandés dans la question sont détectés soit via
   `SYNONYMES_DIMENSIONS` (ex. "femmes" -> "Féminin"), soit par correspondance littérale
   directe du label lui-même (couvre les régions administratives et tout autre libellé
   BDS non couvert par un synonyme, ex. "PIB hors agriculture").
3. Parmi les combinaisons de labels qui contiennent AU MOINS tous les labels demandés,
   on choisit celle qui a le MOINS de labels "en trop" non-agrégat (voir
   `LABELS_AGREGAT` -- "Total"/"National"/"Ensemble", utilisés de façon incohérente
   selon l'indicateur dans les données BDS réelles). En cas d'égalité entre plusieurs
   combinaisons aussi précises l'une que l'autre, on refuse de trancher (même philosophie
   que `_meilleur_nom_correspondant` : mieux vaut renvoyer None et laisser le Routeur
   basculer sur RetrievalReranker qu'associer la question à un sous-groupe arbitraire).
   C'est exactement le risque identifié dans TODO.md ("un mapping de synonymes naïf
   risquerait de renvoyer un sous-groupe très spécifique... maquillé en taux féminin
   général") -- ce refus explicite est la garde-fou.
4. Si aucune dimension n'est demandée mais qu'il n'existe aucune ligne region IS NULL
   pour cet indicateur (ex. "Structure des actifs occupés", ventilée uniquement par
   diplôme, sans ligne agrégée toutes catégories confondues), la même logique
   s'applique avec un ensemble de labels requis vide : elle cherche une combinaison
   composée uniquement de labels agrégat, et refuse (None) si aucune n'existe --
   corrige un bug latent où l'ancien code renvoyait alors une ligne arbitraire (ordre
   d'insertion) présentée comme si elle couvrait toute la population.

Limite qui reste réelle après ce correctif : la qualité de la réponse dépend de ce que
l'API BDS publie vraiment. Si un indicateur ne publie que des lignes pleinement croisées
(ex. sexe x milieu x âge toujours ensemble, jamais de ligne "femmes, tous milieux, tous
âges"), la règle de refus ci-dessus s'applique et LookupStructure renvoie None -- ce
n'est plus un mauvais chiffre silencieux, mais ça peut rester "je ne sais pas" là où on
espérait un chiffre exact. Seule une inspection des vraies données (re-belancer
`scripts/preremplir_indicateurs_bds.py`) dira, indicateur par indicateur, si ce cas se
présente.

Statut : implémenté, testé avec une vraie base SQLite temporaire.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from typing import Optional

from .models import Indicateur


def _normaliser_accents(texte: str) -> str:
    """Retire les diacritiques (ex. "chômage" -> "chomage"), pour tolerer les
    questions tapees sans accents -- frequent en usage reel (sans normalisation,
    "quel est le taux de chomage" sans accent ne correspond pas a "chômage" en
    base, ce qui fait basculer a tort sur RetrievalReranker au lieu de la reponse
    structuree exacte, contraire au principe fondateur ADR 0001).

    Unifie aussi les variantes d'apostrophe (' typographique U+2019 vs ' simple) :
    les labels reels de l'API BDS utilisent l'apostrophe typographique (ex.
    "Industrie d'extraction" avec U+2019), jamais tapee ainsi au clavier standard.
    """
    forme_decomposee = unicodedata.normalize("NFD", texte)
    sans_accents = "".join(c for c in forme_decomposee if unicodedata.category(c) != "Mn")
    return sans_accents.replace("’", "'")


# Mots-outils français exclus du calcul de recouvrement (voir docstring de module).
# Volontairement courte : seulement ce qui apparaît réellement dans les noms
# d'indicateurs BDS et dans des questions naturelles, pas une liste NLP complète.
MOTS_OUTILS = {
    "le", "la", "les", "l", "un", "une", "des", "de", "du", "d", "et", "en", "au", "aux",
    "est", "sont", "quel", "quelle", "quels", "quelles", "ce", "cette", "ces", "pour",
    "sur", "dans", "actuel", "actuelle", "selon", "par",
}

PATTERN_ANNEE = re.compile(r"\b((?:19|20)\d{2})\b")
PATTERN_TRIMESTRE = re.compile(r"\bT([1-4])\b", re.IGNORECASE)

# Synonymes en langage naturel -> label canonique tel qu'il apparaît réellement dans
# `indicateur.region` (voir ConstructeurIndicateurs.structurer_depuis_bds). Organisé par
# catégorie de dimension pour la lisibilité/maintenance ; fusionné en un seul dict
# normalisé (clés sans accents/minuscules) au chargement du module -- voir
# `_fusionner_normalise`. Grounded dans les labels réellement observés en base réelle
# (voir JOURNAL.md, 20-21/07) ou dans le catalogue BDS (data/bds_catalogue.json) pour
# les libellés d'indicateurs pas encore ventilés dans la base locale actuelle.
#
# Volontairement incomplet sur les régions administratives et les groupes d'âge : les
# régions se matchent déjà littéralement (label BDS = nom propre, pas de synonyme
# nécessaire) et les tranches d'âge BDS n'ont pas encore de libellé confirmé en
# conditions réelles pour les indicateurs curés (I4001, I1590) -- à compléter dès que
# `scripts/preremplir_indicateurs_bds.py` aura été relancé en réel (voir TODO.md).
_MILIEU = {
    "urbain": "Urbain", "urbaine": "Urbain", "ville": "Urbain", "villes": "Urbain",
    "citadin": "Urbain", "citadine": "Urbain",
    "rural": "Rural", "rurale": "Rural", "campagne": "Rural",
}

_SEXE = {
    "femme": "Féminin", "femmes": "Féminin", "féminin": "Féminin", "féminine": "Féminin",
    "homme": "Masculin", "hommes": "Masculin", "masculin": "Masculin",
}

_NIVEAU_DIPLOME = {
    "sans diplôme": "Sans diplôme", "non diplômé": "Sans diplôme", "non diplômés": "Sans diplôme",
    "aucun diplôme": "Sans diplôme",
    "niveau moyen": "Niveau moyen", "diplôme moyen": "Niveau moyen",
    "niveau supérieur": "Niveau supérieur", "diplôme supérieur": "Niveau supérieur",
    "diplômés du supérieur": "Niveau supérieur",
}

# Labels réels confirmés (voir requête sur hcp_rag.db, indicateur "Valeurs ajoutées par
# branche d'activité", 17 valeurs) -- I3181/ADR 0002.
_BRANCHE_ACTIVITE = {
    "agriculture": "Agriculture", "agricole": "Agriculture",
    "pêche": "Pêche",
    "industrie de transformation": "Industrie de transformation",
    "industrie manufacturière": "Industrie de transformation",
    "industrie d'extraction": "Industrie d'extraction", "industrie extractive": "Industrie d'extraction",
    "mines": "Industrie d'extraction",
    "bâtiment": "Bâtiment et travaux publics", "btp": "Bâtiment et travaux publics",
    "construction": "Bâtiment et travaux publics", "travaux publics": "Bâtiment et travaux publics",
    "commerce": "Commerce",
    "hôtellerie": "Hôtels et restaurants", "restauration": "Hôtels et restaurants",
    "tourisme": "Hôtels et restaurants", "hôtels": "Hôtels et restaurants",
    "transport": "Transports", "transports": "Transports",
    "télécommunications": "Postes et télécommunications", "poste": "Postes et télécommunications",
    "télécom": "Postes et télécommunications",
    "finance": "Activités financières et assurances", "banque": "Activités financières et assurances",
    "assurance": "Activités financières et assurances", "assurances": "Activités financières et assurances",
    "administration publique": "Administration publique générale et sécurité sociale",
    "fonction publique": "Administration publique générale et sécurité sociale",
    "éducation": "Education, santé et action sociale", "santé": "Education, santé et action sociale",
    "électricité": "Electricité et eau", "eau": "Electricité et eau",
}


def _fusionner_normalise(*dicts: dict[str, str]) -> dict[str, str]:
    fusion: dict[str, str] = {}
    for d in dicts:
        for terme, canonique in d.items():
            fusion[_normaliser_accents(terme.lower())] = canonique
    return fusion


SYNONYMES_DIMENSIONS = _fusionner_normalise(_MILIEU, _SEXE, _NIVEAU_DIPLOME, _BRANCHE_ACTIVITE)

# Labels utilisés de façon incohérente selon l'indicateur pour désigner la ligne
# agrégée/toutes-catégories-confondues (ex. "National" pour Nombre de ménages, "Total"
# pour Population du Maroc par année civile -- confirmé sur les vraies données, voir
# JOURNAL.md 21/07). Comparaison faite après normalisation accents/casse.
LABELS_AGREGAT = {"total", "national", "nationale", "ensemble"}

# Sentinelle interne : aucune combinaison de labels ne satisfait la demande sans
# ambiguïté (voir point 3 du docstring de module). Distincte de `None`, qui désigne la
# ligne agrégée `region IS NULL`.
_AUCUNE_VENTILATION_FIABLE = object()


class LookupStructure:
    """Récupère un indicateur exact par requête directe sur la base structurée."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def rechercher_indicateur(self, question: str) -> Optional[Indicateur]:
        """Identifie l'indicateur demandé (nom, période, ventilation éventuelle) et
        exécute une requête SQL exacte sur la table `indicateur`. Retourne None
        si aucun indicateur correspondant n'est trouvé, ou si la ventilation demandée
        ne peut pas être résolue de façon fiable (le Routeur doit alors basculer sur
        RetrievalReranker, voir docs/fiche_cadrage_v4.pdf section 8.5).
        """
        # GROUP BY + ORDER BY MIN(id_indicateur) plutot qu'un simple SELECT DISTINCT :
        # rend deterministe l'ordre des noms candidats (premier indicateur insere en
        # base gagne les cas d'egalite de score dans _meilleur_nom_correspondant --
        # generalement la version agregee/nationale d'un indicateur, cf.
        # data/indicateurs_cures.py, plutot qu'une ventilation plus specifique) au lieu
        # de dependre de l'ordre non garanti d'un SELECT DISTINCT.
        noms_disponibles = [
            row[0] for row in self._conn.execute(
                "SELECT nom FROM indicateur GROUP BY nom ORDER BY MIN(id_indicateur)"
            ).fetchall()
        ]
        if not noms_disponibles:
            return None

        nom = self._meilleur_nom_correspondant(question, noms_disponibles)
        if nom is None:
            return None

        valeurs_region = [
            row[0] for row in self._conn.execute(
                "SELECT DISTINCT region FROM indicateur WHERE nom = ? AND region IS NOT NULL",
                (nom,),
            ).fetchall()
        ]

        if valeurs_region:
            region = self._resoudre_ventilation(question, valeurs_region)
            if region is _AUCUNE_VENTILATION_FIABLE:
                return None
        else:
            # Aucune ligne ventilee pour cet indicateur : seule la ligne agregee
            # (region IS NULL) existe, comportement d'origine inchange.
            region = None

        annee = self._extraire_annee(question)
        trimestre = self._extraire_trimestre(question)

        requete = "SELECT id_indicateur, nom, valeur, unite, periode, region, id_document, code_bds FROM indicateur WHERE nom = ? AND region IS ?"
        parametres: list = [nom, region]

        if annee:
            motif = f"{annee}T{trimestre}" if trimestre else f"{annee}%"
            requete += " AND periode LIKE ?"
            parametres.append(motif)

        requete += " ORDER BY periode DESC LIMIT 1"

        ligne = self._conn.execute(requete, parametres).fetchone()
        if ligne is None and annee:
            # Repli : la periode demandee n'est pas couverte -- on garde la ventilation
            # deja resolue (region) intacte et on prend juste la periode la plus
            # recente disponible pour CETTE ventilation, plutot que d'abandonner le
            # filtre region (qui pourrait alors renvoyer un tout autre sous-groupe,
            # exactement le risque documente dans TODO.md).
            ligne = self._conn.execute(
                "SELECT id_indicateur, nom, valeur, unite, periode, region, id_document, code_bds "
                "FROM indicateur WHERE nom = ? AND region IS ? ORDER BY periode DESC LIMIT 1",
                (nom, region),
            ).fetchone()

        if ligne is None:
            return None

        return Indicateur(
            id_indicateur=ligne[0], nom=ligne[1], valeur=ligne[2], unite=ligne[3],
            periode=ligne[4], region=ligne[5], id_document=ligne[6], code_bds=ligne[7],
        )

    @classmethod
    def _meilleur_nom_correspondant(cls, question: str, noms_disponibles: list[str]) -> Optional[str]:
        """Trouve le nom d'indicateur le plus proche de la question par recouvrement
        de tokens, ou None si aucune correspondance n'est assez fiable.

        Presque tous les noms d'indicateurs BDS commencent par "Taux" -- avec le seul
        mot "taux" en commun, une question comme "Quel est le taux de travail ?" fait
        decrocher le meme score (1) a quasiment tous les indicateurs de la base, et un
        simple tie-break (premier insere) choisirait arbitrairement un indicateur non
        pertinent avec une reponse presentee comme sure d'elle. D'ou le refus de tout
        match ambigu : si plusieurs noms sont a egalite sur le meilleur score ET que ce
        score ne repose que sur un seul mot partage (typiquement "taux" seul), on
        renvoie None plutot que de trancher au hasard -- le Routeur bascule alors sur
        RetrievalReranker (voir scripts/poser_question.py), plus honnete qu'une valeur
        chiffree associee au mauvais indicateur. Un score de 1 SANS ambiguite (un seul
        nom candidat, ex. correspondance sur un mot distinctif comme "urbanisation")
        reste accepte.
        """
        tokens_question = cls._tokeniser(question)
        if not tokens_question:
            return None

        scores: dict[str, int] = {
            nom: len(tokens_question & cls._tokeniser(nom)) for nom in noms_disponibles
        }
        meilleur_score = max(scores.values(), default=0)
        if meilleur_score == 0:
            return None

        meilleurs_noms = [nom for nom in noms_disponibles if scores[nom] == meilleur_score]
        if len(meilleurs_noms) > 1 and meilleur_score <= 1:
            return None  # ambigu : plusieurs indicateurs a egalite sur un seul mot commun

        return meilleurs_noms[0]

    @staticmethod
    def _tokeniser(texte: str) -> set[str]:
        tokens = re.findall(r"\w+", _normaliser_accents(texte.lower()))
        return {t for t in tokens if t not in MOTS_OUTILS}

    @classmethod
    def _resoudre_ventilation(cls, question: str, valeurs_region: list[str]) -> object:
        """Choisit, parmi les combinaisons de labels reellement presentes dans
        `valeurs_region` (chaines brutes "label1, label2, ..."), celle qui correspond
        le mieux a ce que la question demande explicitement. Voir le docstring de
        module (section "Ventilation") pour l'algorithme complet.

        Retourne soit une valeur de `valeurs_region` telle quelle (a utiliser dans la
        clause `region IS ?`), soit la sentinelle `_AUCUNE_VENTILATION_FIABLE` si rien
        ne peut etre choisi sans risquer un sous-groupe errone.
        """
        tous_labels = {label.strip() for valeur in valeurs_region for label in valeur.split(",")}
        # Label reel (tel que stocke en base) indexe par sa forme normalisee -- les
        # labels BDS ne sont pas toujours accentues de facon coherente (ex. "National"/
        # "Total" pour l'agregat selon l'indicateur, "Feminin" observe SANS accent sur
        # I4001 en conditions reelles alors que le francais standard l'accentuerait).
        # SYNONYMES_DIMENSIONS est ecrit avec les accents standards pour la lisibilite
        # du code ; la correspondance se fait donc par forme normalisee des deux cotes,
        # jamais par egalite stricte de chaine.
        labels_par_forme_normalisee = {
            _normaliser_accents(label.lower()): label for label in tous_labels
        }
        signal = _normaliser_accents(question.lower())

        requis: set[str] = set()
        for terme_normalise, canonique in SYNONYMES_DIMENSIONS.items():
            label_reel = labels_par_forme_normalisee.get(_normaliser_accents(canonique.lower()))
            if label_reel and re.search(rf"\b{re.escape(terme_normalise)}\b", signal):
                requis.add(label_reel)
        # Repli litteral : couvre les regions administratives et tout autre libelle BDS
        # sans synonyme connu (ex. "PIB hors agriculture"), sur le meme principe que
        # l'ancienne _extraire_region mais applique label par label plutot qu'a la
        # chaine region entiere (qui ne matche jamais une fois plusieurs dimensions
        # croisees).
        for label in tous_labels:
            if label in requis:
                continue
            label_normalise = _normaliser_accents(label.lower())
            if label_normalise and re.search(rf"\b{re.escape(label_normalise)}\b", signal):
                requis.add(label)

        candidats: list[tuple[int, int, str]] = []
        for valeur in valeurs_region:
            labels = {label.strip() for label in valeur.split(",")}
            if not requis <= labels:
                continue
            extra = labels - requis
            extra_non_agregat = {
                label for label in extra
                if _normaliser_accents(label.lower()) not in LABELS_AGREGAT
            }
            candidats.append((len(extra_non_agregat), len(extra), valeur))

        if not candidats:
            return _AUCUNE_VENTILATION_FIABLE

        candidats.sort()
        if len(candidats) > 1 and candidats[0][:2] == candidats[1][:2]:
            return _AUCUNE_VENTILATION_FIABLE  # ambigu : plusieurs combinaisons aussi precises

        return candidats[0][2]

    @staticmethod
    def _extraire_annee(question: str) -> Optional[str]:
        m = PATTERN_ANNEE.search(question)
        return m.group(1) if m else None

    @staticmethod
    def _extraire_trimestre(question: str) -> Optional[str]:
        m = PATTERN_TRIMESTRE.search(question)
        return m.group(1) if m else None
