"""Phase 2 : chaîne initiale - starter (README §7 et §8).

IMPLEMENTE sur les primitives partagees (generator/recipes.py) :
- kit de depart : arme + munitions calees ;
- un extracteur par ressource de patch selon son milieu ;
- un bâtiment de transformation tire parmi la banque ;
- transports adaptés : tapis/splitter/underground (+ bras si besoin) pour
  les items, tuyaux + pipe-to-ground pour les fluides ; le palier (tier)
  de chaque transport est tiré au sort ;
- anti-cycle §8 : garanti par construction dans les primitives (ingredients
  tires uniquement dans le pool deja valide, ateliers debloques
  sequentiellement, bootstrap final = fabrication a la main).

Le ProgressionState produit ici EST l'etat repris par les phases suivantes
(recursive, electricite, tech tree).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.common.db import SLOT_FLUID, SLOT_ITEM, ENVIRONMENTAL_ITEMS, ItemDef, VanillaDB
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


def build_starter_chain(rng: random.Random, db: VanillaDB, patches: list[Patch]) -> StarterChain:
    chain = StarterChain()
    chain.kit = _roll_starter_kit(rng, db)

    state = ProgressionState()
    # Pool environnemental de base (README §3, §6) : arbres/rochers/poissons
    # sont récoltables à la main dès le départ. Ils alimentent le pool
    # d'ingrédients initial ; les recettes de démarrage n'ont donc pas besoin
    # de tourner à vide (plus de bootstrap 0-ingrédient).
    for env_item in ENVIRONMENTAL_ITEMS:
        if env_item in db.items:
            state.mark_obtained(SLOT_ITEM, env_item)
    for patch in patches:
        state.mark_obtained(patch.kind, patch.resource)

    for resource_kind, resource_name in _unique_resources(patches):
        _ensure_extraction(rng, db, state, chain, resource_kind, resource_name)

    _ensure_transformer(rng, db, state, chain)
    _ensure_transports(rng, db, state)
    _ensure_research(rng, db, state)
    _ensure_first_science_pack(
        rng, db, state, chain, db.raw_resources({p.resource for p in patches})
    )

    # Kit de départ : arme(s) de poing + munitions ALIGNÉES (roulé en tête de
    # build_starter_chain). On rend ensuite l'arme et les munitions REFABRI-
    # QUABLES dans la seed : même si le kit fournit un stock initial, le joueur
    # doit pouvoir en recrafter (§7). Échec = kit quand même fourni.
    _ensure_kit_craftable(rng, db, state, chain.kit)

    # Spawn cohérent avec la seed : on remplace l'inventaire de départ vanilla
    # par le fabricateur + l'extracteur URPLS de la seed. Si l'un d'eux est à
    # combustible ("burner"), on ajoute aussi un combustible pour pouvoir les
    # démarrer sans chercher à la main.
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

    Appelé après le starter PUIS rejoué après l'électricité (pipeline.py) :
    toute recette créée sur le tas (générateur, combustible) doit appartenir à
    une tech, jamais rester sans unlock.

    Chaque recette est unlockée par UNE SEULE tech : les recettes des items
    d'extracteur appartiennent à la tech d'extraction, la tech de
    transformation n'ouvre que les autres recettes de craft (pas de doublon
    d'unlock entre les deux techs starter).
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
) -> None:
    candidates = _extractors_for_resource(db, resource_kind, resource_name)
    if not candidates:
        raise ValueError(
            f"aucun extracteur pour {resource_kind} {resource_name}"
        )
    extractor = rng.choice(candidates)
    item = _item_for_building(db, extractor.name)
    if item is not None:
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name, exclude_buildings=_EXCLUDED_BUILDINGS)
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


def _extractors_for_resource(db: VanillaDB, kind: str, name: str):
    if kind == SLOT_FLUID:
        fluid_extractors = [
            b for b in db.buildings_of_type("extractor") if b.fluid_outputs > 0
        ]
        if name == "water":
            water_pumps = [b for b in fluid_extractors if b.pumped_fluid == "water"]
            return water_pumps or [b for b in db.extractors_for_medium("water")]
        # Les « lacs » (étendues fluides non-eau : pétrole brut, gaz, acide…)
        # sont extractibles SANS électricité, comme l'eau : on préfère une
        # pompe à énergie void (offshore-pump — §10). Le pumpjack électrique
        # n'est qu'un repli si aucune pompe sans électricité n'existe : sinon
        # un lac exigerait l'électricité pour l'extraire, boucle dure §10.
        no_electric = [
            b for b in fluid_extractors if b.energy_type in ("void", "burner")
        ]
        if no_electric:
            return no_electric
        # Repli : gisement en resource-category (basic-fluid/basic-gas) pompé
        # par un extracteur qui déclare ces categories (pumpjack, ...).
        return [
            b for b in fluid_extractors
            if b.resource_categories
            and any("fluid" in c or "gas" in c for c in b.resource_categories)
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
        b for b in db.buildings_of_type("transformer")
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
    """Garantit un bâtiment de RECHERCHE (type "research", par essence un lab)
    dès la phase starter.

    Toute recherche non gratuite (les 3 dispatches relais, §9.3, puis toutes
    les sciences §13) se réalise DANS un lab : sans lab, le joueur ne peut
    rien rechercher après les techs gratuites et la partie se fige. Le lab est
    donc une brique indispensable du bootstrap, au même titre que les
    transports : cette recette de craft est unlockée par la 2e recherche
    gratuite (starter-transformation)."""
    candidates = [
        i
        for i in db.items.values()
        if i.place_result is not None
        and db.buildings.get(i.place_result) is not None
        and db.buildings[i.place_result].functional_type == "research"
        and i.name not in state.obtained_items
    ]
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
    """Garantit un PREMIER science pack craftable dès le bootstrap (façon
    red-science vanilla : sa recette est disponible au début, et les techs de
    prologue la consomment comme coût — seuls les items TOOL, ici les packs,
    peuvent servir de coût de recherche §13).

    Sa recette est un step de craft du starter : elle est donc unlockée
    GRATUITEMENT par la tech starter-transformation, avant toute tech de
    prologue payante. C'est le point d'entrée de l'économie de packs.

    §13 : la recette du pack est tirée SANS ressource brute (patches,
    environnement, fluides d'extraction eau/pétrole/vapeur — infinis ou non) :
    les packs ne se craftent jamais à partir de matières extraites du sol."""
    packs = [
        i for i in db.items.values()
        if i.is_science_pack and i.name not in state.obtained_items
    ]
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


def _ensure_transport_item(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    role: str,
) -> None:
    patterns = _config.transport_patterns[role]
    candidates = [
        i
        for i in db.items.values()
        if any(pattern in i.name for pattern in patterns) and not i.is_tool
    ]
    if not candidates:
        return
    chosen = rng.choice(candidates)
    ensure_obtainable(rng, db, state, SLOT_ITEM, chosen.name, exclude_buildings=_EXCLUDED_BUILDINGS)


def _roll_starter_kit(rng: random.Random, db: VanillaDB) -> list[dict]:
    guns = [i for i in db.items.values() if i.is_handheld_gun]
    ammos = [i for i in db.items.values() if i.is_ammo]
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
    """Rend l'arme et les munitions du kit CRAFTABLES dans la seed.

    « Coneorde avec le reste » (§7) : l'arme de départ ne doit pas être une
    munition/arme frappée de recette désactivée — même si le kit en fournit
    un stock initial, le joueur doit pouvoir EN REFABRIQUER. `ensure_obtainable`
    crée la recette randomisée randputf-<arme> / randputf-<munition>, attachée
    aux techs du starter via build_tech_steps. Échec = kit quand même fourni
    (le stock initial suffit)."""
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
    """Ajoute au kit de départ le fabricateur et l'extracteur URPLS de la seed,
    ainsi qu'un combustible si l'un d'eux est à combustible (burner).

    Pas de vérification de compatibilité de catégorie : le mod unifie toutes
    les catégories de combustible au data-stage (§8) — tout brûleur accepte
    tout combustible. On glisse donc simplement la plus grosse fuel_value du
    pool (uranium-fuel-cell inclus s'il est obtenu).

    Les mêmes items sont déjà rendus CRAFTABLES (état de la seed), donc on ne
    refait pas `ensure_obtainable` ici : on fournit simplement un stock initial
    cohérent. Seuls des items obtenus par la seed (fabricateur/extracteur
    choisis ; combustible issu du pool de state) peuvent être glissés au kit."""
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
            to_add.append({"type": SLOT_ITEM, "name": item.name, "count": 1})

    if to_add and _needs_fuel(db, chain):
        fuel = _pick_spawn_fuel(db, state)
        if fuel is not None:
            # Compte borné par la stackabilité réelle : un nuclear-fuel
            # (stack_size 1) ne remplit qu'UN seul slot — en donner 50
            # inonde l'inventaire de slots à 1 exemplaire.
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
    """Meilleur combustible de la seed : item combustible présent dans le pool
    des items obtenus (le plus gros fuel_value), sinon le bois (toujours
    obtenable, environnemental).

    PAS de filtrage par catégorie : le mod applique une catégorie de
    combustible globale au data-stage (mod/data-updates.lua, §8) — tout
    brûleur accepte tout combustible (item ou fluide). La plus grosse
    fuel_value est donc toujours utilisable dans le brûleur du kit."""
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
