"""Tests de l'assignation de fluides aux bâtiments à comportement fixe (§6/§10).

Vérifie que :
- les steam-generators (turbine, steam-engine) reçoivent un fluide obtainable (lac) ;
- les transformateurs à recette fixe (boiler, heat-exchanger) reçoivent input + output ;
- aucun doublon (un même fluide n'est pas assigné deux fois en input) ;
- la seed contient building_fluid_assignments ;
- rien n'est codé en dur (détection par capacités, pas par nom) ;
- les fabricateurs à recette fixe à SORTIE ITEM (équivalents de mods) reçoivent
  une recette randomisée item, sans toucher à l'assignation fluide (réservée
  aux fabricateurs fluide, boiler/heat-exchanger)."""

from __future__ import annotations

import random

import pytest

from tool.common.demo import build_demo_db
from tool.generator.building_fluids import assign_building_fluids
from tool.generator.recipes import ProgressionState, _is_fixed_recipe_transformer


def test_steam_engine_recoit_un_fluide_du_lac():
    """Un steam-engine (générateur à vapeur, fluid_inputs > 0) non encore
    débloqué reçoit un fluide assigné parmi les lacs de la seed."""
    rng = random.Random(42)
    db = build_demo_db()
    state = ProgressionState()
    # steam-engine PAS dans unlocked_buildings (pas encore débloqué par electricity)
    lake_res = {"water", "crude-oil"}
    result = assign_building_fluids(rng, db, state, lake_res)
    assert "steam-engine" in result
    assert "input" in result["steam-engine"]
    assert result["steam-engine"]["input"] in lake_res


def test_boiler_recoit_input_et_output():
    """Un boiler (transformateur à recette fixe, fluid_inputs > 0,
    fluid_outputs > 0, pas de crafting_categories valides) reçoit
    input + output distincts."""
    rng = random.Random(42)
    db = build_demo_db()
    state = ProgressionState()
    # boiler PAS dans unlocked_buildings
    lake_res = {"water", "crude-oil"}
    result = assign_building_fluids(rng, db, state, lake_res)
    assert "boiler" in result
    assert "input" in result["boiler"]
    assert "output" in result["boiler"]
    assert result["boiler"]["input"] in lake_res
    assert result["boiler"]["output"] in lake_res
    assert result["boiler"]["input"] != result["boiler"]["output"]


def test_pas_de_doublon_fluide_input():
    """Un même fluide n'est JAMAIS assigné comme input à deux bâtiments
    différents (anti-doublon)."""
    rng = random.Random(42)
    db = build_demo_db()
    state = ProgressionState()
    lake_res = {"water"}
    result = assign_building_fluids(rng, db, state, lake_res)
    inputs = [v["input"] for v in result.values() if "input" in v]
    # Avec un seul lac, les deux ne peuvent pas avoir un input distinct —
    # seul le premier recevra un input, le second sera ignoré.
    assert len(inputs) == len(set(inputs))


def test_fluide_assigne_dans_la_seed():
    """La seed contient building_fluid_assignments avec les bons champs."""
    from tool.generator.pipeline import generate_seed

    seed = generate_seed(build_demo_db(), {"map": {"patches_min": 2, "patches_max": 3}}, validate=False)
    bfa = seed.get("building_fluid_assignments", {})
    assert isinstance(bfa, dict)
    # Au moins un bâtiment doit avoir reçu un fluide
    for name, assignment in bfa.items():
        assert "input" in assignment, f"{name} n'a pas de champ 'input'"


def test_is_fixed_recipe_transformer_demo_boiler():
    """Le boiler du demo est bien détecté comme transformateur à recette fixe."""
    db = build_demo_db()
    boiler = db.buildings["boiler"]
    assert _is_fixed_recipe_transformer(boiler)


def test_rien_nest_code_en_dur_detection():
    """La détection des steam-generators et fixed-recipe-transformers repose
    sur les CAPACITÉS (fluid_inputs, fluid_outputs, tags is_generator /
    produces_electricity, crafting_categories), jamais sur une liste de noms.
    On vérifie qu'un bâtiment fictif avec les bonnes capacités est correctement
    détecté."""
    db = build_demo_db()
    # Ajouter un bâtiment fictif "fake-turbine" avec les mêmes capacités
    # qu'un steam-engine
    from tool.common.db import BuildingDef
    db.buildings["fake-turbine"] = BuildingDef(
        name="fake-turbine",
        entity_type="generator",
        is_generator=True,
        produces_electricity=True,
        fluid_inputs=1,
        fluid_outputs=0,
        energy_type="electric",
    )
    state = ProgressionState()
    rng = random.Random(42)
    result = assign_building_fluids(rng, db, state, {"water"})
    assert "fake-turbine" in result
    assert result["fake-turbine"]["input"] == "water"


def test_sans_lac_aucune_assignation():
    """Sans lacs (lake_resources vide), aucune assignation n'est faite."""
    rng = random.Random(42)
    db = build_demo_db()
    state = ProgressionState()
    result = assign_building_fluids(rng, db, state, set())
    assert result == {}


def test_tag_large_devoile_toutes_les_machines_a_recette_fixe():
    """§10 + IDEES C7 : ``has_hidden_recipe`` dévoile les bâtiments « qui ont
    une recette cachée » = une VRAIE recette (entrée item/fluide/combustible ET
    sortie item/fluide, y compris les résidus de combustion ``fuel_residues``)
    non accessible comme recette de craft. En vanilla : boiler + heat-exchanger
    (fluide → fluide) ET nuclear-reactor (item quelconque en pseudo-combustible
    → item résidu). Les autres générateurs/extracteurs/lab (soleil/combustible
    → électricité, champ → ressource, packs → recherche) n'ont PAS de sortie
    item/fluide → ce n'est pas une recette cachée, c'est de la mécanique
    moteur (jamais taggés)."""
    import json
    from pathlib import Path

    from tool.common.db import has_hidden_recipe
    from tool.parsers.vanilla import load_db_from_dump

    db = load_db_from_dump(json.loads(
        (Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()
    ))
    tagged = {b.name for b in db.buildings.values() if has_hidden_recipe(b)}
    assert tagged == {"boiler", "heat-exchanger", "nuclear-reactor"}
    # Mécanique moteur = jamais une recette cachée (entrée OU sortie absente) :
    # le réacteur, lui, a une SORTIE item (résidu de combustion) → taggé.
    for name in ("solar-panel", "steam-engine", "steam-turbine",
                 "burner-generator", "lab",
                 "burner-mining-drill", "electric-mining-drill",
                 "offshore-pump", "pumpjack"):
        assert not has_hidden_recipe(db.buildings[name]), name


def test_reacteur_entree_combustible_residu_est_la_sortie():
    """Le réacteur a une entrée ET une sortie : entrée = combustible
    (``fuel_categories``), sortie ITEM = le RÉSIDU du combustible brûlé
    (``burnt_result``) : uranium-fuel-cell → depleted-uranium-fuel-cell. La
    chaleur (``produces_heat``) est une sortie « spéciale » stockée à part
    (traitée plus tard, comme l'électricité). Comme il a entrée + sortie item,
    il est taggé ``has_hidden_recipe`` (recette cachée), mais reste un
    générateur : jamais d'atelier. Correspondance PAR CATÉGORIE de fuel, rien
    en dur : le charbon (chemical) n'est pas combustible du réacteur."""
    import json
    from pathlib import Path

    from tool.common.db import has_hidden_recipe
    from tool.parsers.vanilla import load_db_from_dump

    db = load_db_from_dump(json.loads(
        (Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()
    ))
    reactor = db.buildings["nuclear-reactor"]
    assert reactor.fuel_categories == ("nuclear",)   # entrée : combustible
    assert reactor.produces_heat                      # sortie spéciale : chaleur

    # Sortie item du réacteur = résidu de ses combustibles (burned → item).
    assert db.fuels_for(reactor) == [db.items["uranium-fuel-cell"]]
    assert db.fuel_residues(reactor) == {"depleted-uranium-fuel-cell"}
    assert db.fuel_residues(db.buildings["burner-generator"]) == frozenset()
    # Vue NORMALISÉE (générique) : le réacteur = machine item → item (un item
    # quelconque en pseudo-combustible → un item en résidu), sans aucune
    # référence à « nuclear » — plus malléable pour la suite.
    assert db.has_fuel_item_flow(reactor)
    assert db.fuel_item_flow(reactor)["input"] == "item"
    assert db.fuel_item_flow(reactor)["outputs"] == {"depleted-uranium-fuel-cell"}
    assert not db.has_fuel_item_flow(db.buildings["burner-generator"])
    # Le réacteur est une vraie RECETTE CACHÉE (entrée item + sortie item
    # résidu) → taggé ``has_hidden_recipe``, comme boiler/heat-exchanger. Mais
    # il reste un GÉNÉRATEUR : jamais d'atelier, aucun fake crafted_in
    # (``is_fixed_crafter`` est restreint aux transformateurs).
    assert has_hidden_recipe(reactor)


def test_reacteur_hors_electricite_vrais_producteurs_dedans():
    """TAG ``produces_electricity`` (PAR CAPACITÉS, aucune liste de noms) : les
    vrais producteurs de courant (steam-engine, turbine, burner-generator,
    solar-panel) en font partie ; le réacteur NO — il produit de la chaleur
    (``produces_heat``), pas du courant. L'électricité §10 ne démarre donc
    jamais le réseau avec le réacteur."""
    import json
    from pathlib import Path

    from tool.parsers.vanilla import load_db_from_dump

    db = load_db_from_dump(json.loads(
        (Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()
    ))
    electric = {b.name for b in db.buildings.values() if b.produces_electricity}
    assert electric == {"steam-engine", "steam-turbine", "burner-generator", "solar-panel"}
    assert not db.buildings["nuclear-reactor"].produces_electricity
    assert db.buildings["nuclear-reactor"].produces_heat


def test_tag_etroit_fluide_seulement_boiler_et_heat_exchanger():
    """Seuls les fabricateurs FLUIDE à recette fixe (boiler, heat-exchanger :
    transformer, entrée ET sortie fluide) reçoivent une recette randomisée.
    Les générateurs/extracteurs/lab, pourtant taggés, gardent leur comportement
    figé — ils ne doivent pas passer par `_make_fixed_recipe_for_crafter`."""
    import json
    from pathlib import Path

    from tool.common.db import is_fixed_fluid_crafter
    from tool.parsers.vanilla import load_db_from_dump

    db = load_db_from_dump(json.loads(
        (Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()
    ))
    fluid = {b.name for b in db.buildings.values() if is_fixed_fluid_crafter(b)}
    assert fluid == {"boiler", "heat-exchanger"}


def _make_item_fixed_transformer(db) -> "BuildingDef":
    """Un transformateur à recette fixe à SORTIE ITEM (équivalent fourni par un
    mod) : même tag que le boiler mais sort physique item — jamais présent en
    vanilla, testé via un bâtiment synthétique."""
    from tool.common.db import BuildingDef

    crafter = BuildingDef(
        name="fake-item-fabricator",
        entity_type="assembling-machine",
        is_crafter=True,
        crafting_categories=(),
        item_input_slots=2,
        fluid_inputs=0,
        fluid_outputs=0,
        item_output_slots=1,
        energy_type="burner",
    )
    db.buildings[crafter.name] = crafter
    return crafter


def test_reacteur_est_routé_vers_recette_item():
    """SUJETRATION IDEES C7 étendue : le réacteur nucléaire (recette cachée
    item → item via ses résidus de combustion ``fuel_residues``) est désormais
    un ``is_fixed_crafter`` : il reçoit une recette UNIQUE randomisée dont la
    SORTIE est son résidu (depleted-uranium-fuel-cell), crafted_in = le
    réacteur. Il n'est plus « dévoilé sans rôle » : il est routé comme un
    fabricateur à recette fixe item → item."""
    import json
    from pathlib import Path

    from tool.common.db import is_fixed_crafter
    from tool.generator.recursive_phase import _make_fixed_recipe_for_crafter
    from tool.parsers.vanilla import load_db_from_dump

    db = load_db_from_dump(json.loads(
        (Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()
    ))
    reactor = db.buildings["nuclear-reactor"]
    assert is_fixed_crafter(reactor)
    # La recette héberge le résidu de combustion comme SORTIE item.
    state = ProgressionState()
    state.obtained_items = {"iron-plate", "copper-plate", "steel-plate"}
    rng = random.Random(7)
    recipe = _make_fixed_recipe_for_crafter(rng, db, state, reactor)
    assert recipe["results"][0]["type"] == "item"
    assert recipe["results"][0]["name"] == "depleted-uranium-fuel-cell"
    assert recipe["crafted_in"] == "nuclear-reactor"
    assert recipe["name"] == "randputf-nuclear-reactor-depleted-uranium-fuel-cell"
    # Ingrédients 100% items déjà obtenus, jamais l'output (anti-boucle).
    assert all(ing["type"] == "item" and ing["name"] in state.obtained_items
               and ing["name"] != "depleted-uranium-fuel-cell"
               for ing in recipe["ingredients"])
    assert recipe in state.recipes


def test_is_fixed_crafter_couvre_item_et_fluide():
    """``is_fixed_crafter`` couvre les fabricateurs à recette fixe à sortie
    FLUIDE (boiler/heat-exchanger) ET à sortie ITEM (mod), alors que
    ``is_fixed_fluid_crafter`` (pairing C7, filters de fluid boxes) n'est vrai
    que pour la variante fluide."""
    from tool.common.db import is_fixed_crafter, is_fixed_fluid_crafter

    db = build_demo_db()
    assert is_fixed_crafter(db.buildings["boiler"])
    assert is_fixed_fluid_crafter(db.buildings["boiler"])
    item_crafter = _make_item_fixed_transformer(db)
    assert is_fixed_crafter(item_crafter)
    assert not is_fixed_fluid_crafter(item_crafter)


def test_recette_fixe_sortie_item_assignee_au_batiment():
    """Un fabricateur à recette fixe à sortie item (mod) reçoit une recette
    UNIQUE randomisée : output item NON encore produit, ingrédients déjà
    obtenus (items + éventuellement fluide), crafted_in = CE bâtiment, nom de
    recette unique randputf-<bâtiment>-<item>."""
    from tool.generator.recursive_phase import _make_fixed_recipe_for_crafter

    rng = random.Random(42)
    db = build_demo_db()
    item_crafter = _make_item_fixed_transformer(db)
    state = ProgressionState()
    state.obtained_items = {"wood", "stone", "iron-plate", "copper-plate"}
    state.obtained_fluids = {"water"}

    recipe = _make_fixed_recipe_for_crafter(rng, db, state, item_crafter)

    assert recipe["results"][0]["type"] == "item"
    out = recipe["results"][0]["name"]
    assert out in {"iron-plate", "copper-plate"}
    assert recipe["name"] == f"randputf-{item_crafter.name}-{out}"
    assert recipe["crafted_in"] == item_crafter.name
    assert recipe["category"] == "crafting"
    # Ingrédients 100% déjà obtenus, jamais l'output lui-même (anti-boucle §10).
    assert all(ing["type"] == "item" and ing["name"] in state.obtained_items
               and ing["name"] != out for ing in recipe["ingredients"])
    assert recipe in state.recipes
    assert state.is_obtained("item", out)


def test_recette_fixe_sortie_item_forced_output():
    """Le paramètre ``output_item`` force l'output de la recette du fabricateur
    fixe (équivalent du ``output_fluid`` du pairing C7 pour la variante item)."""
    from tool.generator.recursive_phase import _make_fixed_recipe_for_crafter

    rng = random.Random(42)
    db = build_demo_db()
    item_crafter = _make_item_fixed_transformer(db)
    state = ProgressionState()
    state.obtained_items = {"wood", "stone", "iron-plate", "copper-plate"}

    recipe = _make_fixed_recipe_for_crafter(
        rng, db, state, item_crafter, output_item="copper-plate"
    )
    assert recipe["results"][0]["name"] == "copper-plate"


def test_recette_fixe_item_refuse_fluid_output():
    """Un fabricateur à sortie item ne peut PAS recevoir un ``output_fluid``
    imposé (les deux variantes sont exclusives : c'est le pairing C7 qui garde
    le pending strictement sur ``is_fixed_fluid_crafter``)."""
    from tool.generator.recursive_phase import _make_fixed_recipe_for_crafter

    rng = random.Random(42)
    db = build_demo_db()
    item_crafter = _make_item_fixed_transformer(db)
    state = ProgressionState()
    state.obtained_items = {"wood", "stone", "iron-plate", "copper-plate"}
    state.obtained_fluids = {"water"}

    with pytest.raises(ValueError):
        _make_fixed_recipe_for_crafter(
            rng, db, state, item_crafter, output_fluid="water"
        )
