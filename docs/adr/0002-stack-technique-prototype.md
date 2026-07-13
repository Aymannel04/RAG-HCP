# ADR 0002 — Choix de la stack technique pour le prototype

**Statut :** proposé — à confirmer avec l'encadrante (voir hypothèses de travail,
`docs/fiche_cadrage_v4.pdf` section 11)

## Contexte

Besoin d'aller vite sur un prototype en 4-5 semaines, tout en gardant une architecture
propre et facilement remplaçable si les contraintes du service SI l'exigent (hébergement,
souveraineté des données).

## Décision

- Scraping : `requests` + `BeautifulSoup`
- Extraction PDF/tableaux : `pdfplumber` (+ `pymupdf` en repli)
- Embeddings : modèle multilingue open source (BGE-M3), via `sentence-transformers`
- Index vectoriel : `chromadb` (local, simple, suffisant pour un prototype)
- Recherche lexicale : `rank-bm25`
- Base indicateurs : SQLite (`db/schema.sql`)
- Interface de démonstration : Streamlit
- LLM de génération : **non tranché** — dépend de la politique de sécurité des données du
  HCP (API externe autorisée ou solution hébergée en interne). Voir point ouvert en
  section 11 de la fiche de cadrage.

## Justification

Stack majoritairement open source et locale, qui minimise la dépendance externe pendant
la phase de développement. Le seul point réellement bloquant est le choix du LLM de
génération, qui doit être validé avec l'encadrante avant la semaine 3 (retrieval +
génération).

## Conséquences

Si le LLM externe n'est pas autorisé, prévoir un repli sur un modèle open-weight
(Llama/Mistral/Qwen) servi localement — impact sur le temps de réponse (NF1) à réévaluer
dans ce cas.
