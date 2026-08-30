"""Prototype : transports (§7).

Gère les types de transports (belt, inserter, pipe, etc.) et
les tiers disponibles. Pour v1, un seul tier par rôle ;
le branchement sera ajouté plus tard.

Configuration :
- patterns de recherche par rôle
- rôles requis par type de ressource
- probabilités d'ajout optionnel
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tool.common.db import VanillaDB
from tool.common.pool_manager import PoolManager
from tool.common.weighted_picker import WeightedPicker
from tool.prototypes.base import MechanicPrototype, PrototypeConfig

if TYPE_CHECKING:
    from tool.generator.recipes import ProgressionState


@dataclass
class TransportConfig(PrototypeConfig):
    """Configuration pour les transports."""
    # Patterns de recherche d'items par rôle
    patterns: dict[str, list[str]] = field(default_factory=lambda: {
        "belt": ["transport-belt"],
        "splitter": ["splitter"],
        "underground": ["underground-belt"],
        "pipe": ["pipe"],
        "pipe_to_ground": ["pipe-to-ground"],
        "inserter": ["inserter"],
    })
    # Rôles requis pour les items solides
    item_roles: tuple[str, ...] = ("belt", "splitter", "underground")
    # Rôles requis pour les fluides
    fluid_roles: tuple[str, ...] = ("pipe", "pipe_to_ground")
    # Rôles optionnels (probabilité d'ajout)
    optional_roles: dict[str, float] = field(default_factory=lambda: {
        "inserter": 0.5,
    })

    @classmethod
    def from_config(cls, config: dict) -> TransportConfig:
        trans_cfg = config.get("transport", {})
        return cls(
            item_roles=tuple(trans_cfg.get("item_roles", ["belt", "splitter", "underground"])),
            fluid_roles=tuple(trans_cfg.get("fluid_roles", ["pipe", "pipe_to_ground"])),
            optional_roles=trans_cfg.get("optional_roles", {"inserter": 0.5}),
        )


class CategoryTransportPrototype(MechanicPrototype):
    """Prototype pour les transports (version complète, catégorie獨立).

    Pool : items correspondant aux patterns de transport.
    Rôles : belt, splitter, underground, pipe, pipe_to_ground, inserter.
    """

    def __init__(self, config: TransportConfig, pool: PoolManager) -> None:
        super().__init__(config, pool)
        self._config = config

    def build_picker(self) -> WeightedPicker:
        """Pool de tous les items de transport."""
        picker = WeightedPicker()
        for role, patterns in self._config.patterns.items():
            for item in self.pool.db.items.values():
                if any(p in item.name for p in patterns) and not item.is_tool:
                    picker.add(item.name, weight=1.0, tags={role})
        return picker

    def build_picker_for_role(self, role: str) -> WeightedPicker:
        """Pool d'items pour un rôle spécifique."""
        picker = WeightedPicker()
        patterns = self._config.patterns.get(role, [])
        for item in self.pool.db.items.values():
            if any(p in item.name for p in patterns) and not item.is_tool:
                picker.add(item.name, weight=1.0)
        return picker

    def item_roles(self) -> tuple[str, ...]:
        return self._config.item_roles

    def fluid_roles(self) -> tuple[str, ...]:
        return self._config.fluid_roles

    def optional_roles(self) -> dict[str, float]:
        return self._config.optional_roles

    def should_add_role(self, rng: random.Random, role: str) -> bool:
        """Détermine si un rôle optionnel doit être ajouté."""
        chance = self._config.optional_roles.get(role, 0.0)
        return rng.random() < chance
