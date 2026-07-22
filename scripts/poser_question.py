"""
Script d'orchestration Sprint 3 : relie Routeur -> LookupStructure/RetrievalReranker ->
Generateur, implémentation concrète des deux scénarios formalisés dans
docs/conception_uml_v3.pdf (figures 5 et 6).

`poser_question` est la fonction réutilisable (testée avec de vraies bases SQLite/Chroma
et des fonctions embedding/reranking/génération factices, voir
tests/test_poser_question.py) ; `main` est le point d'entrée CLI, qui suppose l'index
déjà peuplé (scripts/indexer_documents.py) et branche le LLM de production pour le
chemin notion (voir ADR 0002, src/llm_mistral.py).

Usage prévu :

    python -m scripts.poser_question "Quel est le taux de chômage actuel ?"

Repli explicite (voir docstring de LookupStructure.rechercher_indicateur, qui renvoie
elle-même à docs/fiche_cadrage_v4.pdf section 8.5) : si le Routeur classe la question
comme CHIFFRE mais qu'aucun indicateur correspondant n'est trouvé en base, on retente
via RetrievalReranker plutôt que de répondre "indicateur non trouvé" sans avoir cherché
dans le texte des rapports.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from src import llm_mistral
from src.base_donnees import connecter
from src.generateur import Generateur, Reponse
from src.indexeur_texte import IndexeurTexte
from src.lookup_structure import LookupStructure
from src.retrieval_reranker import RetrievalReranker
from src.routeur import Routeur, TypeQuestion


def poser_question(
    conn,
    reranker: RetrievalReranker,
    routeur: Routeur,
    generateur: Generateur,
    question: str,
) -> Reponse:
    """Implémente les figures 5 et 6 : classifie la question, suit le chemin
    correspondant, avec repli chiffré -> notion si aucun indicateur trouvé.

    `reranker` est pris en paramètre déjà construit (plutôt que construit ici à partir
    d'un `IndexeurTexte`) pour que les tests puissent injecter une fonction de
    reranking factice (voir tests/test_poser_question.py) sans provoquer le
    téléchargement du vrai modèle -- même raisonnement que l'injection de
    `fonction_embedding`/`fonction_generation` ailleurs dans le projet.
    """
    type_question = routeur.classifier(question)

    if type_question == TypeQuestion.CHIFFRE:
        indicateur = LookupStructure(conn).rechercher_indicateur(question)
        if indicateur is not None:
            return generateur.generer_reponse(question, indicateur)
        # Repli documenté (voir docstring de module) : pas d'indicateur exact trouve,
        # on retente via la recherche textuelle plutot que d'abandonner.

    chunks = reranker.rechercher_et_trier(question)
    return generateur.generer_reponse(question, chunks)


def main(question: str, chemin_db: Optional[Path] = None) -> None:
    conn = connecter(chemin_db)
    try:
        indexeur = IndexeurTexte()
        reranker = RetrievalReranker(indexeur)  # vrai cross-encoder, voir ADR 0007
        routeur = Routeur()
        # Mistral choisi comme LLM de production (voir ADR 0002, src/llm_mistral.py) :
        # necessite MISTRAL_API_KEY dans un fichier .env. Le chemin chiffre fonctionne
        # meme sans cle configuree (voir Generateur).
        generateur = Generateur(conn, fonction_generation=llm_mistral.generer)

        reponse = poser_question(conn, reranker, routeur, generateur, question)

        print(f"Question : {question}")
        print(f"Reponse  : {reponse.texte}")
        if reponse.source_url:
            print(f"Source   : {reponse.source_titre} ({reponse.source_date or 'date inconnue'})")
            print(f"           {reponse.source_url}")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage : python -m scripts.poser_question "question" [chemin_db]')
        sys.exit(1)
    chemin = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    main(sys.argv[1], chemin)
