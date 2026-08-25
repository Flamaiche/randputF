"""Normalisation du dump JSON produit par le mod exporter vers VanillaDB.

Le dump est ecrit par Factorio au runtime (prototypes API 2.0) dans
script-output/randputF/vanilla_dump.json. Ce module transforme ce brut en
schema intermediaire stable utilisee par le generateur.
"""

from __future__ import annotations

import json
from pathlib import Path

from tool.common.db import BuildingDef, FluidDef, ItemDef, RecipeRef, VanillaDB


JUNK_PREFIXES = ("parameter-",)
JUNK_SUFFIXES = ("-unknown",)
JUNK_NAMES = {
    "no-item",
    "science",
    "electric-energy-interface",
    "heat-interface",
    "bottomless-chest",
    "proxy-container",
    "empty-module-slot",
    "lane-splitter",
    "one-way-valve",
    "overflow-valve",
    "top-up-valve",
    "linked-belt",
    "linked-chest",
    "infinity-pipe",
    "infinity-chest",
    "infinity-cargo-wagon",
    "simple-entity-with-force",
    "simple-entity-with-owner",
    "cut-paste-tool",
    "loader",
    "fast-loader",
    "express-loader",
    "coin",
    "copper-wire",
}


def is_junk(name: str) -> bool:
    return (
        name in JUNK_NAMES
        or any(name.startswith(p) for p in JUNK_PREFIXES)
        or any(name.endswith(s) for s in JUNK_SUFFIXES)
    )


def load_db_from_dump(dump: dict) -> VanillaDB:
    meta = dump.get("meta", {})
    db = VanillaDB(seed_value=int(meta.get("game_version_numeric", 0)))

    for name, entry in (dump.get("items") or {}).items():
        if is_junk(name):
            db.excluded_items[name] = entry
            continue
        itype = entry.get("type", "item")
        subgroup = _safe_group(entry)
        db.items[name] = ItemDef(
            name=name,
            subgroup=subgroup,
            place_result=entry.get("place_result"),
            fuel_value=_fuel_value(entry.get("fuel_value")),
            is_ammo=itype == "ammo",
            is_gun=itype == "gun",
            is_science_pack=subgroup == "science-pack",
            is_tool=itype == "tool",
            ammo_category=entry.get("ammo_category") or "",
        )

    for name, entry in (dump.get("fluids") or {}).items():
        if is_junk(name):
            db.excluded_fluids[name] = entry
            continue
        db.fluids[name] = FluidDef(
            name=name,
            fuel_value=_fuel_value(entry.get("fuel_value")),
            default_temperature=entry.get("default_temperature"),
        )

    for name, entry in (dump.get("entities") or {}).items():
        bdef = _parse_entity(name, entry)
        if bdef:
            db.buildings[name] = bdef

    for name, entry in (dump.get("recipes") or {}).items():
        db.recipes[name] = RecipeRef(
            name=name,
            category=entry.get("category") or "",
            ingredients=tuple(_parse_stack(i) for i in entry.get("ingredients", [])),
            products=tuple(_parse_stack(p) for p in entry.get("products", [])),
            energy=float(entry.get("energy", 0.5)),
        )
    return db


def _safe_group(entry: dict) -> str:
    group = entry.get("subgroup")
    if isinstance(group, dict):
        return group.get("name", "")
    return group or ""


def _fuel_value(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return float(raw.get("value", 0)) or None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_stack(stack: dict) -> tuple:
    return (stack.get("type", "item"), stack.get("name", ""), float(stack.get("amount", 0)))


def _parse_entity(name: str, e: dict) -> BuildingDef | None:
    """Classement fonctionnel PAR CAPACITES intrinseques, sans liste de types :
    - categories de craft / entrees de lab / pieces de fusee / temperature
      cible  -> transformateur ;
    - production electrique ou chaleur -> generateur ;
    - categories de ressources minables ou pompage -> extracteur.
    """
    directives: dict = {}

    craft_categories = tuple(e.get("crafting_categories") or ())
    resource_categories = tuple(e.get("resource_categories") or ())
    lab_inputs = e.get("lab_inputs") or []
    rocket_parts = e.get("rocket_parts_required")
    target_temp = e.get("target_temperature")
    max_power = float(e.get("max_power_output") or 0)
    energy_prod = float((e.get("energy_source") or {}).get("production") or 0)
    has_heat = bool(e.get("has_heat_output"))
    supply_area = e.get("supply_area_distance")
    pumping_speed = e.get("pumping_speed")
    pumped_fluid = e.get("pumped_fluid")

    fluidboxes = e.get("fluidboxes") or {}
    fluid_in = int(fluidboxes.get("input", 0) or 0)
    fluid_out = int(fluidboxes.get("output", 0) or 0)

    if lab_inputs:
        directives["lab_inputs"] = tuple(lab_inputs)
    if rocket_parts:
        directives["rocket_parts_required"] = int(rocket_parts)

    if craft_categories or lab_inputs or rocket_parts or target_temp is not None:
        functional = "transformer"
    elif max_power > 0 or energy_prod > 0 or has_heat:
        functional = "generator"
        directives["energy_output"] = True
    elif supply_area:
        # Poteaux electriques : distribution du reseau.
        functional = "distribution"
    elif resource_categories or pumping_speed is not None:
        functional = "extractor"
    else:
        # Aucune capacite reconnue : range en "other", jamais perdu.
        functional = "other"

    if pumped_fluid:
        medium = "water"
    elif "basic-fluid" in resource_categories or (
        functional == "extractor" and fluid_out > 0
    ):
        medium = "fluid"
    elif functional == "extractor":
        medium = "ground"
    else:
        medium = ""

    if fluid_in > 0 and functional != "generator":
        directives["fluid_inputs"] = True

    energy_src = e.get("energy_source") or {}
    energy_type = energy_src.get("type") or ""

    return BuildingDef(
        name=name,
        entity_type=e.get("type", ""),
        functional_type=functional,
        medium=medium,
        crafting_categories=craft_categories,
        energy_type=energy_type,
        fuel_categories=tuple(energy_src.get("fuel_categories") or ()),
        resource_categories=resource_categories,
        pumped_fluid=pumped_fluid,
        item_input_slots=int(e.get("ingredient_count") or 0),
        fluid_inputs=fluid_in,
        fluid_outputs=fluid_out,
        directives=directives,
    )


def summarize_db(db: VanillaDB) -> str:
    mediums = sorted({b.medium for b in db.buildings.values() if b.functional_type == "extractor" and b.medium})
    others = sum(1 for b in db.buildings.values() if b.functional_type == "other")
    lines = [
        f"Items: {len(db.items)} ({len(db.fuel_items())} combustibles) + {len(db.excluded_items)} exclus",
        f"Fluides: {len(db.fluids)} ({len(db.fuel_fluids())} combustibles) + {len(db.excluded_fluids)} exclus",
        f"Bâtiments classés: {len(db.buildings)}",
        f"  extracteurs: total={len(db.buildings_of_type('extractor'))} "
        + ", ".join(f"{m}={len(db.extractors_for_medium(m))}" for m in mediums),
        f"  transformateurs: {len(db.buildings_of_type('transformer'))}",
        f"  générateurs: {len(db.buildings_of_type('generator'))}",
        f"  distribution: {len(db.buildings_of_type('distribution'))}",
        f"  non classés (other): {others}",
        f"Recettes vanilla connues: {len(db.recipes)}",
    ]
    return "\n".join(lines)
