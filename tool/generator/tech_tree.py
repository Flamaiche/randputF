"""Arbre technologique linéaire valide (README §13).

Chaque groupe de steps consécutifs produit UNE technologie qui débloque
**1 objet de base, étendu en chaîne probabiliste** (un objet = un
unlock-recipe) : 75 % de chance d'un 2e, 65 % d'un 3e, 35 % d'un 4e,
15 % d'un 5e (probabilités configurables via `tree.group_chances`). Les
prérequis suivent strictement l'ordre du graphe (aucune boucle) ; l'arbre
reste linéaire v1.

Le coût d'une tech peut mêler PLUSIEURS science packs (façon vanilla) : on
rassemble les packs des steps fusionnés et chaque tech paie d'autant plus de
packs qu'elle est avancée. Le branchement en arborescence reste hors scope v1.
"""

from __future__ import annotations

import hashlib
import random

from tool.common.db import POWER_POLES

# Durée de recherche par unité (secondes). Avec `amount = 1` par pack, la jauge
# de recherche compte exactement le nombre de cycles (packs) à fournir (§13).
_DEFAULT_RESEARCH_TIME = 60

# Nombre max de science packs DIFFÉRENTS demandés par une tech (façon vanilla,
# les techs avancées combinent typiquement jusqu'à 4 packs).
_MAX_COST_PACKS = 4

# Plafond ABSOLU d'objets (unlocks) par tech : 1 de base + 4 extensions de
# _config_group_chances (aucune tech au-delà de 5 objets).
_MAX_PER_TECH = 1 + 4

# Probabilités d'extension du groupe (§13) : après le 1er objet, chance d'en
# ajouter un 2e, puis un 3e, un 4e, un 5e. Tirage en chaîne (on s'arrête au
# premier tirage raté). Défauts repris dans config/settings.yaml.
_DEFAULT_GROUP_CHANCES = (0.75, 0.65, 0.35, 0.15)

_config_group_chances = _DEFAULT_GROUP_CHANCES


def _count_objects(step: dict) -> int:
    """Nombre d'« objets » débloqués par un step : chaque unlock-recipe compte
    pour un objet (une recette = un effet unlock-recipe, un bâtiment devient
    aussi un unlock-recipe randputf-<bâtiment>)."""
    return len(step.get("unlocks_recipes", [])) + len(step.get("unlocks_buildings", []))


def _step_unlocks_pole(step: dict) -> bool:
    """Un step débloque un VRAI pylône (poteau électrique) ?

    Deux étapes débloquant chacune un pylône ne doivent JAMAIS être fusionnées
    dans la même tech : la cadence garantie des pôles (§9.4) exige des
    positions d'arbre DISTINCTES (vérifiée en test)."""
    for building in step.get("unlocks_buildings", []):
        if building in POWER_POLES:
            return True
    for recipe in step.get("unlocks_recipes", []):
        name = recipe[len("randputf-"):] if recipe.startswith("randputf-") else recipe
        if name in POWER_POLES:
            return True
    return False


def _is_science_step(step: dict) -> bool:
    """Un step de la catégorie science débloque un NOUVEAU science pack.

    Il doit rester isolé (jamais fusionné) : le pack qu'il rend unlocké est
    consommé par les steps SUIVANTS comme coût — si on le fusionnait avec un
    consommateur, le pack serait payé par la même tech que celle qui
    l'unlocke, cassant l'invariant de « production avant consommation » (§13)."""
    return (step.get("id") or "").startswith("randputf-science-")


def _is_free_step(step: dict) -> bool:
    """Tech sans coût (gratuite, auto-complétée au runtime) : starter."""
    count = step.get("count", 10)
    cost = step.get("cost", [])
    return count <= 1 and (not cost or cost == [])


def _per_pack_count(depth: int, total: int) -> int:
    """Quantité (cycles) payable de CHAQUE pack pour une tech de profondeur
    donnée. Déterministe par graine (hash de la profondeur), croît avec la
    profondeur : une tech en profondeur exige plus de packs qu'un début."""
    ratio = depth / max(total - 1, 1)
    if ratio < 0.3:
        lo, hi = 5, 10
    elif ratio < 0.7:
        lo, hi = 12, 24
    else:
        lo, hi = 28, 60
    seed = int(hashlib.md5(f"count:{depth}".encode()).hexdigest()[:4], 16)
    return lo + (seed % (hi - lo + 1))


def set_config(config: dict) -> None:
    """§13 : probabilités d'extension du nombre d'objets par tech (chaîne de
    1..5), lues dans ``tree.group_chances`` (liste de 4 probabilités)."""
    global _config_group_chances
    chances = (config.get("tree") or {}).get("group_chances", None)
    if chances is None:
        _config_group_chances = _DEFAULT_GROUP_CHANCES
    else:
        values = tuple(max(0.0, min(float(c), 1.0)) for c in chances)
        if 1 <= len(values) <= 4:
            _config_group_chances = values


def _roll_group_size(rng: random.Random) -> int:
    """Taille (en objets) d'une tech PAYANTE groupable, tirée en chaîne :
    1 objet de base, puis une chance d'extension pour chaque objet suivant
    (75 % → 2e, 65 % → 3e, 35 % → 4e, 15 % → 5e par défaut). Le premier
    tirage raté stoppe la chaîne."""
    size = 1
    for probability in _config_group_chances:
        if rng.random() >= probability:
            break
        size += 1
    return size


def _collect_packs(steps: list[dict], limit: int = _MAX_COST_PACKS) -> list[str]:
    """Packs distincts demandés par un ensemble de steps, ordre d'apparition."""
    packs: list[str] = []
    for step in steps:
        for ing in step.get("cost", []):
            name = ing.get("name")
            if name and name not in packs:
                packs.append(name)
    return packs[:limit]


def build_linear_tech_tree(
    steps: list[dict],
    rng: random.Random,
) -> list[dict]:
    """Assemble un arbre technologique linéaire à partir des macro-steps.

    Regroupe les steps payants CONSECUTIFS en techs dont le nombre d'objets
    suit la chaîne probabiliste (§13) : 1 objet de base, extensions 75/65/35/15
    % ; les techs gratuites du starter, les prologue (hand-craft) et la tech
    endgame restent des nœuds dédiés. Unlock UNIQUE (§13) : une recette n'est
    débloquée que par la PREMIÈRE tech qui la revendique.
    """
    technologies: list[dict] = []
    previous_id: str | None = None
    unlocked_recipes: set[str] = set()

    # ── Groupement des steps payants consécutifs (taille tirée en chaîne) ────
    groups: list[dict] = []          # {kind, steps}
    cur_paid: list[dict] = []
    cur_objs = 0
    cur_target = 1
    cur_has_pole = False

    def flush_paid() -> bool:
        nonlocal cur_paid, cur_objs, cur_target, cur_has_pole
        if not cur_paid:
            return False
        groups.append({"kind": "paid", "steps": cur_paid})
        cur_paid = []
        cur_objs = 0
        cur_target = 1
        cur_has_pole = False
        return True

    for step in steps:
        if step.get("craft_trigger"):
            # Prologue relais : se débloque par hand-craft, nœud dédié.
            flush_paid()
            groups.append({"kind": "trigger", "steps": [step]})
            continue

        if (step.get("id") or "") == "randputf-endgame-rocket":
            # Tech finale de la fusée (§14) : nœud dédié, jamais fusionnée.
            flush_paid()
            groups.append({"kind": "endgame", "steps": [step]})
            continue

        if _is_free_step(step):
            # Tech gratuite du starter : nœud dédié.
            flush_paid()
            groups.append({"kind": "free", "steps": [step]})
            continue

        # Step PAYANT, groupable.
        objs = _count_objects(step)
        is_science = _is_science_step(step)
        is_isolated = step.get("isolate") or False
        step_has_pole = _step_unlocks_pole(step)

        if not cur_paid:
            # Nouveau groupe : on tire sa taille (nb d'objets) en chaîne.
            cur_target = _roll_group_size(rng)

        flush_before = (
            is_science
            or is_isolated
            or (cur_has_pole and step_has_pole)
            or (cur_objs + objs > _MAX_PER_TECH)
            or (cur_objs + objs > cur_target)
        )
        if flush_before and flush_paid():
            # Un groupe vient d'être vidé : ce step ouvre un NOUVEAU groupe,
            # on tire sa taille (nb d'objets) en chaîne.
            cur_target = _roll_group_size(rng)

        cur_paid.append(step)
        cur_objs += objs
        if step_has_pole:
            cur_has_pole = True

        if is_science or is_isolated:
            # Isole le step science (le pack qu'il débloque est consommé par
            # les steps SUIVANTS comme coût — jamais fusionné avec eux, §13) et
            # les steps DISPATCH isolés (ammo de véhicule §12.1, chaque dispatch
            # garde sa propre tech avant celle du véhicule).
            flush_paid()
    flush_paid()

    # ── Coût multi-packs de la tech endgame (packs les plus avancés) ────────
    all_packs = _collect_packs(steps, limit=None)
    endgame_packs = all_packs[-_MAX_COST_PACKS:] if all_packs else []

    n_paid = sum(1 for g in groups if g["kind"] == "paid")
    paid_index = 0

    # ── Conversion des groupes en technologies ──────────────────────────────
    for group in groups:
        kind = group["kind"]
        gsteps = group["steps"]
        claimed: list[str] = []
        for step in gsteps:
            for recipe in step.get("unlocks_recipes", []):
                if recipe not in unlocked_recipes:
                    unlocked_recipes.add(recipe)
                    claimed.append(recipe)
            for building in step.get("unlocks_buildings", []):
                recipe = f"randputf-{building}"
                if recipe not in unlocked_recipes:
                    unlocked_recipes.add(recipe)
                    claimed.append(recipe)
        effects = [{"type": "unlock-recipe", "recipe": r} for r in claimed]

        if kind == "free":
            unit = {"count": 1, "time": 1, "ingredients": []}
        elif kind == "trigger":
            unit = {"count": 1, "time": 1, "ingredients": []}
        elif kind == "endgame":
            if endgame_packs:
                q = _per_pack_count(max(n_paid, 1), max(n_paid, 1))
                unit = {
                    "count": q,
                    "time": _DEFAULT_RESEARCH_TIME,
                    "ingredients": [
                        {"type": "item", "name": p, "amount": 1} for p in endgame_packs
                    ],
                }
            else:
                unit = {"count": 1, "time": 1, "ingredients": []}
        else:  # paid
            packs = _collect_packs(gsteps)
            if not packs:
                # Fallback : aucune source de coût (cas limite) -> gratuit.
                unit = {"count": 1, "time": 1, "ingredients": []}
            else:
                q = _per_pack_count(paid_index, max(n_paid, 1))
                unit = {
                    "count": q,
                    "time": _DEFAULT_RESEARCH_TIME,
                    "ingredients": [
                        {"type": "item", "name": p, "amount": 1} for p in packs
                    ],
                }
            paid_index += 1

        tech_id = gsteps[0].get("id") or f"randputf-step-{len(technologies)}"
        tech = {
            "id": tech_id,
            "localised_name": gsteps[0].get("title") or tech_id,
            "prerequisites": [previous_id] if previous_id else [],
            "unit": unit,
            "effects": effects,
        }
        if kind == "trigger":
            tech["craft_trigger"] = gsteps[0]["craft_trigger"]
            tech["craft_trigger_count"] = gsteps[0].get(
                "craft_trigger_count", 1
            )

        technologies.append(tech)
        previous_id = tech_id

    return technologies
