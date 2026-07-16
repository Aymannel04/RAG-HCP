"""
Structures de données partagées entre les modules, alignées sur le MLD
(voir docs/conception_uml_v3.pdf, figure 3, et db/schema.sql).
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Document:
    """Correspond à la table `document` du schéma relationnel."""

    id_document: Optional[int]
    url: str
    titre: str
    date_publication: Optional[str]
    langue: str
    categorie: str
    type: str  # "html", "pdf", "xlsx" ou "api" (fiche synthétique BDS, voir ADR 0004)
    texte_brut: str = ""  # HTML/texte brut avant extraction (non persisté tel quel)


@dataclass
class Chunk:
    """Correspond à la table `chunk`. `embedding` est calculé par IndexeurTexte."""

    id_chunk: Optional[int]
    id_document: int
    texte: str
    position: int
    embedding: Optional[list] = None


@dataclass
class Indicateur:
    """Correspond à la table `indicateur`."""

    id_indicateur: Optional[int]
    nom: str
    valeur: float
    unite: Optional[str]
    periode: str
    region: Optional[str]
    id_document: int
    code_bds: Optional[str] = None  # code indicateur BDS si venant de l'API (ADR 0004)
