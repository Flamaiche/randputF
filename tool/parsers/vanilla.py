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
    etype = e.get("type", "")
    extractor_types = {"mining-drill", "offshore-pump"}
    transformer_types = {
        "assembling-machine",
        "furnace",
        "chemical-plant",
        "oil-refinery",
        "boiler",
        "lab",
        "rocket-silo",
    }
    generator_types = {"generator", "solar-panel", "reactor", "burner-generator"}

    functional = ""
    if etype in extractor_types:
        functional = "extractor"
    elif etype in transformer_types:
        functional = "transformer"
    elif etype in generator_types:
        functional = "generator"

    energy_src = e.get("energy_source") or {}
    known_burners = {"furnace", "boiler", "burner-generator"}
    energy_type = (
        energy_src.get("type")
        if isinstance(energy_src, dict) and energy_src.get("type")
        else ("burner" if etype in known_burners else "electric")
    )

    fluidboxes = e.get("fluidboxes") or {}
    fluid_in = int(fluidboxes.get("input", 0) or 0)
    fluid_out = int(fluidboxes.get("output", 0) or 0)

    if functional == "" and not (fluid_in or fluid_out):
        return None

    resource_categories = tuple(e.get("resource_categories") or ())
    if etype == "offshore-pump":
        medium = "water"
    elif fluid_out > 0 or "basic-fluid" in resource_categories:
        # Extracteur de fluides profonds (pumpjack).
        medium = "fluid"
    else:
        medium = "ground"

    directives = {}
    if functional == "generator":
        directives["energy_output"] = True
    if fluid_in > 0 and functional != "generator":
        directives["fluid_inputs"] = True
    lab_inputs = e.get("lab_inputs") or []
    if lab_inputs:
        directives["lab_inputs"] = tuple(lab_inputs)
    if e.get("rocket_parts_required"):
        directives["rocket_parts_required"] = int(e["rocket_parts_required"])

    return BuildingDef(
        name=name,
        entity_type=etype,
        functional_type=functional,
        medium=medium,
        crafting_categories=tuple(e.get("crafting_categories") or ()),
        energy_type=energy_type,
        fuel_categories=tuple(energy_src.get("fuel_categories") or ()) if isinstance(energy_src, dict) else (),
        resource_categories=resource_categories,
        pumped_fluid=e.get("pumped_fluid"),
        item_input_slots=int(e.get("ingredient_count") or 0),
        fluid_inputs=fluid_in,
        fluid_outputs=fluid_out,
        directives=directives,
    )


def summarize_db(db: VanillaDB) -> str:
    mediums = sorted({b.medium for b in db.buildings.values() if b.functional_type == "extractor" and b.medium})
    lines = [
        f"Items: {len(db.items)} ({len(db.fuel_items())} combustibles)",
        f"Fluides: {len(db.fluids)} ({len(db.fuel_fluids())} combustibles)",
        f"Bâtiments classés: {len(db.buildings)}",
        f"  extracteurs: total={len(db.buildings_of_type('extractor'))} "
        + ", ".join(f"{m}={len(db.extractors_for_medium(m))}" for m in mediums),
        f"  transformateurs: {len(db.buildings_of_type('transformer'))}",
        f"  générateurs: {len(db.buildings_of_type('generator'))}",
        f"Recettes vanilla connues: {len(db.recipes)}",
    ]
    return "\n".join(lines)
