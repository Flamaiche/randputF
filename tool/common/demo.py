"""Base vanilla synthetique pour developper et tester la pipeline sans le jeu."""

from __future__ import annotations

from tool.common.db import (
    ENVIRONMENTAL_ITEMS,
    BuildingDef,
    FluidDef,
    ItemDef,
    RecipeRef,
    VanillaDB,
)


def build_demo_db() -> VanillaDB:
    """Base vanilla SYNTHÉTIQUE pour développer et tester la pipeline sans le
    jeu : quelques items bruts/intermédiaires, fluides, bâtiments taggés et
    recettes de démo suffisants à un run complet."""
    db = VanillaDB(seed_value=0)

    raw_items = {
        "iron-ore": ("raw-resource", None),
        "copper-ore": ("raw-resource", None),
        "stone": ("raw-resource", None),
        "coal": ("raw-resource", 4.0),
        "wood": ("raw-resource", 2.0),
        "raw-fish": ("raw-resource", None),
    }
    for name, (subgroup, fuel) in raw_items.items():
        # wood/stone/raw-fish sont récoltés à la main : mêmes tags
        # ``is_environmental`` que le parser réel (vanilla.py).
        db.items[name] = ItemDef(
            name=name,
            subgroup=subgroup,
            fuel_value=fuel,
            is_environmental=(name in ENVIRONMENTAL_ITEMS),
        )

    intermediate = [
        "iron-plate",
        "copper-plate",
        "steel-plate",
        "stone-brick",
        "iron-gear-wheel",
        "copper-cable",
        "electronic-circuit",
    ]
    for name in intermediate:
        db.items[name] = ItemDef(name=name, subgroup="intermediate")

    for name, place in [
        ("pipe", "pipe"),
        ("pipe-to-ground", "pipe-to-ground"),
        ("transport-belt", "transport-belt"),
        ("splitter", "splitter"),
        ("underground-belt", "underground-belt"),
        ("burner-inserter", "inserter"),
    ]:
        # Fidèle au vanilla : chaque item de transport pose SON bâtiment
        # (place_result) — la sélection passe par le tag du bâtiment
        # (is_belt, is_pipe…), pas par un motif de nom.
        db.items[name] = ItemDef(name=name, subgroup="intermediate", place_result=place)

    for name, place, fuel in [
        ("burner-mining-drill", "burner-mining-drill", None),
        ("electric-mining-drill", "electric-mining-drill", None),
        ("offshore-pump", "offshore-pump", None),
        ("pumpjack", "pumpjack", None),
        ("stone-furnace", "stone-furnace", None),
        ("assembling-machine-1", "assembling-machine-1", None),
        ("assembling-machine-2", "assembling-machine-2", None),
        ("boiler", "boiler", None),
        ("steam-engine", "steam-engine", None),
        ("burner-generator", "burner-generator", None),
        ("pipe-item", "pipe", None),
        ("belt-item", "transport-belt", None),
        ("inserter-item", "inserter", None),
        ("wooden-chest", "wooden-chest", None),
        ("lab", "lab", None),
        ("rocket-silo", "rocket-silo", None),
    ]:
        db.items[name] = ItemDef(name=name, subgroup="logistics", place_result=place)

    for gun in ["pistol"]:
        db.items[gun] = ItemDef(name=gun, subgroup="combat", is_gun=True,
                                ammo_category="bullet", item_type="gun", stack_size=1)
    for ammo in ["firearm-magazine"]:
        db.items[ammo] = ItemDef(name=ammo, subgroup="combat", is_ammo=True, ammo_category="bullet")
    for pack in ["automation-science-pack"]:
        # Un science pack EST un objet de type ``tool`` (raffinage is_tool →
        # is_science_pack, cf. vanilla) ; sa filière reste gérée par le flux
        # recherche, pas par le craft des items.
        db.items[pack] = ItemDef(name=pack, subgroup="science", is_tool=True,
                                 is_science_pack=True)

    db.items["landfill"] = ItemDef(name="landfill", subgroup="terrain", stack_size=100)

    db.fluids["water"] = FluidDef(name="water")
    db.fluids["crude-oil"] = FluidDef(name="crude-oil")
    db.fluids["steam-demo"] = FluidDef(name="steam-demo")
    db.fluids["lubricant"] = FluidDef(name="lubricant")

    def building(name, ftype, **kw):
        """Ajoute un bâtiment de démo ``ftype`` (extractor/transformer/
        generator/research/distribution/rocket_silo/other) avec ses tags."""
        etype = kw.pop("etype", name)
        tags = {
            "extractor": {"is_extractor": True},
            "transformer": {"is_crafter": True},
            "generator": {"is_generator": True},
            "research": {"is_research": True},
            "distribution": {"is_distribution": True},
            "rocket_silo": {"is_crafter": True},
            "other": {"is_other": True},
        }
        db.buildings[name] = BuildingDef(
            name=name, entity_type=etype, **tags[ftype], **kw
        )

    building("burner-mining-drill", "extractor", medium="ground", energy_type="burner",
             resource_categories=("basic-solid",), item_input_slots=1)
    building("electric-mining-drill", "extractor", medium="ground", energy_type="electric",
             resource_categories=("basic-solid",))
    building("offshore-pump", "extractor", medium="water", energy_type="void",
             pumped_fluid="water", fluid_outputs=1)
    building("pumpjack", "extractor", etype="pumpjack", medium="ground", energy_type="electric",
             resource_categories=("basic-fluid",), fluid_outputs=1)
    building("stone-furnace", "transformer", crafting_categories=("smelting",),
             energy_type="burner", fuel_categories=("chemical",))
    building("assembling-machine-1", "transformer", crafting_categories=("crafting",),
             energy_type="electric", item_input_slots=2)
    building("assembling-machine-2", "transformer", crafting_categories=("crafting", "advanced-crafting", "crafting-with-fluid"),
             energy_type="electric", item_input_slots=2, fluid_inputs=1, fluid_outputs=1,
             directives={"fluid_inputs": True})
    building("boiler", "transformer", crafting_categories=("boiler",), etype="boiler",
             energy_type="burner", fuel_categories=("chemical",), fluid_inputs=1, fluid_outputs=1)
    building("steam-engine", "generator", etype="steam-engine", energy_type="electric",
             fluid_inputs=1, produces_electricity=True)
    building("burner-generator", "generator", etype="burner-generator", energy_type="burner",
             fuel_categories=("chemical",), produces_electricity=True)
    building("lab", "research", energy_type="electric", item_input_slots=1,
             directives={"lab_inputs": ("automation-science-pack",)})
    # rocket-silo : sans le building vanilla, la phase endgame ne licencierait
    # pas la recette randputf-rocket-silo et la complétude échouerait.
    building("rocket-silo", "rocket_silo", etype="rocket-silo", energy_type="electric",
             crafting_categories=("rocket-building",))

    for name, etype, tag in [
        ("transport-belt", "transport-belt", "is_belt"),
        ("splitter", "splitter", "is_splitter"),
        ("underground-belt", "underground-belt", "is_underground_belt"),
        ("pipe", "pipe", "is_pipe"),
        ("pipe-to-ground", "pipe-to-ground", "is_pipe_to_ground"),
        ("inserter", "inserter", "is_inserter"),
    ]:
        db.buildings[name] = BuildingDef(
            name=name, entity_type=etype, is_other=True, **{tag: True}
        )

    # Conteneur d'items (chest) : fidèle au vanilla (entity_type `container`,
    # tag is_chest) — le kit de départ peut rouler un objet de stockage.
    db.buildings["wooden-chest"] = BuildingDef(
        name="wooden-chest", entity_type="container", is_chest=True, is_other=True
    )

    def recipe(name, ingredients, products, category=""):
        """Ajoute une recette de démo (ingrédients/produits en listes de
        tuples (type, nom, montant))."""
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
