"""Audit U1/U2 sur seed finale (Vérification post-génération D2).

Lit les claims d'unlock par tech via ``effects`` (unlock-recipe) — c'est la
forme canonique produite par `build_linear_tech_tree`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool.__main__ import _load_config, _load_db
from tool.generator.pipeline import generate_seed
from tool.generator.recipes import _is_atelier

DUMP = Path(__file__).resolve().parent.parent / "data" / "vanilla_dump.json"
TERMINALS = {"lab", "rocket-silo", "steam-generator"}
AFTER_PASS_PREFIXES = ("randputf-relay-", "randputf-ease-")


def _tech_unlocks(tech: dict) -> list[str]:
    """Noms de recettes revendiqués par une tech (unlock unique, claims)."""
    out = []
    for effect in tech.get("effects", []):
        if effect.get("type") == "unlock-recipe":
            out.append(effect["recipe"])
    return out


def audit(seed: dict, db) -> dict:
    recipes = seed["recipes"]
    techs = seed["technologies"]
    free_techs = set(seed["free_researches"])
    kit = set()
    for entry in seed["starter_kit"]:
        if entry.get("type") != "item":
            continue
        item = db.items.get(entry["name"])
        if item is not None and item.place_result in db.buildings:
            kit.add(item.place_result)

    idx: dict[str, int] = {}
    free: set[str] = set()
    for i, tech in enumerate(techs):
        for name in _tech_unlocks(tech):
            if name not in idx:
                idx[name] = i
                if tech["id"] in free_techs:
                    free.add(name)

    hosted_all: dict[str, list] = {}
    hosted_primary: dict[str, list] = {}
    for r in recipes:
        ci = r.get("crafted_in")
        if not ci:
            continue
        hosted_all.setdefault(ci, []).append(r)
        if not r["name"].startswith(AFTER_PASS_PREFIXES):
            hosted_primary.setdefault(ci, []).append(r)

    candidates = {
        b
        for b, rec in ((k.removeprefix("randputf-"), k)
                       for k in idx if k.startswith("randputf-"))
        if b in db.buildings and _is_atelier(db.buildings[b])
    }

    # U1 (recette randputf-<b> présente = « unlocké »), sur le PRIMAIRE :
    # les relais/ease sont créés APRÈS la passe, ils masqueraient les bâtiments
    # morts du primaire (spec D2). Bâtiments du kit et terminaux exclus.
    u1 = sorted(
        b for b in candidates
        if b not in kit and b not in TERMINALS
        and not hosted_primary.get(b)
    )

    # U2 sur TOUTES les recettes hébergées (relais compris, créés post-passe :
    # leurs techs prologue suivent le starter, donc « recette avant bâtiment »
    # ne peut venir que du primaire). Kit : bâtiment réputé tech 0.
    # Exemptions : double-free (recette ET bâtiment en techs gratuites, §7) ;
    # auto-consommation du bootstrap (§7) — l'item de R est consommé par une
    # recette débloquée AVANT le bâtiment, le déblocage précoce de R est alors
    # voulu et le repli « précéder B » créerait une recette injouable.
    def _item(r: dict) -> str:
        if r["name"].startswith("randputf-"):
            return r["name"].removeprefix("randputf-")
        results = r.get("results")
        return results[0]["name"] if results else ""

    def _consumed_before(item: str, i_b: int) -> bool:
        return any(
            r2["name"] != r["name"]
            and any(
                ing.get("type") != "fluid" and ing.get("name") == item
                for ing in r2.get("ingredients", [])
            )
            for r2 in recipes
            if idx.get(r2["name"]) is not None and idx[r2["name"]] < i_b
        )

    u2 = []
    for r in recipes:
        ci = r.get("crafted_in")
        if not ci:
            continue
        i_r = idx.get(r["name"])
        i_b = 0 if ci in kit else idx.get(f"randputf-{ci}")
        if i_r is None or i_b is None:
            continue
        if i_r < i_b and not (r["name"] in free and f"randputf-{ci}" in free):
            if _consumed_before(_item(r), i_b):
                continue
            u2.append((r["name"], ci, i_r, i_b))

    return {"u1": u1, "u2": u2, "extractors": audit_extractors(seed, db, idx, free)}


def audit_extractors(seed: dict, db, idx: dict[str, int], free: set[str]) -> list[str]:
    """C3 — déblocage « juste-au-besoin » des extracteurs.

    Rejoue l'invariant de `extractor_timing.apply_extractor_timing` sur la seed
    finale, à partir du mapping ``seed["extractor_timing"]["extractors"]``
    (source de vérité posée par la passe pipeline) :

    - EXT1 : ``claim(extracteur) ≥ claim(atelier)`` — craftable dès le claim
      (miroir D2 U2, « bâtiment avant recette ») ;
    - EXT2 : ressource consommée ⇒ ``claim ≤ max(premier-usage, claim(atelier))``
      — jamais débloqué après le moment où elle devient utile et fabriquable ;
    - EXT3 : ressource jamais consommée ⇒ le claim n'est PAS une tech gratuite
      (son extracteur suit le balayage §9.6).
    """
    report = seed.get("extractor_timing") or {}
    extractors = report.get("extractors", {})
    if not extractors:
        return []
    kit = set()
    for entry in seed.get("starter_kit") or []:
        if entry.get("type") != "item":
            continue
        item = db.items.get(entry["name"])
        if item is not None and item.place_result in db.buildings:
            kit.add(item.place_result)
    resources: set[tuple[str, str]] = {
        (res["type"], res["name"])
        for rs in extractors.values()
        for res in rs
    }
    first: dict[tuple[str, str], int] = {}
    for recipe in seed["recipes"]:
        i = idx.get(recipe["name"])
        if i is None:
            continue
        for ing in recipe.get("ingredients", []):
            key = (ing.get("type"), ing.get("name"))
            if key not in resources:
                continue
            if key not in first or i < first[key]:
                first[key] = i

    def _atelier(r: dict) -> int:
        ci = r.get("crafted_in")
        if not ci or ci in kit:
            return 0
        return idx.get(f"randputf-{ci}", 0)

    violations = []
    for name, rs in extractors.items():
        i_r = idx.get(name)
        if i_r is None:
            continue
        recipe = next(r for r in seed["recipes"] if r["name"] == name)
        atelier = _atelier(recipe)
        consumed = [
            first[(res["type"], res["name"])]
            for res in rs
            if (res["type"], res["name"]) in first
        ]
        if i_r < atelier:
            violations.append(f"{name}: claim {i_r} < atelier {atelier}")
        if consumed:
            bound = max(min(consumed), atelier)
            if i_r > bound:
                violations.append(
                    f"{name}: claim {i_r} > max(1er usage {min(consumed)}, "
                    f"atelier {atelier})"
                )
        elif name in free:
            violations.append(
                f"{name}: jamais consommé mais débloqué par une tech gratuite"
            )
    return violations


def main() -> int:
    cfg = _load_config()
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 201
    u1_total = u2_total = ex_total = 0
    bad_seeds = []
    for seed_value in range(lo, hi):
        db = _load_db(False, DUMP)
        db.seed_value = seed_value
        cfg2 = dict(cfg)
        cfg2["seed"] = seed_value
        seed = generate_seed(db, cfg2, validate=False)
        res = audit(seed, db)
        u1_total += len(res["u1"])
        u2_total += len(res["u2"])
        ex_total += len(res["extractors"])
        if res["u1"] or res["u2"] or res["extractors"]:
            bad_seeds.append(
                (seed_value, res["u1"], res["u2"][:3], res["extractors"][:3])
            )
    print(f"seeds {lo}-{hi-1}: U1 = {u1_total}, U2 = {u2_total}, "
          f"extracteurs = {ex_total}, "
          f"seeds violants = {len(bad_seeds)}")
    for s in bad_seeds[:20]:
        print("  ", s)
    return 0 if not bad_seeds else 1


if __name__ == "__main__":
    raise SystemExit(main())