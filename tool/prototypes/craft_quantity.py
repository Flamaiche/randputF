"""Prototype D : randomisation des quantités de craft.

Au lieu du pur 1-pour-1, un facteur aléatoire est appliqué aux volumes
d'entrée/sortie de chaque recette. Deux variantes :
- symétrique : même facteur sur toutes les lignes d'une recette ;
- asymétrique : facteur indépendant par ingrédient (plus chaotique).

Contraintes : minimum 1 unité par ingrédient, PRNG déterministe par seed,
désactivation possible (facteur 1.0 partout).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.common import config as _cfg
from tool.prototypes.base import PrototypeConfig


@dataclass
class CraftQuantityConfig(PrototypeConfig):
    """Configuration de la randomisation des quantités de craft.

    ``enabled`` active la passe, ``mode`` vaut ``symmetric`` ou ``asymmetric``, ``factor_min``/``factor_max`` bornent le facteur multiplicatif et ``amount_min`` garantit un plancher par ingrédient.
    """
    enabled: bool = False
    # Mode : "symmetric" (même facteur pour toute la recette) ou "asymmetric".
    mode: str = "symmetric"
    # Bornes du facteur multiplicatif sur les quantités.
    factor_min: float = 0.5
    factor_max: float = 3.0
    # Minimum absolu par ingrédient (jamais en dessous).
    amount_min: int = 1

    @classmethod
    def from_config(cls, config: dict) -> CraftQuantityConfig:
        """Construit la configuration ``craft_quantity`` depuis le dict complet.

        ``config`` peut être partiel ; les clés absentes prennent les défauts de ``defaults.yaml`` via ``default_value``. Retourne une ``CraftQuantityConfig`` validée.
        """
        cfg = config.get("craft_quantity", {})
        return cls(
            enabled=bool(cfg.get("enabled", _cfg.default_value("craft_quantity", "enabled"))),
            mode=str(cfg.get("mode", _cfg.default_value("craft_quantity", "mode"))),
            factor_min=float(cfg.get("factor_min", _cfg.default_value("craft_quantity", "factor_min"))),
            factor_max=float(cfg.get("factor_max", _cfg.default_value("craft_quantity", "factor_max"))),
            amount_min=int(cfg.get("amount_min", _cfg.default_value("craft_quantity", "amount_min"))),
        )


@dataclass
class Ingredient:
    """Ingrédient ou résultat d'une recette du prototype.

    ``name`` est l'identifiant, ``amount`` la quantité et ``type`` vaut ``item`` ou ``fluid``. Modèle léger indépendant de ``VanillaDB``.
    """
    name: str
    amount: int
    type: str = "item"  # "item" | "fluid"


@dataclass
class RecipeSpec:
    """Recette du prototype de quantités.

    ``name`` identifie la recette, ``ingredients`` et ``results`` sont des listes d'``Ingredient``. Sert à appliquer la randomisation sans dépendre du format complet du seed.
    """
    name: str
    ingredients: list[Ingredient]
    results: list[Ingredient]


def randomise_recipe_quantities(
    rng: random.Random,
    recipe: RecipeSpec,
    config: CraftQuantityConfig,
) -> RecipeSpec:
    """Applique la randomisation de quantités sur une recette.

    - ``enabled=False`` → copie identique.
    - ``mode="symmetric"`` → un seul facteur pour tous les ingrédients et sorties.
    - ``mode="asymmetric"`` → un facteur indépendant par ligne.
    - ``amount_min`` garanti sur chaque ingrédient.
    """
    if not config.enabled:
        return RecipeSpec(
            name=recipe.name,
            ingredients=[Ingredient(i.name, i.amount, i.type) for i in recipe.ingredients],
            results=[Ingredient(r.name, r.amount, r.type) for r in recipe.results],
        )

    def _scale(amount: int, factor: float, amount_min: int) -> int:
        """Met à l'échelle un montant avec un plancher.

        ``amount`` est la quantité d'origine, ``factor`` le multiplicateur et ``amount_min`` le minimum garanti. Retourne ``max(amount_min, round(amount × factor))``.
        """
        return max(amount_min, int(round(amount * factor)))

    if config.mode == "symmetric":
        factor = rng.uniform(config.factor_min, config.factor_max)
        new_ing = [
            Ingredient(i.name, _scale(i.amount, factor, config.amount_min), i.type)
            for i in recipe.ingredients
        ]
        new_res = [
            Ingredient(r.name, _scale(r.amount, factor, config.amount_min), r.type)
            for r in recipe.results
        ]
    else:  # asymmetric
        new_ing = [
            Ingredient(
                i.name,
                _scale(i.amount, rng.uniform(config.factor_min, config.factor_max), config.amount_min),
                i.type,
            )
            for i in recipe.ingredients
        ]
        new_res = [
            Ingredient(
                r.name,
                _scale(r.amount, rng.uniform(config.factor_min, config.factor_max), config.amount_min),
                r.type,
            )
            for r in recipe.results
        ]

    return RecipeSpec(name=recipe.name, ingredients=new_ing, results=new_res)


def randomise_all_quantities(
    rng: random.Random,
    recipes: list[RecipeSpec],
    config: CraftQuantityConfig,
) -> list[RecipeSpec]:
    """Applique la randomisation à une liste de recettes.

    ``rng`` est la source aléatoire, ``recipes`` les recettes d'entrée et ``config`` la configuration validée. Retourne une nouvelle liste de ``RecipeSpec`` ; si la passe est désactivée, les recettes sont copiées à l'identique.
    """
    if not config.enabled:
        return [
            RecipeSpec(
                name=r.name,
                ingredients=[Ingredient(i.name, i.amount, i.type) for i in r.ingredients],
                results=[Ingredient(rr.name, rr.amount, rr.type) for rr in r.results],
            )
            for r in recipes
        ]
    return [randomise_recipe_quantities(rng, r, config) for r in recipes]


def verify_no_zero_amounts(recipes: list[RecipeSpec], amount_min: int = 1) -> list[str]:
    """Retourne les recettes ayant un ingrédient sous le plancher.

    ``recipes`` est la liste à vérifier et ``amount_min`` le minimum autorisé. Le résultat contient au plus une fois le nom de chaque recette fautive.
    """
    bad: list[str] = []
    for r in recipes:
        for i in r.ingredients:
            if i.amount < amount_min:
                bad.append(r.name)
                break
    return bad


def verify_recipe_names_preserved(recipes: list[RecipeSpec], originals: list[RecipeSpec]) -> bool:
    """Vérifie que les noms de recettes sont inchangés.

    ``recipes`` est la liste transformée et ``originals`` la liste d'origine. Retourne ``True`` si les noms se correspondent dans le même ordre, ``False`` sinon.
    """
    return [r.name for r in recipes] == [o.name for o in originals]
