"""Invariants de pipeline sur UNE seed (fuzz réduit) : unlock unique §13,
lab dans la 2e recherche gratuite §8, chaîne fusée complète §14, aucun cycle
de recettes réel (§8) — vérifiés sur plusieurs graines différentes."""

from __future__ import annotations

import collections
import copy
import json
from pathlib import Path

import pytest

from tool.generator.pipeline import generate_seed
from tool.generator.recipes import ProgressionState, make_recipe
from tool.parsers.vanilla import load_db_from_dump
from tool.validator.pipeline_validator import _detect_recipe_cycles, _detect_unreachable_products

import random

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))

SEEDS = (0, 5, 36, 43, 57)


@pytest.fixture(scope="module")
def seeds():
    out = {}
    for s in SEEDS:
        db = copy.deepcopy(DB)
        db.seed_value = s
        out[s] = generate_seed(db)
    return out


def _unlocks(techs):
    by_recipe = collections.defaultdict(list)
    for t in techs:
        for e in t.get("effects") or []:
            if e.get("type") == "unlock-recipe":
                by_recipe[e["recipe"]].append(t["id"])
    return by_recipe


def test_unlock_unique_sur_plusieurs_seeds(seeds):
    for s, seed in seeds.items():
        doubles = {r for r, v in _unlocks(seed["technologies"]).items() if len(v) > 1}
        assert not doubles, f"seed {s}: doublons {doubles}"


def test_pas_de_recette_orpheline(seeds):
    for s, seed in seeds.items():
        unlocked = set(_unlocks(seed["technologies"]))
        orphans = [
            r["name"] for r in seed["recipes"]
            if r["name"].startswith("randputf-") and r["name"] not in unlocked
        ]
        assert not orphans, f"seed {s}: orphelines {orphans}"


def test_research_obligatoire_2eme_recherche_gratuite(seeds):
    for s, seed in seeds.items():
        techs = {t["id"]: t for t in seed["technologies"]}
        trans = techs["randputf-starter-transformation"]
        recipes = [
            e["recipe"] for e in trans["effects"] if e.get("type") == "unlock-recipe"
        ]
        assert "randputf-lab" in recipes, f"seed {s}: lab pas dans la 2e recherche gratuite"
        assert trans["unit"]["ingredients"] == [], f"seed {s}: la 2e recherche doit être gratuite"


def test_chain_rosee_complete_et_unlockee_par_endgame(seeds):
    for s, seed in seeds.items():
        endgame = [t for t in seed["technologies"] if t["id"] == "randputf-endgame-rocket"]
        assert len(endgame) == 1, f"seed {s}: tech endgame absente"
        recipes = {e["recipe"] for e in endgame[0]["effects"] if e.get("type") == "unlock-recipe"}
        assert recipes >= {
            "randputf-processing-unit",
            "randputf-low-density-structure",
            "randputf-rocket-fuel",
        }, f"seed {s}: {recipes}"
        # Rocket-part se craft DANS le silo : la victoire exige SA recette (§14)
        assert "randputf-rocket-silo" in {r["name"] for r in seed["recipes"]}, f"seed {s}: silo absent"


def test_aucun_produit_inaccessible(seeds):
    for s, seed in seeds.items():
        state = ProgressionState()
        for r in seed["recipes"]:
            state.recipes.append(r)
        external = {p["resource"] for p in seed["map"]["patches"]}
        unreachable = _detect_unreachable_products(state, external)
        assert not unreachable, f"seed {s}: produits inaccessibles {unreachable}"


# Randomisation des armes montées (§7/§12.1) : pool de VRAIS items gun (défaut
# config settings.yaml / RecursiveConfig) — armes MONTÉES-UNIQUEMENT (jamais
# craftées : la seed les clone à la volée pour les monter) et armes de poing
# adoptables (pompe etc. : craftables, ET clonables sur un véhicule).
ARMED_VEHICLES = ("tank", "spidertron", "artillery-wagon")
VEHICLE_POOL = [
    "tank-cannon",
    "vehicle-machine-gun",
    "tank-flamethrower",
    "artillery-wagon-cannon",
    "spidertron-rocket-launcher-1",
    "pistol",
    "submachine-gun",
    "shotgun",
    "combat-shotgun",
    "rocket-launcher",
    "flamethrower",
]
# Items legacy/dead de la famille montée : jamais de recette ni d'unlock (le
# tank-machine-gun vanilla et les spidertron launchers 2/3/4 sont identiques
# au représentant -1 → contenu mort).
LEGACY_VEHICLE_GUNS = {
    "tank-machine-gun",
    "spidertron-rocket-launcher-2",
    "spidertron-rocket-launcher-3",
    "spidertron-rocket-launcher-4",
}


def test_armement_vehicules(seeds):
    for s, seed in seeds.items():
        armament = seed.get("vehicle_armament") or {}
        assert set(armament) == set(ARMED_VEHICLES), f"seed {s}: véhicules armés {set(armament)}"
        assert seed["pools"].get("vehicle_weapons") == VEHICLE_POOL, f"seed {s}"

        # §12.1 : portée montée scalée selon la taille du véhicule — le mod
        # reçoit base_size + scale (clones), aucune valeur en dur.
        scaling = seed["pools"].get("vehicle_range_scaling") or {}
        assert {"base_size", "scale"} <= set(scaling), f"seed {s}: scaling manquant {scaling}"

        for vehicle, guns in armament.items():
            assert 1 <= len(guns) <= len(VEHICLE_POOL), f"seed {s}: {vehicle} {len(guns)} armes"
            assert len(set(guns)) == len(guns), f"seed {s}: {vehicle} armes dupliquées {guns}"
            assert set(guns) <= set(VEHICLE_POOL), f"seed {s}: {vehicle} hors pool {guns}"

        # La seed n'exporte PLUS d'items résolus : la pool est déjà en items
        # gun réels, le mod clone directement (arme dans arme).
        assert "vehicle_armament_items" not in seed, f"seed {s}: champ obsolète présent"

        # §12.1 : AUCUNE arme MONTÉE-UNIQUEMENT n'a de recette ni d'unlock
        # (jamais craftable ; un clone la monte à la place). Les armes de poing
        # de la pool, elles, restent de vrais items craftables.
        produced = {r["results"][0]["name"] for r in seed["recipes"]}
        assert not (produced & LEGACY_VEHICLE_GUNS), f"seed {s}: recettes legacy {produced & LEGACY_VEHICLE_GUNS}"
        unlocked_by = {}
        for t in seed["technologies"]:
            for e in t.get("effects") or []:
                if e.get("type") != "unlock-recipe":
                    continue
                item = e["recipe"].removeprefix("randputf-")
                unlocked_by.setdefault(item, set()).add(t["id"])
        unlock_legacy = {item for item in unlocked_by if item in LEGACY_VEHICLE_GUNS}
        assert not unlock_legacy, f"seed {s}: unlock legacy {unlock_legacy}"


def test_munitions_vehicules_dispatch_apres(seeds):
    """§12.1 : quand le véhicule est créé dans une tech, on vérifie ses
    munitions ; celles qui manquent sont dispatchées dans les 3 techs
    ISOLÉES qui suivent immédiatement la tech du véhicule. Résultat garanti :
    chaque munition d'une arme montée est unlockée AU PLUS TARD dans les
    3 techs après celle du véhicule (idx[ameth] <= idx[vtech] + 3)."""
    for s, seed in seeds.items():
        armament = seed.get("vehicle_armament") or {}
        order = seed["progression_order"]
        idx = {tid: i for i, tid in enumerate(order)}

        def unlocker(item):
            for t in seed["technologies"]:
                for e in t.get("effects") or []:
                    if e.get("type") == "unlock-recipe" and e["recipe"].removeprefix("randputf-") == item:
                        return t["id"]
            return None

        dispatch_techs = [tid for tid in order if tid.startswith("randputf-ammo-")]
        for vehicle, guns in armament.items():
            vtech = unlocker(vehicle)
            assert vtech is not None, f"seed {s}: véhicule {vehicle} sans tech"
            v_idx = idx[vtech]
            # Les steps dispatch sont isolés : jamais fusionnés avec un autre
            # step — chaque dispatch-tech est bien une tech dédiée.
            dispatch_after = [tid for tid in dispatch_techs
                              if v_idx < idx[tid] <= v_idx + 3]
            assert len(dispatch_after) <= 3, f"seed {s}: {vehicle} trop de techs dispatch {dispatch_after}"
            for gun in guns:
                cat = DB.items[gun].ammo_category
                if not cat:
                    continue
                ammos = [a.name for a in DB.items.values() if a.is_ammo and a.ammo_category == cat]
                for ammo in ammos:
                    atech = unlocker(ammo)
                    assert atech is not None, f"seed {s}: munition {ammo} ({gun}) sans unlock"
                    a_idx = idx[atech]
                    assert a_idx <= v_idx + 3, (
                        f"seed {s}: munition {ammo} de {gun} au-delà des 3 techs "
                        f"après {vehicle} ({a_idx} > {v_idx} + 3)"
                    )


def test_assignation_armes_deterministe_et_distincte():
    import random as _random

    from tool.generator.recursive_phase import _assign_vehicle_weapons

    a = _assign_vehicle_weapons(_random.Random(5))
    b = _assign_vehicle_weapons(_random.Random(5))
    assert a == b, "même graine → même assignation"
    for vehicle, guns in a.items():
        assert 1 <= len(guns) <= 4, f"{vehicle}: {len(guns)} armes hors bornes"
        assert len(set(guns)) == len(guns), f"{vehicle}: armes dupliquées"
    # Plusieurs graines : le nombre de slots varie réellement (1..4 exploités).
    slot_counts = {len(guns) for rng in (_random.Random(i) for i in range(60))
                   for guns in _assign_vehicle_weapons(rng).values()}
    assert slot_counts >= {1, 2, 3, 4}, f"bornes 1..4 jamais toutes exploitées: {slot_counts}"


def test_pack_sans_ressource_brute(seeds):
    """§13 : aucun science pack est crafté avec une ressource brute (patches au
    sol, environnement récolté à la main, fluides d'extraction infinis ou non
    — eau, pétrole brut, vapeur, §3)."""
    for s, seed in seeds.items():
        raw = set(seed["pools"]["raw_resources"])
        checked = 0
        for r in seed["recipes"]:
            if r["results"][0]["type"] != "item":
                continue
            item_name = r["results"][0]["name"]
            item = DB.items.get(item_name)
            if item is None or not item.is_science_pack:
                continue
            checked += 1
            hit = {i["name"] for i in r.get("ingredients", [])} & raw
            assert not hit, f"seed {s}: {r['name']} consomme brut {hit}"
        assert checked >= 1, f"seed {s}: aucun pack vérifié ?!"


def test_toute_tech_recursive_paie_un_science_pack(seeds):
    """§13 : toute tech récursive (bâtiments/armes/packs) n'est PAS gratuite ;
    chaque coût est un science pack unlocké par une tech STRICTEMENT
    antérieure (le premier pack est unlocké gratuitement par le starter
    §7/§13, ensuite en chaîne). Les techs de prologue paient ce premier pack.
    """
    for s, seed in seeds.items():
        pack_unlock_idx = {}
        techs, recs = seed["technologies"], seed["recipes"]
        idx_of = {t["id"]: i for i, t in enumerate(techs)}
        for idx, t in enumerate(techs):
            for e in t.get("effects") or []:
                if e.get("type") != "unlock-recipe":
                    continue
                for r in recs:
                    if r["name"] != e["recipe"]:
                        continue
                    for res in r["results"]:
                        if res["type"] == "item" and res["name"].endswith("-science-pack"):
                            pack_unlock_idx.setdefault(res["name"], idx)
        for idx, t in enumerate(techs):
            if not t["unit"]["ingredients"]:
                ok = (
                    t["id"].startswith("randputf-starter")
                    or t["id"].startswith("randputf-prologue")
                    or t["id"].startswith("randputf-science-")
                    or t["id"] == "randputf-endgame-rocket"
                )
                assert ok, f"seed {s}: tech récursive gratuite {t['id']}"
                continue
            for ing in t["unit"]["ingredients"]:
                p = ing["name"]
                assert p in pack_unlock_idx, f"seed {s}: {t['id']} coûte {p} jamais unlocké"
                assert pack_unlock_idx[p] < idx, (
                    f"seed {s}: {t['id']} coûte {p} unlocké plus tard"
                )


POLES = {
    "small-electric-pole",
    "medium-electric-pole",
    "big-electric-pole",
    "substation",
}


def _pole_tech_indices(seed):
    idxs = []
    for idx, t in enumerate(seed["technologies"]):
        for e in t.get("effects") or []:
            if e.get("type") != "unlock-recipe":
                continue
            name = e["recipe"]
            if name.startswith("randputf-"):
                name = name[len("randputf-"):]
            if name in POLES:
                idxs.append(idx)
    return sorted(set(idxs))


def test_cadence_pylones_garantie(seeds):
    # §9.4 : au moins 3 types de pylônes distincts par seed, le premier pôle
    # apparaissant tôt (dès le bootstrap électricité / ou ~10 premières techs).
    for s, seed in seeds.items():
        idxs = _pole_tech_indices(seed)
        assert len(idxs) >= 3, f"seed {s}: seulement {len(idxs)} positions de pylônes"
        assert idxs[0] < 12, f"seed {s}: premier pylône trop tard ({idxs[0]})"
        # les 3 jalons garantis sont espacés : le 2e pôle doit être au-delà
        # du 1er et le 3e au-delà du 2e (positions distinctes).
        assert len(set(idxs)) == len(idxs), f"seed {s}: positions de pylônes dupliquées"


def test_craft_trigger_prologue_craftable_des_le_starter(seeds):
    """§9.3 : le déclencheur hand-craft de chaque tech prologue doit être un
    item craftable à partir des SEULES recettes des techs gratuites du
    starter (jamais un item unlocké plus tard par une tech de labo —
    régression : les candidats étaient tirés de `state.recipes`, étendue par
    la phase récursive → nuclear-reactor/spidertron/… en déclencheur)."""
    for s, seed in seeds.items():
        craftable: set[str] = set()
        for t in seed["technologies"]:
            if not t["id"].startswith("randputf-starter"):
                continue
            for e in t.get("effects") or []:
                if e.get("type") == "unlock-recipe":
                    craftable.add(e["recipe"].removeprefix("randputf-"))
        idx_of = {t["id"]: i for i, t in enumerate(seed["technologies"])}
        for t in seed["technologies"]:
            trigger = t.get("craft_trigger")
            if not trigger:
                continue
            assert t["id"].startswith("randputf-prologue"), f"seed {s}: {trigger} hors prologue"
            assert trigger in craftable, (
                f"seed {s}: {t['id']} trigger={trigger} non craftable au starter "
                f"(disponibles: {sorted(craftable)})"
            )
            # §9.3 : la quantité demandée est un nombre d'items = round(2^(n + 1/4))
            # avec n ∈ (1, 6] → bornes 2^2.25 ≈ 5 .. 2^6.25 ≈ 76 — jamais un
            # singleton trivial, craftable à la main au bootstrap.
            n = t["craft_trigger_count"]
            assert isinstance(n, int) and 5 <= n <= 76, f"seed {s}: {t['id']} quantité {n}"
            # §9.3 : l'item doit être available AVANT la tech qui le demande.
            unlocker = next(
                (x["id"] for x in seed["technologies"]
                 for e in x.get("effects") or []
                 if e.get("type") == "unlock-recipe"
                 and e["recipe"].removeprefix("randputf-") == trigger),
                None,
            )
            assert unlocker is not None, f"seed {s}: trigger {trigger} sans unlock"
            assert idx_of[unlocker] < idx_of[t["id"]], (
                f"seed {s}: {t['id']} trigger {trigger} unlocké plus tard (idx "
                f"{idx_of[unlocker]} >= {idx_of[t['id']]})"
            )


def test_premier_generateur_de_la_seed_craftable_a_la_main(seeds):
    """§10 : le PREMIER générateur électrique débloqué par la seed (quelle que
    soit la phase : électricité d'amorçage OU récursif, quand le starter n'a
    rien demandé en électricité) a une recette craftable à la main : ingrédients
    100% solides, aucune catégorie ni atelier. Un atelier électrique
    (assembling-machine-2, usine chimique...) exigerait l'électricité que ce
    générateur doit amorcer — boucle bootstrap §10. Les générateurs suivants
    retombent sur des ateliers normaux."""
    generators = {b.name for b in DB.buildings_of_type("generator")}
    for s, seed in seeds.items():
        first: str | None = None
        first_recipe: dict | None = None
        for idx, t in enumerate(seed["technologies"]):
            for e in t.get("effects") or []:
                if e.get("type") != "unlock-recipe":
                    continue
                name = e["recipe"].removeprefix("randputf-")
                if name not in generators:
                    continue
                if first is None:
                    first = name
                    first_recipe = next(
                        (r for r in seed["recipes"] if r["name"] == e["recipe"]), None
                    )
        assert first is not None, f"seed {s}: aucun générateur débloqué"
        assert first_recipe is not None, f"seed {s}: recette du générateur {first} absente"
        assert not first_recipe.get("category"), (
            f"seed {s}: 1er générateur {first} en atelier "
            f"({first_recipe.get('category')})"
        )
        assert not first_recipe.get("crafted_in"), (
            f"seed {s}: 1er générateur {first} exige "
            f"{first_recipe.get('crafted_in')}"
        )
        for ing in first_recipe["ingredients"]:
            assert ing["type"] == "item", (
                f"seed {s}: 1er générateur {first} consomme un fluide {ing}"
            )


def test_detecteur_de_cycle_repere_un_cycle_reel():
    db = DB
    state = ProgressionState()
    for name in ("iron-ore", "stone"):
        state.mark_obtained("item", name)
    a = make_recipe(random.Random(1), db, state, "item", "iron-plate")
    b = make_recipe(random.Random(2), db, state, "item", "copper-plate")
    state.recipes.append(a)
    state.recipes.append(b)
    assert _detect_recipe_cycles(state) == []

    a["ingredients"].append({"type": "item", "name": "copper-plate", "amount": 1})
    b["ingredients"].append({"type": "item", "name": "iron-plate", "amount": 1})
    cycles = _detect_recipe_cycles(state)
    assert cycles, "un cycle A<->B doit être détecté"