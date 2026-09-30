"""Classement « late raws » (design jalons §6.2) — pass d'ANALYSE seule.

Rejoue une tranche de seeds via le pipeline ACTUEL (aucune modification du
graphe) et classe chaque ressource brute (patchs + lacs) :

- ``bucket`` C3 (extractor_timing) : starter / timed / random ;
- ``startup`` : fermeture D4bis de la « boîte du spawn » (recettes des techs
  gratuites + trigger 1re tech + fluides des bâtiments du spawn) ;
- ``first_claim`` : index de progression du PREMIER consommateur de la
  ressource (recette qui l'utilise en ingrédient) ;
- ``first_tier`` / ``first_pack`` : science pack (échelon de la chaîne §13)
  qui paie la tech du premier consommateur — le « S » du cap (§2).

Sortie : CSV par `(seed, recette d'extracteur, ressource)` + résumé agrégé.
Sert à dimensionner le report des late raws et le cap par science avant
d'implémenter la gating (§6.3).
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool.__main__ import _load_config, _load_db
from tool.common.db import SLOT_FLUID, SLOT_ITEM
from tool.generator.pipeline import generate_seed

DUMP = Path(__file__).resolve().parent.parent / "data" / "vanilla_dump.json"
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("/tmp/opencode/late_raws_classification.csv")


def _claim_indexes(tech_order: list[str], tech_by_id: dict) -> dict[str, int]:
    claim: dict[str, int] = {}
    for index, tech_id in enumerate(tech_order):
        tech = tech_by_id[tech_id]
        for effect in tech.get("effects", []):
            if effect.get("type") == "unlock-recipe":
                claim.setdefault(effect["recipe"], index)
    return claim


def _science_chain(claim: dict[str, int], recipes: list[dict]) -> list[str]:
    """Science packs ordonnés par leur déblocage (chaîne §13 : chacun coûte
    le précédent). Ordre de premier claim de leur recette."""
    packs = {
        r["results"][0]["name"]
        for r in recipes
        if r.get("results") and r["results"][0].get("type") == SLOT_ITEM
        and str(r["results"][0]["name"]).endswith("-science-pack")
    }
    return sorted(
        ({p: claim.get(f"randputf-{p}") for p in packs}),
        key=lambda p: (claim.get(f"randputf-{p}", 10**9), p),
    )


def _tech_tier(tech, chain: list[str]) -> tuple[int, str | None]:
    """Tier (échelon science) + pack de la tech : échelon max de ses packs."""
    packs = [i["name"] for i in tech.get("unit", {}).get("ingredients", [])]
    tiers = [(chain.index(p) if p in chain else -1, p) for p in packs]
    tiers = [(t, p) for t, p in tiers if t >= 0]
    if not tiers:
        return 0, None
    return max(t[0] for t in tiers), max(tiers, key=lambda t: t[0])[1]


def _startup_raw_resources(
    free_tech_ids: list[str],
    tech_order: list[str],
    tech_by_id: dict,
    recipes: list[dict],
    extracted: set[tuple[str, str]],
    building_fluid_assignments: dict,
) -> set[tuple[str, str]]:
    """Miroir de `extractor_timing._startup_raw_resources` sur la seed finale
    (progression_order + free_researches + recettes + assignations fluides)."""
    free_techs = set(free_tech_ids)
    free_recipes: set[str] = set()
    for tech_id in tech_order:
        if tech_id not in free_techs:
            continue
        for effect in tech_by_id[tech_id].get("effects", []):
            if effect.get("type") == "unlock-recipe":
                free_recipes.add(effect["recipe"])
    producers: dict[str, set[str]] = {}
    byname: dict[str, dict] = {}
    for recipe in recipes:
        byname[recipe["name"]] = recipe
        if recipe["name"] in free_recipes:
            for res in recipe.get("results", []):
                producers.setdefault(res["name"], set()).add(recipe["name"])
    roots: list[str] = sorted(free_recipes)
    after_free = [
        (i, t) for i, t in enumerate(tech_order) if t not in free_techs
    ]
    if after_free:
        trig = tech_by_id[after_free[0][1]].get("craft_trigger")
        if trig:
            roots.extend(sorted(producers.get(trig, ())))
    raws: set[tuple[str, str]] = set()
    processed: set[str] = set()
    while roots:
        name = roots.pop()
        if name in processed or name not in byname:
            continue
        processed.add(name)
        for ing in byname[name].get("ingredients", []):
            key = (ing.get("type"), ing.get("name"))
            if key in extracted:
                raws.add(key)
            else:
                roots.extend(p for p in producers.get(ing.get("name"), ()) if p not in processed)
    for assignment in building_fluid_assignments.values():
        inp = assignment.get("input")
        if inp:
            raws.add((SLOT_FLUID, inp))
    return raws


def classify_seed(seed: dict) -> list[dict[str, object]]:
    report = seed.get("extractor_timing") or {}
    tech_order = seed["progression_order"]
    tech_by_id = {t["id"]: t for t in seed["technologies"]}
    recipes = seed["recipes"]
    claim = _claim_indexes(tech_order, tech_by_id)
    chain = _science_chain(claim, recipes)

    extracted: set[tuple[str, str]] = {
        (r["type"], r["name"]) for rs in report.get("extractors", {}).values() for r in rs
    }
    startup_raw = _startup_raw_resources(
        seed["free_researches"], tech_order, tech_by_id, recipes, extracted,
        seed.get("building_fluid_assignments", {}),
    )

    first: dict[tuple[str, str], tuple[int, int, str | None]] = {}
    for recipe in recipes:
        i = claim.get(recipe["name"])
        if i is None:
            continue
        for ing in recipe.get("ingredients", []):
            key = (ing.get("type"), ing.get("name"))
            if key not in extracted:
                continue
            tier, pack = _tech_tier(tech_by_id[tech_order[i]], chain)
            if key not in first or i < first[key][0]:
                first[key] = (i, tier, pack)

    lines: list[dict[str, object]] = []
    for recipe, rs in report.get("extractors", {}).items():
        for r in rs:
            key = (r["type"], r["name"])
            fc = first.get(key)
            lines.append({
                "seed": seed["meta"]["seed"],
                "recipe": recipe,
                "raw_type": r["type"],
                "raw": r["name"],
                "bucket": _bucket_of(report, recipe),
                "startup": key in startup_raw,
                "first_claim": fc[0] if fc else None,
                "first_tier": fc[1] if fc else None,
                "first_pack": fc[2] if fc else None,
            })
    return lines


def _bucket_of(report: dict, recipe: str) -> str:
    for bucket in ("starter", "timed", "random"):
        if recipe in report.get(bucket, []):
            return bucket
    return "?"


def main() -> int:
    cfg = _load_config()
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 201
    rows: list[dict[str, object]] = []
    per_seed: dict[int, Counter] = {}
    late_tier: Counter = Counter()
    late_never: int = 0
    plateau_sizes: list[int] = []
    for seed_value in range(lo, hi):
        db = _load_db(False, DUMP)
        db.seed_value = seed_value
        cfg2 = dict(cfg)
        cfg2["seed"] = seed_value
        seed = generate_seed(db, cfg2, validate=False)
        lines = classify_seed(seed)
        rows.extend(lines)
        c = Counter(l["bucket"] for l in lines)
        per_seed[seed_value] = c
        plateau_sizes.append(len(seed["free_researches"]))
        for l in lines:
            if l["bucket"] != "starter":
                if l["first_claim"] is None:
                    late_never += 1
                else:
                    late_tier[l["first_tier"]] += 1

    with OUT.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "seed", "recipe", "raw_type", "raw", "bucket",
            "startup", "first_claim", "first_tier", "first_pack",
        ])
        writer.writeheader()
        writer.writerows(rows)

    total_starter = sum(c["starter"] for c in per_seed.values())
    total_timed = sum(c["timed"] for c in per_seed.values())
    total_random = sum(c["random"] for c in per_seed.values())
    n_seeds = hi - lo
    print(f"seeds {lo}-{hi-1}: {n_seeds} | plateau gratuit {min(plateau_sizes)}..{max(plateau_sizes)}")
    print(f"extracteurs: {total_starter} starter, {total_timed} timed, {total_random} random "
          f"({n_seeds} seeds)")
    per_seed_late = {s: c["timed"] + c["random"] for s, c in per_seed.items()}
    vals = sorted(per_seed_late.values())
    print(f"late raws par seed: min {vals[0]}, median {vals[len(vals)//2]}, "
          f"max {vals[-1]}; seeds sans late raw: {sum(1 for v in vals if v==0)}")
    print(f"late jamais consommés: {late_never}")
    print("late consommés par science-tier (échelon max du 1er pack):")
    for tier, n in sorted(late_tier.items(), key=lambda kv: (kv[0] or -1)):
        print(f"  tier {tier}: {n}")
    print(f"écrit: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())