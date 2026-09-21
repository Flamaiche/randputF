"""Assignation de fluides aux bâtiments à comportement fixe (§6/§10).

Détecte automatiquement les bâtiments qui transforment un fluide en un autre
(boilers, heat-exchangers) ou qui en consomment pour produire de l'énergie
(turbines, steam-engines), et leur assigne un fluide obtainable dès le début
du run (un lac, §7.5).

Rien n'est codé en dur : détection par TAGS (is_generator +
produces_electricity, is_crafter pour les transformateurs) et CAPACITÉS
(fluid_inputs, fluid_outputs, energy_type), jamais par liste de noms.

La seed exporte ``building_fluid_assignments`` :
  { "steam-turbine": {"input": "water"},
    "boiler":         {"input": "crude-oil", "output": "steam-demo"} }
Le mod lit cette section et applique les filters + tooltips en data-updates.
"""

from __future__ import annotations

import random

from tool.common.db import VanillaDB, is_fixed_fluid_crafter
from tool.generator.recipes import ProgressionState


def _is_steam_generator(building) -> bool:
    """Générateur à vapeur : is_generator + produces_electricity + fluide en
    entrée (steam-engine / steam-turbine). ``produces_electricity`` exclut les
    producteurs de chaleur taggés ``is_generator`` (heat-exchanger)."""
    return (
        getattr(building, "is_generator", False)
        and getattr(building, "produces_electricity", False)
        and getattr(building, "fluid_inputs", 0) > 0
    )


def assign_building_fluids(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    lake_resources: set[str],
) -> dict[str, dict[str, str]]:
    """Assigne un fluide de lac à chaque bâtiment à comportement fixe.

    1. Générateurs à vapeur : ``input`` = fluide du lac (consommation →
       énergie).
    2. Transformateurs à recette fixe (boiler, heat-exchanger) : ``input`` et
       ``output`` = deux fluides distincts du lac (transformation active par
       combustible).

    Retourne ``{building_name: {"input": fluid, "output"?: fluid}}``, exporté
    dans la seed et appliqué par le mod en data-stage.
    """
    assignments: dict[str, dict[str, str]] = {}
    if not lake_resources:
        return assignments

    # Ordre déterministe : ``lake_resources`` est un set (itération non stable
    # entre processus) et alimente des rng.choice.
    available = sorted(lake_resources)
    used_as_input: set[str] = set()

    # 1) Générateurs à vapeur (turbine, steam-engine)
    steam_gens = [
        b for b in db.buildings.values()
        if _is_steam_generator(b)
        and b.name not in state.unlocked_buildings
    ]
    rng.shuffle(steam_gens)
    for b in steam_gens:
        fluid = _pick_fluid(rng, available, used_as_input)
        if fluid:
            assignments[b.name] = {"input": fluid}
            used_as_input.add(fluid)

    # 2) Transformateurs à recette fixe (boiler, heat-exchanger)
    # L'output peut réutiliser un fluide déjà en input ailleurs (rôle physique
    # différent) ; contraintes : output ≠ input du même bâtiment, pas de
    # doublon output entre transformateurs.
    fixed_transformers = [
        b for b in db.buildings.values()
        if is_fixed_fluid_crafter(b)
        and b.name not in state.unlocked_buildings
    ]
    rng.shuffle(fixed_transformers)
    used_as_output: set[str] = set()
    for b in fixed_transformers:
        fluid_in = _pick_fluid(rng, available, used_as_input)
        exclude_out = used_as_output | ({fluid_in} if fluid_in else set())
        fluid_out = _pick_fluid(rng, available, exclude_out)
        if fluid_in:
            entry: dict[str, str] = {"input": fluid_in}
            if fluid_out:
                entry["output"] = fluid_out
            assignments[b.name] = entry
            used_as_input.add(fluid_in)
            if fluid_out:
                used_as_output.add(fluid_out)

    return assignments


def _pick_fluid(
    rng: random.Random,
    available: list[str],
    exclude: set[str],
) -> str | None:
    """Choisit un fluide aléatoire parmi les candidats, hors ``exclude``."""
    candidates = [f for f in available if f not in exclude]
    if not candidates:
        return None
    return rng.choice(candidates)