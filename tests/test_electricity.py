"""Tests de la phase électricité (README §10) et de l'assignation de
combustible aux bâtiments burner (§8, §9.3)."""

from __future__ import annotations

import random

from tool.common.db import SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.common.demo import build_demo_db
from tool.generator.electricity import resolve_electricity
from tool.generator.map_patches import Patch
from tool.generator.recipes import ProgressionState, _ensure_burner_fuel
from tool.generator.starter_chain import build_starter_chain


def make_patches(*specs) -> list[Patch]:
    return [Patch(kind, resource, 1000) for kind, resource in specs]


def test_burner_fuel_piece_parmi_tous_les_combustibles():
    """§10 : un bâtiment burner (qui consomme un combustible) reçoit un item
    combustible même s'il n'est pas encore obtenu — le créateur de recette
    s'occupe du reste."""
    rng = random.Random(3)
    db = build_demo_db()
    burner = db.buildings["stone-furnace"]  # energy_type == "burner"
    assert burner.energy_type == "burner"
    state = ProgressionState()
    for name in ("iron-ore", "copper-ore", "stone", "water"):
        state.mark_obtained(SLOT_FLUID if name == "water" else SLOT_ITEM, name)
    before = len(state.recipes)
    _ensure_burner_fuel(rng, db, state, burner)
    assert len(state.recipes) > before
    # Au moins une recette produit bien le combustible pioché.
    fuels = {
        r["results"][0]["name"] for r in state.recipes
        if r["results"][0]["type"] == SLOT_ITEM and db.items[r["results"][0]["name"]].fuel_value
    }
    assert fuels


def test_burner_fuel_ne_touche_pas_le_steam_engine():
    """§10 : un générateur à vapeur (steam-engine, energy_type electric) ne
    CONSOMME pas de combustible : il ne doit en recevoir aucun."""
    rng = random.Random(3)
    db = build_demo_db()
    steam = db.buildings["steam-engine"]
    assert steam.energy_type != "burner"
    state = ProgressionState()
    for name in ("iron-ore", "copper-ore", "stone", "water"):
        state.mark_obtained(SLOT_FLUID if name == "water" else SLOT_ITEM, name)
    before = len(state.recipes)
    _ensure_burner_fuel(rng, db, state, steam)
    assert len(state.recipes) == before


def test_burner_fuel_jamais_fluide_ni_chaine_fusee():
    """§10 : le combustible est TOUJOURS un item (jamais un fluide) et la
    chaîne fusée (dont rocket-fuel) est réservée à la fin de partie (§14)."""
    db = build_demo_db()
    burner = db.buildings["stone-furnace"]
    for _ in range(100):
        state = ProgressionState()
        for name in ("iron-ore", "copper-ore", "stone", "water"):
            state.mark_obtained(SLOT_FLUID if name == "water" else SLOT_ITEM, name)
        _ensure_burner_fuel(random.Random(1), db, state, burner)
        assert state.recipes  # un combustible a bien été créé
        for recipe in state.recipes:
            name = recipe["results"][0]["name"]
            assert name not in ("rocket-fuel", "processing-unit", "low-density-structure")


def test_burner_fuel_jeu_vide_ne_plante_pas():
    """§10 : aucun combustible dans le jeu (base vide) → `_ensure_burner_fuel`
    ne crée rien et ne plante pas."""
    db = VanillaDB()
    state = ProgressionState()
    _ensure_burner_fuel(random.Random(1), db, state, None)  # bâtiment absent
    assert not state.recipes


def test_electricite_declenche_generateur_et_pylone():
    """§10 : dès qu'un bâtiment électrique est débloqué, `resolve_electricity`
    débloque un générateur et un pylône sans planter."""
    rng = random.Random(21)
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("item", "iron-ore"), ("fluid", "water")))
    resolve_electricity(rng, db, chain)
    assert "steam-engine" in chain.state.unlocked_buildings
    for recipe in chain.state.recipes:
        assert recipe["results"]


def test_premier_generateur_craftable_a_la_main():
    """§10 : le générateur d'amorçage du réseau (débloqué par
    `resolve_electricity`) est craftable à la main : ingrédients 100% solides,
    AUCUNE catégorie ni atelier — jamais un assembling-machine-2 ou une usine
    chimique, qui exigeraient l'électricité que ce générateur doit amorcer
    (antibooucle bootstrap)."""
    rng = random.Random(21)
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("item", "iron-ore"), ("fluid", "water")))
    resolve_electricity(rng, db, chain)
    generator_recipes = [
        r for r in chain.state.recipes
        if r["results"] and r["results"][0]["name"] in ("steam-engine", "steam-turbine", "burner-generator")
    ]
    assert generator_recipes, "aucune recette de générateur créée"
    for recipe in generator_recipes:
        assert not recipe.get("category"), f"{recipe['name']} a une catégorie d'atelier"
        assert not recipe.get("crafted_in"), f"{recipe['name']} exige un atelier"
        for ing in recipe["ingredients"]:
            assert ing["type"] == SLOT_ITEM, f"{recipe['name']} consomme un fluide {ing}"
