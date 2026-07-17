# Planning — RAG HCP, en sprints

5 sprints d'une semaine, calés sur `docs/fiche_cadrage_v4.pdf` (section 12). Chaque sprint a
un objectif, un backlog, et une definition of done (le critère qui dit "ce sprint est fini").
Convertir en Issues/board GitHub si besoin d'un board visuel partagé avec l'encadrante.

Extensions notées mais volontairement hors scope V1 : légendage visuel des graphiques
(voir échange du 13 juillet), PixelRAG pour les PDF à tableaux complexes.

---

## Sprint 1 (7-13 juillet) — Cadrage, conception, premiers scripts

**Objectif :** poser des bases solides et disposer d'un premier script fonctionnel avant
d'attaquer le pipeline complet.

Backlog :
- [x] Fiche de cadrage détaillée
- [x] Dossier de conception UML/Merise (cas d'utilisation, MCD, MLD, classes, séquences, activité)
- [x] Choix de la stack (`docs/adr/0002-stack-technique-prototype.md`)
- [x] Squelette du repo + schéma DB (`db/schema.sql`)
- [x] Scraper fonctionnel (`src/scraper.py`) + extracteur HTML (`src/extracteur.py`)
- [x] Tests de base (6 tests, mocks)
- [x] Liste d'URLs de départ pour les 3 catégories ciblées (`data/seed_urls.py`, 27 URLs)
- [x] Test du scraper en conditions réelles : 27/27 pages récupérées, 27/27 titres,
      25/27 dates du premier coup (2 corrigées ensuite, cf. journal du 15 juillet)
- [ ] Validation des hypothèses de travail avec l'encadrante (section 11 de la fiche de cadrage)

**Definition of done :** le scraper tourne sur un vrai échantillon et produit des `Document`
exploitables ; les hypothèses bloquantes (LLM/hébergement notamment) sont tranchées ou
explicitement encore ouvertes et non-bloquantes pour la suite.

---

## Sprint 2 (14-20 juillet) — Pipeline d'ingestion complet

**Objectif :** transformer chaque PDF/XLSX collecté en données indexées (texte +
indicateurs), de bout en bout. Périmètre confirmé le 15 juillet (voir ADR 0003) : le
RAG s'appuie **uniquement** sur les publications PDF/XLSX de hcp.ma — le HTML ne sert
qu'à les découvrir (liens de téléchargement) et à fournir titre/date, jamais indexé.

Backlog :
- [x] Trancher la traçabilité et la stratégie de mise à jour des indicateurs BDS
      (ADR 0004 complété + `docs/complement_conception_bds.pdf` : document
      synthétique `type="api"`, colonne `indicateur.code_bds`, lookup hybride
      cache-aside)
- [x] Valider en réel `src/bds_client.py` (API BDS, voir ADR 0004) : catalogue
      téléchargé (832 indicateurs, répartition par thème identique à ce qui avait
      été vérifié dans le navigateur) et `recuperer_indicateur("I3181")` renvoie
      bien la série complète (périodes T1 2007 à T4 2021 + dimensions/modalités).
      Testé le 16 juillet 2026 sur la machine d'Ayman.
- [x] Repenser `ConstructeurIndicateurs` autour de l'API BDS : `structurer_depuis_bds()`
      (parsing testé contre la vraie réponse de I3181 : 1020 lignes, 17 ventilations x
      60 périodes) + `construire_document_synthetique()`, `data/indicateurs_cures.py`
      (12 codes réels vérifiés, Population & Économie), `scripts/preremplir_indicateurs_bds.py`,
      3 tests unitaires (mock fidèle à la forme réelle de l'API). PDF/XLSX reste le repli.
- [x] Compléter `data/indicateurs_cures.py` avec Marché du travail (6 codes fournis par
      Ayman depuis data/bds_catalogue.json : taux de chômage, taux net d'activité, taux
      d'emploi, effectif des chômeurs, chômage par sexe/région, structure des actifs
      occupés). Liste curée complète : 18 indicateurs (6 par catégorie).
- [x] Valider en réel la détection de liens PDF/XLSX (`Scraper._detecter_pieces_jointes`) :
      testée contre du vrai HTML de 4 pages hcp.ma (note de conjoncture, rapport
      d'enquête, page RGPH régionale à 8 fichiers, bulletin emploi trimestriel — 338
      liens `<a>` au total, menus/sidebar/pied de page inclus). Résultat : 0 faux
      positif, 0 faux négatif. La "sur-détection" suspectée en Sprint 1 n'est PAS
      confirmée par ces tests réels — probable confusion avec des pages ayant
      plusieurs vraies pièces jointes (ex. RGPH régional, 8 fichiers légitimes).
      Aucune correction de code nécessaire ; 2 tests de régression ajoutés
      (`tests/test_scraper.py`) avec fixtures reconstruites depuis le vrai HTML.
      À confirmer sur les 27 pages en conditions 100% réelles (voir note ci-dessous).
- [ ] Valider en réel `Extracteur._extraire_pdf` (pdfplumber) et `_extraire_xlsx`
      (openpyxl) sur les PDF/XLSX ainsi téléchargés — premier test concluant le 15/07
      (8000+ caractères et tableaux réels extraits d'un PDF), à confirmer sur plus d'échantillons
- [ ] Chunking + embeddings (`IndexeurTexte.indexer`), en ne traitant QUE les
      `Document` de type `pdf`/`xlsx` (filtrer `type == "html"` explicitement)
- [ ] Indexation Chroma + BM25
- [ ] Script d'insertion en base (`db/schema.sql`), adapté pour stocker les indicateurs
      venant de la BDS (avec le code indicateur BDS comme référence) en plus de ceux
      extraits de PDF/XLSX

**Definition of done :** les PDF/XLSX collectés en Sprint 1 sont indexés de bout en bout
(texte + indicateurs) et interrogeables par script. Aucun contenu HTML n'est indexé.

---

## Sprint 3 (21-27 juillet) — Retrieval + génération

**Objectif :** répondre correctement aux deux types de questions, toujours avec source.

Backlog :
- [ ] Recherche hybride + reranking (`IndexeurTexte.rechercher`, `RetrievalReranker`)
- [ ] Routeur de question (`Routeur.classifier`)
- [ ] Lookup structuré (`LookupStructure.rechercher_indicateur`)
- [ ] Génération avec grounding strict + citation (`Generateur.generer_reponse`)
- [ ] Tests de bout en bout sur les deux scénarios (question chiffrée / conceptuelle)

**Definition of done :** les deux diagrammes de séquence (`docs/conception_uml_v3.pdf`,
figures 5 et 6) fonctionnent réellement en code, sur des vraies données indexées en Sprint 2.

---

## Sprint 4 (28 juillet - 3 août) — Interface + évaluation

**Objectif :** disposer d'un prototype démontrable et mesuré.

Backlog :
- [ ] Interface Streamlit (`src/interface.py`)
- [ ] Jeu de test de 30-50 questions-réponses
- [ ] Mesure de fiabilité (faithfulness, exactitude factuelle, pertinence du contexte)
- [ ] Itération sur les points faibles identifiés

**Definition of done :** démonstration de bout en bout fonctionnelle + rapport de fiabilité
chiffré (voir NF2 de la fiche de cadrage : ≥90% d'exactitude sur les questions chiffrées).

---

## Sprint 5 (4-10 août) — Finalisation

**Objectif :** livrable propre, documenté, présentable.

Backlog :
- [ ] Corrections finales
- [ ] Documentation à jour (README, ADR, journal)
- [ ] Rapport de stage
- [ ] Préparation de la démonstration finale

**Definition of done :** repo propre, rapport prêt, démo répétée au moins une fois avant
la présentation officielle.

---

## Marge (jusqu'à fin août)

Réserve en cas de retard, ou extension (support arabe, amélioration interface, légendage
visuel des graphiques).
