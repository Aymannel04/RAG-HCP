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


# --- Regression : sur-detection de pieces jointes ---------------------------------
#
# Une sur-detection (liens de menu/sidebar pris a tort pour des pieces jointes) avait
# ete suspectee lors des premiers tests reels (voir rapport_sprint1.pdf). Verifiee le
# 17 juillet 2026 avec du vrai HTML reconstruit a partir de 4 pages hcp.ma recuperees
# via web_fetch (note de conjoncture, rapport d'enquete, page RGPH regionale a 8
# fichiers, bulletin trimestriel emploi) : sur ces 4 pages (338 liens <a> au total,
# menus + sidebar + pied de page inclus), 0 faux positif et 0 faux negatif. Les deux
# fixtures ci-dessous reproduisent les deux cas limites observes : un menu tres charge
# autour d'une seule vraie piece jointe, et une page a plusieurs pieces jointes reelles
# (qui ne doivent pas etre confondues avec de la sur-detection).

MENU_HCP_TYPE = """
<a href="https://www.hcp.ma/plugin/">Rechercher</a>
<a href="https://www.hcp.ma/">L'accueil</a>
<a href="https://www.hcp.ma/Economie_r327.html">Economie</a>
<a href="https://www.hcp.ma/Marche-du-travail_r423.html">Marche du travail</a>
<a href="https://www.hcp.ma/Population-demographie_r513.html">Population &amp; demographie</a>
<a href="https://www.hcp.ma/Bases-de-donnees_r631.html">Bases de donnees</a>
<a href="https://www.hcp.ma/downloads/?tag=Dernieres+parutions">Publications</a>
<a href="https://www.hcp.ma/Qui-sommes-nous_a3079.html">Tout sur HCP</a>
<a href="https://www.hcp.ma/glossary/Concepts-et-definitions_gi4113.html">Methodologies</a>
<a href="https://resultats2024.rgphapps.ma/">Resultats RGPH 2024</a>
<a href="https://applications-web.hcp.ma/DCN2022/Accueil.html">Agregats des comptes nationaux</a>
<a href="https://www.facebook.com/HCPMaroc/">Facebook</a>
<a href="http://www.youtube.com/user/marochcp">YouTube</a>
<a href="https://www.hcp.ma/Partenaires_r681.html">Nos partenaires</a>
<a href="https://idarati.ma/">Idarati</a>
"""


def test_detecter_pieces_jointes_pas_de_faux_positif_sur_menu_reel():
    # Fixture reconstruite depuis la vraie page "Note de conjoncture N 48" (17/07/2026) :
    # un menu tres charge (accueil, categories, bases de donnees, reseaux sociaux, liens
    # partenaires...) autour d'UNE seule vraie piece jointe.
    html = MENU_HCP_TYPE + '<a href="https://www.hcp.ma/file/247582/">Note de conjoncture N 48, Avril 2026</a>'
    soup = BeautifulSoup(html, "lxml")

    pieces = Scraper._detecter_pieces_jointes(soup)

    assert [href for href, _, _ in pieces] == ["https://www.hcp.ma/file/247582/"]


def test_detecter_pieces_jointes_plusieurs_vraies_pieces_jointes_pas_confondu_avec_sur_detection():
    # Fixture reconstruite depuis la vraie page RGPH 2024 Rabat-Sale-Kenitra (17/07/2026) :
    # 8 vraies pieces jointes (rapport regional + 7 prefectures/provinces), toutes
    # legitimement liees a l'article. Ce n'est PAS de la sur-detection.
    hrefs_reels = [
        "https://www.hcp.ma/file/248115", "https://www.hcp.ma/file/248114",
        "https://www.hcp.ma/file/248113", "https://www.hcp.ma/file/248112",
        "https://www.hcp.ma/file/248111/", "https://www.hcp.ma/file/248110/",
        "https://www.hcp.ma/file/248108/", "https://www.hcp.ma/file/248107/",
    ]
    html = MENU_HCP_TYPE + "\n".join(
        f'<a href="{href}">RGPH 2024, document {i}</a>' for i, href in enumerate(hrefs_reels)
    )
    soup = BeautifulSoup(html, "lxml")

    pieces = Scraper._detecter_pieces_jointes(soup)

    assert {href for href, _, _ in pieces} == set(hrefs_reels)
    assert len(pieces) == 8
