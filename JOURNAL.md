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
- Note de correction sur la numerotation : la note ci-dessus evoquait "ADR 0006" pour
  Redis si la proposition est retenue. Ce numero a finalement ete pris par la decision
  ci-dessous (decouverte automatique des publications), traitee en premier suite a la
  demande explicite d'Ayman. La formalisation de Redis en ADR, si elle a lieu, portera
  donc le numero 0007.

## 20 juillet 2026 — decouverte automatique des publications (ADR 0006)

- Point souleve par Ayman apres la note ci-dessus : les 27 URLs de `data/seed_urls.py`
  n'etaient qu'un echantillon de depart (Sprint 1). Deux trous restaient non traites :
  (1) aucune couverture de l'historique des publications hcp.ma (des annees de
  documents), (2) aucune detection des nouvelles publications au fil du temps.
- Verification en reel sur hcp.ma (seul `web_fetch` a un vrai acces reseau dans ce
  sandbox, `bash`/`curl` restent bloques par l'allowlist du proxy) : les pages
  "vitrine" par categorie (Economie_r327, Marche-du-travail_r423,
  Population-demographie_r513) n'affichent qu'une dizaine d'actualites/publications
  recentes - PAS un archive complet. En revanche, des pages listing dediees existent,
  avec une vraie pagination :
  `https://www.hcp.ma/Publications-Marche-du-travail_r425.html` -> 50 publications
  reparties sur 10 pages de 5 (`?start=0` a `?start=45`) ; meme mecanisme verifie sur
  `Etudes-economiques_r650.html` (25 publications, 5 pages). Volume par listing modeste
  (dizaines a centaines), donc un crawl complet est realiste.
- Decision actee dans `docs/adr/0006-decouverte-automatique-publications.md` : un seul
  mecanisme de decouverte (parcourir un listing paginee, en extraire les URLs
  d'articles), utilise a deux portees - `max_pages=None` pour une collecte historique
  ponctuelle, `max_pages=1` pour une collecte de fraicheur reguliere (les listings sont
  tries du plus recent au plus ancien, donc toute nouveaute apparait en page 1). Aucun
  changement de schema necessaire : la contrainte `document.url UNIQUE` deja en place
  (ADR 0001) suffit a dedupliquer.
- Implemente dans `src/scraper.py` : `_extraire_urls_articles` (filtre double - lien
  dans un titre `<h2>-<h5>` + motif d'URL `..._aXXX.html`), `_increments_pagination`
  (paliers `?start=N` deduits des vrais liens de pagination, pas code en dur),
  `decouvrir_urls_liste` et `collecter_depuis_listing`. Premiere version du filtre
  (motif d'URL seul) laissait passer un faux positif reel trouve en ecrivant les
  tests : le lien de menu "Tout sur HCP" pointe vers `Qui-sommes-nous_a3079.html`, qui
  suit le meme motif `_aXXX.html` qu'un vrai article - corrige en exigeant en plus que
  le lien soit dans un titre de section, conforme au gabarit reel des pages listing
  (`### [titre](url) - date`).
- Nouveaux fichiers : `data/listing_urls.py` (pages listing par categorie - Marche du
  travail confirmee en reel, Economie/Population encore partielles, sous-themes a
  inventorier) et `scripts/decouverte_publications.py` (modes `historique`/`quotidien`,
  meme style que `scripts/preremplir_indicateurs_bds.py`).
- 8 nouveaux tests dans `tests/test_scraper.py` (dont la regression sur le faux positif
  "Qui-sommes-nous"), avec mocks reconstruits depuis le vrai HTML observe. Suite
  complete : 22/22 tests passes.
- Limite explicitement non traitee (documentee dans l'ADR) : un document deja connu
  peut etre revise a la meme URL - la dedup par URL ne le detecte pas. Necessiterait
  une comparaison de hash de contenu, hors perimetre de cet ADR.
- Comme pour le DOCX (ADR 0005), reste a valider en conditions reelles sur la machine
  d'Ayman (`scripts/decouverte_publications.py`), pas d'acces reseau hcp.ma ici.

## 20 juillet 2026 — inventaire des pages listing (Economie, Population) + piste /downloads/

- Complete l'inventaire de `data/listing_urls.py` en parcourant en reel les pages de
  rubrique de hcp.ma (breadcrumb "Publications" de chaque sous-theme). Resultat :
  Population & demographie 10/10 sous-themes trouves (Recensement, Structure de la
  population, Naissances et fecondite, Mortalite, Couples et familles, Vieillissement,
  Immigration, Genre, Education et formation, Sante) ; Economie 3 sous-themes confirmes
  (Comptes nationaux, Conjoncture et prevision economique, Conjoncture entreprise) + la
  page "Etudes economiques" deja connue, mais incomplet ("Indices des prix et
  production" est lui-meme un regroupement de 4 sous-sous-themes - IPC, IPPI, IPI, ICE -
  sans page Publications a lui ; "Secteurs d'activite" et "Sphere informelle" pas
  verifies). Constat important : contrairement a Marche du travail (une seule page
  agregee pour toute la categorie), Economie et Population n'ont PAS de page
  "Publications-<categorie>" globale (verifie pour Population : la page existe -
  Publications-Population-demographie_r515.html - mais est vide) ; chaque sous-theme a
  sa propre page, il faut TOUTES les donner au Scraper.
- Piste alternative decouverte en cherchant cet inventaire, volontairement pas
  exploitee tout de suite : `hcp.ma/downloads/?tag=<categorie>` est une base de
  telechargements distincte de tout ce qui precede. Trouvee via `robots.txt` ->
  `news-sitemap.xml` (sitemap Google News, ne contient que les publications des
  dernieres 48h - piste interessante pour la fraicheur) et le "Plan du site"
  (`Plan-du-site_r670.html`), qui liste tous les tags de telechargement possibles,
  alignes sur les categories/sous-themes du site. Verification en reel de
  `?tag=Dernieres+parutions` : chaque entree donne directement le lien du fichier
  (`hcp.ma/file/<id>/`, PAS une page HTML article intermediaire), avec titre, date de
  publication et TOUS ses tags (categorie + sous-theme + type de publication) deja
  fournis - potentiellement plus simple et plus riche que l'approche actuelle
  (Scraper visite une page HTML puis cherche une piece jointe dessus). Egalement
  organisee en "collections" avec compteur de fichiers (ex. "Voir tous les fichiers
  (25)"). Pas encore verifiee en profondeur (pagination, couverture reelle) : c'est un
  changement de fond du mecanisme de decouverte, pas juste un complement d'inventaire,
  donc volontairement laisse de cote pour l'instant plutot que de re-ouvrir l'ADR 0006
  a chaud. A soumettre a Ayman comme piste pour un ADR ulterieur si le mecanisme actuel
  montre ses limites.
- `data/listing_urls.py` mis a jour (Economie 4 URLs, Marche du travail 1, Population
  10 = 15 pages listing au total), commentaires a jour sur ce qui reste ouvert. Suite
  de tests inchangee (24/24, ce fichier n'a pas de tests dedies).

## 20 juillet 2026 — validation reelle de la decouverte + filtre arabe

- Ayman a execute `python -m scripts.decouverte_publications quotidien` sur sa
  machine : 5 URLs trouvees pour Economie, 5 pour Marche du travail (Population
  ignoree comme attendu, listing pas encore configure). Les 10 URLs correspondent
  exactement, titre par titre, aux articles observes en direct sur hcp.ma pendant la
  verification du 20 juillet — premier test reel du mecanisme de decouverte : succes,
  aucune correction necessaire sur la logique de pagination/extraction elle-meme.
- Un cas reel a neanmoins ete repere dans les resultats : une page en arabe
  (`Situation-du-marche-du-travail-dans-la-region-de-Rabat-Sale-Kenitra-en-2024-version-Ar_a4217.html`,
  titre de lien "... (version Ar)") remontee par la decouverte automatique. Avec
  l'ancienne liste fixe de 27 URLs, ce cas n'arrivait jamais (Ayman choisissait les
  pages a la main, toutes en francais) — la decouverte automatique, elle, remonte le
  listing tel quel, versions arabes comprises.
- Corrige dans `src/scraper.py` : `_extraire_urls_articles` detecte maintenant la
  langue de chaque lien d'article (meme heuristique `_detecter_langue` que pour les
  pieces jointes, sur un signal URL + texte du lien — "(version Ar)" dans le texte
  suffit, meme quand l'URL seule ne le signale pas clairement) ; nouvelle methode
  `_filtrer_urls_arabe` ecarte ces pages par defaut (`self.inclure_arabe`, meme regle
  que pour les pieces jointes, hors scope V1). 2 nouveaux tests avec fixture
  reconstruite depuis le cas reel trouve. Suite complete : 24/24 tests passes.

## 20 juillet 2026 — fin du Sprint 2 : indexation (chunking, embeddings, Chroma/BM25) + insertion en base

- Objectif : terminer les 3 derniers items du backlog Sprint 2 (TODO.md) demande
  par Ayman ("avancer le maximum" apres la reunion avec l'encadrante) : chunking +
  embeddings, indexation Chroma + BM25, script d'insertion en base.
- Releve prealable des decisions deja actees dans les docs de conception (fiche de
  cadrage, dossier UML) pour rester coherent avec ce qui a ete livre a l'encadrante :
  BGE-M3 + sentence-transformers, ChromaDB, rank_bm25 sont bien les choix ecrits
  (ADR 0002) ; en revanche taille de chunk, chevauchement, formule de fusion
  dense/BM25 et schema de metadonnees Chroma ne sont fixes nulle part -- ce sont
  des decisions d'implementation prises et justifiees directement dans le code.
- `src/indexeur_texte.py` : `IndexeurTexte.indexer(document, texte)` decoupe par
  paragraphe (empaquetage glouton, ~1500 caracteres, chevauchement ~200), calcule un
  embedding par chunk et les ajoute a une collection Chroma persistante
  (`data/chroma/`, gitignore). `rechercher(question, top_k)` fait une recherche
  hybride : requete Chroma (dense) + BM25 (rank_bm25, reconstruit a la demande car
  pas de persistance native), fusion par Reciprocal Rank Fusion (RRF, k=60) plutot
  qu'une moyenne ponderee -- les scores denses (cosinus, 0-1) et BM25 (non bornes)
  ne sont pas sur la meme echelle, RRF s'appuie uniquement sur le rang et evite ce
  probleme. La fonction d'embedding est injectable au constructeur : le vrai modele
  BGE-M3 (~2 Go) n'est pas telechargeable dans ce sandbox sans acces reseau (meme
  contrainte que pour hcp.ma), donc les tests (15, `tests/test_indexeur_texte.py`)
  utilisent chromadb et rank_bm25 REELS (installes et verifies dans le sandbox) mais
  une fonction d'embedding factice (vecteur binaire sur un petit vocabulaire),
  suffisante pour verifier que la recherche hybride retrouve bien le bon document
  parmi plusieurs sujets differents.
- `src/base_donnees.py` (nouveau) : connexion SQLite + upsert `document`/`chunk`/
  `indicateur`. Dedoublonnage des documents par `url` UNIQUE (deja en place, ADR
  0001/0006). Pour les indicateurs, le schema n'a pas de contrainte UNIQUE -- ajoute
  un upsert applicatif sur (nom, periode, region, code_bds) cote code : necessaire
  car le pre-remplissage BDS (ADR 0004) est prevu pour tourner a repetition
  (nocturne), et sans ca chaque execution dupliquerait toutes les lignes. Embedding
  serialise en BLOB via le module standard `array` (float32), pas de dependance
  supplementaire. 9 tests avec une vraie base SQLite temporaire (meme esprit que
  tests/test_schema.py deja existant).
- `scripts/preremplir_indicateurs_bds.py` mis a jour : fait maintenant le vrai
  upsert en base (avant, le script affichait juste un resume sans jamais ecrire en
  SQLite -- limite documentee explicitement dans son propre docstring depuis le
  16 juillet).
- `scripts/indexer_documents.py` (nouveau) : chaine Extracteur -> insertion
  `document` -> `IndexeurTexte.indexer` -> insertion `chunk`. Les documents HTML
  sont explicitement ignores (ADR 0003 : jamais indexes). Teste bout en bout avec
  un vrai fichier .docx genere a la volee (python-docx, meme pattern que les tests
  DOCX de l'ADR 0005) : extraction reelle, insertion SQLite reelle, indexation
  Chroma/BM25 reelle (embedding factice), puis verification qu'une recherche
  retrouve bien le chunk insere. 4 tests.
- Limite assumee et documentee : `ConstructeurIndicateurs.structurer` (repli
  PDF/XLSX pour les indicateurs hors catalogue BDS) reste un `NotImplementedError`
  -- pas re-ouvert aujourd'hui, priorite plus basse depuis l'ADR 0004 (l'API BDS
  couvre deja la majorite des indicateurs des 3 categories). `indexer_documents.py`
  ne branche donc pas encore cette source.
- Suite de tests complete : 52/52 (24 avant aujourd'hui + 15 IndexeurTexte + 9
  base_donnees + 4 indexer_documents).
- Sprint 2 (TODO.md) est maintenant fonctionnellement complet cote code. Reste a
  valider en conditions reelles sur la machine d'Ayman : le vrai modele BGE-M3, et
  un vrai lot de documents indexes de bout en bout (comme pour le DOCX et la
  decouverte automatique, ce sandbox n'a pas d'acces reseau vers hcp.ma).
- Question d'Ayman en repassant sur le code : la fonction d'embedding factice
  (utilisee UNIQUEMENT dans les tests, jamais dans le pipeline reel) semait un doute
  legitime sur ce qui est reellement teste vs simule. Clarifie explicitement : le
  vrai chemin (`_embarquer`, chargement de BAAI/bge-m3 via sentence-transformers)
  n'a jamais tourne pour de vrai dans ce sandbox (pas d'acces reseau pour telecharger
  le modele, ~2 Go) -- seule la logique autour (chunking, Chroma, BM25, fusion,
  insertion SQLite) a ete verifiee reellement, avec un embedding factice injecte a
  la place du modele.
- `scripts/inspecter_index.py` (nouveau) : script de demonstration/verification,
  affiche un resume lisible de la base (nombre de documents/chunks/indicateurs,
  extraits de chunks avec dimension d'embedding, exemples d'indicateurs) + option
  `--recherche "question"` pour lancer une vraie recherche hybride (avec le vrai
  modele BGE-M3 cette fois). Pense pour montrer un resultat concret a l'encadrante
  une fois que `scripts/indexer_documents.py` aura tourne en reel. Verifie
  manuellement (base peuplee via fixture + base vide) : les deux cas s'affichent
  correctement.

## 20 juillet 2026 — premier test reel de bout en bout du pipeline complet

- Ajoute `--limite N` a `scripts/indexer_documents.py` pour permettre un test rapide
  sur quelques documents avant un run complet (le premier lancement telecharge
  BGE-M3, ~2 Go, potentiellement long).
- Ayman a lance `python -m scripts.indexer_documents --limite 3` sur sa machine :
  premiere execution reelle du pipeline complet (reseau hcp.ma + telechargement et
  inference BGE-M3 + Chroma + BM25 + SQLite), jusque-la jamais possible dans ce
  sandbox (pas d'acces reseau).
- Resultat conforme a l'attendu : 2 pages HTML ignorees (ADR 0003), 2 pieces
  jointes en arabe ecartees par le filtre de langue (comportement voulu), 1 PDF
  reel ("Les comptes regionaux...") extrait, decoupe et indexe -- 40 chunks.
- Verification via `scripts/inspecter_index.py --recherche "produit interieur
  brut"` : embeddings de dimension 1024 (signature BGE-M3, confirme que le vrai
  modele a tourne, pas un stub), et les 5 resultats retournes sont tous
  effectivement pertinents sur le PIB regional, bien classes.
- Premiere preuve concrete en conditions reelles que toute la chaine Sprint 2
  (scraping -> extraction -> chunking -> embeddings BGE-M3 -> indexation
  Chroma/BM25 -> recherche hybride -> persistance SQLite) fonctionne de bout en
  bout, pas seulement en tests avec des composants factices.
- Reste a faire : lancer un run plus large (sans `--limite`, ou avec une limite
  plus haute) pour couvrir aussi un vrai document DOCX (note IPC/IPPI) et valider
  ADR 0005 en conditions reelles (tache #24, toujours en cours).

## 20 juillet 2026 — run complet reel : 151 documents, 6999 chunks, DOCX valide

- Ayman a laisse tourner `python -m scripts.indexer_documents` (sans `--limite`)
  jusqu'au bout sur les 15 pages listing (Economie, Marche du travail,
  Population et demographie). Run long (gros volume, plusieurs publications a
  pieces jointes multiples comme le RGPH 2024 avec 9 PDF distincts) mais aucune
  erreur bloquante du debut a la fin.
- Resultat final : **151 documents indexes, 6999 chunks au total**.
- Validation en conditions reelles du support DOCX (ADR 0005, tache #24,
  ouverte depuis le Sprint 1) : 2 vrais fichiers `.docx` rencontres et indexes
  avec succes ("Note sur les resultats de l'enquete nationale sur la
  migration...", 43 chunks ; "Allocution de Monsieur le Haut-Commissaire au
  Plan...", 12 chunks). Tache #24 fermee.
- Plusieurs cas limites reels bien geres, observes dans les logs : liens
  annonces comme PDF/DOCX mais dont le contenu telecharge n'est pas valide
  (ecartes via la verification de signature binaire ajoutee en Sprint 1, sans
  interrompre le run) ; filtre de langue arabe actif tout du long, aussi bien
  sur des pages article completes (cas deja connu, ADR 0006) que sur des
  pieces jointes individuelles.
- Sprint 2 est maintenant valide de bout en bout en conditions reelles, pas
  seulement fonctionnellement complet cote code : chunking, embeddings BGE-M3
  reels, indexation Chroma/BM25, persistance SQLite, et desormais les 3 formats
  de fichiers cibles (PDF, XLSX -- via extraction reelle Sprint 1, DOCX) tous
  confirmes sur de vraies publications hcp.ma.
- `docs/rapport_sprint2.pdf`/`.tex` mis a jour avec ce resultat final.

## 21 juillet 2026 — demarrage Sprint 3 : Routeur, LookupStructure, RetrievalReranker, Generateur

- Sprint 2 clos, "go ahead" d'Ayman pour attaquer le Sprint 3 (retrieval + generation,
  voir TODO.md). Releve prealable du point explicitement flagge comme bloquant dans
  l'ADR 0002 ("le choix du LLM de generation... doit etre valide avec l'encadrante") :
  jamais resolu depuis. Plutot que d'attendre, meme strategie que pour BGE-M3 en
  Sprint 2 -- fonction de generation injectable, toute la logique de grounding/citation
  ecrite et testee des maintenant, le vrai LLM restant a cabler en une ligne une fois le
  choix arrete.
- `src/routeur.py` : `Routeur.classifier` implemente par heuristique de mots-cles
  (signal narratif prioritaire sur signal chiffre -- une question comme "pourquoi le
  chomage a-t-il augmente" a les deux composantes mais seul RetrievalReranker peut
  repondre au "pourquoi"), plutot que par appel LLM comme l'envisageait le docstring
  d'origine. Deja l'option V1 proposee a l'encadrante dans
  docs/note_stockage_routage_benchmark.pdf. 11 tests, aucune dependance externe.
- `src/lookup_structure.py` : `LookupStructure(conn).rechercher_indicateur(question)`
  fait correspondre la question a un nom d'indicateur reel en base par recouvrement de
  tokens (les noms viennent tels quels de l'API BDS, ex. "Taux de chomage selon le
  Milieu, le sexe et le groupe d'ages" -- jamais formules comme une question), extrait
  region/periode de la question si mentionnees, execute une requete SQL exacte. Repli
  sur la derniere periode connue si le filtre exact ne donne rien. 7 tests avec une
  vraie base SQLite peuplee de libelles realistes (dont un cas de discrimination entre
  plusieurs indicateurs contenant tous "taux").
- `src/retrieval_reranker.py` : `RetrievalReranker.rechercher_et_trier` interroge
  `IndexeurTexte.rechercher` (Sprint 2) puis reordonne par cross-encoder. Modele choisi
  et documente dans un nouvel ADR (0007) : `BAAI/bge-reranker-v2-m3`, meme famille que
  BGE-M3 deja retenu pour les embeddings (ADR 0002) -- coherent, multilingue, open
  source, aucune dependance au point encore ouvert sur le LLM de generation (un
  reranker n'est pas un LLM generatif). Fonction de reranking injectable, 4 tests avec
  vrai IndexeurTexte/Chroma/BM25.
- `src/generateur.py` : `Generateur.generer_reponse` distingue deux chemins tres
  differents, conformement a l'analyse de la figure 5 de conception_uml_v3.pdf --
  chemin chiffre (indicateur) : gabarit de texte deterministe, AUCUN LLM, "sans marge
  d'interpretation sur le chiffre lui-meme" (citation du dossier de conception) ;
  chemin notion (chunks) : synthese necessitant un vrai LLM, fonction injectable,
  leve une erreur explicite (pas une reponse inventee) si aucune fonction n'est
  fournie et que le choix de production n'est pas encore fait. Signature etendue avec
  un parametre `question` (absent du squelette d'origine) pour que la generation
  notion reste centree sur la vraie question posee -- ecart mineur documente. 7 tests.
- `scripts/poser_question.py` (nouveau) : orchestre Routeur -> LookupStructure (si
  CHIFFRE) -> repli RetrievalReranker si aucun indicateur trouve -> Generateur --
  implementation concrete des figures 5 et 6. 4 tests bout en bout.
- Suite de tests complete du projet : 85/85 (52 avant aujourd'hui + 33 Sprint 3).
- Smoke-test manuel de `scripts.poser_question.main()` contre une base vide : atteint
  bien le vrai `IndexeurTexte._embarquer`, qui tente de charger BGE-M3 -- absent du
  sandbox (`ModuleNotFoundError: sentence_transformers`), comportement attendu et deja
  connu depuis le Sprint 2, confirme que le cablage reel fonctionne jusqu'au bout.
- Sprint 3 fonctionnellement complet cote code. Reste a valider en conditions reelles
  sur la machine d'Ayman (vrai bge-reranker-v2-m3, comme BGE-M3 en Sprint 2) et,
  surtout, a faire trancher par l'encadrante le choix du LLM de generation pour le
  chemin notion -- le chemin chiffre, lui, fonctionne deja reellement des qu'un
  indicateur est en base, sans attendre cette decision.

## 21 juillet 2026 (suite) — choix du LLM de generation tranche : Mistral

- Ayman a rapporte la reponse de l'encadrante : "n'importe quel LLM gratuit qui fait
  le travail" pour la phase prototype. Point bloquant de l'ADR 0002 (ouvert depuis le
  Sprint 1) enfin resolu.
- Comparaison des options gratuites 2026 (recherche web, voir sources dans l'echange) :
  Google Gemini (1500 req/jour, contexte 1M), Groq (Llama 3.3 70B, tres rapide,
  1000 req/jour), Mistral (~1 milliard de tokens/mois, tier "Experiment"). Point
  souleve sur toutes ces options : le tier gratuit implique generalement un opt-in a
  l'entrainement sur les prompts envoyes.
- Ayman a clarifie que ce n'est pas un probleme ici : les documents indexes par le RAG
  sont des publications deja publiques du HCP (hcp.ma), aucune donnee confidentielle
  n'est en jeu -- contrairement a l'inquietude initiale de l'ADR 0002 qui visait un cas
  plus general.
- Mistral retenu (entreprise francaise, meilleure qualite attendue en francais pour
  restituer des publications administratives/statistiques marocaines, choix plus
  simple a justifier que "un modele anglophone quelconque").
- `src/llm_mistral.py` (nouveau) : fonction `generer(question, texte_contexte)`
  compatible avec `Generateur.fonction_generation`, appel REST direct a l'API Mistral
  (`requests`, pas de SDK, coherent avec `src/bds_client.py`), prompt systeme imposant
  le grounding strict ("reponds UNIQUEMENT a partir du contexte fourni... si le
  contexte ne permet pas de repondre, dis-le explicitement"). Cle API lue depuis
  `.env` (`MISTRAL_API_KEY`, `python-dotenv` deja dans requirements.txt, jamais
  commite). 3 tests avec `requests.post` simule (meme patron que test_scraper.py) :
  erreur claire si cle absente, contenu du prompt envoye, propagation des erreurs HTTP.
- `scripts/poser_question.py` cable desormais `llm_mistral.generer` par defaut dans
  `main()`. `docs/adr/0002-stack-technique-prototype.md` mis a jour (LLM "tranche",
  justification de l'absence de risque de fuite de donnees).
- Suite de tests complete : 88/88.
- **Reste a faire** : Ayman doit creer un compte gratuit sur console.mistral.ai,
  generer une cle API, la mettre dans `.env`, puis lancer
  `python -m scripts.poser_question "question"` en conditions reelles -- premiere
  execution complete du chemin notion avec un vrai LLM, jamais testee jusqu'ici.

## 21 juillet 2026 (suite 2) — premier test reel complet du chemin notion : succes

- Petit incident de parcours resolu seul par Ayman : `.env` cree via Notepad s'etait
  enregistre en `.env.txt` (piege classique Windows, extension masquee) -- renomme,
  cle relue correctement par `python-dotenv`.
- `python -m scripts.poser_question "C'est quoi le RGPH ?"` execute en conditions
  reelles de bout en bout, pour la premiere fois avec absolument tous les composants
  reels (aucune fonction factice) : `Routeur.classifier` -> NOTION -> vrai BGE-M3
  (deja en cache) -> vrai `bge-reranker-v2-m3` (cache depuis le test precedent,
  chargement instantane) -> vrai appel Mistral (`mistral-small-latest`) -> reponse.
- Resultat : reponse en francais, correcte, sourcee avec titre exact + date + URL
  reelle de la publication ("RGPH 2024, caracteristiques demographiques et
  socio-economiques..."). Grounding respecte (pas de chiffre invente), citation
  systematique -- exactement les deux garanties visees par le projet (README.md,
  section "Idee du projet").
- Ceci valide en conditions reelles : ADR 0007 (reranker), le choix Mistral (ADR
  0002), et l'orchestration complete `scripts/poser_question.py` -- le scenario de
  la figure 6 de docs/conception_uml_v3.pdf fonctionne reellement de bout en bout,
  pas seulement en tests avec composants factices.
- Point cosmetique releve, pas bloquant : Mistral renvoie du markdown (`**gras**`)
  dans le texte -- lisible tel quel dans un futur rendu Streamlit (`st.markdown`),
  mais s'affiche litteralement dans la sortie console actuelle. A ajuster si besoin
  au moment de l'Interface (semaine 4).
- Sprint 3 desormais valide en conditions reelles sur son scenario le plus complexe
  (chemin notion). Reste a tester le chemin chiffre en conditions reelles (question
  sur un indicateur precis, ex. "quel est le taux de chomage actuel") une fois des
  indicateurs BDS presents en base (`scripts/preremplir_indicateurs_bds.py`).

## 21 juillet 2026 (suite 3) — pre-remplissage BDS a pleine echelle : 35561 lignes

- Ayman a lance `python -m scripts.preremplir_indicateurs_bds` en reel sur les 18
  codes cures (data/indicateurs_cures.py) : **35561 lignes d'indicateurs upsertees,
  0 echec**. Bien plus gros que les tests ponctuels precedents (un seul code a la
  fois) -- premiere validation a pleine echelle du pipeline complet ADR 0004
  (bds_client -> ConstructeurIndicateurs.structurer_depuis_bds -> base_donnees).
- Quelques volumes notables : I3981 (Indice des prix a la consommation) a lui seul
  24696 lignes (ventilation fine par produit/ville sans doute), I3287 (taux de
  chomage par sexe et region) 1072 lignes, I3181 (valeurs ajoutees par branche)
  1020 lignes. Confirme que `inserer_indicateur` (upsert applicatif sur nom/periode/
  region/code_bds, Sprint 2) tient la charge sans probleme visible.
- La base contient desormais de vrais indicateurs BDS complets sur les 3 categories :
  next step naturel, tester `LookupStructure`/`Generateur` (chemin chiffre, figure 5)
  en conditions reelles avec ce volume de donnees.

## 21 juillet 2026 (suite 4) — chemin chiffre valide en reel + bug reel corrige (unite BDS)

- `python -m scripts.poser_question "Quel est le taux de chomage actuel ?"` execute
  en conditions reelles : `Routeur` -> CHIFFRE, `LookupStructure` retrouve le bon
  indicateur (I4001, "Taux de chomage selon le Milieu, le sexe et le groupe d'ages")
  et la bonne periode (2025, la plus recente en base), citation source correcte
  (URL BDS + date). Confirme que la correspondance par recouvrement de tokens
  (Sprint 3) fonctionne sur de vraies donnees, pas seulement les fixtures de test.
- Bug reel trouve dans la reponse : "9 POURCENTAGE" au lieu de "9%" -- l'API BDS
  renvoie l'unite de cet indicateur en toutes lettres et en MAJUSCULES, jamais
  normalisee nulle part dans le pipeline. Jamais rencontre avant (les tests
  utilisaient "%" directement, et le seul indicateur teste manuellement en reel
  avant aujourd'hui, I3181, n'a pas ce probleme).
- Corrige dans `Generateur._unite_formatee` (nouveau) plutot que dans
  `ConstructeurIndicateurs` : "pourcentage"/"pour cent"/"percent" -> "%" (sans espace
  avant) ; unites longues -> minuscules avec espace avant ; codes courts (<=4
  caracteres, ex. "MAD", "USD") laisses tels quels -- probablement des codes devise/
  unite a ne pas alterer. Choix deliberе de corriger au moment de l'affichage plutot
  qu'a la source : la valeur brute de l'API reste inchangee en base (traçabilite).
  3 nouveaux tests de regression (pourcentage majuscule, unite longue, code court).
- Suite de tests complete : 91/91.
- **Sprint 3 desormais valide en conditions reelles sur ses deux scenarios** (figures
  5 et 6 de docs/conception_uml_v3.pdf), avec tous les composants reels (BGE-M3,
  bge-reranker-v2-m3, Mistral, API BDS) et un vrai bug de conditions reelles trouve
  et corrige au passage -- exactement le genre de probleme qu'aucun test avec donnees
  factices n'aurait pu reveler.

## 21 juillet 2026 (suite 5) — deuxieme bug reel : faux-positif de LookupStructure

- Ayman a teste "Quel est le taux de travail ?" (question volontairement approximative,
  pas un vrai libelle d'indicateur) : reponse confiante mais fausse -- "Taux
  d'urbanisation, 62.8%", sans rapport avec la question.
- Cause : presque tous les noms d'indicateurs BDS commencent par "Taux", donc avec
  seulement ce mot en commun, la quasi-totalite des indicateurs de la base decrochait
  le meme score de recouvrement (1) -- le tie-break (premier insere en base) tranchait
  alors arbitrairement en faveur de "Taux d'urbanisation" plutot que "Taux net
  d'activite"/"Taux d'emploi" (plus pertinents pour "travail"), sans aucun signal
  d'incertitude dans la reponse. Plus grave que le bug d'unite precedent : c'est
  exactement le risque que le projet est cense eliminer (chiffre officiel associe au
  mauvais indicateur, presente avec la meme confiance qu'une bonne reponse).
- Corrige dans `LookupStructure._meilleur_nom_correspondant` : si plusieurs noms sont
  a egalite sur le meilleur score ET que ce score vaut seulement 1 (un seul mot
  partage, typiquement "taux"), la correspondance est jugee trop ambigue -> renvoie
  None -> le Routeur bascule sur RetrievalReranker (repli deja en place depuis
  l'orchestration Sprint 3) plutot que d'inventer un indicateur. Un score de 1 SANS
  ambiguite (mot distinctif unique, ex. "urbanisation") reste accepte -- verifie par
  un nouveau test dedie, pour ne pas sur-corriger et rejeter des matchs legitimes.
- 2 nouveaux tests de regression (match ambigu -> None ; mot distinctif unique ->
  toujours accepte). Suite complete : 93/93.
- Ayman a valide les deux cas en reel : "taux de travail" bascule desormais
  proprement sur RetrievalReranker, avec une reponse Mistral qui reconnait
  explicitement l'absence de cet indicateur et propose les libelles disponibles
  (taux d'activite, d'emploi, de chomage) -- comportement anti-hallucination
  exemplaire, meilleur que prevu. "Taux d'urbanisation" continue de matcher
  correctement (pas de sur-correction).

## 21 juillet 2026 (suite 6) — troisieme bug reel : sensibilite aux accents

- Test bonus d'Ayman ("Quel est le taux de chomage pour les femmes", sans accent sur
  "chomage") : la question bascule a tort sur RetrievalReranker au lieu du chemin
  chiffre -- reponse quand meme correcte et sourcee (18,3 %, tiree d'un rapport texte
  via Mistral), mais ce n'est pas le chemin voulu. Le vrai indicateur BDS structure
  (I4001, avec ventilation par sexe) existe bien en base et aurait du repondre.
- Cause : `LookupStructure._tokeniser` comparait les tokens sans normaliser les
  accents -- "chomage" (tape sans accent, tres frequent en usage reel/clavier) et
  "chômage" (tel quel dans le libelle BDS) sont deux tokens differents pour un set
  Python, donc aucun recouvrement sur ce mot precis.
- Corrige par une fonction `_normaliser_accents` (unicodedata, decomposition NFD +
  filtrage des marques diacritiques) appliquee a la fois dans `_tokeniser` et dans
  `_extraire_region` (meme probleme potentiel sur des noms de region accentues,
  ex. "Rabat-Salé-Kénitra"). 2 nouveaux tests de regression (indicateur et region
  sans accents). Suite complete : 95/95.
- Trois bugs reels trouves et corriges le meme jour sur `LookupStructure`/
  `Generateur`, tous invisibles dans les tests avec donnees factices -- confirme
  la valeur du test en conditions reelles a chaque etape plutot qu'une seule
  passe finale.
- Test de confirmation d'Ayman ("Quel est le taux de chomage pour les femmes") :
  route desormais bien vers `LookupStructure`, MAIS renvoie le taux national tous
  sexes confondus, pas le taux feminin -- le "pour les femmes" n'est pas pris en
  compte. Cause : les libelles BDS ("Feminin"/"Masculin") ne partagent aucun mot
  avec "femmes"/"hommes". Delibérément PAS corrige aujourd'hui (contrairement aux
  3 bugs precedents) : un mapping de synonymes naif risquerait de renvoyer un
  sous-groupe tres specifique (croisement sexe+milieu+age dans le meme champ
  `region`) maquille en taux feminin general -- pire que l'actuelle reponse
  agregee honnete. Documente comme limite connue dans TODO.md, a traiter
  proprement dans un sprint dedie plutot qu'en correctif rapide.

## 28 juillet 2026 — filtrage demographique corrige, decouverte d'une base locale perimee

- Avant de resoudre la limite ci-dessus, inspection de `data/hcp_rag.db` (vraie base,
  pas les tests) pour voir les formes reelles du champ `region` par indicateur --
  demande explicite d'Ayman de ne pas se limiter a sexe/milieu/age. Resultat : le
  champ `region` sert en realite a stocker n'importe quelle ventilation BDS, pas
  seulement geographique -- confirme 3 autres familles reellement presentes dans les
  18 indicateurs cures : niveau de diplome (`Structure des actifs occupes` : "Sans
  diplome"/"Niveau moyen"/"Niveau superieur"), branche d'activite (17 valeurs reelles
  sur `Valeurs ajoutees...`, dont deux pseudo-agregats "PIB"/"PIB hors agriculture"),
  et un libelle d'agregat incoherent selon l'indicateur ("National" pour certains,
  "Total" pour d'autres, jamais NULL alors que la logique d'origine supposait NULL =
  agregat).
- Decouverte annexe non prevue : la base locale actuelle ne contient que 1895 lignes
  d'indicateurs au total, contre les 35561 lignes documentees le 21/07 (voir plus
  haut). I1590 et I3287, qui avaient alors respectivement 6757 et 1072 lignes
  ventilees reelles, n'ont aujourd'hui plus que des lignes agregees (`region IS
  NULL`) -- la base semble avoir ete reinitialisee/reduite depuis, sans trace dans ce
  journal. Signale a Ayman : `python -m scripts.preremplir_indicateurs_bds` doit etre
  relance sur sa machine pour reconstituer les vraies donnees ventilees avant de
  pouvoir demontrer le filtrage demographique en conditions reelles.
- Correctif implemente dans `src/lookup_structure.py` : dictionnaire de synonymes par
  categorie de dimension (milieu/sexe/niveau de diplome/branche d'activite,
  extensible), resolution generique de la ventilation demandee (eclatement de
  `region` en labels individuels, recherche de la combinaison la plus precise qui
  couvre tous les labels demandes), et refus explicite (renvoie `None`) en cas
  d'ambiguite entre plusieurs combinaisons aussi precises -- au lieu de deviner.
  Corrige au passage un bug latent distinct : les indicateurs sans aucune ligne
  agregee (ex. diplome uniquement) pouvaient renvoyer une categorie arbitraire comme
  si elle representait toute la population ; renvoie desormais `None` dans ce cas.
- 7 nouveaux tests (`tests/test_lookup_structure.py`), donnees realistes pour chaque
  cas : croisement sans ligne marginale (refus attendu), croisement avec ligne
  marginale (resolution attendue), dimension simple avec/sans label agregat,
  diplome, branche d'activite. Suite complete : 102/102, aucune regression.
- Reste a valider en conditions reelles une fois la base repeuplee (voir
  decouverte ci-dessus) : verifier si l'API BDS publie de vraies lignes marginales
  par sexe seul pour I4001/I3287/I1590, ou si elle ne publie que des croisements
  complets -- dans ce dernier cas `LookupStructure` continuera de repondre `None`
  honnetement plutot que par le mauvais chiffre, mais la fonctionnalite restera
  moins utile qu'espere. Limite mise a jour dans TODO.md.

## 28 juillet 2026 (suite) — vraie cause racine : bug de parsing des cles dimension, pas une limite de donnees

- Ayman relance `python -m scripts.preremplir_indicateurs_bds` en reel : 35561 lignes,
  0 echec, coherent avec le run du 21/07 -- la base etait bien perimee, maintenant
  reconstituee. Test immediat : `poser_question.py "Quel est le taux de chomage des
  femmes ?"` repond 9% pour 2025.
- Verification : 9% est l'agregat national d'I4001, pas le taux feminin -- confirme
  en inspectant `data/hcp_rag.db` directement (une seule valeur de `region` pour
  I4001/I3287/I1590 : `None`). Pas coherent avec les 6757/1072 lignes "ventilees"
  documentees le 21/07 pour I1590/I3287 -- ces lignes existaient bien en nombre, mais
  avaient DEJA `region=None` a l'epoque (mal interprete a tort comme des lignes
  ventilees dans la relecture du journal du matin).
- Script de diagnostic cree (`scripts/diagnostic_dimensions.py`) pour afficher la
  reponse API brute d'un indicateur. Ayman le lance sur I4001 : `dimensions` N'EST
  PAS vide -- 3 dimensions reelles (Milieu, Age, Sexe), chacune avec plusieurs
  modalites ET une modalite marquee `"total": true` (l'agregat de cette dimension
  precise : "National" pour Milieu, "15 ans et plus" pour Age, "Total" pour Sexe).
  540 entrees dans `data`, cles de la forme `"11.14.21_2014"`.
- Cause racine identifiee : `ConstructeurIndicateurs.structurer_depuis_bds` supposait
  (docstring d'origine, jamais verifie contre un indicateur reellement multi-
  dimensions avant aujourd'hui) que les ids de modalite etaient joints par `"_"`
  comme la periode. En realite ils sont joints par un POINT a l'interieur d'un seul
  segment separe de la periode par `"_"` (`"11.14.21_2014"`, pas
  `"11_14_21_2014"`). `cle.split("_")` sur cette forme reelle donne `["11.14.21",
  "2014"]` : le prefixe `"11.14.21"` echoue `str.isdigit()` (a cause des points) et
  est silencieusement rejete -- `region` tombe TOUJOURS a `None`, pour absolument
  toutes les lignes de tout indicateur a plusieurs dimensions croisees. I3181
  (branche d'activite, UNE seule dimension) n'etait jamais touche par ce bug -- ses
  cles n'ont jamais eu besoin de points (`"250_2007T1"`). D'ou l'illusion d'un
  probleme de correspondance de synonymes cote `LookupStructure` (limite documentee
  le 21/07) : le vrai probleme etait en amont, dans la construction meme de
  `indicateur.region`.
- Corrige : `structurer_depuis_bds` fait maintenant `cle.rsplit("_", 1)` (isole la
  periode par le dernier `"_"`) puis `prefixe.split(".")` (eclate les ids de
  modalite). Exploite aussi le flag `"total": true` de l'API : les modalites
  agregees sont exclues de `region`, qui ne garde que les dimensions reellement
  specifiques -- une ligne "sexe=Feminin, milieu=agrege, age=agrege" donne
  `region="Feminin"`, pas une longue chaine avec les labels d'agregat inclus. Une
  ligne entierement agregee (toutes dimensions a leur modalite total) donne
  `region=None`, coherent avec la convention deja utilisee pour les indicateurs sans
  ventilation du tout.
- Effet de bord decouvert en ecrivant le test de regression : le vrai label BDS pour
  "Feminin" n'a PAS d'accent (`"Feminin"`, verifie sur la reponse reelle d'I4001),
  alors que `src/lookup_structure.py` utilisait `"Féminin"` (accentue) comme valeur
  canonique dans son dictionnaire de synonymes -- une simple egalite de chaine entre
  le canonique et les vrais labels aurait donc echoue silencieusement, meme apres le
  fix de `structurer_depuis_bds`. Corrige : la resolution passe maintenant par une
  forme normalisee (accents retires) des deux cotes plutot que par egalite stricte,
  qui tolere aussi bien "Feminin" que "Féminin" cote donnees reelles.
- 2 nouveaux tests de regression (forme de cle reelle d'I4001 sur
  `ConstructeurIndicateurs`, label BDS non accentue sur `LookupStructure`). Suite
  complete : 104/104.
- A refaire par Ayman : relancer `preremplir_indicateurs_bds` une derniere fois (le
  code de parsing a change depuis le dernier remplissage) puis retester la question
  sur les femmes -- devrait cette fois refleter une vraie ligne "Feminin" si l'API la
  publie effectivement (probable vu la modalite "total" explicite par dimension).
- **Confirme** : Ayman relance le pre-remplissage (35561 lignes, 0 echec) puis
  `poser_question.py "Quel est le taux de chomage des femmes ?"` -> **20.5% (2025,
  Feminin)**, different des 9% de l'agregat national obtenus avant le fix. Chaine
  complete validee : parsing des cles -> `region="Feminin"` en base ->
  `LookupStructure` la retrouve sans ambiguite -> `Generateur` la mentionne dans la
  reponse et cite la source BDS. Limite du 21/07 (filtrage demographique) et son vrai
  bug racine (parsing des cles dimension) tous deux definitivement resolus.

## 28 juillet 2026 (suite 2) — trou distinct trouve dans Routeur en testant d'autres domaines

- Ayman teste "Quelle est la structure des actifs occupés sans diplôme ?" (question
  suggeree pour couvrir le cas diplome explicite sur I2863) : reponse plausible et
  sourcee (47.2% national / 36.9% urbain / 59.7% rural), MAIS source = un rapport PDF
  ("Activité, emploi et chômage, résultats annuels 2025"), pas l'URL BDS de
  l'indicateur -- signe que la question est passee par RetrievalReranker/NOTION, pas
  par LookupStructure/CHIFFRE. Le correctif du jour sur la ventilation n'a donc pas
  ete sollicite du tout ici.
- Cause : `src/routeur.py`, liste `MOTS_CHIFFRE` ne contenait que des tournures
  centrees sur "taux"/"nombre"/"valeur"/"indice"/"pourcentage" -- "structure des
  actifs occupés" ne matche aucun mot-cle des deux listes (`MOTS_NOTION` non plus),
  et le classifieur retombe sur NOTION par defaut (comportement volontaire, docstring
  du module : plus sur de sur-classer NOTION que CHIFFRE). Degradation propre (la
  reponse reste correcte et sourcee via le texte), mais le chemin chiffre exact
  n'est jamais tente.
- Corrige : ajout de tournures reelles (`structure de/des`, `répartition de/des`,
  `part de/des`, `proportion de/des`, `effectif de/des`, `espérance de vie`,
  `valeurs ajoutées`, `population de/du`) a `MOTS_CHIFFRE`, choisies en reprenant les
  vrais noms d'indicateurs cures (`data/indicateurs_cures.py`) plutot que devinees au
  hasard. 7 nouveaux tests de regression (`tests/test_routeur.py`), suite complete :
  111/111.
- A confirmer par Ayman : retester "Quelle est la structure des actifs occupés sans
  diplôme ?" -- devrait maintenant citer directement l'indicateur BDS (I2863) via
  LookupStructure plutot qu'un rapport PDF via RetrievalReranker.

## 28 juillet 2026 (suite 3) — Routeur : filet de securite LLM en dernier recours

- Proposition d'Ayman suite au trou trouve juste avant : plutot que de completer
  `MOTS_CHIFFRE`/`MOTS_NOTION` a la main a chaque nouveau cas trouve (jeu perdant a
  long terme), ajouter un appel LLM pour les questions qu'aucune des deux listes ne
  sait classer. Idee deja evoquee dans
  `docs/note_stockage_routage_benchmark.pdf` (V2, explicitement repoussee a l'epoque
  en faveur d'une V1 heuristique) -- jamais implementee jusqu'ici.
- Implemente comme filet de securite, pas comme remplacement : `Routeur.__init__`
  accepte `fonction_classification_llm` optionnelle (meme patron d'injection que
  `fonction_generation` de `Generateur`), appelee uniquement si `MOTS_NOTION`,
  `MOTS_CHIFFRE` et `PATTERN_PERIODE` n'ont RIEN tranche -- l'heuristique reste le
  chemin principal (rapide, gratuit, deterministe), le LLM n'intervient que sur les
  cas vraiment ambigus. Appel entierement defensif : exception reseau, cle API
  absente, ou reponse inattendue (autre chose que "CHIFFRE"/"NOTION") sont toutes
  traitees comme "ne sait pas" et retombent sur le meme defaut NOTION qu'avant --
  aucune regression possible meme si le LLM est indisponible.
- Nouvelle fonction `llm_mistral.classifier_question` (prompt dedie, temperature 0.0,
  timeout 15s) injectee dans `scripts/poser_question.py`.
- 8 nouveaux tests avec fonctions factices (`tests/test_routeur.py`) : CHIFFRE/NOTION
  renvoyes par le LLM, exception qui ne fait pas planter, reponse inattendue qui
  retombe sur NOTION, normalisation espaces/casse, ET un test qui prouve que le LLM
  n'est JAMAIS appele quand l'heuristique a deja tranche (fonction factice qui leve
  une AssertionError si appelee). Suite complete : 118/118.
- A tester par Ayman en conditions reelles : poser une question chiffree avec un
  vocabulaire volontairement absent des deux listes (ex. "Quel est le montant des
  exportations marocaines ?" -- "montant" n'est dans aucune liste) et verifier que le
  LLM la reclasse correctement en CHIFFRE plutot que de tomber sur NOTION.
- **Confirme** : "Quel est le montant des exportations marocaines ?" correctement
  reclasse CHIFFRE par le LLM, reponse sourcee directement sur l'indicateur BDS I1437.

## 28 juillet 2026 (suite 4) — cas mixte du Routeur : dispatch parallele et fusion

- Derniere limite ouverte de la synthese Sprint 2/3 (Q4) : une question comme
  "pourquoi le chomage a-t-il augmente ?" a une composante chiffree ET narrative,
  mais seul le signal narratif etait retenu (priorite au narratif en cas de conflit) --
  LookupStructure n'etait jamais sollicite, alors que la proposition initiale de
  l'encadrante (20/07) envisageait un dispatch parallele des deux chemins avec fusion
  des resultats.
- Implemente : `TypeQuestion.MIXTE` (nouvelle valeur de l'enum), renvoye quand un
  signal narratif ET un signal chiffre sont tous les deux presents dans la question.
  Piege identifie et evite en ecrivant les tests : associer N'IMPORTE quel mot de
  `MOTS_NOTION` a un mot de `MOTS_CHIFFRE` aurait casse des questions purement
  notionnelles qui citent un nom d'indicateur sans rien demander de chiffre -- ex.
  "Comment est calcule l'indice des prix a la consommation ?" contient "indice des"
  (signal chiffre) ET "comment" (signal narratif), mais ne demande aucun chiffre.
  Solution : `MOTS_NOTION_COMBINABLES`, un sous-ensemble de `MOTS_NOTION` limite aux
  mots qui parlent d'evolution/cause d'une valeur dans le temps (pourquoi, tendance,
  evolution, analyse, cause, raison) -- seuls ceux-la peuvent declencher MIXTE en
  presence d'un signal chiffre. Les mots purement definitionnels/methodologiques
  (comment, expliquer, definir, methodologie, difference entre) gardent l'ancien
  comportement : NOTION pur, quel que soit ce qui les accompagne.
- `scripts/poser_question.py` : nouveau branchement MIXTE qui interroge LookupStructure
  ET RetrievalReranker (dispatch parallele reel, pas sequentiel avec repli). Degrade
  proprement a chaque etage : indicateur + chunks trouves -> reponse fusionnee ;
  indicateur seul -> reponse chiffree seule ; rien trouve en base structuree -> repli
  sur le chemin notion seul.
- `src/generateur.py` : nouvelle dataclass `ContexteMixte(indicateur, chunks)` et
  methode `_generer_reponse_mixte`. Principe respecte : le chiffre reste TOUJOURS
  produit par le gabarit deterministe (`_phrase_chiffree`, factorisee depuis
  `_generer_reponse_chiffree` pour eviter la duplication), jamais reformule par le
  LLM -- celui-ci ne sert qu'a expliquer le "pourquoi", avec le chiffre officiel
  injecte en tete de son contexte pour que son explication reste coherente avec la
  valeur deja citee. `Reponse` etendue avec trois champs optionnels
  (`source_url_secondaire`, etc.) pour citer les deux sources quand elles different
  (l'indicateur BDS et le document narratif ne sont pas toujours le meme document) --
  champs vides par defaut, aucune regression sur les chemins chiffre/notion purs.
- 11 nouveaux tests (routeur : signal combinable vs non-combinable, LLM peut aussi
  renvoyer MIXTE ; generateur : fusion, meme document donc pas de source secondaire,
  degradation sans chunks, degradation sans fonction_generation ; poser_question :
  bout en bout mixte avec vraies bases SQLite/Chroma temporaires). Suite complete :
  130/130, aucune regression sur les 119 tests existants.
- Reste a valider en conditions reelles par Ayman :
  `python -m scripts.poser_question "Pourquoi le taux de chomage a-t-il augmente ?"`
  devrait maintenant citer le chiffre exact ET une explication sourcee, potentiellement
  deux sources distinctes.

## 28 juillet 2026 (suite 5) — cache Redis + historique de conversation

- Ajout demande par Ayman en dehors du planning initial, explicitement pour la
  pratique de Redis (choix confirme via question directe : "je veux bien learn redis
  donc je pense on perd rien si on le fait") -- pas une necessite de performance, SQLite
  tient sans probleme au volume actuel (35561 lignes). Deux besoins distincts geres
  dans le meme module par souci de coherence (meme client Redis injectable) :
  - `CacheReponses` : cache question -> reponse, pour eviter de rappeler le LLM sur une
    question deja posee. Scope volontairement restreint au chemin NOTION pur (confirme
    par Ayman : "juste les questions an relation avec narratif") -- le chemin CHIFFRE
    est deja une requete SQL directe (rien a gagner), et le chemin MIXTE en est
    explicitement exclu pour ne jamais resservir un chiffre potentiellement perime a
    cote d'une explication figee. TTL 24h, aligne sur le cycle de rafraichissement du
    corpus (`decouverte_publications.py --quotidien`) pour ne jamais ignorer une
    publication nouvellement indexee.
  - `HistoriqueConversation` : historique de conversation par session, enregistre
    toutes les questions quel que soit leur type (c'est un journal pour l'interface,
    pas une optimisation). Cle = `id_session`, generee et retenue par l'interface
    (Streamlit aujourd'hui), jamais par ce module -- decision volontaire pour rester
    deployable ailleurs qu'en Streamlit un jour (discute explicitement avec Ayman :
    "l'utilisation de streamlit est juste pour cette version de prototype, what if we
    wanna deploy it otherwise").
- Correspondance question -> cache choisie EXACTE pour cette V1 (question normalisee :
  minuscules, espaces reduits), pas semantique -- confirme par Ayman ("le plus pratique
  et le faire en premier temps et embedding semantique en deuxieme temps"). Une
  correspondance semantique reste une extension V2 possible, avec le risque de faux
  positif a calibrer d'abord.
- `redis` et `fakeredis` installables via pip dans le sandbox (contrairement a un vrai
  serveur Redis, qui necessite root/sudo, indisponibles ici) -- `fakeredis` fournit un
  faux serveur en memoire avec la meme API, suffisant pour tester toute la logique de
  branchement sans jamais faire tourner de vrai serveur.
- `src/cache_redis.py` (nouveau) : `normaliser_question`, `CacheReponses`,
  `HistoriqueConversation`. Meme patron d'injection que partout ailleurs dans le
  projet (`client_redis=None` par defaut, degradation silencieuse -- jamais d'erreur
  si Redis absent, un cache absent doit se comporter comme un cache qui rate toujours).
  13 tests avec `fakeredis` (`tests/test_cache_redis.py`).
- Cable dans `scripts/poser_question.py` : `poser_question` accepte `cache`/
  `historique`/`id_session`, tous optionnels et `None` par defaut -- aucune regression
  possible sur les appels existants (verifie explicitement par un test de non-
  regression). Cache verifie seulement dans la branche NOTION (avant ET apres calcul :
  hit -> reponse retournee directement sans reranker ni generation ; miss -> calcul
  normal puis enregistrement). Historique ajoute a la toute fin, apres le calcul,
  quel que soit le chemin emprunte. `main()` tente une connexion a un vrai serveur
  Redis local (`localhost:6379`) et se degrade silencieusement si indisponible
  (`_connecter_redis`, capture toute exception).
- 7 nouveaux tests de cablage dans `tests/test_poser_question.py`, dont un avec un
  faux reranker qui leve une erreur s'il est appele (preuve que le cache hit
  court-circuite bien tout recalcul), et un qui verifie que le cache reste vide apres
  une question CHIFFRE ou MIXTE. Suite complete : 150/150, aucune regression sur les
  130 tests existants.
- `requirements.txt` (`redis>=5.0`, `fakeredis>=2.20`) et `README.md` (section
  installation Redis local, WSL ou Docker) mis a jour.
- **Valide en conditions reelles le 28/07 (suite)** : Redis lance via Docker Desktop
  (`docker run -d --name redis-hcp -p 6379:6379 redis`). Premier obstacle reel,
  attendu vu le patron de degradation silencieuse du projet : le paquet Python
  `redis` manquait dans le venv d'Ayman (`requirements.txt` mis a jour apres la
  creation du venv, jamais reinstalle) -- `_connecter_redis()` avalait l'erreur sans
  prevenir, le cache tournait a vide sans message. Diagnostique en testant
  directement `redis.Redis(...).ping()` en dehors du script, meme demarche que les
  bugs precedents du 28/07 (diagnostic isole avant de re-tester le pipeline complet).
  Corrige par `pip install -r requirements.txt`. Une fois le paquet installe :
  `python -m scripts.poser_question "C'est quoi le RGPH ?"` lance deux fois de suite
  -> deuxieme reponse identique mot pour mot a la premiere, confirmant que le cache
  sert bien la reponse en cache sans rappeler Mistral. Cache Redis + historique
  entierement valides, code et conditions reelles.

## 23 aout 2026 — interface Streamlit + salutation ignoree par le Routeur

- `src/interface.py` implemente (Sprint 4) : chat Streamlit au-dessus du pipeline
  existant, sans logique metier propre. Modeles lourds (BGE-M3 + cross-encoder) charges
  via `st.cache_resource` (persistant entre reruns/sessions) ; connexion SQLite
  volontairement NON mise en cache (thread-safety : `st.cache_resource` est un cache
  global partage entre toutes les sessions, `sqlite3.Connection` n'est pas partageable
  entre threads) ; `id_session` genere une fois par session via `st.session_state` ;
  historique affiche relit `HistoriqueConversation.recuperer()` a chaque rerun (persiste
  au F5, contrairement a une simple liste Python locale).
- Premier test reel : le process a plante en pleine reponse ("Connection error" cote
  navigateur), sans trace Python dans le terminal -- diagnostique via le Gestionnaire des
  taches Windows : memoire a 96%, la cause est l'OS qui tue le process (BGE-M3 +
  cross-encoder + tout le reste ouvert sur la machine d'Ayman, dont `VmmemWSL` a lui
  seul 1.6 Go pour Docker/Redis). Pas un bug de code.
- En testant une deuxieme fois, une vraie limite fonctionnelle est apparue : poser
  "hello"/"salut" comme question fait partir le Routeur par defaut sur NOTION (aucun mot-
  cle de `MOTS_NOTION`/`MOTS_CHIFFRE` ne matche une salutation), donc une vraie recherche
  semantique + appel LLM pour une politesse -- gaspillage de ressources (aggrave le
  probleme memoire ci-dessus) et reponse de refus techniquement correcte mais peu
  naturelle pour l'utilisateur.
- Corrige par un troisieme type de routage, `TypeQuestion.SALUTATION` (`src/routeur.py`) :
  detecte par regex avec frontieres de mot (`\b...\b`, pour eviter qu'un mot comme "hi"
  matche a tort a l'interieur de "chiffre"), verifie seulement APRES notion/chiffre pour
  qu'une question du type "Bonjour, quel est le taux de chomage ?" continue de repondre a
  la vraie question. `scripts/poser_question.py::_reponse_salutation` court-circuite
  entierement le pipeline pour ce type (pas de lookup, pas de reranker, pas de LLM,
  reponse canned instantanee), avec deux gabarits (accueil vs cloture/remerciement).
  22 nouveaux tests (`test_routeur.py`, `test_poser_question.py`, dont un qui prouve
  explicitement que le reranker/generateur ne sont jamais appeles). Suite complete :
  172/172, aucune regression.

## 23 aout 2026 (suite) — bug reel : projection future prise pour la valeur actuelle

- Teste en reel via l'interface Streamlit : "population de maroc" renvoyait 43562
  (en milliers) pour la periode 2050, alors que "population actuelle" (formulee
  differemment, donc classee NOTION au lieu de CHIFFRE) renvoyait correctement 37,0
  millions sourcee sur les Cahiers du Plan. Cause : l'indicateur I1588 ("Population du
  Maroc par annee civile ... 1960-2050") melange donnees observees et projections dans
  la meme serie API BDS, sans distinction. `LookupStructure.rechercher_indicateur`
  faisait "ORDER BY periode DESC LIMIT 1" sans filtre quand aucune annee n'est demandee
  -- "2050" etant la plus grande chaine, elle etait toujours choisie, peu importe
  qu'elle soit une projection a 24 ans dans le futur.
- Corrige : quand aucune annee n'est explicitement demandee dans la question, la
  requete exclut desormais les periodes posterieures a l'annee en cours
  (`datetime.date.today().year`) avant de prendre la plus recente restante. Une annee
  future explicitement demandee (ex. "population en 2050") reste servie normalement --
  seul le comportement PAR DEFAUT change.
- 2 nouveaux tests dans test_lookup_structure.py (reproduisent le cas reel I1588 avec
  des periodes relatives a l'annee en cours, donc pas de date codee en dur). Suite
  complete : 174/174.
- Egalement observe dans ce meme test : l'assistant ne peut pas "expliquer" un chiffre
  qu'il a lui-meme donne dans un tour precedent (question de suivi "comment t'as dit
  43562... explique") -- limite connue et acceptee pour l'instant, l'historique
  n'alimente que l'affichage, pas le contexte envoye au LLM. A noter pour la section
  "limites" du rapport de stage, pas un bug a corriger dans le temps restant.

## 23 aout 2026 (suite 2) — memoire conversationnelle (Option C, discutee et choisie avec Ayman)

- Demande explicite d'Ayman apres le test reel precedent : "le chat doit etre un vrai
  chat pas un q and a" -- l'historique n'etait affiche que pour l'interface, jamais
  reinjecte dans le pipeline, donc chaque question etait traitee independamment.
- Discussion de 3 options (A: injecter l'historique brut dans le prompt de generation
  seulement -- pas d'appel LLM en plus mais ne resout pas la recherche ; B: reformuler
  systematiquement CHAQUE question via LLM avant routage -- resout tout mais double le
  cout/latence meme sur les questions deja autonomes ; C: hybride, une heuristique
  gratuite decide d'abord si la question ressemble a un follow-up ambigu, LLM appele
  seulement dans ce cas). Ayman a choisi C apres explication detaillee des compromis.
- Nouveau module `src/reformulateur.py` : `ressemble_a_un_followup` (heuristique pure,
  meme esprit que Routeur -- mots referentiels explicites comme "ça"/"ce chiffre"/
  "explique", ou question trop courte une fois les mots-outils retires) et
  `reformuler_si_necessaire` (orchestration defensive : ne reformule que si un
  historique existe ET qu'une fonction est injectee ET que l'heuristique se declenche ;
  toute exception ou reponse vide retombe sur la question originale).
- `llm_mistral.reformuler_question` : nouvelle fonction, meme patron que `generer`/
  `classifier_question` (cle API, gestion d'erreur, prompt systeme dedie).
- `scripts/poser_question.py` : nouveau parametre optionnel `fonction_reformulation`
  (defaut None, aucune regression). La salutation est detectee AVANT toute tentative de
  reformulation (elle se comprend toujours seule). Pour toute autre question,
  `question_effective` (eventuellement reformulee) alimente la classification, le
  lookup, la recherche, le cache ET la generation -- mais `historique.ajouter` garde
  toujours la question ORIGINALE telle que tapee, jamais la version reformulee.
- Cablage dans `main()` et `src/interface.py` : `fonction_reformulation=
  llm_mistral.reformuler_question`.
- 20 tests dans `tests/test_reformulateur.py`, 3 dans `tests/test_llm_mistral.py`, 3
  dans `tests/test_poser_question.py` (dont un qui prouve que la fonction de
  reformulation n'est jamais appelee sur une question deja autonome, coeur de
  l'Option C). Suite complete : 200/200.

## 23 aout 2026 (suite 3) — abandon de l'heuristique de mots-cles pour la reformulation

- Teste en reel : "population actuelle" confirme le fix du 2050 (donne desormais 38050
  pour 2026, l'annee en cours -- voir suite 1). Mais le follow-up "du derniere annee ?"
  n'a matche AUCUN mot-cle de `ressemble_a_un_followup` (Option C, ajoutee en suite 2) :
  la question a ete envoyee telle quelle au Routeur, qui est parti chercher un texte
  incomprehensible dans les documents et a renvoye un resultat hors-sujet (rapport de
  2011 sur la politique de population).
- Objection d'Ayman, fondee : une liste de mots-cles ne peut structurellement pas
  couvrir toutes les formulations possibles d'une question de suivi en francais -- le
  meme bug reapparaitrait sous une autre formulation a chaque fois, un jeu du chat et
  de la souris sans fin plutot qu'une vraie solution.
- Decision : abandonner toute tentative de deviner si UNE question a besoin de
  reformulation a partir de son seul texte. `ressemble_a_un_followup` et
  `MOTS_FOLLOWUP` supprimes de `src/reformulateur.py`. Nouvelle regle, purement
  structurelle et fiable a 100% : des qu'un historique existe pour la session (ce
  n'est pas la premiere question), la reformulation est SYSTEMATIQUE, quelle que soit
  la question. Compromis assume : une question deja autonome au 2e tour ou plus paie
  quand meme un appel LLM (qui la renvoie quasiment inchangee) -- moins economique
  qu'un bon filtre, mais ne rate plus jamais un vrai suivi. Cout reel juge negligeable
  vu le tier gratuit Mistral (~1 milliard de tokens/mois).
- Tests mis a jour en consequence (suppression des tests d'heuristique, ajout d'un
  test qui prouve que meme une question deja autonome declenche l'appel des qu'un
  historique existe, et d'un test qui prouve qu'aucun appel n'est fait sur la toute
  premiere question d'une session). Suite complete : 187/187.
