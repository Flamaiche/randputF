"""Normalisation du dump JSON produit par le mod exporter vers VanillaDB.

Le dump est ecrit par Factorio au runtime (prototypes API 2.0) dans
script-output/randputF/vanilla_dump.json. Ce module transforme ce brut en
schema intermediaire stable utilisee par le generateur.
"""

from __future__ import annotations

import json
from pathlib import Path

from tool.common.db import BuildingDef, FluidDef, ItemDef, RecipeRef, VanillaDB


def load_db_from_dump(dump: dict) -> VanillaDB:
    meta = dump.get("meta", {})
    db = VanillaDB(seed_value=int(meta.get("game_version_numeric", 0)))

    for name, entry in (dump.get("items") or {}).items():
        db.items[name] = ItemDef(
            name=name,
            subgroup=_safe_group(entry),
            place_result=entry.get("place_result"),
            fuel_value=_fuel_value(entry.get("fuel_value")),
            is_ammo=bool(entry.get("is_ammo")),
            is_gun=bool(entry.get("is_gun")),
            is_science_pack=bool(entry.get("is_science_pack")),
            is_tool=bool(entry.get("is_tool")),
        )

    for name, entry in (dump.get("fluids") or {}).items():
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
    transformer_types = {"assembling-machine", "furnace", "chemical-plant", "oil-refinery", "boiler"}
    generator_types = {"generator", "solar-panel", "reactor", "burner-generator"}

    functional = ""
    if etype in extractor_types:
        functional = "extractor"
    elif etype in transformer_types:
        functional = "transformer"
    elif etype in generator_types:
        functional = "generator"

    energy_src = e.get("energy_source") or {}
    energy_type = energy_src.get("type", "burner") if isinstance(energy_src, dict) else "burner"

    fluidboxes = e.get("fluidboxes") or {}
    fluid_in = int(fluidboxes.get("input", 0) or 0)
    fluid_out = int(fluidboxes.get("output", 0) or 0)

    if functional == "" and not (fluid_in or fluid_out):
        return None

    medium = "water" if etype == "offshore-pump" else "ground"
    directives = {}
    if functional == "generator":
        directives["energy_output"] = True
    if fluid_in > 0 and functional != "generator":
        directives["fluid_inputs"] = True

    return BuildingDef(
        name=name,
        entity_type=etype,
        functional_type=functional,
        medium=medium,
        crafting_categories=tuple(e.get("crafting_categories") or ()),
        energy_type=energy_type,
        fuel_categories=tuple(energy_src.get("fuel_categories") or ()) if isinstance(energy_src, dict) else (),
        resource_categories=tuple(e.get("resource_categories") or ()),
        pumped_fluid=e.get("pumped_fluid"),
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
