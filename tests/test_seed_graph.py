"""Export du graphe de production (IDEES C9) : invariants du DOT produit.

- un nœud par item/fluide, arête produit → ingrédient étiquetée par quantité ;
- ressources brutes (patches/lacs/environnement) en nœuds « source » ;
- sortie déterministe (même seed → même DOT) ;
- le `.dot` est généré par `--out` (jamais dans le mod installé — testé ici
  via `build_seed_graph_dot`)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from tool.common.db import ENVIRONMENTAL_ITEMS
from tool.exporters.seed_graph import build_seed_graph_dot
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))


def _tiny_seed() -> dict:
    """Seed miniature pour tester le format (déterministe, sans génération)."""
    return {
        "meta": {"seed": "mini", "generator_version": "0.1.0", "factorio_version": "2.0"},
        "pools": {"raw_resources": ["wood", "stone", "nickel-ore"]},
        "map": {"patches": [], "lakes": []},
        "recipes": [
            {
                "name": "a",
                "ingredients": [
                    {"type": "item", "name": "wood", "amount": 2},
                    {"type": "item", "name": "nickel-ore", "amount": 3},
                ],
                "results": [{"type": "item", "name": "iron-stick", "amount": 1}],
            },
            {
                "name": "b",
                "ingredients": [
                    {"type": "item", "name": "iron-stick", "amount": 1},
                    {"type": "fluid", "name": 'water"X', "amount": 5},
                ],
                "results": [{"type": "item", "name": "golden-science-pack", "amount": 1}],
            },
        ],
    }


def test_graph_format_mini() -> None:
    dot = build_seed_graph_dot(_tiny_seed())
    assert "digraph seed {" in dot
    assert '"iron-stick" -> "wood" [label="2"];' in dot
    assert '"iron-stick" -> "nickel-ore" [label="3"];' in dot
    assert '"golden-science-pack" -> "iron-stick" [label="1"];' in dot
    # source brute sans icône vanilla (nickel-ore) → ellipse grise ;
    # science pack sans icône → orange
    assert '"nickel-ore" [shape=ellipse, style=filled, fillcolor="#eeeeff", label="nickel-ore"];' in dot
    assert '"golden-science-pack" [shape=box, style="rounded,filled", fillcolor="#ffe8d0", label="golden-science-pack"];' in dot
    # wood (icône dispo) → nœud image ; sinon on retombe sur l'ellipse source
    wood_line = next(line for line in dot.splitlines() if '"wood"' in line)
    assert 'image=' in wood_line or 'shape=ellipse' in wood_line
    # échappement des identifiants DOT
    assert '"water\\"X"' in dot


def test_graph_deterministe() -> None:
    seed = _tiny_seed()
    assert build_seed_graph_dot(seed) == build_seed_graph_dot(copy.deepcopy(seed))


def test_graph_seed_reelle(tmp_path: Path) -> None:
    db = copy.deepcopy(DB)
    db.seed_value = 0
    seed = generate_seed(db)
    dot = build_seed_graph_dot(seed)
    assert "digraph seed {" in dot
    assert "->" in dot
    assert "[label=" in dot
    assert "science-pack" in dot
    # déterminisme réel
    assert build_seed_graph_dot(seed) == build_seed_graph_dot(copy.deepcopy(seed))
    # les ressources brutes de la seed sont des sources
    for raw in (seed["pools"]["raw_resources"] or [])[:2]:
        assert f'"' + raw.replace('"', '\\"') + f'" [shape=ellipse' in dot or raw in dot
    # les environnements (bois/pierre/poisson) sont bien sources
    assert any(name in dot for name in ENVIRONMENTAL_ITEMS)