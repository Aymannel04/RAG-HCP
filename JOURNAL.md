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
