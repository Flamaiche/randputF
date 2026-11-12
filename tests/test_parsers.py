"""Tests du taggage fonctionnel des bâtiments (§5.1) : le tag « recherche » est
réservé aux labs, les accumulateurs ne sont jamais des générateurs."""

from __future__ import annotations

import json
from pathlib import Path

from tool.common.db import VanillaDB
from tool.parsers.vanilla import (
    equivalent_functional_type,
    inject_pumped_fluids,
    load_db_from_dump,
    rocket_chain_from_dump,
    science_pack_names,
    tag_parse_entity,
)


def _dump_with_tiles(tiles: dict, entities: dict) -> dict:
    return {"meta": {}, "tiles": tiles, "entities": entities}


def test_pumped_fluid_resolu_par_la_chaine_tuiles():
    """Une pompe sans declaration : couches requises -> tuiles -> fluide.

    Reproduit le cas vanilla : la pompe exige water_tile, les tuiles qui
    portent cette couche declarent ``water``."""
    dump = _dump_with_tiles(
        {
            "water": {"collision_layers": ["floor", "water_tile"], "fluid": "water"},
            "grass": {"collision_layers": ["ground_tile"]},
        },
        {
            "offshore-pump": {
                "type": "offshore-pump",
                "tile_buildability_rules": [
                    {
                        "required_tiles": ["ground_tile"],
                        "colliding_tiles": ["water_tile"],
                        "remove_on_collision": True,
                    },
                    {"required_tiles": ["water_tile"], "colliding_tiles": []},
                ],
            }
        },
    )
    inject_pumped_fluids(dump)
    assert dump["entities"]["offshore-pump"]["pumped_fluid"] == "water"


def test_pumped_fluid_modde_via_tuiles():
    """Un mod dont les lacs portent un autre fluide : resolu sans nom en dur."""
    dump = _dump_with_tiles(
        {
            "acid-lake": {"collision_layers": ["water_tile"], "fluid": "sulfuric-acid"},
        },
        {
            "custom-pump": {
                "type": "offshore-pump",
                "tile_buildability_rules": [{"required_tiles": ["water_tile"], "colliding_tiles": []}],
            }
        },
    )
    inject_pumped_fluids(dump)
    assert dump["entities"]["custom-pump"]["pumped_fluid"] == "sulfuric-acid"


def test_pumped_fluid_filtre_fluidbox_prioritaire():
    """Un filtre de boite de sortie declare l'emporte sur la derivation."""
    dump = _dump_with_tiles(
        {"water": {"collision_layers": ["water_tile"], "fluid": "water"}},
        {
            "custom-pump": {
                "type": "offshore-pump",
                "fluidboxes": {
                    "input": 0,
                    "output": 1,
                    "detail": {"1": {"production_type": "output", "filter": "steam"}},
                },
                "tile_buildability_rules": [{"required_tiles": ["water_tile"], "colliding_tiles": []}],
            }
        },
    )
    inject_pumped_fluids(dump)
    assert dump["entities"]["custom-pump"]["pumped_fluid"] == "steam"


def test_pumped_fluid_ambigu_ou_absent_donne_none():
    """Plusieurs fluides distincts sur les couches requises : aucun invente.

    Une pompe sans regles ni filtres n'a pas de fluide pompe (externe)."""
    dump = _dump_with_tiles(
        {
            "lake-a": {"collision_layers": ["water_tile"], "fluid": "water"},
            "lake-b": {"collision_layers": ["water_tile"], "fluid": "sulfuric-acid"},
        },
        {
            "ambiguous-pump": {
                "type": "offshore-pump",
                "tile_buildability_rules": [{"required_tiles": ["water_tile"], "colliding_tiles": []}],
            },
            "bare-pump": {"type": "offshore-pump"},
        },
    )
    inject_pumped_fluids(dump)
    assert "pumped_fluid" not in dump["entities"]["ambiguous-pump"]
    assert "pumped_fluid" not in dump["entities"]["bare-pump"]


def test_pumped_fluid_convertisseur_non_resolu():
    """Regression boiler/heat-exchanger : filtre de sortie sur une machine
    qui PREND un fluide en entree = production declaree, pas un pompage."""
    dump = _dump_with_tiles(
        {},
        {
            "boiler": {
                "type": "boiler",
                "fluidboxes": {
                    "input": 1,
                    "output": 1,
                    "detail": {
                        "1": {"production_type": "input", "filter": "water"},
                        "2": {"production_type": "output", "filter": "steam"},
                    },
                },
            }
        },
    )
    inject_pumped_fluids(dump)
    assert "pumped_fluid" not in dump["entities"]["boiler"]


def test_inject_pumped_fluids_est_idempotent():
    dump = _dump_with_tiles(
        {"water": {"collision_layers": ["water_tile"], "fluid": "water"}},
        {
            "offshore-pump": {
                "type": "offshore-pump",
                "tile_buildability_rules": [{"required_tiles": ["water_tile"], "colliding_tiles": []}],
            }
        },
    )
    inject_pumped_fluids(dump)
    first = dict(dump["entities"]["offshore-pump"])
    inject_pumped_fluids(dump)
    assert dump["entities"]["offshore-pump"] == first


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


def test_fuel_categories_compatibilite_ancien_et_nouveau_format():
    """Le dump peut exposer ``fuel_categories`` (tableau, Factorio >= 2.1.20)
    OU ``fuel_category`` (string, antérieur) : le parseur normalise les deux
    et ``fuels_for`` matche sur n'importe quelle catégorie de l'item."""
    common = {
        "meta": {},
        "fluids": {},
        "entities": {
            "reactor": {
                "type": "reactor",
                "energy_source": {"type": "burner", "fuel_categories": ["nuclear"]},
                "has_heat_output": True,
            }
        },
        "recipes": {},
    }
    old = {
        **common,
        "items": {
            "uranium-fuel-cell": {
                "type": "item",
                "fuel_value": 8000000000,
                "fuel_category": "nuclear",          # ancien format (2.0)
                "burnt_result": "depleted-uranium-fuel-cell",
            },
        },
    }
    new = {
        **common,
        "items": {
            "uranium-fuel-cell": {
                "type": "item",
                "fuel_value": 8000000000,
                "fuel_categories": ["nuclear"],        # nouveau format (2.1.20)
                "burnt_result": "depleted-uranium-fuel-cell",
            },
            "blend-fuel": {
                "type": "item",
                "fuel_value": 1000000,
                "fuel_categories": ["chemical", "nuclear"],  # multi-catégories
            },
        },
    }
    db_old: VanillaDB = load_db_from_dump(old)
    db_new: VanillaDB = load_db_from_dump(new)
    reactor_old = db_old.buildings["reactor"]
    reactor_new = db_new.buildings["reactor"]
    assert db_old.items["uranium-fuel-cell"].fuel_categories == ("nuclear",)
    assert db_new.items["uranium-fuel-cell"].fuel_categories == ("nuclear",)
    # L'ancien format nourrit bien le réacteur (repli automatique).
    assert [i.name for i in db_old.fuels_for(reactor_old)] == ["uranium-fuel-cell"]
    assert db_old.fuel_residues(reactor_old) == {"depleted-uranium-fuel-cell"}
    # Le nouveau format aussi, y compris match sur une catégorie secondaire.
    assert [i.name for i in db_new.fuels_for(reactor_new)] == [
        "blend-fuel", "uranium-fuel-cell"
    ]


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

# --- Chaîne de progression : packs de science par les FAITS du dump ---


def test_science_pack_names_via_unites_et_labs():
    """Un pack = ce que le jeu consomme pour chercher : ingredients des
    unites de tech + lab_inputs des labs. Formes dict et list couvertes."""
    dump_dict = {
        "technologies": {
            "alien-tech": {
                "unit": {"ingredients": [{"name": "alien-science-pack", "amount": 1}]}
            }
        },
        "entities": {"lab": {"type": "lab", "lab_inputs": ["odd-pack"]}},
    }
    assert science_pack_names(dump_dict) == {"alien-science-pack", "odd-pack"}
    dump_list = {
        "technologies": [
            {"unit": {"ingredients": [{"name": "alien-science-pack", "amount": 1}]}}
        ],
        "entities": {},
    }
    assert science_pack_names(dump_list) == {"alien-science-pack"}


def test_science_pack_tagg_par_faits_pas_par_subgroup():
    """Un pack modde (subgroup quelconque) est tagge parce qu'une tech le
    consomme ; un item au subgroup vanilla sans consommateur ne l'est pas."""
    dump = {
        "meta": {"game_version": "2.1.24"},
        "items": {
            "modded-pack": {"type": "item", "subgroup": "bob-logistics"},
            "faux-pack": {"type": "item", "subgroup": "science-pack"},
        },
        "fluids": {},
        "entities": {"lab": {"type": "lab", "lab_inputs": ["modded-pack"]}},
        "recipes": {},
        "technologies": {},
    }
    db = load_db_from_dump(dump)
    assert db.items["modded-pack"].is_science_pack is True
    # Rôle consommable de recherche, quel que soit le type d'item.
    assert db.items["modded-pack"].is_tool is True
    assert db.items["faux-pack"].is_science_pack is False


def _real_dump() -> dict:
    return json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "vanilla_dump.json").read_text(
            encoding="utf-8"
        )
    )


def test_science_packs_du_vrai_dump():
    """Le dump vanilla reel : les 7 packs reconnus par les faits seuls."""
    assert science_pack_names(_real_dump()) == {
        "automation-science-pack",
        "chemical-science-pack",
        "logistic-science-pack",
        "military-science-pack",
        "production-science-pack",
        "space-science-pack",
        "utility-science-pack",
    }


def test_rocket_chain_du_vrai_dump():
    """Le silo se reconnaît à rocket_parts_required, sa recette fusée par
    sa catégorie de craft, les packs spatiaux par rocket_launch_products :
    la chaîne de victoire est DÉRIVÉE, jamais codée en dur."""
    chain = rocket_chain_from_dump(_real_dump())
    assert chain["launch_buildings"] == ["rocket-silo"]
    assert chain["rocket_recipes"] == ["rocket-part"]
    assert chain["victory_items"] == [
        "low-density-structure",
        "processing-unit",
        "rocket-fuel",
        "rocket-silo",
    ]
    assert chain["launch_products"] == ["space-science-pack"]


def test_rocket_chain_moddee_sans_nom_en_dur():
    """Un mod qui remplace la fusée (bâtiment, catégorie, recette,
    ingrédients, produit de lancement) donne une chaîne correcte : aucun
    nom vanilla n'est attendu, tout vient des faits."""
    dump = {
        "meta": {},
        "items": {
            "sonde-mod": {
                "type": "item",
                "rocket_launch_products": [{"name": "science-orbital", "amount": 50}],
            },
        },
        "fluids": {},
        "entities": {
            "portail-spatial": {
                "type": "rocket-silo",
                "rocket_parts_required": 20,
                "crafting_categories": ["portail-assemblage", "parameters"],
            },
        },
        "recipes": {
            "piece-de-portail": {
                "category": "portail-assemblage",
                "ingredients": [{"name": "cristal", "amount": 2}],
                "products": [{"name": "piece-de-portail", "amount": 1}],
            },
            "parameter-0": {
                "category": "parameters",
                "ingredients": {},
                "products": {},
            },
        },
        "technologies": {},
    }
    chain = rocket_chain_from_dump(dump)
    assert chain["launch_buildings"] == ["portail-spatial"]
    assert chain["rocket_recipes"] == ["piece-de-portail"]
    assert chain["victory_items"] == ["cristal", "portail-spatial"]
    assert chain["launch_products"] == ["science-orbital"]


def test_rocket_chain_absente_si_aucun_fait():
    """Sans bâtiment à rocket_parts_required, aucune condition n'est
    inventée : chaîne vide (le rejoueur ne gagnera que par les techs)."""
    assert rocket_chain_from_dump({"meta": {}, "items": {}, "entities": {}, "recipes": {}}) == {
        "launch_buildings": [],
        "rocket_recipes": [],
        "victory_items": [],
        "launch_products": [],
    }
