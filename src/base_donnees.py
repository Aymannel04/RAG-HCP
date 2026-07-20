"""
Module base_donnees — utilitaires de connexion et d'insertion en base SQLite
(db/schema.sql). Fait le lien entre les objets Python (Document, Chunk, Indicateur,
voir src/models.py) et les tables relationnelles, en respectant les règles de
dédoublonnage déjà actées dans le projet :

- `document.url` UNIQUE (voir ADR 0001, réutilisé par ADR 0006 pour la découverte
  automatique) : `inserer_document` renvoie l'id existant si l'URL est déjà connue,
  plutôt que d'échouer ou de dupliquer.
- `indicateur` : pas de contrainte UNIQUE dans le schéma (voir db/schema.sql), mais un
  même indicateur/période/région peut être revu d'une exécution à l'autre du
  pré-remplissage BDS (ADR 0004, exécution régulière prévue) : `inserer_indicateur`
  applique un upsert applicatif sur (nom, periode, region, code_bds) — une seule ligne,
  mise à jour si déjà présente, plutôt que des doublons qui s'accumulent à chaque run.

Statut : implémenté, testé (base SQLite temporaire + vrai schema.sql). Utilisé par
`scripts/indexer_documents.py` et `scripts/preremplir_indicateurs_bds.py`.
"""
from __future__ import annotations

import array
import sqlite3
from pathlib import Path
from typing import Optional

from .models import Chunk, Document, Indicateur

CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
CHEMIN_DB_DEFAUT = Path(__file__).resolve().parent.parent / "data" / "hcp_rag.db"


def connecter(chemin: Optional[Path] = None) -> sqlite3.Connection:
    """Ouvre une connexion SQLite et applique le schéma (`CREATE TABLE IF NOT EXISTS`,
    donc sans danger sur une base déjà initialisée). `chemin=None` utilise le fichier
    par défaut du projet (`data/hcp_rag.db`, gitignoré comme tout `*.db`)."""
    chemin_reel = Path(chemin) if chemin else CHEMIN_DB_DEFAUT
    chemin_reel.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(chemin_reel))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(CHEMIN_SCHEMA.read_text(encoding="utf-8"))
    return conn


def inserer_document(conn: sqlite3.Connection, document: Document) -> int:
    """Insère `document`, ou renvoie l'id existant si son URL est déjà connue
    (contrainte `document.url` UNIQUE, voir ADR 0001/0006)."""
    existant = conn.execute(
        "SELECT id_document FROM document WHERE url = ?", (document.url,)
    ).fetchone()
    if existant:
        return existant[0]

    curseur = conn.execute(
        """INSERT INTO document (url, titre, date_publication, langue, categorie, type)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            document.url,
            document.titre,
            document.date_publication,
            document.langue,
            document.categorie,
            document.type,
        ),
    )
    conn.commit()
    return curseur.lastrowid


def inserer_chunk(conn: sqlite3.Connection, chunk: Chunk) -> int:
    """Insère `chunk`. L'embedding (liste de floats) est sérialisé en BLOB via le
    module standard `array` (float32, compact, sans dépendance externe) — voir
    `_embedding_vers_blob` / `blob_vers_embedding`."""
    embedding_blob = _embedding_vers_blob(chunk.embedding) if chunk.embedding else None
    curseur = conn.execute(
        """INSERT INTO chunk (id_document, texte, position, embedding)
           VALUES (?, ?, ?, ?)""",
        (chunk.id_document, chunk.texte, chunk.position, embedding_blob),
    )
    conn.commit()
    return curseur.lastrowid


def inserer_indicateur(conn: sqlite3.Connection, indicateur: Indicateur) -> int:
    """Insère `indicateur`, ou met à jour la ligne existante si (nom, periode, region,
    code_bds) correspond déjà à une ligne en base (upsert applicatif — voir docstring
    du module)."""
    existant = conn.execute(
        """SELECT id_indicateur FROM indicateur
           WHERE nom = ? AND periode = ? AND region IS ? AND code_bds IS ?""",
        (indicateur.nom, indicateur.periode, indicateur.region, indicateur.code_bds),
    ).fetchone()

    if existant:
        conn.execute(
            "UPDATE indicateur SET valeur = ?, unite = ?, id_document = ? WHERE id_indicateur = ?",
            (indicateur.valeur, indicateur.unite, indicateur.id_document, existant[0]),
        )
        conn.commit()
        return existant[0]

    curseur = conn.execute(
        """INSERT INTO indicateur (nom, valeur, unite, periode, region, id_document, code_bds)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            indicateur.nom,
            indicateur.valeur,
            indicateur.unite,
            indicateur.periode,
            indicateur.region,
            indicateur.id_document,
            indicateur.code_bds,
        ),
    )
    conn.commit()
    return curseur.lastrowid


def _embedding_vers_blob(embedding: list[float]) -> bytes:
    return array.array("f", embedding).tobytes()


def blob_vers_embedding(blob: bytes) -> list[float]:
    tampon: "array.array[float]" = array.array("f")
    tampon.frombytes(blob)
    return list(tampon)
