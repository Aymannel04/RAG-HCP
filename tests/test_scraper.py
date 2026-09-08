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
    assert date == "2026-06-29"  # converti en ISO 8601 (demande encadrante, 08/09)


def test_iso_depuis_date_jjmmaaaa():
    assert Scraper._iso_depuis_date_jjmmaaaa("06/08/2026") == "2026-08-06"


def test_iso_depuis_date_fr_texte_non_reconnu_renvoie_none():
    # Repli attendu par les appelants (_extraire_date/_extraire_entrees_telechargements) :
    # la chaine brute est alors conservee plutot que de perdre la date.
    assert Scraper._iso_depuis_date_fr("date illisible") is None


# --- Correctif du 08/09 : filtre arabe qui excluait aussi les documents bilingues ----
#
# Signale par l'encadrante : un document bilingue (mention "Version Ar / Version Fr"
# dans un meme bloc/tooltip, ou "AR / FR" dans le titre) contient un indice arabe
# (INDICES_ARABE) et se faisait donc exclure comme un document purement arabe, alors
# qu'il contient du contenu francais exploitable. Seul un signal SANS indice francais
# doit desormais etre classe "ar".

def test_detecter_langue_bilingue_ar_fr_conserve_comme_francais():
    assert Scraper._detecter_langue("note (version ar / version fr)") == "fr"


def test_detecter_langue_arabe_seul_toujours_exclu():
    assert Scraper._detecter_langue("rapport (version ar)") == "ar"


def test_detecter_langue_francais_seul_inchange():
    assert Scraper._detecter_langue("rapport_fr.pdf") == "fr"


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
# ete suspectee lors des premiers tests reels (voir rapport_sprint1.pdf). Verifiee avec
# du vrai HTML reconstruit a partir de 4 pages hcp.ma reelles (note de conjoncture,
# rapport d'enquete, page RGPH regionale a 8 fichiers, bulletin trimestriel emploi) :
# sur ces 4 pages (338 liens <a> au total, menus + sidebar + pied de page inclus),
# 0 faux positif et 0 faux negatif. Les deux fixtures ci-dessous reproduisent les deux
# cas limites observes : un menu tres charge autour d'une seule vraie piece jointe, et
# une page a plusieurs pieces jointes reelles (qui ne doivent pas etre confondues avec
# de la sur-detection).

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


# --- ADR 0005 : support DOCX --------------------------------------------------------
#
# Les pages IPC/IPPI (categorie Economie) ne publient leur note mensuelle qu'en .docx,
# jamais en PDF/XLSX. Href sans extension visible (/attachment/{id}/), extension
# uniquement dans le texte du lien — meme schema que les PDF/XLSX. Fixture reconstruite
# depuis la vraie page IPC Mai 2026.

def test_detecter_pieces_jointes_reconnait_le_docx():
    html = (
        MENU_HCP_TYPE
        + '<a href="https://www.hcp.ma/attachment/2885946/">IPC_Mai 2026_Fr.docx</a>'
    )
    soup = BeautifulSoup(html, "lxml")

    pieces = Scraper._detecter_pieces_jointes(soup)

    assert pieces == [("https://www.hcp.ma/attachment/2885946/", "docx", "fr")]


def test_contenu_semble_valide_distingue_xlsx_et_docx():
    # XLSX et DOCX sont tous deux des ZIP (signature "PK" identique) : on ne peut pas
    # se fier a la seule signature. Fixtures generees a la volee avec les vraies
    # bibliotheques (pas de fichier externe necessaire).
    import io

    from docx import Document as DocxDocument
    from openpyxl import Workbook

    tampon_docx = io.BytesIO()
    DocxDocument().save(tampon_docx)
    contenu_docx = tampon_docx.getvalue()

    tampon_xlsx = io.BytesIO()
    Workbook().save(tampon_xlsx)
    contenu_xlsx = tampon_xlsx.getvalue()

    assert Scraper._contenu_semble_valide(contenu_docx, "docx") is True
    assert Scraper._contenu_semble_valide(contenu_docx, "xlsx") is False

    assert Scraper._contenu_semble_valide(contenu_xlsx, "xlsx") is True
    assert Scraper._contenu_semble_valide(contenu_xlsx, "docx") is False


def test_nom_fichier_piece_gere_extension_docx():
    nom = Scraper._nom_fichier_piece("https://www.hcp.ma/attachment/2885946/", "docx")
    assert nom == "2885946.docx"


# --- ADR 0006 : decouverte automatique des publications -----------------------------
#
# Verifie en reel sur https://www.hcp.ma/Publications-Marche-du-travail_r425.html
# (50 publications, 10 pages de 5, pagination ?start=0..45). Fixtures reconstruites a
# partir de cette page reelle et du menu HCP_TYPE deja utilise plus haut (regression :
# le menu ne doit produire aucun faux positif sur le motif d'URL d'article).

PAGE_LISTING_TYPE = (
    MENU_HCP_TYPE
    + '<h3><a href="https://www.hcp.ma/Informalite-genre-et-vieillissement-inegalites-'
    'cumulatives-et-effets-intergenerationnels-Mai-2026_a4311.html">Informalite...</a></h3>'
    + '<a href="https://www.hcp.ma/Informalite-genre-et-vieillissement-inegalites-'
    'cumulatives-et-effets-intergenerationnels-Mai-2026_a4311.html">Lire la suite</a>'
    + '<h3><a href="https://www.hcp.ma/Activite-emploi-et-chomage-resultats-annuels-2025_a4310.html">'
    "Activite...</a></h3>"
    + '<a href="https://www.hcp.ma/Activite-emploi-et-chomage-resultats-annuels-2025_a4310.html">'
    "Lire la suite</a>"
    + '<div class="pagination">'
    '<a href="https://www.hcp.ma/Publications-Marche-du-travail_r425.html">1</a>'
    '<a href="https://www.hcp.ma/Publications-Marche-du-travail_r425.html?start=5&show=&order=">2</a>'
    '<a href="https://www.hcp.ma/Publications-Marche-du-travail_r425.html?start=10&show=&order=">3</a>'
    '<a href="https://www.hcp.ma/Publications-Marche-du-travail_r425.html?start=45&show=&order=">10</a>'
    "</div>"
)


def test_extraire_urls_articles_pas_de_faux_positif_sur_menu_reel():
    # Meme regression que _detecter_pieces_jointes : le menu HCP (categories, pied de
    # page, reseaux sociaux...) ne doit jamais etre pris pour un article, y compris les
    # liens en _rXXX.html (categories) qui pourraient sembler proches du motif _aXXX.html.
    soup = BeautifulSoup(MENU_HCP_TYPE, "lxml")
    urls = Scraper._extraire_urls_articles(soup, "https://www.hcp.ma/Publications-Marche-du-travail_r425.html")
    assert urls == []


def test_extraire_urls_articles_deduplique_lien_titre_et_lire_la_suite():
    soup = BeautifulSoup(PAGE_LISTING_TYPE, "lxml")
    resultats = Scraper._extraire_urls_articles(soup, "https://www.hcp.ma/Publications-Marche-du-travail_r425.html")
    assert resultats == [
        (
            "https://www.hcp.ma/Informalite-genre-et-vieillissement-inegalites-cumulatives-et-effets-intergenerationnels-Mai-2026_a4311.html",
            "fr",
        ),
        (
            "https://www.hcp.ma/Activite-emploi-et-chomage-resultats-annuels-2025_a4310.html",
            "fr",
        ),
    ]


# --- ADR 0006, suite : filtrage des versions arabes ---------------------------------
#
# Trouve en conditions reelles (premiere execution du script) : la decouverte
# automatique remonte aussi des versions arabes d'articles, qui n'apparaissaient
# jamais dans l'ancienne liste fixe (URLs choisies a la main en francais). Fixture
# reconstruite depuis le vrai cas trouve :
# https://www.hcp.ma/Situation-du-marche-du-travail-dans-la-region-de-Rabat-Sale-Kenitra-en-2024-version-Ar_a4217.html
# titre reel du lien : "Situation du marché du travail dans la région de
# Rabat - Salé - Kénitra en 2024 (version Ar)".

def test_extraire_urls_articles_detecte_la_langue_arabe_via_le_texte_du_lien():
    html = (
        '<h3><a href="https://www.hcp.ma/Situation-du-marche-du-travail-dans-la-region-de-'
        'Rabat-Sale-Kenitra-en-2024-version-Ar_a4217.html">Situation du marché du travail '
        "dans la région de Rabat - Salé - Kénitra en 2024 (version Ar)</a></h3>"
    )
    soup = BeautifulSoup(html, "lxml")
    resultats = Scraper._extraire_urls_articles(soup, "https://www.hcp.ma/Publications-Marche-du-travail_r425.html")
    assert resultats == [
        (
            "https://www.hcp.ma/Situation-du-marche-du-travail-dans-la-region-de-Rabat-Sale-Kenitra-en-2024-version-Ar_a4217.html",
            "ar",
        )
    ]


@patch("src.scraper.requests.get")
def test_decouvrir_urls_liste_ecarte_les_pages_arabes_par_defaut(mock_get):
    page_1 = MagicMock()
    page_1.text = (
        MENU_HCP_TYPE
        + '<h3><a href="https://www.hcp.ma/Article-fr_a1111.html">Un article francais</a></h3>'
        + '<h3><a href="https://www.hcp.ma/Article-ar-version-Ar_a2222.html">Un article (version Ar)</a></h3>'
    )
    page_1.raise_for_status = MagicMock()
    mock_get.return_value = page_1

    scraper = Scraper(delay=0)
    urls = scraper.decouvrir_urls_liste(
        "https://www.hcp.ma/Publications-Marche-du-travail_r425.html", max_pages=1
    )

    assert urls == ["https://www.hcp.ma/Article-fr_a1111.html"]


def test_increments_pagination_deduits_des_liens_reels():
    soup = BeautifulSoup(PAGE_LISTING_TYPE, "lxml")
    assert Scraper._increments_pagination(soup) == [5, 10, 45]


@patch("src.scraper.requests.get")
def test_decouvrir_urls_liste_suit_la_pagination(mock_get):
    # Page 1 : 1 article + paliers [5, 10]. Page ?start=5 : 1 nouvel article, pas de
    # pagination (fin du listing). max_pages=None -> doit suivre jusqu'au bout.
    page_1 = MagicMock()
    page_1.text = (
        MENU_HCP_TYPE
        + '<h3><a href="https://www.hcp.ma/Article-un_a1111.html">Un</a></h3>'
        + '<a href="https://www.hcp.ma/Publications-Marche-du-travail_r425.html?start=5&show=&order=">2</a>'
    )
    page_1.raise_for_status = MagicMock()

    page_2 = MagicMock()
    page_2.text = MENU_HCP_TYPE + '<h3><a href="https://www.hcp.ma/Article-deux_a2222.html">Deux</a></h3>'
    page_2.raise_for_status = MagicMock()

    mock_get.side_effect = [page_1, page_2]

    scraper = Scraper(delay=0)
    urls = scraper.decouvrir_urls_liste("https://www.hcp.ma/Publications-Marche-du-travail_r425.html")

    assert urls == [
        "https://www.hcp.ma/Article-un_a1111.html",
        "https://www.hcp.ma/Article-deux_a2222.html",
    ]
    assert mock_get.call_count == 2


@patch("src.scraper.requests.get")
def test_decouvrir_urls_liste_max_pages_1_ne_suit_pas_la_pagination(mock_get):
    # Usage "fraicheur" (ADR 0006) : max_pages=1 ne doit lire que la page 1, meme si
    # elle annonce d'autres pages.
    page_1 = MagicMock()
    page_1.text = (
        MENU_HCP_TYPE
        + '<h3><a href="https://www.hcp.ma/Article-un_a1111.html">Un</a></h3>'
        + '<a href="https://www.hcp.ma/Publications-Marche-du-travail_r425.html?start=5&show=&order=">2</a>'
    )
    page_1.raise_for_status = MagicMock()
    mock_get.return_value = page_1

    scraper = Scraper(delay=0)
    urls = scraper.decouvrir_urls_liste(
        "https://www.hcp.ma/Publications-Marche-du-travail_r425.html", max_pages=1
    )

    assert urls == ["https://www.hcp.ma/Article-un_a1111.html"]
    assert mock_get.call_count == 1


@patch("src.scraper.requests.get")
def test_collecter_depuis_listing_enchaine_decouverte_et_collecter(mock_get):
    page_listing = MagicMock()
    page_listing.text = MENU_HCP_TYPE + '<h3><a href="https://www.hcp.ma/Article-un_a1111.html">Un</a></h3>'
    page_listing.raise_for_status = MagicMock()

    page_article = MagicMock()
    page_article.text = "<html><body><h1>Article un</h1></body></html>"
    page_article.raise_for_status = MagicMock()

    mock_get.side_effect = [page_listing, page_article]

    scraper = Scraper(delay=0, telecharger_pieces_jointes=False)
    docs = scraper.collecter_depuis_listing(
        "https://www.hcp.ma/Publications-Marche-du-travail_r425.html",
        categorie="Marche du travail",
        max_pages=1,
    )

    assert len(docs) == 1
    assert docs[0].titre == "Article un"
    assert docs[0].categorie == "Marche du travail"


# --- Flux transversal "Dernieres parutions" (hcp.ma/downloads/?tag=...) -------------
#
# Trouve le 30/08 : "Chiffres cles 2026" restait absent du corpus alors que publie
# depuis plusieurs semaines. Cause : aucune des 3 categories de listing_urls.py ne le
# referencait (publication transversale, tag "Publications generales"). Structure HTML
# reconstruite depuis la vraie page https://www.hcp.ma/downloads/?tag=Dernieres+parutions
# (verifiee via navigateur le 30/08) : differente des pages Publications-<sous-theme>
# ci-dessus -- chaque entree est un bloc div.delimiter avec un lien DIRECT vers le
# fichier (/file/XXXXXX/), pas de page article HTML intermediaire.

ENTREE_TELECHARGEMENT_TYPE = """
<div class="delimiter">
    <div style="float: left" class="photo"><a href="/file/248696/"><img src="/photo/thumb/248696.png" alt=""></a></div>
    <div style="margin-left:85px">
        <div class="titre_fichier"><a href="/file/248696/">Chiffres clés, 2026 (version arabe et anglaise)</a></div>
        <div><a class="description" href="/file/248696/"></a></div><br>
        <div class="information">
            <a href="/file/248696/"><img src="/_images/ext/icon_pdf.gif" class="image" alt=""></a>
 Publié le : 06/08/2026</div>
        <div class="information" style="margin-top:5px">
            <span>Tags : </span>
            <a class="lien" href="/downloads/?tag=Chiffres+cl%C3%A9s">Chiffres clés</a>
            <a class="lien" href="/downloads/?tag=Derni%C3%A8res+parutions">Dernières parutions</a>
        </div>
    </div>
    <div style="clear: both"></div>
</div>
<div class="delimiter">
    <div style="float: left" class="photo"><a href="/file/248688/"><img src="/_images/download_defaut.png" alt=""></a></div>
    <div style="margin-left:85px">
        <div class="titre_fichier"><a href="/file/248688/">Principaux indicateurs trimestriels rétropolés provisoires du marché du travail selon la méthodologie EMO, Période de 2017 à 2025</a></div>
        <div><a class="description" href="/file/248688/"></a></div><br>
        <div class="information">
            <a href="/file/248688/"><img src="/_images/ext/icon_xlsx.gif" class="image" alt=""></a>
 Publié le : 04/08/2026</div>
    </div>
</div>
"""


def test_extraire_entrees_telechargements_parse_titre_href_type_date():
    # Note (trouve en ecrivant ce test, pas cherche expres) : le titre reel "...(version
    # arabe et anglaise)" contient le mot "arabe", qui declenche _detecter_langue -> "ar"
    # via l'heuristique existante (INDICES_ARABE) -- meme si le document n'est pas QUE en
    # arabe. Ce n'est pas un probleme pratique ici : ce document precis a deja ete
    # diagnostique comme illisible par le pipeline de chunking (mise en page dense
    # bilingue, voir echange du 30/08), donc l'exclure par ce biais accessoire n'a pas
    # de consequence negative pour l'instant. A revisiter si "Chiffres cles" doit un jour
    # etre reellement indexe (voir piste B discutee : extraction visuelle).
    soup = BeautifulSoup(ENTREE_TELECHARGEMENT_TYPE, "lxml")
    resultats = Scraper._extraire_entrees_telechargements(soup)

    # Dates converties en ISO 8601 (YYYY-MM-DD) depuis le format brut JJ/MM/AAAA de la
    # page (demande encadrante, 08/09 -- voir _iso_depuis_date_jjmmaaaa).
    assert resultats == [
        ("Chiffres clés, 2026 (version arabe et anglaise)", "/file/248696/", "pdf", "2026-08-06", "ar"),
        (
            "Principaux indicateurs trimestriels rétropolés provisoires du marché du "
            "travail selon la méthodologie EMO, Période de 2017 à 2025",
            "/file/248688/",
            "xlsx",
            "2026-08-04",
            "fr",
        ),
    ]


def test_extraire_entrees_telechargements_detecte_langue_arabe_via_le_titre():
    html = """
    <div class="delimiter">
        <div class="titre_fichier"><a href="/file/243619/">Point de conjoncture N° 50, Juillet 2026 (version Ar)</a></div>
        <div class="information"><img src="/_images/ext/icon_pdf.gif"> Publié le : 16/07/2026</div>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    resultats = Scraper._extraire_entrees_telechargements(soup)

    assert resultats == [
        ("Point de conjoncture N° 50, Juillet 2026 (version Ar)", "/file/243619/", "pdf", "2026-07-16", "ar")
    ]


def test_increments_pagination_p_deduits_des_liens_reels():
    html = (
        '<a href="https://www.hcp.ma/downloads/?tag=Dernières+parutions">1</a>'
        '<a href="https://www.hcp.ma/downloads/?tag=Dernières+parutions&p=20">2</a>'
    )
    soup = BeautifulSoup(html, "lxml")
    assert Scraper._increments_pagination_p(soup) == [20]


@patch("src.scraper.requests.get")
def test_decouvrir_entrees_telechargements_suit_la_pagination(mock_get):
    page_1 = MagicMock()
    page_1.text = (
        '<div class="delimiter">'
        '<div class="titre_fichier"><a href="/file/111/">Un</a></div>'
        '<div class="information"><img src="/_images/ext/icon_pdf.gif"> Publié le : 06/08/2026</div>'
        "</div>"
        '<a href="https://www.hcp.ma/downloads/?tag=Dernières+parutions&p=20">2</a>'
    )
    page_1.raise_for_status = MagicMock()

    page_2 = MagicMock()
    page_2.text = (
        '<div class="delimiter">'
        '<div class="titre_fichier"><a href="/file/222/">Deux</a></div>'
        '<div class="information"><img src="/_images/ext/icon_pdf.gif"> Publié le : 04/08/2026</div>'
        "</div>"
    )
    page_2.raise_for_status = MagicMock()

    mock_get.side_effect = [page_1, page_2]

    scraper = Scraper(delay=0)
    entrees = scraper._decouvrir_entrees_telechargements("https://www.hcp.ma/downloads/?tag=Dernières+parutions")

    assert [href for _, href, _, _, _ in entrees] == ["/file/111/", "/file/222/"]
    assert mock_get.call_count == 2


@patch("src.scraper.requests.get")
def test_decouvrir_entrees_telechargements_max_pages_1_ne_suit_pas_la_pagination(mock_get):
    page_1 = MagicMock()
    page_1.text = (
        '<div class="delimiter">'
        '<div class="titre_fichier"><a href="/file/111/">Un</a></div>'
        '<div class="information"><img src="/_images/ext/icon_pdf.gif"> Publié le : 06/08/2026</div>'
        "</div>"
        '<a href="https://www.hcp.ma/downloads/?tag=Dernières+parutions&p=20">2</a>'
    )
    page_1.raise_for_status = MagicMock()
    mock_get.return_value = page_1

    scraper = Scraper(delay=0)
    entrees = scraper._decouvrir_entrees_telechargements(
        "https://www.hcp.ma/downloads/?tag=Dernières+parutions", max_pages=1
    )

    assert [href for _, href, _, _, _ in entrees] == ["/file/111/"]
    assert mock_get.call_count == 1


@patch("src.scraper.requests.get")
@patch("src.scraper.Scraper._telecharger_piece_jointe")
def test_collecter_depuis_telechargements_appelle_telecharger_piece_jointe_par_entree(
    mock_telecharger, mock_get
):
    page_listing = MagicMock()
    page_listing.text = ENTREE_TELECHARGEMENT_TYPE
    page_listing.raise_for_status = MagicMock()
    mock_get.return_value = page_listing

    doc_pdf = MagicMock()
    doc_xlsx = MagicMock()
    mock_telecharger.side_effect = [doc_pdf, doc_xlsx]

    # inclure_arabe=True : la 1ere entree du fixture ("...version arabe et anglaise")
    # serait sinon filtree par _detecter_langue (voir note dans le test de parsing
    # ci-dessus) -- non pertinent ici, ce test verifie l'enchainement decouverte ->
    # telechargement par entree, pas le filtrage linguistique (deja teste separement).
    scraper = Scraper(delay=0, inclure_arabe=True)
    docs = scraper.collecter_depuis_telechargements(
        "https://www.hcp.ma/downloads/?tag=Dernières+parutions",
        categorie="Publications generales",
        max_pages=1,
    )

    assert docs == [doc_pdf, doc_xlsx]
    assert mock_telecharger.call_count == 2
    premier_appel = mock_telecharger.call_args_list[0].args
    assert premier_appel[0] == "https://www.hcp.ma/file/248696/"
    assert premier_appel[1] == "pdf"
    assert premier_appel[3] == "Chiffres clés, 2026 (version arabe et anglaise)"


@patch("src.scraper.requests.get")
@patch("src.scraper.Scraper._telecharger_piece_jointe")
def test_collecter_depuis_telechargements_ecarte_les_entrees_arabes_par_defaut(mock_telecharger, mock_get):
    html = """
    <div class="delimiter">
        <div class="titre_fichier"><a href="/file/111/">Note (version Ar)</a></div>
        <div class="information"><img src="/_images/ext/icon_pdf.gif"> Publié le : 06/08/2026</div>
    </div>
    """
    page_listing = MagicMock()
    page_listing.text = html
    page_listing.raise_for_status = MagicMock()
    mock_get.return_value = page_listing

    scraper = Scraper(delay=0)
    docs = scraper.collecter_depuis_telechargements(
        "https://www.hcp.ma/downloads/?tag=Dernières+parutions", max_pages=1
    )

    assert docs == []
    mock_telecharger.assert_not_called()
