"""
Module Generateur — module 8 de l'architecture.
Rôle : rédiger la réponse en langage naturel, toujours accompagnée de sa source
(document, date, lien) — grounding strict, jamais de chiffre hors contexte fourni.

Décisions d'implémentation (Sprint 3, 21 juillet 2026) :

- **Chemin chiffré (contexte = Indicateur) : pas de LLM du tout.** D'après
  docs/conception_uml_v3.pdf (analyse de la figure 5) : « le Generateur n'intervient
  qu'en toute fin de chaîne pour mettre cette valeur en forme dans une phrase, sans
  marge d'interprétation sur le chiffre lui-même ». C'est donc un simple gabarit de
  texte (f-string), pas une génération libre -- zéro risque d'hallucination sur ce
  chemin, et zéro dépendance au choix du LLM (voir point suivant).
- **Chemin notion (contexte = list[Chunk]) : LLM injectable, requis.** Contrairement au
  chemin chiffré, synthétiser plusieurs passages en une réponse cohérente nécessite une
  vraie génération de texte. Le choix du LLM de production (API externe vs modèle
  open-weight hébergé localement) reste une décision ouverte -- voir
  docs/adr/0002-stack-technique-prototype.md, "point réellement bloquant... doit être
  validé avec l'encadrante". Plutôt que d'attendre cette validation pour avancer le
  Sprint 3, `fonction_generation` est injectable au constructeur (même patron que
  `IndexeurTexte._embarquer` pour BGE-M3 en Sprint 2) : toute la logique de grounding,
  de citation de source et de gestion du cas "pas d'information" est déjà écrite et
  testée, il ne restera qu'à câbler le vrai appel LLM une fois le choix arrêté. Sans
  fonction injectée, `generer_reponse` lève une erreur explicite plutôt que d'inventer
  un texte ou de faire semblant de fonctionner.
- **Signature étendue par rapport au squelette d'origine** (`generer_reponse(contexte)`
  sans `question`) : la question est nécessaire pour que la génération LLM du chemin
  notion reste réellement centrée sur ce qui a été demandé plutôt que de résumer les
  passages hors contexte -- écart mineur et justifié, pas un changement d'architecture.
- **Accès à la base SQLite** (constructeur prend `conn`) : le `Chunk`/`Indicateur` en
  mémoire ne portent que `id_document`, pas le titre/URL/date de la publication source
  -- nécessaires pour la citation (exigence NF3, traçabilité). Même patron que
  `LookupStructure(conn)`.

Statut : implémenté (chemin chiffré complet et testé sans dépendance externe ; chemin
notion testé avec une fonction de génération factice -- le vrai LLM reste à choisir).
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

    def generer_reponse(self, question: str, contexte: Union[list[Chunk], Indicateur, None]) -> Reponse:
        """Rédige une réponse sourcée à partir du contexte fourni.

        Contrainte de grounding strict : si `contexte` est vide/None, la réponse doit
        être explicite sur l'absence d'information plutôt que d'inventer une réponse
        (voir docs/fiche_cadrage_v4.pdf, section 8.5 - points de robustesse).
        """
        if contexte is None or (isinstance(contexte, list) and not contexte):
            return Reponse(texte=MESSAGE_SANS_INFORMATION, source_url="", source_titre="", source_date=None)

        if isinstance(contexte, Indicateur):
            return self._generer_reponse_chiffree(contexte)

        return self._generer_reponse_notion(question, contexte)

    # --- Chemin chiffre : gabarit, aucun LLM (voir docstring de module) --------------

    def _generer_reponse_chiffree(self, indicateur: Indicateur) -> Reponse:
        region = f", {indicateur.region}" if indicateur.region else ""
        unite = f" {indicateur.unite}" if indicateur.unite else ""
        texte = (
            f"D'après les données du HCP, {indicateur.nom} s'élève à "
            f"{indicateur.valeur:g}{unite} pour la période {indicateur.periode}{region}."
        )
        titre, url, date_publication = self._recuperer_document(indicateur.id_document)
        return Reponse(texte=texte, source_url=url, source_titre=titre, source_date=date_publication)

    # --- Chemin notion : synthese via LLM injectable ---------------------------------

    def _generer_reponse_notion(self, question: str, chunks: list[Chunk]) -> Reponse:
        if self._fonction_generation is None:
            raise NotImplementedError(
                "Aucune fonction de generation configuree : le choix du LLM de "
                "production (API externe vs modele open-weight local) reste a valider "
                "avec l'encadrante (voir ADR 0002). Injecter `fonction_generation` au "
                "constructeur de Generateur (voir docstring de module) -- pour un test "
                "rapide sans attendre cette decision, une fonction factice suffit, "
                "meme patron que IndexeurTexte en Sprint 2."
            )

        texte_contexte = "\n\n".join(chunk.texte for chunk in chunks)
        texte = self._fonction_generation(question, texte_contexte)

        titre, url, date_publication = self._recuperer_document(chunks[0].id_document)
        return Reponse(texte=texte, source_url=url, source_titre=titre, source_date=date_publication)

    # --- Utilitaire ---------------------------------------------------------------

    def _recuperer_document(self, id_document: int) -> tuple[str, str, Optional[str]]:
        ligne = self._conn.execute(
            "SELECT titre, url, date_publication FROM document WHERE id_document = ?",
            (id_document,),
        ).fetchone()
        if ligne is None:
            return "", "", None
        return ligne[0], ligne[1], ligne[2]
