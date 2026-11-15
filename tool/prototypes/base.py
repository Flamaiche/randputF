"""Configuration de base pour les prototypes de mécaniques.

Sous-classes de ``PrototypeConfig`` pour chaque mécanique du jeu.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PrototypeConfig:
    """Configuration de base des prototypes de mécaniques.

    Cette classe ne porte aucun champ ; chaque sous-classe ajoute les réglages de sa mécanique et implémente ``from_config`` pour les lire depuis le dict validé. Sert de type commun et de point d'ancrage documentaire.
    """
    pass