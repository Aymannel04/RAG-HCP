# ADR 0003 — Les pages HTML sont des vitrines, l'ingestion doit cibler les PDF/XLSX lies

**Statut :** accepté — 15 juillet 2026

## Contexte

Le test réel du Scraper sur 27 pages (Sprint 1) a montré deux choses :
1. Les pages HTML d'articles hcp.ma ne portent qu'un résumé court (quelques phrases),
   pas les données détaillées.
2. Les vraies données — tableaux complets, séries chiffrées, rapports intégraux — sont
   dans des fichiers PDF et XLSX téléchargeables, référencés par des liens sur ces mêmes
   pages (ex. « Note Conj_Fr.pdf », observé sur les pages de note de conjoncture).

Confirmé par Ayman le 15 juillet 2026 : dans la section Publications du site, les
données sont systématiquement fournies en PDF ou en XLSX, jamais en HTML pur.

Un pipeline qui se contente d'extraire le texte des pages HTML (comme la première
version du Scraper/Extracteur) passe donc à côté de l'essentiel du contenu utile.

## Décision

Revoir le rôle du Scraper : pour chaque page HTML collectée, détecter les liens de
téléchargement PDF/XLSX qu'elle contient et les télécharger comme documents à part
entière (`Document.type = "pdf"` ou `"xlsx"`), en plus du résumé HTML.

Le contenu binaire téléchargé est sauvegardé sur disque (`data/raw/`, hors dépôt git)
plutôt que stocké en mémoire/base — seul le chemin local est gardé dans
`Document.texte_brut` pour ce cas.

L'Extracteur gagne deux nouvelles branches :
- PDF via `pdfplumber` (texte page par page + tableaux détectés).
- XLSX via `openpyxl` (chaque feuille devient un tableau ; pas de texte narratif,
  tout part vers `ConstructeurIndicateurs`).

## Justification

Aligné avec ADR 0001 (séparation texte / indicateurs) : les PDF/XLSX sont justement la
source primaire des indicateurs chiffrés qu'on veut extraire avec exactitude. Le résumé
HTML reste utile comme texte narratif léger pour la recherche sémantique générale, mais
ne doit plus être considéré comme la source de données principale.

## Conséquences

- Le Scraper devient plus lourd (une requête HTTP de plus par pièce jointe détectée).
- La détection des liens de téléchargement est une heuristique (le HTML de hcp.ma ne
  met pas toujours l'extension dans l'URL, ex. `/attachment/2866603/`) — à valider et
  affiner sur un vrai échantillon, pas encore fait au moment de cet ADR.
- L'extraction HTML actuelle (`_extraire_html`, tout `<p>`/tout `<table>`) s'est révélée
  insuffisante sur un vrai gabarit de page (menus rendus en `<table>`, corps d'article
  pas toujours dans des `<p>`) — nécessite un extrait de HTML réel pour être corrigée
  proprement ; reste ouvert.
