"""
Module Scraper — module 1 de l'architecture (docs/conception_uml_v3.pdf, figure 4).
Role : collecter les pages HTML des categories ciblees du site hcp.ma, ET les pieces
jointes (PDF / XLSX / DOCX) qu'elles referencent — voir ADR 0003
(docs/adr/0003-ingestion-pdf-xlsx.md) et ADR 0005 (docs/adr/0005-extension-docx.md).

Les pages HTML de hcp.ma ne portent qu'un resume court de l'article ; les vraies
donnees (tableaux complets, series chiffrees) sont dans des PDF/XLSX/DOCX telecharges
depuis ces pages. Le Scraper detecte et telecharge ces pieces jointes en plus du HTML
de la page elle-meme, et filtre par langue (francais par defaut, arabe hors perimetre
V1, voir fiche de cadrage section 11).
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
# hcp.ma. Le href ne contient pas toujours l'extension (ex. /attachment/2866603/,
# /file/247582/) : on se rabat alors sur le texte du lien, son attribut title, ou
# l'icone associee.
EXTENSIONS_XLSX = (".xlsx", ".xls")
EXTENSIONS_PDF = (".pdf",)
EXTENSIONS_DOCX = (".docx",)
INDICES_HREF_TELECHARGEMENT = ("/attachment/", "/file/")

# Indices de langue observes dans les noms de fichiers hcp.ma (ex. "Note Conj_Fr.pdf"
# vs "Note Conj_Ar.pdf"). Le projet cible le francais en priorite (fiche de cadrage,
# section 11) ; l'arabe est une extension volontairement hors scope V1 (TODO.md, marge).
INDICES_ARABE = ("_ar.", "_ar)", "(ar)", " ar)", "version ar", "arabe")
INDICES_FRANCAIS = ("_fr.", "_fr)", "(fr)", " fr)", "version fr", "francais", "français")

# Motif d'URL des pages article sur hcp.ma (ex. ".../Situation-economique-nationale...
# _a4325.html"), stable sur l'ensemble du site — sert a distinguer un lien d'article
# d'un lien de menu/navigation sur une page listing (voir ADR 0006).
PATTERN_URL_ARTICLE = re.compile(r"_a\d+\.html$")

# Parametre de pagination observe sur les pages listing (ex. "?start=5&show=&order=").
# Le pas entre deux pages n'est pas code en dur : il est deduit des liens de pagination
# presents sur la page elle-meme (voir _increments_pagination), pour rester robuste si
# hcp.ma change ce nombre.
PATTERN_PARAM_START = re.compile(r"[?&]start=(\d+)")


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

    def collecter_depuis_listing(
        self, url_listing: str, categorie: str = "", max_pages: Optional[int] = None
    ) -> list[Document]:
        """Decouvre les URLs d'articles sur une page listing (ex.
        "Publications-Marche-du-travail_r425.html") puis les collecte via `collecter()`
        (voir ADR 0006, docs/adr/0006-decouverte-automatique-publications.md).

        `max_pages` controle la portee de la decouverte :
        - `max_pages=1` : seulement la 1ere page (les publications les plus recentes,
          triees par hcp.ma du plus recent au plus ancien) — usage "fraicheur", pense
          pour une execution reguliere qui detecte les nouvelles publications.
        - `max_pages=None` : toutes les pages du listing — usage "historique", pense
          pour une execution ponctuelle qui elargit la couverture du corpus.

        La deduplication des documents deja connus n'est pas geree ici : elle repose
        sur la contrainte `document.url UNIQUE` de `db/schema.sql` au moment de
        l'insertion en base (voir ADR 0006).
        """
        urls = self.decouvrir_urls_liste(url_listing, max_pages=max_pages)
        return self.collecter(urls, categorie=categorie)

    def decouvrir_urls_liste(self, url_listing: str, max_pages: Optional[int] = None) -> list[str]:
        """Parcourt une page listing paginee de hcp.ma et retourne les URLs d'articles
        trouvees (voir ADR 0006).

        Recupere d'abord la page 1, en extrait les URLs d'articles et les paliers de
        pagination (`?start=N`) presents sur la page. Si `max_pages` limite le nombre
        de pages a parcourir (ex. `max_pages=1` pour ne lire que la page 1), les paliers
        au-dela sont ignores. S'arrete tot si une page ne remonte aucune nouvelle URL
        d'article (page vide ou fin du listing atteinte).
        """
        resp = requests.get(url_listing, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        urls_trouvees: list[str] = []
        vues = set()
        for url in self._filtrer_urls_arabe(self._extraire_urls_articles(soup, url_listing)):
            if url not in vues:
                vues.add(url)
                urls_trouvees.append(url)

        paliers = self._increments_pagination(soup)
        if max_pages is not None:
            paliers = paliers[: max(0, max_pages - 1)]

        for palier in paliers:
            url_page = f"{url_listing}?start={palier}&show=&order="
            time.sleep(self.delay)
            try:
                resp = requests.get(url_page, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"[Scraper] echec page listing {url_page} : {e}")
                continue
            soup_page = BeautifulSoup(resp.text, "lxml")
            nouvelles = [
                u
                for u in self._filtrer_urls_arabe(self._extraire_urls_articles(soup_page, url_listing))
                if u not in vues
            ]
            if not nouvelles:
                break  # fin du listing atteinte (ou page vide) : inutile de continuer
            for url in nouvelles:
                vues.add(url)
                urls_trouvees.append(url)

        return urls_trouvees

    def _filtrer_urls_arabe(self, urls_avec_langue: list[tuple[str, str]]) -> list[str]:
        """Ecarte les URLs d'articles detectees comme etant en arabe, sauf si
        `self.inclure_arabe` (meme regle que pour les pieces jointes, voir
        `collecter`/`_recuperer_page_et_pieces` — hors scope V1, fiche de cadrage
        section 11). La decouverte automatique (ADR 0006) remonte les pages listing
        dans leur ordre reel, qui incluent des versions arabes de certains articles
        (ex. "...-version-Ar_a4217.html", titre de lien "(version Ar)") a ecarter
        comme n'importe quelle piece jointe arabe.
        """
        urls: list[str] = []
        for url, langue in urls_avec_langue:
            if langue == "ar" and not self.inclure_arabe:
                print(f"[Scraper] page article arabe ignoree (hors scope V1) : {url}")
                continue
            urls.append(url)
        return urls

    @staticmethod
    def _extraire_urls_articles(soup: BeautifulSoup, url_page: str) -> list[tuple[str, str]]:
        """Repere les liens d'articles sur une page listing, avec leur langue detectee.

        Deux filtres combines, pas un seul (voir ADR 0006) :
        1. Le lien doit etre dans un titre (`<h2>`-`<h5>`) : sur les pages listing
           reelles verifiees (ex. Publications-Marche-du-travail_r425.html), chaque
           article apparait sous la forme "### [titre](url) - date" — le titre est
           dans un titre de section, contrairement aux liens de menu/pied de page.
        2. L'URL doit suivre le motif stable des pages article de hcp.ma
           (`PATTERN_URL_ARTICLE`, ex. "..._a4325.html").
        Le filtre 1 seul aurait suffi a eliminer le faux positif du menu "Tout sur HCP"
        (-> Qui-sommes-nous_a3079.html, hors titre mais dont l'URL suit quand meme le
        motif _aXXX.html) ; les deux filtres combines sont plus robustes qu'un seul en
        cas de gabarit de page legerement different.

        La langue est detectee via `_detecter_langue` (meme heuristique que pour les
        pieces jointes), sur un signal combinant l'URL et le texte du lien — ex.
        "(version Ar)" dans le texte suffit a detecter l'arabe meme quand l'URL seule
        ne le signale pas clairement.
        """
        resultats: list[tuple[str, str]] = []
        vues = set()
        for titre in soup.find_all(["h2", "h3", "h4", "h5"]):
            for a in titre.find_all("a", href=True):
                url_absolue = urljoin(url_page, a["href"].split("?")[0])
                if not PATTERN_URL_ARTICLE.search(url_absolue) or url_absolue in vues:
                    continue
                texte = a.get_text(" ", strip=True).lower()
                titre_attr = (a.get("title") or "").lower()
                signal = " ".join([url_absolue.lower(), texte, titre_attr])
                langue = Scraper._detecter_langue(signal)
                vues.add(url_absolue)
                resultats.append((url_absolue, langue))
        return resultats

    @staticmethod
    def _increments_pagination(soup: BeautifulSoup) -> list[int]:
        """Deduit les paliers de pagination (`?start=N`) presents sur une page listing,
        tries par ordre croissant. Le pas entre deux pages n'est pas suppose fixe :
        chaque palier est lu directement dans les liens de pagination reels (voir
        ADR 0006)."""
        paliers = set()
        for a in soup.find_all("a", href=True):
            m = PATTERN_PARAM_START.search(a["href"])
            if m:
                paliers.add(int(m.group(1)))
        return sorted(p for p in paliers if p > 0)

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
        # Certaines pages encodent "Rédigé le" en Unicode decompose (accent = caractere
        # separe) plutot que compose, ce qui casse le match sur "dig[ée]" sans
        # normalisation prealable en NFC.
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

        On regarde le href, le texte du lien, l'attribut title, et le src des images
        contenues dans le lien (icones "pdf.jpg", "icon_pdf.gif", "icon_docx.gif"
        observees sur le site), pour determiner a la fois le type de fichier et sa
        langue (voir ADR 0005 pour le support DOCX).
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
        # l'heuristique de detection de liens est large et attrape parfois des liens qui
        # ne menent pas vraiment a un PDF/XLSX/DOCX (page d'erreur, redirection...). Sans
        # ce controle, un fichier invalide fait planter pdfplumber/openpyxl/python-docx
        # plus tard dans le pipeline.
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
        signature ne suffit pas a les distinguer. On verifie donc en plus la presence
        du dossier interne caracteristique du format attendu (xl/ pour XLSX, word/ pour
        DOCX).
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
