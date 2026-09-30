"""Loi pondérée du site de crash (§7) : comptes [c0,c1,c2,c3] strictement
décroissants, somme des valeurs 0*c0+1*c1+2*c2+3*c3 = 100, pool de loot valide."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tool.generator.pipeline import generate_seed
from tool.generator.wreck_loot import build_wreck_config, counts_from_formula
from tool.parsers.vanilla import load_db_from_dump

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))


def test_formule_generique_comptes_valides():
    # (t, a, b) -> [c0, c1, c2, c3]
    cases = [
        (15, 1, 1, [24, 23, 16, 15]),    # défauts : 0 = 24 (P(0) ≈ 31 %)
        (10, 13, 46, [70, 24, 23, 10]),  # 0 = 70
        (14, 4, 39, [61, 22, 18, 14]),
    ]
    for t, a, b, expected in cases:
        counts = counts_from_formula(t, a, b)
        assert counts == expected, (t, a, b, counts)
        assert counts[0] > counts[1] > counts[2] > counts[3]
        assert sum(i * c for i, c in enumerate(counts)) == 100


@pytest.mark.parametrize(
    "params",
    [
        {"t": 20, "a": 1, "b": 1},   # 6t+3a = 123 >= 100 -> invalide (c1<=c2)
        {"t": 12, "a": 9, "b": 0},   # b=0 -> c0 == c1, pas strictement décroissant
        {"t": -1, "a": 1, "b": 1},   # compte négatif
    ],
)
def test_formule_rejette_les_mauvais_parametres(params):
    with pytest.raises(ValueError):
        counts_from_formula(params["t"], params["a"], params["b"])


def test_loot_existe_dans_la_base():
    cfg = build_wreck_config(None, DB)
    for name in cfg["loot"]:
        assert name in DB.items, f"loot {name} absent de la base"
    assert DB.items[cfg["loot"][0]].stack_size > 0


def test_loot_restreint_aux_ressources_non_infinies():
    # Le crash ne distribue QUE des ressources non-automatisables (bois,
    # pierre, poisson) : jamais d'item crafté (plaques, fours...) dont la
    # recette n'est pas garantie débloquée par l'arbre randomisé.
    cfg = build_wreck_config(None, DB)
    assert set(cfg["loot"]) == {"wood", "stone", "raw-fish"}


def test_wreck_dans_la_seed():
    db = copy.deepcopy(DB)
    db.seed_value = 5
    seed = generate_seed(db, validate=False)
    wreck = seed["wreck"]
    counts = wreck["counts"]
    assert len(counts) == 4
    assert counts[0] > counts[1] > counts[2] > counts[3]
    assert sum(i * c for i, c in enumerate(counts)) == 100
    assert wreck["loot"], "pool de loot vide"
    for name in wreck["loot"]:
        assert name in DB.items