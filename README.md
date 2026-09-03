# RAG HCP — Système de questions-réponses pour hcp.ma

Stage réalisé au **Haut-Commissariat au Plan (HCP)**, Direction des Systèmes d'Information Statistiques,
par **Ayman El Baida**. Période : 1er juillet – 3 septembre 2026.

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

- [`docs/fiche_cadrage_v4.pdf`](docs/fiche_cadrage_v4.pdf) — note de cadrage d'origine (périmètre, besoins, architecture, risques, planning, glossaire), complétée d'encadrés « Mise à jour (03/09/2026) » qui signalent, section par section, ce qui a réellement changé depuis la rédaction initiale (7 juillet) et pourquoi. Source LaTeX : `docs/fiche_cadrage_v4.tex`.
- [`docs/conception_uml_v4.pdf`](docs/conception_uml_v4.pdf) — dossier de conception UML/Merise (cas d'utilisation, MCD, MLD, classes, séquences, activité), version à jour incluant le scénario de question mixte et les modules ajoutés en cours de route (reformulation, cache). Source LaTeX : `docs/conception_uml_v4.tex`. `docs/conception_uml_v3.pdf` reste dans le dépôt à titre de version historique (Sprint 2).
- [`docs/rapport_stage.pdf`](docs/rapport_stage.pdf) — rapport de stage complet (non versionné, voir `.gitignore` — document personnel).
- `docs/adr/` — Architecture Decision Records : une note courte à chaque décision technique structurante.
- `TODO.md` — planning découpé en tâches, semaine par semaine.
- `JOURNAL.md` — journal de bord (une entrée par jour de travail), utile pour rédiger le rapport de stage a posteriori.

## Structure du dépôt

```
src/                    code source, un module par classe du diagramme de classes
  models.py              structures de données partagées (Document, Chunk, Indicateur)
  scraper.py              module 1 — collecte des pages/PDF ciblés
  extracteur.py            module 2 — nettoyage + séparation texte/tableaux (+ garde-fou
                             anti-texte-illisible, voir JOURNAL.md 03/09)
  indexeur_texte.py         module 3 — chunking, embeddings, index vectoriel + BM25
  constructeur_indicateurs.py  module 4 — structuration des indicateurs chiffrés
  routeur.py                 module 5 — classification de la question
  retrieval_reranker.py       module 6 — recherche hybride + reranking
  lookup_structure.py          module 7 — requête exacte sur les indicateurs
  generateur.py                  module 8 — génération de la réponse sourcée
  interface.py                    module 9 — interface de démonstration
  base_donnees.py         utilitaire — connexion/insertion SQLite, hors numérotation
  bds_client.py            utilitaire — client de l'API BDS (bds.hcp.ma, ADR 0004),
                             source primaire des indicateurs chiffrés
  llm_mistral.py            utilitaire — client Mistral pour le chemin "notion" (ADR 0002)
  cache_redis.py             module ajouté le 28/07 — cache de réponses + historique
                              de conversation, non prévu dans la conception d'origine
  reformulateur.py            module ajouté le 23/08 — reformulation des questions de
                                suivi à partir de l'historique, non prévu non plus
db/
  schema.sql              traduction SQL du MLD (documents, chunks, indicateurs)
data/                    listes de seed (URLs, indicateurs curés) et cache de scraping
scripts/                 points d'entrée exécutables (indexation, question en CLI,
                          mesure de fiabilité NF2, rafraîchissement du corpus...)
tests/                   tests unitaires (pytest) — 224/224 au 03/09/2026
docs/                    livrables et documentation du projet
```

Chaque module numéroté (1 à 9) correspond exactement à une classe du diagramme de classes
(`docs/conception_uml_v4.pdf`, figure 4) — le tableau de correspondance module/rôle/flux
est dans la fiche de cadrage, section 8.1. Les modules non numérotés (`base_donnees.py`,
`bds_client.py`, `llm_mistral.py`, `cache_redis.py`, `reformulateur.py`) ont été ajoutés
en cours de route, pour des besoins découverts en testant le système en conditions
réelles plutôt qu'anticipés dans la conception initiale — voir leurs docstrings et
`JOURNAL.md` pour le contexte de chaque ajout.

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

Pour le cache de réponses et l'historique de conversation (ajoutés le 28/07, voir
`src/cache_redis.py`) : un serveur Redis local, facultatif. `scripts/poser_question.py`
tente une connexion à `localhost:6379` et se dégrade silencieusement si aucun serveur
n'est disponible (aucune erreur, juste pas de cache/historique). Sous Windows, deux
options simples : Redis via **WSL** (`sudo apt install redis-server`, puis
`redis-server` dans le terminal WSL) ou via **Docker** (`docker run -p 6379:6379
redis`). Rien à configurer côté projet au-delà de `pip install -r requirements.txt`
(qui installe déjà `redis`) — les tests, eux, utilisent `fakeredis` (faux serveur en
mémoire) et n'ont besoin d'aucun serveur réel.

## Lancer les tests

```bash
pytest tests/ -v
```

## Statut d'avancement

Voir `TODO.md` et `JOURNAL.md` pour le détail. En résumé, au 3 septembre 2026 (fin de stage) :
projet fonctionnellement complet et validé en conditions réelles de bout en bout (scraping,
extraction, indexation, routage, recherche hybride + reranking, lookup structuré, génération,
cache/historique, reformulation des questions de suivi, interface Streamlit). Jeu de test de
fiabilité (NF2) construit et exécuté : 93,3 % (28/30), objectif atteint — voir
`scripts/mesurer_fiabilite.py`. Suite de tests automatisés : 224/224. Seul point encore ouvert
à cette date : la préparation de la démonstration finale.
