"""
Mesure de fiabilite sur les questions chiffrees (NF2 de la fiche de cadrage :
taux d'exactitude factuelle >= 90% sur le jeu de test, pour les questions chiffrees).

Jeu de test construit le 3 septembre 2026 (Sprint 5) : 30 questions en langage naturel
couvrant les 18 indicateurs cures (data/indicateurs_cures.py), plusieurs variantes de
ventilation (sexe, milieu, region, diplome), quelques reformulations/paraphrases, et
des cas volontairement ambigus ou hors-perimetre dont le SEUL comportement correct est
de refuser (valeur attendue = None) plutot que d'inventer.

Chaque valeur attendue a ete verifiee manuellement contre la vraie base
(data/hcp_rag.db) au moment de la construction du jeu de test, par une requete SQL
independante de la logique de resolution testee (voir JOURNAL.md, 3 septembre) --
jamais en reutilisant LookupStructure lui-meme pour generer sa propre reference, ce qui
aurait ete circulaire.

Deux verifications independantes par question :
  - routage : le Routeur classe-t-il bien la question en TypeQuestion.CHIFFRE
    (heuristique par mots-cles uniquement, aucun appel reseau) ?
  - valeur : LookupStructure renvoie-t-il la bonne valeur (± tolerance), ou refuse-t-il
    correctement (None) quand c'est le comportement attendu ?

Usage : python -m scripts.mesurer_fiabilite [chemin_db]
Sortie : recapitulatif ligne par ligne + taux d'exactitude final, code de sortie 0 si
>= 90%, 1 sinon (utilisable en CI/pre-demo check).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple, Optional

from src.base_donnees import connecter
from src.lookup_structure import LookupStructure
from src.routeur import Routeur, TypeQuestion


class CasTest(NamedTuple):
    question: str
    valeur_attendue: Optional[float]  # None = refus attendu (ambigu ou hors-perimetre)
    tolerance: float
    note: str


# --- Jeu de test (30 cas), valeurs verifiees le 03/09/2026 sur data/hcp_rag.db -------

CAS_TEST: list[CasTest] = [
    # --- Agregats nationaux, un par indicateur cure (14 indicateurs sur 18 ont un
    # agregat region IS NULL ; les 2 restants (Structure des actifs occupes, Valeurs
    # ajoutees par branche) n'en ont pas -- couverts plus bas par une question ciblant
    # une ventilation, seule reponse correcte possible pour ces deux-la) ---
    CasTest("quel est le taux de chômage actuel ?", 13.0, 0.05, "I4001 agregat"),
    CasTest("taux d'urbanisation", 62.8, 0.05, "I2790"),
    CasTest("population du Maroc", 38050.0, 2.0, "I1588 agregat"),
    CasTest("espérance de vie à la naissance", 77.4525, 0.5, "I2781 agregat (annee courante, pas projection)"),
    CasTest("indice synthétique de fécondité", 2.0024, 0.01, "I2786 agregat"),
    CasTest("nombre de ménages au Maroc", 9621.0, 2.0, "I2784 agregat"),
    CasTest("produit intérieur brut aux prix courants", 1089521.0, 1.0, "I1428"),
    CasTest("produit intérieur brut aux prix constants", 1080257.0, 1.0, "I3161"),
    CasTest("exportations de biens et services", 380534.0, 1.0, "I1437"),
    CasTest("importations", 463649.0, 1.0, "I1434"),
    CasTest("indice des prix à la consommation", 119.6, 0.05, "I3981"),
    CasTest("taux d'emploi des 15 ans et plus", 37.8, 0.05, "I1465"),
    CasTest("taux net d'activité", 43.5, 0.05, "I40"),
    CasTest("effectif des chômeurs", 1621.0, 1.0, "I2868 (milliers)"),

    # --- Ventilations explicites (dimension demandee dans la question) ---
    CasTest("taux de chômage des femmes", 20.5, 0.05, "I4001, Feminin"),
    CasTest("taux de chômage des hommes", 10.8, 0.05, "I4001, Masculin"),
    CasTest("taux de chômage en milieu urbain", 16.4, 0.05, "I4001, Urbain"),
    CasTest("taux de chômage en milieu rural", 6.6, 0.05, "I4001, Rural"),
    CasTest("population urbaine du Maroc", 25167.0, 2.0, "I1588, Urbain"),
    CasTest("structure des actifs occupés sans diplôme", 46.4, 0.05, "I2863 (pas d'agregat)"),
    CasTest("structure des actifs occupés niveau supérieur", 20.1, 0.05, "I2863 (pas d'agregat)"),
    CasTest("structure des actifs occupés niveau moyen", 33.5, 0.05, "I2863 (pas d'agregat)"),
    CasTest("valeur ajoutée de l'agriculture", 33359.7, 1.0, "I3181, dernier trimestre dispo (2021T4, pas d'agregat)"),
    CasTest(
        "taux de chômage à Marrakech-Safi", 8.1, 0.05,
        "I3287, region seule (sans sexe) -- LIMITE CONNUE (voir JOURNAL.md 03/09) : "
        "I4001 et I3287 partagent exactement le meme score/mots {taux, chomage}, la "
        "regle d'egalite (Bug 2, 30/08) les traite alors comme de simples ventilations "
        "du meme indicateur et choisit I4001 (agregat 13.0) au lieu de refuser ou de "
        "reconnaitre que ce sont deux indicateurs distincts. Laisse volontairement en "
        "echec ici plutot que corrige a la hate -- necessite de fusionner matching du "
        "nom et matching de la dimension, pas une correction ponctuelle."
    ),

    # --- Paraphrase (memes mots-cles reels, formulation differente) ---
    CasTest(
        "combien de chômeurs y a-t-il ?", 1621.0, 1.0,
        "paraphrase de I2868 -- 'au Maroc' volontairement omis, voir note dans "
        "tests/test_lookup_structure.py (le mot 'Maroc' cree une ambiguite reelle et "
        "distincte avec I1588, comportement attendu du systeme, pas un bug)",
    ),

    # --- Cas volontairement ambigus ou hors-perimetre : seul comportement correct =
    # refuser (None), jamais deviner. Compte comme "correct" si le systeme refuse. ---
    CasTest("chomage", None, 0.0, "trop vague (score<=1, plusieurs indicateurs 'chomage') -> refus attendu"),
    CasTest("quel est le taux", None, 0.0, "signal trop faible (mot 'taux' seul) -> refus attendu"),
    CasTest("quel est le taux de travail", None, 0.0, "cas ambigu documente dans le code (score=1 partage) -> refus attendu"),
    CasTest("quel est le taux de pauvreté au Maroc", None, 0.0, "indicateur hors perimetre cure -> refus attendu, pas d'invention"),
    CasTest("taux de chômage des femmes en milieu urbain", 26.0, 0.05, "I4001, dimension croisee Urbain+Feminin -- existe reellement en base (verifie le 03/09)"),
]


def _valeurs_egales(obtenue: Optional[float], attendue: Optional[float], tolerance: float) -> bool:
    if attendue is None:
        return obtenue is None
    if obtenue is None:
        return False
    return abs(obtenue - attendue) <= tolerance


def main(chemin_db: Optional[Path] = None) -> int:
    conn = connecter(chemin_db)
    lookup = LookupStructure(conn)
    # Sans fonction_classification_llm : le Routeur reste 100% heuristique, aucun
    # appel reseau -- voir docstring de Routeur (repli LLM ignore si non injecte).
    routeur = Routeur()

    nb_corrects = 0
    lignes: list[str] = []

    for cas in CAS_TEST:
        type_classe = routeur.classifier(cas.question)
        routage_ok = type_classe == TypeQuestion.CHIFFRE

        valeur_obtenue: Optional[float] = None
        if routage_ok:
            indicateur = lookup.rechercher_indicateur(cas.question)
            valeur_obtenue = indicateur.valeur if indicateur else None

        correct = routage_ok and _valeurs_egales(valeur_obtenue, cas.valeur_attendue, cas.tolerance)
        # Cas de refus attendu : si le routeur n'a meme pas classe CHIFFRE, le
        # comportement global reste correct (aucun chiffre invente) -- on l'accepte
        # aussi comme correct, tant que la valeur finale n'est jamais une valeur
        # numerique erronee.
        if cas.valeur_attendue is None and not routage_ok:
            correct = True

        nb_corrects += int(correct)
        statut = "OK" if correct else "ECHEC"
        lignes.append(
            f"[{statut:5}] {cas.question!r:55} attendu={cas.valeur_attendue} "
            f"obtenu={valeur_obtenue} (routage={type_classe.value}) -- {cas.note}"
        )

    total = len(CAS_TEST)
    taux = 100.0 * nb_corrects / total

    print("\n".join(lignes))
    print()
    print(f"Resultat : {nb_corrects}/{total} corrects -- taux d'exactitude = {taux:.1f}%")
    print(f"Objectif NF2 (>= 90%) : {'ATTEINT' if taux >= 90.0 else 'NON ATTEINT'}")

    return 0 if taux >= 90.0 else 1


if __name__ == "__main__":
    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(main(chemin))
