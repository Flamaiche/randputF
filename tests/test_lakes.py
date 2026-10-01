"""Lacs de fluide (§7.5) : 3e type de raw ressource.

- `count ∈ [min, max]` lacs tirés (défaut min=1, zéro possible si min=0) ;
- chaque lac un fluide du pool pipable, richesse dans les bornes config ;
- déterministe par seed, flux RNG indépendant (les patchs ne changent pas) ;
- le mod supprime l'eau vanilla, seuls les lacs tirés produisent des nappes.
"""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import pytest

from tool.common import config as _cfg
from tool.common.db import VanillaDB
from tool.generator.lakes import Lake, generate_lakes, make_rng
from tool.generator.map_patches import make_rng as patches_make_rng
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))


def _db(seed: int) -> VanillaDB:
    db = copy.deepcopy(DB)
    db.seed_value = seed
    return db


def test_comptage_min_max_par_defaut():
    lo, hi = _cfg.default_value("lakes", "min"), _cfg.default_value("lakes", "max")
    for seed_value in range(1, 25):
        lakes = generate_lakes(make_rng(seed_value), _db(seed_value), {})
        assert lo <= len(lakes) <= hi, (seed_value, len(lakes))


def test_zero_possible_si_min_zero():
    cfg = {"lakes": {"min": 0, "max": 3}}
    empties = any(len(generate_lakes(make_rng(s), _db(s), cfg)) == 0 for s in range(1, 30))
    assert empties, "aucune seed avec min=0 ne donne 0 lac"


def test_fluides_et_richesse_valides():
    fluids = {f.name for f in DB.pipable_fluids()}
    lo, hi = tuple(_cfg.default_value("lakes", "richness_fluid"))
    for seed_value in [1, 5, 9, 42]:
        for lake in generate_lakes(make_rng(seed_value), _db(seed_value), {}):
            assert lake.resource in fluids, lake
            assert lo <= lake.richness <= hi, lake


def test_deterministe():
    a = generate_lakes(make_rng(5), _db(5), {})
    b = generate_lakes(make_rng(5), _db(5), {})
    assert [l.to_seed() for l in a] == [l.to_seed() for l in b]


def test_flux_rng_independant_de_map_patches():
    # Le rng des lacs a son propre espace de noms : la même seed de patches
    # produit le même nombre de patchs, que des lacs soient tirés ou non.
    cfg = {"lakes": {"min": 5, "max": 5}}
    db = _db(5)
    n0 = len__patches(db)
    generate_lakes(make_rng(5), db, cfg)
    assert len__patches(db) == n0


def len__patches(db: VanillaDB):
    from tool.generator.map_patches import generate_patches

    return len(generate_patches(patches_make_rng(db.seed_value), db, {}))


def test_ords_seed_avec_lacs():
    db = _db(5)
    seed = generate_seed(db, validate=False)
    lakes = seed["map"]["lakes"]
    assert isinstance(lakes, list)
    fluids = {f.name for f in DB.pipable_fluids()}
    for lake in lakes:
        assert lake["resource"] in fluids
        assert "richness" in lake
    # Un fluide de lac est une raw ressource.
    assert {la["resource"] for la in lakes} <= set(seed["pools"]["raw_resources"])
    # Les lacs coexistent avec les patchs (items + fluides pumpjack) : l'eau
    # vanilla elle est supprimée côté mod, pas ici.
    assert isinstance(seed["map"]["patches"], list)


def test_lake_to_seed():
    lake = Lake("crude-oil", 250000)
    assert lake.to_seed() == {"resource": "crude-oil", "richness": 250000}