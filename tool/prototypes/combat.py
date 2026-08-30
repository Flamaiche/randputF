"""Prototype : armes et munitions (§7).

Gère la génération de recettes pour armes et munitions.
Les armes sont déjà couvertes par combat dans recursive.py,
ce prototype gère les spécificités des munitions :
- catégories d'armes (bullet, rocket, laser, etc.)
- quantités de munitions par recette
- probabilité de recettes multiples
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
class CombatConfig(PrototypeConfig):
    """Configuration pour les armes et munitions."""
    # Quantité de munitions par recette
    ammo_amount_min: int = 1
    ammo_amount_max: int = 4
    # Recettes multiples par arme
    recipes_per_weapon_min: int = 1
    recipes_per_weapon_max: int = 2
    # Poids de sélection des armes (pour arbre tech)
    weapon_weight: float = 1.0
    ammo_weight: float = 1.0

    @classmethod
    def from_config(cls, config: dict) -> CombatConfig:
        combat_cfg = config.get("combat", {})
        return cls(
            ammo_amount_min=int(combat_cfg.get("ammo_amount_min", 1)),
            ammo_amount_max=int(combat_cfg.get("ammo_amount_max", 4)),
            recipes_per_weapon_min=int(combat_cfg.get("recipes_per_weapon_min", 1)),
            recipes_per_weapon_max=int(combat_cfg.get("recipes_per_weapon_max", 2)),
        )

    def roll_ammo_amount(self, rng: random.Random) -> int:
        return rng.randint(self.ammo_amount_min, self.ammo_amount_max)

    def roll_recipes_count(self, rng: random.Random) -> int:
        return rng.randint(self.recipes_per_weapon_min, self.recipes_per_weapon_max)


class CombatPrototype(MechanicPrototype):
    """Prototype pour les armes et munitions.

    Pool : armes (guns) et munitions (ammo) de la DB.
    Fournit des pools séparés pour les armes et les munitions.
    """

    def __init__(self, config: CombatConfig, pool: PoolManager) -> None:
        super().__init__(config, pool)
        self._config = config

    def build_picker(self) -> WeightedPicker:
        """Pool combiné armes + munitions."""
        picker = WeightedPicker()
        for item in self.pool.db.items.values():
            if item.is_handheld_gun:
                picker.add(item.name, weight=self._config.weapon_weight, tags={"gun"})
            elif item.is_ammo:
                picker.add(item.name, weight=self._config.ammo_weight, tags={"ammo"})
        return picker

    def guns_picker(self) -> WeightedPicker:
        """Pool des armes uniquement."""
        picker = WeightedPicker()
        for item in self.pool.db.items.values():
            if item.is_handheld_gun:
                picker.add(item.name, weight=1.0)
        return picker

    def ammo_for_gun(self, gun_name: str) -> list[str]:
        """Retourne les munitions compatibles avec une arme."""
        gun = self.pool.db.items.get(gun_name)
        if gun is None:
            return []
        return [
            item.name for item in self.pool.db.items.values()
            if item.is_ammo
            and gun.ammo_category
            and item.ammo_category == gun.ammo_category
        ]

    def roll_ammo_amount(self, rng: random.Random) -> int:
        """Quantité de munitions par recette."""
        return rng.randint(
            self._config.ammo_amount_min,
            self._config.ammo_amount_max,
        )

    def roll_recipes_count(self, rng: random.Random) -> int:
        """Nombre de recettes par arme."""
        return rng.randint(
            self._config.recipes_per_weapon_min,
            self._config.recipes_per_weapon_max,
        )
