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
