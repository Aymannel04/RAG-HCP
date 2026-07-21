# RAG HCP — Système de questions-réponses pour hcp.ma

Stage réalisé au **Haut-Commissariat au Plan (HCP)**, Direction des Systèmes d'Information Statistiques.
Binôme : **Ayman El Baida** et **Saad Mesbah**. Période : 1er juillet – fin août 2026.

## Idée du projet

Un système RAG (Retrieval-Augmented Generation) qui répond en langage naturel aux questions sur les
statistiques et publications du HCP, avec deux garanties : **citation systématique des sources** et
**zéro hallucination sur les chiffres officiels**.

Le principe central : le site hcp.ma mélange du texte narratif (articles, PDF, glossaire, FAQ) et des
données chiffrées précises (indicateurs, séries). On ne traite pas les deux pareil — les indicateurs
sont extraits une fois pour toutes dans une table structurée et récupérés par requête exacte, tandis
que le texte passe par un pipeline RAG classique (recherche hybride + reranking). Un routeur aiguille
chaque question vers le bon chemin.

Le détail complet (problématique, objectifs, architecture, risques, planning) est dans `docs/`.

## Documentation

- [`docs/fiche_cadrage_v4.pdf`](docs/fiche_cadrage_v4.pdf) — note de cadrage complète (périmètre, besoins, architecture, risques, planning, glossaire). Source LaTeX : `docs/fiche_cadrage_v4.tex`.
- [`docs/conception_uml_v3.pdf`](docs/conception_uml_v3.pdf) — dossier de conception UML/Merise (cas d'utilisation, MCD, MLD, classes, séquences, activité). Source LaTeX : `docs/conception_uml_v3.tex`.
- `docs/adr/` — Architecture Decision Records : une note courte à chaque décision technique structurante.
- `TODO.md` — planning découpé en tâches, semaine par semaine.
- `JOURNAL.md` — journal de bord (une entrée par jour de travail), utile pour rédiger le rapport de stage a posteriori.

## Structure du dépôt

```
src/                    code source, un module par classe du diagramme de classes
  models.py              structures de données partagées (Document, Chunk, Indicateur)
  scraper.py              module 1 — collecte des pages/PDF ciblés
  extracteur.py            module 2 — nettoyage + séparation texte/tableaux
  indexeur_texte.py         module 3 — chunking, embeddings, index vectoriel + BM25
  constructeur_indicateurs.py  module 4 — structuration des indicateurs chiffrés
  routeur.py                 module 5 — classification de la question
  retrieval_reranker.py       module 6 — recherche hybride + reranking
  lookup_structure.py          module 7 — requête exacte sur les indicateurs
  generateur.py                  module 8 — génération de la réponse sourcée
  interface.py                    module 9 — interface de démonstration
db/
  schema.sql              traduction SQL du MLD (documents, chunks, indicateurs)
tests/                   tests unitaires (pytest)
docs/                    livrables et documentation du projet
```

Chaque module correspond exactement à une classe du diagramme de classes (`docs/conception_uml_v3.pdf`,
figure 4) — le tableau de correspondance module/rôle/flux est dans la fiche de cadrage, section 8.1.

## Installation

```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sous Windows
pip install -r requirements.txt
```

Pour la génération de réponse (chemin "notion", voir `src/generateur.py` et ADR 0002) :
créer un compte gratuit sur [console.mistral.ai](https://console.mistral.ai/), générer
une clé API, puis créer un fichier `.env` à la racine du projet (jamais commité) :

```
MISTRAL_API_KEY=ta_cle_ici
```

Le chemin "chiffre" (questions sur un indicateur précis) fonctionne sans cette clé.

## Lancer les tests

```bash
pytest tests/ -v
```

## Statut d'avancement

Voir `TODO.md`. En résumé : cadrage et conception terminés, Sprints 1 et 2 (collecte, extraction,
indexation) validés en conditions réelles, Sprint 3 (retrieval + génération) fonctionnellement
complet côté code — reste la validation en conditions réelles du reranker et du LLM Mistral.
