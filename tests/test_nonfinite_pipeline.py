"""Intégration pipeline du chantier A1 (randomisation des ressources non-finies).

- désactivée (défaut) → les gisements sont rendus à l'identique (inertie) ;
- activée → richesse et cluster_radius sont ALÉATOIRES par gisement, dans les
  bornes, sans jamais toucher l'identité (kind + resource) ;
- miroir runtime (§6.5) : pour un ITEM, count reste = len(item_field_tiles(
  radius, well_seed)) — la richesse/count tombe exactement sur les tuiles que
  le mod posera ;
- flux RNG dédié : activer A1 ne perturbe pas les autres phases (les lacs,
  l'électricité, le starter restent identiques à ceux de la run de base).
"""

import copy
import json
from pathlib import Path

from tool.generator.map_patches import Patch, apply_nonfinite_randomisation
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump

DB = load_db_from_dump(
    json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text())
)

FACTORS = {
    "nonfinite": {
        "enabled": True,
        "richness_factor_min": 0.5,
        "richness_factor_max": 2.0,
        "count_factor_min": 0.5,
        "count_factor_max": 2.0,
        "radius_factor_min": 0.7,
        "radius_factor_max": 1.5,
    }
}


def _sample_patches():
    return [
        Patch("item", "iron-ore", 400000, (25, 0), 12, 11, 10),
        Patch("item", "copper-ore", 960000, (49, 0), 8, 3, 9),
        Patch("fluid", "crude-oil", 300000, (73, 0), 5, 77, 12),
        Patch("fluid", "water", 180000, (97, 0), 3, 555, 14),
    ]


def test_defaut_enabled_false_inerte():
    cfg = {}
    out = copy.deepcopy(_sample_patches())
    apply_nonfinite_randomisation(out, 5, cfg)
    assert out == _sample_patches()


def test_active_randomise_richesse_et_rayon():
    out = copy.deepcopy(_sample_patches())
    apply_nonfinite_randomisation(out, 5, FACTORS)
    for p, orig in zip(out, _sample_patches()):
        assert p.kind == orig.kind
        assert p.resource == orig.resource
        assert p.richness != orig.richness
        assert p.cluster_radius != orig.cluster_radius or p.richness != orig.richness
        assert p.richness >= 1
        assert p.cluster_radius >= 3


def test_item_count_miroir_runtime():
    from tool.generator.map_patches import item_field_tiles

    out = copy.deepcopy(_sample_patches())
    apply_nonfinite_randomisation(out, 5, FACTORS)
    for p in out:
        if p.kind == "item":
            assert p.count == len(item_field_tiles(p.cluster_radius, p.well_seed))


def test_deterministe():
    a = copy.deepcopy(_sample_patches())
    b = copy.deepcopy(_sample_patches())
    apply_nonfinite_randomisation(a, 7, FACTORS)
    apply_nonfinite_randomisation(b, 7, FACTORS)
    assert a == b


def test_flux_rng_perturbe_pas_autres_phases():
    db = copy.deepcopy(DB)
    db.seed_value = 5
    base = generate_seed(db)
    db = copy.deepcopy(DB)
    db.seed_value = 5
    a1 = generate_seed(db, config={"nonfinite": FACTORS["nonfinite"]})
    # Identités, centres, lacs, starter : inchangés (seules richesse/rayon/count).
    assert {p["resource"] for p in base["map"]["patches"]} == {
        p["resource"] for p in a1["map"]["patches"]
    }
    assert [(p["resource"], p["center"]) for p in base["map"]["patches"]] == [
        (p["resource"], p["center"]) for p in a1["map"]["patches"]
    ]
    assert base["map"]["lakes"] == a1["map"]["lakes"]
    assert base["starter_kit"] == a1["starter_kit"]
    # Richesse scalairement différente sur au moins un patch.
    assert any(
        b["richness"] != a["richness"]
        for b, a in zip(base["map"]["patches"], a1["map"]["patches"])
    )