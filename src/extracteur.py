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

# Garde-fou anti-texte-illisible : certains PDF a mise en page dense ou police legacy
# (ex. "Les Cahiers du Plan N 33", police arabe legacy) font ressortir de pdfplumber du
# texte qui n'est pas du texte -- des symboles/glyphes bruts sans rapport avec le
# contenu reel. Rien ne signale ce cas a priori (pas d'erreur, pas d'exception -- juste
# une chaine de caracteres qui a la forme d'un texte) : le seul moyen de le detecter
# est heuristique, sur la forme du texte extrait lui-meme.
#
# Heuristique choisie : dans un texte francais normal, la grande majorite des
# caracteres non-espace sont des lettres (accents compris) -- le reste (chiffres,
# ponctuation) reste minoritaire. Un texte illisible issu d'un mauvais mapping de
# police tombe nettement en dessous de ce ratio (glyphes/symboles qui ne sont pas
# des lettres au sens Unicode). Seuil choisi large (0.5) pour eviter de rejeter a
# tort une page dense en chiffres/tableaux legitime -- vise seulement le cas net de
# symboles bruts, pas un simple appauvrissement de texte.
SEUIL_RATIO_ALPHA = 0.5
# Sous ce nombre de caracteres, la mesure n'est pas fiable (trop peu de signal) --
# la page est conservee par defaut plutot que rejetee sur un echantillon trop court.
LONGUEUR_MIN_MESURE = 30

# Limite connue et assumee : ce garde-fou detecte et exclut le texte illisible, il ne
# le corrige pas -- le document reste dans le corpus mais sans son texte narratif
# (ex. "Chiffres cles, 2026", brochure dense bilingue AR/EN, deja illisible pour
# pdfplumber). Piste de solution identifiee mais non implementee (cout/risque juges
# trop eleves pour un cas isole) : rendre chaque page en image et passer par un moteur
# OCR (ex. Tesseract) au lieu de lire les codes de caracteres du PDF -- contournerait
# le mauvais mapping de police en lisant les glyphes visuellement, comme le ferait un
# humain. A explorer si ce type de document devient frequent dans le corpus.



def _texte_lisible(texte: str) -> bool:
    """Retourne False si `texte` ressemble a des symboles/glyphes bruts plutot qu'a
    du texte reel (voir SEUIL_RATIO_ALPHA ci-dessus). Une chaine vide ou trop courte
    est consideree lisible par defaut (rien a rejeter, pas assez de signal)."""
    caracteres_non_espace = [c for c in texte if not c.isspace()]
    if len(caracteres_non_espace) < LONGUEUR_MIN_MESURE:
        return True
    nb_alpha = sum(1 for c in caracteres_non_espace if c.isalpha())
    ratio_alpha = nb_alpha / len(caracteres_non_espace)
    return ratio_alpha >= SEUIL_RATIO_ALPHA


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
                if texte_page and _texte_lisible(texte_page):
                    morceaux_texte.append(texte_page)
                # Page rejetee silencieusement si illisible (voir _texte_lisible) :
                # ses eventuels tableaux restent extraits normalement ci-dessous --
                # le garde-fou ne vise que le texte narratif destine au chunking, pas
                # les tableaux de chiffres (structure differente, propre a
                # ConstructeurIndicateurs, jamais concernee par ce probleme de police).

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
