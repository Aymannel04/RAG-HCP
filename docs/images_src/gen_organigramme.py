import sys
sys.path.insert(0, "/tmp/diagrams")
from svg_helpers import SVG, GREY, WHITE, NAVY, BLUE, FILL, FILL2, render

NAVYT = "#1A2B4C"
BLUEF, BLUEB = "#EEF2FB", "#5E77AC"
GOLDF, GOLDB, GOLDT = "#FDF1DC", "#C9891A", "#8A5A00"
GREENF, GREENB, GREENT = "#EAF7EC", "#2E7D32", "#1B5E20"
GREYF, GREYB = "#F2F2F2", "#888888"

W, H = 1900, 1150
s = SVG(W, H)
s.title("Organigramme simplifié du Haut-Commissariat au Plan", y=42, size=26, color=NAVYT)
s.text(W/2, 72, "Structure institutionnelle -- reconstituée à partir des informations publiques du HCP (hcp.ma)", size=14, color=GREY, style="italic")

def box(cx, top_y, w, h, lines, fill=BLUEF, border=BLUEB, tcolor=NAVYT, size=15, lh=18, weight="bold"):
    s.rect(cx-w/2, top_y, w, h, fill=fill, stroke=border, rx=8, sw=1.8)
    if isinstance(lines, str):
        lines = [lines]
    n = len(lines)
    s.multiline(cx, top_y + h/2 - (n-1)*lh/2 + 5, lines, size=size, color=tcolor, weight=weight, lh=lh)
    return top_y + h

cx0 = W/2

# --- Niveau 1 : Haut Commissaire ---
y0 = 100
h0 = box(cx0, y0, 440, 55, "HAUT COMMISSAIRE AU PLAN", fill=NAVYT, border=NAVYT, tcolor=WHITE, size=16)

# --- Niveau 2 : Inspection generale / Secretariat general / Cabinet ---
y1 = h0 + 45
s.line(cx0, h0, cx0, y1 - 25, sw=1.6, stroke="#555")
s.line(cx0 - 620, y1 - 25, cx0 + 620, y1 - 25, sw=1.6, stroke="#555")
s.line(cx0 - 620, y1 - 25, cx0 - 620, y1, sw=1.6, stroke="#555")
s.line(cx0, y1 - 25, cx0, y1, sw=1.6, stroke="#555")
s.line(cx0 + 620, y1 - 25, cx0 + 620, y1, sw=1.6, stroke="#555")

h_ig = box(cx0 - 620, y1, 380, 55, "Inspection Générale", fill=GOLDF, border=GOLDB, tcolor=GOLDT)
h_sg = box(cx0, y1, 380, 55, "Secrétariat Général", fill=GOLDF, border=GOLDB, tcolor=GOLDT)
h_cab = box(cx0 + 620, y1, 380, 55, "Cabinet", fill=GOLDF, border=GOLDB, tcolor=GOLDT)

# --- Niveau 3 : rattaches au Secretariat general ---
y2 = h_sg + 45
s.line(cx0, h_sg, cx0, y2 - 25, sw=1.6, stroke="#555")
s.line(cx0 - 460, y2 - 25, cx0 + 460, y2 - 25, sw=1.6, stroke="#555")
s.line(cx0 - 460, y2 - 25, cx0 - 460, y2, sw=1.6, stroke="#555")
s.line(cx0 + 460, y2 - 25, cx0 + 460, y2, sw=1.6, stroke="#555")

h_serv = box(cx0 - 460, y2, 620, 95,
             ["Service du Contrôle de gestion", "Service de la Sécurité des Systèmes d'Information",
              "Service de la Gestion des archives"],
             fill=FILL, border="#999999", tcolor="#333333", size=13.5, lh=20, weight="normal")
h_comm = box(cx0 + 460, y2, 500, 95,
             ["Division de la Communication", "et de la Coopération"],
             fill=FILL, border="#999999", tcolor="#333333", size=13.5, lh=20, weight="normal")

# --- Niveau 4 : directions centrales (rattachees au HCP via le Secretariat general) ---
y3 = max(h_serv, h_comm) + 55
s.line(cx0, max(h_serv, h_comm) - 40, cx0, y3 - 20, sw=1.6, stroke="#555")
s.text(cx0, y3 - 5, "Directions centrales", size=15, weight="bold", color=NAVYT, anchor="middle")

directions = [
    "Direction Générale de la Statistique\net de la Comptabilité Nationale",
    "Direction de la Planification",
    "Direction de la Prévision\net de la Prospective",
    "Direction des Ressources Humaines\net des Affaires Générales",
    "DIRECTION DES SYSTÈMES\nD'INFORMATION STATISTIQUES",
    "Centre National de Documentation",
]
cols = 3
bw, bh, gapx, gapy = 560, 70, 40, 22
grid_w = cols * bw + (cols - 1) * gapx
start_x = cx0 - grid_w/2 + bw/2
y_dir_top = y3 + 15
row_bottoms = []
for i, label in enumerate(directions):
    col = i % cols
    row = i // cols
    cx = start_x + col * (bw + gapx)
    ty = y_dir_top + row * (bh + gapy)
    lines = label.split("\n")
    highlight = "SYSTÈMES" in label
    hb = box(cx, ty, bw, bh, lines,
              fill=GOLDF if highlight else BLUEF,
              border=GOLDB if highlight else BLUEB,
              tcolor=GOLDT if highlight else NAVYT,
              size=13.5, lh=17)
    row_bottoms.append(hb)
    s.line(cx0, y3 - 20 if row == 0 else row_bottoms[-1], cx0, ty, sw=1.2, stroke="#BBBBBB", dash="4,3") if False else None

y3b = max(row_bottoms)

# --- Niveau 5 : instituts et ecoles rattaches ---
y4 = y3b + 55
s.line(cx0, y3b, cx0, y4 - 20, sw=1.6, stroke="#555")
s.text(cx0, y4 - 5, "Instituts, écoles et centres rattachés", size=15, weight="bold", color=NAVYT, anchor="middle")

instituts = [
    "Observatoire des Conditions\nde Vie de la Population",
    "Centre d'Études et Recherches\nDémographiques",
    "Institut National d'Analyse\nde la Conjoncture",
    "Centre National d'Évaluation\ndes Programmes",
    "Institut National de Statistique\net d'Économie Appliquée (INSEA)",
    "École des Sciences\nde l'Information (ESI)",
    "Institut de formation des Techniciens\nen Statistique et Informatique",
]
cols2 = 4
bw2, bh2, gapx2, gapy2 = 420, 70, 30, 22
grid_w2 = cols2 * bw2 + (cols2 - 1) * gapx2
start_x2 = cx0 - grid_w2/2 + bw2/2
y_inst_top = y4 + 15
row_bottoms2 = []
for i, label in enumerate(instituts):
    col = i % cols2
    row = i // cols2
    cx = start_x2 + col * (bw2 + gapx2)
    ty = y_inst_top + row * (bh2 + gapy2)
    lines = label.split("\n")
    hb = box(cx, ty, bw2, bh2, lines, fill=GREENF, border=GREENB, tcolor=GREENT, size=13, lh=16)
    row_bottoms2.append(hb)

y4b = max(row_bottoms2)

# --- Niveau 6 : reseau territorial ---
y5 = y4b + 55
s.line(cx0, y4b, cx0, y5 - 20, sw=1.6, stroke="#555")
h5 = box(cx0, y5, 1200, 90,
         ["Réseau des Directions Régionales",
          "12 directions régionales couvrant l'ensemble du territoire, avec directions",
          "provinciales (DP) et services provinciaux (SP) rattachés selon les régions"],
         fill=GREYF, border=GREYB, tcolor="#333333", size=13.5, lh=19, weight="normal")

s.note(W/2, h5 + 35, [
    "La Direction des Systèmes d'Information Statistiques (DSIS, en surbrillance), qui a accueilli ce stage,",
    "est détaillée séparément en figure suivante.",
], size=13, lh=18)

s.save("/tmp/diagrams/organigramme.svg")
render("/tmp/diagrams/organigramme.svg", "/tmp/diagrams/organigramme.png", scale=2.0)
print("done", h5 + 70)
