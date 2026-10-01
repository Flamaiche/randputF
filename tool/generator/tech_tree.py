"""Arbre technologique linéaire valide (§13).

Chaque groupe de steps consécutifs produit UNE technologie qui débloque un
objet de base, étendu en chaîne probabiliste (75/65/35/15 % via
`tree.group_chances`) ; prérequis suivant l'ordre du graphe (aucune boucle,
arbre linéaire v1). Coût d'une tech = plusieurs science packs (les techs
avancées en combinent typiquement jusqu'à 4).
"""

from __future__ import annotations

import hashlib
import random

from tool.common import config as _cfg
from tool.common.db import VanillaDB

# Durée de recherche par unité (secondes). Avec `amount = 1` par pack, la
# jauge compte exactement le nombre de cycles (packs) à fournir (§13).
# Valeurs dans ``config/defaults.yaml`` (section ``tree``) :
# research_time=60, max_cost_packs=4, max_per_tech=5 (1 + 4 extensions).

_config_group_chances = tuple(_cfg.default_value("tree", "group_chances"))
_config_research_time = int(_cfg.default_value("tree", "research_time"))
_config_max_cost_packs = max(1, int(_cfg.default_value("tree", "max_cost_packs")))
_config_max_per_tech = max(1, int(_cfg.default_value("tree", "max_per_tech")))


def _count_objects(step: dict) -> int:
    """Objets débloqués par un step : chaque unlock-recipe compte pour un objet
    (un bâtiment devient aussi un unlock-recipe randputf-<bâtiment>)."""
    return len(step.get("unlocks_recipes", [])) + len(step.get("unlocks_buildings", []))


def _step_unlocks_pole(step: dict, db: VanillaDB) -> bool:
    """Un step débloque un VRAI pylône (poteau électrique) ?

    Deux étapes débloquant chacune un pylône ne doivent jamais être fusionnées
    dans la même tech : la cadence des pôles (§9.4) exige des positions
    d'arbre distinctes (vérifié en test)."""
    for building in step.get("unlocks_buildings", []):
        b = db.buildings.get(building)
        if b and b.is_power_pole:
            return True
    for recipe in step.get("unlocks_recipes", []):
        name = recipe[len("randputf-"):] if recipe.startswith("randputf-") else recipe
        b = db.buildings.get(name)
        if b and b.is_power_pole:
            return True
    return False


def _step_unlocks_handheld_gun(step: dict, db: VanillaDB) -> bool:
    """Un step débloque une arme de poing ?

    Deux steps d'armes ne doivent jamais être fusionnés dans la même tech :
    chaque arme arrive avec SA munition unique (§11), jamais avec toute celle
    du lot (bug « arme + toutes les munitions dans la même tech »)."""
    for recipe in step.get("unlocks_recipes", []):
        name = recipe[len("randputf-"):] if recipe.startswith("randputf-") else recipe
        item = db.items.get(name)
        if item is not None and item.is_handheld_gun:
            return True
    return False


def _is_science_step(step: dict) -> bool:
    """Step science débloquant un NOUVEAU science pack : il doit rester isolé
    (jamais fusionné), sinon le pack serait payé par la tech qui l'unlocke,
    cassant « production avant consommation » (§13)."""
    return (step.get("id") or "").startswith("randputf-science-")


def _is_free_step(step: dict) -> bool:
    """Tech sans coût (gratuite, auto-complétée au runtime) : starter."""
    count = step.get("count", 10)
    cost = step.get("cost", [])
    return count <= 1 and (not cost or cost == [])


def _per_pack_count(depth: int, total: int) -> int:
    """Cycles payables de CHAQUE pack pour une tech de profondeur donnée :
    déterministe par graine (hash de la profondeur), croît avec la profondeur
    (une tech profonde exige plus de packs)."""
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
    """§13 : réglages de l'arbre lus dans la section ``tree`` — probabilités
    d'extension du nombre d'objets par tech (chaîne de 1..5,
    ``group_chances``), durée de recherche par unité, nombre max de packs
    différents par tech et plafond d'unlocks par tech. Défauts dans
    ``config/defaults.yaml``."""
    global _config_group_chances, _config_research_time
    global _config_max_cost_packs, _config_max_per_tech
    tree_cfg = config.get("tree") or {}
    chances = tree_cfg.get("group_chances", None)
    if chances is None:
        _config_group_chances = tuple(_cfg.default_value("tree", "group_chances"))
    else:
        values = tuple(max(0.0, min(float(c), 1.0)) for c in chances)
        if 1 <= len(values) <= 4:
            _config_group_chances = values
    _config_research_time = int(
        tree_cfg.get("research_time", _cfg.default_value("tree", "research_time"))
    )
    _config_max_cost_packs = int(
        tree_cfg.get("max_cost_packs", _cfg.default_value("tree", "max_cost_packs"))
    )
    _config_max_per_tech = int(
        tree_cfg.get("max_per_tech", _cfg.default_value("tree", "max_per_tech"))
    )


def _roll_group_size(rng: random.Random) -> int:
    """Taille (objets) d'une tech payante groupable, tirée en chaîne : 1 objet
    de base, puis une chance d'extension par objet suivant (75/65/35/15 % par
    défaut) ; premier échec = arrêt."""
    size = 1
    for probability in _config_group_chances:
        if rng.random() >= probability:
            break
        size += 1
    return size


def _collect_packs(steps: list[dict], limit: int | None = None) -> list[str]:
    """Packs distincts demandés par un ensemble de steps, ordre d'apparition.

    ``limit=None`` = AUCUNE coupure (liste complète) ; ``limit`` entier borne
    le nombre de packs distincts (max par tech, §13 — cf. set_config)."""
    packs: list[str] = []
    for step in steps:
        for ing in step.get("cost", []):
            name = ing.get("name")
            if name and name not in packs:
                packs.append(name)
    return packs if limit is None else packs[:limit]


def build_linear_tech_tree(
    steps: list[dict],
    rng: random.Random,
    db: VanillaDB,
) -> list[dict]:
    """Assemble un arbre technologique linéaire à partir des macro-steps.

    Regroupe les steps payants consécutifs en techs dont le nombre d'objets
    suit la chaîne probabiliste (§13) ; les techs gratuites du starter, les
    prologue (hand-craft) et la tech endgame restent des nœuds dédiés.
    Unlock unique (§13) : une recette n'est débloquée que par la première
    tech qui la revendique.
    """
    technologies: list[dict] = []
    previous_id: str | None = None
    unlocked_recipes: set[str] = set()

    # Groupement des steps payants consécutifs (taille tirée en chaîne).
    groups: list[dict] = []          # {kind, steps}
    cur_paid: list[dict] = []
    cur_objs = 0
    cur_target = 1
    cur_has_pole = False
    cur_has_gun = False

    def flush_paid() -> bool:
        """Ferme le groupe de steps payants courant : l'ajoute à ``groups``
        et réinitialise ses accumulateurs. Retourne False si aucun groupe
        (rien à vider)."""
        nonlocal cur_paid, cur_objs, cur_target, cur_has_pole, cur_has_gun
        if not cur_paid:
            return False
        groups.append({"kind": "paid", "steps": cur_paid})
        cur_paid = []
        cur_objs = 0
        cur_target = 1
        cur_has_pole = False
        cur_has_gun = False
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

        # Step payant, groupable.
        objs = _count_objects(step)
        is_science = _is_science_step(step)
        is_isolated = step.get("isolate") or False
        step_has_pole = _step_unlocks_pole(step, db)
        step_has_gun = _step_unlocks_handheld_gun(step, db)

        if not cur_paid:
            # Nouveau groupe : on tire sa taille (nb d'objets) en chaîne.
            cur_target = _roll_group_size(rng)

        flush_before = (
            is_science
            or is_isolated
            or (cur_has_pole and step_has_pole)
            or (cur_has_gun and step_has_gun)
            or (cur_objs + objs > _config_max_per_tech)
            or (cur_objs + objs > cur_target)
        )
        if flush_before and flush_paid():
            # Groupe vidé : ce step ouvre un NOUVEAU groupe, on tire sa taille.
            cur_target = _roll_group_size(rng)

        cur_paid.append(step)
        cur_objs += objs
        if step_has_pole:
            cur_has_pole = True
        if step_has_gun:
            cur_has_gun = True

        if is_science or is_isolated:
            # Isole le step science (le pack débloqué est consommé par les
            # steps suivants, §13) et les steps dispatch isolés (ammo de
            # véhicule §12.1, chaque dispatch garde sa propre tech).
            flush_paid()
    flush_paid()

    # Coût multi-packs de la tech endgame (packs les plus avancés).
    all_packs = _collect_packs(steps, limit=None)
    endgame_packs = all_packs[-_config_max_cost_packs:] if all_packs else []

    n_paid = sum(1 for g in groups if g["kind"] == "paid")
    paid_index = 0

    # Conversion des groupes en technologies.
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
                    "time": _config_research_time,
                    "ingredients": [
                        {"type": "item", "name": p, "amount": 1} for p in endgame_packs
                    ],
                }
            else:
                unit = {"count": 1, "time": 1, "ingredients": []}
        else:  # paid
            packs = _collect_packs(gsteps, limit=_config_max_cost_packs)
            if not packs:
                # Fallback : aucune source de coût (cas limite) -> gratuit.
                unit = {"count": 1, "time": 1, "ingredients": []}
            else:
                q = _per_pack_count(paid_index, max(n_paid, 1))
                unit = {
                    "count": q,
                    "time": _config_research_time,
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
