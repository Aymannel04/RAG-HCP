import sys
sys.path.insert(0, "/tmp/diagrams")
from svg_helpers import SeqDiagram, render

actors = ["Utilisateur", "Interface", "Historique\n(Redis)", "Reformulateur", "Routeur", "LookupStructure", "indicateur\n(SQLite)", "Generateur"]
actors = ["Utilisateur", "Interface", "Historique (Redis)", "Reformulateur", "Routeur", "LookupStructure", "table indicateur", "Generateur"]
d = SeqDiagram(actors, lane_w=270, left_pad=170, height=1260)
d.title("Diagramme de sequence -- question chiffree -- v4", 'Exemple : "Quel est le taux de chomage actuel ?"')
d.draw_headers()

U, I, H, RF, RT, LS, DB, G = range(8)

d.call(U, I, "poserQuestion(question)", 1)
d.call(I, H, "recuperer(id_session)", 2)
d.ret(H, I, "historique recent (ou [])", num=None, gap=54)
d.call(I, RF, "reformulerSiNecessaire(question, historique)", 3)
d.ret(RF, I, "question_effective", gap=54)
d.call(I, RT, "classifier(question_effective)", 4)
d.ret(RT, I, "CHIFFRE", gap=54)
d.call(RT, LS, "rechercherIndicateur(question_effective)", 5)
d.call(LS, DB, "SELECT ... WHERE nom=? AND region IS ?", 6)
d.ret(DB, LS, "valeur + periode + source", gap=54)
d.ret(LS, RT, "Indicateur", gap=54)
d.call(RT, G, "genererReponse(indicateur)", 7)
d.ret(G, I, "reponse sourcee", gap=54)
d.call(I, H, "ajouter(id_session, question, reponse)", 8)
d.ret(I, U, "afficherReponse()", num=9, gap=54)

d.footer_note("Traits pleins = appels ; traits pointilles bleus = retours. Nouveau depuis v3 (encadre) : etapes 2-3 et 8 (memoire conversationnelle, 28/07-23/08).")
s = d.finish(0)
s.save("/tmp/diagrams/uml_seq_chiffre.svg")
render("/tmp/diagrams/uml_seq_chiffre.svg", "/tmp/diagrams/uml_seq_chiffre.png", scale=2.0)
print("done", d.y, d.height)
