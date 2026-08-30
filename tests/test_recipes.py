"""Tests des primitives de recettes : anti-cycle §8 (ingredients + crafted_in).

Le replay rejoue les recettes dans l'ordre de creation et verifie qu'au
moment de chaque creation, ses ingredients ET son atelier etaient deja
valides : c'est l'invariant de solvabilite que le validateur re-verifiera
plus tard sur la seed complete.
"""

from __future__ import annotations

import random

import pytest

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.common.demo import build_demo_db
from tool.generator.recipes import (
    ProgressionState,
    _has_production_item,
    _sample_items_weighed,
    ensure_obtainable,
    make_recipe,
)


def make_state(*raw_items: str) -> tuple[VanillaDB, ProgressionState]:
    db = build_demo_db()
    state = ProgressionState()
    for name in raw_items or ("iron-ore", "copper-ore", "stone", "coal"):
        state.mark_obtained(SLOT_FLUID if name == "water" else SLOT_ITEM, name)
    return db, state


def replay(db: VanillaDB, state: ProgressionState) -> None:
    valid = set(state.pool())
    available_buildings: set[str] = set()
    for index, recipe in enumerate(state.recipes):
        product = recipe["results"][0]
        for ing in recipe["ingredients"]:
            assert (ing["type"], ing["name"]) in valid, (
                f"{recipe['name']} : ingredient {ing['name']} pas encore valide"
            )
        crafted_in = recipe.get("crafted_in")
        if crafted_in is not None:
            assert crafted_in in available_buildings, (
                f"{recipe['name']} : atelier {crafted_in} pas encore debloque"
            )
        valid.add((product["type"], product["name"]))
        if product["type"] == SLOT_ITEM:
            entity = next(
                (i.place_result for i in db.items.values() if i.name == product["name"]),
                None,
            )
            if entity is not None:
                available_buildings.add(entity)


def test_chain_topologiquement_valide():
    rng = random.Random(42)
    db, state = make_state()
    for target in ("iron-plate", "iron-gear-wheel", "electronic-circuit"):
        ensure_obtainable(rng, db, state, SLOT_ITEM, target)
    replay(db, state)


def test_produit_jamais_son_propre_ingredient():
    rng = random.Random(7)
    db, state = make_state()
    ensure_obtainable(rng, db, state, SLOT_ITEM, "steel-plate")
    for recipe in state.recipes:
        names = {i["name"] for i in recipe["ingredients"]}
        assert recipe["results"][0]["name"] not in names


def test_ensure_obtainable_idempotent():
    rng = random.Random(1)
    db, state = make_state()
    ensure_obtainable(rng, db, state, SLOT_ITEM, "pipe")
    ensure_obtainable(rng, db, state, SLOT_ITEM, "pipe")
    assert len([r for r in state.recipes if r["results"][0]["name"] == "pipe"]) == 1


def test_atelier_jamais_lui_meme_ni_cycle():
    """Produire un fluide force le deblocage d'un bâtiment a sortie fluide ;
    la chaine crafted_in ne doit jamais reboucler sur elle-meme."""
    rng = random.Random(3)
    db, state = make_state("iron-ore", "water")
    ensure_obtainable(rng, db, state, SLOT_FLUID, "lubricant")
    replay(db, state)
    by_product = {r["results"][0]["name"]: r for r in state.recipes}
    for recipe in state.recipes:
        crafted_in = recipe.get("crafted_in")
        item = next((i for i in db.items.values() if i.place_result == crafted_in), None)
        if item is not None and item.name in by_product:
            assert by_product[item.name] is not recipe


def test_pool_vide_leve_erreur():
    rng = random.Random(5)
    db, state = make_state()
    state.obtained_items.clear()
    with pytest.raises(ValueError, match="pool vide"):
        make_recipe(rng, db, state, SLOT_ITEM, "iron-plate")


def test_dependance_circulaire_detectee():
    """La reentrance sur un produit deja en cours de resolution est refusee."""
    rng = random.Random(11)
    db, state = make_state()
    state.pending.add(f"{SLOT_ITEM}:iron-plate")
    with pytest.raises(ValueError, match="circulaire"):
        ensure_obtainable(rng, db, state, SLOT_ITEM, "iron-plate")


def test_cold_start_environnemental_sans_patch_item():
    """Sans item de production (seed 100% fluides), les ressources
    environnementales (arbres/rochers/poissons) sont LA matière première :
    priorité dans le tirage, en petite quantité."""
    db, state = make_state("water")  # aucun patch item, juste l'eau
    for item in ENVIRONMENTAL_ITEMS:
        state.mark_obtained(SLOT_ITEM, item)
    assert _has_production_item(db, state) is False

    rng = random.Random(4)
    eligible = [(SLOT_ITEM, n) for n in state.obtained_items]
    picked = _sample_items_weighed(rng, db, eligible, 2, state)
    assert all(name in ENVIRONMENTAL_ITEMS for name in {n for _, n in picked})


def test_environnemental_rare_des_qu_item_de_production_existe():
    """Dès qu'un patch item ou un item fabriqué existe, les items
    environnementaux ne sont plus prioritaires : poids faible."""
    db, state = make_state("iron-ore", "water")  # patch item présent
    for item in ENVIRONMENTAL_ITEMS:
        state.mark_obtained(SLOT_ITEM, item)
    assert _has_production_item(db, state) is True

    rng = random.Random(4)
    eligible = [(SLOT_ITEM, n) for n in state.obtained_items]
    picked = _sample_items_weighed(rng, db, eligible, 2, state)
    assert not all(name in ENVIRONMENTAL_ITEMS for name in {n for _, n in picked})


def test_extracteurs_se_craftent_uniquement_avec_des_items():
    """Anti-cycle §8 : la recette d'un extracteur (perceuse, pumpjack, pompe
    offshore) n'utilise jamais de fluide comme ingrédient — surtout pas celui
    qu'il sert à extraire."""
    db = build_demo_db()
    extractor_items = {
        i.name for i in db.items.values()
        if i.place_result and db.buildings.get(i.place_result) is not None
        and db.buildings[i.place_result].functional_type == "extractor"
    }
    assert extractor_items  # la démo doit en contenir
    for target in extractor_items:
        state = ProgressionState()
        for name in ("iron-ore", "copper-ore", "stone", "coal", "water"):
            state.mark_obtained(SLOT_FLUID if name == "water" else SLOT_ITEM, name)
        for env in ENVIRONMENTAL_ITEMS:
            state.mark_obtained(SLOT_ITEM, env)
        rng = random.Random(abs(hash(target)) % 99991)
        ensure_obtainable(rng, db, state, SLOT_ITEM, target)
        recipe = next(r for r in state.recipes if r["results"][0]["name"] == target)
        fluid_ings = [i for i in recipe["ingredients"] if i["type"] == SLOT_FLUID]
        assert not fluid_ings, f"{recipe['name']} utilise un fluide: {fluid_ings}"
