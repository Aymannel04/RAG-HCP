"""
Module Extracteur — module 2 de l'architecture.
Role : nettoyer chaque type de document collecte (HTML, PDF, XLSX) et separer texte
narratif et tableaux de chiffres (voir docs/fiche_cadrage_v4.pdf, section 8.1, et
ADR 0003 sur l'ingestion PDF/XLSX).

Statut :
- HTML : fonctionnel, mais la strategie "tous les <p>, tous les <table>" s'est revelee
  insuffisante sur un vrai gabarit hcp.ma (menus rendus en <table>, corps d'article pas
  toujours dans des <p>) — a retravailler une fois qu'on aura un extrait de HTML reel
  (voir echange du 15 juillet 2026).
- PDF : implemente avec pdfplumber. PAS ENCORE teste sur un vrai PDF hcp.ma.
- XLSX : implemente avec openpyxl. PAS ENCORE teste sur un vrai fichier hcp.ma.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from .models import Document

Tableau = list[list[str]]


class Extracteur:
    """Extrait le texte propre et les tableaux de chiffres d'un Document brut."""

    def extraire(self, document: Document) -> tuple[str, list[Tableau]]:
        """Retourne (texte_propre, tableaux) a partir du contenu brut du document.

        texte_propre : texte narratif nettoye, pret pour le chunking (IndexeurTexte).
        tableaux : liste de tableaux extraits (chacun une liste de lignes de cellules),
                   a transmettre a ConstructeurIndicateurs.
        """
        if document.type == "pdf":
            return self._extraire_pdf(document.texte_brut)
        if document.type == "xlsx":
            return self._extraire_xlsx(document.texte_brut)
        return self._extraire_html(document.texte_brut)

    @staticmethod
    def _extraire_html(html: str) -> tuple[str, list[Tableau]]:
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        paragraphes = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        texte_propre = "\n".join(p for p in paragraphes if p)

        tableaux: list[Tableau] = []
        for table in soup.find_all("table"):
            lignes = []
            for tr in table.find_all("tr"):
                cellules = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cellules:
                    lignes.append(cellules)
            if lignes:
                tableaux.append(lignes)

        return texte_propre, tableaux

    @staticmethod
    def _extraire_pdf(chemin_fichier: str) -> tuple[str, list[Tableau]]:
        # Import local : pdfplumber n'est necessaire que pour ce chemin de code.
        import pdfplumber

        morceaux_texte: list[str] = []
        tableaux: list[Tableau] = []

        with pdfplumber.open(chemin_fichier) as pdf:
            for page in pdf.pages:
                texte_page = page.extract_text()
                if texte_page:
                    morceaux_texte.append(texte_page)

                for table in page.extract_tables():
                    lignes = [
                        [cellule.strip() if cellule else "" for cellule in ligne]
                        for ligne in table
                        if ligne
                    ]
                    if lignes:
                        tableaux.append(lignes)

        texte_propre = "\n".join(morceaux_texte)
        return texte_propre, tableaux

    @staticmethod
    def _extraire_xlsx(chemin_fichier: str) -> tuple[str, list[Tableau]]:
        # Import local : openpyxl n'est necessaire que pour ce chemin de code.
        from openpyxl import load_workbook

        classeur = load_workbook(chemin_fichier, read_only=True, data_only=True)
        tableaux: list[Tableau] = []

        for feuille in classeur.worksheets:
            lignes: Tableau = []
            for ligne in feuille.iter_rows(values_only=True):
                cellules = ["" if v is None else str(v) for v in ligne]
                if any(c for c in cellules):
                    lignes.append(cellules)
            if lignes:
                tableaux.append(lignes)

        # Un XLSX est de la donnee pure : pas de texte narratif a chunker, tout part
        # vers ConstructeurIndicateurs via les tableaux.
        return "", tableaux
