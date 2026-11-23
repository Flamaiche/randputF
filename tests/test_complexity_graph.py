"""Rapport de complexité : dépliage joueur, ateliers et sortie HTML autonome."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tool.audit.graph import analyze_graph
from tool.exporters import report as report_module
from tool.exporters import vanilla_complexity
from tool.exporters.complexity_graph import (
    _format_seconds,
    analyze_complexity,
    analyze_playthrough,
    render_complexity_html,
    write_complexity_html,
)


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


def test_complexite_expose_profondeur_et_goulot() -> None:
    data = analyze_complexity(_tiny_seed())

    assert data["chain_depth"] >= 1
    assert data["critical_seconds"] > 0
    assert data["critical_label"] != "0:00"
    assert data["sequential_seconds"] >= data["total_research_seconds"]


def test_format_seconds_grandes_durees() -> None:
    assert _format_seconds(90) == "1:30"
    assert _format_seconds(3661) == "1:01:01"
    assert _format_seconds(172800) == "2,0 j"
    assert _format_seconds(365.2425 * 86400 * 2.5) == "2,5 ans"
    assert _format_seconds(365.2425 * 86400 * 2_300_000) == "2,3 M d'années"


def test_html_affiche_profondeur_et_temps_critique(tmp_path: Path) -> None:
    path = tmp_path / "seed.complexity.html"
    write_complexity_html(_tiny_seed(), path)
    text = path.read_text(encoding="utf-8")

    assert "Profondeur max" in text
    assert "Goulot de chaîne" in text
    assert "Temps théorique (1 machine)" in text
    assert "id='complexite-courbes'" in text
    assert "id='complexite-ateliers'" in text


def test_html_marque_les_ratios_vs_vanilla() -> None:
    reference = analyze_complexity(_tiny_seed())
    seed = _tiny_seed()
    seed["technologies"][0]["unit"]["count"] = 4
    data = analyze_complexity(seed)

    document = render_complexity_html(seed, data=data, baseline=reference)

    assert "×2 vanilla" in document
    assert "Les « ×N » comparent chaque valeur à vanilla" in document
    assert "bar-val" in document


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
    # Vitesse déclarée par le « dump » (db) : assembling-machine-1 = 0.5.
    db = SimpleNamespace(
        buildings={"assembling-machine-1": SimpleNamespace(crafting_speed=0.5)}
    )
    data = analyze_complexity(_tiny_seed(), db)
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


def test_complexite_et_tableau_fragmentent_la_progression() -> None:
    analyze_events: list[tuple[int, str]] = []
    analyze_complexity(
        _tiny_seed(),
        on_progress=lambda percent, detail: analyze_events.append((percent, detail)),
    )
    analyze_values = [percent for percent, _ in analyze_events]
    assert analyze_values[0] == 0
    assert analyze_values[-1] == 100
    assert analyze_values == sorted(analyze_values)
    assert any("dépliage des recettes" in detail for _, detail in analyze_events)
    assert any(
        "1/1 techs" in detail and "étapes" in detail
        for _, detail in analyze_events
    )
    assert any(" étapes" in detail for _, detail in analyze_events)
    assert any(
        "profondeur" in detail and "automation-science-pack" in detail
        for _, detail in analyze_events
    )

    render_events: list[tuple[int, str]] = []
    document = render_complexity_html(
        _tiny_seed(),
        on_progress=lambda percent, detail: render_events.append((percent, detail)),
    )
    render_values = [percent for percent, _ in render_events]
    assert "<html" in document
    assert render_values == sorted(render_values)
    assert render_values[0] == 0
    assert render_values[-1] == 100
    assert any("graphiques" in detail for _, detail in render_events)
    assert any("tableau" in detail for _, detail in render_events)


def test_tech_sans_science_affiche_zero_etape() -> None:
    seed = _tiny_seed()
    seed["technologies"][0]["unit"]["count"] = 0
    events: list[tuple[int, str]] = []
    analyze_complexity(
        seed,
        on_progress=lambda percent, detail: events.append((percent, detail)),
    )
    assert any(
        "1/1 techs" in detail and detail.endswith("0 étapes")
        for _, detail in events
    )


def test_rapport_sans_simulation_utilise_le_graphe_memoise(tmp_path: Path) -> None:
    events: list[tuple[int, str]] = []
    report_module.write_full_report(
        _tiny_seed(),
        tmp_path / "rapport.html",
        dump={},
        skip=frozenset({"playthrough", "difficulty"}),
        on_progress=lambda percent, detail: events.append((percent, detail)),
    )

    assert any("complexité depuis le graphe mémoïsé" in detail for _, detail in events)
    assert not any("simulation de la partie" in detail for _, detail in events)


def test_playthrough_remonte_sa_progression() -> None:
    events: list[tuple[int, str]] = []
    analyze_playthrough(
        _tiny_seed(),
        on_progress=lambda percent, detail: events.append((percent, detail)),
    )
    values = [percent for percent, _ in events]
    assert values[0] == 0
    assert values[-1] == 100
    assert values == sorted(values)
    assert any("simulation technologique" in detail for _, detail in events)


def test_playthrough_alimente_complexite_sans_depliage_separe() -> None:
    seed = _tiny_seed()
    playthrough = analyze_playthrough(seed)
    stats = playthrough["complexity_stats"]
    assert stats["rows"][0]["packs"] == 2
    assert stats["resources"] == {"iron-plate": 2, "stone": 2, "wood": 4}
    events: list[tuple[int, str]] = []
    data = analyze_complexity(
        seed,
        playthrough=stats,
        on_progress=lambda percent, detail: events.append((percent, detail)),
    )
    assert data["total_packs"] == 2
    assert data["total_raw"] == 8
    assert data["total_crafts"] == 4
    assert any("complexité depuis la simulation" in detail for _, detail in events)
    assert not any("dépliage des recettes" in detail for _, detail in events)


def test_complexite_depuis_simulation_garde_longueur_du_graphe() -> None:
    seed = _tiny_seed()
    graph = analyze_graph(seed)
    stats = analyze_playthrough(seed)["complexity_stats"]

    data = analyze_complexity(seed, playthrough=stats, graph=graph)

    assert data["chain_depth"] >= 1
    assert data["critical_seconds"] > 0


def test_simulation_persistee_dans_le_dump_et_rejouee(monkeypatch) -> None:
    seed = _tiny_seed()
    dump: dict = {"meta": {"game_version": "1.0"}}
    original = vanilla_complexity.analyze_playthrough
    calls: list[int] = []

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(vanilla_complexity, "analyze_playthrough", counted)

    first = vanilla_complexity.playthrough_report(dump, None, seed=seed)
    assert first["cache_written"]
    assert not first["cache_hit"]
    assert "randputf_cache" in dump

    second = vanilla_complexity.playthrough_report(dump, None, seed=seed)
    assert second["cache_hit"]
    assert not second["cache_written"]
    assert len(calls) == 1
    assert second["analysis"] == first["analysis"]

    dump["meta"]["game_version"] = "2.0"
    third = vanilla_complexity.playthrough_report(dump, None, seed=seed)
    assert not third["cache_hit"]
    assert len(calls) == 2

    vanilla_complexity.playthrough_report(dump, None, seed=seed, cache=False)
    assert len(calls) == 3
