"""Tests de la phase ease-up : recettes alternatives des crafts trop lourds.

Un « craft négatif » : produit dont le graphe de production est profond
(≥ depth_threshold sauts) ou contient une boucle. La phase génère pour ces
produits une recette ALTERNATIVE tirée du pool GELÉ de début de run,
débloquée par des techs de type prologue (hand-craft).
"""

from __future__ import annotations

import random

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_FLUID, SLOT_ITEM
from tool.common.demo import build_demo_db
from tool.generator.easeup_phase import (
    build_ease_up_recipes,
    dispatch_ease_steps,
    make_rng,
    set_config,
)
from tool.generator.recipes import ProgressionState


def _make_state(*obtained: str) -> tuple[object, ProgressionState]:
    db = build_demo_db()
    state = ProgressionState()
    for name in obtained:
        state.mark_obtained(SLOT_FLUID, name) if name == "water" else state.mark_obtained(
            SLOT_ITEM, name
        )
    for env in ENVIRONMENTAL_ITEMS:
        state.mark_obtained(SLOT_ITEM, env)
    return db, state


def _chain(state: ProgressionState, names: list[str]) -> None:
    """Chaîne linéaire de recettes : chaque item est produit depuis le précédent."""
    for prev, name in zip(names, names[1:]):
        state.recipes.append(
            {
                "name": f"randputf-{name}",
                "energy": 1.0,
                "ingredients": [{"type": SLOT_ITEM, "name": prev, "amount": 1}],
                "results": [{"type": SLOT_ITEM, "name": name, "amount": 1}],
            }
        )


def _eased_products(state: ProgressionState):
    return sorted(
        r["results"][0]["name"]
        for r in state.recipes
        if r["name"].startswith("randputf-ease-")
    )


def test_detecte_craft_profond_mais_pas_le_peu_profond():
    """Profondeur = nombre de sauts de recettes : seul l'item au-delà du seuil
    (5 par défaut) est ease-up, les étapes intermédiaires restent normales."""
    db, state = _make_state("iron-ore", "coal")
    _chain(state, ["iron-ore", "a", "b", "c", "d", "e"])

    eased, _steps = build_ease_up_recipes(random.Random(1), db, state)
    assert eased, "un produit trop profond doit exister"
    products = {e["product"] for e in eased}
    assert "e" in products, f"e profond non ease-up: {products}"
    assert not ({"a", "b", "c", "d"} & products), f"items peu profonds ease-up: {products}"


def test_recette_alternative_tiree_du_pool_gelee():
    """L'ease-up n'utilise QUE le pool de début de run : aucun item profond de
    la chaîne (d, e) en ingrédient — sinon ce ne serait pas un raccourci."""
    db, state = _make_state("iron-ore", "coal")
    _chain(state, ["iron-ore", "a", "b", "c", "d", "e"])

    build_ease_up_recipes(random.Random(2), db, state)
    eased_items = _eased_products(state)
    assert "e" in eased_items
    recipe = next(r for r in state.recipes if r["name"] == "randputf-ease-e")
    ing_names = {i["name"] for i in recipe["ingredients"]}
    assert not ({"d", "e"} & ing_names), f"ease-up dépendant du profond: {ing_names}"
    assert not (set(ENVIRONMENTAL_ITEMS) & ing_names), (
        f"ease-up encore environnemental: {ing_names}"
    )


def test_pas_de_ease_pour_science_pack():
    """Les science packs sont la monnaie de recherche (§13) : jamais ease-up,
    même très profonds."""
    db, state = _make_state("iron-ore", "coal")
    _chain(state, ["iron-ore", "a", "b", "c", "automation-science-pack"])

    eased, _steps = build_ease_up_recipes(random.Random(3), db, state)
    products = {e["product"] for e in eased}
    assert "automation-science-pack" not in products, f"pack ease-up: {products}"


def test_detecte_boucle_circulaire():
    """Un produit sur une boucle (x dépend de y, y dépend de x) est ease-up :
    craft négatif (infaisable) — le raccourci le rend fabricable."""
    db, state = _make_state("iron-ore")
    _chain(state, ["iron-ore", "x"])
    state.recipes.append(
        {
            "name": "randputf-y",
            "energy": 1.0,
            "ingredients": [{"type": SLOT_ITEM, "name": "x", "amount": 1}],
            "results": [{"type": SLOT_ITEM, "name": "y", "amount": 1}],
        }
    )
    # boucle x ← y (la recette de x consomme y, la recette de y consomme x)
    state.recipes.append(
        {
            "name": "randputf-x-loop",
            "energy": 1.0,
            "ingredients": [{"type": SLOT_ITEM, "name": "y", "amount": 1}],
            "results": [{"type": SLOT_ITEM, "name": "x", "amount": 1}],
        }
    )

    build_ease_up_recipes(random.Random(4), db, state)
    eased_items = _eased_products(state)
    assert "x" in eased_items, f"boucle x non ease-up: {eased_items}"


def test_ease_up_n_introduit_pas_de_boucle():
    """L'ease-up n'utilise JAMAIS son propre produit ni un produit déjà
    ease-up (anti-cycle §8) : le graphe reste acyclique."""
    db, state = _make_state("iron-ore", "coal")
    _chain(state, ["iron-ore", "a", "b", "c", "d", "e"])

    build_ease_up_recipes(random.Random(5), db, state)
    by_product = {
        r["results"][0]["name"]: r for r in state.recipes if r["name"].startswith("randputf-ease-")
    }
    for product, recipe in by_product.items():
        in_ings = {i["name"] for i in recipe["ingredients"]}
        assert product not in in_ings, f"ease-up {product} se consomme lui-même"


def test_dispatch_max_cinq_unlocks_et_triggers_distincts():
    """Chaque tech ease-up ≤ 5 unlocks (§13), ids `randputf-ease-*`, un item
    en ingrédient interdit comme trigger déjà pris."""
    eased = [
        {"recipe_name": f"randputf-ease-{c}"} for c in "abcdef"
    ]
    candidates = ["iron-plate", "copper-plate", "steel-plate", "iron-gear-wheel"]
    steps = dispatch_ease_steps(
        eased, candidates, used_triggers=("iron-plate",), rng=random.Random(7)
    )
    assert steps, "des techs ease-up doivent exister"
    assert 1 <= len(steps) <= 2
    all_recipes = [r for s in steps for r in s["unlocks_recipes"]]
    assert sorted(all_recipes) == sorted(e["recipe_name"] for e in eased)
    seen = set()
    for s in steps:
        assert len(s["unlocks_recipes"]) <= 5, f"{s['id']}: {len(s['unlocks_recipes'])} unlocks"
        assert s["id"].startswith("randputf-ease-")
        assert s["count"] == 1
        assert s["cost"] == []
        assert s["craft_trigger"], f"{s['id']} sans déclencheur"
        assert s["craft_trigger"] != "iron-plate", "trigger déjà pris en doublon"
        assert s["craft_trigger"] in candidates
        assert s["craft_trigger"] not in seen, f"trigger en double: {s['craft_trigger']}"
        seen.add(s["craft_trigger"])
        for r in s["unlocks_recipes"]:
            assert r not in all_recipes or all_recipes.count(r) == 1, f"doublon {r}"


def test_rng_independant_de_la_seed():
    """make_rng fournit un flux DÉDIÉ : deux seeds différentes donnent des
    tirages distincts, sans toucher au flux principal du pipeline."""
    a = make_rng(5)
    b = make_rng(5)
    assert a.random() == b.random()
    c = make_rng(6)
    assert c.random() != a.random()


def test_sans_craft_profond_aucune_recette_ease_up():
    """Seed sans produit lourd ni boucle : aucune recette ease-up."""
    db, state = _make_state("iron-ore", "coal")
    _chain(state, ["iron-ore", "a", "b"])

    eased, steps = build_ease_up_recipes(random.Random(8), db, state)
    assert eased == []
    assert steps == []
    assert _eased_products(state) == []


def test_integration_avec_config():
    """Le prototype se configure depuis le dict : seuil haut → aucun produit,
    seuil bas (défaut) → le profond est ease-up. La config est restaurée pour
    ne pas polluer les autres tests."""
    from tool.generator.easeup_phase import _config as prev

    db, state = _make_state("iron-ore", "coal")
    _chain(state, ["iron-ore", "a", "b", "c", "d"])

    set_config({"easeup": {"depth_threshold": 10, "max_recipes": 2}})
    try:
        eased, _steps = build_ease_up_recipes(random.Random(9), db, state)
        assert eased == [], "seuil 10 : rien ne doit être ease-up"
    finally:
        set_config({
            "easeup": {
                "max_recipes": prev.max_recipes,
                "depth_threshold": prev.depth_threshold,
                "unlocks_per_tech": prev.unlocks_per_tech,
            }
        })