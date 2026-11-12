"""Vérifie la simulation de partie (minage, crafts, fusée, fournitures)."""

import json
from pathlib import Path

import pytest

from tool.exporters.complexity_graph import analyze_playthrough
from tool.exporters.mod_seed import build_vanilla_seed, tag_progression

DUMP_PATH = Path(__file__).resolve().parents[1] / "data" / "vanilla_dump.json"


@pytest.fixture(scope="module")
def dump() -> dict:
    return json.loads(DUMP_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def analysis(dump: dict) -> dict:
    return analyze_playthrough(build_vanilla_seed(dump))


def test_space_science_requires_rocket_launches(analysis: dict) -> None:
    stats = analysis["item_stats"]
    space = stats["space-science-pack"]
    assert space["crafts"] > 0
    assert space["external"] == 0
    # Un lancement consomme les pièces de fusée et le satellite associés.
    assert stats["rocket-part"]["consumed"] == space["crafts"] * 100
    assert stats["satellite"]["consumed"] == space["crafts"]


def test_rocket_silo_is_crafted_for_space_science(analysis: dict) -> None:
    assert "rocket-silo" in analysis["buildings"]
    assert analysis["item_stats"]["rocket-silo"]["crafts"] == 1


def test_water_is_pumped_not_external(analysis: dict) -> None:
    # L'eau vient du dump (``pumped_fluid`` de la pompe offshore) : produite,
    # jamais externe.
    stats = analysis["item_stats"]
    water = stats["water"]
    assert water["produced"] > 0
    assert water["external"] == 0
    assert "offshore-pump" in analysis["buildings"]
    # La vapeur n'est plus exigée par la partie : la chaîne pétrole en dur
    # qui sélectionnait ``coal-liquefaction`` (consommatrice de vapeur) a
    # disparu, les recettes génériques n'en demandent pas.
    assert "steam" not in stats


def test_nothing_is_supplied_externally(analysis: dict) -> None:
    assert analysis["external_items"] == []


def test_raw_resources_are_mined(analysis: dict) -> None:
    stats = analysis["item_stats"]
    assert stats["iron-ore"]["mined"] > 0
    assert stats["crude-oil"]["mined"] > 0


def test_mining_time_comes_from_dump(dump: dict) -> None:
    # Le dump fournit ``mineable_time`` : la synthèse doit le reprendre tel quel.
    seed = build_vanilla_seed(dump)
    raw = (dump.get("entities") or {}).get("iron-ore") or {}
    assert raw.get("mineable_time") is not None
    assert seed["entities"]["iron-ore"]["mineable_time"] == raw["mineable_time"]


def test_mining_time_is_not_invented_when_absent() -> None:
    # Sans ``mineable_time`` dans le dump, la synthèse ne doit pas en fabriquer
    # un : l'extracteur reste la source de vérité.
    dump = {
        "items": {"iron-ore": {"type": "item", "subgroup": "raw-resource"}},
        "fluids": {},
        "entities": {
            "iron-ore": {"type": "resource"},
            "electric-mining-drill": {
                "type": "mining-drill",
                "resource_categories": ["basic-solid"],
                "mining_speed": 1,
            },
        },
        "recipes": {},
        "technologies": [],
    }
    seed = build_vanilla_seed(dump)
    assert "mineable_time" not in seed["entities"]["iron-ore"]


def test_mineable_properties_are_used() -> None:
    dump = {
        "items": {"iron-ore": {"type": "item", "subgroup": "raw-resource"}},
        "fluids": {},
        "entities": {
            "iron-ore": {
                "type": "resource",
                "mineable_properties": {
                    "mining_time": 2,
                    "products": [
                        {"type": "item", "name": "iron-ore", "amount": 5}
                    ],
                },
            },
            "electric-mining-drill": {
                "type": "mining-drill",
                "resource_categories": ["basic-solid"],
                "mining_speed": 1,
            },
        },
        "recipes": {},
        "technologies": [],
    }
    seed = build_vanilla_seed(dump)
    entry = seed["entities"]["iron-ore"]
    assert entry["mineable_products"] == [{"name": "iron-ore", "amount": 5}]
    assert entry["mineable_time"] == 2
    assert entry["resource_category"] == "basic-solid"


def test_pumped_fluid_uses_declared_source() -> None:
    seed = {
        "meta": {"seed": "test"},
        "pools": {
            "raw_resources": [],
            "item_resources": [],
            "fluid_resources": ["water"],
        },
        "fluids": {"water": {"type": "fluid"}},
        "entities": {
            "offshore-pump": {"type": "offshore-pump", "pumped_fluid": "water"}
        },
        "recipes": [],
        "technologies": [
            {
                "id": "t",
                "prerequisites": [],
                "unit": {
                    "count": 1,
                    "ingredients": [{"name": "water", "amount": 10}],
                },
            }
        ],
        "progression_order": ["t"],
    }
    analysis = analyze_playthrough(seed)
    water = analysis["item_stats"]["water"]
    assert water["produced"] == 10
    assert water["external"] == 0


def test_tag_progression_tague_la_fermeture() -> None:
    """« Fait avancer le jeu » = la fermeture de l'analyse (item_stats) ;
    les items hors chaîne restent explicitement non taggés."""
    seed = {
        "items": {
            "pack": {"type": "item", "is_science_pack": True},
            "intermediaire": {"type": "item", "is_science_pack": False},
            "decoratif": {"type": "item", "is_science_pack": False},
        },
        "fluids": {"eau": {"type": "fluid", "is_science_pack": False}},
    }
    analysis = {"item_stats": {"pack": {}, "intermediaire": {}, "eau": {}}}
    prog = tag_progression(seed, analysis)
    assert seed["items"]["pack"]["is_progression"] is True
    assert seed["items"]["intermediaire"]["is_progression"] is True
    assert seed["items"]["decoratif"]["is_progression"] is False
    assert seed["fluids"]["eau"]["is_progression"] is True
    assert prog == {"names": ["eau", "intermediaire", "pack"], "count": 3, "packs": 1}


def test_chaine_de_progression_du_vrai_dump(dump: dict) -> None:
    """Le dump vanilla : la fermeture = les 64 entrées du rapport, dont les
    7 packs, tous taggés science ET progression (faits du dump, pas subgroup)."""
    seed = build_vanilla_seed(dump)
    analysis = analyze_playthrough(seed)
    prog = tag_progression(seed, analysis)
    assert prog["count"] == len(analysis["item_stats"]) == 64
    assert prog["packs"] == 7
    packs = {
        "automation-science-pack",
        "chemical-science-pack",
        "logistic-science-pack",
        "military-science-pack",
        "production-science-pack",
        "space-science-pack",
        "utility-science-pack",
    }
    assert set(prog["names"]) >= packs
    for name in packs:
        assert seed["items"][name]["is_science_pack"] is True
        assert seed["items"][name]["is_progression"] is True


def test_launch_products_come_from_dump() -> None:
    seed = {
        "meta": {"seed": "test"},
        "pools": {"raw_resources": [], "item_resources": [], "fluid_resources": []},
        "fluids": {},
        # L'ITEM lancé (satellite) porte les produits de lancement : c'est la
        # source de vérité (ItemWithInventoryPrototype::rocket_launch_products).
        "items": {
            "satellite": {
                "type": "item",
                "rocket_launch_products": [
                    {"name": "space-science-pack", "amount": 250}
                ],
            }
        },
        "entities": {
            # Repli silo : ignoré quand l'item déclare ses produits.
            "rocket-silo": {
                "type": "rocket-silo",
                "rocket_parts_required": 100,
                "rocket_launch_products": [
                    {"name": "space-science-pack", "amount": 1000}
                ],
            },
            "assembling-machine-1": {"type": "assembling-machine"},
        },
        "recipes": [
            {
                "name": "rocket-part",
                "crafted_in": "rocket-silo",
                "ingredients": [],
                "results": [{"name": "rocket-part", "amount": 1}],
            },
            {
                "name": "satellite",
                "crafted_in": "assembling-machine-1",
                "ingredients": [],
                "results": [{"name": "satellite", "amount": 1}],
            },
        ],
        "technologies": [
            {
                "id": "space-science-pack",
                "prerequisites": [],
                "research_trigger": {
                    "type": "send-item-to-orbit",
                    "item": "satellite",
                },
            }
        ],
        "progression_order": ["space-science-pack"],
    }
    analysis = analyze_playthrough(seed)
    space = analysis["item_stats"]["space-science-pack"]
    assert space["crafts"] == 1
    assert space["produced"] == 250
    assert analysis["item_stats"]["rocket-part"]["consumed"] == 100
