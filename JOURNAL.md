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
