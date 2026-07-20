"""
Tests du module base_donnees. Utilisent une vraie base SQLite temporaire (fichier
tmp_path, pas de mock) avec le vrai db/schema.sql, meme esprit que tests/test_schema.py.
"""
import pytest

from src.base_donnees import (
    blob_vers_embedding,
    connecter,
    inserer_chunk,
    inserer_document,
    inserer_indicateur,
)
from src.models import Chunk, Document, Indicateur


@pytest.fixture
def conn(tmp_path):
    connexion = connecter(tmp_path / "test.db")
    yield connexion
    connexion.close()


def _document_test(url="https://www.hcp.ma/test.html") -> Document:
    return Document(
        id_document=None,
        url=url,
        titre="Titre test",
        date_publication="2026-07-20",
        langue="fr",
        categorie="Economie",
        type="pdf",
    )


def test_connecter_cree_les_trois_tables(conn):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"document", "chunk", "indicateur"} <= tables


def test_inserer_document_renvoie_un_id(conn):
    id_document = inserer_document(conn, _document_test())
    assert isinstance(id_document, int)
    assert id_document > 0


def test_inserer_document_meme_url_renvoie_le_meme_id_sans_dupliquer(conn):
    id1 = inserer_document(conn, _document_test(url="https://www.hcp.ma/x.html"))
    id2 = inserer_document(conn, _document_test(url="https://www.hcp.ma/x.html"))
    assert id1 == id2

    total = conn.execute("SELECT COUNT(*) FROM document").fetchone()[0]
    assert total == 1


def test_inserer_document_urls_differentes_donnent_des_ids_differents(conn):
    id1 = inserer_document(conn, _document_test(url="https://www.hcp.ma/a.html"))
    id2 = inserer_document(conn, _document_test(url="https://www.hcp.ma/b.html"))
    assert id1 != id2


def test_inserer_chunk_avec_embedding_round_trip(conn):
    id_document = inserer_document(conn, _document_test())
    chunk = Chunk(id_chunk=None, id_document=id_document, texte="Un texte.", position=0,
                  embedding=[0.1, 0.2, 0.3])
    id_chunk = inserer_chunk(conn, chunk)

    ligne = conn.execute(
        "SELECT texte, position, embedding FROM chunk WHERE id_chunk = ?", (id_chunk,)
    ).fetchone()
    assert ligne[0] == "Un texte."
    assert ligne[1] == 0
    embedding_relu = blob_vers_embedding(ligne[2])
    assert embedding_relu == pytest.approx([0.1, 0.2, 0.3], abs=1e-6)


def test_inserer_chunk_sans_embedding(conn):
    id_document = inserer_document(conn, _document_test())
    chunk = Chunk(id_chunk=None, id_document=id_document, texte="Sans embedding", position=0)
    id_chunk = inserer_chunk(conn, chunk)

    ligne = conn.execute("SELECT embedding FROM chunk WHERE id_chunk = ?", (id_chunk,)).fetchone()
    assert ligne[0] is None


def test_inserer_indicateur_nouvelle_ligne(conn):
    id_document = inserer_document(conn, _document_test())
    indicateur = Indicateur(
        id_indicateur=None, nom="Taux de chomage", valeur=13.3, unite="%",
        periode="2024", region=None, id_document=id_document, code_bds="I2790",
    )
    id_indicateur = inserer_indicateur(conn, indicateur)
    assert isinstance(id_indicateur, int)

    total = conn.execute("SELECT COUNT(*) FROM indicateur").fetchone()[0]
    assert total == 1


def test_inserer_indicateur_meme_cle_met_a_jour_au_lieu_de_dupliquer(conn):
    id_document = inserer_document(conn, _document_test())
    indicateur_v1 = Indicateur(
        id_indicateur=None, nom="Taux de chomage", valeur=13.3, unite="%",
        periode="2024", region=None, id_document=id_document, code_bds="I2790",
    )
    indicateur_v2 = Indicateur(
        id_indicateur=None, nom="Taux de chomage", valeur=13.5, unite="%",  # valeur revisee
        periode="2024", region=None, id_document=id_document, code_bds="I2790",
    )

    id1 = inserer_indicateur(conn, indicateur_v1)
    id2 = inserer_indicateur(conn, indicateur_v2)

    assert id1 == id2  # meme ligne mise a jour, pas un doublon
    total = conn.execute("SELECT COUNT(*) FROM indicateur").fetchone()[0]
    assert total == 1

    valeur_en_base = conn.execute(
        "SELECT valeur FROM indicateur WHERE id_indicateur = ?", (id1,)
    ).fetchone()[0]
    assert valeur_en_base == pytest.approx(13.5)


def test_inserer_indicateur_regions_differentes_ne_sont_pas_confondues(conn):
    id_document = inserer_document(conn, _document_test())
    indicateur_national = Indicateur(
        id_indicateur=None, nom="Taux de chomage", valeur=13.3, unite="%",
        periode="2024", region=None, id_document=id_document, code_bds="I2790",
    )
    indicateur_urbain = Indicateur(
        id_indicateur=None, nom="Taux de chomage", valeur=16.5, unite="%",
        periode="2024", region="Urbain", id_document=id_document, code_bds="I2790",
    )

    inserer_indicateur(conn, indicateur_national)
    inserer_indicateur(conn, indicateur_urbain)

    total = conn.execute("SELECT COUNT(*) FROM indicateur").fetchone()[0]
    assert total == 2
