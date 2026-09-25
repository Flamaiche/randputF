"""Export du graphe de production : invariants du DOT produit.

- un nœud par item/fluide, arête produit → ingrédient étiquetée par quantité ;
- ressources brutes (patches/lacs/environnement) en nœuds « source » ;
- sortie déterministe (même seed → même DOT) ;
- le `.dot` est généré par `--out` (jamais dans le mod installé — testé ici
  via `build_seed_graph_dot`)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

from tool.common.db import ENVIRONMENTAL_ITEMS
from tool.exporters.seed_graph import (
    _node_info,
    _technology_info,
    build_seed_graph_dot,
    write_seed_graph_html,
)
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


def test_technology_info_costs_and_unlocks() -> None:
    seed = {
        "recipes": [
            {
                "name": "recipe-a",
                "ingredients": [{"name": "iron-plate", "amount": 1}],
                "results": [{"name": "iron-gear", "amount": 1}],
            },
            {
                "name": "recipe-b",
                "ingredients": [{"name": "copper-plate", "amount": 1}],
                "results": [{"name": "copper-cable", "amount": 1}],
            },
        ],
        "technologies": [
            {
                "id": "tech-free",
                "localised_name": "Tech gratuite",
                "unit": {"count": 1, "ingredients": []},
                "effects": [{"type": "unlock-recipe", "recipe": "recipe-a"}],
            },
            {
                "id": "tech-paid",
                "localised_name": "Tech payante",
                "prerequisites": ["tech-free"],
                "craft_trigger": "iron-plate",
                "craft_trigger_count": 3,
                "unit": {
                    "count": 3,
                    "time": 60,
                    "ingredients": [
                        {"name": "automation-science-pack", "amount": 2},
                        {"name": "iron-plate", "amount": 4},
                    ],
                },
                "effects": [
                    {"type": "unlock-recipe", "recipe": "recipe-b"},
                    {"type": "unlock-recipe", "recipe": "recipe-b"},
                ],
            },
        ],
        "progression_order": ["tech-free", "tech-paid"],
        "free_researches": ["tech-free"],
    }

    techs = _technology_info(seed)
    assert techs["tech-free"]["name"] == "Tech gratuite"
    assert techs["tech-free"]["free"] is True
    assert techs["tech-paid"]["prerequisites"] == [
        {"id": "tech-free", "name": "Tech gratuite", "num": 1}
    ]
    assert techs["tech-paid"]["craft_trigger"] == {"name": "iron-plate", "count": 3}
    assert techs["tech-paid"]["ingredients"] == [
        {"name": "automation-science-pack", "amount": 6},
        {"name": "iron-plate", "amount": 12},
    ]
    assert techs["tech-paid"]["unlocks"] == [
        {"recipe": "recipe-b", "product": "copper-cable"}
    ]

    _, recipes = _node_info(seed)
    assert recipes["recipe-a"]["techs"][0]["id"] == "tech-free"
    assert recipes["recipe-b"]["techs"][0]["id"] == "tech-paid"


def test_graph_html_embeds_technology_info(tmp_path: Path, monkeypatch) -> None:
    seed = {
        "meta": {"seed": "html"},
        "pools": {"raw_resources": []},
        "recipes": [
            {
                "name": "recipe-a",
                "ingredients": [{"name": "iron-ore", "amount": 1}],
                "results": [{"name": "iron-plate", "amount": 1}],
            }
        ],
        "technologies": [
            {
                "id": "tech-paid",
                "localised_name": "Tech payante",
                "unit": {
                    "count": 3,
                    "time": 60,
                    "ingredients": [{"name": "automation-science-pack", "amount": 2}],
                },
                "effects": [{"type": "unlock-recipe", "recipe": "recipe-a"}],
            }
        ],
        "progression_order": ["tech-paid"],
    }
    monkeypatch.setattr("tool.exporters.seed_graph.shutil.which", lambda _: "dot")
    monkeypatch.setattr(
        "tool.exporters.seed_graph.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout='<svg><g class="graph"></g></svg>'),
    )

    path = tmp_path / "seed.graph.html"
    write_seed_graph_html(seed, path)
    html = path.read_text(encoding="utf-8")

    assert "__TECHS__" not in html
    assert "const TECHS = " in html
    assert '"tech-paid"' in html
    assert '"amount": 6' in html


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


def test_ressource_brute_jamais_consommee_toujours_visible() -> None:
    """Une ressource brute absente de TOUTES les recettes reste un nœud source
    (§6) : matière non-infinie jamais consommée → pas invisible au graphe
    (bug « on dirait qu'elle n'est pas dans le jeu »)."""
    # Seed miniature SANS consommation d'eau : le lac/fluide d'extraction
    # (water) n'apparaît dans aucune recette, il doit quand même être rendu.
    seed = {
        "meta": {"seed": "mini", "generator_version": "0.1.0", "factorio_version": "2.0"},
        "pools": {"raw_resources": ["water", "wood", "stone", "raw-fish"]},
        "map": {"patches": [], "lakes": [{"resource": "water"}]},
        "recipes": [
            {
                "name": "a",
                "ingredients": [{"type": "item", "name": "wood", "amount": 2}],
                "results": [{"type": "item", "name": "iron-stick", "amount": 1}],
            }
        ],
    }
    dot = build_seed_graph_dot(seed)
    assert '"water"' in dot  # présent même sans être consommé
    assert '"stone"' in dot  # idem, environnemental jamais dans une recette
    assert '"raw-fish"' in dot
    # rendu en nœud source (ellipse grise OU image vanilla), jamais en arête
    water_lines = [l for l in dot.splitlines() if l.startswith('  "water"')]
    assert water_lines, "water doit avoir un nœud"
    assert "-->" not in water_lines[0]