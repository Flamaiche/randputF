"""Tests de l'extracteur « par tags » (tool/parsers/vanilla.py).

Vérifie que les bâtiments ne sont PLUS classés dans un type exclusif mais
reçoivent l'ENSEMBLE de leurs capacités en tags cumulables, et que le
résultat recoupe « plus ou moins » celui du classement original §5.1 :
- equivalent_functional_type(b) retrouve l'ancien classement exclusif sur le
  dump réel (outil de vérification) ;
- produces_electricity / produces_heat / medium / has_hidden_recipe
  identiques à l'ancien comportement ;
- la seule DIVERGENCE voulue : heat-exchanger est désormais is_crafter ET
  is_generator (6 générateurs taggés au lieu de 5), et character est is_crafter
  ET is_extractor (il fabrique à la main ET mine à la main) — le tag
  ``is_extractor`` est chiffré à 5 (contre 4 extracteurs exclusifs avant).
"""

from __future__ import annotations

import json
from pathlib import Path

from tool.common.db import BuildingDef, is_fixed_fluid_crafter
from tool.parsers.vanilla import (
    equivalent_functional_type,
    load_db_from_dump,
    tag_parse_entity,
)

DATA = Path(__file__).resolve().parent.parent / "data" / "vanilla_dump.json"


def test_lab_porte_le_tag_recherche():
    entity = {
        "type": "lab",
        "energy_source": {"type": "electric"},
        "lab_inputs": ["automation-science-pack"],
    }
    tb = tag_parse_entity("lab", entity)
    assert tb is not None
    assert tb.is_research is True
    assert tb.directives["lab_inputs"] == ("automation-science-pack",)
    assert equivalent_functional_type(tb) == "research"


def test_accumulateur_jamais_generateur():
    entity = {
        "type": "accumulator",
        "energy_source": {"type": "electric"},
        "max_power_output": 300000.0,
    }
    tb = tag_parse_entity("accumulator", entity)
    assert tb is not None
    assert tb.is_generator is False
    assert tb.produces_electricity is False


def test_batiment_non_classable_est_tagge_other():
    tb = tag_parse_entity("mystery", {"type": "simple-entity"})
    assert tb is not None
    assert tb.is_other is True
    assert equivalent_functional_type(tb) == "other"


def test_dump_reel_point_ancrages_et_divergence_voulue():
    dump = json.loads(DATA.read_text(encoding="utf-8"))
    db = load_db_from_dump(dump)

    expected_exclusive = {
        "lab": "research",
        "boiler": "transformer",
        "heat-exchanger": "transformer",
        "steam-engine": "generator",
        "nuclear-reactor": "generator",
        "small-electric-pole": "distribution",
        "burner-mining-drill": "extractor",
        "assembling-machine-1": "transformer",
    }
    for name, etype in expected_exclusive.items():
        b = db.buildings[name]
        assert equivalent_functional_type(b) == etype, name

    # La divergence VOULUE du passage aux tags cumulables : l'échangeur de
    # chaleur est à la fois atelier (recette fluide fixe) ET générateur.
    hx = db.buildings["heat-exchanger"]
    assert hx.is_crafter is True
    assert hx.is_generator is True
    assert is_fixed_fluid_crafter(hx) is True
    assert is_fixed_fluid_crafter(db.buildings["boiler"]) is True


def test_dump_reel_tous_les_batiments_ont_un_tag():
    dump = json.loads(DATA.read_text(encoding="utf-8"))
    db = load_db_from_dump(dump)
    for name, building in db.buildings.items():
        assert isinstance(building, BuildingDef), name
        tags = [
            building.is_research,
            building.is_crafter,
            building.is_generator,
            building.is_distribution,
            building.is_extractor,
            building.is_other,
        ]
        assert any(tags), f"{name} n'a aucun tag fonctionnel"


def test_dump_reel_comptes_par_tags():
    dump = json.loads(DATA.read_text(encoding="utf-8"))
    db = load_db_from_dump(dump)
    assert len(db.buildings_with_tag("is_research")) == 1
    assert len(db.buildings_with_tag("is_crafter")) == 13
    # Divergence voulue : heat-exchanger est en plus taggé générateur (6 au
    # lieu de 5 dans l'ancien classement exclusif).
    assert len(db.buildings_with_tag("is_generator")) == 6
    assert len(db.buildings_with_tag("is_distribution")) == 5
    assert len(db.buildings_with_tag("is_extractor")) == 5
    assert len(db.buildings_with_tag("is_other")) == 509


def test_dump_reel_tags_s1_roles():
    """§1 (docs/tags.md §1) : pylône, beacon, accumulateur, offgrid,
    consommation et extracteurs par médium sur le vrai dump vanilla."""
    dump = json.loads(DATA.read_text(encoding="utf-8"))
    db = load_db_from_dump(dump)

    assert len(db.buildings_with_tag("is_power_pole")) == 4
    assert {b.name for b in db.buildings_with_tag("is_power_pole")} == {
        "small-electric-pole",
        "medium-electric-pole",
        "big-electric-pole",
        "substation",
    }
    beacon = db.buildings["beacon"]
    assert beacon.is_beacon is True
    assert beacon.is_power_pole is False
    acc = db.buildings["accumulator"]
    assert acc.is_accumulator is True
    assert acc.is_energy_storage is True
    assert acc.is_generator is False
    assert acc.produces_electricity is False

    assert {b.name for b in db.buildings_with_tag("is_offgrid")} == {
        "burner-generator",
        "solar-panel",
    }
    assert db.buildings["steam-engine"].consumes_electricity is False
    assert db.buildings["radar"].consumes_electricity is True

    assert db.buildings["offshore-pump"].is_water_extractor is True
    assert db.buildings["pumpjack"].is_fluid_extractor is True
    assert {b.name for b in db.buildings_with_tag("is_ground_extractor")} == {
        "burner-mining-drill",
        "electric-mining-drill",
    }


def test_dump_reel_tags_s2_logistique():
    """§2 (docs/tags.md §2) : belts, trieurs, bras, tuyaux et stockage."""
    dump = json.loads(DATA.read_text(encoding="utf-8"))
    db = load_db_from_dump(dump)

    assert len(db.buildings_with_tag("is_belt")) == 3
    assert len(db.buildings_with_tag("is_underground_belt")) == 3
    assert len(db.buildings_with_tag("is_splitter")) == 3
    assert len(db.buildings_with_tag("is_inserter")) == 5
    assert {b.name for b in db.buildings_with_tag("is_pipe")} == {"pipe"}
    assert {b.name for b in db.buildings_with_tag("is_pipe_to_ground")} == {"pipe-to-ground"}
    assert len(db.buildings_with_tag("is_fluid_transport")) == 2

    assert db.buildings["wooden-chest"].is_chest is True
    assert len(db.buildings_with_tag("is_logistics_chest")) == 5
    assert len(db.buildings_with_tag("is_storage")) == 21
    assert db.buildings["roboport"].is_roboport is True
    assert db.buildings["logistic-robot"].is_robot is True
    assert db.buildings["construction-robot"].is_robot is True
    # Le robot de combat est une unité OFFENSIVE distincte (is_combat_robot
    # §7) : jamais confondu avec l'infra robot (logistic/construction).
    assert db.buildings["defender"].is_robot is False


def test_dump_reel_tags_s3_train_vehicules():
    """§3 (docs/tags.md §3) : rails, signals, gare, loco, wagons, véhicules."""
    dump = json.loads(DATA.read_text(encoding="utf-8"))
    db = load_db_from_dump(dump)

    assert len(db.buildings_with_tag("is_rail")) == 10
    assert len(db.buildings_with_tag("is_rail_signal")) == 2
    assert db.buildings["train-stop"].is_train_stop is True
    assert db.buildings["locomotive"].is_locomotive is True
    assert db.buildings["dummy-rail-support"].is_rail_support is True
    assert db.buildings["spidertron"].is_spider_vehicle is True
    assert {b.name for b in db.buildings_with_tag("is_wagon")} == {
        "artillery-wagon",
        "cargo-wagon",
        "fluid-wagon",
    }
    # Les décors de crash (-remnants) ne sont pas des voies.
    assert db.buildings["straight-rail-remnants"].is_rail is False
    for n in ("car", "tank", "spidertron", "locomotive", "cargo-wagon"):
        assert db.buildings[n].is_vehicle is True, n


def test_dump_reel_tags_s4_s5_s6_production_energie_extraction():
    """§4/§5/§6 (docs/tags.md §4/§5/§6) : ateliers spécialisés, chaudière vs
    échangeur, extraction par médium."""
    dump = json.loads(DATA.read_text(encoding="utf-8"))
    db = load_db_from_dump(dump)

    assert len(db.buildings_with_tag("is_furnace")) == 3
    # character fabrique à la main (catégorie 'crafting') : atelier en plus.
    assert len(db.buildings_with_tag("is_assembler")) == 4
    assert db.buildings["chemical-plant"].is_chemical_plant is True
    assert db.buildings["oil-refinery"].is_refinery is True
    assert db.buildings["centrifuge"].is_centrifuge is True
    assert db.buildings["rocket-silo"].is_rocket_parts_crafter is True

    assert db.buildings["boiler"].is_boiler is True
    assert db.buildings["boiler"].is_heat_exchanger is False
    assert db.buildings["heat-exchanger"].is_heat_exchanger is True
    assert db.buildings["heat-exchanger"].is_boiler is False
    assert db.buildings["solar-panel"].is_solar is True
    assert db.buildings["nuclear-reactor"].is_reactor is True
    assert db.buildings["heat-pipe"].is_heat_transport is True
    assert db.buildings["burner-generator"].is_burner_generator is True

    assert len(db.buildings_with_tag("is_mining_drill")) == 3
    assert db.buildings["pumpjack"].is_pumpjack is True
    assert db.buildings["offshore-pump"].is_offshore_pump is True
    assert db.buildings["pump"].is_well_pump is True


def test_detection_par_types_pas_par_noms():
    """Les tags §1-§6 sont détectés par TYPE d'entité / CAPACITÉS (jamais par
    nom de prototype) : on simule des prototypes de mod homonymes."""
    pole = tag_parse_entity(
        "custom-pole", {"type": "electric-pole", "supply_area_distance": 3}
    )
    assert pole.is_power_pole is True
    assert pole.is_distribution is True
    assert pole.is_beacon is False

    bcn = tag_parse_entity(
        "custom-beacon",
        {"type": "beacon", "supply_area_distance": 3, "energy_source": {"type": "electric"}},
    )
    assert bcn.is_beacon is True
    assert bcn.is_power_pole is False

    rail = tag_parse_entity("custom-rail", {"type": "curved-rail-a"})
    assert rail.is_rail is True
    wreck = tag_parse_entity("custom-wreck", {"type": "rail-remnants"})
    assert wreck.is_rail is False

    drill = tag_parse_entity(
        "custom-drill", {"type": "mining-drill", "resource_categories": ["basic-solid"]}
    )
    assert drill.is_ground_extractor is True
    assert drill.is_pumpjack is False
    rig = tag_parse_entity(
        "custom-rig", {"type": "mining-drill", "resource_categories": ["basic-fluid"]}
    )
    assert rig.is_pumpjack is True
    assert rig.is_fluid_extractor is True
    pump = tag_parse_entity(
        "custom-pump",
        {
            "type": "offshore-pump",
            "pumping_speed": 20,
            "fluidboxes": {"input": 0, "output": 1, "detail": {"1": {"production_type": "output"}}},
        },
    )
    assert pump.is_offshore_pump is True
    assert pump.is_water_extractor is True

    hx = tag_parse_entity(
        "custom-hx",
        {
            "type": "boiler",
            "energy_source": {"type": "heat"},
            "fluidboxes": {"input": 1, "output": 1},
        },
    )
    assert hx.is_heat_exchanger is True
    assert hx.is_boiler is False
    cauldron = tag_parse_entity("custom-boiler", {"type": "boiler", "energy_source": {"type": "burner"}})
    assert cauldron.is_boiler is True
    assert cauldron.is_heat_exchanger is False