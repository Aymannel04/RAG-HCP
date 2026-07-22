"""
Module Extracteur — module 2 de l'architecture.
Role : nettoyer chaque type de document collecte (HTML, PDF, XLSX, DOCX) et separer
texte narratif et tableaux de chiffres (voir docs/fiche_cadrage_v4.pdf, section 8.1,
ADR 0003 sur l'ingestion PDF/XLSX, et ADR 0005 sur l'extension au DOCX).

L'extraction HTML n'est jamais indexee (ADR 0003 : le RAG s'appuie exclusivement sur
les pieces jointes PDF/XLSX/DOCX), conservee uniquement pour la retro-compatibilite du
chemin de code. PDF (pdfplumber), XLSX (openpyxl) et DOCX (python-docx) sont les trois
formats reellement exploites par le pipeline d'indexation.
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
        if document.type == "docx":
            return self._extraire_docx(document.texte_brut)
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

    @staticmethod
    def _extraire_docx(chemin_fichier: str) -> tuple[str, list[Tableau]]:
        # Import local : python-docx n'est necessaire que pour ce chemin de code.
        # Alias DocxDocument pour ne pas entrer en collision avec notre propre
        # classe Document (src/models.py).
        from docx import Document as DocxDocument

        docx = DocxDocument(chemin_fichier)

        paragraphes = [p.text.strip() for p in docx.paragraphs]
        texte_propre = "\n".join(p for p in paragraphes if p)

        tableaux: list[Tableau] = []
        for table in docx.tables:
            lignes = [[cellule.text.strip() for cellule in ligne.cells] for ligne in table.rows]
            lignes = [l for l in lignes if any(c for c in l)]
            if lignes:
                tableaux.append(lignes)

        return texte_propre, tableaux
