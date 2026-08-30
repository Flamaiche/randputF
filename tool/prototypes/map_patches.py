"""Prototype : ressources au sol (§6).

Gère la génération des patchs de ressources sur la carte.
Configuration :
- nombre de patchs (min/max)
- richesse des patchs (items/fluides)
- pool de ressources candidates
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
class MapPatchesConfig(PrototypeConfig):
    """Configuration pour les ressources au sol."""
    patches_min: int = 3
    patches_max: int = 8
    richness_item: tuple[int, int] = (50_000, 300_000)
    richness_fluid: tuple[int, int] = (100_000, 600_000)
    # Poids relatif items vs fluides (items 70%, fluides 30% par défaut)
    item_weight: float = 70.0
    fluid_weight: float = 30.0

    @classmethod
    def from_config(cls, config: dict) -> MapPatchesConfig:
        """Construit depuis le dict config du pipeline."""
        map_cfg = config.get("map", {})
        return cls(
            patches_min=int(map_cfg.get("patches_min", 3)),
            patches_max=int(map_cfg.get("patches_max", 8)),
            richness_item=tuple(map_cfg.get("richness_item", [50_000, 300_000])),
            richness_fluid=tuple(map_cfg.get("richness_fluid", [100_000, 600_000])),
            item_weight=float(map_cfg.get("item_weight", 70.0)),
            fluid_weight=float(map_cfg.get("fluid_weight", 30.0)),
        )

    def roll_count(self, rng: random.Random) -> int:
        return rng.randint(max(1, self.patches_min), max(1, self.patches_max))


@dataclass
class PatchChoice:
    """Un choix de patch avec ses métadonnées."""
    kind: str       # "item" ou "fluid"
    name: str       # nom de la ressource
    richness_range: tuple[int, int]


class MapPatchesPrototype(MechanicPrototype):
    """Prototype pour les ressources au sol.

    Pool : tous les items beltables + fluides pipables.
    Poids : items vs fluides (configurable).
    """

    def __init__(self, config: MapPatchesConfig, pool: PoolManager) -> None:
        super().__init__(config, pool)
        self._config = config

    def build_picker(self) -> WeightedPicker:
        """Construit un pool de ressources candidates pondérées."""
        picker = WeightedPicker()

        # Items beltables
        for item in self.pool.db.beltable_items():
            picker.add(
                item.name,
                weight=self._config.item_weight,
                tags={"item"},
            )

        # Fluides pipables
        for fluid in self.pool.db.pipable_fluids():
            picker.add(
                fluid.name,
                weight=self._config.fluid_weight,
                tags={"fluid"},
            )

        return picker

    def roll_count(self, rng: random.Random) -> int:
        """Nombre aléatoire de patchs à générer."""
        return rng.randint(
            max(1, self._config.patches_min),
            max(1, self._config.patches_max),
        )

    def richness_range_for(self, kind: str) -> tuple[int, int]:
        """Retourne les bornes de richesse pour un type donné."""
        if kind == "fluid":
            return self._config.richness_fluid
        return self._config.richness_item
