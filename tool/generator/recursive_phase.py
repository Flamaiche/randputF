"""Phase 3 : récursion pondérée (README §9).

Après le starter, la génération devient récursive. Le pool de ressources
obtenables s'élargit à chaque itération, permettant des recettes de plus en
plus complexes.

Architecture :
- expand_recursive() remplit un module-level _tech_steps (macro-steps pour
  le tech tree) et génère les recettes via les primitives partagées.
- state.recipes contient toutes les recettes (starter + récursif).
- _tech_steps contient les macro-steps tech tree (unlock-recipe, coût, etc.).
"""

from __future__ import annotations

import random

from tool.common.db import SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.generator.map_patches import Patch
from tool.generator.recipes import ProgressionState, ensure_obtainable, make_recipe
from tool.generator.starter_chain import StarterChain

CATEGORY_WEIGHTS = {
    "transformer": 30,
    "extractor": 15,
    "generator": 10,
    "distribution": 10,
    "combat": 15,
    "science": 20,
}

EXCLUDED_BUILDINGS = {"character"}

_tech_steps: list[dict] = []


def expand_recursive(
    rng: random.Random,
    db: VanillaDB,
    patches: list[Patch],
    starter: StarterChain,
) -> None:
    global _tech_steps
    _tech_steps = []
    state = starter.state
    buildings_unlocked = len(state.unlocked_buildings)
    iterations_since_new = 0
    max_iterations = 120

    for _ in range(max_iterations):
        available = _get_available_categories(db, state)
        if not available:
            break

        category = _weighted_category_choice(rng, available, buildings_unlocked)
        if category is None:
            break

        element = _pick_element(rng, db, state, category)
        if element is None:
            iterations_since_new += 1
            if iterations_since_new > 10:
                break
            continue

        iterations_since_new = 0
        old_buildings = len(state.unlocked_buildings)
        old_recipes = len(state.recipes)

        _generate_for_element(rng, db, state, category, element)

        new_buildings = len(state.unlocked_buildings) - old_buildings
        new_recipes = len(state.recipes) - old_recipes
        if new_buildings > 0 or new_recipes > 0:
            buildings_unlocked = len(state.unlocked_buildings)


def steps() -> list[dict]:
    return _tech_steps


def recipes_to_seed() -> list[dict]:
    return []


def _get_available_categories(db: VanillaDB, state: ProgressionState) -> list[str]:
    available = []
    for cat in ("transformer", "extractor", "generator", "distribution"):
        if _has_undeployed_buildings(db, state, cat):
            available.append(cat)
    if _has_undeployed_weapons(db, state):
        available.append("combat")
    if _has_undeployed_science(db, state):
        available.append("science")
    return available


def _has_undeployed_buildings(
    db: VanillaDB, state: ProgressionState, functional_type: str
) -> bool:
    for b in db.buildings_of_type(functional_type):
        if b.name not in EXCLUDED_BUILDINGS and b.name not in state.unlocked_buildings:
            return True
    return False


def _has_undeployed_weapons(db: VanillaDB, state: ProgressionState) -> bool:
    return any(i.is_gun and i.name not in state.obtained_items for i in db.items.values())


def _has_undeployed_science(db: VanillaDB, state: ProgressionState) -> bool:
    return any(
        i.is_science_pack and i.name not in state.obtained_items for i in db.items.values()
    )


def _weighted_category_choice(
    rng: random.Random, categories: list[str], buildings_unlocked: int
) -> str | None:
    if not categories:
        return None
    weights = [
        CATEGORY_WEIGHTS.get(cat, 10) * (1 + buildings_unlocked * 0.1)
        for cat in categories
    ]
    return rng.choices(categories, weights=weights, k=1)[0]


def _pick_element(
    rng: random.Random, db: VanillaDB, state: ProgressionState, category: str
):
    if category in ("transformer", "extractor", "generator", "distribution"):
        candidates = [
            b for b in db.buildings_of_type(category)
            if b.name not in EXCLUDED_BUILDINGS and b.name not in state.unlocked_buildings
        ]
        return rng.choice(candidates) if candidates else None
    elif category == "combat":
        candidates = [i for i in db.items.values() if i.is_gun and i.name not in state.obtained_items]
        return rng.choice(candidates) if candidates else None
    elif category == "science":
        candidates = [i for i in db.items.values() if i.is_science_pack and i.name not in state.obtained_items]
        return rng.choice(candidates) if candidates else None
    return None


def _generate_for_element(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    category: str,
    element,
) -> None:
    from tool.generator.recipes import _unlock_building, _item_for_building

    step_id = f"randputf-{category}-{element.name}"
    step_recipes = []
    step_buildings = []
    step = {
        "id": step_id,
        "title": f"{category.title()}: {element.name}",
        "unlocks_recipes": [],
        "unlocks_buildings": [],
        "cost": [],
        "count": rng.randint(10, 30),
    }

    if category in ("transformer", "extractor", "generator", "distribution"):
        building = element
        item = _item_for_building(db, building.name)
        if item is not None:
            ensure_obtainable(rng, db, state, SLOT_ITEM, item.name)
        state.unlocked_buildings.add(building.name)
        step_buildings.append(building.name)

        num_recipes = rng.randint(1, 3)
        for _ in range(num_recipes):
            recipe = _make_recipe_for_building(rng, db, state, building)
            if recipe:
                step_recipes.append(recipe["name"])

    elif category == "combat":
        item = element
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name)
        step_recipes.append(item.name)

    elif category == "science":
        item = element
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name)
        step_recipes.append(item.name)
        step["cost"] = [{"type": "item", "name": item.name, "amount": rng.randint(5, 15)}]

    step["unlocks_recipes"] = step_recipes
    step["unlocks_buildings"] = step_buildings
    _tech_steps.append(step)


def _make_recipe_for_building(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
) -> dict | None:
    needs_fluid_out = building.fluid_outputs > 0
    product_kind = SLOT_FLUID if needs_fluid_out else SLOT_ITEM
    product_name = _pick_product(rng, db, state, product_kind)
    if product_name is None:
        return None
    try:
        recipe = make_recipe(rng, db, state, product_kind, product_name)
        return recipe
    except ValueError:
        return None


def _pick_product(
    rng: random.Random, db: VanillaDB, state: ProgressionState, kind: str
) -> str | None:
    if kind == SLOT_ITEM:
        candidates = [n for n in state.obtained_items if not n.startswith("randputf-")]
    else:
        candidates = list(state.obtained_fluids)
    return rng.choice(candidates) if candidates else None
