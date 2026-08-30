"""Tests de la chaîne de départ (README §7) : kit, extraction, transformation,
transports, et partage d'état avec les phases suivantes."""

from __future__ import annotations

import random

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.common.demo import build_demo_db
from tool.generator.map_patches import Patch, generate_patches, make_rng
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


def test_pool_environnemental_disponible_des_le_depart():
    """Arbres/rochers/poissons (README §3, §6) : items obtenus dès le départ,
    avant tout patch — ils alimentent le pool d'ingrédients initial."""
    db = build_demo_db()
    chain = build_starter_chain(random.Random(1), db, make_patches(("fluid", "water")))
    assert set(chain.state.obtained_items) >= set(ENVIRONMENTAL_ITEMS)


def test_batiment_recherche_debloque():
    """§8 : le starter doit toujours garantir un bâtiment de type "recherche"
    (un lab) dès les techs gratuites."""
    db = build_demo_db()
    chain = build_starter_chain(random.Random(3), db, make_patches(("item", "iron-ore")))
    unlocked_research = {
        b.name for b in db.buildings.values()
        if b.functional_type == "research" and b.name in chain.state.unlocked_buildings
    }
    assert unlocked_research


def test_recherche_obligatoire_dans_2eme_research_gratuite():
    """§8 : la recette du bâtiment de recherche tombe dans la 2e recherche
    gratuite (starter-transformation), jamais dans la tech d'extraction."""
    db = build_demo_db()
    chain = build_starter_chain(
        random.Random(5),
        db,
        make_patches(("item", "iron-ore"), ("fluid", "water")),
    )
    assert len(chain.tech_steps) >= 2
    extraction, transformation = chain.tech_steps[:2]
    assert extraction["id"] == "randputf-starter-extraction"
    assert transformation["id"] == "randputf-starter-transformation"

    research_items = {
        i.name for i in db.items.values()
        if i.place_result
        and db.buildings.get(i.place_result)
        and db.buildings[i.place_result].functional_type == "research"
    }
    lab_recipes = {f"randputf-{item}" for item in research_items}
    assert not (set(extraction["unlocks_recipes"]) & lab_recipes)
    assert set(transformation["unlocks_recipes"]) & lab_recipes


def test_items_environnementaux_jamais_en_patch():
    """§6 : les ressources non automatisables (wood/stone/raw-fish) ne
    constituent jamais un patch, même sur de nombreuses générations."""
    db = build_demo_db()
    for seed in range(50):
        rng = make_rng(seed)
        patches = generate_patches(rng, db, {})
        resources = {p.resource for p in patches}
        assert not resources & set(ENVIRONMENTAL_ITEMS)


def test_patches_sans_ressource_dupliquee():
    """Chaque ressource apparait au plus une fois sur une seed (tirage sans
    remise) : deux patchs de petroleum-gas sont impossibles."""
    db = build_demo_db()
    for seed in range(50):
        rng = make_rng(seed)
        patches = generate_patches(rng, db, {})
        resources = [p.resource for p in patches]
        assert len(resources) == len(set(resources)), f"seed {seed}: {resources}"
