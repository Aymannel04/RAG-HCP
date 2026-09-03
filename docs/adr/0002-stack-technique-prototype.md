# ADR 0002 — Choix de la stack technique pour le prototype

**Statut :** accepté — 21 juillet 2026 (mis à jour le 03/09 : le statut était resté
« proposé » alors que le dernier point ouvert, le choix du LLM de génération, avait
déjà été tranché par l'encadrante à cette date — voir « Décision » ci-dessous)

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
- LLM de génération : **tranché le 21 juillet 2026** — l'encadrante a validé « n'importe
  quel LLM gratuit qui fait le travail » pour la phase prototype. **Mistral**
  (`mistral-small-latest`, API externe, tier gratuit) retenu parmi les options
  comparées (Google Gemini, Groq, Mistral), pour la qualité du français et la
  cohérence (acteur français reconnu). Voir `src/llm_mistral.py` pour l'implémentation
  et le détail de la comparaison.

## Justification

Stack majoritairement open source et locale, qui minimise la dépendance externe pendant
la phase de développement. Le point réellement bloquant identifié initialement (choix
du LLM de génération) est désormais résolu (voir ci-dessus) : le risque de fuite de
données via une API externe, qui motivait la prudence initiale, ne s'applique pas ici
puisque les documents indexés par le RAG sont des publications déjà publiques du HCP
(hcp.ma) — aucune donnée confidentielle n'est envoyée à Mistral.

## Conséquences

- `src/llm_mistral.py` (nouveau, Sprint 3) : fonction `generer(question, texte_contexte)`
  injectée dans `Generateur` (voir `src/generateur.py`), appel REST direct à l'API
  Mistral (pas de SDK, cohérent avec `src/bds_client.py` qui utilise aussi `requests`
  nu). Nécessite une clé API gratuite (`MISTRAL_API_KEY` dans `.env`, jamais commitée).
- Si Mistral s'avère insuffisant en pratique (qualité, quota, latence) une fois testé en
  conditions réelles, le remplacer est un changement d'une ligne (`fonction_generation`
  injectable) — Google Gemini ou un modèle open-weight local via Ollama restent des
  replis documentés, pas un changement d'architecture.
