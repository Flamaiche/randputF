"""Prototype : kit de départ + extraction + transformation (§7 et §8).

Gère la chaîne initiale :
- kit de départ (arme + munitions)
- extraction par ressource
- transformation de base
- transports (belt, splitter, underground, inserter, pipes)

Configuration :
- nombre de munitions du kit
- probabilité d'inclure un inserter
- patterns de transport par rôle
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tool.common.db import SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.common.pool_manager import PoolManager
from tool.common.weighted_picker import WeightedPicker
from tool.prototypes.base import MechanicPrototype, PrototypeConfig

if TYPE_CHECKING:
    from tool.generator.recipes import ProgressionState


@dataclass
class StarterConfig(PrototypeConfig):
    """Configuration pour le kit de départ et la chaîne initiale."""
    # Kit
    ammo_count: int = 50
    # Transports
    inserter_chance: float = 0.5
    # Patterns de recherche d'items de transport par rôle
    transport_patterns: dict[str, list[str]] = field(default_factory=lambda: {
        "belt": ["transport-belt"],
        "splitter": ["splitter"],
        "underground": ["underground-belt"],
        "pipe": ["pipe"],
        "pipe_to_ground": ["pipe-to-ground"],
        "inserter": ["inserter"],
    })
    # Rôles de transport requis par type de ressource
    item_transport_roles: tuple[str, ...] = ("belt", "splitter", "underground")
    fluid_transport_roles: tuple[str, ...] = ("pipe", "pipe_to_ground")
    # Rôle inserter ajouté conditionnellement
    optional_transport_roles: tuple[str, ...] = ("inserter",)

    @classmethod
    def from_config(cls, config: dict) -> StarterConfig:
        starter_cfg = config.get("starter", {})
        return cls(
            ammo_count=int(starter_cfg.get("ammo_count", 50)),
            inserter_chance=float(starter_cfg.get("inserter_chance", 0.5)),
        )


class StarterKitPrototype(MechanicPrototype):
    """Prototype pour le kit de départ.

    Pool : armes + munitions de la DB.
    Sélection : 1 arme au hasard + munitions correspondantes.
    """

    def __init__(self, config: StarterConfig, pool: PoolManager) -> None:
        super().__init__(config, pool)
        self._config = config

    def build_picker(self) -> WeightedPicker:
        """Pool d'armes disponibles pour le kit."""
        picker = WeightedPicker()
        for item in self.pool.db.items.values():
            if item.is_handheld_gun:
                picker.add(item.name, weight=1.0, tags={"gun"})
        return picker

    def pick_ammo(self, rng, gun_name: str) -> str | None:
        """Pioche des munitions correspondant à l'arme choisie."""
        gun = self.pool.db.items.get(gun_name)
        if gun is None:
            return None

        # Chercher des munitions de la même catégorie
        candidates = [
            item for item in self.pool.db.items.values()
            if item.is_ammo
            and gun.ammo_category
            and item.ammo_category == gun.ammo_category
        ]
        # Fallback : toutes les munitions
        if not candidates:
            candidates = [item for item in self.pool.db.items.values() if item.is_ammo]
        if not candidates:
            return None

        return rng.choice(candidates).name

    @property
    def ammo_count(self) -> int:
        return self._config.ammo_count


class TransportPrototype(MechanicPrototype):
    """Prototype pour les transports initiaux.

    Pool : items correspondant aux patterns de transport.
    Rôles : belt, splitter, underground, pipe, pipe_to_ground, inserter.
    """

    def __init__(self, config: StarterConfig, pool: PoolManager) -> None:
        super().__init__(config, pool)
        self._config = config

    def build_picker(self) -> WeightedPicker:
        """Pool de tous les items de transport."""
        picker = WeightedPicker()
        for role, patterns in self._config.transport_patterns.items():
            for item in self.pool.db.items.values():
                if any(p in item.name for p in patterns) and not item.is_tool:
                    picker.add(item.name, weight=1.0, tags={role})
        return picker

    def build_picker_for_role(self, role: str) -> WeightedPicker:
        """Pool d'items pour un rôle de transport spécifique."""
        picker = WeightedPicker()
        patterns = self._config.transport_patterns.get(role, [])
        for item in self.pool.db.items.values():
            if any(p in item.name for p in patterns) and not item.is_tool:
                picker.add(item.name, weight=1.0)
        return picker

    def should_add_inserter(self, rng) -> bool:
        """Détermine si on ajoute un inserter (probabilité configurable)."""
        return rng.random() < self._config.inserter_chance

    def item_roles(self) -> tuple[str, ...]:
        return self._config.item_transport_roles

    def fluid_roles(self) -> tuple[str, ...]:
        return self._config.fluid_transport_roles
