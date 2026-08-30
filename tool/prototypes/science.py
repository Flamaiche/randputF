"""Prototype : science packs (§7 et §13).

Gère la génération de science packs et de leurs coûts de recherche.
Chaque science pack a un coût configuré en items du pool déjà obtenu.

Configuration :
- items éligibles pour les coûts (par tag ou type)
- montants de coût (nombre d'items × quantité par item)
- nombre de cycles de recherche par pack
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
class ScienceConfig(PrototypeConfig):
    """Configuration pour les science packs."""
    # Coût de recherche : items requis pour chaque cycle
    cost_ingredients_min: int = 1
    cost_ingredients_max: int = 2
    # Montant par ingrédient de coût
    cost_amount_min: int = 5
    cost_amount_max: int = 15
    # Nombre de cycles de recherche
    research_count_min: int = 5
    research_count_max: int = 15
    # Filtre : seuls les items de type "tool" sont éligibles pour les coûts
    cost_item_filter: str = "tool"

    @classmethod
    def from_config(cls, config: dict) -> ScienceConfig:
        sci_cfg = config.get("science", {})
        return cls(
            cost_ingredients_min=int(sci_cfg.get("cost_ingredients_min", 1)),
            cost_ingredients_max=int(sci_cfg.get("cost_ingredients_max", 2)),
            cost_amount_min=int(sci_cfg.get("cost_amount_min", 5)),
            cost_amount_max=int(sci_cfg.get("cost_amount_max", 15)),
            research_count_min=int(sci_cfg.get("research_count_min", 5)),
            research_count_max=int(sci_cfg.get("research_count_max", 15)),
        )

    def roll_research_count(self, rng: random.Random) -> int:
        return rng.randint(self.research_count_min, self.research_count_max)


class SciencePrototype(MechanicPrototype):
    """Prototype pour les science packs.

    Pool : tous les science packs non obtenus.
    Coûts : items du pool déjà obtenu (hors le pack lui-même).
    """

    def __init__(self, config: ScienceConfig, pool: PoolManager) -> None:
        super().__init__(config, pool)
        self._config = config

    def build_picker(self) -> WeightedPicker:
        """Pool des science packs non obtenus."""
        return self.pool.undeployed_science()

    def build_cost_pool(self, exclude_item: str = "") -> WeightedPicker:
        """Pool d'items éligibles pour les coûts de recherche.

        Exclut le pack lui-même et les items générés (randputf-).
        """
        picker = WeightedPicker()
        for name in sorted(self.pool.state.obtained_items):
            if name == exclude_item:
                continue
            if name.startswith("randputf-"):
                continue
            item = self.pool.db.items.get(name)
            if item and item.is_tool:
                picker.add(name, weight=1.0)
        return picker

    def build_cost(self, rng: random.Random, exclude_item: str = "") -> list[dict]:
        """Génère le coût de recherche d'un science pack.

        Retourne une liste de {type: "item", name: ..., amount: ...}.
        """
        cost_pool = self.build_cost_pool(exclude_item)
        if cost_pool.is_empty:
            return []

        n_ingredients = min(
            rng.randint(self._config.cost_ingredients_min, self._config.cost_ingredients_max),
            len(cost_pool),
        )
        chosen_items = cost_pool.pick_many(rng, n_ingredients)

        cost = []
        for item_name in chosen_items:
            amount = rng.randint(
                self._config.cost_amount_min,
                self._config.cost_amount_max,
            )
            cost.append({"type": "item", "name": item_name, "amount": amount})

        return cost

    def roll_research_count(self, rng: random.Random) -> int:
        """Nombre de cycles de recherche."""
        return rng.randint(
            self._config.research_count_min,
            self._config.research_count_max,
        )
