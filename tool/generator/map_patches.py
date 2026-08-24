"""Phase 1 : ressources au sol (README §6).

IMPLEMENTE. Nombre de patchs tire entre 3 et 8 ; chaque patch recoit un type
parmi tous les items beltables ou tous les fluides pipables, sans contrainte
d'homogeneite ; richesse variable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tool.common.db import VanillaDB


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

    candidates = [("item", i.name, tuple(map_cfg.get("richness_item", [50000, 300000])))
                  for i in _excludable_items(db)]
    candidates += [("fluid", f.name, tuple(map_cfg.get("richness_fluid", [100000, 600000])))
                   for f in db.pipable_fluids()]

    patches = []
    for _ in range(count):
        kind, resource, richness_bounds = rng.choice(candidates)
        patches.append(Patch(kind, resource, rng.randint(int(richness_bounds[0]), int(richness_bounds[1]))))
    return patches


def _excludable_items(db: VanillaDB):
    excluded_types = {"combat"}
    return [i for i in db.beltable_items() if i.subgroup not in excluded_types]
