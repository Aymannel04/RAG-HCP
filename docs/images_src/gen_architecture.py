import sys
sys.path.insert(0, "/tmp/diagrams")
from svg_helpers import SVG, GREY, WHITE, render

NAVYT = "#1A2B4C"
BLUEF, BLUEB = "#EEF2FB", "#5E77AC"
GOLDF, GOLDB, GOLDT = "#FDF1DC", "#C9891A", "#8A5A00"
GREENF, GREENB, GREENT = "#EAF7EC", "#2E7D32", "#1B5E20"
REDF, REDB, REDT = "#FDEAEA", "#B71C1C", "#8E1414"
MEMF, MEMB, MEMT = "#E9F0FC", "#2255AA", "#123E7A"

W, H = 2100, 1230
s = SVG(W, H)
s.title("Architecture -- RAG hybride hcp.ma -- v4", y=42, size=27, color=NAVYT)
s.text(W/2, 72, "Deux sources d'ingestion desormais independantes (texte scrape vs API BDS) + memoire conversationnelle (28/07-23/08)", size=14.5, color=GREY, style="italic")

def box(s, cx, top_y, w, h, title, sub, fill, border, tcolor, subcolor=None, title_size=17, sub_size=14):
    subcolor = subcolor or "#333333"
    s.rect(cx-w/2, top_y, w, h, fill=fill, stroke=border, rx=10, sw=2)
    if sub:
        s.text(cx, top_y+h/2-6, title, size=title_size, weight="bold", color=tcolor)
        s.multiline(cx, top_y+h/2+18, sub if isinstance(sub, list) else [sub], size=sub_size, color=subcolor, lh=19)
    else:
        s.text(cx, top_y+h/2+6, title, size=title_size, weight="bold", color=tcolor)
    return top_y+h

LX, RX = 560, 1540

# Sources (deux, independantes)
y0 = 105
h_srcL = box(s, LX, y0, 900, 90, "Sources texte : hcp.ma (scraping)",
             "Articles HTML | Publications PDF/DOCX | 3 categories + \"Dernieres parutions\" (transversal, 30/08)",
             BLUEF, BLUEB, NAVYT)
h_srcR = box(s, RX, y0, 900, 90, "Source chiffree : API BDS (bds.hcp.ma)",
             "832 indicateurs catalogues, non documentee officiellement mais librement accessible (ADR 0004)",
             BLUEF, BLUEB, NAVYT)

y1 = y0+90+50
s.line(LX, y0+90, LX, y1, sw=1.8, stroke="#555")
s.line(RX, y0+90, RX, y1, sw=1.8, stroke="#555")
h_ingL = box(s, LX, y1, 900, 70, "Ingestion / Extraction", "scraping cible, parsing HTML/PDF/DOCX", GOLDF, GOLDB, GOLDT)
h_ingR = box(s, RX, y1, 900, 70, "Pre-remplissage cache-aside", "planifie quotidien (18 codes cures) + upsert par code_bds", GOLDF, GOLDB, GOLDT)

y2 = y1+70+60
s.line(LX, y1+70, LX, y2, sw=1.8, stroke="#555")
s.line(RX, y1+70, RX, y2, sw=1.8, stroke="#555")
h_txt = box(s, LX, y2, 900, 80, "Texte non structure", "Chunking par section -> embeddings BGE-M3", GREENF, GREENB, GREENT)
h_chi = box(s, RX, y2, 900, 80, "Donnees chiffrees", "Repli extraction tableaux concu mais NON implemente (voir TODO.md) -- l'API couvre l'essentiel", REDF, REDB, REDT, sub_size=13)

y3 = y2+80+50
s.line(LX, y2+80, LX, y3, sw=1.8, stroke="#555")
s.line(RX, y2+80, RX, y3, sw=1.8, stroke="#555")
h_idx = box(s, LX, y3, 900, 65, "Index vectoriel (Chroma) + Index BM25 (recherche hybride)", None, GREENF, GREENB, GREENT, title_size=15.5)
h_tbl = box(s, RX, y3, 900, 65, "Table indicateur (valeur, periode, region, code_bds, source)", None, REDF, REDB, REDT, title_size=15.5)

# convergence -> Routeur
yc = y3+65+70
cx = W/2
s.line(LX, y3+65, LX, yc-35, sw=1.8, stroke="#555")
s.line(RX, y3+65, RX, yc-35, sw=1.8, stroke="#555")
s.line(LX, yc-35, cx-260, yc, sw=1.8, stroke="#555")
s.line(RX, yc-35, cx+260, yc, sw=1.8, stroke="#555")
h_rt = box(s, cx, yc, 620, 90, "Routeur de question",
           "CHIFFRE / NOTION / MIXTE / SALUTATION -- + reformulation prealable si historique",
           BLUEF, BLUEB, NAVYT)

# divergence -> retrieval / lookup
yd = yc+90+65
s.line(cx, yc+90, cx-260, yd-35, sw=1.8, stroke="#555")
s.line(cx, yc+90, cx+260, yd-35, sw=1.8, stroke="#555")
s.line(cx-260, yd-35, LX, yd, sw=1.8, stroke="#555")
s.line(cx+260, yd-35, RX, yd, sw=1.8, stroke="#555")
h_rr = box(s, LX, yd, 900, 80, "Retrieval hybride + reranking",
           "cross-encoder BAAI/bge-reranker-v2-m3 (documents, publications)", GREENF, GREENB, GREENT)
h_ls = box(s, RX, yd, 900, 80, "Lookup structure",
           "valeur exacte + periode + source, ventilation resolue (sexe/milieu/diplome/branche)", REDF, REDB, REDT)

# convergence -> generation
ye = yd+80+65
s.line(LX, yd+80, LX, ye-35, sw=1.8, stroke="#555")
s.line(RX, yd+80, RX, ye-35, sw=1.8, stroke="#555")
s.line(LX, ye-35, cx-200, ye, sw=1.8, stroke="#555")
s.line(RX, ye-35, cx+200, ye, sw=1.8, stroke="#555")
h_gen = box(s, cx, ye, 700, 80, "Generation LLM (Mistral)",
            "grounding strict, citation obligatoire -- fusion des 2 sources si MIXTE", GOLDF, GOLDB, GOLDT)

yf = ye+80+55
s.line(cx, ye+80, cx, yf, sw=1.8, stroke="#555")
h_if = box(s, cx, yf, 1000, 70, "Interface chat (Streamlit)",
           "reponse sourcee, session persistante, boucle feedback / evaluation", BLUEF, BLUEB, NAVYT)

# Bloc memoire conversationnelle (nouveau, transversal) -- a droite
mx = W - 190
my = yc - 10
s.rect(mx-150, my, 300, 210, fill=MEMF, stroke=MEMB, rx=10, sw=2, dash="6,4")
s.text(mx, my+30, "Memoire conversationnelle", size=15.5, weight="bold", color=MEMT)
s.text(mx, my+48, "(Redis, 28/07-23/08)", size=13, color=MEMT)
s.multiline(mx, my+76, ["Reformulateur : reecrit la", "question de suivi avant", "classification", "", "CacheReponses : reponses", "NOTION, TTL 24h", "", "Historique : session,", "TTL glissant 24h"], size=12.5, lh=16, color="#333333")
s.path(f"M {mx-150} {my+60} L {cx+310} {yc+45}", stroke=MEMB, sw=1.6, dash="5,4")
s.path(f"M {mx-150} {my+170} L {RX+80} {yd+80+35} L {cx+240} {ye+40}", stroke=MEMB, sw=1.6, dash="5,4")

s.note(W/2, H-45, [
    "Traits pleins = flux principal (donnees). Traits bleus pointilles = memoire conversationnelle (degradation silencieuse si Redis absent).",
], size=13.5)

s.save("/tmp/diagrams/architecture.svg")
render("/tmp/diagrams/architecture.svg", "/tmp/diagrams/architecture.png", scale=2.0)
print("done", yf+70)
