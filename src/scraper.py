"""
Module Scraper — module 1 de l'architecture (docs/conception_uml_v3.pdf, figure 4).
Rôle : collecter les pages HTML et PDF des catégories ciblées du site hcp.ma.

Statut : fonctionnel pour une première itération. Le sélecteur de date (_extraire_date)
est une heuristique basée sur le format observé sur les pages d'articles hcp.ma
("Rédigé le <date>") — à vérifier/ajuster une fois testé sur un échantillon réel plus large.
"""
from __future__ import annotations

import re
import time
import unicodedata
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .models import Document

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; HCP-RAG-Stage/0.1; usage academique interne)"}


class Scraper:
    """Collecte les pages et PDF des catégories ciblées du site hcp.ma."""

    def __init__(self, delay: float = 1.0):
        # Pause entre deux requêtes : reste raisonnable vis-à-vis du serveur (voir robots.txt).
        self.delay = delay

    def collecter(self, urls: list[str], categorie: str = "") -> list[Document]:
        """Récupère chaque URL de la liste et retourne les Document correspondants.

        Les échecs individuels (page indisponible, timeout) sont journalisés et ignorés
        plutôt que d'interrompre toute la collecte.
        """
        documents: list[Document] = []
        for url in urls:
            try:
                doc = self._recuperer_page(url, categorie)
                if doc:
                    documents.append(doc)
            except requests.RequestException as e:
                print(f"[Scraper] echec sur {url} : {e}")
            time.sleep(self.delay)
        return documents

    def _recuperer_page(self, url: str, categorie: str) -> Optional[Document]:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        return Document(
            id_document=None,
            url=url,
            titre=self._extraire_titre(soup),
            date_publication=self._extraire_date(soup),
            langue="fr",
            categorie=categorie,
            type="html",
            texte_brut=resp.text,  # extraction fine deleguee au module Extracteur
        )

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


if __name__ == "__main__":
    # Exemple d'usage manuel pour un premier test rapide en local.
    urls_test = [
        "https://www.hcp.ma/Situation-economique-nationale-au-premier-trimestre-2026_a4325.html",
    ]
    scraper = Scraper()
    for document in scraper.collecter(urls_test, categorie="Economie"):
        print(document.titre, "-", document.date_publication)
