"""
Module Interface — module 9 de l'architecture.
Rôle : afficher la question, la réponse et la source cliquable ; recueillir le
feedback de l'utilisateur.

Prévue en Streamlit (voir requirements.txt et TODO.md).
"""
from __future__ import annotations

from .generateur import Reponse


class Interface:
    """Interface de démonstration (chat) pour interagir avec le système."""

    def afficher(self, reponse: Reponse) -> None:
        """Affiche la réponse et sa source à l'utilisateur."""
        raise NotImplementedError("Interface Streamlit non implementee, voir TODO.md")


if __name__ == "__main__":
    print("Interface de demonstration - non implementee (voir TODO.md).")
    print("Lancement prevu : streamlit run src/interface.py")
