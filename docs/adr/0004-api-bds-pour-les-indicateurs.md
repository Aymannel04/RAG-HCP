# ADR 0004 — Utiliser l'API de la BDS comme source primaire des indicateurs chiffrés

**Statut :** accepté — 15 juillet 2026

## Contexte

En cherchant s'il existait un moyen plus direct d'obtenir les données chiffrées du HCP
qu'en les extrayant de PDF/XLSX (ADR 0003), deux pistes ont été explorées le même jour :

1. `data.gov.ma` (portail national Open Data, plateforme CKAN) republie 79 jeux de
   données du HCP, mais uniquement en téléchargement XLSX, sans couverture de la
   catégorie Population & démographie (0 jeu de données), et sans API de requête
   structurée (`datastore_active: false` sur toutes les ressources inspectées).
2. `bds.hcp.ma` (Base de Données Statistiques du HCP) possède sa **propre API**, non
   documentée publiquement mais librement accessible (aucune authentification requise),
   découverte en inspectant le trafic réseau du site :
   - `GET https://bds.hcp.ma/api/v1/subject-groups` — l'arborescence complète du
     catalogue (thèmes → sujets → sous-sujets → indicateurs), **832 indicateurs** au
     total, répartis sur 7 thèmes dont les 3 ciblés par le projet : Population &
     démographie (49), Marché du travail (32), Économie (216).
   - `GET https://bds.hcp.ma/api/v1/indicators/{code}` — la série complète d'un
     indicateur donné (toutes périodes, toutes dimensions de ventilation — région,
     sexe, branche d'activité, etc.), en JSON structuré. Vérifié manuellement sur
     `I3181` (Valeurs ajoutées par branche d'activité) et `I2818` (Population âgée de
     15 ans et plus selon l'état matrimonial) : les deux répondent correctement.

## Décision

Pour les indicateurs chiffrés couverts par la BDS, interroger directement l'API de
`bds.hcp.ma` plutôt que d'extraire ces mêmes chiffres depuis des PDF/XLSX. Le module
`src/bds_client.py` encapsule cet accès (`recuperer_catalogue`, `aplatir_catalogue`,
`recuperer_indicateur`).

Le pipeline PDF/XLSX (ADR 0003) reste nécessaire pour :
- le texte narratif et le contexte méthodologique (jamais présent dans la BDS, qui ne
  contient que des séries chiffrées) ;
- les publications ponctuelles non couvertes par le catalogue des 832 indicateurs.

## Justification

L'API de la BDS élimine le problème le plus fragile du pipeline actuel : la détection
heuristique de liens PDF/XLSX sur les pages HTML (sur-détection observée le 15 juillet,
voir `docs/rapport_sprint1.pdf`). À la place, on dispose d'un catalogue propre, complet
et directement interrogeable, avec des codes d'indicateurs stables. C'est aussi une
donnée plus fraîche et plus fiable qu'un PDF à re-parser : la série est déjà structurée
par l'institution elle-même.

## Conséquences

- `ConstructeurIndicateurs` (Sprint 2) doit être repensé : au lieu d'extraire des
  tableaux depuis des documents collectés, il doit d'abord consulter
  `data/bds_catalogue.json` (généré par `scripts/telecharger_catalogue_bds.py`) pour
  choisir les indicateurs pertinents, puis appeler `recuperer_indicateur(code)` pour
  chacun.
- Cette API n'étant pas documentée officiellement, elle peut changer sans préavis —
  contrairement à `data.gov.ma` qui est un portail officiel avec engagement de
  stabilité. Prévoir une gestion d'erreur robuste et ne pas en faire une dépendance
  bloquante non testée.
- Le module `src/bds_client.py` est écrit mais n'a pas encore été exécuté en conditions
  réelles depuis ce projet (le sandbox de développement n'a pas d'accès réseau vers
  bds.hcp.ma) — première tâche de validation du Sprint 2.
- Ne couvre toujours pas tout : les publications narratives (notes de conjoncture,
  rapports d'enquête) restent hors de la BDS et continuent de dépendre du pipeline
  PDF/XLSX de l'ADR 0003.
