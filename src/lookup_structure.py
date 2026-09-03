"""
Module LookupStructure — module 7 de l'architecture.
Rôle : requête directe et exacte sur la table `indicateur`, dans le cas d'une
question chiffrée. C'est ce module qui élimine le risque d'hallucination sur les
chiffres officiels : aucune génération libre n'intervient ici, seulement une requête
SQL exacte sur des données déjà en base (pré-remplies par
scripts/preremplir_indicateurs_bds.py, ADR 0004).

Décisions d'implémentation :

- Correspondance par recouvrement de tokens entre la question et les valeurs distinctes
  de `indicateur.nom` (même famille de technique que la tokenisation BM25 de
  `IndexeurTexte._tokeniser`) : le nom en base est la vraie chaîne renvoyée par l'API
  BDS (ex. "Taux de chômage selon le Milieu, le sexe et le groupe d'âges"), jamais
  formulée comme une question -- une correspondance exacte ou par sous-chaîne
  échouerait presque toujours. Une petite liste de mots-outils français est exclue du
  calcul (sinon "le", "de", "est" gonfleraient artificiellement le score de n'importe
  quel indicateur).
- Aucun appel LLM : une requête structurée n'en a pas besoin.
- Période extraite par correspondance simple (année/trimestre explicite) plutôt que par
  NER -- limite connue, acceptable vu le nombre restreint d'indicateurs curés.

Ventilation (colonne `region`) :

La colonne `region` ne contient pas que des noms de région administrative : c'est le
champ générique où `ConstructeurIndicateurs.structurer_depuis_bds` stocke la
concaténation (", ".join) des labels de TOUTES les modalités de ventilation renvoyées
par l'API BDS pour une ligne donnée -- selon l'indicateur, ça peut être un milieu
(Urbain/Rural), un sexe (Masculin/Féminin), un niveau de diplôme, une branche
d'activité, une vraie région administrative, ou plusieurs de ces dimensions croisées à
la fois (ex. "Masculin, Urbain").

Algorithme (générique par catégorie de dimension, voir `SYNONYMES_DIMENSIONS`) :

1. Chaque valeur distincte de `region` pour l'indicateur ciblé est éclatée en labels
   individuels (split sur ", ").
2. Les labels explicitement demandés dans la question sont détectés soit via
   `SYNONYMES_DIMENSIONS` (ex. "femmes" -> "Féminin"), soit par correspondance littérale
   directe du label lui-même (couvre les régions administratives et tout autre libellé
   BDS non couvert par un synonyme).
3. Parmi les combinaisons de labels qui contiennent AU MOINS tous les labels demandés,
   on choisit celle qui a le MOINS de labels "en trop" non-agrégat (voir
   `LABELS_AGREGAT` -- "Total"/"National"/"Ensemble", utilisés de façon incohérente
   selon l'indicateur dans les données BDS réelles). En cas d'égalité entre plusieurs
   combinaisons aussi précises l'une que l'autre, on refuse de trancher (même
   philosophie que `_meilleur_nom_correspondant` : mieux vaut renvoyer None et laisser
   le Routeur basculer sur RetrievalReranker qu'associer la question à un sous-groupe
   arbitraire).
4. Si aucune dimension n'est demandée mais qu'il n'existe aucune ligne region IS NULL
   pour cet indicateur (ex. "Structure des actifs occupés", ventilée uniquement par
   diplôme), la même logique s'applique avec un ensemble de labels requis vide : elle
   cherche une combinaison composée uniquement de labels agrégat, et refuse (None) si
   aucune n'existe.
5. Certains indicateurs publient À LA FOIS des lignes ventilées ET une vraie ligne
   agrégée nationale (region IS NULL). `rechercher_indicateur` détecte l'existence de
   cette ligne agrégée et la signale à `_resoudre_ventilation` via
   `ligne_agregee_existe` : quand aucune dimension n'est demandée, cette ligne est
   ajoutée comme candidate avec 0 label en trop -- elle l'emporte donc toujours sur les
   combinaisons ventilées (qui ont forcément au moins 1 label), sans risque de nouvelle
   ambiguïté.

Limite qui reste réelle : la qualité de la réponse dépend de ce que l'API BDS publie
vraiment. Si un indicateur ne publie que des lignes pleinement croisées (ex. sexe x
milieu x âge toujours ensemble, jamais de ligne "femmes, tous milieux, tous âges"), la
règle de refus ci-dessus s'applique et LookupStructure renvoie None -- ce n'est plus un
mauvais chiffre silencieux, mais ça peut rester "je ne sais pas" là où on espérait un
chiffre exact.

Périodes projetées vs périodes réelles : certains indicateurs BDS (ex. "Population du
Maroc par année civile ... 1960-2050") publient une série qui mélange données observées
et projections futures, sans distinction explicite. Quand aucune année n'est demandée,
on exclut donc les périodes postérieures à l'année en cours avant de prendre la plus
récente restante -- une année explicitement demandée (même future) reste servie
normalement, seul le comportement par défaut change.
"""
from __future__ import annotations

import datetime
import re
import sqlite3
import unicodedata
from typing import Optional

from .models import Indicateur


def _normaliser_accents(texte: str) -> str:
    """Retire les diacritiques (ex. "chômage" -> "chomage"), pour tolérer les
    questions tapées sans accents -- sans ça, "quel est le taux de chomage" sans
    accent ne correspond pas à "chômage" en base, ce qui fait basculer à tort sur
    RetrievalReranker au lieu de la réponse structurée exacte.

    Unifie aussi les variantes d'apostrophe (' typographique U+2019 vs ' simple) :
    les labels réels de l'API BDS utilisent l'apostrophe typographique (ex.
    "Industrie d'extraction"), jamais tapée ainsi au clavier standard.
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
    "sur", "dans", "actuel", "actuelle", "selon", "par", "il",
}

PATTERN_ANNEE = re.compile(r"\b((?:19|20)\d{2})\b")
PATTERN_TRIMESTRE = re.compile(r"\bT([1-4])\b", re.IGNORECASE)

# Synonymes en langage naturel -> label canonique tel qu'il apparaît réellement dans
# `indicateur.region` (voir ConstructeurIndicateurs.structurer_depuis_bds). Organisé par
# catégorie de dimension pour la lisibilité/maintenance ; fusionné en un seul dict
# normalisé (clés sans accents/minuscules) au chargement du module -- voir
# `_fusionner_normalise`.
#
# Volontairement incomplet sur les régions administratives et les groupes d'âge : les
# régions se matchent déjà littéralement (label BDS = nom propre, pas de synonyme
# nécessaire) et les tranches d'âge BDS n'ont pas encore de libellé confirmé en
# conditions réelles pour les indicateurs curés.
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

# Labels réels confirmés sur les vraies données (indicateur "Valeurs ajoutées par
# branche d'activité").
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
# pour Population du Maroc par année civile). Comparaison faite après normalisation
# accents/casse.
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
        RetrievalReranker).
        """
        # GROUP BY + ORDER BY MIN(id_indicateur) plutôt qu'un simple SELECT DISTINCT :
        # rend déterministe l'ordre des noms candidats (premier indicateur inséré en
        # base gagne les cas d'égalité de score dans _meilleur_nom_correspondant),
        # plutôt que de dépendre de l'ordre non garanti d'un SELECT DISTINCT.
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
            # Certains indicateurs ont à la fois des lignes ventilées ET une ligne
            # agrégée nationale (region IS NULL) -- on signale son existence à
            # _resoudre_ventilation, qui la traite comme un candidat à part entière
            # (voir docstring de module, point 5).
            ligne_agregee_existe = self._conn.execute(
                "SELECT 1 FROM indicateur WHERE nom = ? AND region IS NULL LIMIT 1", (nom,)
            ).fetchone() is not None
            region = self._resoudre_ventilation(question, valeurs_region, ligne_agregee_existe)
            if region is _AUCUNE_VENTILATION_FIABLE:
                return None
        else:
            # Aucune ligne ventilée pour cet indicateur : seule la ligne agrégée
            # (region IS NULL) existe.
            region = None

        annee = self._extraire_annee(question)
        trimestre = self._extraire_trimestre(question)

        requete = "SELECT id_indicateur, nom, valeur, unite, periode, region, id_document, code_bds FROM indicateur WHERE nom = ? AND region IS ?"
        parametres: list = [nom, region]

        if annee:
            motif = f"{annee}T{trimestre}" if trimestre else f"{annee}%"
            requete += " AND periode LIKE ?"
            parametres.append(motif)
        else:
            # Aucune période demandée explicitement : certains indicateurs BDS publient
            # une série qui inclut des projections futures (voir docstring de module).
            # On exclut donc les périodes postérieures à l'année en cours avant de
            # prendre la plus récente restante.
            annee_courante = datetime.date.today().year
            requete += " AND CAST(SUBSTR(periode, 1, 4) AS INTEGER) <= ?"
            parametres.append(annee_courante)

        requete += " ORDER BY periode DESC LIMIT 1"

        ligne = self._conn.execute(requete, parametres).fetchone()
        if ligne is None and annee:
            # Repli : la période demandée n'est pas couverte -- on garde la ventilation
            # déjà résolue (region) intacte et on prend juste la période la plus
            # récente disponible pour CETTE ventilation, plutôt que d'abandonner le
            # filtre region (qui pourrait alors renvoyer un tout autre sous-groupe).
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
        décrocher le même score (1) à quasiment tous les indicateurs de la base, et un
        simple tie-break (premier inséré) choisirait arbitrairement un indicateur non
        pertinent avec une réponse présentée comme sûre d'elle. D'où le refus de tout
        match ambigu : si plusieurs noms sont à égalité sur le meilleur score, on
        renvoie None plutôt que de trancher au hasard -- le Routeur bascule alors sur
        RetrievalReranker, plus honnête qu'une valeur chiffrée associée au mauvais
        indicateur. Un score sans ambiguïté (un seul nom candidat) reste accepté, quel
        que soit le score.

        Règle à deux étages pour les cas d'égalité, distinguant un vrai risque
        (candidats sans rapport) d'une simple variante/ventilation du même indicateur :
        un score <= 1 partagé par plusieurs candidats reste refusé quels que soient les
        mots (signal trop faible, cas "taux" seul en commun) ; un score > 1 partagé
        n'est refusé que si les candidats à égalité ne partagent pas tous exactement le
        même ensemble de mots correspondants (signe de sujets réellement distincts, pas
        de simples ventilations du même indicateur -- ex. "Taux de chômage selon le
        Milieu..." et "Taux de chômage par sexe et région" partagent {taux, chomage} et
        restent acceptés, alors qu'un même score obtenu via des mots différents selon
        le candidat signale deux sujets sans rapport).
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
        if len(meilleurs_noms) > 1:
            if meilleur_score <= 1:
                return None  # ambigu : signal trop faible (typiquement "taux" seul en commun)
            mots_correspondants = {
                frozenset(tokens_question & cls._tokeniser(nom)) for nom in meilleurs_noms
            }
            if len(mots_correspondants) > 1:
                return None  # ambigu : égalité via des mots différents -> sujets réellement distincts

        return meilleurs_noms[0]

    @staticmethod
    def _tokeniser(texte: str) -> set[str]:
        """Découpe en tokens en excluant MOTS_OUTILS et les tokens d'une seule lettre
        ("a", "y", "t" -- issus par exemple de contractions comme "a-t-il"), qui n'ont
        jamais de valeur discriminante pour identifier un indicateur mais peuvent créer
        une fausse égalité de score avec un indicateur sans rapport qui les contient
        par hasard."""
        tokens = re.findall(r"\w+", _normaliser_accents(texte.lower()))
        return {t for t in tokens if t not in MOTS_OUTILS and len(t) > 1}

    @classmethod
    def _resoudre_ventilation(
        cls, question: str, valeurs_region: list[str], ligne_agregee_existe: bool = False,
    ) -> object:
        """Choisit, parmi les combinaisons de labels réellement présentes dans
        `valeurs_region` (chaînes brutes "label1, label2, ..."), celle qui correspond
        le mieux à ce que la question demande explicitement. Voir le docstring de
        module (section "Ventilation") pour l'algorithme complet.

        `ligne_agregee_existe` signale qu'une ligne agrégée nationale (region IS NULL)
        existe aussi pour cet indicateur, en plus des lignes ventilées de
        `valeurs_region`. Quand aucune dimension n'est demandée (`requis` vide), cette
        ligne agrégée est alors ajoutée comme candidate à part entière avec 0 label en
        trop -- elle gagne donc toujours face aux combinaisons ventilées (qui ont
        forcément au moins 1 label), sans introduire de nouvelle ambiguïté possible.

        Retourne soit une valeur de `valeurs_region` telle quelle (à utiliser dans la
        clause `region IS ?`), soit `None` si c'est la ligne agrégée qui l'emporte, soit
        la sentinelle `_AUCUNE_VENTILATION_FIABLE` si rien ne peut être choisi sans
        risquer un sous-groupe erroné.
        """
        tous_labels = {label.strip() for valeur in valeurs_region for label in valeur.split(",")}
        # Label réel (tel que stocké en base) indexé par sa forme normalisée -- les
        # labels BDS ne sont pas toujours accentués de façon cohérente (ex. "National"/
        # "Total" pour l'agrégat selon l'indicateur, "Feminin" observé sans accent sur
        # certains indicateurs). SYNONYMES_DIMENSIONS est écrit avec les accents
        # standards pour la lisibilité du code ; la correspondance se fait donc par
        # forme normalisée des deux côtés, jamais par égalité stricte de chaîne.
        labels_par_forme_normalisee = {
            _normaliser_accents(label.lower()): label for label in tous_labels
        }
        signal = _normaliser_accents(question.lower())

        requis: set[str] = set()
        for terme_normalise, canonique in SYNONYMES_DIMENSIONS.items():
            label_reel = labels_par_forme_normalisee.get(_normaliser_accents(canonique.lower()))
            if label_reel and re.search(rf"\b{re.escape(terme_normalise)}\b", signal):
                requis.add(label_reel)
        # Repli littéral : couvre les régions administratives et tout autre libellé BDS
        # sans synonyme connu (ex. "PIB hors agriculture"), appliqué label par label
        # plutôt qu'à la chaîne region entière (qui ne matche jamais une fois plusieurs
        # dimensions croisées).
        for label in tous_labels:
            if label in requis:
                continue
            label_normalise = _normaliser_accents(label.lower())
            if label_normalise and re.search(rf"\b{re.escape(label_normalise)}\b", signal):
                requis.add(label)

        candidats: list[tuple[int, int, object]] = []
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

        if not requis and ligne_agregee_existe:
            # 0 label en trop par construction : ne peut jamais être battue par une
            # combinaison ventilée (qui a toujours >= 1 label), donc jamais de risque
            # d'égalité introduit ici.
            candidats.append((0, 0, None))

        if not candidats:
            return _AUCUNE_VENTILATION_FIABLE

        candidats.sort(key=lambda c: (c[0], c[1]))
        if len(candidats) > 1 and candidats[0][:2] == candidats[1][:2]:
            return _AUCUNE_VENTILATION_FIABLE  # ambigu : plusieurs combinaisons aussi précises

        return candidats[0][2]

    @staticmethod
    def _extraire_annee(question: str) -> Optional[str]:
        m = PATTERN_ANNEE.search(question)
        return m.group(1) if m else None

    @staticmethod
    def _extraire_trimestre(question: str) -> Optional[str]:
        m = PATTERN_TRIMESTRE.search(question)
        return m.group(1) if m else None
