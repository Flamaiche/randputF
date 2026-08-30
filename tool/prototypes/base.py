"""Classes de base pour les prototypes de mécaniques.

Chaque mécanique du jeu (extraction, combat, science, etc.) est modélisée
comme un prototype qui définit :
- son pool d'éléments (via PoolManager)
- ses poids de sélection (via WeightedPicker)
- sa configuration (magic numbers → attributs configurables)
- sa logique de génération

Les prototypes ne contiennent PAS de logique de pipeline — ils sont
purement déclaratifs et utilisés par les phases existantes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tool.common.db import VanillaDB
from tool.common.pool_manager import PoolManager
from tool.common.weighted_picker import WeightedPicker

if TYPE_CHECKING:
    from tool.generator.recipes import ProgressionState


@dataclass
class PrototypeConfig:
    """Configuration de base pour un prototype.

    Toutes les valeursmagiques sont ici. Chaque sous-classe
    ajoute ses propres champs de configuration.
    """
    pass


class MechanicPrototype(ABC):
    """Classe de base pour tous les prototypes de mécaniques.

    Chaque prototype encapsule :
    - Une config typée (sous-classe de PrototypeConfig)
    - Un pool d'éléments pondérés
    - Des méthodes pour interroger et manipuler le pool

    Usage :
        proto = ExtractionPrototype(config, pool_manager)
        picker = proto.build_picker()
        choix = picker.pick(rng)
    """

    def __init__(self, config: PrototypeConfig, pool: PoolManager) -> None:
        self.config = config
        self.pool = pool

    @abstractmethod
    def build_picker(self) -> WeightedPicker:
        """Construit le WeightedPicker pour cette mécanique.

        Doit filtrer les éléments par l'état de progression
        et appliquer les poids de la config.
        """
        ...

    def has_available(self) -> bool:
        """Vérifie s'il y a des éléments disponibles."""
        picker = self.build_picker()
        return not picker.is_empty

    def pick(self, rng) -> str | None:
        """Pioche un élément au hasard pondéré."""
        picker = self.build_picker()
        return picker.pick(rng)
