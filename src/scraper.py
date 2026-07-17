"""
Module Scraper — module 1 de l'architecture (docs/conception_uml_v3.pdf, figure 4).
Role : collecter les pages HTML des categories ciblees du site hcp.ma, ET les pieces
jointes (PDF / XLSX / DOCX) qu'elles referencent — voir ADR 0003
(docs/adr/0003-ingestion-pdf-xlsx.md) et ADR 0005 (docs/adr/0005-extension-docx.md).

Constat du 15 juillet 2026 (test reel sur 27 pages) : les pages HTML ne portent qu'un
resume court de l'article ; les vraies donnees (tableaux complets, series chiffrees)
sont dans des PDF/XLSX/DOCX telecharges depuis ces pages. Le Scraper doit donc detecter
et telecharger ces pieces jointes, pas seulement lire le HTML de la page elle-meme.

Statut : la collecte de page HTML + titre/date est fonctionnelle et testee en reel
(27/27). La detection/telechargement de pieces jointes a ete testee en reel une premiere
fois le 15 juillet : le telechargement marche (8000+ caracteres et de vrais tableaux de
donnees extraits d'un PDF reel), mais le premier test a remonte un vrai PDF en arabe
alors que le champ langue etait code en dur "fr" — corrige ci-dessous (detection de la
langue + filtrage arabe pour l'instant, voir TODO.md/support arabe en marge V1).
Le 17 juillet 2026, decouverte que certaines pages (IPC, IPPI) ne publient qu'en DOCX —
support ajoute (ADR 0005) plutot que de laisser ces publications sans contenu indexe.
"""
from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import Document

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; HCP-RAG-Stage/0.1; usage academique interne)"}

# Dossier de stockage des fichiers bruts telecharges (PDF/XLSX/DOCX). Volontairement
# hors du depot git (voir .gitignore : data/raw/) — trop volumineux pour etre versionne.
DOSSIER_BRUT = Path(__file__).resolve().parent.parent / "data" / "raw"

# Indices utilises pour reperer un lien de telechargement PDF/XLSX/DOCX sur une page
# hcp.ma. Heuristique construite a partir des pages observees le 15 juillet 2026 (notes
# de conjoncture) : le href ne contient pas toujours l'extension (ex.
# /attachment/2866603/, /file/247582/), mais le texte du lien, son attribut title, ou
# l'icone associee si. Le DOCX suit le meme schema (ex. page IPC : href
# "/attachment/2885946/", texte du lien "IPC_Mai 2026_Fr.docx" — verifie le 17/07/2026).
EXTENSIONS_XLSX = (".xlsx", ".xls")
EXTENSIONS_PDF = (".pdf",)
EXTENSIONS_DOCX = (".docx",)
INDICES_HREF_TELECHARGEMENT = ("/attachment/", "/file/")

# Indices de langue observes dans les noms de fichiers hcp.ma (ex. "Note Conj_Fr.pdf"
# vs "Note Conj_Ar.pdf"). Le projet cible le francais en priorite (fiche de cadrage,
# section 11) ; l'arabe est une extension volontairement hors scope V1 (TODO.md, marge).
INDICES_ARABE = ("_ar.", "_ar)", "(ar)", " ar)", "version ar", "arabe")
INDICES_FRANCAIS = ("_fr.", "_fr)", "(fr)", " fr)", "version fr", "francais", "français")


class Scraper:
    """Collecte les pages et pieces jointes (PDF/XLSX/DOCX) des categories ciblees de hcp.ma."""

    def __init__(
        self,
        delay: float = 1.0,
        telecharger_pieces_jointes: bool = True,
        inclure_arabe: bool = False,
    ):
        # Pause entre deux requetes : reste raisonnable vis-a-vis du serveur (voir robots.txt).
        self.delay = delay
        self.telecharger_pieces_jointes = telecharger_pieces_jointes
        # Hors scope V1 par defaut (voir fiche de cadrage section 11 + TODO.md marge) :
        # on ne telecharge pas les variantes arabes tant que ce n'est pas explicitement demande.
        self.inclure_arabe = inclure_arabe

    def collecter(self, urls: list[str], categorie: str = "") -> list[Document]:
        """Recupere chaque URL de la liste et retourne les Document correspondants
        (page HTML + pieces jointes PDF/XLSX/DOCX detectees sur chaque page).

        Les echecs individuels (page indisponible, timeout) sont journalises et ignores
        plutot que d'interrompre toute la collecte.
        """
        documents: list[Document] = []
        for url in urls:
            try:
                documents.extend(self._recuperer_page_et_pieces(url, categorie))
            except requests.RequestException as e:
                print(f"[Scraper] echec sur {url} : {e}")
            time.sleep(self.delay)
        return documents

    def _recuperer_page_et_pieces(self, url: str, categorie: str) -> list[Document]:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        titre = self._extraire_titre(soup)
        date_publication = self._extraire_date(soup)

        page = Document(
            id_document=None,
            url=url,
            titre=titre,
            date_publication=date_publication,
            langue="fr",
            categorie=categorie,
            type="html",
            texte_brut=resp.text,  # extraction fine deleguee au module Extracteur
        )
        resultats = [page]

        if self.telecharger_pieces_jointes:
            for href, type_fichier, langue in self._detecter_pieces_jointes(soup):
                if langue == "ar" and not self.inclure_arabe:
                    print(f"[Scraper] piece jointe arabe ignoree (hors scope V1) : {href}")
                    continue
                url_piece = urljoin(url, href)
                try:
                    doc_piece = self._telecharger_piece_jointe(
                        url_piece, type_fichier, langue, titre, date_publication, categorie
                    )
                    if doc_piece:
                        resultats.append(doc_piece)
                except requests.RequestException as e:
                    print(f"[Scraper] echec piece jointe {url_piece} : {e}")

        return resultats

    @staticmethod
    def _extraire_titre(soup: BeautifulSoup) -> str:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
        meta = soup.find("meta", attrs={"property": "og:title"})
        if meta and meta.get("content"):
            return meta["content"].strip()
        return ""

    @staticmethod
    def _extraire_date(soup: BeautifulSoup) -> Optional[str]:
        # Teste sur un vrai echantillon de 27 pages (15 juillet 2026) : 25/27 dates
        # trouvees du premier coup. Les 2 echecs venaient de pages ou "Rédigé le" est
        # encode en Unicode decompose (accent = caractere separe) plutot que compose,
        # ce qui cassait le match sur "dig[ée]". Normaliser en NFC avant la regex regle
        # ce cas sans rien retirer au comportement existant.
        texte = unicodedata.normalize("NFC", soup.get_text(" ", strip=True))
        m = re.search(r"R[ée]dig[ée] le ([^\.]+?\d{4}(?:\s*[àa]\s*\d{1,2}[:h]\d{2})?)", texte)
        return m.group(1).strip() if m else None

    @staticmethod
    def _detecter_langue(signal: str) -> str:
        if any(indice in signal for indice in INDICES_ARABE):
            return "ar"
        if any(indice in signal for indice in INDICES_FRANCAIS):
            return "fr"
        return "fr"  # a defaut d'indice explicite, on suppose francais (langue par defaut du site)

    @classmethod
    def _detecter_pieces_jointes(cls, soup: BeautifulSoup) -> list[tuple[str, str, str]]:
        """Repere les liens de telechargement PDF/XLSX/DOCX sur une page article, avec
        leur langue.

        Heuristique (affinee le 15 juillet apres un premier test reel qui a remonte un PDF
        arabe non identifie comme tel ; etendue le 17 juillet au DOCX, voir ADR 0005) : on
        regarde le href, le texte du lien, l'attribut title, et le src des images
        contenues dans le lien (icones "pdf.jpg", "icon_pdf.gif", "icon_docx.gif"
        observees sur le site), pour determiner a la fois le type de fichier et sa langue.
        """
        pieces: list[tuple[str, str, str]] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            texte = a.get_text(" ", strip=True).lower()
            titre_attr = (a.get("title") or "").lower()
            img_srcs = " ".join(img.get("src", "") for img in a.find_all("img")).lower()
            signal = " ".join([href.lower(), texte, titre_attr, img_srcs])
            langue = cls._detecter_langue(signal)

            if any(ext in signal for ext in EXTENSIONS_XLSX):
                pieces.append((href, "xlsx", langue))
            elif any(ext in signal for ext in EXTENSIONS_DOCX):
                pieces.append((href, "docx", langue))
            elif any(ext in signal for ext in EXTENSIONS_PDF):
                pieces.append((href, "pdf", langue))
            elif any(indice in href for indice in INDICES_HREF_TELECHARGEMENT):
                # Lien de telechargement sans extension visible (ex. /attachment/2866603/) :
                # on suppose PDF par defaut, le Content-Type reel corrigera si besoin
                # (voir _telecharger_piece_jointe).
                pieces.append((href, "pdf", langue))
        return pieces

    def _telecharger_piece_jointe(
        self,
        url_piece: str,
        type_suppose: str,
        langue: str,
        titre_page: str,
        date_publication: Optional[str],
        categorie: str,
    ) -> Optional[Document]:
        resp = requests.get(url_piece, headers=HEADERS, timeout=30)
        resp.raise_for_status()

        # Le Content-Type reel de la reponse prime sur la supposition faite a partir du lien.
        content_type = resp.headers.get("Content-Type", "").lower()
        if "spreadsheet" in content_type or "excel" in content_type:
            type_fichier = "xlsx"
        elif "wordprocessingml" in content_type or "msword" in content_type:
            type_fichier = "docx"
        elif "pdf" in content_type:
            type_fichier = "pdf"
        else:
            type_fichier = type_suppose

        # Verification du contenu reel (nombres magiques), pas seulement du Content-Type :
        # l'heuristique de detection de liens est large et attrape parfois des liens qui ne
        # menent pas vraiment a un PDF/XLSX/DOCX (page d'erreur, redirection...). Sans ce
        # controle, un fichier invalide fait planter pdfplumber/openpyxl/python-docx plus
        # tard dans le pipeline (vu en reel le 15 juillet : "PDFSyntaxError: No /Root
        # object! - Is this really a PDF?" ; et le 17 juillet : des .docx recuperes AVANT
        # ce fix trainaient dans data/raw/ sous une fausse extension .pdf).
        if not self._contenu_semble_valide(resp.content, type_fichier):
            print(
                f"[Scraper] contenu invalide pour {url_piece} "
                f"(pas un vrai {type_fichier} malgre le lien) — ignore"
            )
            return None

        DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
        nom_fichier = self._nom_fichier_piece(url_piece, type_fichier)
        chemin = DOSSIER_BRUT / nom_fichier
        chemin.write_bytes(resp.content)

        return Document(
            id_document=None,
            url=url_piece,
            titre=titre_page,  # a affiner : pas toujours le meme titre que la page parente
            date_publication=date_publication,
            langue=langue,
            categorie=categorie,
            type=type_fichier,
            texte_brut=str(chemin),  # chemin local du fichier brut, lu par Extracteur
        )

    @staticmethod
    def _contenu_semble_valide(contenu: bytes, type_fichier: str) -> bool:
        """Verifie les nombres magiques du fichier telecharge plutot que de se fier
        uniquement au Content-Type (parfois absent ou trompeur sur des liens indirects).

        XLSX et DOCX sont tous deux des archives ZIP (signature "PK") : la seule
        signature ne suffit pas a les distinguer. Decouverte concrete le 17 juillet 2026
        en diagnostiquant des fichiers .docx recuperes (avant ce fix) sous une fausse
        extension .pdf dans data/raw/ — on verifie donc en plus la presence du dossier
        interne caracteristique du format attendu (xl/ pour XLSX, word/ pour DOCX).
        """
        if type_fichier == "pdf":
            return contenu[:5] == b"%PDF-"
        if type_fichier in ("xlsx", "docx"):
            if contenu[:2] != b"PK":
                return False
            dossier_attendu = b"xl/" if type_fichier == "xlsx" else b"word/"
            return dossier_attendu in contenu
        return True

    @staticmethod
    def _nom_fichier_piece(href: str, type_fichier: str) -> str:
        base = re.sub(r"[^\w\-]", "_", href.strip("/").split("/")[-1]) or "piece"
        extensions_par_type = {"xlsx": ".xlsx", "docx": ".docx"}
        extension = extensions_par_type.get(type_fichier, ".pdf")
        return base if base.endswith(extension) else base + extension


if __name__ == "__main__":
    # Exemple d'usage manuel pour un premier test rapide en local.
    urls_test = [
        "https://www.hcp.ma/Situation-economique-nationale-au-premier-trimestre-2026_a4325.html",
    ]
    scraper = Scraper()
    for document in scraper.collecter(urls_test, categorie="Economie"):
        print(document.type, "-", document.langue, "-", document.titre, "-", document.date_publication)
