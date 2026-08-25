"""Pipeline de génération d'une seed randputF.

Orchestre les phases décrites au README §6 à §13 et produit le dictionnaire
seed consommé par le mod (structure documentée dans exporters/mod_seed.py).
"""

from __future__ import annotations

from tool.common.db import VanillaDB
from tool.generator import electricity, map_patches, recursive_phase, starter_chain, tech_tree


def generate_seed(db: VanillaDB, config: dict | None = None) -> dict:
    """Génère une seed complète à partir de la base vanilla."""
    rng = map_patches.make_rng(db.seed_value)

    # Phase 1 : Ressources au sol
    patches = map_patches.generate_patches(rng, db, config or {})

    # Phase 2 : Chaîne initiale (starter)
    starter = starter_chain.build_starter_chain(rng, db, patches)

    # Phase 3 : Récursion pondérée
    recursive_phase.expand_recursive(rng, db, patches, starter)

    # Phase 4 : Électricité
    electricity.resolve_electricity(rng, db, starter)

    # Phase 5 : Arbre technologique (macro-steps uniquement)
    all_tech_steps = starter.tech_steps + recursive_phase.steps()
    technologies = tech_tree.build_linear_tech_tree(all_tech_steps)

    # Les techs du starter sont gratuites (count=1, cost=[] = pas de packs)
    starter.free_researches = [s["id"] for s in starter.tech_steps]

    # Assemblage de la seed
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
        "recipes": starter.recipes + recursive_phase.recipes_to_seed(),
        "technologies": technologies,
        "progression_order": [t["id"] for t in technologies],
    }
