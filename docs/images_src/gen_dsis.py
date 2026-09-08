import sys
sys.path.insert(0, "/tmp/diagrams")
from svg_helpers import SVG, GREY, WHITE, render

NAVYT = "#1A2B4C"
GOLDF, GOLDB, GOLDT = "#FDF1DC", "#C9891A", "#8A5A00"
BLUEF, BLUEB, BLUET = "#EEF2FB", "#5E77AC", "#1A2B4C"

W, H = 1900, 650
s = SVG(W, H)
s.title("Organisation de la Direction des Systèmes d'Information Statistiques (DSIS)", y=42, size=22, color=NAVYT)
s.text(W/2, 70, "Direction d'accueil du stage -- deux divisions, trois services chacune", size=14, color=GREY, style="italic")

def box(cx, top_y, w, h, lines, fill=BLUEF, border=BLUEB, tcolor=BLUET, size=15, lh=18, weight="bold"):
    s.rect(cx-w/2, top_y, w, h, fill=fill, stroke=border, rx=8, sw=1.8)
    if isinstance(lines, str):
        lines = [lines]
    n = len(lines)
    s.multiline(cx, top_y + h/2 - (n-1)*lh/2 + 5, lines, size=size, color=tcolor, weight=weight, lh=lh)
    return top_y + h

cx0 = W/2

y0 = 110
h0 = box(cx0, y0, 500, 60, "Direction des Systèmes d'Information\nStatistiques (DSIS)".split("\n"),
         fill=GOLDF, border=GOLDB, tcolor=GOLDT, size=16)

y1 = h0 + 55
s.line(cx0, h0, cx0, y1 - 25, sw=1.6, stroke="#555")
s.line(cx0 - 420, y1 - 25, cx0 + 420, y1 - 25, sw=1.6, stroke="#555")
s.line(cx0 - 420, y1 - 25, cx0 - 420, y1, sw=1.6, stroke="#555")
s.line(cx0 + 420, y1 - 25, cx0 + 420, y1, sw=1.6, stroke="#555")

h_div1 = box(cx0 - 420, y1, 720, 75,
             ["Division de la Transformation Digitale", "et du Développement des Systèmes d'Information"],
             size=14)
h_div2 = box(cx0 + 420, y1, 720, 75,
             ["Division de l'Infrastructure et de l'Exploitation", "des Plateformes d'Information Statistiques"],
             size=14)

y2 = max(h_div1, h_div2) + 55

serv1 = [
    "Service de Développement\ndes Applications Informatiques",
    "Service de Digitalisation\ndes Opérations Statistiques",
    "Service de la Qualité, des Normes\net de la Veille Technologique",
]
serv2 = [
    "Service des Équipements,\ndes Réseaux et de la Sécurité\ndes Systèmes d'Information",
    "Service des Bases de Données\net des Plateformes\nStatistiques",
    "Service de la Diffusion\nMulticanal et des Plateformes\nCollaboratives et Régionales",
]

bw, bh, gapx = 240, 105, 15
grid_w = 3 * bw + 2 * gapx
start1 = (cx0 - 420) - grid_w/2 + bw/2
start2 = (cx0 + 420) - grid_w/2 + bw/2

s.line(cx0 - 420, max(h_div1, h_div2), cx0 - 420, y2 - 20, sw=1.6, stroke="#555")
s.line(cx0 + 420, max(h_div1, h_div2), cx0 + 420, y2 - 20, sw=1.6, stroke="#555")
s.line(start1, y2 - 20, start1 + grid_w - bw, y2 - 20, sw=1.6, stroke="#555")
s.line(start2, y2 - 20, start2 + grid_w - bw, y2 - 20, sw=1.6, stroke="#555")

row_bottoms = []
for i, label in enumerate(serv1):
    cx = start1 + i * (bw + gapx)
    s.line(cx, y2 - 20, cx, y2, sw=1.6, stroke="#555")
    hb = box(cx, y2, bw, bh, label.split("\n"), fill="#EAF7EC", border="#2E7D32", tcolor="#1B5E20", size=12, lh=17, weight="normal")
    row_bottoms.append(hb)
for i, label in enumerate(serv2):
    cx = start2 + i * (bw + gapx)
    s.line(cx, y2 - 20, cx, y2, sw=1.6, stroke="#555")
    hb = box(cx, y2, bw, bh, label.split("\n"), fill="#EAF7EC", border="#2E7D32", tcolor="#1B5E20", size=12, lh=17, weight="normal")
    row_bottoms.append(hb)

ymax = max(row_bottoms)
s.note(W/2, ymax + 35, [
    "Les deux divisions assurent conjointement la transformation digitale, le développement, la maintenance,",
    "la sécurité, l'exploitation et la diffusion des systèmes d'information statistiques du HCP.",
], size=13, lh=18)

s.save("/tmp/diagrams/dsis.svg")
render("/tmp/diagrams/dsis.svg", "/tmp/diagrams/dsis.png", scale=2.0)
print("done", ymax + 70)
