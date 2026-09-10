"""Tests du prototype D : randomisation des quantités de craft.

Vérifie :
- déterminisme (même seed → même résultat) ;
- noms de recettes préservés ;
- aucun montant nul (amount_min garanti) ;
- mode symmetric : même facteur partout ;
- mode asymmetric : facteurs indépendants ;
- mode désactivé : aucune modification ;
- intégrité des noms d'ingrédients/sorties.
"""

from __future__ import annotations

import random

import pytest

from tool.prototypes.craft_quantity import (
    CraftQuantityConfig,
    Ingredient,
    RecipeSpec,
    randomise_all_quantities,
    randomise_recipe_quantities,
    verify_no_zero_amounts,
    verify_recipe_names_preserved,
)

SEEDS = (0, 5, 13, 42, 99)

RECIPES = [
    RecipeSpec(
        name="assembling-machine-1",
        ingredients=[Ingredient("iron-plate", 9), Ingredient("iron-gear-wheel", 5)],
        results=[Ingredient("assembling-machine-1", 1)],
    ),
    RecipeSpec(
        name="electronic-circuit",
        ingredients=[Ingredient("iron-plate", 1), Ingredient("copper-plate", 3)],
        results=[Ingredient("electronic-circuit", 1)],
    ),
    RecipeSpec(
        name="science-pack-1",
        ingredients=[Ingredient("copper-plate", 1), Ingredient("iron-gear-wheel", 1)],
        results=[Ingredient("science-pack-1", 1)],
    ),
]


# ── déterminisme ─────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_determinisme_symmetric(seed: int) -> None:
    rng1 = random.Random(seed)
    rng2 = random.Random(seed)
    cfg = CraftQuantityConfig(enabled=True, mode="symmetric")
    out1 = randomise_all_quantities(rng1, RECIPES, cfg)
    out2 = randomise_all_quantities(rng2, RECIPES, cfg)
    for a, b in zip(out1, out2):
        for ai, bi in zip(a.ingredients, b.ingredients):
            assert ai.amount == bi.amount


@pytest.mark.parametrize("seed", SEEDS)
def test_determinisme_asymmetric(seed: int) -> None:
    rng1 = random.Random(seed)
    rng2 = random.Random(seed)
    cfg = CraftQuantityConfig(enabled=True, mode="asymmetric")
    out1 = randomise_all_quantities(rng1, RECIPES, cfg)
    out2 = randomise_all_quantities(rng2, RECIPES, cfg)
    for a, b in zip(out1, out2):
        for ai, bi in zip(a.ingredients, b.ingredients):
            assert ai.amount == bi.amount


# ── noms préservés ───────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_noms_recettes_preserves(seed: int) -> None:
    rng = random.Random(seed)
    cfg = CraftQuantityConfig(enabled=True, mode="symmetric")
    out = randomise_all_quantities(rng, RECIPES, cfg)
    assert verify_recipe_names_preserved(out, RECIPES)


# ── aucun montant nul ────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_aucun_montant_nul(seed: int) -> None:
    rng = random.Random(seed)
    cfg = CraftQuantityConfig(enabled=True, mode="symmetric", amount_min=1)
    out = randomise_all_quantities(rng, RECIPES, cfg)
    bad = verify_no_zero_amounts(out, 1)
    assert not bad, f"recettes avec amount < 1 : {bad}"


@pytest.mark.parametrize("seed", SEEDS)
def test_aucun_montant_nul_asymmetric(seed: int) -> None:
    rng = random.Random(seed)
    cfg = CraftQuantityConfig(enabled=True, mode="asymmetric", amount_min=1)
    out = randomise_all_quantities(rng, RECIPES, cfg)
    bad = verify_no_zero_amounts(out, 1)
    assert not bad, f"recettes avec amount < 1 : {bad}"


# ── mode symmetric : même facteur partout ────────────────────────────

def test_symmetric_meme_facteur() -> None:
    """Dans le mode symmetric, TOUS les ingrédients d'une recette sont
    multipliés par le même facteur (arrondi int)."""
    rng = random.Random(42)
    cfg = CraftQuantityConfig(enabled=True, mode="symmetric")
    out = randomise_recipe_quantities(rng, RECIPES[0], cfg)
    # Le facteur est le même : le ratio entre deux amounts doit être
    # quasi identique (± arrondi) à celui de l'original.
    orig = RECIPES[0]
    if len(orig.ingredients) >= 2:
        ratio_orig = orig.ingredients[0].amount / orig.ingredients[1].amount
        ratio_new = out.ingredients[0].amount / out.ingredients[1].amount
        assert abs(ratio_orig - ratio_new) < 0.5, (
            f"symmetric : ratio devrait être conservé {ratio_orig} vs {ratio_new}"
        )


# ── mode asymmetric : facteurs indépendants ─────────────────────────

def test_asymmetric_facteurs_independants() -> None:
    """Dans le mode asymmetric, les ingrédients peuvent avoir des ratios
    très différents de l'original."""
    # On force des bornes larges pour maximiser la différence
    rng = random.Random(7)
    cfg = CraftQuantityConfig(enabled=True, mode="asymmetric", factor_min=0.5, factor_max=4.0)
    # Plusieurs runs pour avoir une chance d'obtenir des facteurs différents
    ratios = set()
    for seed in range(50):
        r = random.Random(seed)
        out = randomise_recipe_quantities(r, RECIPES[0], cfg)
        if len(out.ingredients) >= 2 and out.ingredients[1].amount > 0:
            ratios.add(out.ingredients[0].amount / out.ingredients[1].amount)
    # Au moins 3 ratios différents sur 50 tirages
    assert len(ratios) >= 3, f"trop peu de variation : {ratios}"


# ── mode désactivé ──────────────────────────────────────────────────

def test_desactive_sans_modification() -> None:
    rng = random.Random(999)
    cfg = CraftQuantityConfig(enabled=False)
    out = randomise_all_quantities(rng, RECIPES, cfg)
    for orig, modif in zip(RECIPES, out):
        for oi, mi in zip(orig.ingredients, modif.ingredients):
            assert mi.amount == oi.amount
        for orr, mr in zip(orig.results, modif.results):
            assert mr.amount == orr.amount


# ── intégrité des noms ──────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_integrite_noms_ingredients(seed: int) -> None:
    """Les noms d'ingrédients et de sorties ne changent jamais."""
    rng = random.Random(seed)
    cfg = CraftQuantityConfig(enabled=True, mode="asymmetric")
    out = randomise_all_quantities(rng, RECIPES, cfg)
    for orig, modif in zip(RECIPES, out):
        for oi, mi in zip(orig.ingredients, modif.ingredients):
            assert mi.name == oi.name
        for orr, mr in zip(orig.results, modif.results):
            assert mr.name == orr.name
