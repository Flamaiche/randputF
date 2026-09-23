"""Rejoueur « fake player » : tests du simulateur de partie.

Un joueur simulé rejoue la seed : chaque tech est recherchée dès que son coût
(pack / déclencheur prologue) est produisible — extraction (patchs/lacs),
électricité (générateur obtenable + pylône), combustible/chaleur selon le
bâtiment, ateliers et kit inclus. La victoire = chaîne fusée atteignable.

NOTE ancrage temporel : la génération actuelle ne garantit pas encore le
bootstrap pour ~50% des graines (softlock lab/spawn). Les seeds ci-dessus
(1, 5, 7, 17) passent aujourd'hui ; ``test_seed0_bloquee_detectee`` documente
la sensibilité du rejoueur et DOIT être révisée quand la génération sera
corrigée (seed 0 rejouable → assertion inversée).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tool.common.db import SLOT_ITEM
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump
from tool.replay import player as rp

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))

# Seeds « gagnables » avec la génération actuelle (vérifié par balayage).
WINNING = (1, 5, 7, 17)


@pytest.fixture(scope="module")
def seeds():
    out = {}
    for seed_value in (0, *WINNING):
        db = copy.deepcopy(DB)
        db.seed_value = seed_value
        out[seed_value] = generate_seed(db, {"seed": seed_value}, validate=False)
    return out


def test_seeds_connues_gagnables(seeds):
    for seed_value in WINNING:
        db = copy.deepcopy(DB)
        db.seed_value = seed_value
        report = rp.play(db, seeds[seed_value])
        assert report.victory, f"seed {seed_value}: {report.summary()}"
        assert report.all_techs_researched, seed_value
        assert report.researched == report.total_techs


def test_seed0_bloquee_au_lab_detectee(seeds):
    """Sensibilité du rejoueur : il DÉTECTE le softlock réel de seed 0 (le lab
    gratuit exige un steel-furnace → exoskeleton-equipment, item profond).
    À inverser quand la génération garantira un bootstrap jouable."""
    db = copy.deepcopy(DB)
    db.seed_value = 0
    report = rp.play(db, seeds[0])
    assert not report.victory
    assert report.blocker is not None
    assert report.blocker.item == "lab"


def test_victoire_donne_les_items_fusee(seeds):
    for seed_value in WINNING:
        db = copy.deepcopy(DB)
        db.seed_value = seed_value
        report = rp.play(db, seeds[seed_value])
        assert set(rp.VICTORY_ITEMS) <= report.obtainable_items, seed_value


def test_closure_est_un_point_fixe_deterministe(seeds):
    """Deux clôtures successives au même état → identiques (le rejoueur est
    déterministe, pas de course entre extracteurs / électricité / recettes)."""
    db = copy.deepcopy(DB)
    db.seed_value = 5
    fp = rp.FakePlayer(db, seeds[5])
    a = fp.closure()
    b = fp.closure()
    assert a == b
    assert "lab" in a[0]          # le lab pur starter est déjà modelé
    assert isinstance(a[2], bool)  # (items, fluids, power, generator)


def test_fermeture_initiale_respecte_les_sources(seeds):
    """Kit, environnement et lacs sont des sources au départ — pas de craft."""
    db = copy.deepcopy(DB)
    db.seed_value = 5
    seed = seeds[5]
    fp = rp.FakePlayer(db, seed)
    items, fluids, _, _ = fp.closure()
    kit = {e["name"] for e in seed["starter_kit"] if e.get("type") == SLOT_ITEM}
    assert kit <= items
    for la in seed["map"]["lakes"]:
        assert la["resource"] in fluids


def test_explication_de_blocage_bornee(seeds):
    """L'explication d'un blocage est bornée (jamais de récursion infinie)."""
    reason = seeds[0]
    db = copy.deepcopy(DB)
    db.seed_value = 0
    fp = rp.FakePlayer(db, reason)
    items, fluids, power, _ = fp.closure()
    txt = fp.explain("exoskeleton-equipment", items, fluids, power)
    assert isinstance(txt, str)
    assert 0 < len(txt) < 500
    # Un item déjà obtenable n'a pas d'explication « manquant ».
    assert "déjà obtenu" in fp.explain("wood", items, fluids, power)


def test_generateur_et_electricite_modelises(seeds):
    """Le réseau passe à OUI uniquement quand un générateur (produces_
    electricity) obtenable peut tourner + un pylône obtenable."""
    db = copy.deepcopy(DB)
    db.seed_value = 5
    seed = seeds[5]
    fp = rp.FakePlayer(db, seed)
    report = fp.play()
    assert report.power_available
    gen = report.power_generator
    assert gen is not None
    b = DB.buildings[gen]
    assert b.produces_electricity
    if getattr(b, "fluid_inputs", 0) > 0:
        assign = seed.get("building_fluid_assignments", {}).get(gen, {})
        inp = assign.get("input")
        if inp:
            assert inp in report.obtainable_fluids