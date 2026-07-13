# ADR 0001 — Séparation stricte texte narratif / indicateurs chiffrés

**Statut :** accepté — 7 juillet 2026

## Contexte

Le site hcp.ma mélange du contenu textuel (articles, PDF, glossaire, FAQ) et des données
chiffrées officielles (indicateurs, séries temporelles). Un RAG classique qui traite tout
comme du texte risque l'hallucination : un chiffre plausible mais faux, non vérifié.
Inacceptable pour un institut statistique officiel.

## Décision

Séparer dès le pipeline d'ingestion les deux natures de contenu :

- le texte narratif passe par un pipeline RAG classique (chunking, embeddings, recherche
  hybride vectorielle + BM25, reranking) ;
- les indicateurs chiffrés sont extraits une fois pour toutes dans une table structurée
  (`indicateur`, voir `db/schema.sql`) et récupérés par requête exacte, jamais par recherche
  approximative.

Un routeur (`src/routeur.py`) classe chaque question et aiguille vers le bon chemin.

## Justification

Élimine le risque de restituer un chiffre approximatif issu d'une recherche par similarité
plutôt que la vraie valeur officielle. Voir `docs/fiche_cadrage_v4.pdf`, section 3
(problématique) et section 9 (analyse des risques).

## Conséquences

- Deux pipelines de traitement à maintenir plutôt qu'un seul.
- Nécessite une étape de curation (au moins semi-manuelle en V1) des indicateurs clés.
- En contrepartie, garantit l'exactitude factuelle sur les questions chiffrées (exigence
  NF2 de la fiche de cadrage).
