"""C3 — déblocage « juste-au-besoin » des extracteurs (niveau seed).

Passe post-récursion / post-ease (pipeline.generate_seed), juste avant la
deuxième passe de garantie d'usage (usage_pass). La tech gratuite
``randputf-starter-extraction`` débloque la recette de craft de TOUS les
extracteurs du run (patchs + lacs, §7/§7.5) — même ceux dont la ressource
n'est consommée qu'en profondeur de seed, ou jamais. C3 repositionne ces
claims d'unlock :

- ressource consommée dès le starter → l'extracteur reste (ou revient) dans
  ``randputf-starter-extraction`` (tech gratuite) ;
- ressource consommée plus tard → le claim est posé au plus tard à
  ``max(first-consumer, atelier)`` : à la fois quand la ressource devient utile
  ET quand l'atelier qui fabrique l'extracteur est débloqué (contrainte D2 U2
  « bâtiment avant recette », déjà appliquée par la passe usage antérieure) ;
- ressource jamais consommée → le claim part sur un step PAYANT tiré
  aléatoirement (stream RNG dédié et déterministe, façon balayage §9.6),
  toujours ≥ l'index de l'atelier.

Seules les listes ``unlocks_recipes`` des macro-steps sont mutées : le graphe
produit→ingrédient reste intact, l'« unlock unique » (§13) est préservé.

Invariant garanti par construction : ``claim ≥ atelier`` (craftable dès le
claim, miroir D2 U2) et ``claim ≤ max(premier-usage, atelier)`` (utile dès que
possible — l'extracteur n'est JAMAIS débloqué après le moment où sa ressource
est réellement nécessaire et sa fabrication permise).

Sûreté (vérifiée, pas une mécanique) :
- la recette d'extracteur est FORCÉE au starter (``force=True``, ingrédients du
  watershed pré-élec) → craftable dès son claim quel que soit l'index ;
- les science packs sont créés avec ``forbidden=raw_resources`` (§13) → la tech
  qui paie un claim ne dépend jamais de la ressource gateée (pas de circularité
  coût↔extraction) ;
- l'électricité est garantie au starter (§10) → un premier consommateur profond
  est forcément après le générateur : jamais d'extracteur électrique réclamé
  avant de pouvoir fonctionner.
"""

from __future__ import annotations

import logging
import random

from tool.common.db import VanillaDB
from tool.generator.recipes import _item_for_building

log = logging.getLogger(__name__)

STARTER_EXTRACTION_ID = "randputf-starter-extraction"


def _extractor_resources(db: VanillaDB, state) -> dict[str, list[tuple[str, str]]]:
    """Recette d'extracteur -> ressources extraites (groupées par recette).

    Miroir de `starter_chain.build_tech_steps` (extractor_item_recipes) : les
    steps ``"type": "extract"`` portent resource + extracteur ; la recette
    canonique de l'item qui place l'extracteur est ``randputf-<item>``.
    """
    by_recipe: dict[str, list[tuple[str, str]]] = {}
    for step in state.steps:
        if step.get("type") != "extract":
            continue
        item = _item_for_building(db, step["extractor"])
        if item is None:
            continue
        res = step["resource"]
        by_recipe.setdefault(f"randputf-{item.name}", []).append(
            (res["type"], res["name"])
        )
    return by_recipe


def _claim_indexes(steps: list[dict]) -> dict[str, int]:
    """Index du PREMIER step qui réclame chaque recette — miroir de
    `usage_pass._claim_index` : une recette ``randputf-<x>`` est aussi réclamée
    par ``unlocks_buildings: [x]`` (les techs bâtiments, ex. génératrices)."""
    out: dict[str, int] = {}
    for index, step in enumerate(steps):
        for name in step.get("unlocks_recipes", []):
            out.setdefault(name, index)
        for building in step.get("unlocks_buildings", []):
            out.setdefault(f"randputf-{building}", index)
    return out


def _first_consumers(
    state, claim: dict[str, int], resources: set[tuple[str, str]]
) -> dict[tuple[str, str], int]:
    """Premier consommateur (index de claim) par ressource extraite.

    Une ressource absente du résultat n'est consommée par AUCUNE recette
    claimée — l'extracteur est alors « jamais utilisé » (fallback aléatoire).
    """
    first: dict[tuple[str, str], int] = {}
    for recipe in state.recipes:
        i = claim.get(recipe["name"])
        if i is None:
            continue
        for ing in recipe.get("ingredients", []):
            key = (ing.get("type"), ing.get("name"))
            if key not in resources:
                continue
            if key not in first or i < first[key]:
                first[key] = i
    return first


def _atelier_claim(
    state, db: VanillaDB, claim: dict[str, int], kit: set[str], recipe_name: str
) -> int:
    """Index du déblocage de l'atelier qui fabrique ``recipe_name`` (0 si kit
    ou sans atelier). L'extracteur ne peut être débloqué avant que l'atelier
    qui le fabrique soit disponible (U2)."""
    recipe = next((r for r in state.recipes if r["name"] == recipe_name), None)
    if recipe is None:
        return 0
    crafted_in = recipe.get("crafted_in")
    if not crafted_in or crafted_in in kit:
        return 0
    return claim.get(f"randputf-{crafted_in}", 0)


def _kit_buildings(starter, db: VanillaDB) -> set[str]:
    """Bâtiments fournis par le kit de départ (réputés débloqués en tech 0)."""
    kit: set[str] = set()
    for entry in starter.kit:
        if entry.get("type") != "item":
            continue
        item = db.items.get(entry["name"])
        if item is not None and item.place_result in db.buildings:
            kit.add(item.place_result)
    return kit


def _move_claim(source: int, target: int, steps: list[dict], recipe: str) -> None:
    """Déplace ``recipe`` de steps[source] vers steps[target] (unlock unique)."""
    if source == target:
        return
    steps[source]["unlocks_recipes"] = [
        r for r in steps[source]["unlocks_recipes"] if r != recipe
    ]
    steps[target].setdefault("unlocks_recipes", []).append(recipe)


def apply_extractor_timing(
    db: VanillaDB, starter, all_tech_steps: list[dict], *, seed_value: int
) -> dict:
    """Applique le déblocage juste-au-besoin. Retourne un rapport sérialisable
    (l'audit et les tests le rejoignent comme source de vérité)."""
    report: dict = {"extractors": {}, "starter": [], "timed": [], "random": []}
    extractors = _extractor_resources(db, starter.state)
    if not extractors:
        return report

    claim = _claim_indexes(all_tech_steps)
    resources = {resource for rs in extractors.values() for resource in rs}
    first = _first_consumers(starter.state, claim, resources)
    kit = _kit_buildings(starter, db)
    extraction_idx = next(
        (i for i, step in enumerate(all_tech_steps)
         if step.get("id") == STARTER_EXTRACTION_ID),
        None,
    )

    rng = random.Random(f"randputf:extractor-timing:{seed_value}")
    free_count = len(starter.tech_steps)
    paid = list(range(free_count, len(all_tech_steps)))

    for recipe, rs in sorted(extractors.items()):
        s = claim.get(recipe)
        if s is None:
            continue
        report["extractors"][recipe] = [
            {"type": kind, "name": name} for kind, name in rs
        ]
        atelier = _atelier_claim(starter.state, db, claim, kit, recipe)
        needy = [first[key] for key in rs if key in first]
        needed = min(needy) if needy else None

        if needed is None:
            # Jamais consommé : comme les autres bâtiments (§9.6), le claim part
            # sur un step payant, tiré sur un RNG dédié déterministe, et jamais
            # avant l'atelier qui le fabrique.
            target = max(rng.choice(paid), atelier) if paid else atelier
        else:
            # Au plus tard à (premier usage, atelier) : utile dès que possible
            # ET fabriquable dès le claim (U2).
            target = max(needed, atelier)

        if target != s:
            _move_claim(s, target, all_tech_steps, recipe)
        if target == extraction_idx:
            bucket = "starter"
        else:
            bucket = "random" if needed is None else "timed"
        report[bucket].append(recipe)

    if report["timed"] or report["random"]:
        log.info(
            "[randputF] extractor_timing: %d au starter, %d au premier usage, "
            "%d aléatoires (jamais utilisés)",
            len(report["starter"]), len(report["timed"]), len(report["random"]),
        )
    return report