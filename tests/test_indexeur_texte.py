"""
Tests du module IndexeurTexte. Le chunking est teste pur (aucune dependance).
Chroma et rank_bm25 sont utilises REELLEMENT (installes dans requirements.txt) pour
valider la vraie API des bibliotheques, mais avec une fonction d'embedding FACTICE
injectee au constructeur : le vrai modele BGE-M3 (~2 Go) n'est pas telechargeable dans
ce sandbox sans acces reseau (meme contrainte que pour le scraping reel, voir
JOURNAL.md). A valider avec le vrai modele sur la machine d'Ayman.
"""
import re

import pytest

from src.indexeur_texte import IndexeurTexte
from src.models import Document


# --- Chunking (pur, aucune dependance) -----------------------------------------------


def test_decouper_en_chunks_texte_vide():
    assert IndexeurTexte._decouper_en_chunks("") == []
    assert IndexeurTexte._decouper_en_chunks("   \n  \n ") == []


def test_decouper_en_chunks_texte_court_un_seul_chunk():
    texte = "Premier paragraphe.\nDeuxieme paragraphe."
    chunks = IndexeurTexte._decouper_en_chunks(texte, taille_max=1000, chevauchement=100)
    assert chunks == ["Premier paragraphe.\nDeuxieme paragraphe."]


def test_decouper_en_chunks_empaquete_plusieurs_paragraphes_sans_depasser_la_taille_max():
    paragraphes = [f"Paragraphe numero {i}." for i in range(20)]
    texte = "\n".join(paragraphes)
    chunks = IndexeurTexte._decouper_en_chunks(texte, taille_max=100, chevauchement=20)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 100
    # Aucun paragraphe perdu : chaque paragraphe original doit apparaitre dans au moins un chunk.
    for p in paragraphes:
        assert any(p in c for c in chunks)


def test_decouper_en_chunks_chevauchement_entre_deux_chunks_consecutifs():
    # 3 paragraphes de 40 caracteres chacun, taille_max=50 -> chaque chunk ne peut
    # contenir qu'un seul paragraphe (2 paragraphes = 81 caracteres > 50).
    paragraphes = ["A" * 40, "B" * 40, "C" * 40]
    texte = "\n".join(paragraphes)
    chunks = IndexeurTexte._decouper_en_chunks(texte, taille_max=50, chevauchement=15)

    assert len(chunks) == 3
    # La fin du chunk precedent (chevauchement) doit se retrouver au debut du suivant.
    fin_premier = chunks[0][-15:]
    assert fin_premier in chunks[1]


def test_decouper_en_chunks_paragraphe_geant_tronconne_sans_perte():
    # Paragraphe distinctif (pas juste "X" repete) pour verifier precisement quels
    # caracteres finissent dans quel chunk, plutot qu'une simple longueur.
    paragraphe_geant = "".join(chr(ord("A") + (i % 26)) for i in range(250))
    chunks = IndexeurTexte._decouper_en_chunks(paragraphe_geant, taille_max=100, chevauchement=20)

    # pas = taille_max - chevauchement = 80 -> decoupage attendu a 0, 80, 160, 240.
    attendu = [
        paragraphe_geant[0:100],
        paragraphe_geant[80:180],
        paragraphe_geant[160:250],
        paragraphe_geant[240:250],
    ]
    assert chunks == attendu
    # Chaque caractere du paragraphe original doit apparaitre dans au moins un chunk.
    couverts = set()
    for i, c in enumerate(attendu):
        debut = [0, 80, 160, 240][i]
        couverts.update(range(debut, debut + len(c)))
    assert couverts == set(range(250))


def test_decouper_en_chunks_respecte_taille_max_par_defaut():
    texte = "\n".join(f"Phrase {i} avec un peu de texte pour remplir." for i in range(50))
    chunks = IndexeurTexte._decouper_en_chunks(texte)
    for c in chunks:
        assert len(c) <= 1500


# --- Fusion RRF (pur, aucune dependance) ----------------------------------------------


def test_fusionner_rrf_favorise_les_ids_bien_classes_dans_les_deux_listes():
    denses = ["a", "b", "c", "d"]
    bm25 = ["c", "a", "d", "b"]
    resultat = IndexeurTexte._fusionner_rrf([denses, bm25], top_k=4)

    # "a" (rang 0 dense, rang 1 bm25) et "c" (rang 2 dense, rang 0 bm25) doivent
    # dominer "b" et "d", moins bien classes dans les deux listes.
    assert set(resultat[:2]) == {"a", "c"}


def test_fusionner_rrf_id_absent_d_une_liste_est_quand_meme_pris_en_compte():
    denses = ["x", "y"]
    bm25 = ["z"]  # "z" absent de la recherche dense
    resultat = IndexeurTexte._fusionner_rrf([denses, bm25], top_k=3)
    assert set(resultat) == {"x", "y", "z"}


def test_fusionner_rrf_respecte_top_k():
    denses = ["a", "b", "c", "d", "e"]
    resultat = IndexeurTexte._fusionner_rrf([denses], top_k=2)
    assert resultat == ["a", "b"]


# --- Indexation + recherche hybride (Chroma + BM25 reels, embedding factice) ----------

VOCABULAIRE_TEST = ["chomage", "emploi", "population", "prix", "inflation", "recensement"]


def _fausse_fonction_embedding(textes: list[str]) -> list[list[float]]:
    """Vecteur binaire sur un petit vocabulaire fixe : suffisant pour verifier que la
    recherche dense distingue des textes de sujets differents, sans charger BGE-M3."""
    vecteurs = []
    for texte in textes:
        mots = set(re.findall(r"\w+", texte.lower()))
        vecteur = [1.0 if mot in mots else 0.0 for mot in VOCABULAIRE_TEST]
        if not any(vecteur):
            vecteur[0] = 0.01  # evite un vecteur nul (distance cosinus indefinie)
        vecteurs.append(vecteur)
    return vecteurs


@pytest.fixture
def indexeur(tmp_path):
    return IndexeurTexte(dossier_chroma=tmp_path / "chroma", fonction_embedding=_fausse_fonction_embedding)


def _document_test(id_document: int, categorie: str = "Marche du travail") -> Document:
    return Document(
        id_document=id_document,
        url=f"https://www.hcp.ma/test-{id_document}.html",
        titre=f"Document test {id_document}",
        date_publication="2026-01-01",
        langue="fr",
        categorie=categorie,
        type="pdf",
    )


def test_indexer_leve_erreur_si_id_document_absent(indexeur):
    document_sans_id = Document(
        id_document=None, url="https://www.hcp.ma/x.html", titre="X",
        date_publication=None, langue="fr", categorie="Economie", type="pdf",
    )
    with pytest.raises(ValueError):
        indexeur.indexer(document_sans_id, "Un texte quelconque.")


def test_indexer_texte_vide_ne_cree_aucun_chunk(indexeur):
    chunks = indexeur.indexer(_document_test(1), "")
    assert chunks == []


def test_indexer_ajoute_les_chunks_dans_chroma_avec_les_bonnes_metadonnees(indexeur):
    document = _document_test(42, categorie="Population et demographie")
    chunks = indexeur.indexer(document, "Le taux de chomage a baisse.\nLa population augmente.")

    assert len(chunks) >= 1
    for c in chunks:
        assert c.id_document == 42
        assert c.embedding is not None

    # Verifie directement dans Chroma que les metadonnees sont bien celles attendues.
    resultat = indexeur._collection.get(ids=[f"doc42_chunk{c.position}" for c in chunks], include=["metadatas"])
    for meta in resultat["metadatas"]:
        assert meta["id_document"] == 42
        assert meta["categorie"] == "Population et demographie"


def test_rechercher_collection_vide_renvoie_liste_vide(indexeur):
    assert indexeur.rechercher("une question quelconque") == []


def test_rechercher_hybride_retrouve_le_chunk_thematiquement_pertinent(indexeur):
    doc_emploi = _document_test(1, categorie="Marche du travail")
    doc_population = _document_test(2, categorie="Population et demographie")

    indexeur.indexer(doc_emploi, "Le taux de chomage recule au premier trimestre. L'emploi progresse.")
    indexeur.indexer(doc_population, "Le recensement general de la population montre une hausse.")

    resultats = indexeur.rechercher("Quelle est la situation du chomage ?", top_k=1)

    assert len(resultats) == 1
    assert resultats[0].id_document == 1  # le chunk du document "Marche du travail", pas "Population"


def test_indexer_puis_reindexer_le_meme_document_ecrase_via_upsert(indexeur):
    document = _document_test(7)
    indexeur.indexer(document, "Version initiale du texte.")
    compte_initial = indexeur._collection.count()

    indexeur.indexer(document, "Version initiale du texte.")  # meme texte -> memes ids
    assert indexeur._collection.count() == compte_initial  # upsert, pas de doublon
