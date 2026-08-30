"""Tests de la phase endgame : chaîne de la fusée intable (§14)."""

from __future__ import annotations

import random

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_ITEM, ItemDef
from tool.common.demo import build_demo_db
from tool.generator.endgame_phase import ROCKET_CHAIN, ensure_rocket_chain
from tool.generator.map_patches import Patch
from tool.generator.starter_chain import build_starter_chain


def _db_with_rocket_items():
    db = build_demo_db()
    for item in ROCKET_CHAIN:
        db.items[item] = ItemDef(name=item, subgroup="intermediate-product")
    return db


def test_garantit_une_recette_par_ingredient_fusee():
    db = _db_with_rocket_items()
    chain = build_starter_chain(random.Random(1), db, [Patch("item", "coal", 1000)])

    steps = ensure_rocket_chain(random.Random(2), db, chain.state)

    assert steps, "une tech de fin d'arbre doit unlocker la fusée"
    step = steps[0]
    assert step["id"] == "randputf-endgame-rocket"
    produced = {r["results"][0]["name"] for r in chain.state.recipes}
    for item in ROCKET_CHAIN:
        assert item in produced, f"{item} doit avoir une recette générée"
        recipe = next(r for r in chain.state.recipes if r["results"][0]["name"] == item)
        env_ings = {
            i["name"] for i in recipe["ingredients"]
            if i["name"] in ENVIRONMENTAL_ITEMS
        }
        assert not env_ings, f"recette de fusée dépendante des environnementaux: {env_ings}"
    assert len(step["unlocks_recipes"]) == len(set(step["unlocks_recipes"]))


def test_pas_de_doublon_si_deja_obtenu():
    db = build_demo_db()
    chain = build_starter_chain(random.Random(3), db, [Patch("item", "coal", 1000)])
    before = len(chain.state.recipes)

    ensure_rocket_chain(random.Random(4), db, chain.state)
    after = len(chain.state.recipes)

    ensure_rocket_chain(random.Random(5), db, chain.state)
    assert len(chain.state.recipes) == after, "2e appel = idempotent"
    assert after >= before