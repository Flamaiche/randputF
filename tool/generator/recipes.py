"""Primitives partagees de creation de recettes (README §7 et §8).

Coeur du generateur : deux fonctions que toutes les phases consomment.

- make_recipe / _make_recipe : tire une recette pour un produit donne
  (ingredients pondere dans le pool deja valide, montants, batiment compatible).
- ensure_obtainable : garantit qu'un item ou un fluide est obtenable, en
  creant au besoin la recette qui le produit (et recursivement les
  intermediaires manquants, ex. le batiment de craft).

Anti-cycle §8 garanti par construction, sur DEUX axes :

1. Ingredients : tires EXCLUSIVEMENT dans le pool deja valide au moment de
   la creation (ressources au sol, kit, recettes enregistrees avant), jamais
   dans l'ensemble en cours de fabrication ; le produit est ajoute a sa
   propre liste interdite.
2. Batiments (crafted_in) : un bâtiment n'est utilisable comme atelier qu'une
   fois son item obtenable resolu (deblockage sequentiel : item d'abord,
   inscription ensuite). Un garde ``pending`` detecte toute reentrance sur
   un produit deja en cours de resolution, ce qui rend impossible tout
   cycle du type chaudiere -> assembleur -> chaudiere.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.common.db import SLOT_FLUID, SLOT_ITEM, VanillaDB

INGREDIENT_COUNTS = [(1, 3), (2, 5), (3, 2)]
RESULT_AMOUNTS = [(1, 7), (2, 3)]
RECIPE_ENERGIES = [0.5, 1.0, 2.0]


@dataclass
class ProgressionState:
    """Etat de progression partage par toutes les phases du pipeline."""

    obtained_items: set[str] = field(default_factory=set)
    obtained_fluids: set[str] = field(default_factory=set)
    unlocked_buildings: set[str] = field(default_factory=set)
    recipes: list[dict] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    pending: set[str] = field(default_factory=set)

    def is_obtained(self, kind: str, name: str) -> bool:
        if kind == SLOT_ITEM:
            return name in self.obtained_items
        return name in self.obtained_fluids

    def mark_obtained(self, kind: str, name: str) -> None:
        if kind == SLOT_ITEM:
            self.obtained_items.add(name)
        else:
            self.obtained_fluids.add(name)

    def pool(self) -> list[tuple[str, str]]:
        return [(SLOT_ITEM, n) for n in sorted(self.obtained_items)] + [
            (SLOT_FLUID, n) for n in sorted(self.obtained_fluids)
        ]


def ensure_obtainable(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    kind: str,
    name: str,
    forbidden: frozenset[str] = frozenset(),
    exclude_buildings: frozenset[str] = frozenset(),
) -> None:
    """Garantit que ``name`` est produisible, en creant sa recette si besoin."""
    if state.is_obtained(kind, name):
        return
    key = f"{kind}:{name}"
    if key in state.pending:
        raise ValueError(f"dépendance circulaire détectée sur {key}")
    state.pending.add(key)
    try:
        recipe = _make_recipe(rng, db, state, kind, name, forbidden | {name}, exclude_buildings)
        state.recipes.append(recipe)
        state.mark_obtained(kind, name)
    finally:
        state.pending.discard(key)
    state.steps.append(
        {
            "type": "craft",
            "target": {"type": kind, "name": name},
            "recipe": recipe["name"],
            "crafted_in": recipe.get("crafted_in"),
        }
    )


def make_recipe(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    product_kind: str,
    product_name: str,
    forbidden: frozenset[str] = frozenset(),
) -> dict:
    """Tire et enregistre une recette pour ``product_name``, puis le marque obtenu."""
    key = f"{product_kind}:{product_name}"
    if key in state.pending:
        raise ValueError(f"dépendance circulaire détectée sur {key}")
    state.pending.add(key)
    try:
        recipe = _make_recipe(rng, db, state, product_kind, product_name, forbidden | {product_name})
    finally:
        state.pending.discard(key)
    state.recipes.append(recipe)
    state.mark_obtained(product_kind, product_name)
    return recipe


def _make_recipe(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    product_kind: str,
    product_name: str,
    forbidden: frozenset[str],
    exclude_buildings: frozenset[str] = frozenset(),
) -> dict:
    eligible = [entry for entry in state.pool() if entry[1] not in forbidden]
    if not eligible:
        raise ValueError(
            f"pool vide pour produire {product_kind} {product_name} : "
            "aucune branche valide disponible"
        )

    max_ingredients = min(_weighted_choice(rng, INGREDIENT_COUNTS), len(eligible))
    ingredients = rng.sample(eligible, max_ingredients)

    n_fluid_ing = sum(1 for k, _ in ingredients if k == SLOT_FLUID)
    n_item_ing = len(ingredients) - n_fluid_ing
    needs_fluid_out = product_kind == SLOT_FLUID
    building = _pick_building(
        rng, db, state, n_item_ing, n_fluid_ing, needs_fluid_out, product_name, exclude_buildings
    )

    recipe = {
        "name": f"randputf-{product_name}",
        "energy": float(rng.choice(RECIPE_ENERGIES)),
        "ingredients": [
            {"type": kind, "name": name, "amount": rng.randint(1, 4)}
            for kind, name in ingredients
        ],
        "results": [
            {"type": product_kind, "name": product_name, "amount": _weighted_choice(rng, RESULT_AMOUNTS)}
        ],
    }
    if building is None:
        # Bootstrap a la main (dernier recours, cf. four de pierre vanilla) :
        # recette sans categorie ni atelier, fabricable dans l'inventaire.
        return recipe
    recipe["category"] = building.functional_type
    recipe["crafted_in"] = building.name
    return recipe


def _weighted_choice(rng: random.Random, weighted: list[tuple[int, int]]) -> int:
    values, weights = zip(*weighted)
    return rng.choices(values, weights=weights, k=1)[0]


def _pick_building(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    n_item_ing: int,
    n_fluid_ing: int,
    needs_fluid_out: bool,
    product_name: str,
    exclude_buildings: frozenset[str],
):
    def fits(b) -> bool:
        return (
            b.item_input_slots >= n_item_ing
            and b.fluid_inputs >= n_fluid_ing
            and (not needs_fluid_out or b.fluid_outputs >= 1)
        )

    def blocked(b) -> bool:
        item = _item_for_building(db, b.name)
        return item is not None and f"{SLOT_ITEM}:{item.name}" in state.pending

    candidates = [
        b
        for b in db.buildings.values()
        if b.name in state.unlocked_buildings and b.name not in exclude_buildings and fits(b)
    ]
    if candidates:
        return rng.choice(candidates)

    candidates = [
        b
        for b in db.buildings.values()
        if b.name not in exclude_buildings and fits(b) and not blocked(b)
    ]
    if not candidates:
        # Aucun atelier possible sans boucler : la recette sera fabriquee a
        # la main (bootstrap). C'est le seul chemin de terminaison.
        return None
    building = rng.choice(candidates)
    _unlock_building(rng, db, state, building, product_name)
    return building


def _unlock_building(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
    requester: str,
) -> None:
    """Debloque un bâtiment : son item est resolu AVANT son inscription.

    L'ordre garantit qu'aucune recette ne peut jamais avoir pour atelier un
    bâtiment dont l'item depend (directement ou indirectement) d'elle-meme.
    """
    item = _item_for_building(db, building.name)
    if item is not None:
        ensure_obtainable(
            rng,
            db,
            state,
            SLOT_ITEM,
            item.name,
            frozenset({item.name, requester}),
            exclude_buildings=frozenset({building.name}),
        )
    state.unlocked_buildings.add(building.name)


def _item_for_building(db: VanillaDB, entity_name: str):
    return next((i for i in db.items.values() if i.place_result == entity_name), None)
