"""Tests des jalons « late raws » (§6.2/§6.3 plan extracteurs).

Couvrent config, plan (mesure de dépendance sur la passe A / seed finale),
dégradation du pool (état + base), et les invariants end-to-end :

- inertie par défaut : gating DÉSACTIVÉ ⇒ la seed est strictement la seed
  historique (régression 0) ;
- déterminisme : même graine + même config ⇒ même seed (les tirages 60 % sont
  sur le flux principal) ;
- sûreté bootstrap : les techs gratuites (boîte du spawn) ne consomment JAMAIS
  un late raw gaté — la fermeture D4bis reste vraie après dégradation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from tool.common.db import SLOT_FLUID, SLOT_ITEM
from tool.generator import late_raws
from tool.generator.late_raws import (
    LateRawsConfig,
    LateRawsPlan,
    degrade,
    plan_from_seed,
)
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))

GATING = {"late_raws": {"enabled": True, "share": 0.25, "pick_chance": 0.6}}


def db_for(seed_value: int):
    db = copy.deepcopy(DB)
    db.seed_value = seed_value
    return db


# ── Config ────────────────────────────────────────────────────────────────


def test_config_defaults():
    cfg = LateRawsConfig.from_config(None)
    assert cfg.enabled is False
    assert cfg.share == 0.25
    assert cfg.pick_chance == 0.6
    cfg2 = LateRawsConfig.from_config({"late_raws": {"enabled": True}})
    assert cfg2.enabled is True
    assert cfg2.pick_chance == 0.6  # défauts préservés


def test_plan_eligible_respecte_les_floors():
    plan = LateRawsPlan(
        gated={("item", "a"), ("fluid", "b")},
        floor_tier={("item", "a"): 0, ("fluid", "b"): 3},
        pick_chance=0.6,
    )
    assert set(plan.eligible(0)) == {("item", "a")}
    assert set(plan.eligible(3)) == {("item", "a"), ("fluid", "b")}
    assert plan.gated_fluids == {"b"}


# ── Plan sur une VRAIE seed (mesure de dépendance) ────────────────────────


def test_plan_invariants_sur_seed_reelle():
    """Sur une vraie seed, le plan gate TOUTES les raws non-startup (modèle
    §6 révisé), jamais un raw de la boîte du spawn (D4bis), et affecte un
    jalon (tier) à chaque raw gaté."""
    for seed_value in (0, 1, 3, 4, 5):
        db = db_for(seed_value)
        cfg = LateRawsConfig.from_config(GATING)
        seed = generate_seed(db, GATING, validate=False)
        plan = plan_from_seed(seed, cfg)

        report = seed["extractor_timing"].get("extractors", {})
        extracted = set()
        for rs in report.values():
            extracted.update((r["type"], r["name"]) for r in rs)
        assert plan.gated == extracted - plan.startup  # gate TOUTES les non-startup
        assert plan.gated.isdisjoint(plan.startup)
        for key in plan.gated:
            assert key[0] in (SLOT_ITEM, SLOT_FLUID)
            assert key in plan.floor_tier
            assert plan.floor_tier[key] >= 0

        # D4bis : aucun raw gaté n'est consommé par une tech gratuite du starter.
        free_ids = set(seed.get("free_researches") or [])
        for tech in seed["technologies"]:
            if tech["id"] not in free_ids:
                continue
            for effect in tech.get("effects", []):
                if effect.get("type") != "unlock-recipe":
                    continue
                recipe = next(
                    (r for r in seed["recipes"] if r["name"] == effect["recipe"]), None
                )
                if recipe is None:
                    continue
                for ing in recipe.get("ingredients", []):
                    assert (ing.get("type"), ing.get("name")) not in plan.gated, (
                        f"seed {seed_value}: la tech gratuite {tech['id']} "
                        f"consomme le late raw gaté {ing['name']}"
                    )


def test_export_late_raws_present_seulement_si_gating():
    """La seed gatée exporte ``late_raws`` (startup disjointe, chaque raw gated
    avec un jalon ``tier`` entier ≥ 0) ; la seed historique n'exporte pas la
    clé (comportement rejoueur inchangé). Seed choisie non-inerte (jalon > 0)."""
    base = generate_seed(db_for(10), {}, validate=False)
    assert not base.get("late_raws")

    gated = generate_seed(db_for(10), GATING, validate=False)
    lr = gated.get("late_raws")
    assert lr is not None
    assert lr.get("gated")
    assert any(info["tier"] >= 1 for info in lr["gated"].values())
    startup = {tuple(k) for k in lr.get("startup", [])}
    for name, info in lr["gated"].items():
        assert info["kind"] in (SLOT_ITEM, SLOT_FLUID)
        assert isinstance(info["tier"], int) and info["tier"] >= 0
        assert (info["kind"], name) not in startup


# ── Dégradation ───────────────────────────────────────────────────────────


def _make_plan(*keys):
    return LateRawsPlan(
        gated=set(keys),
        floor_tier={k: 0 for k in keys},
    )


def test_degrade_retire_obtained_sans_toucher_au_graphe():
    from tool.generator.recipes import ProgressionState

    state = ProgressionState()
    base = ProgressionState()
    for name in ("iron-ore", "crude-oil"):
        state.mark_obtained(SLOT_ITEM, name)
        base.mark_obtained(SLOT_ITEM, name)
    state.mark_obtained(SLOT_FLUID, "water")
    base.mark_obtained(SLOT_FLUID, "water")
    plan = _make_plan(("item", "crude-oil"), ("fluid", "water"))

    degrade(state, base, plan)

    assert "crude-oil" not in state.obtained_items
    assert "crude-oil" not in base.obtained_items
    assert "water" not in state.obtained_fluids
    assert "water" not in base.obtained_fluids
    # Le retrait ne touche que les MARKERS : le reste du pool est intact.
    assert "iron-ore" in state.obtained_items
    assert state.recipes == []
    assert state.steps == []


# ── End-to-end : inertie, déterminisme, sûreté ────────────────────────────


def test_desactive_par_defaut_seed_historique():
    """Sans config lapropos ``late_raws``, generate_seed produit EXACTEMENT la
    seed historique (invariant de non-régression ; le bacillé règle le flux)."""
    baseline = generate_seed(db_for(3), {}, validate=False)
    disabled = generate_seed(db_for(3), {"late_raws": {"enabled": False}}, validate=False)
    assert baseline == disabled


def test_determinisme_meme_seed_meme_config():
    a = generate_seed(db_for(7), GATING, validate=False)
    b = generate_seed(db_for(7), GATING, validate=False)
    assert a == b


def test_gating_change_effectivement_le_graphe_quand_active():
    """Une seed NON-inerte (jalons > 0) diffère de la seed historique : le
    ré-bakage de la passe B déplace la première consommation des raws gatées
    vers leur jalon. (Inverse : gating inerte = seed historique, cf.
    test_gating_inerte_rend_la_seed_historique.)"""
    db = db_for(10)
    base = generate_seed(db, {}, validate=False)
    gated = generate_seed(db, GATING, validate=False)
    lr = gated.get("late_raws") or {}
    assert lr.get("gated"), "seed 10 sans raw gatée"
    assert any(info["tier"] >= 1 for info in lr["gated"].values())
    assert base != gated


def test_gating_inerte_rend_la_seed_historique():
    """Gating inerte (jalons tous ≤ 0) : AUCUNE raw n'est réellement retenue —
    la seed gatée est byte-identique à la seed historique. Rejouer la passe B
    ne ferait que changer l'arbre sans changer la disponibilité (régression
    seed 1757 : défaite en gaté à la tech 21, victoire 89/89 en baseline)."""
    for seed_value in (1, 2):
        db = db_for(seed_value)
        base = generate_seed(db, {}, validate=False)
        gated = generate_seed(db, GATING, validate=False)
        assert gated == base, f"seed {seed_value}: gating inerte ≠ seed historique"
        assert not gated.get("late_raws")


def test_seed_1757_gating_inerte_victoire_comme_baseline():
    """Régression 1757 (config réelle du jeu) : sous `config/settings.yaml` +
    gating, toutes les raws gatées ont un jalon ≤ 0 → la seed sert la même
    seed de la passe A ; le rejoueur gagne comme en baseline (89/89), là où la
    passe B re-générée perdait à la tech 21 (atelier assembling-machine-2)."""
    from tool.__main__ import _load_config
    from tool.replay import player as rp

    db = db_for(1757)
    base_cfg = dict(_load_config())
    base_cfg["seed"] = 1757
    base = generate_seed(db, base_cfg, validate=False)
    gated_cfg = dict(base_cfg)
    gated_cfg["late_raws"] = {"enabled": True, "pick_chance": 0.6}
    gated = generate_seed(db, gated_cfg, validate=False)

    assert gated == base, "seed 1757: gating inerte → seed re-générée différente"
    assert rp.play(db, base).victory
    assert rp.play(db, gated).victory


def test_tous_les_late_raws_gates_ont_leur_extracteur_present():
    """La dégradation retire l'obtention, jamais l'EXTRACTEUR : le claim C3 et
    le graphe d'extraction restent complets (le player pourra toujours miner /
    pomper — seule la disponibilité dans les recettes est reportée)."""
    db = db_for(4)
    seed = generate_seed(db, GATING, validate=False)
    cfg = LateRawsConfig.from_config(GATING)
    plan = plan_from_seed(seed, cfg)
    if not plan.gated:
        raise AssertionError("seed 4: aucune raw gatée (test sans objet)")
    known = set()
    for rs in seed["extractor_timing"].get("extractors", {}).values():
        known.update((r["type"], r["name"]) for r in rs)
    assert plan.gated <= known


# ── Rejoueur : il RESPECTE la disponibilité par jalon (§6 révisé) ─────────


def test_rejoueur_verrouille_les_raws_gatees_jusqu_au_jalon():
    """Le rejoueur (joueur quantitatif) n'utilise une raw gated qu'une fois son
    échelon ``tier`` atteint ; les raws startup sont disponibles dès le spawn ;
    une seed sans export garde le comportement historique (tout disponible)."""
    from tool.replay import player as rp

    db = seed = None
    gated = None
    for seed_value in range(2, 12):
        db = db_for(seed_value)
        seed = generate_seed(db, GATING, validate=False)
        gated = (seed.get("late_raws") or {}).get("gated") or {}
        if gated:
            break
    assert gated, "aucune seed de test avec des raws non-startup gatées"
    name, info = next(iter(gated.items()))
    kind, tier = info["kind"], info["tier"]

    p = rp.FakePlayer(db, seed)
    # Avant le jalon : verrouillée.
    p.researched = {t for t, tt in p._tech_tier.items() if tt < tier}
    assert p._current_tier() < tier
    assert not p._raw_available(kind, name)
    # À partir du jalon : débloquée (et le reste inchangé).
    p.researched = {t for t, tt in p._tech_tier.items() if tt <= tier}
    assert p._current_tier() >= tier
    assert p._raw_available(kind, name)

    p2 = rp.FakePlayer(db, seed)
    # Les raws startup (libres) ne sont jamais verrouillées, même au spawn.
    for key in (tuple(k) for k in seed["late_raws"]["startup"]):
        assert p2._raw_available(key[0], key[1])

    # Seeds historiques : pas de gating → tout reste disponible, comportement
    # rejoueur identique (aucune `late_tier`).
    base = generate_seed(db_for(1), {}, validate=False)
    pb = rp.FakePlayer(db_for(1), base)
    assert not pb.late_tier
    assert pb._raw_available(SLOT_ITEM, name)
    mapped = next(iter(pb.item_patch_resources or pb.patch_resources or pb.lake_resources))
    assert pb._raw_infinite_now(mapped)


def test_plan_exporte_remeasure_sur_la_seed_finale():
    """Anti-drift §6.3 : le plan exporté (`late_raws` STARTUP + GATED + jalons)
    est mesuré sur la SEED FINALE servie (structure rejouée + rapport C3), pas
    sur la seed de mesure A — sinon la disponibilité du rejoueur contredit
    l'analyse D4bis/C3 embarquée dans la même seed (drift de trigger de la 1re
    tech payante observé : pipe vs substation)."""
    from tool.generator.late_raws import LateRawsConfig, plan_from_seed

    lr_cfg = LateRawsConfig.from_config(GATING["late_raws"])
    exported_seen = 0
    for seed_value in (*range(0, 14), 50, 300, 600, 1400):
        db = db_for(seed_value)
        seed = generate_seed(db, GATING, validate=False)
        exported = seed.get("late_raws")
        recomputed = plan_from_seed(seed, lr_cfg)
        if exported is None:
            continue
        exported_seen += 1
        assert exported["startup"] == sorted(list(k) for k in recomputed.startup), (
            f"seed {seed_value}: startup exporté != startup remesuré "
            f"({[tuple(k) for k in exported['startup']]} != "
            f"{sorted(recomputed.startup)})"
        )
        assert exported["gated"] == {
            name: {"kind": kind, "tier": recomputed.floor_tier[(kind, name)]}
            for (kind, name) in recomputed.gated
        }, f"seed {seed_value}: jalons exportés != jalons remesurés"
    assert exported_seen >= 1, "aucune seed gatée exportée (test sans objet)"