"""Configuration : recettes.

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
    # Énergie par palier de complexité (nb d'ingrédients).
    # Multiplie le tirage de base par (1 + energy_per_ingredient × n_ingredients).
    energy_per_ingredient: float = 0.25
    # Équilibre production/consommation : cible cons/prod tirée uniformément
    # entre balance_min et balance_max. Un item beaucoup produit mais peu consommé
    # est « pléthore » : on encourage sa consommation et on freine sa production ;
    # l'inverse pour un item rare.
    balance_min: float = 3.0 / 16.0
    balance_max: float = 2.0 / 3.0
    # Pente du facteur de correction et bornes du multiplicateur.
    balance_steepness: float = 1.0
    balance_max_factor: float = 4.0
    # Quota plafond « pléthore » : production ramenée à ce quota max (défaut 1/3).
    max_overproduced_ratio: float = 1.0 / 3.0
    balance_iterations: int = 2
    ingredient_amount_min: int = 1
    ingredient_amount_max: int = 4
    recipe_prefix: str = "randputf-"
    # Ressources environnementales (arbres/rochers/poissons) : poids faible
    # quand des patchs existent, poids fort quand la seed n'a aucun patch item
    # (urgence : fabriquer les extracteurs), quantités plafonnées.
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
            energy_per_ingredient=float(
                rec_cfg.get("energy_per_ingredient", 0.25)
            ),
            balance_min=float(rec_cfg.get("balance_min", 3.0 / 16.0)),
            balance_max=float(rec_cfg.get("balance_max", 2.0 / 3.0)),
            balance_steepness=float(rec_cfg.get("balance_steepness", 1.0)),
            balance_max_factor=float(rec_cfg.get("balance_max_factor", 4.0)),
            max_overproduced_ratio=float(
                rec_cfg.get("max_overproduced_ratio", 1.0 / 3.0)
            ),
            balance_iterations=int(rec_cfg.get("balance_iterations", 2)),
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

    def roll_energy(self, rng: random.Random, n_ingredients: int = 0) -> float:
        base = float(rng.choice(self.recipe_energies))
        return round(base * (1 + self.energy_per_ingredient * n_ingredients), 3)

    def balance_weight(self, ratio: float, target: float) -> float:
        """Facteur de pondération équilibre pour un ratio cons/prod.
        Reward pléthore (ratio bas), penalty rareté (ratio haut).
        Ratio borné au plancher max_overproduced_ratio."""
        eff = max(ratio, self.max_overproduced_ratio)
        if eff <= 0:
            return self.balance_max_factor
        closeness = target / eff  # > 1 si pléthore (reward), < 1 si rare (penalty)
        factor = closeness ** self.balance_steepness
        return max(1.0 / self.balance_max_factor,
                   min(self.balance_max_factor, factor))

    def roll_ingredient_amount(self, rng: random.Random) -> int:
        return rng.randint(self.ingredient_amount_min, self.ingredient_amount_max)

    def recipe_name(self, product_name: str) -> str:
        return f"{self.recipe_prefix}{product_name}"