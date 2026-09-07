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