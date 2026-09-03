import sys
sys.path.insert(0, "/tmp/diagrams")
from svg_helpers import SeqDiagram, render

actors = ["Utilisateur", "Interface", "Historique", "Reformulateur", "Routeur", "LookupStructure", "RetrievalReranker", "Generateur"]
d = SeqDiagram(actors, lane_w=272, left_pad=165, height=1600)
d.title("Diagramme de sequence -- question mixte -- v4 (nouveau, ajoute le 28/07)",
        "Exemple : \"Pourquoi le taux de chomage a-t-il augmente ?\" (chiffre + explication)")
d.draw_headers()

U, I, H, RF, RT, LS, RR, G = range(8)

d.call(U, I, "poserQuestion(question)", 1)
d.call(I, H, "recuperer(id_session)", 2)
d.ret(H, I, "historique recent (ou [])", gap=54)
d.call(I, RF, "reformulerSiNecessaire(question, historique)", 3)
d.ret(RF, I, "question_effective", gap=54)
d.call(I, RT, "classifier(question_effective)", 4)
d.ret(RT, I, "MIXTE", gap=54)

d.note_band("dispatch parallele -- les DEUX chemins sont interroges, quoi qu'il arrive")
d.call(RT, LS, "rechercherIndicateur(question_effective)", 5)
d.ret(LS, RT, "Indicateur ou None", gap=54)
d.call(RT, RR, "rechercherEtTrier(question_effective)", 6)
d.ret(RR, RT, "chunks (liste, potentiellement vide)", gap=58)

d.note_band("SI indicateur trouve -- fusion (degrade seule si chunks vide)")
d.call(RT, G, "genererReponse(ContexteMixte(indicateur, chunks))", 7)
d.ret(G, I, "reponse fusionnee (source primaire + secondaire)", gap=58)
d.note_band("SINON -- aucun indicateur : repli sur le chemin notion seul")
d.call(RT, G, "genererReponse(chunks)", "7b")
d.ret(G, I, "reponse notion seule", gap=54)

d.call(I, H, "ajouter(id_session, question, reponse)", 8)
d.ret(I, U, "afficherReponse()", num=9, gap=54)

d.footer_note("Traits pleins = appels ; traits pointilles bleus = retours. Chemin exclu du cache NOTION (le chiffre doit rester a jour a chaque appel).")
s = d.finish(0)
s.save("/tmp/diagrams/uml_seq_mixte.svg")
render("/tmp/diagrams/uml_seq_mixte.svg", "/tmp/diagrams/uml_seq_mixte.png", scale=2.0)
print("done", d.y, d.height)
