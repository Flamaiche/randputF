"""Modèle « chaleur » (docs/energie.md §10bis, docs/tags.md §5bis) : un consommateur de
chaleur (heat-exchanger) ne doit JAMAIS être débloqué avant sa SOURCE
(nuclear-reactor) ni son TRANSPORT (heat-pipe). La garantie est posée « à la
volée » par `recursive_phase._ensure_heat_prereq` au premier sink qui reçoit
sa recette fluide→fluide : les unlock de la triade sont STRICTEMENT antérieurs,
par construction, et jamais fusionnés dans la tech du consommateur (steps
isolés)."""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path

import pytest

from tool.common.demo import build_demo_db
from tool.generator.heat import find_heat_roles
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))

SEEDS = (0, 5, 36, 43, 57)


def test_tags_chaleur_source_transport_consommateur():
    """La détection PAR CAPACITÉS (jamais de liste de noms en dur) distingue la
    SOURCE (produit la chaleur : energy burner + has_heat_output), le TRANSPORT
    (heat-pipe) et le CONSOMMATEUR (energy_source 'heat'). ``produces_heat``
    est restreint à la source : la heat-pipe et l'échangeur ne le portent plus
    (l'ancien `has_heat_output` ratissait tout ce qui touche au heat)."""
    reactor = DB.buildings["nuclear-reactor"]
    hx = DB.buildings["heat-exchanger"]
    pipe = DB.buildings["heat-pipe"]
    assert reactor.is_heat_source and not reactor.is_heat_sink
    assert hx.is_heat_sink and not hx.is_heat_source
    assert pipe.is_heat_transport and not pipe.is_heat_source and not pipe.is_heat_sink
    assert reactor.produces_heat
    assert not hx.produces_heat
    assert not pipe.produces_heat
    assert "heat-interface" not in DB.buildings  # junk sandbox exclu


def test_roles_chaleur_sur_le_dump():
    roles = find_heat_roles(DB)
    assert roles == {
        "sources": ["nuclear-reactor"],
        "transports": ["heat-pipe"],
        "sinks": ["heat-exchanger"],
    }


def test_modele_inerte_sans_consommateur():
    """Le modèle heat est INERTE sans sink : aucun rôle détecté, aucune
    contrainte ajoutée par find_heat_roles sur un pool sans consommateur."""
    db = build_demo_db()
    assert find_heat_roles(db) == {"sources": [], "transports": [], "sinks": []}


@pytest.fixture(scope="module")
def seeds():
    out = {}
    for s in SEEDS:
        db = copy.deepcopy(DB)
        db.seed_value = s
        out[s] = generate_seed(db)
    return out


def _unlock_index(techs: list[dict], prefix: str) -> int | None:
    """Indice (position dans l'arbre) de la PREMIÈRE tech qui débloque une
    recette commençant par ``prefix``."""
    for i, t in enumerate(techs):
        for e in t.get("effects", []) or []:
            if e.get("type") == "unlock-recipe" and e["recipe"].startswith(prefix):
                return i
    return None


@pytest.mark.parametrize("seed", SEEDS)
def test_consommateur_debloque_apres_source_et_transport(seeds, seed):
    """TRIADE garantie : dès qu'un consommateur de chaleur est unlocké (sa
    recette fluide→fluide randputf-heat-exchanger-*), la SOURCE et le
    TRANSPORT sont unlockés à des techs STRICTEMENT antérieures — sinon
    l'échangeur réclamerait du heat réseau sans aucun moyen d'en produire
    ni de le transporter (suite infaisable)."""
    seed_val = seeds[seed]
    techs = seed_val["technologies"]
    sink = _unlock_index(techs, "randputf-heat-exchanger-")
    assert sink is not None, "le heat-exchanger (sink) doit exister dans la seed"
    source = _unlock_index(techs, "randputf-nuclear-reactor")
    transport = _unlock_index(techs, "randputf-heat-pipe")
    assert source is not None, "un heat source doit être débloqué"
    assert transport is not None, "un heat transport doit être débloqué"
    assert source < sink, f"source (tech {source}) après le consommateur (tech {sink})"
    assert transport < sink, f"transport (tech {transport}) après le consommateur (tech {sink})"


def test_roles_items_obtenables_avant_consommateur(seeds):
    """Les recettes de la source et du transport générées par la garantie sont
    bien POSÉES dans la seed (jamais orphelines) avant le consommateur."""
    seed0 = seeds[SEEDS[0]]
    recipes = {r["name"]: r for r in seed0["recipes"]}
    assert "randputf-nuclear-reactor" in recipes
    assert "randputf-heat-pipe" in recipes
    unlocked = defaultdict(set)
    for t in seed0["technologies"]:
        for e in t.get("effects", []) or []:
            if e.get("type") == "unlock-recipe":
                unlocked[e["recipe"]].add(t["id"])
    assert "randputf-nuclear-reactor" in unlocked
    assert "randputf-heat-pipe" in unlocked