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

# Ressources non automatisables (README §3, §6 et §9.3) : récoltées à la main
# depuis des entités du monde (arbres -> wood, rochers -> stone, poissons ->
# raw-fish). Elles ne constituent JAMAIS un patch, demeurent disponibles dès
# le départ comme pool environnemental de base (ingrédients des premiers
# crafts), et restent des ingrédients possibles des recettes randomisées.
ENVIRONMENTAL_ITEMS = frozenset({"wood", "stone", "raw-fish"})

# La chaîne fusée (les 3 ingrédients de ``rocket-part``, recette vanilla
# exempte §14). Elle est réservée à la fin de partie : aucune autre phase (en
# particulier l'électricité, qui pioche des combustibles) ne doit la débloquer
# en avance. Shared ici (et non dans endgame_phase) pour éviter tout cycle
# d'import entre generators.
ROCKET_CHAIN = frozenset({"processing-unit", "low-density-structure", "rocket-fuel"})

# Les VRAIS pylônes (poteaux électriques) — le lecteur de débit « beacon »
# est un bâtiment de distribution mais PAS un pylône : il ne transporte pas
# le courant (§9.1/§10). La cadence garantie et le starter ne doivent
# débloquer que ceux-ci ; le beacon reste randomisé comme un simple bâtiment.
POWER_POLES = frozenset(
    {"small-electric-pole", "medium-electric-pole", "big-electric-pole", "substation"}
)

# Items « contrôle » non fabricables / non empilables : blueprint, planners,
# copy-paste, selection-tool, remotes (spidertron, artillery, discharge). Ils
# ne sont PAS du contenu de craft : jamais de recette randputf-*, jamais de
# patch au sol (une recette en produirait un nombre > 1 → erreur Factorio
# « item-product is not stackable »). Les science packs partagent curieusement
# le flag is_tool dans le dump ; ils restent traités séparément (filière §13).
TOOL_LIKE_ITEMS = frozenset(
    {
        "blueprint",
        "blueprint-book",
        "deconstruction-planner",
        "upgrade-planner",
        "copy-paste-tool",
        "selection-tool",
        "rail-planner",
        "spidertron-remote",
        "discharge-defense-remote",
        "artillery-targeting-remote",
    }
)

# Armes MONTÉES sur des entités (chars, véhicules, artillerie, spidertron) :
# dans le dump vanilla leur type est « gun », donc is_gun=True, mais elles ne
# sont PAS utilisables à pied par le personnage — les randomiser comme armes
# de poing (kit de départ, combat) produit du contenu mort / trompeur
# (ex. spidertron-rocket-launcher sans spidertron). Elles restent exclues du
# pool d'armes « de poing » et du balayage de couverture §9.6. Depuis la
# randomisation des véhicules (§7/§12.1), la pool RecursiveConfig.vehicle_weapons
# peut contenter ces items MONTÉS-UNIQUEMENT : jamais craftés, ils ne servent
# que de source à un clone monté sur le véhicule (§12.1) — les items legacy
# (tank-machine-gun, spidertron-rocket-launcher-2/3/4, identiques à -1) sont
# du contenu mort : jamais tirés, jamais unlockés.
VEHICLE_GUNS = frozenset(
    {
        "tank-cannon",
        "tank-machine-gun",
        "tank-flamethrower",
        "vehicle-machine-gun",
        "artillery-wagon-cannon",
        "spidertron-rocket-launcher-1",
        "spidertron-rocket-launcher-2",
        "spidertron-rocket-launcher-3",
        "spidertron-rocket-launcher-4",
    }
)

# Types d'items non-empilables (stack_size = 1 dans Factorio vanilla 2.0) :
# une recette ne peut en produire/consommer que 1 exemplaire. Fallback quand
# le dump n'emporte pas stack_size (type conservateur : clamper davantage ne
# casse rien, rater un item non-stackable fait crasher le chargement).
# NB : "tool" (science packs !) et "module"/"ammo" sont stackables et donc
# volontairement absents.
NON_STACKABLE_ITEM_TYPES = frozenset(
    {
        "gun",
        "armor",
        "item-with-entity-data",  # véhicules, wagons, locomotive
        "capsule",  # grenades, remotes, raw-fish — certains sont stack 1
        "repair-tool",
        "mining-tool",
        "selection-tool",
        "copy-paste-tool",
        "blueprint",
        "blueprint-book",
        "deconstruction-item",
        "upgrade-item",
        "rail-planner",
        "spidertron-remote",
    }
)


@dataclass(frozen=True)
class ItemDef:
    name: str
    subgroup: str = ""
    place_result: str | None = None
    fuel_value: float | None = None
    is_ammo: bool = False
    is_gun: bool = False
    is_armor: bool = False
    is_science_pack: bool = False
    is_tool: bool = False
    ammo_category: str = ""
    # Type brut du dump (source de vérité : "item", "gun", "armor",
    # "item-with-entity-data", "capsule", "tool", ...).
    item_type: str = ""
    # Stack size réel (0 = inconnu : dump non régénéré). Quand il est connu,
    # il fait foi ; sinon on déduit la stackabilité du type (voir
    # is_stackable).
    stack_size: int = 0

    @property
    def is_handheld_gun(self) -> bool:
        """Arme utilisable à pied (hors armes montées sur véhicule/spidertron)."""
        return self.is_gun and self.name not in VEHICLE_GUNS

    @property
    def is_stackable(self) -> bool:
        """Un item est-il empilable (stack_size > 1) ? Factorio refuse qu'une
        recette produise/consomme plus de 1 exemplaire d'un item non-stackable
        (armure, arme à feu, véhicule, télécommande...) — erreur de chargement
        « not stackable but has a max count of N ». ``stack_size`` réel du dump
        fait foi quand il est fourni ; sinon on se rabat sur le type (les
        types non-stackables sont connus : gun, armor, item-with-entity-data,
        capsules/remotes, outils de planification)."""
        if self.stack_size:
            return self.stack_size > 1
        return self.item_type not in NON_STACKABLE_ITEM_TYPES


@dataclass(frozen=True)
class FluidDef:
    """Un fluide est identifie par son nom uniquement (README §6) :
    la temperature n'est pas une dimension, elle n'existe pas ici."""

    name: str
    fuel_value: float | None = None


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
    # Bac a rien-decide : items/fluides ecartes des pools (junk) et entites
    # sans capacite reconnue. Conserve pour requalification ulterieure.
    excluded_items: dict[str, dict] = field(default_factory=dict)
    excluded_fluids: dict[str, dict] = field(default_factory=dict)

    def beltable_items(self) -> list[ItemDef]:
        return sorted(
            (i for i in self.items.values() if not i.is_tool),
            key=lambda i: i.name,
        )

    def pipable_fluids(self) -> list[FluidDef]:
        return sorted(self.fluids.values(), key=lambda f: f.name)

    @property
    def extraction_only_fluids(self) -> frozenset[str]:
        """Fluides sans recette de production DIRECTE : l'eau (offshore-pump),
        le pétrole brut (pumpjack) et la vapeur (chaudière). Le
        barillage/débarillage est un cycle (fluide → baril → fluide), pas une
        production : on ignore les recettes dont le nom contient "barrel". Ces
        fluides sont des RESSOURCES BRUTES (README §3) : extraites de
        l'environnement, jamais craftées — infinies ou non."""
        produced = {
            p[1]
            for r in self.recipes.values()
            if "barrel" not in r.name
            for p in r.products
            if p[0] == SLOT_FLUID
        }
        return frozenset(name for name in self.fluids if name not in produced)

    def raw_resources(self, patch_resources: set[str]) -> frozenset[str]:
        """Ressources « brutes » d'une seed (README §3) : patches posés au sol
        (fini), items environnementaux récoltables à la main (arbres/rochers/
        poissons) et fluides d'extraction (eau/pétrole brut/vapeur — infinis
        ou non). Un science pack ne doit JAMAIS être crafté avec une ressource
        brute (§13) : exclue en génération (forbidden) et vérifiée par
        pipeline_validator."""
        return frozenset(patch_resources) | set(ENVIRONMENTAL_ITEMS) | self.extraction_only_fluids

    def fuel_items(self) -> list[ItemDef]:
        return sorted(
            (i for i in self.items.values() if i.fuel_value),
            key=lambda i: i.name,
        )

    def fuel_fluids(self) -> list[FluidDef]:
        return sorted(
            (f for f in self.fluids.values() if f.fuel_value),
            key=lambda f: f.name,
        )

    def buildings_of_type(self, functional_type: str) -> list[BuildingDef]:
        return sorted(
            (b for b in self.buildings.values() if b.functional_type == functional_type),
            key=lambda b: b.name,
        )

    def extractors_for_medium(self, medium: str) -> list[BuildingDef]:
        return sorted(
            (
                b
                for b in self.buildings.values()
                if b.functional_type == "extractor" and (not medium or b.medium == medium)
            ),
            key=lambda b: b.name,
        )
