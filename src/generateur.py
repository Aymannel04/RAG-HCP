"""
Module Generateur — module 8 de l'architecture.
Rôle : rédiger la réponse en langage naturel, toujours accompagnée de sa source
(document, date, lien) — grounding strict, jamais de chiffre hors contexte fourni.

Décisions d'implémentation :

- **Chemin chiffré (contexte = Indicateur) : pas de LLM du tout.** D'après
  docs/conception_uml_v3.pdf (analyse de la figure 5) : « le Generateur n'intervient
  qu'en toute fin de chaîne pour mettre cette valeur en forme dans une phrase, sans
  marge d'interprétation sur le chiffre lui-même ». C'est donc un simple gabarit de
  texte (f-string), pas une génération libre -- zéro risque d'hallucination sur ce
  chemin, et zéro dépendance au choix du LLM (voir point suivant).
- **Chemin notion (contexte = list[Chunk]) : LLM injectable, requis.** Contrairement au
  chemin chiffré, synthétiser plusieurs passages en une réponse cohérente nécessite une
  vraie génération de texte. `fonction_generation` est injectable au constructeur (même
  patron que `IndexeurTexte._embarquer` pour BGE-M3) : toute la logique de grounding, de
  citation de source et de gestion du cas "pas d'information" est indépendante du LLM
  branché (voir `src/llm_mistral.py` pour l'implémentation de production, ADR 0002). Sans
  fonction injectée, `generer_reponse` lève une erreur explicite plutôt que d'inventer un
  texte ou de faire semblant de fonctionner.
- **Signature étendue par rapport au squelette d'origine** (`generer_reponse(contexte)`
  sans `question`) : la question est nécessaire pour que la génération LLM du chemin
  notion reste réellement centrée sur ce qui a été demandé plutôt que de résumer les
  passages hors contexte -- écart mineur et justifié, pas un changement d'architecture.
- **Accès à la base SQLite** (constructeur prend `conn`) : le `Chunk`/`Indicateur` en
  mémoire ne portent que `id_document`, pas le titre/URL/date de la publication source
  -- nécessaires pour la citation (exigence NF3, traçabilité). Même patron que
  `LookupStructure(conn)`.
- **Chemin mixte (contexte = `ContexteMixte`)** : une question comme "pourquoi le
  chômage a-t-il augmenté ?" a une composante chiffrée ET narrative.
  `Routeur.classifier` renvoie désormais `TypeQuestion.MIXTE` pour ce cas (voir
  `src/routeur.py`) et `scripts/poser_question.py` interroge les deux chemins en
  parallèle. Ici, la fusion respecte le même principe fondateur que le chemin chiffré
  seul : **le chiffre lui-même reste toujours produit par le gabarit déterministe**,
  jamais reformulé par le LLM -- celui-ci ne sert qu'à expliquer le "pourquoi", avec le
  chiffre officiel injecté dans son contexte pour que son explication reste cohérente
  avec la valeur déjà citée (zéro risque que le LLM invente un chiffre différent dans sa
  partie de la réponse). Dégradation propre si un des deux chemins ne trouve rien :
  réponse chiffrée seule, ou notion seule, plutôt qu'un échec complet.

"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable, Optional, Union

from .models import Chunk, Indicateur


@dataclass
class Reponse:
    texte: str
    source_url: str
    source_titre: str
    source_date: Optional[str] = None
    # Renseignes uniquement pour une reponse mixte dont les deux sources (l'indicateur
    # BDS et le document narratif) sont distinctes -- voir _generer_reponse_mixte.
    # `source_*` ci-dessus reste la source du CHIFFRE dans ce cas (le plus verifiable
    # des deux, coherent avec le principe "chiffre = gabarit deterministe").
    source_url_secondaire: Optional[str] = None
    source_titre_secondaire: Optional[str] = None
    source_date_secondaire: Optional[str] = None


@dataclass
class ContexteMixte:
    """Contexte du chemin mixte (voir docstring de module) : un indicateur exact ET des
    chunks narratifs, tous deux trouves pour la meme question."""
    indicateur: Indicateur
    chunks: list[Chunk]


TypeFonctionGeneration = Callable[[str, str], str]  # (question, texte_contexte) -> reponse

MESSAGE_SANS_INFORMATION = (
    "Je n'ai pas trouvé d'information sur ce sujet dans les publications indexées du HCP."
)


class Generateur:
    """Génère la réponse finale à partir du contexte récupéré (chunks ou indicateur)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        fonction_generation: Optional[TypeFonctionGeneration] = None,
    ):
        """
        `fonction_generation` : injectable pour les tests et en attendant le choix du
        LLM de production (voir docstring de module). Utilisée uniquement pour le
        chemin notion -- le chemin chiffré ne l'appelle jamais.
        """
        self._conn = conn
        self._fonction_generation = fonction_generation

    def generer_reponse(
        self, question: str, contexte: Union[list[Chunk], Indicateur, ContexteMixte, None]
    ) -> Reponse:
        """Rédige une réponse sourcée à partir du contexte fourni.

        Contrainte de grounding strict : si `contexte` est vide/None, la réponse doit
        être explicite sur l'absence d'information plutôt que d'inventer une réponse
        (voir docs/fiche_cadrage_v4.pdf, section 8.5 - points de robustesse).
        """
        if contexte is None or (isinstance(contexte, list) and not contexte):
            return Reponse(texte=MESSAGE_SANS_INFORMATION, source_url="", source_titre="", source_date=None)

        if isinstance(contexte, ContexteMixte):
            return self._generer_reponse_mixte(question, contexte)

        if isinstance(contexte, Indicateur):
            return self._generer_reponse_chiffree(contexte)

        return self._generer_reponse_notion(question, contexte)

    # --- Chemin chiffre : gabarit, aucun LLM (voir docstring de module) --------------

    def _generer_reponse_chiffree(self, indicateur: Indicateur) -> Reponse:
        texte = self._phrase_chiffree(indicateur)
        titre, url, date_publication = self._recuperer_document(indicateur.id_document)
        return Reponse(texte=texte, source_url=url, source_titre=titre, source_date=date_publication)

    def _phrase_chiffree(self, indicateur: Indicateur) -> str:
        """Gabarit déterministe partagé par le chemin chiffré seul et le chemin mixte
        (voir `_generer_reponse_mixte`) -- factorisé pour ne jamais dupliquer la seule
        logique qui produit le chiffre lui-même dans une phrase."""
        region = f", {indicateur.region}" if indicateur.region else ""
        unite = self._unite_formatee(indicateur.unite)
        return (
            f"D'après les données du HCP, {indicateur.nom} s'élève à "
            f"{indicateur.valeur:g}{unite} pour la période {indicateur.periode}{region}."
        )

    @staticmethod
    def _unite_formatee(unite: Optional[str]) -> str:
        """Met en forme `indicateur.unite` pour un gabarit de phrase.

        L'API BDS renvoie parfois l'unite en toutes lettres et en MAJUSCULES (ex.
        "POURCENTAGE"), jamais normalisee nulle part dans le pipeline
        (`ConstructeurIndicateurs.structurer_depuis_bds` la transmet telle quelle) --
        collee directement apres le chiffre, ca donnerait "9 POURCENTAGE" au lieu de
        "9%". Corrige ici plutot que dans `ConstructeurIndicateurs`, pour ne pas
        modifier la valeur stockee en base (traçabilite : on veut garder la valeur
        API brute en base, seule sa mise en forme dans une phrase doit changer).
        """
        if not unite:
            return ""
        nettoye = unite.strip()
        if nettoye.lower() in {"pourcentage", "pour cent", "percent", "%"}:
            return "%"
        if len(nettoye) <= 4:
            return f" {nettoye}"  # probablement un code court (MAD, USD...), garde tel quel
        return f" {nettoye.lower()}"

    # --- Chemin notion : synthese via LLM injectable ---------------------------------

    def _generer_reponse_notion(self, question: str, chunks: list[Chunk]) -> Reponse:
        if self._fonction_generation is None:
            raise NotImplementedError(
                "Aucune fonction de generation LLM configuree : injecter "
                "`fonction_generation` au constructeur de Generateur (voir docstring "
                "de module -- `src/llm_mistral.py` pour la production, ou une "
                "fonction factice pour les tests)."
            )

        texte_contexte = "\n\n".join(chunk.texte for chunk in chunks)
        try:
            texte = self._fonction_generation(question, texte_contexte)
        except Exception:
            # Degradation propre, meme philosophie que le fallback LLM de
            # Routeur/Reformulateur : une panne reseau/API ne doit jamais faire
            # crasher tout le pipeline, seulement degrader vers un message explicite.
            return Reponse(
                texte=(
                    "Une erreur technique (reseau ou service de generation indisponible) "
                    "a empeche de repondre a cette question. Reessayez dans quelques instants."
                ),
                source_url="", source_titre="", source_date=None,
            )

        titre, url, date_publication = self._recuperer_document(chunks[0].id_document)
        return Reponse(texte=texte, source_url=url, source_titre=titre, source_date=date_publication)

    # --- Chemin mixte : gabarit chiffre + explication LLM groundee, voir docstring ---

    def _generer_reponse_mixte(self, question: str, contexte: ContexteMixte) -> Reponse:
        phrase_chiffree = self._phrase_chiffree(contexte.indicateur)
        titre_chiffre, url_chiffre, date_chiffre = self._recuperer_document(contexte.indicateur.id_document)

        if not contexte.chunks or self._fonction_generation is None:
            # Pas de contexte narratif exploitable (rien trouve par RetrievalReranker,
            # ou aucun LLM configure) : degradation propre vers le chiffre seul plutot
            # que d'echouer completement -- meme philosophie que le repli CHIFFRE ->
            # NOTION deja documente dans scripts/poser_question.py.
            return Reponse(texte=phrase_chiffree, source_url=url_chiffre, source_titre=titre_chiffre, source_date=date_chiffre)

        # Le chiffre officiel est injecte EN TETE du contexte fourni au LLM, pour que
        # son explication du "pourquoi" reste coherente avec la valeur deja citee
        # ci-dessus -- le LLM explique, il ne reformule jamais le chiffre lui-meme
        # (voir docstring de module).
        texte_contexte = (
            f"Chiffre officiel a mentionner tel quel si utile : {phrase_chiffree}\n\n"
            + "\n\n".join(chunk.texte for chunk in contexte.chunks)
        )
        try:
            explication = self._fonction_generation(question, texte_contexte)
        except Exception:
            # Degradation propre (voir docstring de _generer_reponse_notion) : le
            # chiffre officiel reste fiable puisqu'il ne depend d'aucun appel LLM --
            # une panne de l'explication ne doit pas priver l'utilisateur du chiffre.
            return Reponse(texte=phrase_chiffree, source_url=url_chiffre, source_titre=titre_chiffre, source_date=date_chiffre)
        texte = f"{phrase_chiffree} {explication}"

        titre_notion, url_notion, date_notion = self._recuperer_document(contexte.chunks[0].id_document)
        if url_notion == url_chiffre:
            # Meme document source (rare mais possible, ex. fiche synthetique BDS citee
            # aussi comme chunk) : pas besoin d'une seconde citation redondante.
            return Reponse(texte=texte, source_url=url_chiffre, source_titre=titre_chiffre, source_date=date_chiffre)

        return Reponse(
            texte=texte, source_url=url_chiffre, source_titre=titre_chiffre, source_date=date_chiffre,
            source_url_secondaire=url_notion, source_titre_secondaire=titre_notion, source_date_secondaire=date_notion,
        )

    # --- Utilitaire ---------------------------------------------------------------

    def _recuperer_document(self, id_document: int) -> tuple[str, str, Optional[str]]:
        ligne = self._conn.execute(
            "SELECT titre, url, date_publication FROM document WHERE id_document = ?",
            (id_document,),
        ).fetchone()
        if ligne is None:
            return "", "", None
        return ligne[0], ligne[1], ligne[2]
