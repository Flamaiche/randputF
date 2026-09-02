"""Configuration de base pour les prototypes de mécaniques.

Chaque mécanique du jeu (extraction, combat, science, etc.) expose une
sous-classe de ``PrototypeConfig`` qui centralise ses valeurs magiques et
sa lecture depuis ``config/settings.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PrototypeConfig:
    """Configuration de base pour un prototype.

    Toutes les valeurs magiques sont ici. Chaque sous-classe
    ajoute ses propres champs de configuration.
    """
    pass