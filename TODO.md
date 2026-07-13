# Planning — RAG HCP

Planning détaillé dans `docs/fiche_cadrage_v4.pdf` (section 12). Résumé actionnable ici,
à cocher au fur et à mesure. Convertir en Issues GitHub si besoin d'un board visuel partagé.

## Semaine 1 (7-13 juillet) — Cadrage + premiers scripts

- [x] Cadrage complet (fiche de cadrage + dossier de conception UML/Merise)
- [x] Choix de la stack (voir `docs/adr/0002-stack-technique-prototype.md`)
- [x] Squelette du repo (structure, modules stub, schéma DB, tests de base)
- [x] Script de scraping fonctionnel (`src/scraper.py`)
- [ ] Valider avec l'encadrante les hypothèses de travail (section 11 de la fiche de cadrage),
      en particulier le choix du LLM/hébergement
- [ ] Tester le scraper sur un vrai échantillon (~20-30 pages) des catégories ciblées

## Semaine 2 (14-20 juillet) — Pipeline d'ingestion complet

- [ ] Extraction PDF (`Extracteur.extraire` pour `type == "pdf"`, via pdfplumber)
- [ ] Chunking + embeddings (`IndexeurTexte.indexer`)
- [ ] Indexation Chroma + BM25
- [ ] Curation des 15-20 indicateurs clés (`ConstructeurIndicateurs.structurer`)
- [ ] Script d'insertion en base (`db/schema.sql`)

## Semaine 3 (21-27 juillet) — Retrieval + génération

- [ ] Recherche hybride + reranking (`IndexeurTexte.rechercher`, `RetrievalReranker`)
- [ ] Routeur de question (`Routeur.classifier`)
- [ ] Lookup structuré (`LookupStructure.rechercher_indicateur`)
- [ ] Génération avec grounding strict + citation (`Generateur.generer_reponse`)
- [ ] Premiers tests de bout en bout sur les deux scénarios (question chiffrée / conceptuelle)

## Semaine 4 (28 juillet - 3 août) — Interface + évaluation

- [ ] Interface Streamlit (`src/interface.py`)
- [ ] Jeu de test de 30-50 questions-réponses
- [ ] Mesure de fiabilité (faithfulness, exactitude, pertinence du contexte)
- [ ] Itération sur les points faibles identifiés

## Semaine 5 (4-10 août) — Finalisation

- [ ] Corrections finales
- [ ] Documentation à jour
- [ ] Rapport de stage
- [ ] Préparation de la démonstration finale

## Marge (jusqu'à fin août)

Réserve en cas de retard, ou extension (support arabe, amélioration interface) si le
calendrier le permet.
