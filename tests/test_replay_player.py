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

from tool.common.db import SLOT_ITEM, ItemDef
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump
from tool.replay import player as rp

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))

# Seeds « gagnables » avec la génération actuelle (vérifié par balayage
# 0-200 sous joueur ensembliste : 201/201 ; sous joueur QUANTITATIF : 165/201).
# seed 0 était bloquée au lab — rejouable depuis D4bis (extracteurs du spawn
# gardés au starter) + extraction par capacité physique ; seed 20 était bloquée
# (lab → pipe → stone-furnace → productivity-module-2, gisement non minable
# pré-élec) — rejouable depuis D4ter (mineur non-électrique dans le graphe + fin
# de l'auto-hébergement des recettes).
# seed 255 (cycle d'hébergement mutuel AM-2 ⇄ steel-furnace) est rejouable
# depuis D4quater (_hosting_cycle) ; seed 426 (fabrication d'atelier à fluides,
# chemical-plant → oil-refinery unlock 45) est rejouable depuis le même chantier
# (_is_building_item_recipe : bâtiments fabriqués items-only).
# seed 7 était BLOQUÉE depuis le rejoueur quantitatif (D5) : cost space-science-pack
# (idx 5) exigeant ~20 pumpjacks hors kit alors que randputf-pumpjack était unlockée
# à idx 9 (C3 ne voyait que la consommation de la ressource extraite, jamais l'item
# extracteur consommé comme ingrédient — offshore-pump en veut dès idx 0). Corrigé
# par C3 (borne item-as-ingrédient) → seed 7 rejouable.
# seed 1043 (cycle d'hébergement à 4 maillons) est de nouveau BLOQUÉE depuis le
# rejoueur quantitatif (D5) : la recette de fabrication de l'electric-mining-drill
# est unlockée au tech idx 32 alors que la chaîne du military-science-pack (idx 4)
# exige ≈32 EMD hors du kit (frappée en quantité, pas en présence).
WINNING = (0, 1, 5, 7, 17, 20, 255, 426)


@pytest.fixture(scope="module")
def seeds():
    out = {}
    for seed_value in WINNING + (7, 1043):
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


def test_residu_de_combustion_obtenable_des_le_spawn(seeds):
    """Le charbon posé en patch produit son ``burnt_result`` sans recette.

    Le dump moddé porte ``burnt_result`` sur le charbon (→ ash). Le joueur
    peut miner ce patch à la main puis brûler le charbon : le résidu doit
    entrer dans la clôture dès le spawn, sans atelier ni technologie.
    """
    dump = json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text())
    dump["items"]["test-ash"] = copy.deepcopy(dump["items"]["stone"])
    dump["items"]["coal"]["burnt_result"] = "test-ash"
    db = load_db_from_dump(dump)
    db.seed_value = 5
    seed = copy.deepcopy(seeds[5])
    seed["map"]["patches"].append({"kind": SLOT_ITEM, "resource": "coal"})

    fp = rp.FakePlayer(db, seed)
    items, _fluids, _power, _generator = fp.closure()

    assert "coal" in items
    assert "test-ash" in items
    assert fp._craft("test-ash", 2)


def test_seed1043_gagnable_apres_regen_extracteur(seeds):
    """C3 + régénération : la seed 1043 était bloquée en QUANTITÉ — le
    military-science-pack (tech idx 4) requiert ≈32 electric-mining-drills dont
    la recette était unlockée au tech idx 32 dans ``steel-furnace`` (elle-même
    ingrédient de la recette : rien à faire avant). L'extracteur étant requis
    au spawn, sa recette est RÉGÉNÉRÉE au jalon du besoin (§C3) : re-tirée
    dans le watershed pré-électrique et rendue craftable à la main → seed
    gagnable."""
    db = copy.deepcopy(DB)
    db.seed_value = 1043
    report = rp.play(db, seeds[1043])
    assert report.victory, report.summary()
    assert report.all_techs_researched


def test_seed7_rejouable_apres_c3_item_ingredient(seeds):
    """C3 : seed 7 était bloquée en QUANTITÉ — l'item extracteur pumpjack,
    consommé comme ingrédient par offshore-pump dès le starter, était unlocké
    au tech idx 9 car sa ressource extraite (lubricant/heavy-oil) n'était
    consommée qu'en profondeur. La borne « item consommé comme ingrédient »
    ramène le craft à temps → seed 7 rejouable jusqu'à la victoire."""
    db = copy.deepcopy(DB)
    db.seed_value = 7
    report = rp.play(db, seeds[7])
    assert report.victory, report.summary()
    assert report.all_techs_researched


def test_victoire_donne_les_items_fusee(seeds):
    """La chaîne de lancement est DÉRIVÉE des faits du dump
    (db.rocket_chain) : les items exigés par la victoire sont obtenables
    sur toutes les seeds gagnantes — sans aucun nom en dur côté test."""
    for seed_value in WINNING:
        db = copy.deepcopy(DB)
        db.seed_value = seed_value
        report = rp.play(db, seeds[seed_value])
        assert set(db.rocket_chain["victory_items"]) <= report.obtainable_items, seed_value


def test_le_joueur_fabrique_reellement_la_chaine(seeds):
    """Le rejoueur ne se contente pas d'une OBTENABILITÉ de fin : il a
    VRAIMENT fabriqué la chaîne de lancement DÉRIVÉE du dump (silo +
    ingrédients des recettes de fusée), un bâtiment de recherche, et
    récupéré les produits de lancement quand la seed les exige.

    Dans une seed modpack, ``space-science-pack`` n'est pas un produit de
    lancement mais une RECETTE générée (ex. utility-pack + rocket-launcher) :
    « récupérer les packs » = les fabriquer jusqu'à la maîtrise (10×) pour
    payer les techs et les recettes aval qui les consomment."""
    for seed_value in WINNING:
        db = copy.deepcopy(DB)
        db.seed_value = seed_value
        seed = seeds[seed_value]
        fp = rp.FakePlayer(db, seed)
        report = fp.play()
        assert report.victory, seed_value
        labs = sorted(b.name for b in db.buildings.values() if b.is_research)
        assert labs, "la base doit exposer un bâtiment de recherche (is_research)"
        chain = db.rocket_chain
        for item in (*chain["victory_items"], labs[0]):
            assert fp.had[item] > 0, (seed_value, item)
        for product in chain["launch_products"]:
            assert fp.had[product] > 0, (seed_value, product)
            assert product in fp.mastered, (seed_value, product)


def test_rejeu_remonte_le_nombre_de_techs_recherchees(seeds):
    seed_value = WINNING[0]
    db = copy.deepcopy(DB)
    db.seed_value = seed_value
    events = []
    report = rp.FakePlayer(db, seeds[seed_value]).play(
        lambda percent, researched, total: events.append((percent, researched, total))
    )

    assert report.victory
    assert events
    assert all(0 <= researched <= total for _, researched, total in events)
    assert events[-1] == (100, report.researched, report.total_techs)
    assert any(researched for _, researched, _ in events[:-1])


def test_cloture_inclut_les_produits_de_lancement(seeds):
    db = copy.deepcopy(DB)
    db.seed_value = 5
    fp = rp.FakePlayer(db, seeds[5])
    fp.launch_buildings = []
    fp.rocket_part_product = "offshore-pump"
    fp.rocket_parts_required = 1
    fp.launch_requirements = {
        "produit-de-lancement": {"item": "offshore-pump", "amount": 1}
    }

    items, fluids, power, _ = fp.closure()

    assert "offshore-pump" in items
    assert "produit-de-lancement" in items


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


def test_explication_quantifie_les_fluides_par_leur_vraie_sortie():
    """Le diagnostic d'un fluide absent doit trouver ses producteurs et diviser
    par le rendement réel (pas 1), même s'il n'est pas encore dans la fermeture."""
    from collections import Counter

    from tool.common.demo import build_demo_db

    db = build_demo_db()
    recipe = {
        "name": "demo-vapeur",
        "ingredients": [{"type": "fluid", "name": "water", "amount": 1}],
        "results": [{"type": "fluid", "name": "steam-demo", "amount": 100}],
        "crafted_in": None,
    }
    seed = {
        "meta": {},
        "recipes": [recipe],
        "technologies": [],
        "map": {"patches": [], "lakes": []},
        "pools": {"raw_resources": []},
    }
    fp = rp.FakePlayer(db, seed)
    fp.unlocked.add(recipe["name"])

    txt = fp._explain_qty(
        "steam-demo", 100, Counter(), (set(), set()), set(), set(), True, 0
    )

    assert "steam-demo×100 (demo-vapeur)" in txt
    assert "water×1" in txt


def test_explication_detecte_un_cycle_de_fabrication():
    from collections import Counter

    from tool.common.demo import build_demo_db

    db = build_demo_db()
    seed = {
        "meta": {},
        "recipes": [
            {
                "name": "demo-a",
                "ingredients": [{"type": "item", "name": "demo-b", "amount": 1}],
                "results": [{"type": "item", "name": "demo-a", "amount": 1}],
                "crafted_in": None,
            },
            {
                "name": "demo-b",
                "ingredients": [{"type": "item", "name": "demo-a", "amount": 1}],
                "results": [{"type": "item", "name": "demo-b", "amount": 1}],
                "crafted_in": None,
            },
        ],
        "technologies": [],
        "map": {"patches": [], "lakes": []},
        "pools": {"raw_resources": []},
    }
    fp = rp.FakePlayer(db, seed)
    fp.unlocked.update({"demo-a", "demo-b"})

    txt = fp._explain_qty(
        "demo-a", 1, Counter(), (set(), set()), set(), set(), True, 0
    )

    assert "cycle de fabrication" in txt


def _cycle_demo_seed(starter: list[dict]) -> dict:
    return {
        "meta": {},
        "recipes": [
            {
                "name": "demo-fer",
                "ingredients": [
                    {"type": "item", "name": "copper-plate", "amount": 1},
                    {"type": "item", "name": "iron-plate", "amount": 1},
                ],
                "results": [{"type": "item", "name": "iron-plate", "amount": 3}],
                "crafted_in": None,
            },
            {
                "name": "demo-cuivre",
                "ingredients": [{"type": "item", "name": "iron-plate", "amount": 1}],
                "results": [{"type": "item", "name": "copper-plate", "amount": 1}],
                "crafted_in": None,
            },
        ],
        "technologies": [],
        "map": {"patches": [], "lakes": []},
        "pools": {"raw_resources": []},
        "starter_kit": starter,
    }


def test_cycle_positif_avec_starter_devient_source_infinie():
    from collections import Counter

    from tool.common.demo import build_demo_db

    db = build_demo_db()
    seed = _cycle_demo_seed(
        [{"name": "iron-plate", "type": "item", "count": 1}]
    )
    fp = rp.FakePlayer(db, seed)
    fp.unlocked.update({"demo-fer", "demo-cuivre"})
    fp._invalidate_caches()

    items, fluids, power, _ = fp.closure()
    fp._world_items, fp._world_fluids, fp._world_power = items, fluids, power
    inf = fp._infinite_items(items, fluids, power)
    assert "iron-plate" not in inf[0]

    assert fp._craft("iron-plate", 25)
    assert "iron-plate" in fp._cycle_infinite_items
    assert "copper-plate" in fp._cycle_infinite_items

    txt = fp._explain_qty(
        "iron-plate", 25, Counter(), (set(), set()), items, fluids, power, 0
    )
    assert "cycle productif" in txt


def test_cycle_positif_avec_multiplicateurs_de_recette():
    from tool.common.demo import build_demo_db

    seed = {
        "meta": {},
        "recipes": [
            {
                "name": "demo-a",
                "ingredients": [
                    {"type": "item", "name": "copper-plate", "amount": 2},
                    {"type": "item", "name": "steel-plate", "amount": 10},
                ],
                "results": [{"type": "item", "name": "iron-plate", "amount": 8}],
                "crafted_in": None,
            },
            {
                "name": "demo-b",
                "ingredients": [
                    {"type": "item", "name": "iron-plate", "amount": 1}
                ],
                "results": [{"type": "item", "name": "copper-plate", "amount": 50}],
                "crafted_in": None,
            },
            {
                "name": "demo-c",
                "ingredients": [
                    {"type": "item", "name": "copper-plate", "amount": 2}
                ],
                "results": [{"type": "item", "name": "steel-plate", "amount": 1}],
                "crafted_in": None,
            },
        ],
        "technologies": [],
        "map": {"patches": [], "lakes": []},
        "pools": {"raw_resources": []},
        "starter_kit": [{"name": "iron-plate", "type": "item", "count": 1}],
    }
    fp = rp.FakePlayer(build_demo_db(), seed)
    fp.unlocked.update({"demo-a", "demo-b", "demo-c"})
    fp._invalidate_caches()

    items, fluids, power, _ = fp.closure()
    fp._world_items, fp._world_fluids, fp._world_power = items, fluids, power
    inf = fp._infinite_items(items, fluids, power)
    assert "iron-plate" not in inf[0]

    assert fp._craft("iron-plate", 100)
    assert {"iron-plate", "copper-plate", "steel-plate"} <= fp._cycle_infinite_items


def test_cycle_positif_avec_starter_externe_catalyseur():
    from tool.common.demo import build_demo_db

    seed = {
        "meta": {},
        "recipes": [
            {
                "name": "demo-a",
                "ingredients": [
                    {"type": "item", "name": "copper-plate", "amount": 2}
                ],
                "results": [{"type": "item", "name": "iron-plate", "amount": 3}],
                "crafted_in": None,
            },
            {
                "name": "demo-b",
                "ingredients": [
                    {"type": "item", "name": "iron-plate", "amount": 1},
                    {"type": "item", "name": "stone", "amount": 1},
                ],
                "results": [
                    {"type": "item", "name": "copper-plate", "amount": 10},
                    {"type": "item", "name": "stone", "amount": 2},
                ],
                "crafted_in": None,
            },
        ],
        "technologies": [],
        "map": {"patches": [], "lakes": []},
        "pools": {"raw_resources": []},
        "starter_kit": [{"name": "stone", "type": "item", "count": 1}],
    }
    fp = rp.FakePlayer(build_demo_db(), seed)
    fp.unlocked.update({"demo-a", "demo-b"})
    fp._invalidate_caches()

    items, fluids, power, _ = fp.closure()
    fp._world_items, fp._world_fluids, fp._world_power = items, fluids, power
    inf = fp._infinite_items(items, fluids, power)
    assert "iron-plate" not in inf[0]
    assert "copper-plate" not in inf[0]

    assert fp._ensure_cycle_inf("iron-plate", inf, items, fluids, power)
    assert "iron-plate" in fp._cycle_infinite_items
    assert "copper-plate" in fp._cycle_infinite_items


def test_cycle_negatif_avec_starter_reste_bloquant():
    from tool.common.demo import build_demo_db

    db = build_demo_db()
    seed = {
        "meta": {},
        "recipes": [
            {
                "name": "demo-a",
                "ingredients": [{"type": "item", "name": "demo-b", "amount": 1}],
                "results": [{"type": "item", "name": "demo-a", "amount": 1}],
                "crafted_in": None,
            },
            {
                "name": "demo-b",
                "ingredients": [{"type": "item", "name": "demo-a", "amount": 1}],
                "results": [{"type": "item", "name": "demo-b", "amount": 1}],
                "crafted_in": None,
            },
        ],
        "technologies": [],
        "map": {"patches": [], "lakes": []},
        "pools": {"raw_resources": []},
        "starter_kit": [{"name": "demo-a", "type": "item", "count": 1}],
    }
    fp = rp.FakePlayer(db, seed)
    fp.unlocked.update({"demo-a", "demo-b"})
    fp._invalidate_caches()

    items, fluids, power, _ = fp.closure()
    fp._world_items, fp._world_fluids, fp._world_power = items, fluids, power
    inf = fp._infinite_items(items, fluids, power)
    assert not fp._ensure_cycle_inf("demo-a", inf, items, fluids, power)


def test_cycle_positif_sans_starter_reste_bloquant():
    from collections import Counter

    from tool.common.demo import build_demo_db

    db = build_demo_db()
    fp = rp.FakePlayer(db, _cycle_demo_seed([]))
    fp.unlocked.update({"demo-fer", "demo-cuivre"})
    fp._invalidate_caches()

    items, fluids, power, _ = fp.closure()
    fp._world_items, fp._world_fluids, fp._world_power = items, fluids, power
    inf = fp._infinite_items(items, fluids, power)
    assert not fp._ensure_cycle_inf("iron-plate", inf, items, fluids, power)

    txt = fp._explain_qty(
        "iron-plate", 25, Counter(), inf, items, fluids, power, 0
    )
    assert "cycle de fabrication" in txt
    assert not fp._cycle_infinite_items
    brief = fp.explain_qty("iron-plate", items, fluids, power, need=25)
    assert "cycle productif sans starter" in brief


def test_rejoueur_utilise_le_tag_environnemental_de_la_db():
    from tool.common.demo import build_demo_db

    db = build_demo_db()
    db.items["mod-fish"] = ItemDef(name="mod-fish", is_environmental=True)
    seed = {
        "meta": {},
        "recipes": [],
        "technologies": [],
        "map": {"patches": [], "lakes": []},
        "pools": {"raw_resources": []},
    }
    fp = rp.FakePlayer(db, seed)

    assert "mod-fish" in fp.base_infinite
    items, _fluids, _power, _generator = fp.closure()
    assert "mod-fish" in items


def test_message_de_blocage_est_court_et_explicite():
    blocker = rp.Blocker(
        "coal-mk02",
        "cost",
        "logistic-science-pack",
        "cottongut×12 : cycle de fabrication",
        previous="coal-mk01",
        done=142,
        attempted=7,
    )

    txt = str(blocker)

    assert "avant : coal-mk01 (142 techs recherchées)" in txt
    assert "blocage : coal-mk02" in txt
    assert "erreur : coût — logistic-science-pack" in txt
    assert "pourquoi : cottongut×12" in txt
    assert "7 tech(s) disponible(s) essayée(s)" in txt
    assert blocker.brief() == "coal-mk02:cost"


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


def test_declencheur_mine_entity_consomme_les_produits_du_dump(seeds):
    seed = copy.deepcopy(seeds[5])
    seed["entities"] = {}
    seed["entities"]["ae-ressource"] = {
        "type": "resource",
        "mineable_products": [{"name": "ae-minerai", "amount": 1}],
    }
    fp = rp.FakePlayer(copy.deepcopy(DB), seed)
    tech = {
        "research_trigger": {"type": "mine-entity", "entities": ["ae-ressource"]},
        "unit": {},
    }

    fp.fluids_obtainable = set()
    failed, _ = fp._evaluate_tech(tech, set(), set(), False)
    assert failed == "ae-ressource"

    fp.fluids_obtainable = {"ae-minerai"}
    assert fp._evaluate_tech(tech, set(), {"ae-minerai"}, False) == (None, None)


def test_mastery_sweep_est_un_point_fixe_deterministe(seeds):
    """Modèle « maîtrise » (faire chaque recette débloquée 10×, l'atelier étant
    recrafé à chaque passe ; had>=10 → item sûr/infini) : la passe est un point
    fixe déterministe et ne fabrique que via des recettes déjà débloquées."""
    db = copy.deepcopy(DB)
    db.seed_value = 5
    fp = rp.FakePlayer(db, seeds[5])
    items, fluids, power, _gen = fp.closure()
    fp._world_items, fp._world_fluids, fp._world_power = items, fluids, power
    unlocked0 = set(fp.unlocked)
    had0 = dict(fp.had)
    fp._mastery_sweep()
    a = (dict(fp.had), dict(fp.inv))
    fp._mastery_sweep()
    assert (dict(fp.had), dict(fp.inv)) == a            # point fixe (2e passe no-op)
    assert set(fp.unlocked) == unlocked0                # la passe ne débloque rien
    grown = [it for it in fp.had if fp.had[it] > had0.get(it, 0)]
    assert grown                                        # la passe a fabriqué quelque chose
    results = {r["name"]: [q["name"] for q in (r.get("results") or [])]
               for r in fp.recipes if r["name"] in unlocked0}
    assert all(any(it in results[r] for r in results) for it in grown)  # recettes débloquées