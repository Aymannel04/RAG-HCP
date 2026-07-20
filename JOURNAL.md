# Journal de bord

Une entrée courte par jour de travail (2-3 lignes chacun) — sert de base pour le rapport
de stage en fin de période, pas besoin d'être exhaustif.

## 7 juillet 2026

- Rédaction de la fiche de cadrage (nature, périmètre, problématique, objectifs, besoins,
  architecture première, risques, planning, glossaire).
- Rédaction du dossier de conception UML/Merise (cas d'utilisation, MCD, MLD, classes,
  séquences, activité).
- Mise en place du squelette de code (structure du repo, modules stub alignés sur le
  diagramme de classes, schéma SQL, premier scraper fonctionnel, tests de base).

## 15 juillet 2026

- Planning reformulé en 5 sprints (`TODO.md`) avec objectif, backlog et definition of done
  par sprint.
- Constitution de `data/seed_urls.py` : 27 URLs réelles réparties sur les 3 catégories
  ciblées (12 Économie, 6 Marché du travail, 9 Population & démographie), à partir des
  pages de rubrique de hcp.ma.
- Premier test réel du scraper (`scripts/tester_scraper_reel.py`) sur ces 27 pages :
  27/27 documents récupérés, 27/27 titres corrects, 25/27 dates trouvées du premier coup.
  Les 2 échecs de date venaient de pages où le texte est encodé en Unicode décomposé
  (accent = caractère séparé) — corrigé en normalisant en NFC avant l'extraction
  (`src/scraper.py`, `_extraire_date`). Sprint 1 quasiment bouclé, il ne reste que la
  validation des hypothèses avec l'encadrante.

<!-- Continuer une entrée par jour ci-dessous -->

## 15 juillet 2026 (suite) — correction de trajectoire

- Test du pipeline complet (Scraper + Extracteur) sur les 27 pages : 0 caractère de
  texte propre extrait, et les "tableaux" trouvés étaient en fait des menus de
  navigation. La stratégie HTML actuelle (tous les `<p>`, tous les `<table>`) ne colle
  pas au vrai gabarit de page hcp.ma.
- Confirmé avec Ayman : les vraies données (HCP, section Publications) sont fournies en
  PDF ou XLSX, pas en HTML — les pages HTML ne sont que des résumés/vitrines avec liens
  de téléchargement. Décision documentée dans `docs/adr/0003-ingestion-pdf-xlsx.md`.
- Réécrit `Scraper` : détecte maintenant les liens PDF/XLSX sur chaque page et les
  télécharge (`data/raw/`, hors dépôt), en plus du résumé HTML.
- Réécrit `Extracteur` : ajout des branches PDF (pdfplumber) et XLSX (openpyxl), en plus
  du HTML existant.
- Mis à jour `db/schema.sql` (type XLSX ajouté), `requirements.txt` (openpyxl),
  `TODO.md` (Sprint 2 recentré sur la validation PDF/XLSX en priorité).
- Rien de tout ça n'est encore testé en conditions réelles (pas d'accès réseau vers
  hcp.ma depuis le sandbox) — prochaine étape concrète avant de coder la suite.

## 15 juillet 2026 (recadrage) — périmètre confirmé : PDF/XLSX uniquement

- Ayman a confirmé le périmètre exact : le RAG doit s'appuyer uniquement sur les
  publications hcp.ma en PDF ou Excel. Le texte des pages HTML n'est jamais une donnée
  du projet — juste un moyen de découvrir les liens de téléchargement et le titre/date.
- Conséquence directe : plus la peine de corriger `Extracteur._extraire_html` (retiré du
  backlog Sprint 2). `IndexeurTexte` devra explicitement ignorer les `Document` de type
  `html` lors de l'indexation.
- ADR 0003 précisé pour verrouiller cette règle et éviter d'y revenir sans raison.

## 15 juillet 2026 (suite 2) — decouverte de l'API BDS

- Ayman a repere que bds.hcp.ma propose une API pour recuperer les donnees, en plus
  du telechargement de fichiers. Verification en direct (navigateur connecte,
  inspection du trafic reseau) : l'API existe bel et bien, non documentee
  publiquement mais librement accessible, sans authentification.
- Deux endpoints identifies : `/api/v1/subject-groups` (arborescence complete du
  catalogue, 832 indicateurs sur 7 themes) et `/api/v1/indicators/{code}` (serie
  complete d'un indicateur : toutes periodes, toutes dimensions de ventilation).
  Verifie sur 2 codes reels (I3181, I2818).
- Couverture confirmee des 3 categories du projet : Population & demographie (49
  indicateurs), Marche du travail (32), Economie (216).
- Decision actee en ADR 0004 : utiliser cette API comme source primaire des
  indicateurs chiffres (remplace en grande partie l'extraction PDF/XLSX pour cette
  partie-la), le pipeline PDF/XLSX restant necessaire pour le texte narratif et les
  publications hors catalogue.
- Cree `src/bds_client.py` (client API) et `scripts/telecharger_catalogue_bds.py`
  (telecharge et sauvegarde le catalogue local). Pas encore teste en reel depuis le
  code Python (pas d'acces reseau dans le sandbox) — premiere tache du Sprint 2.

## 15 juillet 2026 (suite 3) — traçabilité et strategie de mise à jour de l'API BDS

- Deux questions de conception laissees ouvertes par l'ADR 0004 ont ete tranchees
  avec Ayman : (1) comment tracer un indicateur qui ne vient plus d'un document
  scrape — decision : un `Document` synthetique par indicateur BDS (`type="api"`,
  url = fiche bds.hcp.ma/main/indicators/{code}) ; (2) fraicheur vs temps de reponse
  — decision : strategie hybride cache-aside (pre-remplissage nocturne des
  indicateurs cures + appel API en direct si absent du cache, avec ecriture du
  resultat dans la base pour enrichir le cache).
- ADR 0004 mis a jour avec cette section. `db/schema.sql` : `document.type` accepte
  desormais `'api'`, et `indicateur` gagne une colonne `code_bds` (cle de cache).
  `src/models.py` aligne en consequence.
- Redige `docs/complement_conception_bds.tex/.pdf` : document complementaire au
  dossier de conception initial, avec le delta MLD et deux diagrammes d'activite
  (lookup hybride cache-aside, pre-remplissage nocturne). Compile sans erreur.
- Prochaine etape concrete : test reel de `src/bds_client.py` sur la machine
  d'Ayman (`python -m scripts.telecharger_catalogue_bds`).

## 16 juillet 2026 — test réel de l'API BDS

- Lancé `python -m scripts.telecharger_catalogue_bds` sur la machine d'Ayman :
  succès, `data/bds_catalogue.json` créé, 832 indicateurs, répartition par thème
  identique à celle vue dans le navigateur (Économie 216, Marché du travail 32,
  Population & Démographie 49, + 4 autres thèmes hors périmètre projet).
- Vérifié `recuperer_indicateur("I3181")` en direct : retourne bien la fiche complète
  (label, métadonnées, 60 périodes trimestrielles de 2007T1 à 2021T4, dimensions et
  modalités de ventilation par branche d'activité).
- `src/bds_client.py` est donc validé de bout en bout en conditions réelles. Tâche
  correspondante cochée dans `TODO.md` (Sprint 2).

## 17 juillet 2026 — ConstructeurIndicateurs repensé autour de l'API BDS

- Récupéré en direct (web_fetch) la réponse réelle de `GET /api/v1/indicators/I3181` :
  la forme exacte de `data` n'était pas documentée dans l'ADR 0004 (juste "JSON
  structuré") — en réalité c'est un dict plat `{"idModalite_periode": {"value":...}}`.
  Implémenté `ConstructeurIndicateurs.structurer_depuis_bds()` en généralisant sur ce
  format (0, 1 ou plusieurs dimensions croisées) et vérifié contre la vraie réponse :
  1020 lignes construites pour I3181 (17 branches x 60 périodes), toutes correctes.
- Ajouté `construire_document_synthetique()` (Option A de l'ADR 0004 : type="api",
  url=fiche BDS, titre=label, date_publication dérivée du champ `updatingDate`).
- Récupéré (web_fetch, en 2 appels vu la taille) le catalogue réel pour les thèmes
  Population & Démographie (49) et Économie (216) ; le thème Marché du travail n'a
  pas pu être récupéré (réponse coupée avant). Constitué `data/indicateurs_cures.py`
  avec 12 codes réels vérifiés sur ces deux thèmes ; Marché du travail à compléter
  (item ajouté au TODO).
- `scripts/preremplir_indicateurs_bds.py` : orchestration bds_client -> Constructeur
  sur la liste curée (pas encore d'upsert en base, ça reste un item séparé du backlog).
- 3 nouveaux tests unitaires (`tests/test_constructeur_indicateurs.py`), mock fidèle à
  la forme réelle de l'API. Suite complète : 9/9 tests passent.
- Ayman a fourni les 32 indicateurs du thème Marché du travail depuis son
  `data/bds_catalogue.json` local. Choisi 6 codes headline (taux de chômage, taux
  net d'activité, taux d'emploi, effectif des chômeurs, chômage par sexe/région,
  structure des actifs occupés) et complété `data/indicateurs_cures.py`. Liste
  curée finale : 18 indicateurs, 6 par catégorie ciblée.

## 17 juillet 2026 (suite) — bug reel : dimensions null sur I2790

- Test reel de `scripts/preremplir_indicateurs_bds.py` sur les 18 codes cures (par
  Ayman) : I1588 et I1590 ok (273 et 6757 lignes), puis crash sur I2790 "Taux
  d'urbanisation" : `TypeError: 'NoneType' object is not iterable`.
- Cause : l'API renvoie `"dimensions": null` (pas `[]`) quand l'indicateur n'a pas de
  ventilation. `dict.get("dimensions", [])` ne rattrape pas ce cas car la cle EST
  presente, juste avec une valeur `null` — le repli par defaut de `.get()` ne joue que
  si la cle est absente.
- Corrige dans `structurer_depuis_bds` : chaque `.get(...)` a risque est suivi d'un
  `or []`/`or {}` pour absorber a la fois cle absente et valeur null. Ajoute un test de
  regression avec `dimensions: None`. Suite complete : 10/10 tests.

## 17 juillet 2026 (suite 2) — pipeline BDS valide de bout en bout sur les 18 codes

- Relance de `scripts/preremplir_indicateurs_bds.py` apres le fix dimensions=null :
  18/18 codes recuperes avec succes, 0 echec, 35561 lignes d'indicateurs construites
  au total (de 4 lignes pour I2790 "Taux d'urbanisation" a 24696 pour I3981 "Indice
  des prix a la consommation", detaille par produit et par mois).
- `ConstructeurIndicateurs` est donc valide en conditions reelles sur l'integralite
  de la liste curee, pas seulement sur I3181. Item du backlog Sprint 2 confirme.

## 17 juillet 2026 (suite 3) — detection PDF/XLSX validee, "sur-detection" non confirmee

- Decouvert que web_fetch (contrairement a curl/requests dans le sandbox, bloques par
  le proxy) peut atteindre www.hcp.ma. Recupere le HTML reel (converti en markdown par
  l'outil) de 4 pages seed representatives : note de conjoncture (1 piece jointe),
  rapport d'enquete avec tabulations (2), page RGPH regionale (8 fichiers), bulletin
  emploi trimestriel (1).
- Reconstruit fidelement les balises <a> de ces 4 pages (338 liens au total : menus,
  sidebar, reseaux sociaux, pied de page inclus) et fait tourner le vrai code
  `Scraper._detecter_pieces_jointes` dessus (pas une reimplementation).
- Resultat : 0 faux positif, 0 faux negatif sur les 4 pages. La sur-detection
  suspectee en Sprint 1 (rapport_sprint1.pdf) n'est pas confirmee par ces tests reels
  - hypothese la plus probable : confusion avec des pages ayant legitimement plusieurs
  pieces jointes (le cas RGPH regional, 8 fichiers tous reels, avait pu etre lu comme
  de la sur-detection sans verification directe du HTML a l'epoque).
- Aucune correction de code necessaire. Ajoute 2 tests de regression dans
  `tests/test_scraper.py` avec des fixtures reconstruites depuis le vrai HTML, pour
  verrouiller ce resultat. Suite complete : 12/12 tests.
- Limite assumee : test sur 4/27 pages, HTML reconstruit depuis du markdown (pas les
  octets bruts). A confirmer par un run complet sur les 27 pages en conditions 100%
  reelles depuis la machine d'Ayman pour cloturer definitivement ce point.

## 17 juillet 2026 (suite 4) — Extracteur valide sur PDF reels + decouverte DOCX

- Teste `Extracteur._extraire_pdf` (vrai code) sur les fichiers deja presents dans
  `data/raw/` (telecharges lors des tests precedents). 47 fichiers ".pdf" au total,
  mais 14 se sont reveles invalides (signatures PK ou OLE2, pas %PDF-) : verifie via
  horodatage git que ces 14 fichiers datent de 17h00-17h14 le 15/07, soit AVANT le
  commit e2fa9bc (17h20, fix `_contenu_semble_valide`). Confirmes stale, supprimes.
- Sur les 33 fichiers valides restants : 30 traites sans erreur (texte + tableaux
  coherents, de 2 a 645 tableaux selon le fichier). 2 gros PDF tres denses en tableaux
  ("Tabulations", ~4.3 Mo) n'ont pas fini l'extraction en moins de 40s dans le sandbox
  (limite d'un appel bash) - a chronometrer sans cette contrainte sur la machine
  d'Ayman. Le fichier de 14 Mo pas encore teste, faute de temps.
- Decouverte importante en cherchant un exemple de vrai .xlsx a tester : les pages
  IPC et IPPI (categorie Economie, dans seed_urls.py) ne publient leur note mensuelle
  qu'en **.docx** (FR+AR), pas en PDF ni Excel. Confirme sur 2 pages via web_fetch.
  Le lien `/attachment/{id}/` est actuellement classe "pdf" par defaut par
  `_detecter_pieces_jointes`, puis correctement rejete par `_contenu_semble_valide`
  (bon comportement defensif : pas de crash, pas de fausse donnee) mais consequence :
  ces publications finissent avec 0 contenu indexe pour le RAG.
- `_extraire_xlsx` reste donc non teste en reel (aucun vrai .xlsx trouve a ce jour).
- Question ouverte posee a Ayman : etendre le perimetre de l'ADR 0003 pour supporter
  le .docx (nouvelle branche d'extraction, python-docx), ou accepter ce trou pour la V1.

## 17 juillet 2026 (suite 5) — Implementation du support DOCX (ADR 0005)

- Ayman tranche la question ouverte : etendre le perimetre au .docx plutot
  qu'accepter le trou (IPC/IPPI sont des publications mensuelles recurrentes, avec
  du contenu chiffre et narratif propre - les laisser hors RAG serait une perte
  reelle, pas un simple detail de couverture).
- Redige `docs/adr/0005-extension-docx.md` (Statut/Contexte/Decision/Justification/
  Consequences) documentant la decouverte, la decision et son impact code.
- `db/schema.sql` : `document.type` accepte desormais `'docx'` en plus de
  `'html'/'pdf'/'xlsx'/'api'`.
- `src/models.py` : commentaire du champ `Document.type` mis a jour ; aucun autre
  changement structurel necessaire (un `Document` docx produit du texte + tableaux,
  exactement comme un PDF).
- `src/scraper.py` : nouvelle constante `EXTENSIONS_DOCX` ; `_detecter_pieces_jointes`
  reconnait maintenant les liens `.docx` (meme logique que xlsx/pdf, y compris
  `/attachment/{id}/` sans extension visible dans le href) ; `_telecharger_piece_jointe`
  reconnait le Content-Type `wordprocessingml`/`msword`. Point delicat : XLSX et DOCX
  sont tous deux des archives ZIP, donc partagent la meme signature magique `PK` -
  `_contenu_semble_valide` a du etre renforcee pour verifier en plus la presence du
  dossier interne caracteristique (`xl/` pour XLSX, `word/` pour DOCX), sinon un
  .docx aurait pu passer la validation en se faisant passer pour un xlsx corrompu
  ou l'inverse. C'est precisement ce risque qui avait cause le bug des 14 fichiers
  stale nettoyes dans l'entree precedente (des .docx sauvegardes sous extension .pdf).
- `src/extracteur.py` : nouvelle methode `_extraire_docx` (python-docx), extrait
  les paragraphes non vides (texte narratif) et les tableaux (lignes non vides
  uniquement) separement, comme pour `_extraire_pdf`. Ajoutee au dispatch de
  `extraire()` sur `document.type == "docx"`.
- `requirements.txt` : ajout de `python-docx>=1.1`.
- 6 nouveaux tests ajoutes : 3 dans `tests/test_scraper.py` (detection d'un lien
  DOCX reel - motif IPC `/attachment/2885946/` + texte "IPC_Mai 2026_Fr.docx" -,
  distinction xlsx/docx a la validation via de vrais octets ZIP generes a la volee,
  nommage de fichier avec extension .docx) et 1 dans `tests/test_extracteur.py`
  (extraction sur une fixture .docx generee en reel via python-docx, avec verification
  que les paragraphes vides ne polluent pas le texte extrait). Suite complete :
  16/16 tests passes.
- Limite assumee, explicitement notee dans l'ADR 0005 : tout ceci est valide contre
  des fixtures generees synthetiquement par python-docx, PAS contre un vrai fichier
  IPC/IPPI telecharge depuis hcp.ma. C'est la prochaine etape.

## 20 juillet 2026 — note de reponse a l'encadrante (stockage, Redis, routeur, benchmark)

- Reunion avec l'encadrante le 17 juillet : questions sur le stockage post-collecte
  (chunks vs indicateurs, limites), l'interet de Redis, pourquoi diviser la base, et
  comment le Routeur distingue une question chiffree d'une question narrative (et gere
  le cas des deux a la fois). Redige `docs/note_stockage_routage_benchmark.pdf` (LaTeX,
  style maison) en reponse.
- Point de conception identifie en re-analysant la question du "cas mixte" : le modele
  actuel de `routeur.py` (Enum CHIFFRE/NOTION, choix unique) ne gere pas correctement
  une question qui a les deux composantes. Revision proposee dans la note : deux
  signaux booleens independants (chiffre / narratif) pouvant etre vrais simultanement,
  avec dispatch parallele vers LookupStructure et RetrievalReranker si les deux sont
  positifs. A formaliser en ADR au debut de l'implementation du Routeur (semaine 3).
- Proposition Redis documentee comme couche de cache devant SQLite (pas en
  remplacement), branchee sur la strategie cache-aside deja actee en ADR 0004 -
  a documenter formellement en ADR 0006 si retenue.
- Benchmarking demande par l'encadrante sur les choix de l'ADR 0002 : scraping
  (requests+BeautifulSoup vs Scrapy vs Playwright), extraction PDF (pdfplumber vs
  PyMuPDF vs Camelot), embeddings (BGE-M3 vs OpenAI text-embedding-3-large vs
  multilingual-e5-large), index vectoriel (ChromaDB vs FAISS vs Qdrant vs pgvector),
  recherche lexicale (rank-bm25 vs BM25S vs Elasticsearch/OpenSearch), base indicateurs
  (SQLite vs PostgreSQL vs DuckDB), interface (Streamlit vs Gradio) - avec pour chaque
  brique un chemin de montee en charge si deploiement reel au-dela du prototype.
