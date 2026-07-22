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
- Région et période extraites de la question par un même principe de correspondance
  simple (la région doit apparaître littéralement dans la question ; la période cherche
  une année/trimestre explicite) plutôt que par NER -- limite connue, documentée dans
  TODO.md, acceptable pour la V1 vu le nombre restreint d'indicateurs curés (une vingtaine,
  voir data/indicateurs_cures.py).

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
    structuree exacte, contraire au principe fondateur ADR 0001)."""
    forme_decomposee = unicodedata.normalize("NFD", texte)
    return "".join(c for c in forme_decomposee if unicodedata.category(c) != "Mn")

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


class LookupStructure:
    """Récupère un indicateur exact par requête directe sur la base structurée."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def rechercher_indicateur(self, question: str) -> Optional[Indicateur]:
        """Identifie l'indicateur demandé (nom, période, région éventuelle) et
        exécute une requête SQL exacte sur la table `indicateur`. Retourne None
        si aucun indicateur correspondant n'est trouvé (le Routeur doit alors
        basculer sur RetrievalReranker, voir docs/fiche_cadrage_v4.pdf section 8.5).
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

        region = self._extraire_region(question, nom)
        annee = self._extraire_annee(question)
        trimestre = self._extraire_trimestre(question)

        requete = "SELECT id_indicateur, nom, valeur, unite, periode, region, id_document, code_bds FROM indicateur WHERE nom = ?"
        parametres: list = [nom]

        requete += " AND region IS ?"
        parametres.append(region)

        if annee:
            motif = f"{annee}T{trimestre}" if trimestre else f"{annee}%"
            requete += " AND periode LIKE ?"
            parametres.append(motif)

        requete += " ORDER BY periode DESC LIMIT 1"

        ligne = self._conn.execute(requete, parametres).fetchone()
        if ligne is None and (annee or region):
            # Repli : le filtre annee/region exact n'a rien donne (ex. periode
            # demandee non couverte par les donnees BDS) -- mieux vaut renvoyer la
            # derniere valeur connue de l'indicateur que rien du tout, quitte a ce
            # que Generateur precise la periode reellement utilisee dans sa reponse.
            ligne = self._conn.execute(
                "SELECT id_indicateur, nom, valeur, unite, periode, region, id_document, code_bds "
                "FROM indicateur WHERE nom = ? ORDER BY periode DESC LIMIT 1",
                (nom,),
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

    def _extraire_region(self, question: str, nom: str) -> Optional[str]:
        """Cherche si une des régions connues pour cet indicateur apparaît
        littéralement dans la question (comparaison insensible aux accents, même
        raison que `_tokeniser`) ; sinon retombe sur la ligne nationale (region IS
        NULL, convention déjà utilisée par ConstructeurIndicateurs pour les
        indicateurs sans ventilation géographique)."""
        signal = _normaliser_accents(question.lower())
        regions = self._conn.execute(
            "SELECT DISTINCT region FROM indicateur WHERE nom = ? AND region IS NOT NULL",
            (nom,),
        ).fetchall()
        for (region,) in regions:
            if region and _normaliser_accents(region.lower()) in signal:
                return region
        return None

    @staticmethod
    def _extraire_annee(question: str) -> Optional[str]:
        m = PATTERN_ANNEE.search(question)
        return m.group(1) if m else None

    @staticmethod
    def _extraire_trimestre(question: str) -> Optional[str]:
        m = PATTERN_TRIMESTRE.search(question)
        return m.group(1) if m else None
