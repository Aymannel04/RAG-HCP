from svg_helpers import SVG, NAVY, BLUE, GREY, WHITE, render

W, H = 2260, 1700
s = SVG(W, H)
s.title("Diagramme de classes (composants logiciels) -- v4", y=42, size=28)

def uml_class(s, cx, top_y, w, name, ops, name_h=42, op_h=26, fill=WHITE, stroke=NAVY, name_color=NAVY, op_size=13.5):
    n = len(ops)
    h = name_h + max(n, 1) * op_h + 10
    x = cx - w / 2
    s.rect(x, top_y, w, h, fill=fill, stroke=stroke, rx=0, sw=1.8)
    s.line(x, top_y + name_h, x + w, top_y + name_h, stroke=stroke, sw=1.8)
    s.text(cx, top_y + name_h - 13, name, size=18, weight="bold", color=name_color)
    for i, op in enumerate(ops):
        s.text(x + 14, top_y + name_h + 19 + i * op_h, op, size=op_size, anchor="start", color=NAVY, family="Consolas, monospace")
    return h, x, x + w

# --- Pipeline d'ingestion (haut), inchange depuis v3 -----------------------
CX = 1150
h_scraper, *_ = uml_class(s, CX, 78, 340, "Scraper", ["+ collecter(urls)"])
h_extr, ex0, ex1 = uml_class(s, CX, 250, 340, "Extracteur", ["+ extraire(document)"])
s.line(CX, 78 + h_scraper, CX, 250, sw=1.8)

h_idx, ix0, ix1 = uml_class(s, 620, 430, 400, "IndexeurTexte", ["+ indexer(texte)", "+ rechercher(question)"])
h_bds, bx0, bx1 = uml_class(s, 1980, 350, 300, "BdsClient", ["+ recupererCatalogue()", "+ recupererIndicateur(code)"])
h_ci, cx0, cx1 = uml_class(s, 1620, 560, 400, "ConstructeurIndicateurs", ["+ structurerDepuisBds(json)", "+ structurer(tableaux)"])

s.line(CX, 250 + h_extr, 620, 430, sw=1.8)
s.line(CX, 250 + h_extr, 1620, 560, sw=1.8)
s.text(1330, 505, "repli PDF/XLSX", size=12, color=GREY, style="italic")
s.text(1330, 521, "(implemente Sprint 5)", size=12, color=GREY, style="italic")
s.line(1980, 350 + h_bds, 1620, 560, sw=1.8)

# --- Memoire conversationnelle (nouveau, 28/07-23/08) -----------------------
h_ref, rf0, rf1 = uml_class(s, 300, 660, 380, "Reformulateur", ["+ reformulerSiNecessaire(", "   question, historique)"], op_size=12.5)
h_cache, ca0, ca1 = uml_class(s, 300, 850, 380, "CacheRedis", [
    "CacheReponses",
    "+ obtenir(question)",
    "+ enregistrer(question, rep.)",
    "HistoriqueConversation",
    "+ ajouter(session, q, rep.)",
    "+ recuperer(session)",
], op_size=12.5)

# --- Routeur (coeur) ---------------------------------------------------------
h_rt, rt0, rt1 = uml_class(s, CX, 660, 400, "Routeur", ["+ classifier(question)", "  -> CHIFFRE / NOTION /", "     MIXTE / SALUTATION"])

s.line(620, 430 + h_idx, CX, 660, sw=1.8)
s.line(1620, 560 + h_ci, CX, 660, sw=1.8)
s.line(rf1, 660 + h_ref / 2, rt0, 660 + 40, sw=1.8)
s.text(CX, 660 + h_rt + 34, "(CHIFFRE -> LookupStructure ; NOTION -> RetrievalReranker ;", size=12.5, color=GREY, style="italic")
s.text(CX, 660 + h_rt + 50, "MIXTE -> les deux, en parallele)", size=12.5, color=GREY, style="italic")

# fleche pointillee bleue : historique (lecture) CacheRedis -> Reformulateur
xm = min(rf0, ca0) - 40
s.path(f"M {ca0} 862 L {xm} 862 L {xm} {660+h_ref/2} L {rf0} {660+h_ref/2}", stroke=BLUE, sw=1.6, dash="5,4")
s.text(xm - 8, 760, "historique", size=11.5, color=BLUE, anchor="end", style="italic")
s.text(xm - 8, 774, "(lecture)", size=11.5, color=BLUE, anchor="end", style="italic")

# --- Recherche : deux chemins + fusion MIXTE --------------------------------
h_rr, rr0, rr1 = uml_class(s, 620, 900, 400, "RetrievalReranker", ["+ rechercherEtTrier", "  (question)"])
h_ls, ls0, ls1 = uml_class(s, 1620, 900, 400, "LookupStructure", ["+ rechercherIndicateur", "  (question)"])

s.line(CX, 660 + h_rt, 620, 900, sw=1.8)
s.line(CX, 660 + h_rt, 1620, 900, sw=1.8)

h_gen, g0, g1 = uml_class(s, CX, 1160, 460, "Generateur", ["+ genererReponse(contexte)", "  contexte : Indicateur |", "  list[Chunk] | ContexteMixte"])
s.line(620, 900 + h_rr, CX, 1160, sw=1.8)
s.line(1620, 900 + h_ls, CX, 1160, sw=1.8)

# fleche pointillee bleue : CacheRedis <-> chemin NOTION (cache) + Generateur (historique ecriture)
ycache_bottom = 850 + h_cache
s.path(f"M {ca0+40} {ycache_bottom} L {ca0+40} 1480 L {g0+60} 1480 L {g0+60} {1160+h_gen}", stroke=BLUE, sw=1.6, dash="5,4")
s.text(ca0 - 10, 1440, "cache reponses (NOTION uniquement)", size=12, color=BLUE, style="italic", anchor="start")
s.text(ca0 - 10, 1456, "+ historique (ecriture, tous types)", size=12, color=BLUE, style="italic", anchor="start")

h_if, *_ = uml_class(s, CX, 1370, 340, "Interface", ["+ afficher(reponse)"])
s.line(CX, 1160 + h_gen, CX, 1370, sw=1.8)

s.note(CX, 1620, [
    "Traits pleins : flux de donnees / appels de la chaine principale (inchangee depuis v3).",
    "Traits bleus pointilles : memoire conversationnelle Redis (ajoutee le 28/07, degradation silencieuse si Redis absent).",
], size=13.5)

s.save("../images/uml_classes.svg")
render("../images/uml_classes.svg", "../images/uml_classes.png", scale=2.0)
print("done")
