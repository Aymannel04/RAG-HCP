"""
Evaluation du Routeur (heuristique par mots-cles, aucun appel reseau) sur un jeu de
questions etiquetees a la main -- ecrit le 13/10/2026 pour chiffrer une faiblesse
connue : jusqu'ici seul le chemin chiffre avait un jeu de test (scripts/
mesurer_fiabilite.py), jamais le routage lui-meme sur des formulations variees.

Les etiquettes sont celles qu'un lecteur humain donnerait a la question (ce que
l'utilisateur VEUT), pas celles que l'heuristique produit : jeu volontairement ecrit
sans regarder les listes MOTS_NOTION / MOTS_CHIFFRE pour ne pas etre circulaire.
Il contient des formulations naturelles, courtes, familieres ou avec fautes, comme
dans les vraies sessions de test de l'interface.

Lecture des resultats (important) : plusieurs questions "pourquoi X ?" etiquetees MIXTE
ici sont classees NOTION PAR CHOIX DE CONCEPTION, pas par accident -- voir
tests/test_routeur.py : un "pourquoi" sans mot-outil de mesure ("taux de", "nombre de"...)
reste NOTION pur (decision du 28/07, voir docstring de src/routeur.py). Ces cas mesurent
donc l'ecart entre l'intention d'un utilisateur et ce compromis, pas un bug a corriger.
Les vrais manques sont ailleurs : noms d'indicateurs nus ("PIB", "population totale",
"salaire") et questions en anglais, non reconnus comme CHIFFRE.

Usage : python -m scripts.evaluer_routeur
Sortie : matrice de confusion, exactitude globale et par classe, liste des erreurs.
Ne modifie rien. Code de sortie toujours 0 (c'est une mesure, pas un test de non-regression).
"""
from __future__ import annotations

from collections import Counter, defaultdict

from src.routeur import Routeur, TypeQuestion

C, N, M, S = TypeQuestion.CHIFFRE, TypeQuestion.NOTION, TypeQuestion.MIXTE, TypeQuestion.SALUTATION

JEU: list[tuple[str, TypeQuestion]] = [
    # --- CHIFFRE : une valeur precise est demandee -------------------------------
    ("Quel est le taux de chômage actuel ?", C),
    ("combien de chômeurs au Maroc ?", C),
    ("taux de chômage chez les jeunes", C),
    ("Quelle est la population du Maroc en 2024 ?", C),
    ("population totale", C),
    ("combien d'habitants a le Maroc", C),
    ("quel est le PIB du Maroc ?", C),
    ("produit intérieur brut aux prix courants", C),
    ("le taux d'urbanisation", C),
    ("espérance de vie à la naissance", C),
    ("quelle est l'espérance de vie des femmes ?", C),
    ("indice des prix à la consommation", C),
    ("quel est le taux d'inflation ?", C),
    ("nombre de ménages", C),
    ("taux d'activité des femmes", C),
    ("taux de chômage à Casablanca", C),
    ("taux de chômage en milieu rural", C),
    ("Quel est le taux d'emploi ?", C),
    ("indice synthétique de fécondité", C),
    ("combien exporte le Maroc ?", C),
    ("valeur des importations", C),
    ("part de l'agriculture dans la valeur ajoutée", C),
    ("répartition des actifs occupés par diplôme", C),
    ("taux de chômage des diplômés", C),
    ("chiffre du chômage 2023", C),
    ("population urbaine", C),
    ("quel pourcentage de la population est rurale ?", C),
    ("nombre d'actifs occupés", C),
    ("le chômage en 2022 c'est combien ?", C),
    ("quel est le niveau de l'inflation en 2025", C),
    ("Quelle est la croissance du PIB en 2023 ?", C),
    ("nombre de naissances par an", C),
    ("taux de pauvreté", C),
    ("salaire moyen au Maroc", C),
    ("how many unemployed in Morocco", C),
    ("unemployment rate", C),
    # --- NOTION : definition, methode, explication, sans chiffre demande ---------
    ("C'est quoi le RGPH ?", N),
    ("Qu'est-ce que le HCP ?", N),
    ("c quoi rghp", N),
    ("Comment est calculé l'indice des prix à la consommation ?", N),
    ("Comment est définie la population active ?", N),
    ("quelle est la différence entre chômage et sous-emploi", N),
    ("Explique-moi la méthodologie du recensement", N),
    ("que fait la DSIS ?", N),
    ("quel est le rôle du Haut-Commissariat au Plan ?", N),
    ("Qu'est-ce qu'un ménage selon le HCP ?", N),
    ("définition du taux d'activité", N),
    ("à quoi sert l'enquête nationale sur l'emploi ?", N),
    ("parle-moi des comptes nationaux", N),
    ("quelles publications existent sur le marché du travail ?", N),
    ("Comment fonctionne l'enquête sur la consommation des ménages ?", N),
    ("que veut dire PIB ?", N),
    ("Qu'est-ce que la transition démographique ?", N),
    ("résume la note d'information sur la situation du marché du travail", N),
    ("what is the HCP", N),
    ("c'est quoi la BDS", N),
    ("Comment sont collectées les données du recensement ?", N),
    ("explique la différence entre PIB nominal et réel", N),
    ("quelle est la méthodologie de l'indice des prix", N),
    ("a quoi correspond le milieu urbain dans les statistiques ?", N),
    # --- MIXTE : un chiffre ET une explication/evolution -------------------------
    ("Pourquoi le chômage a-t-il augmenté ?", M),
    ("Le chômage a-t-il baissé récemment, et pourquoi ?", M),
    ("quelle est l'évolution de la population depuis 2014 ?", M),
    ("tendance du taux d'activité des femmes", M),
    ("pourquoi le taux d'urbanisation augmente-t-il ?", M),
    ("explique l'évolution du PIB entre 2019 et 2023", M),
    ("quelles sont les causes de la hausse de l'inflation et de combien a-t-elle augmenté ?", M),
    ("le taux de chômage est de combien et pourquoi touche-t-il plus les jeunes ?", M),
    ("analyse du chômage des diplômés", M),
    ("raisons de la baisse de la fécondité et valeur actuelle", M),
    ("how did unemployment evolve and why", M),
    ("le chômage a augmenté de combien depuis 2020 et à cause de quoi ?", M),
    # --- SALUTATION ---------------------------------------------------------------
    ("hello", S),
    ("Bonjour", S),
    ("salut", S),
    ("salam", S),
    ("merci", S),
    ("merci beaucoup", S),
    ("bonsoir", S),
    ("coucou", S),
    ("au revoir", S),
    ("ça va ?", S),
    ("hi", S),
    ("slm", S),
]


def main() -> None:
    routeur = Routeur()
    confusion: dict[tuple[TypeQuestion, TypeQuestion], int] = Counter()
    erreurs: list[tuple[str, TypeQuestion, TypeQuestion]] = []
    par_classe_total: dict[TypeQuestion, int] = defaultdict(int)
    par_classe_ok: dict[TypeQuestion, int] = defaultdict(int)

    for question, attendu in JEU:
        obtenu = routeur.classifier(question)
        confusion[(attendu, obtenu)] += 1
        par_classe_total[attendu] += 1
        if obtenu == attendu:
            par_classe_ok[attendu] += 1
        else:
            erreurs.append((question, attendu, obtenu))

    total = len(JEU)
    ok = sum(par_classe_ok.values())
    print(f"Questions : {total}   Corrects : {ok}   Exactitude globale : {100 * ok / total:.1f}%\n")

    print("Par classe attendue :")
    for classe in (C, N, M, S):
        t, o = par_classe_total[classe], par_classe_ok[classe]
        print(f"  {classe.value:11} {o:3}/{t:3}  ({100 * o / t:5.1f}%)")

    ordre = [C, N, M, S]
    print("\nMatrice de confusion (lignes = attendu, colonnes = obtenu) :")
    print("  " + " " * 11 + "".join(f"{c.value:>11}" for c in ordre))
    for a in ordre:
        print("  " + f"{a.value:11}" + "".join(f"{confusion[(a, o)]:11}" for o in ordre))

    print(f"\nErreurs ({len(erreurs)}) :")
    for question, attendu, obtenu in erreurs:
        print(f"  attendu={attendu.value:10} obtenu={obtenu.value:10} {question!r}")


if __name__ == "__main__":
    main()
