# ADR 0003 — Le RAG s'indexe uniquement sur les PDF/XLSX, le HTML sert à les découvrir

**Statut :** accepté — 15 juillet 2026 (précisé le 15 juillet 2026, suite à la
clarification du périmètre par Ayman)

## Contexte

Le test réel du Scraper sur 27 pages (Sprint 1) a montré deux choses :
1. Les pages HTML d'articles hcp.ma ne portent qu'un résumé court (quelques phrases),
   pas les données détaillées, et cette extraction HTML est de toute façon peu fiable
   (0 caractère de texte propre trouvé sur plusieurs pages, gabarits inconsistants).
2. Les vraies données — tableaux complets, séries chiffrées, rapports intégraux — sont
   dans des fichiers PDF et XLSX téléchargeables, référencés par des liens sur ces mêmes
   pages (ex. « Note Conj_Fr.pdf »).

Confirmé par Ayman : le périmètre du projet est explicitement « un chatbot RAG basé sur
les publications du site hcp.ma, et seulement les publications en PDF ou Excel ». Le
texte des pages HTML n'est **pas** une donnée du projet, même en complément.

## Décision

Le HTML n'est jamais indexé pour le RAG. Son seul rôle est instrumental :
1. Servir de point d'entrée de collecte (pages de catégories/publications) pour repérer
   les liens de téléchargement PDF/XLSX.
2. Fournir des métadonnées légères (titre, date de publication) rattachées aux documents
   PDF/XLSX téléchargés depuis cette page.

Le Scraper télécharge chaque PDF/XLSX détecté comme document à part entière
(`Document.type = "pdf"` ou `"xlsx"`), stocké sur disque (`data/raw/`, hors dépôt git) ;
seul le chemin local est gardé dans `Document.texte_brut` pour ce cas.

L'Extracteur ne fait donc réellement travailler que deux branches pour le contenu RAG :
- PDF via `pdfplumber` (texte page par page + tableaux détectés).
- XLSX via `openpyxl` (chaque feuille devient un tableau ; pas de texte narratif,
  tout part vers `ConstructeurIndicateurs`).
La branche HTML (`_extraire_html`) reste dans le code par simplicité d'implémentation
mais **son résultat n'est plus consommé par `IndexeurTexte`** (voir Conséquences) — pas
la peine de la perfectionner davantage.

## Justification

Aligné avec ADR 0001 (séparation texte / indicateurs) et avec le périmètre confirmé du
projet : les PDF/XLSX sont la source de vérité unique, à la fois pour le texte narratif
(chunking/embeddings) et pour les indicateurs chiffrés (lookup exact).

## Conséquences

- `IndexeurTexte.indexer` (Sprint 2) doit filtrer sur `document.type in ("pdf", "xlsx")`
  et ignorer les `Document` de type `"html"` — à faire explicitement dans le SQL/logique
  d'insertion, pas seulement une intention.
- La tâche « corriger `Extracteur._extraire_html` » sort du backlog Sprint 2 (voir
  TODO.md) : ce n'est plus un blocage, juste une branche de code non prioritaire.
- Le Scraper devient plus lourd (une requête HTTP de plus par pièce jointe détectée).
- La détection des liens de téléchargement (type ET langue) est une heuristique validée
  une première fois en réel le 15 juillet (voir `src/scraper.py`,
  `_detecter_pieces_jointes`) — un PDF arabe non filtré a été corrigé le même jour, mais
  l'heuristique reste à re-valider sur un échantillon plus large.
