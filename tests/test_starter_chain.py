"""Tests de la chaîne de départ (README §7) : kit, extraction, transformation,
transports, et partage d'état avec les phases suivantes."""

from __future__ import annotations

import random

from tool.common.db import SLOT_FLUID, SLOT_ITEM
from tool.common.demo import build_demo_db
from tool.generator.map_patches import Patch
from tool.generator.starter_chain import build_starter_chain
from tests.test_recipes import replay


def make_patches(*specs):
    return [Patch(kind, resource, 1000) for kind, resource in specs]


def test_kit_contient_arme_et_munitions():
    rng = random.Random(9)
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("item", "iron-ore")))
    names = {entry["name"] for entry in chain.kit}
    assert "pistol" in names
    assert "firearm-magazine" in names


def test_chaine_item_complete_et_valide():
    rng = random.Random(21)
    db = build_demo_db()
    patches = make_patches(
        ("item", "iron-ore"),
        ("item", "copper-ore"),
        ("fluid", "water"),
        ("fluid", "crude-oil"),
    )
    chain = build_starter_chain(rng, db, patches)
    replay(db, chain.state)

    targets = {r["results"][0]["name"] for r in chain.recipes}
    # extracteurs : un pour le sol + un pompage eau + un fluide profond
    assert any("mining-drill" in t or t == "offshore-pump" for t in targets)
    # transformation
    assert any("furnace" in t or "assembling" in t or "boiler" in t for t in targets)
    # transports item ET fluide
    assert any("belt" in t for t in targets)
    assert any("splitter" in t for t in targets)
    assert any("underground" in t for t in targets)
    assert any("pipe" in t for t in targets)


def test_extracteur_eau_pour_patch_water():
    rng = random.Random(4)
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("fluid", "water")))
    extract_steps = [s for s in chain.steps if s["type"] == "extract"]
    assert extract_steps[0]["extractor"] == "offshore-pump"


def test_state_partage_avec_phases_suivantes():
    rng = random.Random(77)
    db = build_demo_db()
    patches = make_patches(("item", "stone"), ("fluid", "lubricant"))
    chain = build_starter_chain(rng, db, patches)
    assert chain.state.obtained_items >= {"stone"}
    assert chain.state.obtained_fluids >= {"lubricant"}
    assert len(chain.state.unlocked_buildings) >= 2
    assert chain.buildings == sorted(chain.state.unlocked_buildings)
