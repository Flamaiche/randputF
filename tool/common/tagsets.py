"""Ensembles de noms figés (D3) : source unique par ensemble.

Centralise les listes en dur qui ne se parlent pas (chantier D3). Chaque
ensemble a UNE seule définition ici ; les modules consommateurs l'importent
(tool.common.db re-exporte pour compatibilité). Index de référence :
``docs/tags.md §14`` — ne définir un ensemble nul part ailleurs que ce module
et cette section. Les valeurs sont des constantes de conception, stables :
les modifier change l'espace des seeds (déterminisme, §nondeterminism).
"""

from __future__ import annotations

# Ressources non automatisables : récoltées à la main depuis des entités du
# monde (arbres → wood, rochers → stone, poissons → raw-fish). Jamais un patch,
# disponibles dès le départ, ingrédients possibles des recettes randomisées.
ENVIRONMENTAL_ITEMS = frozenset({"wood", "stone", "raw-fish"})

# Catégories de crafting valides : un bâtiment qui en possède une est un atelier
# général multi-recettes, pas un fabricateur à recette fixe. Partagée ici pour
# éviter tout cycle d'import avec les parsers.
VALID_RECIPE_CATEGORIES = frozenset({
    "crafting",
    "basic-crafting",
    "advanced-crafting",
    "smelting",
    "chemistry",
    "crafting-with-fluid",
    "oil-processing",
    "rocket-building",
    "centrifuging",
})

ROCKET_CHAIN = frozenset({"processing-unit", "low-density-structure", "rocket-fuel"})

# Armes MONTÉES sur des entités : de type « gun » dans le dump mais PAS
# utilisables à pied — les randomiser comme armes de poing produit du contenu
# mort. Exclues du pool « de poing ». La pool RecursiveConfig.vehicle_weapons
# peut les inclure comme source d'un clone monté sur véhicule.
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

# Types d'items non-empilables (stack_size = 1) : une recette ne peut en
# produire/consommer que 1 exemplaire. Fallback quand le dump n'emporte pas
# stack_size (type conservateur). "tool" (science packs !) et "module"/"ammo"
# sont stackables et volontairement absents.
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
    }
)

# Rails POLLABLES (vrai tracé de voie) : droits/courbes/half-diagonal, legacy
# et surélevés. Les ``-remnants``, ``rail-ramp``/``rail-support`` (dummies) et
# ``loader``/``linked-belt`` sont exclus. Jeu de TYPES d'entités API 2.0.
RAIL_TYPES = frozenset({
    "straight-rail",
    "curved-rail-a",
    "curved-rail-b",
    "half-diagonal-rail",
    "legacy-straight-rail",
    "legacy-curved-rail",
    "elevated-straight-rail",
    "elevated-curved-rail-a",
    "elevated-curved-rail-b",
    "elevated-half-diagonal-rail",
})

# Items « contrôle » non fabricables / non empilables (blueprint, planners,
# remotes), détectés par TYPE d'item. Le rail vanilla (``rail-planner`` 2.0)
# est volontairement absent : il se fabrique et se pose.
VIRTUAL_ITEM_TYPES = frozenset({
    "blueprint", "blueprint-book", "deconstruction-item", "upgrade-item",
    "selection-tool", "copy-paste-tool", "rail-planner", "spidertron-remote",
})

# Seules ces catégories acceptent des fluides en ingrédients.
FLUID_RECIPE_CATEGORIES = frozenset({
    "crafting-with-fluid",
    "chemistry",
    "oil-processing",
})

# Transformateurs du starter : bâtiments de base forcés dans la chaîne initiale
# pour pouvoir transformer les raws de départ (forge, assembleur).
STARTER_TRANSFORMERS = frozenset({
    "stone-furnace",
    "steel-furnace",
    "assembling-machine-1",
    "assembling-machine-2",
})

# Bâtiments à ne JAMAIS ouvrir au starter (déjà hérités du design moteur :
# lab/rocket-silo/centrifuge sont des terminaux ou des machines lourdes qui
# écraseaient la cadence initiale) — raccourci de pool pour le tirage starter.
EXCLUDED_BUILDINGS = frozenset({"character", "lab", "rocket-silo", "centrifuge", "nuclear-reactor", "oil-refinery", "chemical-plant", "assembling-machine-3"})

# Recettes/endgame exclues de la phase easeup (déjà hors de la timeline).
ENDGAME_EXCLUDED = frozenset({"rocket", "satellite", "rocket-silo", "rocket-part"})