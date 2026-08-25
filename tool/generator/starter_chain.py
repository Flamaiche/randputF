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

from tool.common.db import SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.generator.map_patches import Patch
from tool.generator.recipes import (
    ProgressionState,
    _item_for_building,
    ensure_obtainable,
)

KIT_AMMO_COUNT = 50

TRANSPORT_PATTERNS = {
    "belt": ["transport-belt"],
    "splitter": ["splitter"],
    "underground": ["underground-belt"],
    "pipe": ["pipe"],
    "pipe_to_ground": ["pipe-to-ground"],
    "inserter": ["inserter"],
}


@dataclass
class StarterChain:
    kit: list[dict] = field(default_factory=list)
    free_researches: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    tech_steps: list[dict] = field(default_factory=list)
    buildings: list[str] = field(default_factory=list)
    recipes: list[dict] = field(default_factory=list)
    state: ProgressionState = field(default_factory=ProgressionState)


def build_starter_chain(rng: random.Random, db: VanillaDB, patches: list[Patch]) -> StarterChain:
    chain = StarterChain()
    chain.kit = _roll_starter_kit(rng, db)

    state = ProgressionState()
    for patch in patches:
        # Les ressources au sol sont valides d'office (extraction directe),
        # mais elles ne deviennent des ingredients utilisables qu'une fois
        # la branche extraction -> transport posee ci-dessous.
        state.mark_obtained(patch.kind, patch.resource)

    for resource_kind, resource_name in _unique_resources(patches):
        _ensure_extraction(rng, db, state, resource_kind, resource_name)

    _ensure_transformer(rng, db, state)
    _ensure_transports(rng, db, state)

    chain.state = state
    chain.steps = state.steps
    chain.buildings = sorted(state.unlocked_buildings)
    chain.recipes = state.recipes
    chain.tech_steps = _build_tech_steps(state, rng)
    return chain


def _unique_resources(patches: list[Patch]) -> list[tuple[str, str]]:
    seen: dict[tuple[str, str], None] = {}
    for patch in patches:
        seen.setdefault((patch.kind, patch.resource))
    return list(seen)


def _build_tech_steps(state: ProgressionState, rng: random.Random) -> list[dict]:
    """Regroupe les micro-steps en macro-steps pour le tech tree."""
    tech_steps = []
    
    # Regrouper par type de ressource
    extraction_steps = [s for s in state.steps if s.get("type") == "extract"]
    craft_steps = [s for s in state.steps if s.get("type") == "craft"]
    
    # Créer une macro-step pour l'extraction
    if extraction_steps:
        step = {
            "id": "randputf-starter-extraction",
            "title": "Extraction initiale",
            "unlocks_recipes": [],
            "unlocks_buildings": [s["extractor"] for s in extraction_steps],
            "cost": [],
            "count": 10,
        }
        tech_steps.append(step)
    
    # Créer une macro-step pour la transformation
    if craft_steps:
        step = {
            "id": "randputf-starter-transformation",
            "title": "Transformation initiale",
            "unlocks_recipes": [s["recipe"] for s in craft_steps if "recipe" in s],
            "unlocks_buildings": [],
            "cost": [],
            "count": 10,
        }
        tech_steps.append(step)
    
    return tech_steps


def _ensure_extraction(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
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
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name)
        state.unlocked_buildings.add(extractor.name)
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
        return fluid_extractors
    return [b for b in db.extractors_for_medium("ground") if b.fluid_outputs == 0]


def _ensure_transformer(rng: random.Random, db: VanillaDB, state: ProgressionState) -> None:
    transformers = db.buildings_of_type("transformer")
    if not transformers:
        return
    chosen = rng.choice(transformers)
    item = _item_for_building(db, chosen.name)
    if item is not None:
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name)
        state.unlocked_buildings.add(chosen.name)


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
        # Bras si besoin : utile des qu'un tapis alimente une machine.
        if rng.random() < 0.5:
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
    patterns = TRANSPORT_PATTERNS[role]
    candidates = [
        i
        for i in db.items.values()
        if any(pattern in i.name for pattern in patterns) and not i.is_tool
    ]
    if not candidates:
        return
    chosen = rng.choice(candidates)
    ensure_obtainable(rng, db, state, SLOT_ITEM, chosen.name)


def _roll_starter_kit(rng: random.Random, db: VanillaDB) -> list[dict]:
    guns = [i for i in db.items.values() if i.is_gun]
    ammos = [i for i in db.items.values() if i.is_ammo]
    kit: list[dict] = []
    if guns:
        gun = rng.choice(guns)
        kit.append({"type": "item", "name": gun.name, "count": 1})
        if ammos:
            # Munitions calees : meme categorie que l'arme si connue.
            matching = [
                a for a in ammos if gun.ammo_category and a.ammo_category == gun.ammo_category
            ]
            ammo = rng.choice(matching or ammos)
            kit.append({"type": "item", "name": ammo.name, "count": KIT_AMMO_COUNT})
    return kit
