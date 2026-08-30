"""
Module cache_redis — cache et historique de conversation, ajoutés le 28/07 (voir
JOURNAL.md et TODO.md).

Deux responsabilités distinctes, dans le même fichier parce qu'elles partagent le même
client Redis injectable :

- `CacheReponses` : cache question -> réponse, UNIQUEMENT pour le chemin NOTION (voir
  `scripts/poser_question.py`). Le chemin CHIFFRE est déjà une requête SQL directe
  quasi instantanée -- rien à gagner à le cacher. Le chemin MIXTE est délibérément
  exclu : sa partie chiffrée est recalculée à chaque appel pour rester à jour (voir
  ADR 0004, pré-remplissage nocturne), et mettre en cache une réponse mixte risquerait
  de resservir un chiffre périmé à côté d'une explication qui, elle, ne change pas --
  incohérent avec tout le travail fait le 28/07 pour garantir un chiffre toujours
  exact. Seul le NOTION pur n'a pas ce problème (rien de chiffré dedans).

  TTL de 24h, aligné sur `scripts/decouverte_publications.py --quotidien` : une
  réponse ne doit jamais survivre plus longtemps que le cycle de rafraîchissement du
  corpus, sinon elle pourrait ignorer une publication nouvellement indexée.

- `HistoriqueConversation` : historique par session. Clé = `id_session`, généré et
  retenu par l'INTERFACE (Streamlit aujourd'hui, autre chose peut-être demain) --
  jamais par ce module. Décision volontaire : si l'interface change un jour, seul le
  petit bout qui génère/retient l'id de session change, pas le stockage sous-jacent.
  Alternative envisagée et écartée : `st.session_state` de Streamlit directement --
  fonctionne, mais piège l'historique dans Streamlit, aucune portabilité si
  l'interface change (voir discussion du 28/07).

Correspondance question -> cache : EXACTE, sur la question normalisée (minuscules,
espaces réduits) -- voir `normaliser_question`. Choix délibéré pour cette V1 : une
correspondance sémantique (embeddings de la question + seuil de similarité)
reconnaîtrait plus de reformulations ("chômage actuel" ~ "chômage aujourd'hui") mais
avec un risque réel de faux positif -- retourner la réponse d'une question jugée
"assez proche" mais en réalité différente. Prévu comme extension V2, une fois la
version exacte validée en conditions réelles (voir TODO.md).

Redis choisi ici -- plutôt que SQLite, utilisé partout ailleurs dans le projet -- par
choix explicite d'Ayman, pour la pratique de l'outil : aucune nécessité de performance
démontrée au volume actuel du prototype (même mise en garde que pour toute autre
décision d'infrastructure de ce projet, voir TODO.md section Redis).

Client injectable au constructeur, même patron que `fonction_embedding`/
`fonction_generation` ailleurs dans le projet : `fakeredis.FakeRedis()` dans les tests
(aucun serveur Redis réel nécessaire, voir tests/test_cache_redis.py), un vrai
`redis.Redis(...)` en production (nécessite un serveur Redis lancé séparément sur la
machine -- voir README.md pour l'installation locale). Absence de client (`None`,
valeur par défaut) : comportement dégradé silencieux, jamais d'erreur -- un cache
absent doit se comporter comme un cache qui rate toujours, pas comme une panne.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Optional

from .generateur import Reponse

TTL_CACHE_NOTION = 24 * 60 * 60  # 24h, aligné sur decouverte_publications.py --quotidien
TTL_HISTORIQUE = 24 * 60 * 60  # 24h glissant -- voir docstring de HistoriqueConversation.ajouter
PREFIXE_CACHE = "rag_hcp:cache_notion:"
PREFIXE_HISTORIQUE = "rag_hcp:historique:"


def normaliser_question(question: str) -> str:
    """Minuscules + espaces superflus réduits -- suffisant pour reconnaître "Quel est
    le taux ?" et "quel   est le taux ?" comme la même question, pas plus (voir
    docstring de module : correspondance EXACTE choisie pour cette V1, pas
    sémantique)."""
    return " ".join(question.strip().lower().split())


class CacheReponses:
    """Cache question -> Reponse pour le chemin NOTION uniquement (voir docstring de
    module)."""

    def __init__(self, client_redis=None):
        self._client = client_redis

    def obtenir(self, question: str) -> Optional[Reponse]:
        """Renvoie la Reponse en cache, ou None si absente (client non configuré,
        question jamais posée, ou entrée expirée -- les trois cas sont indiscernables
        et c'est très bien ainsi : l'appelant retombe simplement sur un calcul frais)."""
        if self._client is None:
            return None
        brut = self._client.get(PREFIXE_CACHE + normaliser_question(question))
        if brut is None:
            return None
        return Reponse(**json.loads(brut))

    def enregistrer(self, question: str, reponse: Reponse) -> None:
        """No-op silencieux si aucun client -- un cache absent ne doit jamais faire
        échouer le calcul de la réponse elle-même."""
        if self._client is None:
            return
        self._client.set(
            PREFIXE_CACHE + normaliser_question(question),
            json.dumps(asdict(reponse)),
            ex=TTL_CACHE_NOTION,
        )


class HistoriqueConversation:
    """Historique de conversation par session, découplé de l'interface (voir
    docstring de module)."""

    def __init__(self, client_redis=None):
        self._client = client_redis

    def ajouter(self, id_session: str, question: str, reponse: Reponse) -> None:
        """Ajoute un echange, avec un TTL glissant de 24h sur la cle de session
        (bug trouve le 27/08, voir JOURNAL.md -- cette cle n'avait jusqu'ici AUCUNE
        expiration, contrairement au cache : elle s'accumulait indefiniment dans
        Redis). `expire()` est rappele a chaque ajout plutot que fixe une seule fois
        a la creation : une conversation active voit son TTL repousse a chaque
        message, seule une session vraiment abandonnee finit par expirer -- jamais
        de coupure en pleine conversation."""
        if self._client is None:
            return
        entree = json.dumps({"question": question, "reponse": asdict(reponse)})
        cle = PREFIXE_HISTORIQUE + id_session
        self._client.rpush(cle, entree)
        self._client.expire(cle, TTL_HISTORIQUE)

    def recuperer(self, id_session: str) -> list[dict]:
        """Renvoie la liste des échanges (question + réponse, dans l'ordre
        chronologique) pour la session donnée, ou [] si absente/client non
        configuré."""
        if self._client is None:
            return []
        brutes = self._client.lrange(PREFIXE_HISTORIQUE + id_session, 0, -1)
        return [json.loads(b) for b in brutes]
