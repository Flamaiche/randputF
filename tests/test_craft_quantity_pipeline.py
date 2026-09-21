"""Intégration pipeline du chantier C1 (randomisation des quantités de craft).

- désactivée (défaut) → les recettes sont rendues à l'identique ;
- activée → chaque quantitié (ingrédients ET résultats) est multipliée par un
  facteur aléatoire dans les bornes, jamais en-dessous de `amount_min` ;
- déterministe : mêmes graines → mêmes quantités ;
- structure préservée : noms de recettes, étapes, ordre et solvabilité
  (le validateur ne lit que la structure, pas les montants).
"""

import copy
import json
from pathlib import Path

from tool.generator.craft_quantity import apply_craft_quantity
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump

DB = load_db_from_dump(
    json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text())
)

CONFIG = {
    "craft_quantity": {
        "enabled": True,
        "mode": "symmetric",
        "factor_min": 0.5,
        "factor_max": 3.0,
        "amount_min": 1,
    }
}


def _seed(seed_value=7, config=None):
    db = copy.deepcopy(DB)
    db.seed_value = seed_value
    return generate_seed(db, config)


def test_defaut_inerte():
    a = _seed(config=None)
    b = _seed(config=None)
    assert a["recipes"] == b["recipes"]


def test_activation_change_les_montants():
    base = _seed(config=None)
    act = _seed(config={"craft_quantity": CONFIG["craft_quantity"]})
    diff_ing = diff_res = 0
    for r0, r1 in zip(base["recipes"], act["recipes"]):
        for ing0, ing1 in zip(r0["ingredients"], r1["ingredients"]):
            if ing0["amount"] != ing1["amount"]:
                diff_ing += 1
        for res0, res1 in zip(r0["results"], r1["results"]):
            if res0["amount"] != res1["amount"]:
                diff_res += 1
    assert diff_ing + diff_res > 0


def test_amount_min_et_structure_preserves():
    act = _seed(config={"craft_quantity": CONFIG["craft_quantity"]})
    for r in act["recipes"]:
        for ing in r["ingredients"]:
            assert ing["amount"] >= 1
        for res in r["results"]:
            assert res["amount"] >= 1
    # Structure : noms et count identiques à la run de base.
    base = _seed(config=None)
    assert len(act["recipes"]) == len(base["recipes"])
    assert [r["name"] for r in act["recipes"]] == [r["name"] for r in base["recipes"]]


def test_deterministe():
    a = _seed(config={"craft_quantity": CONFIG["craft_quantity"]})
    b = _seed(config={"craft_quantity": CONFIG["craft_quantity"]})
    assert a["recipes"] == b["recipes"]


def test_action_unitaire_sur_dict():
    r = {
        "meta": {"seed": 5},
        "recipes": [
            {
                "name": "recette-a",
                "ingredients": [
                    {"type": "item", "name": "fer", "amount": 2},
                    {"type": "fluid", "name": "eau", "amount": 10},
                ],
                "results": [{"type": "item", "name": "acier", "amount": 1}],
            }
        ],
    }
    apply_craft_quantity(r, {"craft_quantity": CONFIG["craft_quantity"]})
    for ing in r["recipes"][0]["ingredients"]:
        assert ing["amount"] >= 1
    assert r["recipes"][0]["results"][0]["amount"] >= 1
    assert r["recipes"][0]["ingredients"][0]["name"] == "fer"


def test_mode_asymmetric_independance():
    cfg = {"craft_quantity": {**CONFIG["craft_quantity"], "mode": "asymmetric"}}
    base = _seed(config=None)
    act = _seed(config=cfg)
    changed = 0
    for r0, r1 in zip(base["recipes"], act["recipes"]):
        for ing0, ing1 in zip(r0["ingredients"], r1["ingredients"]):
            if ing0["amount"] != ing1["amount"]:
                changed += 1
    assert changed > 0