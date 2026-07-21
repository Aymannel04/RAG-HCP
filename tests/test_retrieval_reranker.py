"""
Tests de RetrievalReranker avec un vrai IndexeurTexte (chromadb + rank_bm25 reels,
meme fixture qu'en Sprint 2, voir tests/test_indexeur_texte.py) et une fonction de
reranking factice (evite de telecharger BAAI/bge-reranker-v2-m3, voir ADR 0007).
"""
import re

import pytest

from src.indexeur_texte import IndexeurTexte
from src.models import Document
from src.retrieval_reranker import RetrievalReranker

VOCABULAIRE_TEST = ["chomage", "emploi", "population", "prix", "inflation", "recensement"]


def _fausse_fonction_embedding(textes: list[str]) -> list[list[float]]:
    vecteurs = []
    for texte in textes:
        mots = set(re.findall(r"\w+", texte.lower()))
        vecteur = [1.0 if mot in mots else 0.0 for mot in VOCABULAIRE_TEST]
        if not any(vecteur):
            vecteur[0] = 0.01
        vecteurs.append(vecteur)
    return vecteurs


def _fausse_fonction_reranking(question: str, textes: list[str]) -> list[float]:
    """Score de reranking factice : recouvrement de mots entre la question et chaque
    texte (assez pour verifier que RetrievalReranker respecte l'ordre retourne par la
    fonction injectee, sans dependre du vrai cross-encoder)."""
    mots_question = set(re.findall(r"\w+", question.lower()))
    scores = []
    for texte in textes:
        mots_texte = set(re.findall(r"\w+", texte.lower()))
        scores.append(float(len(mots_question & mots_texte)))
    return scores


@pytest.fixture
def indexeur(tmp_path):
    return IndexeurTexte(dossier_chroma=tmp_path / "chroma", fonction_embedding=_fausse_fonction_embedding)


@pytest.fixture
def reranker(indexeur):
    return RetrievalReranker(indexeur, fonction_reranking=_fausse_fonction_reranking)


def _indexer(indexeur, id_document, texte, categorie="Economie"):
    document = Document(
        id_document=id_document, url=f"https://www.hcp.ma/doc{id_document}.html",
        titre=f"Document {id_document}", date_publication="2026-07-20", langue="fr",
        categorie=categorie, type="pdf",
    )
    return indexeur.indexer(document, texte)


def test_rechercher_et_trier_renvoie_les_chunks_les_plus_pertinents(indexeur, reranker):
    _indexer(indexeur, 1, "Le taux de chomage a recule ce trimestre.\nL'emploi progresse.")
    _indexer(indexeur, 2, "Les prix a la consommation ont augmente.\nL'inflation reste moderee.")
    _indexer(indexeur, 3, "Le recensement general de la population a debute.")

    resultats = reranker.rechercher_et_trier("Quel est le taux de chomage ?", top_k=2)

    assert len(resultats) <= 2
    assert any("chomage" in c.texte.lower() for c in resultats)


def test_rechercher_et_trier_respecte_lordre_du_reranking(indexeur, reranker):
    _indexer(indexeur, 1, "Le recensement general de la population a debute.")
    _indexer(indexeur, 2, "Le taux de chomage a recule ce trimestre.")

    resultats = reranker.rechercher_et_trier("chomage", top_k=2)

    # Le chunk qui contient litteralement "chomage" doit etre mieux classe (la fonction
    # de reranking factice score sur le recouvrement de mots avec la question).
    assert "chomage" in resultats[0].texte.lower()


def test_rechercher_et_trier_index_vide_renvoie_liste_vide(indexeur, reranker):
    assert reranker.rechercher_et_trier("chomage") == []


def test_rechercher_et_trier_top_k_limite_le_nombre_de_resultats(indexeur, reranker):
    for i in range(5):
        _indexer(indexeur, i, f"Texte numero {i} a propos du chomage et de l'emploi.")

    resultats = reranker.rechercher_et_trier("chomage", top_k=3)
    assert len(resultats) == 3
