"""Base de donnees normalisee du contenu vanilla.

Schema intermediaire entre le dump brut du jeu et le moteur de tirage.
Chaque bâtiment y est decrit par type fonctionnel, slots in/out types
et directives (possibilites), conformement au README §5.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SLOT_ITEM = "item"
SLOT_FLUID = "fluid"
SLOT_FUEL = "fuel"
SLOT_ENERGY = "energy"


@dataclass(frozen=True)
class ItemDef:
    name: str
    subgroup: str = ""
    place_result: str | None = None
    fuel_value: float | None = None
    is_ammo: bool = False
    is_gun: bool = False
    is_science_pack: bool = False
    is_tool: bool = False
    ammo_category: str = ""


@dataclass(frozen=True)
class FluidDef:
    name: str
    fuel_value: float | None = None
    default_temperature: float | None = None


@dataclass
class BuildingDef:
    name: str
    entity_type: str
    functional_type: str
    medium: str = ""
    crafting_categories: tuple[str, ...] = ()
    energy_type: str = "burner"
    fuel_categories: tuple[str, ...] = ()
    item_input_slots: int = 0
    fluid_inputs: int = 0
    fluid_outputs: int = 0
    resource_categories: tuple[str, ...] = ()
    pumped_fluid: str | None = None
    directives: dict = field(default_factory=dict)


@dataclass
class RecipeRef:
    name: str
    category: str = ""
    ingredients: tuple = ()
    products: tuple = ()
    energy: float = 0.5


@dataclass
class VanillaDB:
    seed_value: int = 0
    items: dict[str, ItemDef] = field(default_factory=dict)
    fluids: dict[str, FluidDef] = field(default_factory=dict)
    buildings: dict[str, BuildingDef] = field(default_factory=dict)
    recipes: dict[str, RecipeRef] = field(default_factory=dict)

    def beltable_items(self) -> list[ItemDef]:
        return [i for i in self.items.values() if not i.is_tool]

    def pipable_fluids(self) -> list[FluidDef]:
        return list(self.fluids.values())

    def fuel_items(self) -> list[ItemDef]:
        return [i for i in self.items.values() if i.fuel_value]

    def fuel_fluids(self) -> list[FluidDef]:
        return [f for f in self.fluids.values() if f.fuel_value]

    def buildings_of_type(self, functional_type: str) -> list[BuildingDef]:
        return [b for b in self.buildings.values() if b.functional_type == functional_type]

    def extractors_for_medium(self, medium: str) -> list[BuildingDef]:
        return [
            b
            for b in self.buildings.values()
            if b.functional_type == "extractor" and (not medium or b.medium == medium)
        ]
