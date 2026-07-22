from src.extracteur import Extracteur
from src.models import Document


def test_extraire_separe_texte_et_tableaux():
    html = """
    <html><body>
      <p>Premier paragraphe.</p>
      <p>Deuxieme paragraphe.</p>
      <table><tr><th>Annee</th><th>Valeur</th></tr><tr><td>2025</td><td>13.3</td></tr></table>
    </body></html>
    """
    doc = Document(
        id_document=None, url="https://example.test", titre="t",
        date_publication=None, langue="fr", categorie="Economie",
        type="html", texte_brut=html,
    )
    texte, tableaux = Extracteur().extraire(doc)

    assert "Premier paragraphe." in texte
    assert "Deuxieme paragraphe." in texte
    assert len(tableaux) == 1
    assert tableaux[0][0] == ["Annee", "Valeur"]
    assert tableaux[0][1] == ["2025", "13.3"]


def test_extraire_docx_separe_texte_et_tableaux(tmp_path):
    # ADR 0005 : support DOCX (pages IPC/IPPI, qui ne publient qu'en .docx). Fixture
    # generee a la volee avec python-docx, pas de fichier externe necessaire.
    from docx import Document as DocxDocument

    docx = DocxDocument()
    docx.add_paragraph("Premier paragraphe.")
    docx.add_paragraph("Deuxieme paragraphe.")
    docx.add_paragraph("")  # paragraphe vide : ne doit pas polluer le texte
    table = docx.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Annee"
    table.cell(0, 1).text = "Valeur"
    table.cell(1, 0).text = "2025"
    table.cell(1, 1).text = "13.3"

    chemin = tmp_path / "note_test.docx"
    docx.save(str(chemin))

    doc = Document(
        id_document=None, url="https://www.hcp.ma/attachment/999999/", titre="t",
        date_publication=None, langue="fr", categorie="Economie",
        type="docx", texte_brut=str(chemin),
    )
    texte, tableaux = Extracteur().extraire(doc)

    assert "Premier paragraphe." in texte
    assert "Deuxieme paragraphe." in texte
    assert texte.count("\n") == 1  # le paragraphe vide n'a pas laisse de ligne parasite
    assert len(tableaux) == 1
    assert tableaux[0][0] == ["Annee", "Valeur"]
    assert tableaux[0][1] == ["2025", "13.3"]
