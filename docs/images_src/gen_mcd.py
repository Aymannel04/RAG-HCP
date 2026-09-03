import sys
sys.path.insert(0, "/tmp/diagrams")
from svg_helpers import SVG, NAVY, BLUE, GREY, WHITE, FILL, render

W, H = 1900, 1300
s = SVG(W, H)
s.title("Modele conceptuel de donnees (MCD) -- perimetre relationnel -- v4", y=42, size=25)
s.text(W/2, 74, "(l'index vectoriel des embeddings n'est pas represente ici : ce n'est pas une structure relationnelle)", size=15, color=GREY, style="italic")

def entity(s, cx, top_y, w, name, attrs, header_h=44, attr_h=27, new_attrs=None):
    new_attrs = new_attrs or set()
    h = header_h + len(attrs) * attr_h + 10
    x = cx - w/2
    s.rect(x, top_y, w, h, fill=WHITE, stroke=NAVY, rx=0, sw=1.8)
    s.rect(x, top_y, w, header_h, fill=BLUE, stroke=NAVY, rx=0, sw=1.8)
    s.text(cx, top_y + header_h - 14, name, size=19, weight="bold", color=WHITE)
    for i, a in enumerate(attrs):
        col = "#B00020" if a in new_attrs else NAVY
        label = a + ("   (nouveau, ADR 0004)" if a in new_attrs else "")
        s.text(x + 16, top_y + header_h + 20 + i*attr_h, label, size=15, anchor="start", color=col)
    return h

h_doc = entity(s, 950, 90, 480, "DOCUMENT", ["id_document (id)", "url", "titre", "date_publication", "langue", "categorie", "type  (+'api', +'docx')"])

h_chunk = entity(s, 460, 760, 460, "CHUNK", ["id_chunk (id)", "texte", "position", "embedding (vecteur)"])
h_ind = entity(s, 1470, 760, 480, "INDICATEUR", ["id_indicateur (id)", "nom", "valeur", "unite", "periode", "region", "code_bds"], new_attrs={"code_bds"})

def relation(s, cx, cy, label, w=170, h=52):
    s.rect(cx-w/2, cy-h/2, w, h, fill=FILL, stroke=NAVY, rx=26, sw=1.8)
    s.text(cx, cy+6, label, size=16)

rel1_y = 470
rel2_y = 470
relation(s, 700, rel1_y, "contient")
relation(s, 1250, rel1_y, "est source de")

s.line(950-40, 90+h_doc, 700, rel1_y-26, sw=1.6)
s.text(790, 90+h_doc+40, "(0,N)", size=15)
s.line(950+40, 90+h_doc, 1250, rel1_y-26, sw=1.6)
s.text(1110, 90+h_doc+40, "(0,N)", size=15)

s.line(700, rel1_y+26, 460, 760, sw=1.6)
s.text(560, 660, "(1,1)", size=15)
s.line(1250, rel1_y+26, 1470, 760, sw=1.6)
s.text(1360, 660, "(1,1)", size=15)

s.note(W/2, 1210, [
    "Lecture : un DOCUMENT contient de 0 a N CHUNK ; un CHUNK appartient a exactement 1 DOCUMENT.",
    "Un DOCUMENT est source de 0 a N INDICATEUR ; un INDICATEUR provient d'exactement 1 DOCUMENT.",
    "Structure inchangee depuis v3 (ADR 0004) : aucune entite ni association ajoutee -- seuls 'type' (valeurs 'api'/'docx' en plus)",
    "et 'code_bds' (nouveau, cle de cache pour la strategie cache-aside vers l'API BDS) evoluent, en rouge ci-dessus.",
], size=15, lh=24)

s.save("/tmp/diagrams/uml_mcd.svg")
render("/tmp/diagrams/uml_mcd.svg", "/tmp/diagrams/uml_mcd.png", scale=2.0)
print("done")
