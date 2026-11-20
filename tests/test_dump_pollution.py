"""Dumps moddés : l'état réel est conservé, les recettes sont canonisées.

Un dump produit avec randputF actif contient les prototypes vanilla
neutralisés (``hidden = true``) et les prototypes préfixés actifs. Le tool ne
les filtre plus : il garde les liens, puis choisit ``randputf-X`` comme
recette canonique du produit ``X`` quand elle existe et n'est pas cachée.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from tool.common.db import SLOT_FLUID
from tool.exporters.mod_seed import build_vanilla_seed
from tool.generator.pipeline import generate_seed
from tool.generator.starter_chain import _extractors_for_resource
from tool.parsers.vanilla import load_db_from_dump, rocket_chain_from_dump

DUMP_PATH = Path(__file__).resolve().parent.parent / "data" / "vanilla_dump.json"
CLEAN = json.loads(DUMP_PATH.read_text(encoding="utf-8"))


def _add_prefixed_recipe(dump: dict, *, hidden: bool = False) -> dict:
    """Ajoute ``randputf-iron-plate`` et neutralise ``iron-plate``."""
    modded = copy.deepcopy(dump)
    recipe = copy.deepcopy(modded["recipes"]["iron-plate"])
    recipe["enabled"] = not hidden
    recipe["hidden"] = hidden
    modded["recipes"]["randputf-iron-plate"] = recipe
    modded["recipes"]["iron-plate"]["enabled"] = False
    modded["recipes"]["iron-plate"]["hidden"] = True
    return modded


def test_dump_modde_garde_les_liens_et_canonise_la_recette_prefixee():
    modded = _add_prefixed_recipe(CLEAN)

    db = load_db_from_dump(modded)

    assert db.canonical_recipes["iron-plate"] == "randputf-iron-plate"
    assert "randputf-iron-plate" in db.recipes
    assert "iron-plate" not in db.recipes
    assert db.recipes["randputf-iron-plate"].hidden is False
    assert db.recipes["randputf-iron-plate"].enabled is True
    # Le dump brut garde la recette vanilla neutralisée : aucun lien perdu.
    assert modded["recipes"]["iron-plate"]["hidden"] is True


def test_recette_prefixee_cachee_ne_remplace_pas_la_vanilla():
    modded = _add_prefixed_recipe(CLEAN, hidden=True)

    db = load_db_from_dump(modded)

    assert "iron-plate" not in db.canonical_recipes
    assert "iron-plate" in db.recipes
    assert "randputf-iron-plate" in db.recipes


def test_dump_mute_en_place_est_accepte():
    mutated = copy.deepcopy(CLEAN)
    mutated["fluids"]["crude-oil"]["fuel_value"] = 200000

    db = load_db_from_dump(mutated)

    assert db.fluids["crude-oil"].fuel_value == 200000


def test_contenu_prefixe_reste_hors_des_pools_de_generation():
    modded = _add_prefixed_recipe(CLEAN)
    modded["items"]["randputf-tank-shotgun"] = copy.deepcopy(modded["items"]["pistol"])
    modded["fluids"]["randputf-neutre"] = copy.deepcopy(modded["fluids"]["water"])
    modded["entities"]["randputf-oil-test"] = copy.deepcopy(modded["entities"]["iron-ore"])

    db = load_db_from_dump(modded)
    db.seed_value = 5
    seed = generate_seed(db, validate=False)

    assert "randputf-tank-shotgun" in db.modded_items
    assert "randputf-neutre" in db.modded_fluids
    assert "randputf-oil-test" in db.modded_buildings
    assert "randputf-tank-shotgun" not in db.items
    assert "randputf-neutre" not in db.fluids
    assert "randputf-oil-test" not in db.buildings
    assert not any(recipe["name"].startswith("randputf-randputf-") for recipe in seed["recipes"])


def test_double_prefixe_reste_un_artefact_ignore():
    modded = copy.deepcopy(CLEAN)
    recipe = copy.deepcopy(modded["recipes"]["iron-plate"])
    modded["recipes"]["randputf-randputf-iron-plate"] = recipe

    db = load_db_from_dump(modded)

    assert "randputf-randputf-iron-plate" not in db.recipes


def test_build_vanilla_seed_derive_residu_et_fluide_de_procede():
    dump = copy.deepcopy(CLEAN)
    dump["items"]["coal"]["burnt_result"] = "stone"
    dump["fluids"]["test-flux"] = copy.deepcopy(dump["fluids"]["water"])
    boiler = copy.deepcopy(dump["entities"]["boiler"])
    boiler["fluidboxes"] = {
        "input": 1,
        "output": 0,
        "detail": {
            "1": {"production_type": "input", "filter": "test-flux"}
        },
    }
    dump["entities"]["test-boiler"] = boiler

    seed = build_vanilla_seed(dump)

    assert seed["items"]["coal"]["burnt_result"] == "stone"
    assert "test-flux" in seed["pools"]["process_fluids"]


def test_build_vanilla_seed_ignore_hidden_et_suit_la_recette_canonique():
    modded = _add_prefixed_recipe(CLEAN)

    tech = copy.deepcopy(modded["technologies"]["automation"])
    tech["enabled"] = True
    tech["hidden"] = False
    modded["technologies"]["randputf-automation"] = tech
    modded["technologies"]["automation"]["enabled"] = False
    modded["technologies"]["automation"]["hidden"] = True

    hidden_recipe = copy.deepcopy(modded["recipes"]["iron-gear-wheel"])
    hidden_recipe["enabled"] = False
    hidden_recipe["hidden"] = True
    modded["recipes"]["randputf-hidden-recipe"] = hidden_recipe

    hidden_tech = copy.deepcopy(modded["technologies"]["automation"])
    hidden_tech["hidden"] = True
    modded["technologies"]["randputf-hidden-tech"] = hidden_tech

    seed = build_vanilla_seed(modded)
    recipe_names = {recipe["name"] for recipe in seed["recipes"]}
    tech_ids = {tech["id"] for tech in seed["technologies"]}

    assert "randputf-iron-plate" in recipe_names
    assert "iron-plate" not in recipe_names
    assert "randputf-hidden-recipe" not in recipe_names
    assert "randputf-automation" in tech_ids
    assert "automation" not in tech_ids
    assert "randputf-hidden-tech" not in tech_ids


def test_build_vanilla_seed_preserve_les_types_de_slots():
    modded = copy.deepcopy(CLEAN)
    modded["recipes"]["test-fluid-recipe"] = {
        "category": "crafting",
        "energy": 1,
        "ingredients": [{"type": "fluid", "name": "water", "amount": 10}],
        "products": [{"type": "item", "name": "iron-gear-wheel", "amount": 1}],
        "enabled": True,
        "hidden": False,
    }

    seed = build_vanilla_seed(modded)
    recipe = next(r for r in seed["recipes"] if r["name"] == "test-fluid-recipe")

    assert recipe["ingredients"][0]["type"] == "fluid"
    assert recipe["results"][0]["type"] == "item"


def test_build_vanilla_seed_garde_les_recettes_cachees_actives_sur_ressources_brutes():
    modded = copy.deepcopy(CLEAN)
    modded["recipes"]["test-hidden-raw"] = {
        "category": "crafting",
        "energy": 1,
        "ingredients": [{"type": "item", "name": "iron-ore", "amount": 1}],
        "products": [{"type": "item", "name": "iron-plate", "amount": 1}],
        "enabled": True,
        "hidden": True,
    }
    modded["recipes"]["test-hidden-crafted"] = {
        "category": "crafting",
        "energy": 1,
        "ingredients": [{"type": "item", "name": "iron-gear-wheel", "amount": 1}],
        "products": [{"type": "item", "name": "iron-plate", "amount": 1}],
        "enabled": True,
        "hidden": True,
    }

    seed = build_vanilla_seed(modded)
    names = {recipe["name"] for recipe in seed["recipes"]}

    assert "test-hidden-raw" in names
    assert "test-hidden-crafted" not in names


def test_produit_sans_quantite_devient_une_unite():
    modded = copy.deepcopy(CLEAN)
    modded["recipes"]["test-no-amount"] = {
        "category": "crafting",
        "energy": 1,
        "ingredients": [{"type": "item", "name": "iron-ore", "amount": 1}],
        "products": [{"type": "item", "name": "iron-plate"}],
        "enabled": True,
        "hidden": False,
    }

    seed = build_vanilla_seed(modded)
    recipe = next(recipe for recipe in seed["recipes"] if recipe["name"] == "test-no-amount")

    assert recipe["results"][0]["amount"] == 1


def test_build_vanilla_seed_ajoute_la_conversion_du_boiler():
    seed = build_vanilla_seed(CLEAN)
    recipe = next(
        recipe for recipe in seed["recipes"]
        if recipe["name"] == "dump-boiler-steam"
    )

    assert recipe["ingredients"] == [
        {"type": "fluid", "name": "water", "amount": 100}
    ]
    assert recipe["results"] == [
        {"type": "fluid", "name": "steam", "amount": 100}
    ]
    assert recipe["crafted_in"] == "boiler"
    assert recipe["enabled"] is True


def test_atelier_reference_resout_la_variante_vers_son_item():
    modded = copy.deepcopy(CLEAN)
    modded["items"]["wpu-mk01"] = copy.deepcopy(modded["items"]["iron-plate"])
    modded["items"]["wpu-mk01"]["place_result"] = "wpu-mk01"
    modded["entities"]["wpu-mk01-turd"] = {
        "type": "assembling-machine",
        "crafting_categories": ["wpu"],
        "crafting_speed": 0.333333,
        "energy_source": {"type": "electric"},
        "items_to_place_this": ["wpu-mk01"],
    }
    modded["recipes"]["test-wpu-recipe"] = {
        "category": "wpu",
        "energy": 1,
        "ingredients": [{"type": "item", "name": "iron-ore", "amount": 1}],
        "products": [{"type": "item", "name": "iron-plate", "amount": 1}],
        "enabled": False,
        "hidden": False,
    }

    seed = build_vanilla_seed(modded)
    recipe = next(r for r in seed["recipes"] if r["name"] == "test-wpu-recipe")

    assert recipe["crafted_in"] == "wpu-mk01"


def test_atelier_reference_ignore_l_item_a_recette_cachee():
    modded = copy.deepcopy(CLEAN)
    for item, entity, hidden in (
        ("usine-cachee", "usine-cachee-turd", True),
        ("usine-mk01", "usine-mk01", False),
    ):
        modded["items"][item] = copy.deepcopy(modded["items"]["iron-plate"])
        modded["items"][item]["place_result"] = entity
        modded["entities"][entity] = {
            "type": "assembling-machine",
            "crafting_categories": ["usinage-test"],
            "crafting_speed": 1.0,
            "energy_source": {"type": "electric"},
            "items_to_place_this": [item],
        }
        modded["recipes"][item] = {
            "category": "crafting",
            "energy": 1,
            "ingredients": [{"type": "item", "name": "iron-ore", "amount": 1}],
            "products": [{"type": "item", "name": item, "amount": 1}],
            "enabled": False,
            "hidden": hidden,
        }
    modded["recipes"]["test-usinage"] = {
        "category": "usinage-test",
        "energy": 1,
        "ingredients": [{"type": "item", "name": "iron-ore", "amount": 1}],
        "products": [{"type": "item", "name": "iron-plate", "amount": 1}],
        "enabled": False,
        "hidden": False,
    }

    seed = build_vanilla_seed(modded)
    recipe = next(r for r in seed["recipes"] if r["name"] == "test-usinage")

    assert recipe["crafted_in"] == "usine-mk01"


def test_fluidbox_de_type_quelconque_devient_conversion():
    modded = copy.deepcopy(CLEAN)
    modded["fluids"]["ae-fluor"] = copy.deepcopy(modded["fluids"]["water"])
    modded["fluids"]["ae-vapeur"] = copy.deepcopy(modded["fluids"]["steam"])
    modded["entities"]["ae-transformeur"] = {
        "type": "assembling-machine",
        "fluidboxes": {
            "input": 1,
            "output": 1,
            "detail": {
                "1": {"production_type": "input", "filter": "ae-fluor"},
                "2": {"production_type": "output", "filter": "ae-vapeur"},
            },
        },
    }

    seed = build_vanilla_seed(modded)
    recipe = next(r for r in seed["recipes"] if r["name"] == "dump-ae-transformeur-ae-vapeur")

    assert recipe["ingredients"] == [
        {"type": "fluid", "name": "ae-fluor", "amount": 100}
    ]
    assert recipe["results"] == [
        {"type": "fluid", "name": "ae-vapeur", "amount": 100}
    ]
    assert recipe["crafted_in"] == "ae-transformeur"


def test_fluidbox_en_boucle_ne_cree_pas_de_conversion():
    modded = copy.deepcopy(CLEAN)
    modded["entities"]["ae-boucle"] = {
        "type": "generator",
        "fluidboxes": {
            "input": 1,
            "output": 1,
            "detail": {
                "1": {"production_type": "input-output", "filter": "steam"},
            },
        },
    }

    seed = build_vanilla_seed(modded)

    assert not any(r["name"].startswith("dump-ae-boucle-") for r in seed["recipes"])


def test_lac_generique_utilise_un_extracteur_sans_nom_vanilla():
    modded = copy.deepcopy(CLEAN)
    modded["fluids"]["ae-lac"] = copy.deepcopy(modded["fluids"]["water"])
    modded["entities"]["ae-pompe"] = {
        "type": "offshore-pump",
        "energy_source": {"type": "void"},
        "fluidboxes": {
            "input": 0,
            "output": 1,
            "detail": {"1": {"production_type": "output", "filter": "ae-lac"}},
        },
    }

    db = load_db_from_dump(modded)
    candidates = _extractors_for_resource(db, SLOT_FLUID, "ae-lac", is_lake=True)

    assert [b.name for b in candidates][0] == "ae-pompe"


def test_chaine_fusee_ignore_les_categories_non_rocket_d_un_silo():
    modded = copy.deepcopy(CLEAN)
    modded["entities"]["ae-ferme"] = {
        "type": "rocket-silo",
        "rocket_parts_required": 1,
        "crafting_categories": ["ae-ferme"],
    }
    modded["recipes"]["ae-recette-ferme"] = {
        "category": "ae-ferme",
        "energy": 1,
        "ingredients": [{"type": "item", "name": "iron-ore", "amount": 1}],
        "products": [{"type": "item", "name": "iron-plate", "amount": 1}],
        "enabled": True,
        "hidden": False,
    }

    chain = rocket_chain_from_dump(modded)

    assert "rocket-silo" in chain["launch_buildings"]
    assert "ae-ferme" not in chain["launch_buildings"]
    assert "ae-recette-ferme" not in chain["rocket_recipes"]


def test_build_vanilla_seed_repli_prefixe_sans_champs_d_etat():
    modded = copy.deepcopy(CLEAN)
    for recipe in modded["recipes"].values():
        recipe.pop("enabled", None)
        recipe.pop("hidden", None)

    recipe = copy.deepcopy(modded["recipes"]["iron-plate"])
    modded["recipes"]["randputf-iron-plate"] = recipe

    seed = build_vanilla_seed(modded)
    recipe_names = {entry["name"] for entry in seed["recipes"]}

    assert "randputf-iron-plate" in recipe_names
    assert "iron-plate" not in recipe_names


def test_build_vanilla_seed_garde_main_product_lab_et_formule():
    modded = copy.deepcopy(CLEAN)
    modded["recipes"]["dual-sortie"] = {
        "category": "crafting",
        "energy": 1,
        "ingredients": [{"type": "item", "name": "iron-plate", "amount": 1}],
        "products": [
            {"type": "item", "name": "principal", "amount": 1},
            {"type": "item", "name": "secondaire", "amount": 1},
        ],
        "main_product": "secondaire",
        "enabled": True,
        "hidden": False,
    }
    modded["items"]["pack-lab"] = {
        "type": "item",
        "used_by_labs": True,
        "science_capacity": 1,
    }
    modded["technologies"]["tech-formule"] = {
        "unit": {"count": 1, "time": 1, "ingredients": []},
        "research_unit_count_formula": "1000*(L-4)",
        "prerequisites": [],
        "effects": [],
    }
    seed = build_vanilla_seed(modded)
    recipe = next(r for r in seed["recipes"] if r["name"] == "dual-sortie")
    tech = next(t for t in seed["technologies"] if t["id"] == "tech-formule")

    assert recipe["main_product"] == "secondaire"
    assert seed["items"]["pack-lab"]["used_by_labs"] is True
    assert seed["items"]["pack-lab"]["science_capacity"] == 1
    assert seed["items"]["pack-lab"]["is_science_pack"] is True
    assert tech["research_unit_count_formula"] == "1000*(L-4)"


def test_build_vanilla_seed_garde_le_barrel_mais_pas_le_barillage():
    seed = build_vanilla_seed(copy.deepcopy(CLEAN))
    names = {recipe["name"] for recipe in seed["recipes"]}

    assert "barrel" in names
    assert "water-barrel" not in names
    assert "empty-water-barrel" not in names


def test_build_vanilla_seed_garde_un_baril_utilise_hors_barillage():
    modded = copy.deepcopy(CLEAN)
    modded["items"]["water-barrel"] = {
        "type": "item",
        "subgroup": "barrel",
        "stack_size": 50,
    }
    modded["recipes"]["water-barrel"] = {
        "category": "py-unbarreling",
        "enabled": False,
        "hidden": False,
        "ingredients": [
            {"type": "item", "name": "barrel", "amount": 1},
            {"type": "fluid", "name": "water", "amount": 50},
        ],
        "products": [{"type": "item", "name": "water-barrel", "amount": 1}],
    }
    modded["recipes"]["empty-water-barrel"] = {
        "category": "py-barreling",
        "enabled": False,
        "hidden": False,
        "ingredients": [{"type": "item", "name": "water-barrel", "amount": 1}],
        "products": [
            {"type": "item", "name": "barrel", "amount": 1},
            {"type": "fluid", "name": "water", "amount": 50},
        ],
    }
    modded["recipes"]["consomme-eau-barrel"] = {
        "category": "crafting",
        "enabled": True,
        "hidden": False,
        "ingredients": [
            {"type": "item", "name": "water-barrel", "amount": 1},
            {"type": "item", "name": "iron-plate", "amount": 1},
        ],
        "products": [{"type": "item", "name": "bidon-utilise", "amount": 1}],
    }

    names = {recipe["name"] for recipe in build_vanilla_seed(modded)["recipes"]}

    assert "water-barrel" in names
    assert "consomme-eau-barrel" in names
    assert "empty-water-barrel" not in names
