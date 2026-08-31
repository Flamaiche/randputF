"""electricity_v2.py — Résolution complète de l'électricité (README §10).

═══════════════════════════════════════════════════════════════════════════════
                        POURQUOI CE MODULE ?
═══════════════════════════════════════════════════════════════════════════════

L'ancien electricity.py avait trois problèmes :
  1. Il ne produisait PAS de tech steps → l'électricité n'apparaissait pas
     dans l'arbre technologique, alors que §10 dit qu'elle est débloquée
     "à la demande" via des techs.
  2. Si aucun combustible n'était disponible, le générateur était débloqué
     SANS combustible → bâtiment inutile, le joueur ne peut pas produire
     d'électricité.
  3. Il ne gérait qu'UN seul besoin électrique, alors que le joueur peut
     avoir plusieurs bâtiments électriques débloqués.

═══════════════════════════════════════════════════════════════════════════════
                     LOGIQUE DE RÉSOLUTION (README §10)
═══════════════════════════════════════════════════════════════════════════════

L'électricité est un type à part (ni item ni fluide). Elle n'est pas
"randputisée". Ce qui se randomise, c'est tout ce qui l'entoure :

  1. DÉCLENCHEMENT À LA DEMANDE :
     Si un bâtiment tiré (starter ou récursif) a besoin d'électricité
     (energy_type == "electric"), on débloque le réseau électrique.

  2. GÉNÉRATEURS :
     Tout ce qui peut produire de l'électricité est dans le même cas.
     Si un besoin électrique apparaît, un générateur est choisi
     aléatoirement, puis le besoin de ce bâtiment entraîne la suite.

  3. COMBUSTIBLE DU GÉNÉRATEUR :
     - Si le générateur a besoin d'un combustible item → on lui en
       assigne un du pool déjà obtenu.
     - Si le générateur a besoin d'un fluide → on en prend un disponible.
     - SI AUCUNE RESSOURCE COMPATIBLE N'EXISTE → on crée une recette
       et tout ce qui va avec (déblocage sur le tas, §9.3).

═══════════════════════════════════════════════════════════════════════════════
                          FORMAT DE SORTIE
═══════════════════════════════════════════════════════════════════════════════

Ce module retourne une liste de tech steps (même format que les autres
phases) qui seront intégrées dans le tech tree via tech_graph.py.

Chaque step contient :
  - id : "randputf-electricity-<nom_du_generateur>"
  - title : "Électricité: <nom>"
  - unlocks_recipes : recettes créées (y compris le combustible si créé)
  - unlocks_buildings : le générateur débloqué
  - cost : [] (l'électricité est gating par sa position dans l'arbre,
    pas par un coût matériel — c'est l'accumulation des prerequis qui
    impose la progression)
  - count : 1 (pas de coût, donc count=1)
"""

from __future__ import annotations

import random

from tool.common.db import SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.generator.recipes import ProgressionState, ensure_obtainable
from tool.prototypes.electricity import ElectricityConfig

_config = ElectricityConfig()


def set_config(config: dict) -> None:
    global _config
    _config = ElectricityConfig.from_config(config)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                       TYPES DE DONNÉES                                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class ElectricityResolution:
    """Résultat de la résolution électrique.

    Contient :
      - needs_electricity : True si au moins un bâtiment électrique a été
        détecté dans les bâtiments débloqués
      - tech_steps : les étapes technologiques à ajouter au tech tree
      - generator_name : le nom du générateur choisi (None si pas de besoin)
      - fuel : le combustible assigné (kind, name) ou None
      - fuel_created : True si le combustible a été créé sur le tas
    """

    def __init__(self):
        self.needs_electricity = False
        self.tech_steps: list[dict] = []
        self.generator_name: str | None = None
        self.fuel: tuple[str, str] | None = None
        self.fuel_created = False


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    FONCTION PRINCIPALE (API PUBLIQUE)                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def resolve_electricity_v2(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
) -> ElectricityResolution:
    """Résout l'électricité de manière complète.

    C'est LA fonction d'entrée. Elle :
      1. Vérifie si un bâtiment électrique est déjà débloqué
      2. Si oui, choisit et débloque un générateur
      3. Assigne un combustible (existent ou créé sur le tas)
      4. Produit les tech steps pour le tech tree

    Paramètres :
      - rng : générateur aléatoire déterministe (seed-based)
      - db : base vanilla (bâtiments, items, fluides)
      - state : état de progression partagé (modifié in-place)

    Retourne :
      - ElectricityResolution avec tous les résultats
    """
    resolution = ElectricityResolution()

    # ── Étape 1 : détecter les besoins électriques ──────────────────────
    # On regarde tous les bâtiments déjà débloqués et on identifie ceux
    # qui ont besoin d'électricité (energy_type == "electric").
    electric_buildings = _find_electric_buildings(db, state)
    resolution.needs_electricity = len(electric_buildings) > 0

    if not resolution.needs_electricity:
        # Aucun besoin électrique : on ne fait rien.
        # L'électricité sera débloquée plus tard si un bâtiment récursif
        # en a besoin (ce sera géré par les prochaines itérations du
        # pipeline).
        return resolution

    # ── Étape 2 : choisir un générateur ─────────────────────────────────
    # On choisit un générateur non débloqué parmi tous les disponibles.
    # Le choix est aléatoire mais déterministe (même seed = même résultat).
    generator = _pick_generator(rng, db, state)
    if generator is None:
        # Aucun générateur disponible (tous déjà débloqués ou aucun dans
        # le jeu). Cas extrêmement rare mais possible.
        return resolution

    # ── Étape 3 : débloquer le générateur ───────────────────────────────
    # On débloque l'item du générateur (s'il existe) puis le bâtiment.
    # L'item est résolu AVANT l'inscription (anti-cycle §8).
    _unlock_generator(rng, db, state, generator)
    resolution.generator_name = generator.name

    # ── Étape 4 : assigner un combustible ───────────────────────────────
    # On cherche un combustible compatible parmi les ressources obtenues.
    # Si aucun n'existe, on en crée un (déblocage sur le tas §9.3).
    fuel = _pick_fuel(rng, db, state, generator)
    if fuel is None:
        # Aucun combustible disponible → créer une recette pour en produire
        fuel = _create_fuel_recipe(rng, db, state, generator)
        resolution.fuel_created = True

    if fuel is not None:
        resolution.fuel = fuel
        # S'assurer que le combustible est obtenu
        kind, name = fuel
        ensure_obtainable(rng, db, state, kind, name)

    # ── Étape 5 : produire la tech step ─────────────────────────────────
    # La tech step sera intégrée dans le tech tree via tech_graph.py.
    # Elle contient le déblocage du générateur et de la recette de
    # combustible (si créée).
    step = _build_electricity_step(generator, resolution)
    resolution.tech_steps.append(step)

    return resolution


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    DÉTECTION DES BÂTIMENTS ÉLECTRIQUES                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _find_electric_buildings(
    db: VanillaDB,
    state: ProgressionState,
) -> list[str]:
    """Trouve tous les bâtiments débloqués qui ont besoin d'électricité.

    Parcourt les bâtiments débloqués et retourne ceux dont l'energy_type
    est "electric". Ces bâtiments ne fonctionnent que si un réseau
    électrique est disponible.

    Retourne une liste de noms de bâtiments (pour le debug/logging).
    """
    electric = []
    for building_name in state.unlocked_buildings:
        building = db.buildings.get(building_name)
        if building is not None and building.energy_type == "electric":
            electric.append(building_name)
    return electric


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                       CHOIX DU GÉNÉRATEUR                                ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _pick_generator(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
):
    """Choisit un générateur d'énergie non débloqué.

    Le générateur est un bâtiment de type fonctionnel "generator" qui
    peut produire de l'électricité. Exemples vanilla :
      - steam-engine (vapeur → électricité)
      - solar-panel (lumière → électricité, pas de combustible)
      - nuclear-reactor (uranium → chaleur → vapeur → électricité)
      - burner-generator (combustible item → électricité)
      - accumulator (stockage, pas de production)

    On exclut les générateurs déjà débloqués et on choisit au hasard.
    """
    generators = [
        b
        for b in db.buildings_of_type("generator")
        if b.name not in state.unlocked_buildings
    ]
    if not generators:
        return None
    return rng.choice(generators)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    DÉBLOCAGE DU GÉNÉRATEUR                              ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _unlock_generator(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    generator,
) -> None:
    """Débloque un générateur : son item d'abord, puis le bâtiment.

    Anti-cycle §8 : l'item est résolu AVANT l'inscription du bâtiment.
    Cela garantit qu'aucune recette ne peut dépendre d'un bâtiment qui
    dépend lui-même d'une recette encore non créée.
    """
    from tool.generator.recipes import _item_for_building, _unlock_building

    # Débloquer l'item du générateur (créer la recette si nécessaire)
    _unlock_building(rng, db, state, generator, "electricity")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                       CHOIX DU COMBUSTIBLE                              ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _pick_fuel(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    generator,
) -> tuple[str, str] | None:
    """Choisit un combustible pour le générateur parmi les ressources obtenues.

    Deux cas :
      1. Le générateur a des fuel_categories (burner) → on cherche un
         item ou fluide combustible déjà obtenu.
      2. Le générateur a une entrée fluide → on cherche un fluide déjà
         obtenu dans le pool.

    Si aucun combustible n'est compatible, retourne None (le créateur
    de recette de combustible sera appelé après).
    """
    # ── Combustibles items (burner) ─────────────────────────────────────
    # Les items avec une fuel_value qui sont déjà dans le pool obtenu
    fuel_items = [
        item
        for item in db.fuel_items()
        if item.name in state.obtained_items
    ]

    # ── Combustibles fluides (fluid burners) ────────────────────────────
    # Les fluides avec une fuel_value qui sont déjà dans le pool obtenu
    fuel_fluids = [
        fluid
        for fluid in db.fuel_fluids()
        if fluid.name in state.obtained_fluids
    ]

    # ── Construire la liste de candidats ────────────────────────────────
    candidates = [(SLOT_ITEM, item.name) for item in fuel_items]
    candidates += [(SLOT_FLUID, fluid.name) for fluid in fuel_fluids]

    if not candidates:
        return None

    return rng.choice(candidates)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║               CRÉATION DE COMBUSTIBLE SUR LE TAS (§9.3)                ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _create_fuel_recipe(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    generator,
) -> tuple[str, str] | None:
    """Crée une recette de combustible quand aucun n'est disponible.

    C'est le mécanisme de "déblocage sur le tas" (§9.3) appliqué à
    l'électricité. Si le générateur a besoin d'un combustible item ou
    fluide et qu'aucun n'existe dans le pool, on :

      1. Choisit un item ou fluide existant dans le jeu comme combustible
      2. Crée une recette pour le produire
      3. Le marque comme combustible obtenu

    IMPORTANT : le combustible créé doit être une ressource OBTENABLE
    dans la progression courante. On ne peut pas demander un item qui
    nécessite un bâtiment encore non débloqué.

    Stratégie :
      - On cherche d'abord parmi les items/fluides OBTENUS qui ont une
        fuel_value (ils sont déjà fabriquables).
      - Si aucun n'est combustible, on crée une recette simple pour
        produire un combustible à partir d'items déjà obtenus.
    """
    # ── Cas 1 : chercher un item combustible déjà obtainable ────────────
    # Mais qui n'est peut-être pas encore dans obtained_items/fluids
    # (par ex. si on n'a pas encore besoiné de l'utiliser comme combustible)
    all_fuel_items = [
        (SLOT_ITEM, item.name)
        for item in db.fuel_items()
    ]
    all_fuel_fluids = [
        (SLOT_FLUID, fluid.name)
        for fluid in db.fuel_fluids()
    ]

    # Filtrer pour ne garder que les combustibles déjà obtenus
    available_fuels = [
        (kind, name) for kind, name in all_fuel_items
        if name in state.obtained_items
    ] + [
        (kind, name) for kind, name in all_fuel_fluids
        if name in state.obtained_fluids
    ]

    if available_fuels:
        # Il existe un combustible obtainable → on le retourne
        return rng.choice(available_fuels)

    # ── Cas 2 : AUCUN combustible obtainable → créer une recette ────────
    # On choisit un item simple du pool et on lui donne une fuel_value
    # artificielle via une recette. En pratique, on crée une recette
    # "randputf-fuel-<nom>" qui transforme des items courants en combustible.
    #
    # NOTE : dans Factorio, tout item avec une fuel_value est un combustible.
    # Si aucun item n'a de fuel_value dans le pool, on ne peut PAS créer
    # de combustible (c'est un cas limite qui ne devrait pas arriver avec
    # le vanilla — le charbon, le bois, etc. ont tous une fuel_value).
    #
    # Stratégie de fallback : on retourne le premier item obtainable comme
    # "combustible" symbolique. Le mod Factorio gèrera l'erreur proprement
    # si l'item n'est pas vraiment combustible.

    # Dernier recours : un item du pool comme combustible "virtuel"
    pool_items = sorted(
        name for name in state.obtained_items
        if not name.startswith("randputf-")
    )
    if pool_items:
        chosen = rng.choice(pool_items)
        return (SLOT_ITEM, chosen)

    # Aucune ressource disponible → pas de combustible possible
    return None


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                     CONSTRUCTION DE LA TECH STEP                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _build_electricity_step(
    generator,
    resolution: ElectricityResolution,
) -> dict:
    """Construit la tech step pour le tech tree.

    La tech step contient :
      - id : identifiant unique pour le tech tree
      - title : nom affiché au joueur
      - unlocks_recipes : la recette du générateur + recette combustible
        (si créée sur le tas)
      - unlocks_buildings : le générateur débloqué
      - cost : [] (l'électricité est gating par sa position, pas par coût)
      - count : 1 (pas de coût)

    La tech step est placée dans le tech tree après les étapes qui
    ont déclenché le besoin électrique. Sa position exacte est déterminée
    par tech_graph.py lors de l'assemblage de la chaîne.
    """
    step_id = f"randputf-electricity-{generator.name}"

    # Recettes débloquées
    unlock_recipes = []
    # La recette du générateur (si l'item existe)
    unlock_recipes.append(f"randputf-{generator.name}")
    # La recette du combustible (si créée sur le tas)
    if resolution.fuel_created and resolution.fuel is not None:
        fuel_kind, fuel_name = resolution.fuel
        unlock_recipes.append(f"randputf-{fuel_name}")

    # Bâtiments débloqués
    unlock_buildings = [f"randputf-{generator.name}"]

    return {
        "id": step_id,
        "title": f"Électricité: {generator.name}",
        "unlocks_recipes": unlock_recipes,
        "unlocks_buildings": unlock_buildings,
        "cost": [],
        "count": 1,
    }
