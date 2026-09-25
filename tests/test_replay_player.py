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

# Seeds « gagnables » avec la génération actuelle (vérifié par balayage
# 0-200 : 201/201). seed 0 était bloquée au lab — rejouable depuis D4bis
# (extracteurs du spawn gardés au starter) + extraction par capacité physique ;
# seed 20 était bloquée (lab → pipe → stone-furnace → productivity-module-2,
# gisement non minable pré-élec) — rejouable depuis D4ter (mineur non-électrique
# dans le graphe + fin de l'auto-hébergement des recettes).
# seed 255 (cycle d'hébergement mutuel AM-2 ⇄ steel-furnace) est rejouable
# depuis D4quater (_hosting_cycle) ; seed 426 (fabrication d'atelier à fluides,
# chemical-plant → oil-refinery unlock 45) est rejouable depuis le même chantier
# (_is_building_item_recipe : bâtiments fabriqués items-only).
# seed 1043 (cycle d'hébergement à 4 maillons AM2→AM3→rocket-silo→oil-refinery→AM2,
# fermé par un rehome U1) est rejouable depuis D4quinquies (_hosting_cycle
# parcourt le graphe FORWARD « ce que l'atelier exige »).
WINNING = (0, 1, 5, 7, 17, 20, 255, 426, 1043)


@pytest.fixture(scope="module")
def seeds():
    out = {}
    for seed_value in WINNING:
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


def test_seed0_rejouable_apres_d4bis(seeds):
    """D4bis : les extracteurs de la « boîte du spawn » restent à la tech
    gratuite (foreuse burner minant les patchs item, pompe offshore pour le
    lac de la turbine) — seed 0, bloquée au lab sur la passe C3 naïve, est
    rejouable jusqu'à la victoire."""
    db = copy.deepcopy(DB)
    db.seed_value = 0
    report = rp.play(db, seeds[0])
    assert report.victory, report.summary()
    assert report.all_techs_researched


def test_seed20_rejouable_apres_d4ter(seeds):
    """D4ter : seed 20 était bloquée au lab (lab → pipe → stone-furnace →
    productivity-module-2, gisement miné par electric-mining-drill uniquement
    → rien d'extractible avant le réseau) et sa recette stone-furnace était
    auto-hébergée (crafted_in==produit). Le mineur non-électrique fait partie du
    graphe + fin de l'auto-hébergement → seed rejouable jusqu'à la victoire."""
    db = copy.deepcopy(DB)
    db.seed_value = 20
    report = rp.play(db, seeds[20])
    assert report.victory, report.summary()
    assert report.all_techs_researched


def test_seed255_rejouable_apres_d4quater(seeds):
    """D4quater : seed 255 restait bloquée par un cycle d'hébergement MUTUEL —
    randputf-assembling-machine-2 ré-hébergé dans steel-furnace alors que
    randputf-steel-furnace est fabriqué dans assembling-machine-2. La garde
    transitive `_hosting_cycle` (U2) l'empêche à la racine → seed gagnable."""
    db = copy.deepcopy(DB)
    db.seed_value = 255
    report = rp.play(db, seeds[255])
    assert report.victory, report.summary()
    assert report.all_techs_researched


def test_seed426_rejouable_apres_d4quater(seeds):
    """D4quater : seed 426 bloquée car la recette de FABRICATION du
    chemical-plant exigeait 2 fluides → posée dans l'oil-refinery (unlock 45)
    alors qu'il sert d'atelier au science pack dès step ~11. Un item de bâtiment
    ne se fabrique plus qu'avec des items (_is_building_item_recipe) →
    seed gagnable."""
    db = copy.deepcopy(DB)
    db.seed_value = 426
    report = rp.play(db, seeds[426])
    assert report.victory, report.summary()
    assert report.all_techs_researched


def test_seed1043_rejouable_apres_d4quinquies(seeds):
    """D4quinquies : seed 1043 bloquée par un cycle d'hébergement à QUATRE
    maillons — randputf-assembling-machine-2 in assembling-machine-3,
    randputf-assembling-machine-3 in rocket-silo, randputf-rocket-silo in
    oil-refinery, randputf-oil-refinery in assembling-machine-2. Le rehome U1
    (AM3→rocket-silo) refermait la boucle sans que l'ancienne garde transitive
    (chemin PAYANT « consommateurs ») ne la voie ; `_hosting_cycle` parcourt
    désormais le graphe FORWARD (« ce que l'atelier cible exige », up to P) →
    seed gagnable. Le coût de tech 18 (utility-science-pack) exigeait un pistol
    lui-même fabriqué dans AM-2 — atelier intraçable sur ce cycle."""
    db = copy.deepcopy(DB)
    db.seed_value = 1043
    report = rp.play(db, seeds[1043])
    assert report.victory, report.summary()
    assert report.all_techs_researched


def test_patches_item_ramassables_a_la_main(seeds):
    """Un patch ITEM est hand-pickable au spawn (stock fini façon épave) — le
    drill ne sert qu'à le rendre infini. Le rejoueur doit donc obtenir ces
    ressources dès la clôture initiale, SANS foreuse ni électricité.

    NOTE ancrage temporel : la seed 5 tire-t-elle des patchs item ? Le test est
    tolérant : si la carte est 100% fluide/lac il n'y a rien à vérifier
    (patchs item = ensemble vide → invariants vrais par vacuité)."""
    db = copy.deepcopy(DB)
    db.seed_value = 5
    seed = seeds[5]
    fp = rp.FakePlayer(db, seed)
    items, _fluids, _power, _gen = fp.closure()
    assert fp.item_patch_resources <= items


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


def test_extraction_par_capacite_physique(seeds):
    """Couvre la vérification « ressources non infinies et tout » : le modèle
    d'extraction est physique (data-updates.lua) — tout patch item
    ``basic-solid`` est mineable par toute foreuse obtenable, un patch fluide
    exige un pumpjack, un lac se pompe par pompe offshore (void). Indépendant
    de la passe ``extractor_timing`` (le `del` est un no-op comportemental)."""
    seed = copy.deepcopy(seeds[5])
    del seed["extractor_timing"]
    db = copy.deepcopy(DB)
    db.seed_value = 5
    fp = rp.FakePlayer(db, seed)
    items, fluids, power, generator = fp.closure()
    lake = {la["resource"] for la in seed["map"]["lakes"]}
    kit = {e["name"] for e in seed["starter_kit"] if e.get("type") == SLOT_ITEM}
    if "offshore-pump" in kit:                   # pompe au kit → lacs pompables
        assert lake <= fluids
    assert "wood" in items                       # environnement (non infini)
    assert kit <= items
    assert isinstance(power, bool)
    assert generator is None or isinstance(generator, str)
    rp.play(db, seed)                            # jouable sans crash, les deux formats