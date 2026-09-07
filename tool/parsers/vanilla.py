"""Normalisation du dump JSON produit par le mod exporter vers VanillaDB.

Le dump est ecrit par Factorio au runtime (prototypes API 2.0) dans
script-output/randputF/vanilla_dump.json. Ce module transforme ce brut en
schema intermediaire stable utilisee par le generateur.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tool.common.db import BuildingDef, FluidDef, ItemDef, RecipeRef, VanillaDB, has_hidden_recipe


JUNK_PREFIXES = ("parameter-",)
JUNK_SUFFIXES = ("-unknown",)
JUNK_NAMES = {
    "no-item",
    "science",
    "electric-energy-interface",
    "hidden-electric-energy-interface",
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
            is_armor=itype == "armor",
            is_science_pack=subgroup == "science-pack",
            is_tool=itype == "tool",
            ammo_category=entry.get("ammo_category") or "",
            item_type=itype,
            fuel_category=entry.get("fuel_category") or "",
            burnt_result=entry.get("burnt_result"),
            stack_size=int(entry.get("stack_size") or 0),
        )

    for name, entry in (dump.get("fluids") or {}).items():
        if is_junk(name):
            db.excluded_fluids[name] = entry
            continue
        db.fluids[name] = FluidDef(
            name=name,
            fuel_value=_fuel_value(entry.get("fuel_value")),
        )

    for name, entry in (dump.get("entities") or {}).items():
        # Les entités cheat/junk (electric-energy-interface, bottomless-chest,
        # linked-belt...) n'ont aucun intérêt : un bâtiment classé "other" ou
        # générateur sans effet finirait par remplir l'arbre tech de fillers.
        if is_junk(name):
            db.excluded_items[name] = entry
            continue
        bdef = tag_parse_entity(name, entry)
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

    # POST-PARSE (§6/§10, IDEES C7) : le tag « recette cachée » dépend des
    # RÉSIDUS de combustible (``burnt_result`` des items du bâtiment) — une
    # information de la base items, indisponible à la volée pendant le parse.
    # On stampe donc sur chaque bâtiment ses résidus PUIS le tag
    # ``has_hidden_recipe``. Le réacteur (item quelconque → item résidu)
    # devient ainsi une recette cachée item → item, sans aucune liste de noms.
    for b in db.buildings.values():
        b.fuel_residues = db.fuel_residues(b)
        b.has_hidden_recipe = has_hidden_recipe(b)
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


def equivalent_functional_type(b: BuildingDef) -> str:
    """RECONSTRUIT l'ancien type fonctionnel exclusif (research/transformer/
    generator/distribution/extractor/other) à partir des TAGS cumulables, dans
    le MÊME ordre de priorité que l'ancien ``_parse_entity``. Outil de
    VÉRIFICATION : la logique du générateur ne repose plus que sur les tags,
    mais ce « rôle gagnant » sert encore aux décisions d'héritage intrinsèques
    au DUMP (medium, directives fluid_inputs)."""
    if b.is_research:
        return "research"
    if b.is_crafter:
        return "transformer"
    if b.is_generator:
        return "generator"
    if b.is_distribution:
        return "distribution"
    if b.is_extractor:
        return "extractor"
    return "other"


def tag_parse_entity(name: str, e: dict) -> BuildingDef | None:
    """Tagging PAR CAPACITES intrinseques, sans liste de types : chaque
    bâtiment reçoit des TAGS ORTHOGONAUX CUMULABLES (il peut être à la fois
    atelier et générateur) :
    - consommation de science packs (lab_inputs) -> ``is_research`` :
      premier-plan, le lab est une brique de base, pas un atelier de craft ;
    - categories de craft / pieces de fusee / temperature cible -> ``is_crafter`` ;
    - production electrique ou chaleur -> ``is_generator`` ;
    - perimetre de supply (pylônes) -> ``is_distribution`` ;
    - categories de ressources minables ou pompage -> ``is_extractor`` ;
    - sinon -> ``is_other`` (backup, jamais perdu).

    ``equivalent_functional_type`` reproduit l'ancien classement EXCLUSIF ; on
    le réutilise ici pour les décisions d'héritage du dump (medium,
    directives) — strictement identiques à l'ancien comportement.
    """
    directives: dict = {}

    energy_src = e.get("energy_source") or {}
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

    if rocket_parts:
        directives["rocket_parts_required"] = int(rocket_parts)

    if lab_inputs:
        # Le lab consomme des science packs : bâtiment de RECHERCHE, pas un
        # atelier de craft (anti-cycle §8) ni un générateur.
        directives["lab_inputs"] = tuple(lab_inputs)
        is_research = True
    else:
        is_research = False

    if craft_categories or rocket_parts or target_temp is not None:
        # Le personnage lui-meme tombe ici (categories de craft) :
        # c'est la fabrication a la main, le premier fabricant gratuit.
        is_crafter = True
    else:
        is_crafter = False

    # Un accumulateur affiche un max_power_output (decharge) mais ne PRODUIT
    # pas d'energie : il n'a rien a faire parmi les generateurs (electricite
    # §10 le prendrait pour source de courant -> faux depart). Le réacteur
    # (has_heat_output, pas de max_power) produit de la CHALEUR.
    is_generator = (
        e.get("type") != "accumulator"
        and (max_power > 0 or energy_prod > 0 or (has_heat and bool(energy_src.get("type"))))
    )
    # Poteaux electriques : distribution du reseau.
    is_distribution = bool(supply_area)
    # Un extracteur CREE sa ressource depuis le monde : fluides sortants sans
    # entree (offshore-pump, pumpjack) ou categories de minage.
    is_extractor = bool(
        resource_categories
        or pumped_fluid
        or (pumping_speed is not None and fluid_in == 0 and fluid_out > 0)
    )
    # Aucune capacite reconnue : range en "other", jamais perdu.
    is_other = not (is_research or is_crafter or is_generator or is_distribution or is_extractor)

    # « Rôle gagnant » (ex-classement exclusif) — sert aux décisions d'héritage
    # du dump (medium, directives) : strictement identique à l'ancien code.
    functional = equivalent_functional_type(
        SimpleNamespace(
            is_research=is_research,
            is_crafter=is_crafter,
            is_generator=is_generator,
            is_distribution=is_distribution,
            is_extractor=is_extractor,
        )
    )

    # Électricité vs chaleur (TAGS orthogonaux) : un VRAI producteur de courant
    # (steam-engine, turbine, burner-generator, solar-panel) produit de
    # l'électricité ; un réacteur produit de la CHALEUR. L'accumulateur
    # affiche une puissance de décharge mais ne PRODUIT pas de courant.
    produces_electricity = (
        e.get("type") != "accumulator"
        and (max_power > 0 or energy_prod > 0)
    )

    if pumped_fluid:
        medium = "water"
    elif "basic-fluid" in resource_categories:
        medium = "fluid"
    elif functional == "extractor" and fluid_out > 0 and not resource_categories:
        # Sortie de fluide sans categorie de minage = source d'eau (offshore-pump).
        medium = "water"
    elif functional == "extractor":
        medium = "ground"
    else:
        medium = ""

    if fluid_in > 0 and functional != "generator":
        directives["fluid_inputs"] = True

    energy_type = energy_src.get("type") or ""

    return BuildingDef(
        name=name,
        entity_type=e.get("type", ""),
        medium=medium,
        is_research=is_research,
        is_crafter=is_crafter,
        is_generator=is_generator,
        is_distribution=is_distribution,
        is_extractor=is_extractor,
        is_other=is_other,
        has_crafting=bool(craft_categories),
        has_mining=bool(resource_categories),
        has_pumping=bool(pumped_fluid) or (pumping_speed is not None and fluid_in == 0 and fluid_out > 0),
        has_fluid_input=fluid_in > 0,
        has_fluid_output=fluid_out > 0,
        has_fuel=energy_type == "burner",
        has_target_temperature=target_temp is not None,
        has_rocket_parts=bool(rocket_parts),
        crafting_categories=craft_categories,
        resource_categories=resource_categories,
        energy_type=energy_type,
        fuel_categories=tuple(energy_src.get("fuel_categories") or ()),
        pumped_fluid=pumped_fluid,
        item_input_slots=int(e.get("ingredient_count") or 0),
        fluid_inputs=fluid_in,
        fluid_outputs=fluid_out,
        produces_heat=has_heat,
        produces_electricity=produces_electricity,
        directives=directives,
    )


def summarize_db(db: VanillaDB) -> str:
    mediums = sorted({b.medium for b in db.buildings.values() if b.is_extractor and b.medium})
    others = sum(1 for b in db.buildings.values() if b.is_other)
    lines = [
        f"Items: {len(db.items)} ({len(db.fuel_items())} combustibles) + {len(db.excluded_items)} exclus",
        f"Fluides: {len(db.fluids)} ({len(db.fuel_fluids())} combustibles) + {len(db.excluded_fluids)} exclus",
        f"Bâtiments classés: {len(db.buildings)}",
        f"  extracteurs (is_extractor): total={len(db.buildings_with_tag('is_extractor'))} "
        + ", ".join(f"{m}={len(db.extractors_for_medium(m))}" for m in mediums),
        f"  ateliers (is_crafter): {len(db.buildings_with_tag('is_crafter'))}",
        f"  recherche (is_research): {len(db.buildings_with_tag('is_research'))}",
        f"  générateurs (is_generator): {len(db.buildings_with_tag('is_generator'))}",
        f"  distribution (is_distribution): {len(db.buildings_with_tag('is_distribution'))}",
        f"  non classés (is_other): {others}",
        f"Recettes vanilla connues: {len(db.recipes)}",
    ]
    return "\n".join(lines)
