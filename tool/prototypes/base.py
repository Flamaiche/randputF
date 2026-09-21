"""Configuration de base pour les prototypes de mécaniques.

Sous-classes de ``PrototypeConfig`` pour chaque mécanique du jeu.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PrototypeConfig:
    """Configuration de base. Chaque sous-classe ajoute ses propres champs."""
    pass