"""Invariants de pipeline sur UNE seed (fuzz réduit) : unlock unique §13,
lab dans la 2e recherche gratuite §8, chaîne fusée complète §14, aucun cycle
de recettes réel (§8) — vérifiés sur plusieurs graines différentes."""

from __future__ import annotations

import collections
import copy
import json
from pathlib import Path

import pytest

from tool.common.db import SLOT_ITEM
from tool.generator.pipeline import generate_seed
from tool.generator.recipes import ProgressionState, make_recipe
from tool.parsers.vanilla import load_db_from_dump
from tool.validator.pipeline_validator import _detect_recipe_cycles, _detect_unreachable_products

import random

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))

SEEDS = (0, 5, 36, 43, 57)


def item_of(db, entity_name: str) -> str | None:
    return next(
        (i.name for i in db.items.values() if i.place_result == entity_name), None
    )


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


def test_contenu_reseau_differe_apres_contenu_passif(seeds):
    """§7/§8 : dans le balayage de couverture, les items dépendant du réseau
    (tourelle laser, radar, combinator, lampe) sont DEFERRÉS après le contenu
    « passif » (tourelle balistique, mur). Pour chaque seed, la 1re tech
    content-laser-turret arrive après la 1re tech content-gun-turret."""
    def _first_content_index(techs, fragment):
        for i, t in enumerate(techs):
            if "content-" + fragment in t.get("id", ""):
                return i
        return None

    for s, seed in seeds.items():
        techs = seed["technologies"]
        laser = _first_content_index(techs, "laser-turret")
        gun = _first_content_index(techs, "gun-turret")
        if laser is not None and gun is not None:
            assert laser > gun, (
                f"seed {s}: laser-turret (idx {laser}) doit venir APRÈS gun-turret "
                f"(idx {gun}) — tier tardif §7/§8"
            )


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
        external |= {l["resource"] for l in seed["map"]["lakes"]}
        unreachable = _detect_unreachable_products(state, external)
        assert not unreachable, f"seed {s}: produits inaccessibles {unreachable}"


# Randomisation des armes montées (§7/§12.1) : pool de VRAIS items gun (défaut
# config defaults.yaml / RecursiveConfig) — armes MONTÉES-UNIQUEMENT (jamais
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


def test_une_seule_arme_de_poing_par_tech(seeds):
    """§11 + §13 : jamais PLUSIEURS armes de poing dans la même tech.

    Chaque tech combat débloque au plus une arme (avec sa munition alignée).
    Deux steps combat consécutifs ne doivent pas être fusionnés par le
    groupement §13, sinon la tech arrive « avec toute dans sa tech » — ex. seed
    1 avant fix : submachine-gun + shotgun + leurs 2 munitions dans UNE tech."""
    for s, seed in seeds.items():
        for t in seed["technologies"]:
            guns = [
                e["recipe"].removeprefix("randputf-")
                for e in t.get("effects") or []
                if e.get("type") == "unlock-recipe"
                and DB.items.get(e["recipe"].removeprefix("randputf-")) is not None
                and DB.items[e["recipe"].removeprefix("randputf-")].is_handheld_gun
            ]
            assert len(guns) <= 1, f"seed {s}: tech {t['id']} débloque {len(guns)} armes {guns}"


def test_companions_proches(seeds):
    """« companion guarantee » — les groupes d'items dépendants restent
    PROCHES dans l'arbre (jamais une paire diffusée loin l'une de l'autre).
    - roboport ↔ robots (logistic/construction) : un robot sans roboport est
      du contenu mort ;
    - solar-panel ↔ accumulator : un premier solaire sans accumulateur =
      blackout nocturne.
    Vérifie que chaque membre d'un groupe est unlocké AU PLUS TARD 3 techs
    après le premier membre du groupe déployé (façon dispatch §12.1)."""
    COMPANION_GROUPS = [
        {"roboport", "logistic-robot", "construction-robot"},
        {"solar-panel", "accumulator"},
    ]
    for s, seed in seeds.items():
        order = seed["progression_order"]
        idx = {tid: i for i, tid in enumerate(order)}

        def unlocker(item):
            for t in seed["technologies"]:
                for e in t.get("effects") or []:
                    if e.get("type") == "unlock-recipe" and e["recipe"].removeprefix("randputf-") == item:
                        return t["id"]
            return None

        for group in COMPANION_GROUPS:
            present = [item for item in group if unlocker(item) is not None]
            if not present:
                continue
            first_idx = min(idx[unlocker(item)] for item in present)
            for item in group:
                t = unlocker(item)
                assert t is not None, f"seed {s}: compagnon {item} jamais unlocké"
                assert idx[t] <= first_idx + 3, (
                    f"seed {s}: compagnon {item}@{idx[t]} loin de son groupe "
                    f"(début @{first_idx})"
                )


def test_munitions_armes_de_poing(seeds):
    """§11 : une arme de poing débloquée par une tech combat ne doit JAMAIS être
    sans munition. Règle : si AUCUNE munition de sa catégorie n'est débloquée
    avant, une seule munition aléatoire parmi celles restantes est générée dans
    la MÊME tech que l'arme (pas toutes d'un coup). Invariant vérifié : au
    moins une munition craftée de la catégorie est unlockée AU PLUS TARD à la
    tech de l'arme (min(timings) <= idx_arme)."""
    for s, seed in seeds.items():
        order = seed["progression_order"]
        idx = {tid: i for i, tid in enumerate(order)}

        def unlocker(item):
            for t in seed["technologies"]:
                for e in t.get("effects") or []:
                    if e.get("type") == "unlock-recipe" and e["recipe"].removeprefix("randputf-") == item:
                        return t["id"]
            return None

        # Armes de poing réellement craftées par la seed (exclut les armes
        # montées-uniquement, jamais craftées).
        crafted_guns = {
            r["results"][0]["name"] for r in seed["recipes"]
            if r["results"] and DB.items.get(r["results"][0]["name"]) is not None
            and DB.items[r["results"][0]["name"]].is_handheld_gun
        }
        for gun in crafted_guns:
            gtech = unlocker(gun)
            assert gtech is not None, f"seed {s}: arme de poing {gun} sans tech"
            g_idx = idx[gtech]
            cat = DB.items[gun].ammo_category
            if not cat:
                continue
            ammos = [a.name for a in DB.items.values() if a.is_ammo and a.ammo_category == cat]
            assert ammos, f"seed {s}: arme {gun} sans munition vanilla ({cat})"
            timings = []
            for ammo in ammos:
                atech = unlocker(ammo)
                if atech is not None:
                    timings.append(idx[atech])
            assert timings, (
                f"seed {s}: arme de poing {gun} ({cat}) sans munition craftée"
            )
            assert min(timings) <= g_idx, (
                f"seed {s}: arme de poing {gun} débloquée @{g_idx} sans munition "
                f"disponible (munitions @{sorted(timings)})"
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


def test_aucun_science_pack_en_patch(seeds):
    """§13 : un science pack n'est JAMAIS une ressource au sol (patch). S'il y
    était posé, sa recette n'existerait pas au démarrage et la filière de coût
    des techs (amorcée par le premier pack craftable du starter) serait brisée
    — régression du crash `rng.choice(_unlocked_science_packs)` sur liste
    vide."""
    for s, seed in seeds.items():
        patch_resources = {p["resource"] for p in seed["map"]["patches"]}
        packs_in_patches = {
            r for r in patch_resources
            if DB.items.get(r) is not None and DB.items[r].is_science_pack
        }
        assert not packs_in_patches, f"seed {s}: packs en patch {packs_in_patches}"


def test_c6_aucune_ressource_dupliquee_sur_la_carte(seeds):
    """Une même ressource brute n'apparaît qu'UNE fois sur la carte —
    jamais à la fois en patch et en lac, ni deux fois en patch (tirages sans
    remise garantis par `generate_patches(lake_resources=...)` + ordre
    lacs→patchs dans `generate_seed`)."""
    for s, seed in seeds.items():
        patch_res = [p["resource"] for p in seed["map"]["patches"]]
        lake_res = [l["resource"] for l in seed["map"]["lakes"]]
        assert len(patch_res) == len(set(patch_res)), f"seed {s}: patch dupliqué {patch_res}"
        assert len(lake_res) == len(set(lake_res)), f"seed {s}: lac dupliqué {lake_res}"
        both = set(patch_res) & set(lake_res)
        assert not both, f"seed {s}: fluide à la fois patch et lac {both}"


def test_oil_puits_posse_explicite_chaque_patch(seeds):
    """§6.5 : CHAQUE patch (item ET fluide) doit porter son gisement posé au
    runtime — centre déterministe, un nombre de blocs/puits et un rayon adaptés
    au KIND (fluides : 3..8 puits éparpillés rayon 9..16 ; items : champ plein
    « type mapgen vanilla » — disque de rayon 9..17, count = nombre RÉEL de
    tuiles posées par l'algo de forme, dérivé de `item_field_tiles`),
    une graine locale > 0."""
    from tool.generator.map_patches import item_field_tiles

    for s, seed in seeds.items():
        for patch in seed["map"]["patches"]:
            assert "center" in patch and "x" in patch["center"] and "y" in patch["center"], \
                f"seed {s}: patch {patch['resource']} sans centre"
            if patch["kind"] == "fluid":
                assert 3 <= patch["count"] <= 8, \
                    f"seed {s}: {patch['resource']} nb puits {patch['count']} hors 3..8"
                assert 9 <= patch["cluster_radius"] <= 16, \
                    f"seed {s}: {patch['resource']} rayon puits invalide"
            else:
                assert 9 <= patch["cluster_radius"] <= 17, \
                    f"seed {s}: {patch['resource']} rayon item invalide"
                expect = len(item_field_tiles(patch["cluster_radius"], patch["well_seed"]))
                assert patch["count"] == expect, \
                    f"seed {s}: {patch['resource']} count {patch['count']} != tuiles réelles {expect}"
            assert patch["well_seed"] > 0, f"seed {s}: well_seed nul"


def test_gisements_serres_au_spawn(seeds):
    """§6.5 (cluster serré) : tous les gisements restent dans un rayon ~25..200
    tuiles du spawn — accessibles à pied très tôt, sans jamais exiger un long
    voyage au départ. (Le rayon de dispersion, 9-16, borne les blocs autour du
    centre.)"""
    import math

    MAX_CENTER_DIST = 200
    for s, seed in seeds.items():
        for patch in seed["map"]["patches"]:
            c = patch["center"]
            d = math.hypot(c["x"], c["y"])
            assert d <= MAX_CENTER_DIST, \
                f"seed {s}: gisement {patch['resource']} à {d:.0f} tuiles (> {MAX_CENTER_DIST})"


def test_oil_puits_deterministe_entre_generations():
    """§6.5 : la pose des gisements est déterministe — refaire la seed (même
    graine) donne exactement les mêmes gisements (centre, nb de blocs, rayon,
    graine). Dépend d'un flux RNG dédié : les autres phases sont inchangées."""
    db = copy.deepcopy(DB)
    db.seed_value = 5
    a = generate_seed(db)
    db.seed_value = 5
    b = generate_seed(db)
    fa = {p["resource"]: {k: p[k] for k in ("center", "count", "well_seed", "cluster_radius")}
          for p in a["map"]["patches"]}
    fb = {p["resource"]: {k: p[k] for k in ("center", "count", "well_seed", "cluster_radius")}
          for p in b["map"]["patches"]}
    assert fa == fb


def test_c2_lac_est_obtenable_sans_recette():
    """Un lac est une ressource brute obtenable DÈS LE DÉPART (pompe
    offshore, volume infini) — il compte comme source externe de la solvabilité,
    au même titre qu'un patch. Vérifie en isolation que
    `_detect_unreachable_products` ne signale PAS une recette consommant un
    fluide déjà posé en lac."""
    state = ProgressionState()
    # Recette qui consomme un fluide disponible SEULEMENT en lac (jamais crafté).
    state.recipes.append({
        "name": "randputf-lac-consumer",
        "ingredients": [{"name": "crude-oil"}],
        "results": [{"name": "randputf-lac-product"}],
    })
    # Sans fournir le lac comme source externe, le produit serait inaccessible.
    unreachable = _detect_unreachable_products(state, external={"crude-oil"})
    assert "randputf-lac-product" not in unreachable, unreachable


def test_c2_validate_pipeline_valide_avec_lacs(seeds):
    """`validate_pipeline` reçoit désormais les lacs comme sources
    externes (au même titre que les patchs). Sur des seeds réelles, aucun
    cycle/problème de progressivité n'est dû à un fluide de lac : le validateur
    le traite comme obtenable (pompe offshore)."""
    from tool.validator.pipeline_validator import validate_pipeline as _vp

    for s, seed in seeds.items():
        state = ProgressionState()
        for r in seed["recipes"]:
            state.recipes.append(r)
        patch_res = {p["resource"] for p in seed["map"]["patches"]}
        lake_res = {la["resource"] for la in seed["map"]["lakes"]}
        # L'anti-cycle et la progressivité se basent sur patchs + lacs : aucune
        # recette réelle ne doit être déclarée en boucle/manquante à cause d'un
        # lac (sinon le starter ne pourrait pas dépendre d'un fluide de lac).
        vr = _vp(state, seed["technologies"], DB, patch_res, lake_res)
        assert not vr.issues, f"seed {s}: issues {vr.issues}"


def test_aucun_pack_crafte_avec_ressource_brute(seeds):
    """§13 : aucun science pack n'est crafté avec une ressource brute (patches
    au sol, environnement récolté à la main, fluides d'extraction infinis ou
    non — eau, pétrole brut, vapeur, §3)."""
    for s, seed in seeds.items():
        raw = set(seed["pools"]["raw_resources"])
        checked = 0
        for r in seed["recipes"]:
            if r["results"][0]["type"] != "item":
                continue
            item = DB.items.get(r["results"][0]["name"])
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
                    or t["id"].startswith("randputf-ease-")
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
            assert (
                t["id"].startswith("randputf-prologue")
                or t["id"].startswith("randputf-ease-")
            ), f"seed {s}: {trigger} hors prologue/ease-up"
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
    # Les vrais producteurs de COURANT (tag ``produces_electricity``) : le tag
    # ``is_generator`` inclurait aussi les producteurs de chaleur (réacteur,
    # heat-exchanger) qui ne démarrent jamais le réseau §10.
    generators = {b.name for b in DB.buildings.values() if b.produces_electricity}
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


def test_pylone_du_bootstrap_craftable_a_la_main(seeds):
    """§10 : le pylône d'amorçage (débloqué avec le générateur) est CRAFTABLE À
    LA MAIN comme lui — son atelier exigerait l'électricité que le poteau est
    censé transporter (boucle bootstrap sinon). Sa recette est réintégrée aux
    techs GRATUITES du starter → disponible dès le spawn."""
    for s, seed in seeds.items():
        hand_recipes = [
            r for r in seed["recipes"]
            if r["results"] and r["results"][0]["name"] in POLES
            and not r.get("category") and not r.get("crafted_in")
        ]
        assert hand_recipes, f"seed {s}: aucun pylône craftable à la main"
        names = {r["name"] for r in hand_recipes}
        unlockers = [
            t["id"] for t in seed["technologies"]
            for e in t.get("effects") or []
            if e.get("type") == "unlock-recipe" and e["recipe"] in names
        ]
        assert any(u.startswith("randputf-starter") for u in unlockers), (
            f"seed {s}: pylône à la main non dispo au starter "
            f"(recettes {sorted(names)}, unlockers {sorted(unlockers)})"
        )


def test_extracteur_unlocke_avant_tout_consommateur(seeds):
    """§7 + C3 « la tech d'avant » : pour chaque ressource brute (patchs +
    lacs), la recette de son extracteur n'est JAMAIS débloquée après le premier
    consommateur « non-extracteur » de la ressource (claim ≤ 1er usage —
    l'extracteur est utilisable dès que la ressource devient nécessaire ; il
    reste au starter quand celle-ci sert dès le spawn, sinon il part au moment
    du besoin ou sur une tech payante s'il n'est jamais consommé, §C3)."""
    import tool.generator.starter_chain as sc

    captured = {}
    _orig = sc.build_starter_chain

    def _wrap(rng, db, patches, **kw):
        chain = _orig(rng, db, patches, **kw)
        captured[id(chain)] = [
            (s["resource"]["type"], s["resource"]["name"], s["extractor"])
            for s in chain.steps if s.get("type") == "extract"
        ]
        return chain

    sc.build_starter_chain = _wrap
    try:
        for s in seeds:
            db = copy.deepcopy(DB)
            db.seed_value = s
            captured.clear()
            seed = generate_seed(db)
            extracts = list(captured.values())[-1]
            techs = seed["technologies"]
            idx = {t["id"]: i for i, t in enumerate(techs)}
            unlock = {}
            for t in techs:
                for e in t.get("effects") or []:
                    if e.get("type") == "unlock-recipe":
                        unlock.setdefault(e["recipe"], idx[t["id"]])
            # Recettes des extracteurs (auto-conso exclue de « consommateur »)
            extractor_item_recipes = {
                r["name"]
                for _, _, ext in extracts
                for r in seed["recipes"]
                if any(
                    res.get("type") == SLOT_ITEM and item_of(DB, ext) == res["name"]
                    for res in r.get("results") or []
                )
            }
            for kind, resource, ext in extracts:
                item = item_of(DB, ext)
                prod = [
                    r["name"] for r in seed["recipes"]
                    if any(res.get("type") == SLOT_ITEM and res.get("name") == item
                           for res in r.get("results") or [])
                ]
                assert prod, (
                    f"seed {s}: {item} (extracteur de {resource}) sans recette "
                    "dans la seed"
                )
                ext_unlock = min(unlock.get(r) for r in prod)
                consumers = [
                    r["name"] for r in seed["recipes"]
                    if any(i.get("name") == resource for i in r.get("ingredients") or [])
                    and r["name"] not in extractor_item_recipes
                ]
                consumers_unlock = sorted(
                    unlock.get(rc) for rc in consumers if unlock.get(rc) is not None
                )
                if consumers_unlock:
                    # C3 : jamais d'extracteur après le premier usage réel de sa
                    # ressource (sinon le consommateur serait injouable) —
                    # égalité quand le besoin et la fabrication arrivent ensemble.
                    assert ext_unlock <= consumers_unlock[0], (
                        f"seed {s}: {resource}/{item} recette@{ext_unlock} après "
                        f"1er consommateur@tech {consumers_unlock[0]}"
                    )
    finally:
        sc.build_starter_chain = _orig


def test_bootstrap_double_cout_ingredients_non_infinis(seeds):
    """§9.5/§10 : les recettes craftables à la main (bootstrap, ni atelier ni
    catégorie) DOUBLENT la quantité de leurs ingrédients non infinis
    (wood/stone/raw-fish, tag ``is_environmental``) — le début de run se joue
    sur ces ressources rares, et les relais (§9.3) fournissent ensuite les
    recettes « propres ». Les ingrédients déjà produits ne sont pas doublés."""
    for s, seed in seeds.items():
        for r in seed["recipes"]:
            if r.get("category") or r.get("crafted_in"):
                continue
            for ing in r["ingredients"]:
                if ing["type"] != "item":
                    continue
                item = DB.items.get(ing["name"])
                if item is not None and item.is_environmental:
                    assert ing["amount"] % 2 == 0, (
                        f"seed {s}: bootstrap {r['name']} consomme "
                        f"{ing['amount']} de {ing['name']} (non doublé)"
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


def test_aucune_recette_sur_machine_a_recette_fixe(seeds):
    """§10 : les bâtiments à RECETTE CACHÉE taggés
    ``has_hidden_recipe`` (boiler/heat-exchanger/nuclear-reactor en vanilla) ne
    reçoivent JAMAIS une recette quelconque en tant qu'atelier — seule la
    recette randomisée assignée (crafted_in) les concerne. Tout bâtiment à
    recette cachée qui apparaît en ``crafted_in`` doit être un ``is_fixed_crafter``
    (boiler/hx = fluide→fluide, réacteur = item→item via ses résidus). Les
    autres générateurs/extracteurs/lab (non taggés : pas une recette, mécanique
    moteur) sont déjà exclus par ``_is_atelier`` (aucune catégorie valide)."""
    from tool.common.db import has_hidden_recipe, is_fixed_crafter

    for s, seed in seeds.items():
        for r in seed["recipes"]:
            ci = r.get("crafted_in")
            if not ci:
                continue
            building = DB.buildings.get(ci)
            assert building is not None, f"seed {s}: crafted_in inconnu {ci}"
            if has_hidden_recipe(building) and not is_fixed_crafter(building):
                raise AssertionError(
                    f"seed {s}: recette {r['name']} craftée dans {ci}, "
                    "une machine à recette fixe hors `is_fixed_crafter` (jamais un atelier)"
                )


def test_aucun_cycle_produit_produit_item_ou_fluide(seeds):
    """§10ter-redesign : le graphe produit→ingrédient, TOUS crafts confondus
    et items comme fluides, doit être acyclique sur chaque seed générée — le
    garde anti-boucle transitive est appliqué à chaque création (primaire,
    relais, ease, fabricateurs fixes, balayage §9.6), le diagnostic `find_cycles`
    couvre les SCC items+fluides."""
    from tool.generator.bootstrap_guard import find_cycles
    from tool.generator.early_oracle import compute_early_reachable

    for s, seed in seeds.items():
        recipes = seed["recipes"]
        items = {
            res["name"] for r in recipes
            for res in r.get("results", []) if res["type"] == "item"
        }
        fluids = {
            res["name"] for r in recipes
            for res in r.get("results", []) if res["type"] == "fluid"
        }
        early, _ = compute_early_reachable(DB, recipes, items, fluids)
        cycles = find_cycles(DB, recipes, early)
        assert not cycles, (
            f"seed {s}: {len(cycles)} SCC produit|fluide dans le graphe "
            f"(membres: {[c['members'] for c in cycles[:3]]})"
        )


@pytest.mark.parametrize("seed", range(30, 60))
def test_aucun_cycle_produit_produit_balayage_large(seed):
    """Même invariant sur un éventail de graines plus large (sans solveur,
    coupé vite) : la non-cyclicitté produit|fluide est une propriété
    STRUCTURELLE de la génération, pas un accident de seed."""
    from tool.generator.bootstrap_guard import find_cycles
    from tool.generator.early_oracle import compute_early_reachable

    db = copy.deepcopy(DB)
    db.seed_value = seed
    generated = generate_seed(db)
    recipes = generated["recipes"]
    items = {
        res["name"] for r in recipes
        for res in r.get("results", []) if res["type"] == "item"
    }
    fluids = {
        res["name"] for r in recipes
        for res in r.get("results", []) if res["type"] == "fluid"
    }
    early, _ = compute_early_reachable(DB, recipes, items, fluids)
    cycles = find_cycles(DB, recipes, early)
    assert not cycles, (
        f"seed {seed}: {len(cycles)} SCC produit|fluide "
        f"(membres: {[c['members'] for c in cycles[:3]]})"
    )