"""Prototype : énergie / électricité (§10).

Gère la résolution de la chaîne énergétique :
- sélection du générateur
- affectation du combustible
- fallback si aucun combustible disponible
- steps pour le tech tree

Configuration :
- priorité des types de générateurs
- stratégies de sélection de combustible
- paramètres de fallback
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
class ElectricityConfig(PrototypeConfig):
    """Configuration pour l'énergie / électricité."""
    # Priorité des types de générateurs (plus haut = choisi en premier)
    generator_priorities: dict[str, float] = field(default_factory=lambda: {
        "generator": 10.0,
        "boiler": 5.0,
        "solar": 3.0,
        "accumulator": 1.0,
    })
    # Stratégie de sélection de combustible : "weighted" ou "random"
    fuel_strategy: str = "weighted"
    # Créer des recettes de combustible fallback si aucun fuel disponible
    allow_fallback_fuel: bool = True
    # Combustibles fallback à créer (noms d'items vanilla)
    fallback_fuels: list[str] = field(default_factory=lambda: [
        "wood",
        "coal",
    ])
    # Poids des combustibles par type de générateur
    fuel_weights: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: dict) -> ElectricityConfig:
        elec_cfg = config.get("electricity", {})
        return cls(
            allow_fallback_fuel=bool(elec_cfg.get("allow_fallback_fuel", True)),
            fuel_strategy=elec_cfg.get("fuel_strategy", "weighted"),
        )


class ElectricityPrototype(MechanicPrototype):
    """Prototype pour l'énergie / électricité.

    Pool : générateurs non débloqués + combustibles disponibles.
    Fournit des pools séparés pour générateurs et combustibles.
    """

    def __init__(self, config: ElectricityConfig, pool: PoolManager) -> None:
        super().__init__(config, pool)
        self._config = config

    def build_picker(self) -> WeightedPicker:
        """Pool combiné générateurs + combustibles."""
        picker = WeightedPicker()
        for b in self.pool.db.buildings_of_type("generator"):
            if b.name not in self.pool.state.unlocked_buildings:
                picker.add(b.name, weight=1.0, tags={"generator"})
        for item in self.pool.db.fuel_items():
            if item.name not in self.pool.state.obtained_items:
                picker.add(item.name, weight=1.0, tags={"fuel"})
        return picker

    def generators_picker(self) -> WeightedPicker:
        """Pool des générateurs non débloqués."""
        picker = WeightedPicker()
        for b in self.pool.db.buildings_of_type("generator"):
            if b.name not in self.pool.state.unlocked_buildings:
                weight = self._config.generator_priorities.get("generator", 10.0)
                picker.add(b.name, weight=weight)
        return picker

    def fuels_picker(self) -> WeightedPicker:
        """Pool des combustibles disponibles."""
        picker = WeightedPicker()
        for item in self.pool.db.fuel_items():
            if item.name not in self.pool.state.obtained_items:
                picker.add(item.name, weight=1.0)
        return picker

    def should_create_fallback(self) -> bool:
        """Vérifie si le fallback combustible est autorisé."""
        return self._config.allow_fallback_fuel

    def fallback_fuels(self) -> list[str]:
        """Liste des combustibles fallback à créer."""
        return self._config.fallback_fuels
