"""Configuration : recettes (§7 et §8).

Configuration lue par le générateur recipes.py :
- nombre d'ingrédients par recette
- montants des résultats
- temps de craft (énergie)
- montants des ingrédients
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.common.weighted_picker import weighted_choice
from tool.prototypes.base import PrototypeConfig


@dataclass
class RecipeConfig(PrototypeConfig):
    """Configuration pour la génération de recettes."""
    ingredient_counts: list[tuple[int, int]] = field(default_factory=lambda: [
        (1, 3),
        (2, 5),
        (3, 2),
    ])
    result_amounts: list[tuple[int, int]] = field(default_factory=lambda: [
        (1, 7),
        (2, 3),
    ])
    recipe_energies: list[float] = field(default_factory=lambda: [0.5, 1.0, 2.0])
    ingredient_amount_min: int = 1
    ingredient_amount_max: int = 4
    recipe_prefix: str = "randputf-"
    # Ressources environnementales (arbres/rochers/poissons) : utilisables des
    # le depart mais rares. Poids faible quand des patchs items existent,
    # poids fort quand la seed n'a AUCUN patch item (urgence : fabriquer les
    # extracteurs), et quantites plafonnees.
    environmental_weight_rich: float = 0.02
    environmental_weight_starved: float = 2.0
    environmental_amount_max: int = 2

    @classmethod
    def from_config(cls, config: dict) -> RecipeConfig:
        rec_cfg = config.get("recipes", {})
        return cls(
            ingredient_counts=[
                (1, int(rec_cfg.get("weight_1_ingredient", 3))),
                (2, int(rec_cfg.get("weight_2_ingredients", 5))),
                (3, int(rec_cfg.get("weight_3_ingredients", 2))),
            ],
            result_amounts=[
                (1, int(rec_cfg.get("weight_1_result", 7))),
                (2, int(rec_cfg.get("weight_2_results", 3))),
            ],
            recipe_energies=[
                float(e) for e in rec_cfg.get("energies", [0.5, 1.0, 2.0])
            ],
            ingredient_amount_min=int(rec_cfg.get("ingredient_amount_min", 1)),
            ingredient_amount_max=int(rec_cfg.get("ingredient_amount_max", 4)),
            environmental_weight_rich=float(
                rec_cfg.get("environmental_weight_rich", 0.02)
            ),
            environmental_weight_starved=float(
                rec_cfg.get("environmental_weight_starved", 2.0)
            ),
            environmental_amount_max=int(
                rec_cfg.get("environmental_amount_max", 2)
            ),
        )

    def roll_ingredient_count(self, rng: random.Random) -> int:
        return weighted_choice(rng, self.ingredient_counts)

    def roll_result_amount(self, rng: random.Random) -> int:
        return weighted_choice(rng, self.result_amounts)

    def roll_energy(self, rng: random.Random) -> float:
        return float(rng.choice(self.recipe_energies))

    def roll_ingredient_amount(self, rng: random.Random) -> int:
        return rng.randint(self.ingredient_amount_min, self.ingredient_amount_max)

    def recipe_name(self, product_name: str) -> str:
        return f"{self.recipe_prefix}{product_name}"