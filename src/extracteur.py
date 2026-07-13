"""
Module Extracteur — module 2 de l'architecture.
Rôle : nettoyer le HTML et séparer texte narratif et tableaux de chiffres
(voir docs/fiche_cadrage_v4.pdf, section 8.1).

Statut : extraction HTML fonctionnelle. Extraction PDF (pdfplumber) à ajouter
en semaine 2 pour les notes d'information jointes en PDF.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from .models import Document


class Extracteur:
    """Extrait le texte propre et les tableaux de chiffres d'un Document brut."""

    def extraire(self, document: Document) -> tuple[str, list[list[list[str]]]]:
        """Retourne (texte_propre, tableaux) à partir du contenu brut du document.

        texte_propre : texte narratif nettoyé, prêt pour le chunking (IndexeurTexte).
        tableaux : liste de tableaux extraits (chacun une liste de lignes de cellules),
                   à transmettre à ConstructeurIndicateurs.
        """
        if document.type == "pdf":
            raise NotImplementedError(
                "Extraction PDF a implementer (pdfplumber) - semaine 2, voir TODO.md"
            )
        return self._extraire_html(document.texte_brut)

    @staticmethod
    def _extraire_html(html: str) -> tuple[str, list[list[list[str]]]]:
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        paragraphes = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        texte_propre = "\n".join(p for p in paragraphes if p)

        tableaux: list[list[list[str]]] = []
        for table in soup.find_all("table"):
            lignes = []
            for tr in table.find_all("tr"):
                cellules = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cellules:
                    lignes.append(cellules)
            if lignes:
                tableaux.append(lignes)

        return texte_propre, tableaux
