"""Base vanilla synthetique pour developper et tester la pipeline sans le jeu."""

from __future__ import annotations

from tool.common.db import BuildingDef, FluidDef, ItemDef, RecipeRef, VanillaDB


def build_demo_db() -> VanillaDB:
    db = VanillaDB(seed_value=0)

    raw_items = {
        "iron-ore": ("raw-resource", None),
        "copper-ore": ("raw-resource", None),
        "stone": ("raw-resource", None),
        "coal": ("raw-resource", 4.0),
    }
    for name, (subgroup, fuel) in raw_items.items():
        db.items[name] = ItemDef(name=name, subgroup=subgroup, fuel_value=fuel)

    intermediate = [
        "iron-plate",
        "copper-plate",
        "steel-plate",
        "stone-brick",
        "iron-gear-wheel",
        "copper-cable",
        "electronic-circuit",
        "pipe",
        "pipe-to-ground",
        "transport-belt",
        "splitter",
        "underground-belt",
        "burner-inserter",
    ]
    for name in intermediate:
        db.items[name] = ItemDef(name=name, subgroup="intermediate")

    for name, place, fuel in [
        ("burner-mining-drill", "burner-mining-drill", None),
        ("electric-mining-drill", "electric-mining-drill", None),
        ("offshore-pump", "offshore-pump", None),
        ("stone-furnace", "stone-furnace", None),
        ("assembling-machine-1", "assembling-machine-1", None),
        ("assembling-machine-2", "assembling-machine-2", None),
        ("boiler", "boiler", None),
        ("steam-engine", "steam-engine", None),
        ("pipe-item", "pipe", None),
        ("belt-item", "transport-belt", None),
        ("inserter-item", "burner-inserter", None),
        ("lab", "lab", None),
        ("rocket-silo", "rocket-silo", None),
    ]:
        db.items[name] = ItemDef(name=name, subgroup="logistics", place_result=place)

    for gun in ["pistol"]:
        db.items[gun] = ItemDef(name=gun, subgroup="combat", is_gun=True, ammo_category="bullet")
    for ammo in ["firearm-magazine"]:
        db.items[ammo] = ItemDef(name=ammo, subgroup="combat", is_ammo=True, ammo_category="bullet")
    for pack in ["automation-science-pack"]:
        db.items[pack] = ItemDef(name=pack, subgroup="science", is_science_pack=True)

    db.fluids["water"] = FluidDef(name="water")
    db.fluids["crude-oil"] = FluidDef(name="crude-oil")
    db.fluids["steam-demo"] = FluidDef(name="steam-demo")
    db.fluids["lubricant"] = FluidDef(name="lubricant")

    def building(name, ftype, **kw):
        db.buildings[name] = BuildingDef(name=name, entity_type=kw.pop("etype", name), functional_type=ftype, **kw)

    building("burner-mining-drill", "extractor", medium="ground", energy_type="burner",
             resource_categories=("basic-solid",), item_input_slots=1)
    building("electric-mining-drill", "extractor", medium="ground", energy_type="electric",
             resource_categories=("basic-solid",))
    building("offshore-pump", "extractor", medium="water", energy_type="void", pumped_fluid="water")
    building("pumpjack", "extractor", etype="pumpjack", medium="ground", energy_type="electric",
             fluid_outputs=1)
    building("stone-furnace", "transformer", crafting_categories=("smelting",),
             energy_type="burner", fuel_categories=("chemical",))
    building("assembling-machine-1", "transformer", crafting_categories=("crafting",),
             energy_type="electric", item_input_slots=2)
    building("assembling-machine-2", "transformer", crafting_categories=("crafting", "advanced-crafting"),
             energy_type="electric", item_input_slots=2, fluid_inputs=1,
             directives={"fluid_inputs": True})
    building("boiler", "transformer", crafting_categories=("boiler",), etype="boiler",
             energy_type="burner", fuel_categories=("chemical",), fluid_inputs=1, fluid_outputs=1)
    building("steam-engine", "generator", etype="steam-engine", energy_type="electric",
             fluid_inputs=1, directives={"energy_output": True})

    def recipe(name, ingredients, products, category=""):
        db.recipes[name] = RecipeRef(
            name=name,
            category=category,
            ingredients=tuple(ingredients),
            products=tuple(products),
        )

    recipe("demo-smelt-iron", [("item", "iron-ore", 1)], [("item", "iron-plate", 1)], "smelting")
    recipe("demo-gear", [("item", "iron-plate", 2)], [("item", "iron-gear-wheel", 1)])
    recipe("demo-pipe", [("item", "iron-plate", 1)], [("item", "pipe-item", 1)])
    return db
