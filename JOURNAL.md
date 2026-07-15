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
