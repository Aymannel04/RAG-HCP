"""
Script d'orchestration Sprint 3 : relie Routeur -> LookupStructure/RetrievalReranker ->
Generateur, implémentation concrète des deux scénarios formalisés dans
docs/conception_uml_v3.pdf (figures 5 et 6), plus le scénario mixte (Q4 de la synthèse
Sprint 2/3) ajouté le 28/07.

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

Cas mixte (TypeQuestion.MIXTE, ajouté le 28/07 -- voir src/routeur.py) : les deux
chemins sont interrogés, LookupStructure ET RetrievalReranker, puis fusionnés par
Generateur (voir src/generateur.py::ContexteMixte). Dégradation à chaque étage plutôt
qu'un échec complet si un seul des deux chemins trouve quelque chose : chiffre+chunks
trouvés -> réponse fusionnée ; chiffre seul trouvé -> réponse chiffrée seule ; chunks
seuls trouvés -> réponse notion seule ; rien trouvé -> message explicite d'absence
d'information (voir Generateur.generer_reponse).

Cache + historique (ajoutés le 28/07 -- voir src/cache_redis.py) : `cache` et
`historique` sont injectables, tous deux `None` par défaut -- comportement inchangé si
absents, aucune régression possible sur les appels existants (même patron que tous les
autres paramètres injectables du projet). Le cache ne s'applique QU'AU chemin NOTION
pur (dernier `else` ci-dessous) : le chemin CHIFFRE est déjà une requête SQL directe,
rien à gagner à le cacher, et le chemin MIXTE est délibérément exclu (son chiffre doit
rester à jour à chaque appel -- voir docstring de src/cache_redis.py). L'historique,
lui, enregistre TOUTES les questions quel que soit leur type : c'est un journal de
conversation pour l'interface, pas une optimisation de calcul.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Optional

from src import llm_mistral
from src.base_donnees import connecter
from src.cache_redis import CacheReponses, HistoriqueConversation
from src.generateur import ContexteMixte, Generateur, Reponse
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
    cache: Optional[CacheReponses] = None,
    historique: Optional[HistoriqueConversation] = None,
    id_session: Optional[str] = None,
) -> Reponse:
    """Implémente les figures 5 et 6, plus le scénario mixte (voir docstring de
    module) : classifie la question, suit le(s) chemin(s) correspondant(s), avec repli
    chiffré -> notion si aucun indicateur trouvé.

    `reranker` est pris en paramètre déjà construit (plutôt que construit ici à partir
    d'un `IndexeurTexte`) pour que les tests puissent injecter une fonction de
    reranking factice (voir tests/test_poser_question.py) sans provoquer le
    téléchargement du vrai modèle -- même raisonnement que l'injection de
    `fonction_embedding`/`fonction_generation` ailleurs dans le projet.

    `cache`/`historique` : voir docstring de module. `id_session` est ignoré si
    `historique` est `None` (rien à indexer sans backend), et inversement aucun
    historique n'est enregistré si `id_session` est `None` (pas de clé sous laquelle
    ranger l'entrée) -- les deux sont nécessaires ensemble, jamais l'un sans l'autre.
    """
    type_question = routeur.classifier(question)

    if type_question == TypeQuestion.CHIFFRE:
        indicateur = LookupStructure(conn).rechercher_indicateur(question)
        if indicateur is not None:
            reponse = generateur.generer_reponse(question, indicateur)
        else:
            # Repli documenté (voir docstring de module) : pas d'indicateur exact
            # trouve, on retente via la recherche textuelle plutot que d'abandonner.
            chunks = reranker.rechercher_et_trier(question)
            reponse = generateur.generer_reponse(question, chunks)

    elif type_question == TypeQuestion.MIXTE:
        # Dispatch parallele : les deux chemins sont interroges, quoi qu'il arrive.
        indicateur = LookupStructure(conn).rechercher_indicateur(question)
        chunks = reranker.rechercher_et_trier(question)
        if indicateur is not None:
            # Generateur degrade proprement tout seul si `chunks` est vide (voir
            # ContexteMixte / _generer_reponse_mixte) -- pas besoin de le refaire ici.
            reponse = generateur.generer_reponse(question, ContexteMixte(indicateur=indicateur, chunks=chunks))
        else:
            # Aucun indicateur trouve du tout : repli sur le chemin notion seul.
            reponse = generateur.generer_reponse(question, chunks)

    else:
        # TypeQuestion.NOTION -- seul chemin mis en cache (voir docstring de module).
        reponse_en_cache = cache.obtenir(question) if cache is not None else None
        if reponse_en_cache is not None:
            reponse = reponse_en_cache
        else:
            chunks = reranker.rechercher_et_trier(question)
            reponse = generateur.generer_reponse(question, chunks)
            if cache is not None:
                cache.enregistrer(question, reponse)

    if historique is not None and id_session is not None:
        historique.ajouter(id_session, question, reponse)

    return reponse


def _connecter_redis():
    """Tente une connexion a un serveur Redis local (voir README.md pour
    l'installation). Renvoie `None` si indisponible (pas de serveur lance, paquet
    absent, etc.) -- degradation silencieuse, coherente avec CacheReponses/
    HistoriqueConversation qui savent tourner sans client (voir src/cache_redis.py) :
    le script continue de fonctionner normalement, juste sans cache ni historique."""
    try:
        import redis
        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def main(question: str, chemin_db: Optional[Path] = None, id_session: Optional[str] = None) -> None:
    conn = connecter(chemin_db)
    try:
        indexeur = IndexeurTexte()
        reranker = RetrievalReranker(indexeur)  # vrai cross-encoder, voir ADR 0007
        # fonction_classification_llm : dernier recours seulement, voir docstring de
        # Routeur ("V2 ajoutee le 28/07") -- sans effet si MISTRAL_API_KEY absente,
        # l'appel echoue silencieusement et le repli NOTION habituel s'applique.
        routeur = Routeur(fonction_classification_llm=llm_mistral.classifier_question)
        # Mistral choisi comme LLM de production (voir ADR 0002, src/llm_mistral.py) :
        # necessite MISTRAL_API_KEY dans un fichier .env. Le chemin chiffre fonctionne
        # meme sans cle configuree (voir Generateur).
        generateur = Generateur(conn, fonction_generation=llm_mistral.generer)

        # Cache + historique (voir docstring de module) : un seul client Redis pour
        # les deux. `id_session` genere ici si absent -- un appel CLI, c'est une
        # session a lui seul ; une vraie interface (Streamlit ou autre) generera et
        # retiendra son propre id_session sur toute la duree d'une conversation.
        client_redis = _connecter_redis()
        cache = CacheReponses(client_redis)
        historique = HistoriqueConversation(client_redis)
        id_session = id_session or str(uuid.uuid4())

        reponse = poser_question(
            conn, reranker, routeur, generateur, question,
            cache=cache, historique=historique, id_session=id_session,
        )

        print(f"Question : {question}")
        print(f"Reponse  : {reponse.texte}")
        if reponse.source_url:
            print(f"Source   : {reponse.source_titre} ({reponse.source_date or 'date inconnue'})")
            print(f"           {reponse.source_url}")
        if reponse.source_url_secondaire:
            # Cas mixte avec deux sources distinctes (chiffre + narratif), voir
            # src/generateur.py::ContexteMixte.
            print(f"Source 2 : {reponse.source_titre_secondaire} ({reponse.source_date_secondaire or 'date inconnue'})")
            print(f"           {reponse.source_url_secondaire}")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage : python -m scripts.poser_question "question" [chemin_db]')
        sys.exit(1)
    chemin = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    main(sys.argv[1], chemin)
