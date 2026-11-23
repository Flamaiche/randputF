"""Calcul mémoïsé partagé entre complexité et profil de difficulté."""

from __future__ import annotations

import math
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tool.audit.difficulty import (
    _primary_recipe,
    _produced_amount,
    _rocket_meta,
    _tech_sequence,
)

HAND = "main"
MAX_DEPTH = 64


def clean_number(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _name(value: Any) -> str | None:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("product") or "") or None
    return str(value) if value else None


def _crafting_speeds(db: Any = None) -> dict[str, float]:
    speeds: dict[str, float] = {}
    buildings = getattr(db, "buildings", None) if db is not None else None
    if buildings is None and isinstance(db, dict):
        buildings = db.get("buildings")
    for name, building in (buildings or {}).items():
        speed = getattr(building, "crafting_speed", None)
        if speed is None and isinstance(building, dict):
            speed = building.get("crafting_speed")
        try:
            value = float(speed) if speed else 0.0
        except (TypeError, ValueError):
            value = 0.0
        if value:
            speeds[name] = value
    return speeds


def _science_requirements(tech: dict) -> list[tuple[str, int]]:
    unit = tech.get("unit") or {}
    try:
        count = max(0, int(unit.get("count", 0) or 0))
    except (TypeError, ValueError):
        count = 0
    out: list[tuple[str, int]] = []
    for ingredient in unit.get("ingredients") or []:
        name = _name(ingredient)
        if not name:
            continue
        try:
            amount = max(0, int(ingredient.get("amount", 0) or 0))
        except (TypeError, ValueError):
            amount = 0
        out.append((name, count * amount))
    return out


def _science_demand(seed: dict) -> Counter[str]:
    demand: Counter[str] = Counter()
    for tech in seed.get("technologies") or []:
        for name, amount in _science_requirements(tech):
            demand[name] += amount
    rocket = _rocket_meta(seed)
    for value in rocket["launch_buildings"]:
        name = _name(value)
        if name:
            demand[name] += 1
    part = rocket["rocket_part_product"]
    if part:
        demand[part] += rocket["rocket_parts_required"]
    for value in rocket["launch_items"]:
        name = _name(value)
        if name:
            demand[name] += 1
    return demand


@dataclass
class Expansion:
    crafts: Counter[str] = field(default_factory=Counter)
    raw: Counter[str] = field(default_factory=Counter)
    buildings: Counter[str] = field(default_factory=Counter)
    hand_crafts: float = 0.0
    machine_seconds: float = 0.0
    unknown: set[str] = field(default_factory=set)

    def add(self, other: "Expansion") -> None:
        self.crafts.update(other.crafts)
        self.raw.update(other.raw)
        self.buildings.update(other.buildings)
        self.hand_crafts += other.hand_crafts
        self.machine_seconds += other.machine_seconds
        self.unknown |= other.unknown

    def scaled(self, factor: float) -> "Expansion":
        result = Expansion()
        if not factor:
            return result
        result.crafts.update({k: v * factor for k, v in self.crafts.items()})
        result.raw.update({k: v * factor for k, v in self.raw.items()})
        result.buildings.update({k: v * factor for k, v in self.buildings.items()})
        result.hand_crafts = self.hand_crafts * factor
        result.machine_seconds = self.machine_seconds * factor
        result.unknown = set(self.unknown)
        return result


@dataclass
class _Cost:
    expansion: Expansion = field(default_factory=Expansion)
    depth: int = 0
    items: frozenset[str] = frozenset()
    recipes: frozenset[str] = frozenset()
    buildings: frozenset[str] = frozenset()
    fluids: frozenset[str] = frozenset()
    raw_items: frozenset[str] = frozenset()


@dataclass
class GraphAnalysis:
    profile: dict[str, Any]
    tech_expansions: dict[str, Expansion]
    pack_totals: Counter[str]
    progression: list[str]
    unknown: list[str]
    recipes: list[dict]
    speeds: dict[str, float]
    terminal: set[str]
    by_product: dict[str, list[dict]]


def _format_steps(value: Any) -> str:
    return f"{clean_number(value):,}".replace(",", " ")


class _GraphProgress:
    def __init__(
        self,
        on_progress: Callable[[int, str], None] | None,
        low: int,
        high: int,
        detail: str,
        interval: float = 0.15,
    ) -> None:
        self.on_progress = on_progress
        self.low = low
        self.high = high
        self.detail = detail
        self.value = low
        self.steps = 0
        self.checked = 0
        self.interval = interval
        self.last = time.monotonic()
        self.position = ""

    def tick(self, item: str, amount: int, depth: int = 1) -> None:
        if self.on_progress is None:
            return
        self.steps += 1
        self.checked += 1
        self.position = (
            f"profondeur {depth}/{MAX_DEPTH} · {item} · {_format_steps(amount)} unités"
        )
        if self.checked < 64:
            return
        self.checked = 0
        now = time.monotonic()
        if now - self.last < self.interval:
            return
        self.last = now
        if self.value < self.high:
            self.value += 1
        self.on_progress(self.value, self.label())

    def label(self) -> str:
        label = f"{self.detail} · {_format_steps(self.steps)} étapes"
        if self.position:
            label += f" · {self.position}"
        return label

    def done(self) -> None:
        if self.on_progress is not None:
            self.on_progress(self.high, self.label())


def _axes(
    totals: Counter[str],
    critical_seconds: float,
    depth: int,
    seen_items: set[str],
    seen_recipes: set[str],
    seen_buildings: set[str],
    seen_fluids: set[str],
    novelty: Counter[str],
) -> dict[str, Any]:
    raw_axes = {
        "structure": {
            "recipes": len(seen_recipes),
            "items": len(seen_items),
            "links": int(totals["links"]),
            "raw_inputs": int(totals["_raw_items"]),
            "depth": depth,
            "buildings": len(seen_buildings),
        },
        "volume": {
            "crafts": round(totals["crafts"], 2),
            "raw_units": round(totals["raw_units"], 2),
            "machine_seconds": round(totals["machine_seconds"], 2),
        },
        "critical": {
            "depth": depth,
            "critical_seconds": round(critical_seconds, 2),
        },
        "novelty": {
            "new_items": novelty["new_items"],
            "new_recipes": novelty["new_recipes"],
            "new_buildings": novelty["new_buildings"],
            "new_fluids": novelty["new_fluids"],
        },
        "infrastructure": {
            "buildings": len(seen_buildings),
            "fluids": len(seen_fluids),
            "wide_recipes": int(totals["wide_recipes"]),
        },
    }
    return {"axes": raw_axes, "raw_axes": raw_axes}


def analyze_graph(
    seed: dict,
    db: Any = None,
    on_progress: Callable[[int, str], None] | None = None,
) -> GraphAnalysis:
    recipes = [r for r in seed.get("recipes") or [] if isinstance(r, dict)]
    by_product: dict[str, list[dict]] = defaultdict(list)
    for recipe in recipes:
        for result in recipe.get("results") or []:
            name = _name(result)
            if name:
                by_product[name].append(recipe)

    rocket = _rocket_meta(seed)
    reserved: dict[str, dict] = {}
    if rocket["rocket_part_product"] and rocket["rocket_recipe_data"]:
        reserved[rocket["rocket_part_product"]] = rocket["rocket_recipe_data"]

    terminal = set((seed.get("pools") or {}).get("raw_resources") or ())
    terminal.update(
        item.get("name")
        for item in seed.get("starter_kit") or []
        if isinstance(item, dict) and item.get("name")
    )
    fluids = {
        name
        for name, data in (seed.get("fluids") or {}).items()
        if isinstance(data, dict)
    }
    fluids.update(
        item.get("name")
        for item in seed.get("items") or []
        if isinstance(item, dict) and item.get("name")
    )

    speeds = _crafting_speeds(db)
    memo: dict[str, _Cost] = {}
    visiting: set[str] = set()
    unknown: set[str] = set()

    def cost(item: str) -> _Cost:
        if item in terminal:
            return _Cost(
                expansion=Expansion(raw=Counter({item: 1})),
                items=frozenset({item}),
                raw_items=frozenset({item}),
            )
        if item in memo:
            return memo[item]
        if item in visiting:
            return _Cost(
                expansion=Expansion(raw=Counter({item: 1})),
                items=frozenset({item}),
                raw_items=frozenset({item}),
            )
        recipe = _primary_recipe(by_product, item, reserved)
        if recipe is None:
            unknown.add(item)
            return _Cost(
                expansion=Expansion(raw=Counter({item: 1}), unknown={item}),
                items=frozenset({item}),
                raw_items=frozenset({item}),
            )

        name = str(recipe.get("name") or item)
        produced = max(1.0, _produced_amount(recipe, item))
        crafted_in = str(recipe.get("crafted_in") or "")
        try:
            energy = max(0.0, float(recipe.get("energy", 0) or 0))
        except (TypeError, ValueError):
            energy = 0.0
        speed = speeds.get(crafted_in, 1.0) or 1.0 if crafted_in else 1.0
        expansion = Expansion()
        expansion.crafts[name] += 1 / produced
        if crafted_in:
            expansion.buildings[crafted_in] += 1 / produced
        else:
            expansion.hand_crafts += 1 / produced
        expansion.machine_seconds += energy / (produced * speed)

        result = _Cost(
            expansion=expansion,
            depth=1,
            items=frozenset({item}),
            recipes=frozenset({name}),
            buildings=frozenset({crafted_in}) if crafted_in else frozenset(),
            fluids=frozenset({crafted_in}) if crafted_in in fluids else frozenset(),
        )
        visiting.add(item)
        for ingredient in recipe.get("ingredients") or []:
            child_name = _name(ingredient)
            if not child_name:
                continue
            try:
                quantity = max(0.0, float(ingredient.get("amount", 1) or 1))
            except (TypeError, ValueError):
                quantity = 1.0
            child = cost(child_name)
            result.expansion.add(child.expansion.scaled(quantity / produced))
            result.depth = max(result.depth, 1 + child.depth)
            result.items |= child.items
            result.recipes |= child.recipes
            result.buildings |= child.buildings
            result.fluids |= child.fluids
            result.raw_items |= child.raw_items
        visiting.discard(item)
        memo[item] = result
        return result

    def expansion_for(item: str, amount: float) -> Expansion:
        if amount <= 0:
            return Expansion()
        recipe = _primary_recipe(by_product, item, reserved)
        if item in terminal or recipe is None:
            return cost(item).expansion.scaled(amount)
        produced = max(1.0, _produced_amount(recipe, item))
        crafts = math.ceil(amount / produced)
        return cost(item).expansion.scaled(crafts * produced)

    tech_by_id, progression = _tech_sequence(seed)
    tech_expansions: dict[str, Expansion] = {}
    pack_totals: Counter[str] = Counter()
    if on_progress is not None:
        on_progress(0, "dépliage des recettes")
    total_techs = max(1, len(progression))
    for position, tech_id in enumerate(progression, start=1):
        step = _GraphProgress(
            on_progress,
            (position - 1) * 100 // total_techs,
            position * 100 // total_techs,
            f"dépliage des recettes · {position}/{total_techs} techs",
        )
        tech = tech_by_id.get(tech_id)
        if not tech:
            step.done()
            continue
        tech_exp = Expansion()
        for name, amount in _science_requirements(tech):
            pack_totals[name] += amount
            if amount <= 0:
                continue
            step.tick(name, amount)
            tech_exp.add(expansion_for(name, amount))
        tech_expansions[tech_id] = tech_exp
        step.done()

    totals: Counter[str] = Counter()
    critical_seconds = 0.0
    depth = 0
    seen_items: set[str] = set()
    seen_recipes: set[str] = set()
    seen_buildings: set[str] = set()
    seen_fluids: set[str] = set()
    novelty: Counter[str] = Counter()
    nodes: dict[str, _Cost] = {}
    for item, amount in _science_demand(seed).items():
        current = cost(item)
        nodes[item] = current
        scaled = current.expansion.scaled(amount)
        totals["crafts"] += sum(scaled.crafts.values())
        totals["raw_units"] += sum(scaled.raw.values())
        totals["machine_seconds"] += scaled.machine_seconds
        critical_seconds = max(critical_seconds, scaled.machine_seconds)
        depth = max(depth, current.depth)
        novelty["new_items"] += len(current.items - seen_items)
        novelty["new_recipes"] += len(current.recipes - seen_recipes)
        novelty["new_buildings"] += len(current.buildings - seen_buildings)
        novelty["new_fluids"] += len(current.fluids - seen_fluids)
        seen_items |= current.items
        seen_recipes |= current.recipes
        seen_buildings |= current.buildings
        seen_fluids |= current.fluids

    all_items: set[str] = set()
    all_recipes: set[str] = set()
    all_buildings: set[str] = set()
    all_fluids: set[str] = set()
    raw_items: set[str] = set()
    for current in nodes.values():
        all_items |= current.items
        all_recipes |= current.recipes
        all_buildings |= current.buildings
        all_fluids |= current.fluids
        raw_items |= current.raw_items

    links = 0
    wide_recipes = 0
    for name in all_recipes:
        recipe = next((r for r in recipes if str(r.get("name") or "") == name), None)
        if recipe is None:
            continue
        count = sum(1 for ingredient in recipe.get("ingredients") or [] if _name(ingredient))
        links += count
        if links and count >= 4:
            wide_recipes += 1
    totals["links"] = links
    totals["wide_recipes"] = wide_recipes
    totals["_raw_items"] = len(raw_items)

    profile = _axes(
        totals,
        critical_seconds,
        depth,
        all_items,
        all_recipes,
        all_buildings,
        all_fluids,
        novelty,
    )
    profile["unknown"] = sorted(unknown)
    if on_progress is not None:
        on_progress(100, "complexité calculée")

    return GraphAnalysis(
        profile=profile,
        tech_expansions=tech_expansions,
        pack_totals=pack_totals,
        progression=progression,
        unknown=sorted(unknown),
        recipes=recipes,
        speeds=speeds,
        terminal=terminal,
        by_product=dict(by_product),
    )
