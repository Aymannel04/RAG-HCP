"""
Liste curée des indicateurs BDS pré-remplis chaque nuit (voir ADR 0004, section
"Précisions du 15 juillet" — étape 1 de la stratégie cache-aside, figure B du
complément de conception).

Chaque code a été vérifié réel : soit par appel direct à
`GET https://bds.hcp.ma/api/v1/indicators/{code}` (I3181), soit trouvé dans le
catalogue réel via `GET https://bds.hcp.ma/api/v1/subject-groups` le 17 juillet 2026
(voir data/bds_catalogue.json, généré par scripts/telecharger_catalogue_bds.py).

Marché du travail : thème pas encore couvert ici (32 indicateurs au catalogue, non
récupérés lors de l'inspection réseau — réponse trop volumineuse, coupée avant ce
thème). À compléter : chercher dans data/bds_catalogue.json (généré en local) les
entrées avec theme_label == "Marché du travail" et ajouter 5-6 codes pertinents
(taux de chômage, taux d'activité, population active occupée...).
"""
from __future__ import annotations

# (code, catégorie du projet) — catégorie utilisée pour remplir Document.categorie
# du document synthétique associé (voir ConstructeurIndicateurs.construire_document_synthetique).
INDICATEURS_CURES: list[tuple[str, str]] = [
    # --- Population & démographie ---
    ("I1588", "Population & démographie"),  # Population du Maroc par année civile (1960-2050)
    ("I1590", "Population & démographie"),  # Population par groupe d'âge, sexe et milieu
    ("I2790", "Population & démographie"),  # Taux d'urbanisation
    ("I2781", "Population & démographie"),  # Espérance de vie à la naissance
    ("I2786", "Population & démographie"),  # Indice synthétique de fécondité
    ("I2784", "Population & démographie"),  # Nombre de ménages

    # --- Économie ---
    ("I1428", "Economie"),  # PIB aux prix courants (Annuelle Base 2007)
    ("I3161", "Economie"),  # PIB aux prix constants (Annuelle Base 2007) -> croissance
    ("I3981", "Economie"),  # Indice des prix à la consommation, IPC (Base 100 2017)
    ("I1437", "Economie"),  # Exportations de biens et services aux prix courants
    ("I1434", "Economie"),  # Importations aux prix courants
    ("I3181", "Economie"),  # Valeurs ajoutées par branche d'activité (Trimestrielle) -- testé en réel le 16/07

    # --- Marché du travail --- (à compléter, voir docstring ci-dessus)
]
