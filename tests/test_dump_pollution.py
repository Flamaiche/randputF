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

from tool.exporters.mod_seed import build_vanilla_seed
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump

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
