"""Phase 4 : résolution de l'électricité (README §10).

L'électricité est un type à part : elle n'est pas « randputisée » en tant que
ressource. Ce qui se randomise, c'est tout ce qui l'entoure :
- Déclenchement à la demande : si un bâtiment tiré a besoin d'électricité
  dès le début, alors le réseau électrique est débloqué au début.
- Générateurs : tout ce qui peut produire de l'électricité est dans le
  même cas.
- Combustible du générateur :
  - si le bâtiment a besoin d'un combustible item, on lui assigne un item ;
  - s'il a besoin d'un fluide, on lui en prend un disponible dans le pool ;
  - s'il n'existe aucune ressource disponible compatible, on crée une
    recette et tout ce qui va avec (même logique de déblocage sur le tas).
"""

from __future__ import annotations

import random

from tool.common.db import SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.generator.recipes import ProgressionState, ensure_obtainable


def resolve_electricity(
    rng: random.Random,
    db: VanillaDB,
    starter,
) -> None:
    """Résout l'électricité : déclenchement à la demande, combustible assigné."""
    state = starter.state
    buildings_unlocked = state.unlocked_buildings

    # Vérifier si un bâtiment électrique est déjà débloqué
    needs_electricity = _needs_electricity(db, buildings_unlocked)

    if needs_electricity:
        # Débloquer un générateur
        generator = _pick_generator(rng, db, state)
        if generator:
            _unlock_generator(rng, db, state, generator)
    else:
        # Pas de besoin électrique immédiat, on passe
        pass


def _needs_electricity(db: VanillaDB, unlocked_buildings: set[str]) -> bool:
    """Vérifie si un bâtiment débloqué a besoin d'électricité."""
    for building_name in unlocked_buildings:
        building = db.buildings.get(building_name)
        if building and building.energy_type == "electric":
            return True
    return False


def _pick_generator(rng: random.Random, db: VanillaDB, state: ProgressionState):
    """Choisit un générateur non débloqué."""
    generators = [
        b
        for b in db.buildings_of_type("generator")
        if b.name not in state.unlocked_buildings
    ]
    if not generators:
        return None
    return rng.choice(generators)


def _unlock_generator(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    generator,
) -> None:
    """Débloque un générateur et lui assigne un combustible."""
    from tool.generator.recipes import _item_for_building, _unlock_building

    # Débloquer le bâtiment
    _unlock_building(rng, db, state, generator, "electricity")

    # Assigner un combustible
    fuel = _pick_fuel(rng, db, state, generator)
    if fuel:
        kind, name = fuel
        ensure_obtainable(rng, db, state, kind, name)


def _pick_fuel(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    generator,
) -> tuple[str, str] | None:
    """Choisit un combustible pour le générateur."""
    # Combustibles items disponibles
    fuel_items = [
        item
        for item in db.fuel_items()
        if item.name in state.obtained_items
    ]

    # Combustibles fluides disponibles
    fuel_fluids = [
        fluid
        for fluid in db.fuel_fluids()
        if fluid.name in state.obtained_fluids
    ]

    # Choisir au hasard parmi les disponibles
    candidates = [(SLOT_ITEM, item.name) for item in fuel_items]
    candidates += [(SLOT_FLUID, fluid.name) for fluid in fuel_fluids]

    if not candidates:
        return None

    return rng.choice(candidates)
