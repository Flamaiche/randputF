"""Phase 2 : chaîne initiale - starter (§7/§8).

IMPLEMENTE sur les primitives partagees (generator/recipes.py) :
- kit de depart (arme + munitions calees) ;
- un extracteur par ressource de patch selon son milieu ;
- un bâtiment de transformation tire parmi la banque ;
- transports adaptés (tapis/splitter/underground + bras ; tuyaux pour les
  fluides), palier tire au sort ;
- anti-cycle §8 garanti par construction dans les primitives.

Le ProgressionState produit ici EST l'etat repris par les phases suivantes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.common.db import SLOT_FLUID, SLOT_ITEM, ENVIRONMENTAL_ITEMS, ItemDef, VanillaDB
from tool.generator.early_oracle import build_early_sources
from tool.generator.map_patches import Patch
from tool.generator.recipes import (
    ProgressionState,
    _item_for_building,
    ensure_obtainable,
)
from tool.prototypes.starter import StarterConfig

_SPAWN_FUEL_COUNT = 50

_config = StarterConfig()


def set_config(config: dict) -> None:
    global _config
    _config = StarterConfig.from_config(config)


@dataclass
class StarterChain:
    kit: list[dict] = field(default_factory=list)
    free_researches: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    tech_steps: list[dict] = field(default_factory=list)
    buildings: list[str] = field(default_factory=list)
    recipes: list[dict] = field(default_factory=list)
    state: ProgressionState = field(default_factory=ProgressionState)
    first_science_pack: str = ""
    fabricator: str = ""
    extractors: list[str] = field(default_factory=list)
    # GEL DES PROMESSES (§10ter) : snapshot des produits des recettes des techs
    # gratuites, pris après l'électricité (pipeline.py). Les primitives
    # dédupées garantissent qu'aucun produit promis n'est re-baké.
    promises: set[str] = field(default_factory=set)


def build_starter_chain(rng: random.Random, db: VanillaDB, patches: list[Patch], *, has_lakes: bool = False, lake_resources: frozenset[str] = frozenset()) -> StarterChain:
    chain = StarterChain()
    chain.kit = _roll_starter_kit(rng, db)

    state = ProgressionState()
    # Environnement (arbres/rochers/poissons), docs/ressources.md §6 : obtenable à la
    # main dès le départ — alimente le pool d'ingrédients initial.
    for env_item in ENVIRONMENTAL_ITEMS:
        if env_item in db.items:
            state.mark_obtained(SLOT_ITEM, env_item)
    for patch in patches:
        state.mark_obtained(patch.kind, patch.resource)

    # Bootstrap inline (§10ter) : activer le watershed pré-élec ici. Toutes
    # les recettes du starter (et de l'électricité, avant le gel pipeline.py)
    # tirent leurs ingrédients uniquement dans ce watershed, sans atelier
    # électrique : chaque produit promis est jouable pré-élec par construction.
    patch_items = {p.resource for p in patches if p.kind == SLOT_ITEM}
    early_items, early_fluids = build_early_sources(db, patch_items, set(lake_resources))
    state.early.activate(early_items, early_fluids)

    for resource_kind, resource_name in _unique_resources(patches):
        _ensure_extraction(rng, db, state, chain, resource_kind, resource_name)

    # Les LACS (§7.5) sont des TUILES fluides : leur extracteur est une pompe sans
    # électricité (offshore-pump), distincte de l'extracteur des patchs fluides
    # (entités basic-fluid → pumpjack). Sans patch fluide, pas de « lacs muets ».
    for lake_resource in sorted(lake_resources):
        _ensure_extraction(rng, db, state, chain, SLOT_FLUID, lake_resource, is_lake=True)

    _ensure_transformer(rng, db, state, chain)
    _ensure_transports(rng, db, state)
    _ensure_research(rng, db, state)
    _ensure_first_science_pack(
        rng, db, state, chain, db.raw_resources({p.resource for p in patches})
    )
    # C4 : un lac tiré (plus d'eau vanilla) = mur sur la carte ; le landfill
    # doit être craftable dès le départ (unlocké par starter-transformation),
    # jamais au hasard en profondeur de seed.
    if has_lakes:
        _ensure_landfill(rng, db, state)

    # Kit de départ : arme + munitions alignées (roulé en tête de fonction).
    # On rend ensuite l'arme et les munitions refabriquables dans la seed
    # (recette §7), même si le kit fournit un stock initial. Échec = kit quand
    # même fourni.
    _ensure_kit_craftable(rng, db, state, chain.kit)

    # Conteneur de stockage (§7) : recette de chest garantie, en matériaux
    # finis (produits). Flux RNG INDÉPENDANT pour ne pas perturber celui du
    # starter (et donc la carte, re-tirée par `resolve_electricity`).
    _ensure_chest_craftable(
        random.Random(f"randputf:chest:{db.seed_value}"), db, state
    )

    # Spawn cohérent avec la seed : inventaire de départ = fabricateur +
    # extracteur de la seed, plus un combustible s'ils sont à "burner".
    _extend_spawn_kit(rng, db, chain, state)

    chain.state = state
    chain.steps = state.steps
    chain.buildings = sorted(state.unlocked_buildings)
    chain.recipes = state.recipes
    chain.tech_steps = build_tech_steps(state, db)
    return chain


def _unique_resources(patches: list[Patch]) -> list[tuple[str, str]]:
    seen: dict[tuple[str, str], None] = {}
    for patch in patches:
        seen.setdefault((patch.kind, patch.resource))
    return list(seen)


def build_tech_steps(state: ProgressionState, db: VanillaDB) -> list[dict]:
    """Regroupe les micro-steps en macro-steps pour le tech tree.

    Rejoué après l'électricité (pipeline.py) : toute recette créée sur le tas
    (générateur, combustible) doit appartenir à une tech. Chaque recette est
    unlockée par une seule tech : items d'extracteur → tech d'extraction, les
    autres crafts → tech de transformation.
    """
    tech_steps = []

    extraction_steps = [s for s in state.steps if s.get("type") == "extract"]
    craft_steps = [s for s in state.steps if s.get("type") == "craft"]

    extractor_item_recipes = {
        r["name"]
        for extractor_name in (s["extractor"] for s in extraction_steps)
        if (item := _item_for_building(db, extractor_name)) is not None
        for r in state.recipes
        if any(
            res.get("type") == SLOT_ITEM and res.get("name") == item.name
            for res in r.get("results", [])
        )
    }

    if extraction_steps and extractor_item_recipes:
        step = {
            "id": "randputf-starter-extraction",
            "title": "Extraction initiale",
            "unlocks_recipes": sorted(extractor_item_recipes),
            "unlocks_buildings": [],
            "cost": [],
            "count": 1,
        }
        tech_steps.append(step)

    if craft_steps:
        craft_recipes = list(dict.fromkeys(s["recipe"] for s in craft_steps if "recipe" in s))
        transform_recipes = [r for r in craft_recipes if r not in extractor_item_recipes]
        if transform_recipes:
            step = {
                "id": "randputf-starter-transformation",
                "title": "Transformation initiale",
                "unlocks_recipes": transform_recipes,
                "unlocks_buildings": [],
                "cost": [],
                "count": 1,
            }
            tech_steps.append(step)

    return tech_steps


def _ensure_extraction(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    chain: StarterChain,
    resource_kind: str,
    resource_name: str,
    *,
    is_lake: bool = False,
) -> None:
    candidates = _extractors_for_resource(
        db, resource_kind, resource_name, is_lake=is_lake
    )
    if not candidates:
        raise ValueError(
            f"aucun extracteur pour {resource_kind} {resource_name}"
        )
    extractor = rng.choice(candidates)
    item = _item_for_building(db, extractor.name)
    if item is not None:
        # force=True (§7) : l'extracteur doit avoir sa recette de craft dans la
        # tech d'extraction (tech 0), même si son item est posé au sol en patch
        # (§6) — sinon un extracteur-patch ne serait craftable qu'en profondeur
        # de seed. La recette forcée reste dans un atelier starter.
        ensure_obtainable(
            rng, db, state, SLOT_ITEM, item.name,
            exclude_buildings=_EXCLUDED_BUILDINGS, force=True,
        )
        state.unlocked_buildings.add(extractor.name)
    if extractor.name not in chain.extractors:
        chain.extractors.append(extractor.name)
    state.steps.append(
        {
            "type": "extract",
            "resource": {"type": resource_kind, "name": resource_name},
            "extractor": extractor.name,
        }
    )


def _extractors_for_resource(db: VanillaDB, kind: str, name: str, *, is_lake: bool = False):
    if kind == SLOT_FLUID:
        fluid_extractors = [
            b for b in db.buildings_with_tag("is_extractor") if b.fluid_outputs > 0
        ]
        if is_lake:
            # Un LAC est une TUILE fluide (copie de la tuile eau, §7.5) : la
            # pompe offshore extrait sans électricité ; le pumpjack n'y a rien.
            water_pumps = [b for b in fluid_extractors if b.pumped_fluid == "water"]
            return water_pumps or [b for b in fluid_extractors if b.energy_type in ("void", "burner")]
        # Un PATCH fluide est une entité resource sur la TERRE (§6.5, §7.5) :
        # les pompes offshore ne minent que les tuiles d'eau — seul un drill de
        # la catégorie (pumpjack, électrique) miniage. Priorité au non-électrique.
        no_electric_drills = [
            b for b in fluid_extractors
            if "basic-fluid" in b.resource_categories
            and b.energy_type in ("void", "burner")
        ]
        if no_electric_drills:
            return no_electric_drills
        return [
            b for b in fluid_extractors
            if "basic-fluid" in b.resource_categories
        ]
    return [b for b in db.extractors_for_medium("ground") if b.fluid_outputs == 0]


_STARTER_TRANSFORMERS = frozenset({
    "stone-furnace",
    "steel-furnace",
    "assembling-machine-1",
    "assembling-machine-2",
})

_EXCLUDED_BUILDINGS = frozenset({"character", "lab", "rocket-silo", "centrifuge", "nuclear-reactor", "oil-refinery", "chemical-plant", "assembling-machine-3"})


def _ensure_transformer(rng: random.Random, db: VanillaDB, state: ProgressionState, chain: StarterChain) -> None:
    transformers = [
        b for b in db.buildings_with_tag("is_crafter")
        if b.name in _STARTER_TRANSFORMERS and b.name not in _EXCLUDED_BUILDINGS
    ]
    if not transformers:
        return
    chosen = rng.choice(transformers)
    item = _item_for_building(db, chosen.name)
    if item is not None:
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name, exclude_buildings=_EXCLUDED_BUILDINGS)
        state.unlocked_buildings.add(chosen.name)
    chain.fabricator = chosen.name


def _ensure_research(rng: random.Random, db: VanillaDB, state: ProgressionState) -> None:
    """Garantit un lab dès le starter : toute recherche non gratuite se fait
    dans un lab — sans lab la partie se fige après les techs gratuites. Sa
    recette est unlockée par la 2e recherche gratuite (starter-transformation)."""
    candidates = sorted(
        (
            i
            for i in db.items.values()
            if i.place_result is not None
            and db.buildings.get(i.place_result) is not None
            and db.buildings[i.place_result].is_research
            and i.name not in state.obtained_items
        ),
        key=lambda i: i.name,
    )
    if not candidates:
        return
    item = rng.choice(candidates)
    ensure_obtainable(rng, db, state, SLOT_ITEM, item.name, exclude_buildings=_EXCLUDED_BUILDINGS)
    state.unlocked_buildings.add(item.place_result)


def _ensure_first_science_pack(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    chain: StarterChain,
    raw_resources: frozenset[str] = frozenset(),
) -> None:
    """Garantit un premier science pack craftable dès le bootstrap (façon
    red-science vanilla) : unlocké gratuitement par starter-transformation,
    c'est le point d'entrée de l'économie de packs (§13, seuls les items TOOL
    servent de coût de recherche).

    §13 : recette tirée sans ressource brute (jamais de matière du sol)."""
    packs = sorted(
        (i for i in db.items.values()
         if i.is_science_pack and i.name not in state.obtained_items),
        key=lambda i: i.name,
    )
    if not packs:
        return
    item = rng.choice(packs)
    ensure_obtainable(
        rng, db, state, SLOT_ITEM, item.name,
        exclude_buildings=_EXCLUDED_BUILDINGS,
        forbidden=raw_resources,
    )
    chain.first_science_pack = item.name


def _ensure_transports(rng: random.Random, db: VanillaDB, state: ProgressionState) -> None:
    kinds_present = {
        SLOT_ITEM: any(
            step["type"] == "extract" and step["resource"]["type"] == SLOT_ITEM
            for step in state.steps
        ),
        SLOT_FLUID: any(
            step["type"] == "extract" and step["resource"]["type"] == SLOT_FLUID
            for step in state.steps
        ),
    }
    if kinds_present[SLOT_ITEM]:
        for role in ("belt", "splitter", "underground"):
            _ensure_transport_item(rng, db, state, role)
        if rng.random() < _config.inserter_chance:
            _ensure_transport_item(rng, db, state, "inserter")
    if kinds_present[SLOT_FLUID]:
        for role in ("pipe", "pipe_to_ground"):
            _ensure_transport_item(rng, db, state, role)


# Rôle de transport → TAG de bâtiment (§2, docs/tags.md §2). Sélection par le
# tag du bâtiment posé (place_result), jamais par motif de nom en dur.
TRANSPORT_ROLE_TAGS = {
    "belt": "is_belt",
    "splitter": "is_splitter",
    "underground": "is_underground_belt",
    "pipe": "is_pipe",
    "pipe_to_ground": "is_pipe_to_ground",
    "inserter": "is_inserter",
}


def _ensure_transport_item(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    role: str,
) -> None:
    tag = TRANSPORT_ROLE_TAGS[role]
    candidates = sorted(
        (
            i
            for i in db.items.values()
            if i.place_result
            and getattr(db.buildings.get(i.place_result), tag, False)
        ),
        key=lambda i: i.name,
    )
    if not candidates:
        return
    chosen = rng.choice(candidates)
    ensure_obtainable(rng, db, state, SLOT_ITEM, chosen.name, exclude_buildings=_EXCLUDED_BUILDINGS)


def _ensure_landfill(rng: random.Random, db: VanillaDB, state: ProgressionState) -> None:
    """C4 : landfill craftable dès le bootstrap quand un lac est tiré. Sans eau
    vanilla, un lac est un mur de spawn ; sa recette (balayage §9.6) arriverait
    trop tard. Unlockée par starter-transformation comme les autres crafts."""
    if "landfill" not in db.items:
        return
    if state.is_obtained(SLOT_ITEM, "landfill"):
        return
    ensure_obtainable(
        rng, db, state, SLOT_ITEM, "landfill", exclude_buildings=_EXCLUDED_BUILDINGS
    )


def _ensure_chest_craftable(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
) -> None:
    """Garantit une recette de CHEST (stockage) dans la seed : container d'items
    (is_chest, jamais logistic-container) tiré aléatoirement, recette à matière
    FINIE uniquement (``finite_materials``) — pas d'environnemental ni de
    fluide. Échec = silencieux (une seed sans chest n'est pas bloquante)."""
    candidates: list[str] = []
    for item in db.items.values():
        if not item.place_result:
            continue
        building = db.buildings.get(item.place_result)
        if building is not None and building.is_chest:
            candidates.append(item.name)
    if not candidates:
        return
    chest_name = rng.choice(sorted(candidates))
    try:
        ensure_obtainable(
            rng, db, state, SLOT_ITEM, chest_name,
            exclude_buildings=_EXCLUDED_BUILDINGS,
            finite_materials=True,
        )
    except ValueError:
        pass


def _roll_starter_kit(rng: random.Random, db: VanillaDB) -> list[dict]:
    guns = sorted(
        (i for i in db.items.values() if i.is_handheld_gun),
        key=lambda i: i.name,
    )
    ammos = sorted(
        (i for i in db.items.values() if i.is_ammo),
        key=lambda i: i.name,
    )
    kit: list[dict] = []
    if guns:
        gun = rng.choice(guns)
        kit.append({"type": "item", "name": gun.name, "count": 1})
        if ammos:
            matching = [
                a for a in ammos if gun.ammo_category and a.ammo_category == gun.ammo_category
            ]
            ammo = rng.choice(matching or ammos)
            count = _config.ammo_count
            if ammo.stack_size:
                count = min(_config.ammo_count, ammo.stack_size)
            kit.append({"type": "item", "name": ammo.name, "count": count})
    return kit


def _ensure_kit_craftable(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    kit: list[dict],
) -> None:
    """Rend l'arme et les munitions du kit craftables dans la seed : malgré le
    stock initial fourni, le joueur doit pouvoir en refabriquer (§7).
    « ensure_obtainable » crée la recette randputf-<arme> / randputf-<munition>,
    attachée aux techs du starter. Échec = kit quand même fourni."""
    for entry in kit:
        if entry.get("type") != SLOT_ITEM:
            continue
        try:
            ensure_obtainable(rng, db, state, SLOT_ITEM, entry["name"])
        except ValueError:
            pass


def _extend_spawn_kit(
    rng: random.Random,
    db: VanillaDB,
    chain: StarterChain,
    state: ProgressionState,
) -> None:
    """Ajoute au kit de départ le fabricateur et l'extracteur de la seed, plus un
    combustible si l'un d'eux est à burner.

    Pas de vérification de catégorie : le mod unifie toutes les catégories de
    combustible au data-stage (§8) — on glisse la plus grosse fuel_value du
    pool (uranium-fuel-cell inclus). Items déjà craftables (état de la seed),
    pas de `ensure_obtainable` ici : on fournit seulement un stock initial."""
    to_add: list[dict] = []

    fabricator_item = _item_for_building(db, chain.fabricator) if chain.fabricator else None
    if fabricator_item is not None:
        to_add.append({"type": SLOT_ITEM, "name": fabricator_item.name, "count": 1})

    seen_extractors = set()
    for name in chain.extractors:
        if name in seen_extractors:
            continue
        seen_extractors.add(name)
        item = _item_for_building(db, name)
        if item is not None:
            # Un seul exemplaire par type d'extracteur (§7) : le kit amorce la
            # chaîne (poser le premier extracteur pour extraire de quoi en
            # refabriquer) ; la recette est unlockée par la tech d'extraction.
            to_add.append({"type": SLOT_ITEM, "name": item.name, "count": 1})

    if to_add and _needs_fuel(db, chain):
        fuel = _pick_spawn_fuel(db, state)
        if fuel is not None:
            # Compte borné par la stackabilité réelle : un nuclear-fuel
            # (stack_size 1) ne remplit qu'un slot — en donner 50 inonderait.
            count = _SPAWN_FUEL_COUNT
            if fuel.stack_size:
                count = min(_SPAWN_FUEL_COUNT, fuel.stack_size)
            to_add.append({"type": SLOT_ITEM, "name": fuel.name, "count": count})

    for entry in to_add:
        if entry["name"] not in {e["name"] for e in chain.kit}:
            chain.kit.append(entry)


def _needs_fuel(db: VanillaDB, chain: StarterChain) -> bool:
    fabricator_burner = (
        chain.fabricator
        and db.buildings.get(chain.fabricator) is not None
        and db.buildings[chain.fabricator].energy_type == "burner"
    )
    extractors_burner = any(
        db.buildings.get(name) is not None
        and db.buildings[name].energy_type == "burner"
        for name in chain.extractors
    )
    return fabricator_burner or extractors_burner


def _pick_spawn_fuel(db: VanillaDB, state: ProgressionState) -> ItemDef | None:
    """Meilleur combustible de la seed : plus gros fuel_value parmi les items
    obtenus, sinon le bois (toujours obtenable, environnemental).

    PAS de filtrage par catégorie : le mod applique une catégorie de
    combustible globale au data-stage (§8) — tout brûleur accepte tout."""
    obtainable = [
        db.items[name]
        for name in state.obtained_items
        if name in db.items and db.items[name].fuel_value
    ]
    obtainable.sort(key=lambda i: i.fuel_value or 0.0, reverse=True)
    if obtainable:
        return obtainable[0]
    if "wood" in db.items:
        return db.items["wood"]
    return None
