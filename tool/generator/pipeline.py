"""Pipeline de generation d'une seed randputF.

Orchestre les phases decrites au README §6 a §13 et produit le dictionnaire
seed consomme par le mod (structure documentee dans exporters/mod_seed.py).

Les fonctions marquées NOT_IMPLEMENTED sont les points de logique à écrire
ensemble : chaque contrat y est decrit precisement.
"""

from __future__ import annotations

from tool.common.db import VanillaDB
from tool.generator import electricity, map_patches, recursive_phase, starter_chain, tech_tree


def generate_seed(db: VanillaDB, config: dict | None = None) -> dict:
    rng = map_patches.make_rng(db.seed_value)

    patches = map_patches.generate_patches(rng, db, config or {})
    starter = starter_chain.build_starter_chain(rng, db, patches)
    recursive_phase.expand_recursive(rng, db, patches, starter)
    electricity.resolve_electricity(rng, db, starter)
    technologies = tech_tree.build_linear_tech_tree(starter.steps + recursive_phase.steps())

    return {
        "meta": {
            "seed": db.seed_value,
            "generator_version": "0.1.0",
            "factorio_version": "2.0",
        },
        "pools": {
            "item_resources": sorted(i.name for i in db.beltable_items()),
            "fluid_resources": sorted(f.name for f in db.pipable_fluids()),
        },
        "map": {"patches": [p.to_seed() for p in patches]},
        "starter_kit": starter.kit,
        "free_researches": starter.free_researches,
        "recipes": recursive_phase.recipes_to_seed(),
        "technologies": technologies,
        "progression_order": [t["id"] for t in technologies],
    }
