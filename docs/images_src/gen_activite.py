import sys
sys.path.insert(0, "/tmp/diagrams")
from svg_helpers import SVG, NAVY, BLUE, GREY, WHITE, FILL, activity_pill, start_node, end_node, render

W, H = 2100, 950
s = SVG(W, H)
s.defs_arrow()
s.title("Diagramme d'activite -- pipeline d'ingestion -- v4", y=42, size=27)
s.text(W/2, 72, "Deux processus independants (triggers et calendriers distincts), non un seul flux forke/joint", size=15, color=GREY, style="italic")

s.line(W/2, 105, W/2, H-90, stroke="#CCCCCC", sw=1.4, dash="3,4")

# ============ Colonne A : pipeline documentaire (texte) ============
AX = 560
s.text(AX, 128, "A -- Pipeline documentaire", size=18, weight="bold", color=NAVY)
start_node(s, AX, 165)
s.line(AX, 179, AX, 210, sw=1.6, marker="arrow")

y = 210
h = activity_pill(s, AX, y, 620, ["Collecter (Scraper) : 3 categories +", "\"Dernieres parutions\" (transversal, 30/08)"])
s.line(AX, y+h, AX, y+h+30, sw=1.6, marker="arrow"); y += h+30

h = activity_pill(s, AX, y, 560, ["Extraire (PDF / XLSX / DOCX)"])
s.line(AX, y+h, AX, y+h+30, sw=1.6, marker="arrow"); y += h+30

# decision
dcx, dcy, dw, dh = AX, y+70, 520, 140
s.diamond(dcx, dcy, dw, dh, fill="#E3E8F5")
s.multiline(dcx, dcy+2, ["Type de", "contenu ?"], size=16)
s.line(AX, y, AX, dcy-dh/2, sw=1.6, marker="arrow")

# left sub-branch : texte narratif
lx = AX - 330
s.line(dcx-dw/2, dcy, lx, dcy, sw=1.6)
s.line(lx, dcy, lx, dcy+70, sw=1.6, marker="arrow")
s.text((dcx-dw/2+lx)/2 - 10, dcy-14, "[texte narratif]", size=13.5, color=BLUE, anchor="middle")
y2 = dcy+70
h = activity_pill(s, lx, y2, 300, ["Decouper en chunks"]); s.line(lx, y2+h, lx, y2+h+26, sw=1.6, marker="arrow"); y2 += h+26
h = activity_pill(s, lx, y2, 300, ["Calculer les embeddings", "(BGE-M3)"]); s.line(lx, y2+h, lx, y2+h+26, sw=1.6, marker="arrow"); y2 += h+26
h = activity_pill(s, lx, y2, 300, ["Indexer (Chroma + BM25)"]); y2 += h

# right sub-branch : tableau de chiffres (NON IMPLEMENTE)
rx = AX + 330
s.line(dcx+dw/2, dcy, rx, dcy, sw=1.6)
s.line(rx, dcy, rx, dcy+70, stroke=GREY, sw=1.6, dash="6,4")
s.text((dcx+dw/2+rx)/2 + 10, dcy-14, "[tableau de chiffres]", size=13.5, color=BLUE, anchor="middle")
y3 = dcy+70
activity_pill(s, rx, y3, 320, ["Extraire les valeurs (tableaux)", "NON IMPLEMENTE -- NotImplementedError"], fill="#FAFAFA", stroke=GREY, size=13.5)
s.text(rx, y3+70, "hors perimetre depuis l'ADR 0004", size=12.5, color=GREY, style="italic")
s.text(rx, y3+86, "(l'API BDS couvre l'essentiel, voir colonne B)", size=12.5, color=GREY, style="italic")

yend_a = max(y2, y3+110) + 40
s.line(lx, y2, lx, yend_a, sw=1.6, marker="arrow")
end_node(s, lx, yend_a+16)
s.text(lx+140, yend_a+22, "index textuel disponible", size=13, color=GREY, style="italic")

# ============ Colonne B : pipeline BDS ============
BX = 1560
s.text(BX, 128, "B -- Pipeline BDS (indicateurs)", size=18, weight="bold", color=NAVY)
start_node(s, BX, 165)
s.line(BX, 179, BX, 210, sw=1.6, marker="arrow")

y = 210
h = activity_pill(s, BX, y, 460, ["Declenchement planifie", "(1 fois par jour)"]); s.line(BX, y+h, BX, y+h+30, sw=1.6, marker="arrow"); y += h+30
h = activity_pill(s, BX, y, 460, ["Pour chaque indicateur cure", "(18 codes -- data/indicateurs_cures.py)"]); s.line(BX, y+h, BX, y+h+30, sw=1.6, marker="arrow"); y += h+30
h = activity_pill(s, BX, y, 460, ["BdsClient.recupererIndicateur(code)", "(bds.hcp.ma/api/v1)"]); s.line(BX, y+h, BX, y+h+30, sw=1.6, marker="arrow"); y += h+30
h = activity_pill(s, BX, y, 460, ["ConstructeurIndicateurs", ".structurerDepuisBds(json)"]); s.line(BX, y+h, BX, y+h+30, sw=1.6, marker="arrow"); y += h+30
h = activity_pill(s, BX, y, 460, ["Upsert table indicateur", "(cle : nom, periode, region, code_bds)"]); y += h

s.line(BX, y, BX, y+56, sw=1.6, marker="arrow")
end_node(s, BX, y+72)
s.text(BX+150, y+78, "table indicateur a jour", size=13, color=GREY, style="italic")

s.note(W/2, H-56, [
    "Repli documente mais jamais implemente (voir TODO.md, colonne A) : le chemin \"tableau de chiffres\" a ete remplace en pratique par la colonne B (ADR 0004),",
    "bien plus fiable que le parsing heuristique de tableaux. Les deux pipelines alimentent independamment la meme base, interrogee par RetrievalReranker (A) et LookupStructure (B).",
], size=13.5, lh=20)

s.save("/tmp/diagrams/uml_activite.svg")
render("/tmp/diagrams/uml_activite.svg", "/tmp/diagrams/uml_activite.png", scale=2.0)
print("done")
