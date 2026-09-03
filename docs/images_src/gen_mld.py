import sys
sys.path.insert(0, "/tmp/diagrams")
from svg_helpers import SVG, NAVY, BLUE, GREY, WHITE, render

W, H = 1900, 1300
s = SVG(W, H)
s.title("Modele logique de donnees (MLD) -- v4", y=42, size=25)
s.text(W/2, 74, "Traduction du MCD en tables SQL - PK = cle primaire, FK = cle etrangere", size=16, color="#333333")

def table(s, cx, top_y, w, name, cols, header_h=44, row_h=27):
    h = header_h + len(cols) * row_h + 10
    x = cx - w/2
    s.rect(x, top_y, w, h, fill=WHITE, stroke=NAVY, rx=0, sw=1.8)
    s.rect(x, top_y, w, header_h, fill=NAVY, stroke=NAVY, rx=0, sw=1.8)
    s.text(cx, top_y + header_h - 14, name, size=19, weight="bold", color=WHITE)
    for i, (label, kind) in enumerate(cols):
        color = BLUE if kind == "fk" else NAVY
        weight = "bold" if kind in ("pk", "fk") else "normal"
        s.text(x + 16, top_y + header_h + 20 + i*row_h, label, size=15, anchor="start", color=color, weight=weight)
    return h, x, x + w

h_doc, dx0, dx1 = table(s, 950, 90, 480, "DOCUMENT", [
    ("id_document (PK)", "pk"), ("url", ""), ("titre", ""), ("date_publication", ""),
    ("langue", ""), ("categorie", ""), ("type  CHECK(...,'api','docx')", ""),
])

h_chunk, chx0, chx1 = table(s, 460, 760, 460, "CHUNK", [
    ("id_chunk (PK)", "pk"), ("texte", ""), ("position", ""), ("embedding", ""), ("id_document (FK)", "fk"),
])
h_ind, ix0, ix1 = table(s, 1470, 760, 480, "INDICATEUR", [
    ("id_indicateur (PK)", "pk"), ("nom", ""), ("valeur", ""), ("unite", ""),
    ("periode", ""), ("region", ""), ("id_document (FK)", "fk"),
    ("code_bds  (nouveau, indexe)", "new"),
])

s.defs_arrow()
s.path(f"M {chx0+130} {760+h_chunk-45} L {dx0+100} {90+h_doc}", stroke=BLUE, sw=2, dash="7,4", marker="arrowblue")
s.path(f"M {ix0+150} {760+h_ind-72} L {dx1-100} {90+h_doc}", stroke=BLUE, sw=2, dash="7,4", marker="arrowblue")

s.note(W/2, 1170, [
    "Les fleches en pointille relient chaque cle etrangere (FK) a la cle primaire (PK) qu'elle reference.",
    "Structure identique a v3 : 3 tables, memes 2 FK. Seuls evoluent le domaine de 'type' (CHECK etendu, ADR 0003/0005)",
    "et l'ajout de 'code_bds' + son index idx_indicateur_code_bds (ADR 0004, cle de la strategie cache-aside vers l'API BDS).",
], size=15, lh=24)

s.save("/tmp/diagrams/uml_mld.svg")
render("/tmp/diagrams/uml_mld.svg", "/tmp/diagrams/uml_mld.png", scale=2.0)
print("done")
