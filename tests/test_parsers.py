"""Tests du classement fonctionnel des bâtiments (§5.1) : le type « recherche »
est réservé aux labs, les accumulateurs ne sont jamais des générateurs."""

from __future__ import annotations

from tool.common.db import VanillaDB
from tool.parsers.vanilla import _parse_entity, load_db_from_dump


def test_lab_classe_en_recherche():
    entity = {
        "type": "lab",
        "energy_source": {"type": "electric", "usage_priority": "secondary-input"},
        "energy_usage": "150kW",
        "lab_inputs": ["automation-science-pack"],
    }
    bdef = _parse_entity("lab", entity)
    assert bdef is not None
    assert bdef.functional_type == "research"
    assert bdef.directives["lab_inputs"] == ("automation-science-pack",)


def test_lab_jamais_atelier_ni_generateur():
    entity = {
        "type": "lab",
        "energy_source": {"type": "electric", "usage_priority": "secondary-input"},
        "lab_inputs": ["automation-science-pack"],
    }
    bdef = _parse_entity("lab", entity)
    assert bdef.crafting_categories == ()
    assert not bdef.fluid_outputs


def test_accumulateur_pas_generateur():
    entity = {
        "type": "accumulator",
        "energy_source": {"type": "electric", "usage_priority": "tertiary"},
        "max_power_output": 300000.0,
    }
    bdef = _parse_entity("accumulator", entity)
    assert bdef.functional_type != "generator"


def test_batiment_recherche_dans_db():
    dump = {
        "meta": {},
        "items": {},
        "fluids": {},
        "entities": {
            "lab": {
                "type": "lab",
                "energy_source": {"type": "electric"},
                "lab_inputs": ["automation-science-pack"],
            }
        },
        "recipes": {},
    }
    db: VanillaDB = load_db_from_dump(dump)
    assert [b.name for b in db.buildings_of_type("research")] == ["lab"]