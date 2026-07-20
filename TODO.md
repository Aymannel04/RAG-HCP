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
- [x] Valider en réel `Extracteur._extraire_pdf` sur les vrais PDF déjà téléchargés
      (`data/raw/`) : 30/33 fichiers valides traités sans erreur (texte + tableaux
      cohérents, de 2 à 645 tableaux selon le fichier) ; 2 gros PDF très denses en
      tableaux ("Tabulations", 4.3 Mo) n'ont pas fini en moins de 40s dans le sandbox —
      à chronométrer sur ta machine sans cette contrainte ; le fichier de 14 Mo pas
      encore testé. Nettoyé 14 fichiers invalides dans `data/raw/` (antérieurs au fix
      `_contenu_semble_valide` du 15/07, confirmés stale par horodatage git).
- [ ] `_extraire_xlsx` toujours pas testé en réel : aucun vrai .xlsx dans le jeu de
      données actuel (aucun exemplaire trouvé sur les pages seed à ce jour).
- [x] Support DOCX ajouté (ADR 0005, décision prise avec Ayman le 17/07 : étendre plutôt
      qu'accepter le trou) : `Scraper` détecte/télécharge/valide les `.docx` (même
      schéma que PDF/XLSX, `/attachment/{id}/` sans extension visible dans le href) ;
      `_contenu_semble_valide` renforcé pour distinguer XLSX et DOCX (tous deux des ZIP,
      signature `PK` identique — vérifie maintenant le dossier interne `xl/` vs `word/`) ;
      `Extracteur._extraire_docx` (python-docx) ajouté. `db/schema.sql`/`models.py` mis
      à jour (`type` accepte `'docx'`). 6 nouveaux tests (détection, validation
      xlsx/docx, extraction avec fixture générée à la volée). Suite complète : 16/16.
      **Reste à valider en conditions réelles** sur un vrai .docx IPC/IPPI téléchargé.
- [x] Découverte automatique des publications (ADR 0006, décidé avec Ayman le 20/07
      après la réunion avec l'encadrante — la liste fixe de 27 URLs ne couvrait ni
      l'historique ni les nouvelles publications) : `Scraper.decouvrir_urls_liste`/
      `collecter_depuis_listing` parcourent les pages listing paginées de hcp.ma
      (`?start=N`, palier déduit dynamiquement des liens de pagination réels, pas codé
      en dur) et en extraient les URLs d'articles (filtre double : lien dans un titre
      `<h3>` + motif d'URL `..._aXXX.html`, affiné après un faux positif trouvé en test
      sur le lien de menu "Tout sur HCP"). `data/listing_urls.py` (config des pages
      listing par catégorie — Marché du travail confirmée en réel, 50 publications/10
      pages ; Économie/Population encore partielles, sous-thèmes à inventorier).
      `scripts/decouverte_publications.py` (mode `historique` = tout le listing, mode
      `quotidien` = 1ère page seulement, même patron que le pré-remplissage BDS
      nocturne). Dédoublonnage géré par la contrainte `document.url UNIQUE` existante,
      aucun changement de schéma. Suite complète : 24/24.
      **Validé en conditions réelles le 20/07** : 10 URLs trouvées (Économie +
      Marché du travail), correspondance exacte avec les articles réels observés sur
      hcp.ma. Un cas réel a mis en évidence un trou : une page en arabe remontée par
      la découverte automatique (n'arrivait jamais avec l'ancienne liste choisie à la
      main). Corrigé : `_extraire_urls_articles` détecte la langue de chaque lien
      (même heuristique que pour les pièces jointes) et les pages arabes sont
      écartées par défaut. Inventaire complété le 20/07 : Population & démographie
      10/10 sous-thèmes trouvés (`data/listing_urls.py`) ; Économie 3 sous-thèmes
      confirmés + Études économiques, encore partiel (Indices des prix et production,
      Secteurs d'activité, Sphère informelle restants). Piste alternative repérée
      mais non exploitée : `hcp.ma/downloads/?tag=<catégorie>` — base de
      téléchargements distincte donnant directement les liens de fichiers (pas de
      page HTML intermédiaire), avec titre/date/tags déjà fournis. Changement de fond
      potentiel, à évaluer dans un ADR séparé si besoin (voir JOURNAL.md, 20/07).
- [x] Chunking + embeddings + indexation Chroma + BM25 (`src/indexeur_texte.py`,
      20/07/2026) : `IndexeurTexte.indexer(document, texte)` — découpe par paragraphe
      avec empaquetage glouton (taille cible ~1500 caractères, chevauchement ~200 —
      valeurs non fixées dans les docs de conception, choisies et justifiées en tête
      de fichier), embeddings via `sentence-transformers`/BGE-M3 (ADR 0002),
      indexation vectorielle Chroma persistante (`data/chroma/`, gitignoré) +
      BM25 (`rank_bm25`, reconstruit à la demande). `rechercher(question, top_k)` :
      recherche hybride dense + BM25, fusionnée par Reciprocal Rank Fusion (RRF,
      k=60 — pas de formule de fusion imposée par les docs, RRF choisi car il évite
      de normaliser deux échelles de score différentes). Fonction d'embedding
      injectable au constructeur pour les tests (le vrai modèle BGE-M3, ~2 Go, n'est
      pas téléchargeable dans le sandbox de dev sans accès réseau) : 15 tests avec
      chromadb/rank_bm25 réels + embedding factice. **Reste à valider avec le vrai
      modèle BGE-M3** sur la machine d'Ayman.
- [x] Script d'insertion en base (20/07/2026) : `src/base_donnees.py` (connexion +
      upsert `document`/`chunk`/`indicateur`, dédoublonnage par `url` UNIQUE pour les
      documents, upsert applicatif sur (nom, periode, region, code_bds) pour les
      indicateurs — le schéma n'a pas de contrainte UNIQUE dessus, nécessaire car le
      pré-remplissage BDS tourne à répétition). Embedding sérialisé en BLOB via le
      module standard `array` (float32). `scripts/preremplir_indicateurs_bds.py` fait
      maintenant le vrai upsert (ne se contentait que d'un résumé affiché avant).
      `scripts/indexer_documents.py` (nouveau) : Extracteur -> insertion `document` ->
      `IndexeurTexte.indexer` -> insertion `chunk`, HTML explicitement ignoré (ADR
      0003). 13 nouveaux tests (9 base_donnees + 4 indexer_documents), dont un bout en
      bout réel sur un vrai .docx généré à la volée (python-docx). Suite complète :
      52/52. **Reste hors périmètre** : `ConstructeurIndicateurs.structurer` (repli
      PDF/XLSX pour les indicateurs, toujours `NotImplementedError` — priorité basse
      depuis que l'API BDS couvre la majorité des indicateurs des 3 catégories, ADR
      0004) n'est donc pas encore branché dans `indexer_documents.py`.

**Definition of done :** les PDF/XLSX/DOCX collectés sont indexés de bout en bout
(texte + indicateurs BDS) et interrogeables par script. Aucun contenu HTML n'est
indexé. **Sprint 2 fonctionnellement complet** côté code.

**Validé en conditions réelles le 20/07** : premier run réel sur la machine
d'Ayman (`python -m scripts.indexer_documents --limite 3`) — vrai téléchargement
BGE-M3, 1 PDF réel extrait/chunké/indexé (40 chunks), pages HTML et pièces
jointes arabes correctement écartées. Recherche hybride vérifiée via
`scripts/inspecter_index.py --recherche "produit intérieur brut"` : embeddings
dimension 1024 (confirme le vrai modèle), 5/5 résultats pertinents. **Reste** :
un run plus large pour valider aussi un vrai .docx (IPC/IPPI) — voir tâche DOCX
ci-dessus.

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
