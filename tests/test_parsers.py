"""Tests du taggage fonctionnel des bâtiments (§5.1) : le tag « recherche » est
réservé aux labs, les accumulateurs ne sont jamais des générateurs."""

from __future__ import annotations

from tool.common.db import VanillaDB
from tool.parsers.vanilla import equivalent_functional_type, load_db_from_dump, tag_parse_entity


def test_lab_classe_en_recherche():
    entity = {
        "type": "lab",
        "energy_source": {"type": "electric", "usage_priority": "secondary-input"},
        "energy_usage": "150kW",
        "lab_inputs": ["automation-science-pack"],
    }
    bdef = tag_parse_entity("lab", entity)
    assert bdef is not None
    assert bdef.is_research is True
    assert equivalent_functional_type(bdef) == "research"
    assert bdef.directives["lab_inputs"] == ("automation-science-pack",)


def test_lab_jamais_atelier_ni_generateur():
    entity = {
        "type": "lab",
        "energy_source": {"type": "electric", "usage_priority": "secondary-input"},
        "lab_inputs": ["automation-science-pack"],
    }
    bdef = tag_parse_entity("lab", entity)
    assert bdef.crafting_categories == ()
    assert not bdef.fluid_outputs


def test_accumulateur_pas_generateur():
    entity = {
        "type": "accumulator",
        "energy_source": {"type": "electric", "usage_priority": "tertiary"},
        "max_power_output": 300000.0,
    }
    bdef = tag_parse_entity("accumulator", entity)
    assert bdef.is_generator is False


def test_batiment_recherche_dans_db():
    dump = {
        "meta": {},
        "items": {},
        "fluids": {},
        "entities": {
            "lab": {
                "type": "lab",
                "energy_source": {"type": "electric"},
                "lab_inputs": ["automation-science-pack"],
            }
        },
        "recipes": {},
    }
    db: VanillaDB = load_db_from_dump(dump)
    assert [b.name for b in db.buildings_with_tag("is_research")] == ["lab"]


def test_tags_items_s9():
    """Tags §9 sur ItemDef (docs/tags.md §12) : environnemental,
    virtual (contrôle), module, capsule — décidés par capacités/type."""
    dump = {
        "meta": {},
        "items": {
            "wood": {"type": "raw-resource", "subgroup": "raw-resource"},
            "stone": {"type": "raw-resource", "subgroup": "raw-resource"},
            "raw-fish": {"type": "raw-resource", "subgroup": "raw-resource"},
            "blueprint": {"type": "blueprint", "stack_size": 1},
            "effectivity-module": {"type": "module", "stack_size": 50},
            "grenade": {"type": "capsule", "stack_size": 5},
            "iron-plate": {"type": "item", "subgroup": "intermediate"},
            "automation-science-pack": {"type": "tool", "subgroup": "science-pack"},
        },
        "fluids": {},
        "entities": {},
        "recipes": {},
    }
    db: VanillaDB = load_db_from_dump(dump)
    items = db.items
    assert items["wood"].is_environmental
    assert items["stone"].is_environmental
    assert items["raw-fish"].is_environmental
    assert not items["iron-plate"].is_environmental
    assert items["blueprint"].is_virtual_item
    assert not items["automation-science-pack"].is_virtual_item  # pack ≠ contrôle
    assert items["effectivity-module"].is_module
    assert items["grenade"].is_capsule_throwable
    assert not items["iron-plate"].is_module


def test_tags_combat_et_defense_s7():
    """Tags §7 (docs/tags.md §10) : les 4 familles de tourelles détectées
    par type, l'union is_turret, muraille/mine/robot de combat distinct du
    robot logistique."""
    dump = {
        "meta": {},
        "items": {},
        "fluids": {},
        "entities": {
            "gun-turret": {"type": "ammo-turret"},
            "laser-turret": {"type": "electric-turret",
                             "energy_source": {"type": "electric"}},
            "flamethrower-turret": {"type": "fluid-turret"},
            "artillery-turret": {"type": "artillery-turret"},
            "stone-wall": {"type": "wall"},
            "gate": {"type": "gate"},
            "land-mine": {"type": "land-mine"},
            "defender": {"type": "combat-robot"},
            "logistic-robot": {"type": "logistic-robot"},
        },
        "recipes": {},
    }
    db: VanillaDB = load_db_from_dump(dump)
    b = db.buildings
    assert b["gun-turret"].is_turret and b["gun-turret"].is_gun_turret
    assert b["laser-turret"].is_turret and b["laser-turret"].is_laser_turret
    assert b["laser-turret"].consumes_electricity
    assert b["flamethrower-turret"].is_turret and b["flamethrower-turret"].is_flame_turret
    assert b["artillery-turret"].is_turret and b["artillery-turret"].is_artillery
    assert not b["gun-turret"].is_laser_turret
    assert b["stone-wall"].is_defensive_wall and b["gate"].is_defensive_wall
    assert b["land-mine"].is_landmine
    assert b["defender"].is_combat_robot
    assert not b["defender"].is_robot          # §7 vs §2 (logistique)
    assert b["logistic-robot"].is_robot and not b["logistic-robot"].is_combat_robot


def test_tags_electronique_s8():
    """Tags §8 (docs/tags.md §11) : combinators (calcul + constant),
    l'union is_circuit_io, lampe et radar — détectés par type, consommateurs
    de courant là où l'énergie est exportée."""
    dump = {
        "meta": {},
        "items": {},
        "fluids": {},
        "entities": {
            "arithmetic-combinator": {"type": "arithmetic-combinator",
                                      "energy_source": {"type": "electric"}},
            "decider-combinator": {"type": "decider-combinator",
                                   "energy_source": {"type": "electric"}},
            "selector-combinator": {"type": "selector-combinator",
                                    "energy_source": {"type": "electric"}},
            "constant-combinator": {"type": "constant-combinator"},
            "programmable-speaker": {"type": "programmable-speaker",
                                     "energy_source": {"type": "electric"}},
            "display-panel": {"type": "display-panel"},
            "power-switch": {"type": "power-switch"},
            "small-lamp": {"type": "lamp", "energy_source": {"type": "electric"}},
            "radar": {"type": "radar", "energy_source": {"type": "electric"}},
            "stone-furnace": {"type": "furnace", "energy_source": {"type": "burner"},
                              "crafting_categories": ["smelting"]},
        },
        "recipes": {},
    }
    db: VanillaDB = load_db_from_dump(dump)
    b = db.buildings
    for name in ("arithmetic-combinator", "decider-combinator", "selector-combinator"):
        assert b[name].is_circuit_combinator and b[name].is_circuit_io
    assert b["constant-combinator"].is_constant_combinator and b["constant-combinator"].is_circuit_io
    for name in ("programmable-speaker", "display-panel", "power-switch"):
        assert b[name].is_circuit_io
    assert b["small-lamp"].is_rgb_lamp and b["small-lamp"].consumes_electricity
    assert b["radar"].is_radar and b["radar"].consumes_electricity
    # Contraste : un four n'est ni tourelle ni électronique.
    assert not b["stone-furnace"].is_circuit_io and not b["stone-furnace"].is_turret
    assert b["stone-furnace"].is_crafter