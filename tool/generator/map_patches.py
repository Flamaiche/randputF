"""Phase 1 : ressources au sol (README §6).

IMPLEMENTE. Nombre de patchs tire entre 3 et 8 ; chaque patch recoit un type
parmi tous les items beltables ou tous les fluides pipables, sans contrainte
d'homogeneite ; richesse variable. Tirage SANS remise : chaque ressource
apparait au plus une fois (deux patchs de petroleum-gas sur la meme seed :
impossible).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tool.common.db import ENVIRONMENTAL_ITEMS, TOOL_LIKE_ITEMS, VanillaDB
from tool.generator.endgame_phase import ROCKET_CHAIN


@dataclass
class Patch:
    kind: str
    resource: str
    richness: int

    def to_seed(self) -> dict:
        return {"kind": self.kind, "resource": self.resource, "richness": self.richness}


def make_rng(seed_value: int) -> random.Random:
    return random.Random(f"randputF:{seed_value}")


def generate_patches(rng: random.Random, db: VanillaDB, config: dict) -> list[Patch]:
    map_cfg = config.get("map", {})
    low = int(map_cfg.get("patches_min", 3))
    high = int(map_cfg.get("patches_max", 8))
    count = rng.randint(max(1, low), max(1, high))

    item_candidates = [("item", i.name, tuple(map_cfg.get("richness_item", [50000, 300000])))
                       for i in _excludable_items(db)]
    fluid_candidates = [("fluid", f.name, tuple(map_cfg.get("richness_fluid", [100000, 600000])))
                        for f in db.pipable_fluids()]

    available_items = len(item_candidates)
    available_fluids = len(fluid_candidates)
    if available_items == 0 and available_fluids == 0:
        return []

    if item_candidates and fluid_candidates:
        type_roll = rng.random()
        if type_roll < 0.15:
            use_items, use_fluids = True, False
        elif type_roll < 0.30:
            use_items, use_fluids = False, True
        else:
            use_items, use_fluids = True, True
    elif item_candidates:
        use_items, use_fluids = True, False
    else:
        use_items, use_fluids = False, True

    if use_items and use_fluids:
        min_items = max(1, count // 2)
        min_fluids = max(1, count - min_items)
        n_items = rng.randint(min_items, max(min_items, count - 1))
        n_fluids = count - n_items
        n_items = min(n_items, available_items)
        n_fluids = min(n_fluids, available_fluids)
    elif use_items:
        n_items = min(count, available_items)
        n_fluids = 0
    else:
        n_items = 0
        n_fluids = min(count, available_fluids)

    patches = []
    for kind, resource, richness_bounds in rng.sample(item_candidates, n_items):
        patches.append(Patch(kind, resource, rng.randint(int(richness_bounds[0]), int(richness_bounds[1]))))
    for kind, resource, richness_bounds in rng.sample(fluid_candidates, n_fluids):
        patches.append(Patch(kind, resource, rng.randint(int(richness_bounds[0]), int(richness_bounds[1]))))

    rng.shuffle(patches)
    return patches


def _excludable_items(db: VanillaDB):
    excluded_types = {"combat"}
    # Les bâtiments de recherche (§8) ne sont jamais des patchs : leur recette
    # est une brique garantie du starter (2e recherche gratuite). Si un lab
    # tombait en ressource minière, il n'existerait pas de recette à débloquer.
    research = {
        i.name
        for i in db.items.values()
        if i.place_result is not None
        and db.buildings.get(i.place_result) is not None
        and db.buildings[i.place_result].functional_type == "research"
    }
    # Idem pour la chaîne fusée (§14) et le rocket-silo lui-même : la victoire
    # exige leurs recettes générées (unlockées par randputf-endgame-rocket).
    # Jamais un patch, sinon la phase endgame n'aurait aucune recette à créer.
    hero = set(ROCKET_CHAIN) | {"rocket-silo"}
    return [
        i for i in db.beltable_items()
        if i.subgroup not in excluded_types
        and not i.is_gun
        and i.name not in ENVIRONMENTAL_ITEMS
        and i.name not in research
        and i.name not in hero
        and i.name not in TOOL_LIKE_ITEMS
    ]
