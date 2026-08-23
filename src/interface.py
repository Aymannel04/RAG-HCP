"""
Module Interface — module 9 de l'architecture (Sprint 4, 3 août 2026).
Rôle : afficher la question, la réponse et la source cliquable, en s'appuyant
uniquement sur le pipeline déjà validé (Routeur -> LookupStructure/RetrievalReranker
-> Generateur, voir scripts/poser_question.py) -- cette interface n'implémente aucune
logique métier, seulement l'affichage. Streamlit choisi en Sprint 1 (ADR 0002) pour ce
prototype.

Décisions de conception (voir aussi echanges avec Ayman, 3 aout) :
- Chargement des modèles lourds (BGE-M3, cross-encoder) via st.cache_resource.
- La connexion SQLite n'est PAS mise en cache (thread-safety, cache_resource partagé
  entre toutes les sessions).
- id_session via st.session_state, généré une fois à l'ouverture de la page.
- L'historique affiché vient de HistoriqueConversation.recuperer(), pas d'une liste
  Python locale (persiste au F5).
- Import absolu + bootstrap sys.path, pas d'import relatif (Streamlit exécute le
  fichier directement comme script, hors du package src).

Lancement : streamlit run src/interface.py depuis la racine du projet.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src import llm_mistral
from src.base_donnees import connecter
from src.cache_redis import CacheReponses, HistoriqueConversation
from src.generateur import Generateur
from src.indexeur_texte import IndexeurTexte
from src.retrieval_reranker import RetrievalReranker
from src.routeur import Routeur
from scripts.poser_question import _connecter_redis, poser_question

st.set_page_config(page_title="Assistant RAG - HCP", page_icon="📊")


@st.cache_resource(show_spinner="Chargement des modèles (BGE-M3 + reranker)...")
def _charger_reranker() -> RetrievalReranker:
    indexeur = IndexeurTexte()
    return RetrievalReranker(indexeur)


@st.cache_resource(show_spinner=False)
def _connecter_redis_cache():
    return _connecter_redis()


def _afficher_reponse(reponse) -> None:
    st.write(reponse.texte)
    if reponse.source_url:
        st.caption(f"Source : {reponse.source_titre} ({reponse.source_date or 'date inconnue'}) — {reponse.source_url}")
    if reponse.source_url_secondaire:
        st.caption(
            f"Source 2 : {reponse.source_titre_secondaire} "
            f"({reponse.source_date_secondaire or 'date inconnue'}) — {reponse.source_url_secondaire}"
        )


def main() -> None:
    reranker = _charger_reranker()
    client_redis = _connecter_redis_cache()
    cache = CacheReponses(client_redis)
    historique = HistoriqueConversation(client_redis)

    conn = connecter()
    routeur = Routeur(fonction_classification_llm=llm_mistral.classifier_question)
    generateur = Generateur(conn, fonction_generation=llm_mistral.generer)

    if "id_session" not in st.session_state:
        st.session_state.id_session = str(uuid.uuid4())

    st.title("Assistant RAG — HCP")
    st.caption("Questions sur les statistiques et publications du Haut-Commissariat au Plan")
    if client_redis is None:
        st.info("Redis indisponible : cache et historique désactivés pour cette session (voir README.md).", icon="ℹ️")

    for entree in historique.recuperer(st.session_state.id_session):
        with st.chat_message("user"):
            st.write(entree["question"])
        with st.chat_message("assistant"):
            st.write(entree["reponse"]["texte"])
            if entree["reponse"].get("source_url"):
                st.caption(
                    f"Source : {entree['reponse'].get('source_titre')} — {entree['reponse'].get('source_url')}"
                )

    question = st.chat_input("Pose ta question sur les statistiques du HCP...")
    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.spinner("Recherche en cours..."):
            reponse = poser_question(
                conn, reranker, routeur, generateur, question,
                cache=cache, historique=historique, id_session=st.session_state.id_session,
            )
        with st.chat_message("assistant"):
            _afficher_reponse(reponse)

    conn.close()


if __name__ == "__main__":
    main()
