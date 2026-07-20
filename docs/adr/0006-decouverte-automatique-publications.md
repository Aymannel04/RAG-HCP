# ADR 0006 — Découverte automatique des publications (remplacement des URLs fixes)

**Statut :** accepté — 20 juillet 2026

## Contexte

Le Scraper (module 1) fonctionne aujourd'hui à partir d'une liste figée de 27 URLs
(`data/seed_urls.py`), compilée manuellement le 15 juillet 2026 pour le premier test
réel. Cette liste avait un objectif clair et assumé : valider que `Scraper`/`Extracteur`
tiennent sur des gabarits de page réels et variés. Elle n'a jamais été pensée comme la
source de vérité définitive du système.

Deux limites de cette approche ont été soulevées lors de la réunion du 20 juillet 2026
avec l'encadrante, puis creusées avec Ayman :

1. **Couverture historique.** hcp.ma publie des centaines de notes, rapports et études
   depuis plus d'une dizaine d'années. 27 URLs ne couvrent qu'une fraction infime de ce
   corpus ; le RAG doit pouvoir répondre sur l'historique, pas seulement sur les
   publications choisies à la main en juillet 2026.
2. **Fraîcheur continue.** hcp.ma publie de nouveaux documents en continu (mensuel,
   trimestriel, annuel selon les séries). Une liste figée ne peut jamais refléter les
   publications à venir : sans mécanisme de détection automatique, chaque nouvelle
   publication resterait invisible du RAG tant que quelqu'un ne rajoute pas son URL à la
   main dans `seed_urls.py`.

Vérification effectuée directement sur hcp.ma (20 juillet 2026) pour évaluer la
faisabilité d'une solution : les 3 catégories ciblées disposent, en plus de leur page
« vitrine » (qui n'affiche qu'une dizaine d'actualités/publications récentes), de pages
dédiées de type liste, paginées de façon classique. Exemple vérifié en réel :

- `https://www.hcp.ma/Publications-Marche-du-travail_r425.html` : 50 publications au
  total, réparties sur 10 pages de 5, accessibles via un paramètre d'URL
  `?start=0`, `?start=5`, ... `?start=45`.
- `https://www.hcp.ma/Etudes-economiques_r650.html` : 25 publications sur 5 pages, même
  logique de pagination.

Le volume par page listing est donc modeste (quelques dizaines à centaines de documents),
et le mécanisme de pagination est simple et prévisible (incrément constant du paramètre
`start`, déductible directement des liens de pagination présents sur la première page).

## Décision

Remplacer la liste fixe d'URLs d'articles par un mécanisme de **découverte automatique**
qui parcourt les pages listing paginées de hcp.ma et en extrait les URLs d'articles, à
donner ensuite en entrée du `Scraper.collecter()` existant (aucun changement de ce côté).

Ce mécanisme est unique mais s'utilise à deux portées différentes, qui répondent chacune
à une des deux limites identifiées :

| | Collecte historique | Collecte de fraîcheur |
|---|---|---|
| **Objectif** | Couvrir le corpus existant | Détecter les nouvelles publications |
| **Portée** | Toutes les pages de chaque listing (pagination suivie jusqu'au bout) | Seulement la 1ère page de chaque listing |
| **Fréquence** | Ponctuelle (à relancer occasionnellement pour élargir le corpus) | Récurrente (idéalement quotidienne, même logique que le pré-remplissage BDS nocturne de l'ADR 0004) |
| **Pourquoi ça marche** | Les listings remontent (au moins en partie) jusqu'aux publications anciennes | hcp.ma trie ses listings du plus récent au plus ancien : toute nouveauté apparaît forcément en page 1 |

Dans les deux cas, la déduplication ne nécessite aucun code supplémentaire : la
contrainte `document.url UNIQUE` déjà présente dans `db/schema.sql` (voir ADR 0001)
rejette silencieusement toute URL déjà connue au moment de l'insertion.

## Justification

- **Un seul mécanisme, pas deux.** Historique et fraîcheur sont le même problème
  (« lire une page listing, en extraire les liens d'articles ») à deux échelles
  différentes. Dupliquer la logique en deux modules distincts aurait été une
  complexité inutile ; faire varier uniquement `max_pages` suffit.
- **Pas de dépendance à un flux RSS ou une API de publication.** hcp.ma n'expose ni
  flux RSS ni API de liste de publications (vérifié — seule `bds.hcp.ma` a une API,
  déjà exploitée par l'ADR 0004, mais elle couvre les indicateurs chiffrés, pas les
  documents/rapports). Le HTML paginé est la seule source disponible.
- **Robustesse du parsing.** Plutôt que de dépendre de classes CSS (fragiles, peuvent
  changer sans préavis), la détection des liens d'articles s'appuie sur le motif d'URL
  stable observé sur l'ensemble du site (`..._a<chiffres>.html`, vérifié sur des dizaines
  de pages depuis le 15 juillet). Le nombre de pages à parcourir n'est pas non plus codé
  en dur (« 5 par page ») : il est déduit dynamiquement des liens de pagination présents
  sur la première page, donc robuste si hcp.ma change ce nombre.
- **Cohérence avec l'existant.** Le pré-remplissage nocturne des indicateurs BDS
  (ADR 0004) établit déjà le patron « tâche planifiée, réexécutée régulièrement,
  s'appuyant sur la base pour ne pas dupliquer le travail ». La collecte de fraîcheur
  suit exactement le même patron, appliqué cette fois aux documents plutôt qu'aux
  indicateurs.

## Conséquences

- `src/scraper.py` : nouvelles méthodes sur `Scraper` —
  `_extraire_urls_articles(soup)` (extraction par motif d'URL),
  `_increments_pagination(soup)` (détection dynamique des paliers `start=`),
  `decouvrir_urls_liste(url_listing, max_pages=None)` (parcourt 1 à N pages d'un
  listing et retourne les URLs d'articles trouvées), et
  `collecter_depuis_listing(url_listing, categorie, max_pages=None)` qui enchaîne
  découverte + `collecter()` existant. Aucune méthode existante n'est modifiée.
- `data/listing_urls.py` (nouveau) : remplace la logique de `data/seed_urls.py`
  (conservé tel quel, toujours utile pour un test rapide et ciblé) — associe à chaque
  catégorie la ou les URLs de listing à parcourir. **Point ouvert** : seule la page
  listing de Marché du travail a été confirmée comme couvrant toute la catégorie en une
  seule page. Économie et Population & démographie sont découpées en sous-thèmes
  (ex. Population : Recensement, Fécondité, Mortalité...) dont il reste à vérifier,
  pour chacun, s'il existe une page listing dédiée ou s'il faut en parcourir plusieurs
  par catégorie. Documenté comme tâche de suivi plutôt que bloquant pour cette décision,
  le mécanisme de découverte étant lui-même indépendant du nombre de listings à lui
  donner en entrée.
- `scripts/decouverte_publications.py` (nouveau) : deux points d'entrée,
  `collecte_historique()` (`max_pages=None`, parcourt tout) et
  `collecte_quotidienne()` (`max_pages=1`, ne regarde que la 1ère page), suivant le
  même style que `scripts/preremplir_indicateurs_bds.py`.
- `db/schema.sql` : aucun changement (la contrainte `UNIQUE` sur `document.url`
  couvrait déjà ce besoin).
- **Limite explicitement non traitée par cet ADR** : un document déjà connu peut être
  révisé *à la même URL* (contenu mis à jour sans changement d'adresse). La
  déduplication par URL ne détecte pas ce cas. Une solution (comparaison d'empreinte/
  hash du contenu téléchargé, avec ré-extraction si le hash a changé) est identifiée
  mais volontairement hors périmètre de cette décision — à traiter dans un ADR
  ultérieur une fois le mécanisme de découverte de base validé en conditions réelles.
- Comme pour l'ADR 0005 (DOCX), la validation en conditions réelles ne peut pas se
  faire dans le bac à sable de développement (pas d'accès réseau vers hcp.ma) — à
  exécuter par Ayman sur sa machine, même patron que
  `scripts/valider_docx_reel.py`.
