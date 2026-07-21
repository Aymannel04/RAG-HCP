# ADR 0007 — Choix du reranker pour RetrievalReranker

**Statut :** accepté — 21 juillet 2026

## Contexte

Le Sprint 3 démarre l'implémentation de `RetrievalReranker` (module 6), dont le rôle
(voir docs/conception_uml_v3.pdf, figure 6) est d'affiner les résultats de la recherche
hybride d'`IndexeurTexte.rechercher` (déjà implémentée et validée en conditions réelles
en Sprint 2) en ne conservant que les passages réellement pertinents pour la question,
avant de les transmettre à `Generateur`. Aucun modèle de reranking n'est fixé dans les
documents de conception (`fiche_cadrage_v4.pdf` §8.1 et `conception_uml_v3.pdf` §8
mentionnent un reranking sans préciser d'implémentation).

## Décision

Utiliser **`BAAI/bge-reranker-v2-m3`** via `sentence_transformers.CrossEncoder`, avec
la fonction de reranking injectable au constructeur (même patron que
`IndexeurTexte._embarquer`), pour permettre les tests sans télécharger le modèle.

## Justification

- **Cohérence avec ADR 0002.** BGE-M3 (`BAAI/bge-m3`) a déjà été retenu pour les
  embeddings, avec la justification suivante (voir
  `docs/note_stockage_routage_benchmark.pdf`, benchmark embeddings) : multilingue
  (français couvert), open source (licence MIT, hébergeable localement, aucun coût par
  appel ni dépendance à une API externe). `bge-reranker-v2-m3` partage exactement ces
  mêmes propriétés (même famille BAAI, même politique de licence, même déploiement
  local via `sentence-transformers`) : c'est une extension cohérente du choix déjà
  acté, pas une nouvelle décision de nature différente.
- **Pas de dépendance au point encore ouvert de l'ADR 0002.** Le choix du LLM de
  génération reste à valider avec l'encadrante (question de politique de sécurité des
  données du HCP, budget d'API externe). Un reranker n'est pas un LLM génératif — c'est
  un classifieur de pertinence (score de similarité question/passage) — donc ce choix
  n'a pas besoin d'attendre cette validation pour permettre d'avancer le Sprint 3.
- **Cross-encoder plutôt que réutiliser les scores denses déjà calculés.** Un
  cross-encoder traite la paire (question, passage) conjointement plutôt que de
  comparer deux embeddings calculés séparément (bi-encoder, ce qu'est BGE-M3 dans
  `IndexeurTexte`) : plus lent (une passe modèle par paire candidate, d'où l'étape de
  recherche hybride en amont pour réduire l'ensemble de candidats avant reranking),
  mais plus précis sur le classement fin d'un petit nombre de passages déjà présélectionnés
  — exactement l'usage prévu ici (reranking de quelques dizaines de candidats, pas de
  recherche sur tout le corpus).

## Conséquences

- `src/retrieval_reranker.py` : `RetrievalReranker(indexeur, fonction_reranking=None)` —
  interroge `IndexeurTexte.rechercher` pour obtenir un ensemble élargi de candidats
  (`top_k * 4`, même marge que la fusion RRF de Sprint 2), les passe au cross-encoder,
  puis retourne les `top_k` mieux notés.
- `fonction_reranking` injectable : `Callable[[str, list[str]], list[float]]`
  (question, textes) -> scores, même esprit que `IndexeurTexte.fonction_embedding` — les
  tests utilisent une fonction factice (pas de téléchargement de `bge-reranker-v2-m3`,
  ~600 Mo, dans le bac à sable de développement sans accès réseau). **Pas encore validé
  avec le vrai modèle** : à faire sur la machine d'Ayman, même patron que BGE-M3 en
  Sprint 2 (voir `docs/rapport_sprint2.pdf`, section 8).
- `requirements.txt` : `sentence-transformers` déjà présent (utilisé pour BGE-M3) couvre
  aussi `CrossEncoder`, aucune nouvelle dépendance.
