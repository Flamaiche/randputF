"""Jalons de ressources « late raws » (§6.2/§6.3 du plan extracteurs, révisé).

Modèle utilisateur (disponibilité réelle, mesurable par le rejoueur) :
- TOUTES les raws NON-startup sont verrouillées à leur jalon : utilisables
  seulement quand le jalon de la ressource est débloqué (index du tech
  d'injection, exporté dans ``seed["late_raws"]``) ;
- au début, seules les raws MINABLES À LA MAIN utilisées par le starter
  (startup — boîte du spawn D4bis, jalon turn 1) sont disponibles ;
- le rejoueur respecte cette disponibilité : la carte n'est plus « infinie
  dès le spawn » pour les raws gatées — c'est ce qui rend le gating mesurable.

Architecture en 2 passes (déterministe, même seed) :
- passe A : pipeline ACTUEL (graphe complet) → mesure de la dépendance ;
- passe B : même prefixe (carte/électricité/starter identiques, flux RNG
  restauré), puis DÉGRADATION (les late raws sortent du pool ``obtained``),
  puis récursion avec injections de jalons (qui renseignent ``milestone_index``).

La dégradation est sûre par construction : les late raws sont par définition
hors de la fermeture D4bis du spawn — aucune recette gratuite/plateau ne les
consomme, aucune assignation fluide de l'électricité n'en dépend. Les recettes
promises du starter restent intactes ; seuls les markers ``obtained`` bougent.

Suffixe de pipeline factorisé dans ``pipeline._finalize_pipeline`` ; ce module
fournit config, plan (mesure passe A) et dégradation (passe B).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.common import config as _cfg
from tool.common.db import SLOT_ITEM


@dataclass
class LateRawsConfig:
    """Config de la section ``late_raws`` : activation et probabilité de pick
    (conservée pour compat ; l'injection est à 100 %, cf. LateRawsPlan)."""
    enabled: bool = False
    share: float = 0.25  # conservé pour compat config ; inutilisé (gating 100 %)
    pick_chance: float = 0.6

    @classmethod
    def from_config(cls, cfg: dict | None) -> "LateRawsConfig":
        """Construit la config depuis ``config["late_raws"]`` — défauts yaml."""
        raw = (cfg or {}).get("late_raws") or {}
        return cls(
            enabled=bool(raw.get("enabled", _cfg.default_value("late_raws", "enabled"))),
            share=float(raw.get("share", _cfg.default_value("late_raws", "share"))),
            pick_chance=float(raw.get("pick_chance", _cfg.default_value("late_raws", "pick_chance"))),
        )


@dataclass
class LateRawsPlan:
    """Plan des jalons décidé sur la passe A (modèle utilisateur §6 révisé) :

    TOUTES les raws NON-startup sont verrouillées à leur jalon — utilisables
    seulement une fois le jalon atteint ; les raws MINABLES À LA MAIN (celles que
    la fermeture D4bis du spawn consomme — startup) restent disponibles dès le
    départ (leur « jalon » est turn 1).

    - ``gated`` : {(kind, name)} — raws hors du pool de départ ;
    - ``startup`` : {(kind, name)} — raws de la boîte du spawn (jamais gatées) ;
    - ``floor_tier`` : {(kind, name): int} — JALON de la raw : échelon science
      (index de chaîne des packs) où elle « revient » — l'injection est
      DÉTERMINISTE au premier échelon ≥ plancher (pas de tirage) ;
    - ``pick_chance`` : conservé pour compat config ; inutilisé (injection 100 %).
    """

    gated: set[tuple[str, str]] = field(default_factory=set)
    startup: set[tuple[str, str]] = field(default_factory=set)
    floor_tier: dict[tuple[str, str], int] = field(default_factory=dict)
    pick_chance: float = 0.6

    @property
    def gated_fluids(self) -> frozenset[str]:
        """Noms des fluides gatés (raws non-item du plan)."""
        return frozenset(n for k, n in self.gated if k != SLOT_ITEM)

    def eligible(self, tier: int) -> list[tuple[str, str]]:
        """Raws (kind, nom) dont le jalon est débloqué à l'échelon ``tier``."""
        return [key for key, floor in self.floor_tier.items() if floor <= tier]


# --- Mesure de la dépendance sur la SEED finale (miroir de la classification
# --- tools/classify_late_raws.py, réutilisée telle quelle). ---------------


def _claim_indexes(tech_order: list[str], tech_by_id: dict) -> dict[str, int]:
    """Index de progression du premier tech qui débloque chaque recette."""
    claim: dict[str, int] = {}
    for index, tech_id in enumerate(tech_order):
        for effect in tech_by_id[tech_id].get("effects", []):
            if effect.get("type") == "unlock-recipe":
                claim.setdefault(effect["recipe"], index)
    return claim


def _science_chain(claim: dict[str, int], recipes: list[dict]) -> list[str]:
    """Science packs ordonnés par leur déblocage (chaîne §13 : chacun coûte
    le précédent)."""
    packs = {
        r["results"][0]["name"]
        for r in recipes
        if r.get("results") and r["results"][0].get("type") == SLOT_ITEM
        and str(r["results"][0]["name"]).endswith("-science-pack")
    }
    return sorted(
        packs,
        key=lambda p: (claim.get(f"randputf-{p}", 10**9), p),
    )


def _tech_tier(tech: dict, chain: list[str]) -> int:
    """Échelon science d'une tech : indice max de ses packs (0 si aucun)."""
    tiers = [
        chain.index(i["name"])
        for i in tech.get("unit", {}).get("ingredients", [])
        if i.get("name") in chain
    ]
    return max(tiers) if tiers else 0


def _startup_raw_resources(
    free_tech_ids: list[str],
    tech_order: list[str],
    tech_by_id: dict,
    recipes: list[dict],
    extracted: set[tuple[str, str]],
    building_fluid_assignments: dict,
) -> set[tuple[str, str]]:
    """Miroir seed de `extractor_timing._startup_raw_resources` (fermeture
    D4bis de la boîte du spawn : recettes gratuites + trigger de la 1re tech
    payante + fluides des bâtiments du spawn)."""
    free_recipes: set[str] = set()
    for tech_id in tech_order:
        if tech_id not in set(free_tech_ids):
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
    after_free = [(i, t) for i, t in enumerate(tech_order) if t not in set(free_tech_ids)]
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
                roots.extend(
                    p for p in producers.get(ing.get("name"), ()) if p not in processed
                )
    for assignment in building_fluid_assignments.values():
        inp = assignment.get("input")
        if inp:
            raws.add(("fluid", inp))
    return raws


def _usage_floors(
    tech_order: list[str],
    tech_by_id: dict,
    claim: dict[str, int],
    recipes: list[dict],
    tiers: list[int],
    candidates: set[tuple[str, str]],
) -> dict[tuple[str, str], int]:
    """Jalon « sûr » d'une raw gatée : le plus petit échelon science où elle est
    STRUCTURELLEMENT requise, scanné sur la partie REFAIE (passe B) :

    - 1er usage INGRÉDIENT d'une recette (jalon historique) ;
    - usage MACHINE (`crafted_in`) d'une recette — une raw peut être un
      bâtiment d'hébergement requis bien avant son 1er ingrédient ;
    - tout COÛT (packs) / DÉCLENCHEUR d'une tech de l'ordre linéaire dont la
      FERMETURE de fabrication la consomme (ingrédient ou machine).

    Rendre une raw disponible PLUS TARD que ce minimum rend la partie refaite
    ingagnable (ex. steel-furnace : machine de la fabrique de stone-furnace,
    requise par le coût de la 1re tech payante, verrouillée ensuite au tier de
    son 1er consommateur-ingrédient). Les fermetures sont RESTREINTES au
    préfixe de recettes débloquées ≤ l'index de la tech (déblocage séquentiel
    — miroir du replay)."""
    producers: dict[tuple[str, str], list[dict]] = {}
    for r in recipes:
        for res in r.get("results", []):
            producers.setdefault((res.get("type"), res.get("name")), []).append(r)

    floors: dict[tuple[str, str], int] = {}

    # (1) Ingrédients + machines des recettes débloquées (jalon historique).
    for recipe in recipes:
        claimed = claim.get(recipe["name"])
        if claimed is None:
            continue
        tier = tiers[claimed]
        for ing in recipe.get("ingredients", []):
            key = (ing.get("type"), ing.get("name"))
            if key in candidates:
                floors[key] = min(floors.get(key, tier), tier)
        machine = recipe.get("crafted_in")
        if machine and (SLOT_ITEM, machine) in candidates:
            key = (SLOT_ITEM, machine)
            floors[key] = min(floors.get(key, tier), tier)

    if not candidates:
        return floors

    # (2) Coûts/déclencheurs des techs : fermeture de fabrication du préfixe.
    for i, tech_id in enumerate(tech_order):
        tech = tech_by_id[tech_id]
        tier = tiers[i]
        roots: list[tuple[str, str]] = [
            (ing.get("type"), ing.get("name"))
            for ing in (tech.get("unit") or {}).get("ingredients", [])
        ]
        trig = tech.get("craft_trigger")
        if trig:
            roots.append((SLOT_ITEM, trig))
        seen: set[tuple[str, str]] = set()
        stack = list(roots)
        while stack:
            key = stack.pop()
            if key[1] is None or key in seen:
                continue
            seen.add(key)
            for r in producers.get(key, ()):
                if claim.get(r["name"], 10**9) > i:
                    continue
                machine = r.get("crafted_in")
                if machine:
                    stack.append((SLOT_ITEM, machine))
                for ing in r.get("ingredients", []):
                    stack.append((ing.get("type"), ing.get("name")))
        hits = seen & candidates
        for h in hits:
            floors[h] = min(floors.get(h, tier), tier)

    return floors


def plan_from_seed(seed: dict, cfg: LateRawsConfig) -> LateRawsPlan:
    """Mesure la dépendance au début sur la seed de la passe A et sélectionne
    les late raws — TOUTES les raws non-startup (plus de share : le gating ne
    souffre pas d'exception) — + leurs échelons plancher (= tier du 1er
    consommateur)."""
    tech_order = seed["progression_order"]
    tech_by_id = {t["id"]: t for t in seed["technologies"]}
    recipes = seed["recipes"]
    claim = _claim_indexes(tech_order, tech_by_id)
    chain = _science_chain(claim, recipes)
    tiers = [_tech_tier(tech_by_id[t], chain) for t in tech_order]

    report = seed.get("extractor_timing") or {}
    extracted: set[tuple[str, str]] = set()
    for rs in report.get("extractors", {}).values():
        extracted.update((r["type"], r["name"]) for r in rs)

    startup_raw = _startup_raw_resources(
        seed.get("free_researches", []),
        tech_order,
        tech_by_id,
        recipes,
        extracted,
        seed.get("building_fluid_assignments", {}),
    )

    first: dict[tuple[str, str], tuple[int, int]] = {}
    for recipe in recipes:
        i = claim.get(recipe["name"])
        if i is None:
            continue
        for ing in recipe.get("ingredients", []):
            key = (ing.get("type"), ing.get("name"))
            if key not in extracted:
                continue
            if key not in first or i < first[key][0]:
                first[key] = (i, tiers[i])

    max_tier = max(tiers) if tiers else 0
    raws = sorted(
        extracted,
        key=lambda key: (
            0 if key in startup_raw else 1,
            first.get(key, (10**9, max_tier))[0],
            key,
        ),
    )
    # Toutes les raws HORS de la boîte du spawn (D4bis) sont gatées : elles ne
    # redeviennent obtenables qu'au jalon de leur 1er consommateur. Les raws
    # startup restent libres (jamais gated — la dégradation leur couperait le
    # bootstrap électricité/lab).
    candidates = [key for key in raws if key not in startup_raw]

    # Jalon « sûr » : plancher = plus petit échelon science où la partie REFAIE
    # (passe B) requiert réellement la raw — ingrédients + machines + coûts et
    # déclencheurs des techs (see _usage_floors). Sans cela, un bâtiment gaté
    # utilisé comme machine par un coût de tech early rend la partie refaite
    # ingagnable (régression seed 1299).
    floors = _usage_floors(
        tech_order, tech_by_id, claim, recipes, tiers, set(candidates)
    )
    for key in candidates:
        # Jamais requis structurellement (ni ingrédient, ni machine, ni coût) :
        # le jalon tombe au sommet de la chaîne (comportement historique).
        floors.setdefault(key, max_tier)

    return LateRawsPlan(
        gated=set(candidates),
        startup=set(startup_raw),
        floor_tier=floors,
        pick_chance=cfg.pick_chance,
    )


def degrade(state, base, plan: LateRawsPlan) -> None:
    """Retire les late raws du pool de départ (état courant + base gelée).

    Les recettes déjà posées qui les consommeraient sont, par construction de
    la fermeture D4bis, inexistantes — les markers ``obtained`` sont les seules
    traces (les étapes d'extraction et leurs recettes d'extracteur restent :
    outils génériques). Seule l'AVAILABILITÉ de la ressource est reportée au
    jalon."""
    for kind, name in plan.gated:
        if kind == SLOT_ITEM:
            state.obtained_items.discard(name)
            base.obtained_items.discard(name)
        else:
            state.obtained_fluids.discard(name)
            base.obtained_fluids.discard(name)


__all__ = [
    "LateRawsConfig",
    "LateRawsPlan",
    "degrade",
    "plan_from_seed",
]