"""
Tests du module Scraper. Utilisent des mocks pour ne pas dépendre d'un accès
réseau réel (important pour que les tests tournent aussi bien en local que dans
une éventuelle CI sans accès à hcp.ma).
"""
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from src.scraper import Scraper


def test_extraire_titre_depuis_h1():
    soup = BeautifulSoup("<html><body><h1>Titre de test</h1></body></html>", "lxml")
    assert Scraper._extraire_titre(soup) == "Titre de test"


def test_extraire_titre_repli_sur_meta_og_title():
    html = '<html><head><meta property="og:title" content="Titre meta"></head><body></body></html>'
    soup = BeautifulSoup(html, "lxml")
    assert Scraper._extraire_titre(soup) == "Titre meta"


def test_extraire_date_pattern_redige_le():
    soup = BeautifulSoup("<p>Redige le Lundi 29 Juin 2026 a 08:00</p>", "lxml")
    date = Scraper._extraire_date(soup)
    assert date is not None
    assert "2026" in date


@patch("src.scraper.requests.get")
def test_collecter_renvoie_un_document(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = "<html><body><h1>Article test</h1><p>Contenu.</p></body></html>"
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    scraper = Scraper(delay=0)
    docs = scraper.collecter(["https://www.hcp.ma/fake-article.html"], categorie="Economie")

    assert len(docs) == 1
    assert docs[0].titre == "Article test"
    assert docs[0].categorie == "Economie"
    assert docs[0].type == "html"
