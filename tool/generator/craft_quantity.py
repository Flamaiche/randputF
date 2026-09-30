"""C1 : randomisation des quantités de craft, branchée au pipeline.

Passe post-assemblage : une fois la seed assemblée (dict de recettes), un flux
RNG DÉDIÉ (`randputF:craft_quantity:`) applique un facteur multiplicatif aux
quantités d'entrée/sortie de chaque recette — sans toucher aux noms, aux
étapes, ni à la structure. La solvabilité (§15) ne dépend pas des quantités
(le validateur lit uniquement la structure), donc cette passe peut tourner
après la validation sans casser les garanties.

Inerte si la section ``craft_quantity`` est absente ou ``enabled: false``.
"""

from __future__ import annotations

from tool.common.rng import make_seeded_rng


def apply_craft_quantity(seed: dict, config: dict) -> None:
    """Applique C1 sur ``seed["recipes"]``, en place (mutate).

    Miroir du prototype `tool/prototypes/craft_quantity.py` : mode symmetric
    (un facteur par recette) ou asymmetric (un facteur par ligne), minimum
    `amount_min` unités par ingrédient/sortie.
    """
    from tool.prototypes.craft_quantity import CraftQuantityConfig

    cq = config.get("craft_quantity") or {}
    if not cq.get("enabled", False):
        return

    cqcfg = CraftQuantityConfig.from_config(config)
    seed_value = int(seed["meta"]["seed"])
    crng = make_seeded_rng(seed_value, "randputF:craft_quantity:")

    def _scale(amount: int, factor: float) -> int:
        return max(cqcfg.amount_min, int(round(amount * factor)))

    for recipe in seed.get("recipes", []):
        if cqcfg.mode == "symmetric":
            factor = crng.uniform(cqcfg.factor_min, cqcfg.factor_max)
            for ing in recipe.get("ingredients", []):
                ing["amount"] = _scale(int(ing["amount"]), factor)
            for res in recipe.get("results", []):
                res["amount"] = _scale(int(res["amount"]), factor)
        else:  # asymmetric : un facteur indépendant par ligne.
            for ing in recipe.get("ingredients", []):
                f = crng.uniform(cqcfg.factor_min, cqcfg.factor_max)
                ing["amount"] = _scale(int(ing["amount"]), f)
            for res in recipe.get("results", []):
                f = crng.uniform(cqcfg.factor_min, cqcfg.factor_max)
                res["amount"] = _scale(int(res["amount"]), f)