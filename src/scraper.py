"""
Module Scraper — module 1 de l'architecture (docs/conception_uml_v3.pdf, figure 4).
Role : collecter les pages HTML des categories ciblees du site hcp.ma, ET les pieces
jointes (PDF / XLSX) qu'elles referencent — voir ADR 0003
(docs/adr/0003-ingestion-pdf-xlsx.md).

Constat du 15 juillet 2026 (test reel sur 27 pages) : les pages HTML ne portent qu'un
resume court de l'article ; les vraies donnees (tableaux complets, series chiffrees)
sont dans des PDF/XLSX telecharges depuis ces pages. Le Scraper doit donc detecter et
telecharger ces pieces jointes, pas seulement lire le HTML de la page elle-meme.

Statut : la collecte de page HTML + titre/date est fonctionnelle et testee en reel
(27/27). La detection/telechargement de pieces jointes est ecrite mais PAS ENCORE
testee en conditions reelles (pas d'acces reseau vers hcp.ma dans ce sandbox) — a
valider en priorite avant de s'appuyer dessus pour le Sprint 2.
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

# Dossier de stockage des fichiers bruts telecharges (PDF/XLSX). Volontairement hors
# du depot git (voir .gitignore : data/raw/) — trop volumineux pour etre versionne.
DOSSIER_BRUT = Path(__file__).resolve().parent.parent / "data" / "raw"

# Indices utilises pour reperer un lien de telechargement PDF/XLSX sur une page hcp.ma.
# Heuristique construite a partir des pages observees le 15 juillet 2026 (notes de
# conjoncture) : le href ne contient pas toujours l'extension (ex. /attachment/2866603/,
# /file/247582/), mais le texte du lien, son attribut title, ou l'icone associee si.
EXTENSIONS_XLSX = (".xlsx", ".xls")
EXTENSIONS_PDF = (".pdf",)
INDICES_HREF_TELECHARGEMENT = ("/attachment/", "/file/")


class Scraper:
    """Collecte les pages et pieces jointes (PDF/XLSX) des categories ciblees de hcp.ma."""

    def __init__(self, delay: float = 1.0, telecharger_pieces_jointes: bool = True):
        # Pause entre deux requetes : reste raisonnable vis-a-vis du serveur (voir robots.txt).
        self.delay = delay
        self.telecharger_pieces_jointes = telecharger_pieces_jointes

    def collecter(self, urls: list[str], categorie: str = "") -> list[Document]:
        """Recupere chaque URL de la liste et retourne les Document correspondants
        (page HTML + pieces jointes PDF/XLSX detectees sur chaque page).

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
            for href, type_fichier in self._detecter_pieces_jointes(soup):
                url_piece = urljoin(url, href)
                try:
                    doc_piece = self._telecharger_piece_jointe(
                        url_piece, type_fichier, titre, date_publication, categorie
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
    def _detecter_pieces_jointes(soup: BeautifulSoup) -> list[tuple[str, str]]:
        """Repere les liens de telechargement PDF/XLSX sur une page article.

        Heuristique (a affiner une fois testee en reel, voir docstring du module) :
        on regarde le href, le texte du lien, l'attribut title, et le src des images
        contenues dans le lien (icones "pdf.jpg", "icon_pdf.gif" observees sur le site).
        """
        pieces: list[tuple[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            texte = a.get_text(" ", strip=True).lower()
            titre_attr = (a.get("title") or "").lower()
            img_srcs = " ".join(img.get("src", "") for img in a.find_all("img")).lower()
            signal = " ".join([href.lower(), texte, titre_attr, img_srcs])

            if any(ext in signal for ext in EXTENSIONS_XLSX):
                pieces.append((href, "xlsx"))
            elif any(ext in signal for ext in EXTENSIONS_PDF):
                pieces.append((href, "pdf"))
            elif any(indice in href for indice in INDICES_HREF_TELECHARGEMENT):
                # Lien de telechargement sans extension visible (ex. /attachment/2866603/) :
                # on suppose PDF par defaut, le Content-Type reel corrigera si besoin
                # (voir _telecharger_piece_jointe).
                pieces.append((href, "pdf"))
        return pieces

    def _telecharger_piece_jointe(
        self,
        url_piece: str,
        type_suppose: str,
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
        elif "pdf" in content_type:
            type_fichier = "pdf"
        else:
            type_fichier = type_suppose

        DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
        nom_fichier = self._nom_fichier_piece(url_piece, type_fichier)
        chemin = DOSSIER_BRUT / nom_fichier
        chemin.write_bytes(resp.content)

        return Document(
            id_document=None,
            url=url_piece,
            titre=titre_page,  # a affiner : pas toujours le meme titre que la page parente
            date_publication=date_publication,
            langue="fr",
            categorie=categorie,
            type=type_fichier,
            texte_brut=str(chemin),  # chemin local du fichier brut, lu par Extracteur
        )

    @staticmethod
    def _nom_fichier_piece(href: str, type_fichier: str) -> str:
        base = re.sub(r"[^\w\-]", "_", href.strip("/").split("/")[-1]) or "piece"
        extension = ".xlsx" if type_fichier == "xlsx" else ".pdf"
        return base if base.endswith(extension) else base + extension


if __name__ == "__main__":
    # Exemple d'usage manuel pour un premier test rapide en local.
    urls_test = [
        "https://www.hcp.ma/Situation-economique-nationale-au-premier-trimestre-2026_a4325.html",
    ]
    scraper = Scraper()
    for document in scraper.collecter(urls_test, categorie="Economie"):
        print(document.type, "-", document.titre, "-", document.date_publication)
