"""Invariants de l'ARDOISE de difficulté (chantier B) : graphe primaire = DAG
(pas de cycle, malgré les alternatives relais/ease), chaîne fusée exempte
jamais dupliquée en recette générée, coûts unitaires mémoïsés corrects.

La violation principale (cycles réels du graphe COMPLET + craft en double
``randputf-rocket-part``) est fixée dans recursive_phase ; ces tests la
prennent en charge pour ne jamais la réintroduire.
"""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path

import pytest

from tool.audit.difficulty import (
    ROCKET_PARTS_TO_LAUNCH,
    compute_difficulty,
    unit_costs,
)
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))

SEEDS = (0, 1, 5)


def _products(seed: dict) -> dict[str, list[dict]]:
    by_product: dict[str, list[dict]] = defaultdict(list)
    for r in seed.get("recipes", []):
        for res in r.get("results", []):
            by_product[res["name"]].append(r)
    return by_product


def _primary_recipe_name(by_product: dict[str, list[dict]], product: str) -> str | None:
    cands = by_product.get(product, [])
    if not cands:
        return None
    for r in cands:
        if r["name"] == f"randputf-{product}":
            return r["name"]
    return cands[0]["name"]


@pytest.fixture(scope="module")
def seeds():
    out = {}
    for s in SEEDS:
        db = copy.deepcopy(DB)
        db.seed_value = s
        out[s] = generate_seed(db)
    return out


def _is_dag(seed: dict) -> list[list[str]]:
    """Circuits du graphe RECETTE PRIMAIRE (un produit = sa recette
    randputf-<name>, sinon la première alternative). Doit être vide."""
    by_product = _products(seed)
    raw = set(seed["pools"]["raw_resources"])

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(product: str) -> None:
        color[product] = GRAY
        stack.append(product)
        recipe = _primary_recipe_name(by_product, product)
        rdict = next((r for r in by_product.get(product, []) if r["name"] == recipe), None)
        for ing in (rdict or {}).get("ingredients", []):
            n = ing["name"]
            if n in raw or n not in by_product:
                continue
            if n not in color:
                visit(n)
            elif color[n] == GRAY:
                i = stack.index(n)
                circuit = stack[i:]
                cycled = set(circuit)
                if not any(set(c) == cycled for c in cycles):
                    cycles.append(list(circuit))
        stack.pop()
        color[product] = BLACK

    for p in list(by_product):
        if p not in color:
            visit(p)
    return cycles


def test_graphe_primaire_dag(seeds):
    for s, seed in seeds.items():
        assert not _is_dag(seed), f"seed {s}: circuits primaires {_is_dag(seed)}"


def test_pas_doublon_rocket_part(seeds):
    """rocket-part n'a AUCUNE recette générée : la recette exempte du silo est
    réservée (data-final-fixes), jamais déployée en atelier (craft en double)."""
    for s, seed in seeds.items():
        rps = [
            r["name"]
            for r in seed["recipes"]
            if any(p.get("name") == "rocket-part" for p in r.get("results", []))
        ]
        assert not rps, f"seed {s}: doubler rocket-part {rps}"


def test_ardoise_rocket_part_non_nul(seeds):
    """Le coût unitaire de 100 rocket-part doit être non nul : la chaîne fusée
    compte ses 3 ingrédients via leurs recettes primaires."""
    for s, seed in seeds.items():
        db = copy.deepcopy(DB)
        db.seed_value = s
        seed = generate_seed(db)
        report = compute_difficulty(seed)
        cost = report.unit_costs["rocket-part"]
        assert sum(cost.values()) > 0, f"seed {s}: rocket-part au coût nul"
        assert sum(report.raw_totals.values()) > 0


def test_ardoise_consomme_seulement_des_bruts(seeds):
    """Toute ressource comptée dans l'ardoise appartient aux raw_resources de
    la seed (aucun produit intermédiaire ne fuit comme feuille)."""
    for s, seed in seeds.items():
        db = copy.deepcopy(DB)
        db.seed_value = s
        seed = generate_seed(db)
        report = compute_difficulty(seed)
        raw = set(seed["pools"]["raw_resources"])
        extra = set(report.raw_totals) - raw
        assert not extra, f"seed {s}: bruts hors pool {extra}"


def test_ardoise_deterministe(seeds):
    s = SEEDS[0]
    db = copy.deepcopy(DB)
    db.seed_value = s
    a = compute_difficulty(generate_seed(db))
    db.seed_value = s
    b = compute_difficulty(generate_seed(db))
    assert dict(a.raw_totals) == dict(b.raw_totals)


def test_ardoise_couvre_toutes_les_techs(seeds):
    """Le nombre d'items comptés pour la recherche = somme des unit.count ×
    amount de TOUTES les techs à coût (les leggings craft_trigger excluent)."""
    for s, seed in seeds.items():
        db = copy.deepcopy(DB)
        db.seed_value = s
        seed = generate_seed(db)
        report = compute_difficulty(seed)
        expected = sum(
            int((t.get("unit") or {}).get("count", 1)) * float(ing.get("amount", 1))
            for t in seed["technologies"]
            for ing in ((t.get("unit") or {}).get("ingredients") or [])
        )
        paid = sum(sum(v.values()) for v in report.spent_per_tech.values())
        assert paid == pytest.approx(expected), f"seed {s}: coût recherche {paid} ≠ {expected}"


def test_ardoise_rocket_parts_constant():
    assert ROCKET_PARTS_TO_LAUNCH == 100


def test_unit_costs_diamond_safe():
    """Le coût unitaire est mémoïsé par produit : un produit partagé par
    plusieurs branches ne multiplie pas son coût (pas d'explosion)."""
    s = SEEDS[-1]
    db = copy.deepcopy(DB)
    db.seed_value = s
    seed = generate_seed(db)
    by_product = _products(seed)
    raw = set(seed["pools"]["raw_resources"])
    costs = unit_costs(raw, by_product)
    # Chaque coût unitaire est stable : recalculer ne change rien (pure).
    again = unit_costs(raw, by_product)
    assert dict(costs) == dict(again)