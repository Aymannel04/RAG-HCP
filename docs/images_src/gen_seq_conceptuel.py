import sys
sys.path.insert(0, "/tmp/diagrams")
from svg_helpers import SeqDiagram, render

actors = ["Utilisateur", "Interface", "Historique", "Reformulateur", "Routeur", "CacheReponses", "RetrievalReranker", "IndexTexte", "Generateur"]
d = SeqDiagram(actors, lane_w=248, left_pad=160, height=1560)
d.title("Diagramme de sequence -- question conceptuelle -- v4", "Exemple : \"C'est quoi le RGPH ?\"")
d.draw_headers()

U, I, H, RF, RT, C, RR, IX, G = range(9)

d.call(U, I, "poserQuestion(question)", 1)
d.call(I, H, "recuperer(id_session)", 2)
d.ret(H, I, "historique recent (ou [])", gap=54)
d.call(I, RF, "reformulerSiNecessaire(question, historique)", 3)
d.ret(RF, I, "question_effective", gap=54)
d.call(I, RT, "classifier(question_effective)", 4)
d.ret(RT, I, "NOTION", gap=54)
d.call(I, C, "obtenir(question_effective)", 5)

d.note_band("SI reponse deja en cache (question normalisee identique, < 24h)")
d.ret(C, I, "reponse (immediate, sans reranker ni LLM)", gap=58)
d.note_band("SINON -- chemin complet (cache miss)")

d.call(RT, RR, "rechercherEtTrier(question_effective)", 6)
d.call(RR, IX, "recherche hybride (BM25 + embeddings)", 7)
d.ret(IX, RR, "passages candidats", gap=54)
d.ret(RR, RT, "passages pertinents (rerank cross-encoder)", gap=58)
d.call(RT, G, "genererReponse(passages)", 8)
d.ret(G, I, "reponse sourcee", gap=54)
d.call(I, C, "enregistrer(question_effective, reponse)", 9)

d.call(I, H, "ajouter(id_session, question, reponse)", 10)
d.ret(I, U, "afficherReponse()", num=11, gap=54)

d.footer_note("Traits pleins = appels ; traits pointilles bleus = retours. Nouveau depuis v3 (encadre) : etapes 2-3, 5, 9-10 (memoire conversationnelle, 28/07-23/08).")
s = d.finish(0)
s.save("/tmp/diagrams/uml_seq_conceptuel.svg")
render("/tmp/diagrams/uml_seq_conceptuel.svg", "/tmp/diagrams/uml_seq_conceptuel.png", scale=2.0)
print("done", d.y, d.height)
