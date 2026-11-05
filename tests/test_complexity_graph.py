"""Rapport de complexité : dépliage joueur, ateliers et sortie HTML autonome."""

from __future__ import annotations

from pathlib import Path

from tool.exporters.complexity_graph import analyze_complexity, write_complexity_html


def _tiny_seed() -> dict:
    return {
        "meta": {"seed": "mini", "generator_version": "0.1.0"},
        "pools": {"raw_resources": ["wood", "stone", "iron-plate"]},
        "starter_kit": [],
        "free_researches": [],
        "progression_order": ["tech-1"],
        "recipes": [
            {
                "name": "gear",
                "energy": 2,
                "crafted_in": "assembling-machine-1",
                "ingredients": [{"name": "iron-plate", "amount": 1}],
                "results": [{"name": "iron-gear", "amount": 1}],
            },
            {
                "name": "pack",
                "energy": 4,
                "crafted_in": "assembling-machine-1",
                "ingredients": [
                    {"name": "wood", "amount": 2},
                    {"name": "stone", "amount": 1},
                    {"name": "iron-gear", "amount": 1},
                ],
                "results": [{"name": "automation-science-pack", "amount": 1}],
            },
        ],
        "technologies": [
            {
                "id": "tech-1",
                "localised_name": "Tech 1",
                "unit": {
                    "count": 2,
                    "time": 10,
                    "ingredients": [{"name": "automation-science-pack", "amount": 1}],
                },
                "effects": [],
            }
        ],
    }


def test_expansion_counts_crafts_and_raw() -> None:
    data = analyze_complexity(_tiny_seed())
    assert data["tech_count"] == 1
    # 2 packs → 2 crafts de pack + 2 crafts de gear.
    assert data["total_crafts"] == 4
    assert data["total_packs"] == 2
    assert data["total_raw"] == 8  # 4 wood + 2 stone + 2 iron-plate
    assert data["most_used_fabricator"] == "assembling-machine-1"
    assert data["most_used_fabricator_crafts"] == 4
    assert data["most_used_resource"] == "wood"
    assert data["most_used_resource_amount"] == 4

    row = data["tech_rows"][0]
    assert row["packs"] == 2
    assert row["building_count"] == 1
    assert row["crafts"] == 4
    assert row["raw_total"] == 8


def test_starter_items_break_recipe_cycles() -> None:
    seed = _tiny_seed()
    seed["pools"]["raw_resources"] = ["wood"]
    seed["starter_kit"] = [
        {"name": "stone"},
        {"name": "iron-gear"},
        {"name": "pickaxe"},
    ]
    seed["recipes"][1]["ingredients"].append({"name": "pickaxe", "amount": 1})

    data = analyze_complexity(seed)
    usage = dict(data["resource_usage"])
    # Même craftable, un objet du kit reste terminal : il amorce les cycles.
    assert usage["iron-gear"] == 2
    assert usage["stone"] == 2
    assert usage["pickaxe"] == 2
    assert usage["wood"] == 4
    assert data["total_raw"] == 10
    assert data["total_crafts"] == 2  # aucun craft de gear


def test_craft_seconds_uses_crafting_speed() -> None:
    # Fallback vanilla : assembling-machine-1 = 0.5.
    data = analyze_complexity(_tiny_seed())
    # 2 packs × 4 s / 0,5 = 16 s ; 2 gears × 2 s / 0,5 = 8 s.
    assert data["total_craft_seconds"] == 24


def test_html_is_autonomous(tmp_path: Path) -> None:
    path = tmp_path / "seed.complexity.html"
    write_complexity_html(_tiny_seed(), path)
    text = path.read_text(encoding="utf-8")
    assert "seed.complexity" not in text
    assert "http://" not in text and "https://" not in text
    assert text.count("<svg") == 6
    assert "assembling-machine-1" in text
