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
5. Corrigé le 31/08 (bug réel observé en conditions réelles, voir JOURNAL.md) : certains
   indicateurs (ex. "Taux de chômage selon le Milieu, le sexe et le groupe d'âges")
   publient À LA FOIS des lignes ventilées ET une vraie ligne agrégée nationale
   (region IS NULL). Le point 3 ci-dessus ne comparait qu'entre combinaisons ventilées
   -- pour une question sans dimension demandée ("taux de chômage" seul), plusieurs
   combinaisons à un seul label (Urbain, Rural, Masculin, Féminin...) se retrouvaient à
   égalité (même score) et étaient donc refusées comme ambiguës, alors que la ligne
   agrégée (la vraie réponse attendue) existait juste à côté et n'était jamais
   considérée. `rechercher_indicateur` détecte maintenant l'existence de cette ligne
   agrégée et la signale à `_resoudre_ventilation` via `ligne_agregee_existe` : quand
   aucune dimension n'est demandée, cette ligne est ajoutée comme candidate avec 0
   label en trop -- elle l'emporte donc toujours sur les combinaisons ventilées (qui
   ont forcément au moins 1 label), sans risque de nouvelle ambiguïté.

Limite qui reste réelle après ce correctif : la qualité de la réponse dépend de ce que
l'API BDS publie vraiment. Si un indicateur ne publie que des lignes pleinement croisées
(ex. sexe x milieu x âge toujours ensemble, jamais de ligne "femmes, tous milieux, tous
âges"), la règle de refus ci-dessus s'applique et LookupStructure renvoie None -- ce
n'est plus un mauvais chiffre silencieux, mais ça peut rester "je ne sais pas" là où on
espérait un chiffre exact. Seule une inspection des vraies données (re-belancer
`scripts/preremplir_indicateurs_bds.py`) dira, indicateur par indicateur, si ce cas se
présente.

Periodes projetees vs periodes reelles -- corrige le 23/08 (bug observe en conditions
reelles, voir JOURNAL.md) :

Certains indicateurs BDS (ex. "Population du Maroc par annee civile ... 1960-2050")
publient une serie qui melange donnees observees et projections futures dans la meme
serie, sans distinction explicite dans les donnees renvoyees par l'API. Quand aucune
annee n'est demandee dans la question, `rechercher_indicateur` prenait jusqu'ici
`ORDER BY periode DESC LIMIT 1` sans filtre -- ce qui renvoyait la ligne 2050 (la plus
grande chaine, donc "la plus recente" au sens du tri) pour une question comme
"population de maroc", presentant une projection a 24 ans comme la valeur actuelle.
Corrige en excluant les periodes posterieures a l'annee en cours de la comparaison
DESC quand aucune annee n'est explicitement demandee -- une annee explicitement
demandee (meme future, ex. "population en 2050") reste servie normalement, seul le
comportement PAR DEFAUT change.

Statut : implémenté, testé avec une vraie base SQLite temporaire.
"""
from __future__ import annotations

import datetime
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
#
# "il" ajouté le 03/09 (bug réel trouvé en construisant le jeu de test de fiabilité,
# voir JOURNAL.md) : "combien de chômeurs y a-t-il au Maroc ?" ne matchait plus
# "Effectif des chômeurs" -- le token "il" (issu de "a-t-il") créait une fausse égalité
# de score avec d'autres indicateurs sans rapport (ex. "Espérance de vie...") qui
# partagent par hasard un token bruit d'une seule lettre. Voir aussi `_tokeniser`
# ci-dessous, qui filtre désormais tous les tokens d'une seule lettre ("a", "y", "t"),
# même cause racine.
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
            # Corrige le 31/08 (bug reel observe en conditions reelles, voir
            # JOURNAL.md) : certains indicateurs (ex. I4001, "Taux de chomage selon le
            # Milieu...") ont A LA FOIS des lignes ventilees ET une ligne agregee
            # nationale (region IS NULL). Sans le savoir, _resoudre_ventilation ne
            # cherchait qu'entre les combinaisons ventilees -- pour une question sans
            # dimension demandee ("taux de chomage" seul), plusieurs combinaisons a un
            # seul label (Urbain, Rural, Masculin, Feminin...) etaient a egalite, donc
            # refusees comme ambigues, alors que la ligne agregee (la vraie reponse
            # attendue) existait juste a cote. On signale maintenant son existence a
            # _resoudre_ventilation, qui la traite comme un candidat a part entiere.
            ligne_agregee_existe = self._conn.execute(
                "SELECT 1 FROM indicateur WHERE nom = ? AND region IS NULL LIMIT 1", (nom,)
            ).fetchone() is not None
            region = self._resoudre_ventilation(question, valeurs_region, ligne_agregee_existe)
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
        else:
            # Aucune periode demandee explicitement -- bug reel observe en conditions
            # reelles le 23/08 (voir JOURNAL.md) : certains indicateurs BDS publient une
            # serie qui inclut des PROJECTIONS futures (ex. "Population du Maroc par
            # annee civile ... 1960-2050"). Sans ce filtre, "ORDER BY periode DESC" pour
            # une question sans annee (ex. "population de maroc") renvoyait
            # systematiquement la ligne 2050 -- la plus grande chaine, donc "la plus
            # recente" au sens du tri, mais une projection a 24 ans dans le futur
            # presentee a tort comme "la" valeur actuelle. On exclut donc les periodes
            # posterieures a l'annee en cours avant de prendre la plus recente restante
            # -- une question sans annee explicite demande la derniere valeur REELLE
            # connue, jamais une projection.
            annee_courante = datetime.date.today().year
            requete += " AND CAST(SUBSTR(periode, 1, 4) AS INTEGER) <= ?"
            parametres.append(annee_courante)

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
        match ambigu : si plusieurs noms sont a egalite sur le meilleur score, on
        renvoie None plutot que de trancher au hasard -- le Routeur bascule alors sur
        RetrievalReranker (voir scripts/poser_question.py), plus honnete qu'une valeur
        chiffree associee au mauvais indicateur. Un score SANS ambiguite (un seul nom
        candidat, ex. correspondance sur un mot distinctif comme "urbanisation") reste
        accepte, quel que soit le score.

        Corrige le 30/08 (bug reel observe en conditions reelles, voir JOURNAL.md) : le
        refus d'ambiguite ne se declenchait auparavant que si le score maximal etait <= 1
        (pense pour le seul cas "taux" partage par presque tout le monde). Une question
        reformulee de travers ("...taux de chomage... Recensement General de l'Habitat et
        de la Population (RGPH)...") a matche a EGALITE (score 2) "Taux de chomage..." ET
        "Population du Maroc...", deux indicateurs totalement sans rapport -- le code a
        alors choisi silencieusement le premier insere en base au lieu de refuser.

        Premiere version du correctif (refuser TOUTE egalite, sans condition sur le
        score) trop large : casse "Quel est le taux de chômage actuel ?", qui matche a
        egalite (score 2, {taux, chomage}) "Taux de chômage selon le Milieu..." ET "Taux
        de chômage par sexe et region" -- ces deux-la ne sont PAS des sujets sans rapport,
        seulement deux ventilations du MEME indicateur (meme mots exacts responsables du
        score : {taux, chomage} pour les deux). Le vrai signal d'un risque reel n'est pas
        "il y a une egalite", mais "l'egalite repose sur des mots DIFFERENTS selon le
        candidat" -- {taux, chomage} pour les uns, {population, maroc} pour l'autre dans
        le cas RGPH. D'ou la regle a deux etages ci-dessous : un score <= 1 partage par
        plusieurs candidats reste refuse quels que soient les mots (signal trop faible,
        cas "taux" seul) ; un score > 1 partage n'est refuse que si les candidats a
        egalite ne partagent pas tous exactement le MEME ensemble de mots correspondants
        (signe de sujets reellement distincts, pas de simples variantes/ventilations).
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
                return None  # ambigu : egalite via des mots differents -> sujets reellement distincts

        return meilleurs_noms[0]

    @staticmethod
    def _tokeniser(texte: str) -> set[str]:
        """Corrige le 03/09 : les tokens d'une seule lettre ("a", "y", "t" -- issus par
        exemple de contractions comme "a-t-il") sont désormais exclus au même titre que
        MOTS_OUTILS. Un token d'une lettre n'a jamais de valeur discriminante pour
        identifier un indicateur, mais peut créer une fausse égalité de score avec un
        indicateur sans rapport qui le contient par hasard (voir MOTS_OUTILS, note
        "il" ajouté le 03/09, même bug réel)."""
        tokens = re.findall(r"\w+", _normaliser_accents(texte.lower()))
        return {t for t in tokens if t not in MOTS_OUTILS and len(t) > 1}

    @classmethod
    def _resoudre_ventilation(
        cls, question: str, valeurs_region: list[str], ligne_agregee_existe: bool = False,
    ) -> object:
        """Choisit, parmi les combinaisons de labels reellement presentes dans
        `valeurs_region` (chaines brutes "label1, label2, ..."), celle qui correspond
        le mieux a ce que la question demande explicitement. Voir le docstring de
        module (section "Ventilation") pour l'algorithme complet.

        `ligne_agregee_existe` (ajoute le 31/08, bug reel voir JOURNAL.md) : signale
        qu'une ligne agregee nationale (region IS NULL) existe AUSSI pour cet
        indicateur, en plus des lignes ventilees de `valeurs_region`. Quand aucune
        dimension n'est demandee (`requis` vide), cette ligne agregee est alors ajoutee
        comme candidate a part entiere avec 0 label en trop -- elle gagne donc toujours
        face aux combinaisons ventilees (qui ont forcement au moins 1 label), sans
        introduire de nouvelle ambiguite possible.

        Retourne soit une valeur de `valeurs_region` telle quelle (a utiliser dans la
        clause `region IS ?`), soit `None` si c'est la ligne agregee qui l'emporte, soit
        la sentinelle `_AUCUNE_VENTILATION_FIABLE` si rien ne peut etre choisi sans
        risquer un sous-groupe errone.
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
            # 0 label en trop par construction : ne peut jamais etre battue par une
            # combinaison ventilee (qui a toujours >= 1 label), donc jamais de risque
            # d'egalite introduit ici -- voir docstring de la methode.
            candidats.append((0, 0, None))

        if not candidats:
            return _AUCUNE_VENTILATION_FIABLE

        candidats.sort(key=lambda c: (c[0], c[1]))
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
