"""
Orchestrateur du rafraichissement nocturne (voir ADR 0004, "un script planifie, ex.
une fois par jour", et JOURNAL.md 27-30/08) : enchaine indexation des publications,
pre-remplissage des indicateurs BDS, puis vide le cache NOTION -- SEULEMENT si de
vraies nouveautes ont ete indexees cette nuit-la.

Pourquoi conditionner le flush (discussion avec Ayman, 30/08) : le cache NOTION reste
volontairement GLOBAL entre sessions/utilisateurs (le but assume est qu'une reponse
deja calculee beneficie a quiconque repose la meme question). Le vider systematiquement
chaque nuit, meme quand rien n'a change dans le corpus, jetterait ce benefice pour
rien. Le vider seulement quand `scripts.indexer_documents.main()` a reellement trouve
au moins un nouveau document garantit qu'aucune reponse ne reste en cache plus
longtemps que necessaire, sans perdre le partage inter-sessions les nuits ou rien de
neuf n'est paru.

Limite assumee (voir aussi discussion avec Ayman) : hcp.ma ne semble jamais reviser
un document existant sous la meme URL, seulement publier de nouveaux documents avec
des chiffres a jour -- ce script ne detecte donc que des ARRIVEES de documents, pas
des modifications. Un nouveau document peut rendre une reponse en cache obsolete sur
un sujet qu'il ne partage avec AUCUN document deja cite dans le cache (donc un suivi
"quel document a servi a quelle reponse" ne suffirait pas a cibler precisement quoi
invalider) -- vider tout le cache NOTION des qu'il y a au moins une nouveaute reste
la seule garantie fiable sans construire une comparaison semantique bien plus lourde.

Usage : python -m scripts.rafraichir_corpus
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def executer(chemin_db: Optional[Path] = None) -> None:
    """Chaque etape est protegee individuellement : un echec sur l'une (ex. hcp.ma
    ou l'API BDS indisponible cette nuit-la) ne doit jamais empecher les suivantes
    de s'executer -- meme principe de degradation propre qu'ailleurs dans le projet
    (voir src/generateur.py, src/reformulateur.py). Avant ce module, cette garantie
    vivait dans scripts/rafraichir_corpus.ps1 (trois blocs try/except PowerShell) ;
    deplacee ici pour rester testable et coherente avec le reste du code Python."""
    from scripts import indexer_documents, preremplir_indicateurs_bds
    from scripts.poser_question import _connecter_redis
    from scripts.vider_cache_notion import vider

    print("=== Indexation des publications ===")
    nouveaux_documents = 0
    try:
        nouveaux_documents = indexer_documents.main(chemin_db=chemin_db) or 0
    except Exception as e:  # noqa: BLE001 - un echec ici ne doit pas bloquer la suite
        print(f"[!] indexer_documents a echoue : {e}")

    print()
    print("=== Pre-remplissage des indicateurs BDS ===")
    try:
        preremplir_indicateurs_bds.main(chemin_db)
    except Exception as e:  # noqa: BLE001 - idem, independant de l'etape precedente
        print(f"[!] preremplir_indicateurs_bds a echoue : {e}")

    print()
    try:
        if nouveaux_documents > 0:
            client = _connecter_redis()
            nombre_vide = vider(client)
            print(f"=== {nouveaux_documents} nouveau(x) document(s) -> cache NOTION vide "
                  f"({nombre_vide} entree(s)) ===")
        else:
            print("=== Aucune nouveaute -> cache NOTION conserve ===")
    except Exception as e:  # noqa: BLE001 - un Redis indisponible ne doit pas faire echouer le run
        print(f"[!] vidage du cache NOTION echoue : {e}")


def main() -> None:
    executer()


if __name__ == "__main__":
    main()
