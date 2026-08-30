"""
Vide le cache NOTION (src/cache_redis.py::CacheReponses) -- appele a la fin du
rafraichissement nocturne (scripts/rafraichir_corpus.ps1), APRES l'indexation de
nouveaux documents et la mise a jour des indicateurs BDS.

Pourquoi (discussion avec Ayman, 30/08, voir JOURNAL.md) : le cache reste
volontairement GLOBAL entre sessions/utilisateurs, pas cloisonne par session -- une
reponse deja calculee doit pouvoir beneficier a quiconque repose la meme question,
meme dans une session differente (c'est le but assume du cache, pas un oubli). Mais
un TTL de 24h glissant depuis l'ECRITURE de l'entree n'est pas aligne sur le moment
REEL ou le corpus change : le rafraichissement nocturne tourne a heure fixe (3h),
alors qu'une entree mise en cache la veille a 14h reste valide jusqu'a 14h le
lendemain -- jusqu'a 11h de decalage possible ou le cache ressert une reponse plus
vieille que du contenu deja mis a jour. Vider le cache explicitement a chaque
rafraichissement garantit qu'aucune reponse en cache ne peut jamais etre plus
ancienne que le dernier passage d'indexation, sans perdre le benefice du partage
inter-sessions le reste du temps. Le TTL de 24h (src/cache_redis.py::TTL_CACHE_NOTION)
reste en place en complement, comme filet de securite si ce script n'est pas execute
un jour donne.

L'historique de conversation (HistoriqueConversation) n'est PAS concerne -- seul le
prefixe cache_notion est vise, jamais le prefixe historique (voir PREFIXE_CACHE vs
PREFIXE_HISTORIQUE dans src/cache_redis.py).

Usage : python -m scripts.vider_cache_notion
"""
from __future__ import annotations

from src.cache_redis import PREFIXE_CACHE


def vider(client_redis) -> int:
    """Supprime toutes les entrees du cache NOTION. Renvoie le nombre d'entrees
    supprimees (0 si `client_redis` est None -- comportement degrade silencieux,
    meme patron que CacheReponses/HistoriqueConversation)."""
    if client_redis is None:
        return 0
    cles = list(client_redis.scan_iter(PREFIXE_CACHE + "*"))
    if cles:
        client_redis.delete(*cles)
    return len(cles)


def main() -> None:
    # Import local (voir meme raisonnement que scripts/indexer_documents.py::main) :
    # evite de necessiter le paquet redis pour les tests qui n'utilisent que vider().
    from scripts.poser_question import _connecter_redis

    client = _connecter_redis()
    nombre = vider(client)
    if client is None:
        print("Redis indisponible -- rien a vider.")
    else:
        print(f"{nombre} entree(s) de cache NOTION videe(s).")


if __name__ == "__main__":
    main()
