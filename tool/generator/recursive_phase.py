"""Phase 3 : récursion pondérée (README §9).

Après le starter, la génération devient récursive. Le pool de ressources
obtenables s'élargit à chaque itération, permettant des recettes de plus en
plus complexes.

Architecture :
- expand_recursive() remplit un module-level _tech_steps (macro-steps pour
  le tech tree) et génère les recettes via les primitives partagées.
- state.recipes contient toutes les recettes (starter + récursif).
- _tech_steps contient les macro-steps tech tree (unlock-recipe, coût, etc.).
"""

from __future__ import annotations

import random

from tool.common.db import (
    ENVIRONMENTAL_ITEMS,
    POWER_POLES,
    SLOT_FLUID,
    SLOT_ITEM,
    TOOL_LIKE_ITEMS,
    VanillaDB,
    VEHICLE_GUNS,
)
from tool.generator.endgame_phase import ROCKET_CHAIN
from tool.generator.map_patches import Patch
from tool.generator.recipes import ProgressionState, ensure_obtainable, make_recipe
from tool.generator.starter_chain import StarterChain
from tool.prototypes.recursive import RecursiveConfig

_config = RecursiveConfig()

_tech_steps: list[dict] = []
_unlocked_science_packs: list[str] = []

# Ressources « brutes » de la seed courante (patches + environnement + fluides
# d'extraction eau/pétrole brut/vapeur, §3/§13). Recalculées au début de
# `expand_recursive` à partir des patches ; un science pack ne se craft JAMAIS
# avec l'une d'elles (interdites à la fois dans les ingrédients de sa recette
# et dans celles du balayage de couverture).
_raw_resources: frozenset[str] = frozenset()

# Assignation véhicule → armes montées distinctes (§7). Remplie au début du
# balayage de couverture (``_expand_content_coverage``) avec le flot RNG de
# la récursion ; exportée dans les données seed (``vehicle_armament``). La
# pool ne sert QU'à cette assignation : aucune recette/unlock n'est généré
# pour les armes montées (l'item source reste clean, §12.1 les clone).
_vehicle_armament: dict[str, list[str]] = {}

# La chaîne fusée (§14) a sa propre tech de fin d'arbre qui unlocke ses 3
# ingrédients : ils ne sont jamais des « produits » de la récursion (sinon
# doublon d'unlock entre une tech profonde et randputf-endgame-rocket).
_ROCKET_CHAIN_ITEM_NAMES = frozenset(ROCKET_CHAIN)

# Balayage de couverture complète : items jamais pris en charge par la
# récursion des catégories fonctionnelles (belts, inserters, chests,
# combinators, trains, modules...) doivent TOUS recevoir une recette
# randputf-* unlockée par une tech (« randomisation complète », §9.6).
# Sont exclus du balayage :
# - la chaîne fusée (le rocket-silo et ses 3 ingrédients appartiennent à la
#   phase endgame §14, sinon doublon d'unlock avec randputf-endgame-rocket) ;
# - les armes MONTÉES (VEHICLE_GUNS) : contenu mort sans leur véhicule (le
#   joueur ne peut pas les utiliser), elles attendent la randomisation des
#   véhicules (§7) ;
# - les items environnementaux (déjà obtenables via le bootstrap) et les
#   outils (blueprint, planners...) qui ne sont pas du contenu fabricable.
_ROCKET_CHAIN_SWEEP_EXCLUDED = _ROCKET_CHAIN_ITEM_NAMES | {"rocket-silo"}

def _roman_value(n: int) -> str:
    """Romanisation arbitraire (1..3999) pour le suffixe numérique d'un ID de
    tech. Factorio lit un nom finissant par `xxx-<nombre>` comme un palier
    d'une chaîne d'upgrade et exige des paliers contigus (ex. uranium-235 puis
    uranium-238 → niveaux 235,238 non contigus → erreur de chargement). Mettre
    la valeur en chiffres romains désactive ce parsing (§9.6)."""
    values = [
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
        (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
        (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
    ]
    out = []
    for value, glyph in values:
        while n >= value:
            out.append(glyph)
            n -= value
    return "".join(out)


def _tech_id(category: str, element_name: str) -> str:
    """ID de tech ne terminant jamais par un chiffre (Factorio exige des
    niveaux contigus pour les noms en `xxx-N` ; les suffixes numériques sont
    convertis en chiffres romains)."""
    base = f"randputf-{category}-{element_name}"
    suffix = base.rsplit("-", 1)[-1]
    if suffix.isdigit():
        return base[: -len(suffix) - 1] + "-" + _roman_value(int(suffix))
    return base


def set_config(config: dict) -> None:
    global _config
    _config = RecursiveConfig.from_config(config)


def expand_recursive(
    rng: random.Random,
    db: VanillaDB,
    patches: list[Patch],
    starter: StarterChain,
) -> None:
    global _tech_steps, _unlocked_science_packs, _raw_resources
    _tech_steps = []
    _unlocked_science_packs = []
    _raw_resources = db.raw_resources({p.resource for p in patches})
    state = starter.state
    buildings_unlocked = len(state.unlocked_buildings)
    iterations_since_new = 0
    max_iterations = _config.max_iterations

    # §13 : le PREMIER science pack est rendu craftable par le STARTER (façon
    # red-science vanilla, recette gratuite unlockée par starter-transformation).
    # Sans lui, les techs de buildings/armes n'auraient aucun coût à payer
    # (elles exigent toutes un pack). Les packs suivants se débloquent en
    # chaîne (chacun coûte le pack précédent), donc toute tech récursive a
    # toujours un pack déjà unlocké vers lequel pointer.
    _seed_first_science(rng, db, state, starter)

    for _ in range(max_iterations):
        # Cadence garantie des pylônes (§9.4) : 3 pôles verrouillés à des
        # positions espacées (early / +~20 / +~20). Les pôles AU-DELÀ de ces
        # jalons restent randomisés comme de simples items/bâtiments.
        if _ensure_pole_cadence(rng, db, state, len(_tech_steps)):
            iterations_since_new = 0
            continue

        available = _get_available_categories(db, state)
        if not available:
            break

        category = _weighted_category_choice(rng, available, buildings_unlocked)
        if category is None:
            break

        element = _pick_element(rng, db, state, category)
        if element is None:
            iterations_since_new += 1
            if iterations_since_new > _config.stall_threshold:
                break
            continue

        iterations_since_new = 0
        old_buildings = len(state.unlocked_buildings)
        old_recipes = len(state.recipes)

        _generate_for_element(rng, db, state, category, element)

        new_buildings = len(state.unlocked_buildings) - old_buildings
        new_recipes = len(state.recipes) - old_recipes
        if new_buildings > 0 or new_recipes > 0:
            buildings_unlocked = len(state.unlocked_buildings)

    # Phase 3bis : BALAYAGE de couverture complète (README §9.6, « randomisation
    # complète »). La récursion pondérée ci-dessus ne touche que les 4
    # catégories fonctionnelles + combat + science. Le reste du contenu
    # craftable (belts, inserters, chests, combinators, robots, trains,
    # modules, intermédiaires...) n'aurait sinon JAMAIS de recette : la boucle
    # s'arrête dès que ces catégories sont épuisées (~35 techs seulement).
    # Ce balayage garantit à CHAQUE item un craft randputf-* + une tech de
    # filière (packs déjà TOUS unlockés par la récursion précédente, donc les
    # coûts restent payable-production §13).
    _expand_content_coverage(rng, db, state)


def _coverage_items(db: VanillaDB, state: ProgressionState) -> list:
    """Items craftables RESTANTS après la récursion (balayage complet §9.6).

    Un item est « couvert » dès qu'une recette produit son nom — même s'il est
    déjà obtenable (patch au sol, §6 : un belt posé au sol ne retire pas le
    belt du pool craftable). Sont exclus du balayage : la chaîne fusée (phase
    endgame, sinon doublon d'unlock avec randputf-endgame-rocket), les armes
    MONTÉES-UNIQUEMENT (VEHICLE_GUNS : contenu mort sans véhicule, jamaise
    crafté — la seed les clone à la volée pour les monter, §12.1 ; les armes
    de poing de la pool restent, elles, de vrais items craftables),
    les ressources environnementales (récoltables à la main, jamais craftées)
    et les outils (non fabricables)."""
    excluded_guns = VEHICLE_GUNS
    return [
        i
        for i in db.beltable_items()
        if not _has_product_recipe(state, i.name)
        and i.name not in ENVIRONMENTAL_ITEMS
        and i.name not in _ROCKET_CHAIN_SWEEP_EXCLUDED
        and i.name not in excluded_guns
        and i.name not in TOOL_LIKE_ITEMS
    ]


def _has_product_recipe(state: ProgressionState, name: str) -> bool:
    """Une recette produit déjà ``name`` ? (vérifie par produit, pas par état
    obtenu : un item posé au sol n'a pas de recette du seul fait d'être
    obtainable.)"""
    return any(
        (r.get("results") or []) and r["results"][0]["type"] == SLOT_ITEM
        and r["results"][0]["name"] == name
        for r in state.recipes
    )


def _expand_content_coverage(rng: random.Random, db: VanillaDB, state: ProgressionState) -> None:
    """Assure une recette randputf-* + une tech à CHAQUE item restant.

    Ordre des items mélangé par la graine (chaque seed explore le contenu
    dans un ordre différent). Chaque item devient une tech « randputf-content-
    <item> » qui unlocke SA recette ; les ingrédients proviennent du pool
    obtenable courant (jamais d'ingrédient pas encore fabricable). Les techs
    arrivent APRÈS la récursion pondérée : les 7 science packs sont donc déjà
    unlockés et tout coût de pack est payable (§13)."""
    global _vehicle_armament
    _vehicle_armament = _assign_vehicle_weapons(rng)
    items = _coverage_items(db, state)
    rng.shuffle(items)
    for item in items:
        if _has_product_recipe(state, item.name):
            continue
        try:
            _generate_for_element(rng, db, state, "content", item)
        except ValueError:
            continue


def _assign_vehicle_weapons(rng: random.Random) -> dict[str, list[str]]:
    """Échantillonne les armes montées par véhicule armé (§7/§12.1).

    Chaque véhicule de ``armed_vehicles`` (config) reçoit ``roll_vehicle_slot_count``
    emplacements, tirés dans la pool ``vehicle_weapons`` (items gun, y compris
    non montés de base : ex. fusil à pompe). Avec remise : les ``n`` tirages se
    font dans la pool complète ; sans remise : dans un sous-échantillon sans
    doublon. Les doublons d'un véhicule sont ensuite éliminés. La pool ne sert
    QU'à l'assignation : aucune recette/unlock n'est généré pour ces armes.
    Consomme le flot RNG de la récursion : déterministe par graine."""
    pool = _config.vehicle_weapon_names
    out: dict[str, list[str]] = {}
    for vehicle in _config.armed_vehicles:
        n = _config.roll_vehicle_slot_count(rng)
        if _config.vehicle_slots_with_replacement:
            drawn = [rng.choice(pool) for _ in range(n)]
        else:
            drawn = rng.sample(pool, min(n, len(pool)))
        out[vehicle] = list(dict.fromkeys(drawn))
    return out


def vehicle_weapons_pool() -> list[str]:
    """Items d'armes montées de la pool (§7), ordre de config."""
    return _config.vehicle_weapon_names


def vehicle_range_scaling() -> dict[str, float]:
    """Scale de portée montée (§12.1) : ``base_size`` + ``scale`` de config,
    exportés dans la seed (``pools.vehicle_range_scaling``)."""
    return {
        "base_size": _config.vehicle_range_base_size,
        "scale": _config.vehicle_range_scale,
    }


def vehicle_armament() -> dict[str, list[str]]:
    """Assignation véhicule → armes distinctes de la graine courante (après
    ``_expand_content_coverage``). Exportée dans les données seed."""
    return {k: list(v) for k, v in _vehicle_armament.items()}


def _dispatch_vehicle_ammo(rng: random.Random, db: VanillaDB, state: ProgressionState, vehicle: str) -> list[dict]:
    """§12.1 : munitions des armes montées, dispatchées dans les 3 techs APRÈS
    celle du véhicule.

    Quand la tech du véhicule est créée, on vérifie si chaque munition de ses
    armes (par ``ammo_category``) a déjà une recette. Pour celles qui n'en ont
    pas encore (elles auraient été réparties au hasard, potentiellement DEEP
    après le véhicule), on crée leur recette IMMÉDIATEMENT et on revoit des
    steps DISPATCH isolés (≤ 3 = « les 3 tech suivantes ») qui seront placés
    JUSTE APRÈS la tech du véhicule : le joueur reçoit son véhicule avec ses
    munitions au labo dans la foulée. Les munitions déjà présentes (recette
    unlockée plus tôt / avec le véhicule) ne sont pas rejouées.
    Retourne les steps dispatch (à étendre APRÈS le step du véhicule)."""
    needed: list[str] = []
    seen: set[str] = set()
    for gun in _vehicle_armament.get(vehicle, []):
        gun_item = db.items.get(gun)
        category = gun_item.ammo_category if gun_item else ""
        if not category:
            continue
        for ammo in db.items.values():
            if ammo.is_ammo and ammo.ammo_category == category and ammo.name not in seen:
                seen.add(ammo.name)
                needed.append(ammo.name)
    missing = [a for a in needed if not _has_product_recipe(state, a)]
    if not missing:
        return []
    rng.shuffle(missing)
    buckets: list[list[str]] = [[] for _ in range(min(3, len(missing)))]
    for i, ammo in enumerate(missing):
        make_recipe(rng, db, state, SLOT_ITEM, ammo)
        buckets[i % len(buckets)].append(ammo)
    steps: list[dict] = []
    for bucket in buckets:
        if not bucket:
            continue
        steps.append({
            "id": _tech_id(f"ammo-{vehicle}", bucket[0]),
            "title": f"Ammo for {vehicle}: {', '.join(bucket)}",
            "unlocks_recipes": [f"randputf-{a}" for a in bucket],
            "unlocks_buildings": [],
            "cost": [{
                "type": "item",
                "name": rng.choice(_unlocked_science_packs),
                "amount": _config.roll_science_cost(rng),
            }],
            "count": 1,
            "isolate": True,
        })
    return steps


def _ensure_pole_cadence(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    steps_so_far: int,
) -> bool:
    """Force la présence de PYLÔNES RÉELS (poteaux électriques) à une cadence
    garantie.

    Seuls les vrais poteaux comptent (``POWER_POLES`` : small/medium/big +
    substation) — le beacon est une distribution mais pas un pylône et reste
    randomisé. Chaque jalon ``dist_marks`` exige un nombre croissant de
    poteaux déployés. Dès la TOUTE première itération récursive (step 0), si
    aucun vrai poteau n'est encore débloqué (cas électricité absente du
    bootstrap), on force le premier immédiatement — jamais de run sans pylône
    jouable pendant les 10 premières techs. Chaque poteau forcé tire un type
    DIFFÉRENT (jamais déjà déployé, via ``_pick_real_pole``).

    Retourne True si un poteau a été forcé (l'itération ne pioche alors pas de
    catégorie normale)."""
    needed = sum(1 for m in _config.dist_marks if steps_so_far >= m)
    needed = min(needed, _config.dist_guaranteed)
    if steps_so_far == 0:
        needed = max(needed, 1)
    if needed <= 0:
        return False
    n_poles = sum(
        1 for name in POWER_POLES if _has_product_recipe(state, name)
    )
    if n_poles >= needed:
        return False
    pole = _pick_real_pole(rng, db, state)
    if pole is None:
        return False
    _generate_for_element(rng, db, state, "distribution", pole)
    return True


def _pick_real_pole(
    rng: random.Random, db: VanillaDB, state: ProgressionState
):
    """Choisit un pylône RÉEL (poteau électrique) non encore débloqué — jamais
    le beacon (distribution sans transport de courant, §9.1/§10)."""
    candidates = [
        b
        for b in db.buildings_of_type("distribution")
        if b.name in POWER_POLES and b.name not in state.unlocked_buildings
    ]
    return rng.choice(candidates) if candidates else None


def _seed_first_science(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    starter: StarterChain,
) -> None:
    """Amore la filière de coût : enregistre le premier science pack (choisi et
    rendu craftable par le starter) comme source de coût des techs récursives.

    La recette de ce pack est déjà unlockée GRATUITEMENT par la tech
    starter-transformation ; ici on ne fait qu'initialiser la chaîne des
    packs disponibles pour les coûts (§13)."""
    name = starter.first_science_pack
    if not name:
        return
    if name not in _unlocked_science_packs:
        _unlocked_science_packs.append(name)


def steps() -> list[dict]:
    return _tech_steps


def recipes_to_seed() -> list[dict]:
    return []


def _get_available_categories(db: VanillaDB, state: ProgressionState) -> list[str]:
    available = []
    for cat in ("transformer", "extractor", "generator", "distribution"):
        if _has_undeployed_buildings(db, state, cat):
            available.append(cat)
    if _has_undeployed_weapons(db, state):
        available.append("combat")
    if _has_undeployed_science(db, state):
        available.append("science")
    return available


def _has_undeployed_buildings(
    db: VanillaDB, state: ProgressionState, functional_type: str
) -> bool:
    for b in db.buildings_of_type(functional_type):
        if b.name not in _config.excluded_buildings and b.name not in state.unlocked_buildings:
            return True
    return False


def _has_undeployed_weapons(db: VanillaDB, state: ProgressionState) -> bool:
    return any(
        i.is_handheld_gun
        and i.name not in state.obtained_items
        for i in db.items.values()
    )


def _has_undeployed_science(db: VanillaDB, state: ProgressionState) -> bool:
    return any(
        i.is_science_pack and i.name not in state.obtained_items for i in db.items.values()
    )


def _weighted_category_choice(
    rng: random.Random, categories: list[str], buildings_unlocked: int
) -> str | None:
    if not categories:
        return None
    weights = [
        _config.category_weights.get(cat, 10.0) * (1 + buildings_unlocked * _config.progressive_factor)
        for cat in categories
    ]
    return rng.choices(categories, weights=weights, k=1)[0]


def _pick_element(
    rng: random.Random, db: VanillaDB, state: ProgressionState, category: str
):
    if category in ("transformer", "extractor", "generator", "distribution"):
        candidates = [
            b for b in db.buildings_of_type(category)
            if b.name not in _config.excluded_buildings and b.name not in state.unlocked_buildings
        ]
        return rng.choice(candidates) if candidates else None
    elif category == "combat":
        candidates = sorted(
            (i for i in db.items.values()
             if i.is_handheld_gun
             and i.name not in state.obtained_items),
            key=lambda i: i.name,
        )
        return rng.choice(candidates) if candidates else None
    elif category == "science":
        candidates = sorted(
            (i for i in db.items.values() if i.is_science_pack and i.name not in state.obtained_items),
            key=lambda i: i.name,
        )
        return rng.choice(candidates) if candidates else None
    return None


def _generate_for_element(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    category: str,
    element,
) -> None:
    from tool.generator.recipes import _unlock_building, _item_for_building

    step_id = _tech_id(category, element.name)
    step_recipes = []
    step_buildings = []
    pending_dispatch: list[dict] = []
    step = {
        "id": step_id,
        "title": f"{category.title()}: {element.name}",
        "unlocks_recipes": [],
        "unlocks_buildings": [],
        "cost": [],
        "count": _config.roll_tech_count(rng),
    }

    if category in ("transformer", "extractor", "generator", "distribution"):
        building = element
        item = _item_for_building(db, building.name)
        handcraft = False
        if category == "generator":
            # Premier générateur électrique de la seed = craftable à la main
            # (§10) : s'il arrive APRÈS le starter qui n'a rien demandé en
            # électricité, il est LE générateur d'amorçage du réseau — jamais
            # un atelier électrique (assembling-machine-2...) requis pour le
            # fabriquer, sinon boucle bootstrap. Les suivants repassent en
            # normal (les assembleurs existent déjà à ce stade).
            handcraft = not any(
                b.name in state.unlocked_buildings
                for b in db.buildings_of_type("generator")
            )
        if item is not None:
            ensure_obtainable(
                rng, db, state, SLOT_ITEM, item.name, handcraft=handcraft
            )
            step_buildings.append(building.name)
        state.unlocked_buildings.add(building.name)

        num_recipes = _config.roll_recipes_count(rng)
        for _ in range(num_recipes):
            recipe = _make_recipe_for_building(rng, db, state, building)
            if recipe:
                step_recipes.append(recipe["name"])

    elif category == "combat":
        item = element
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name)
        step_recipes.append(f"randputf-{item.name}")

    elif category == "science":
        item = element
        # §13 : la recette d'un science pack est tirée SANS ressource brute
        # (patches, environnement, fluides d'extraction — infinis ou non) : le
        # pack se craft à partir d'intermédiaires, jamais de matière brute du sol.
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name, forbidden=_raw_resources)
        step_recipes.append(f"randputf-{item.name}")
        # Un nouveau science pack se débloque en consommation du pack
        # précédent (le premier, gratuit, vient de _seed_first_science) :
        # la filière est toujours payable production → consommation (§13).
        pack = rng.choice(_unlocked_science_packs)
        step["cost"] = [{"type": "item", "name": pack, "amount": _config.roll_science_cost(rng)}]
        _unlocked_science_packs.append(item.name)

    elif category == "content":
        # Balayage de couverture complète (§9.6) : item restant quelconque
        # (belt, inserter, chest, module, intermédiaire...). Sa recette
        # randputf-<item> est unlockée par cette tech ; le coût en pack suit
        # la règle commune ci-dessous (toujours un pack déjà unlocké).
        # `make_recipe` (et non ensure_obtainable) : un item déjà obtainable
        # comme patch au sol (§6) n'a PAS de recette — il doit quand même
        # devenir craftable pour que « tout » ait une recette (§10).
        item = element
        # Véhicule armé (§12.1) : on vérifie les munitions des armes montées ;
        # le dispatch (≤ 3 steps isolés) est étendu APRÈS la tech du véhicule
        # (« les 3 tech suivantes »), voir l'append en fin de fonction.
        pending_dispatch = (
            _dispatch_vehicle_ammo(rng, db, state, item.name)
            if item.name in _vehicle_armament
            else []
        )
        # Garde §13 : si un science pack (ex. posé au sol en patch) atteint le
        # balayage SANS recette (jamais pické par la branche science, déjà
        # obtainable), sa recette de secours est tirée sans ressource brute.
        recipe = make_recipe(
            rng, db, state, SLOT_ITEM, item.name,
            forbidden=_raw_resources if item.is_science_pack else frozenset(),
        )
        step_recipes.append(recipe["name"])

    # TOUTE tech récursive (buildings, armes, packs) paie un coût en science
    # pack. Grâce à _seed_first_science, _unlocked_science_packs est
    # toujours non vide ici : jamais de tech récursive gratuite (§13).
    if not step["cost"]:
        pack = rng.choice(_unlocked_science_packs)
        step["cost"] = [{"type": "item", "name": pack, "amount": _config.roll_science_cost(rng)}]

    step["unlocks_recipes"] = step_recipes
    step["unlocks_buildings"] = step_buildings
    _tech_steps.append(step)
    # Véhicule armé (§12.1) : les steps DISPATCH des munitions (≤ 3 isolés)
    # suivent IMMÉDIATEMENT la tech du véhicule (« les 3 tech suivantes »).
    _tech_steps.extend(pending_dispatch)


def _make_recipe_for_building(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
) -> dict | None:
    needs_fluid_out = building.fluid_outputs > 0
    product_kind = SLOT_FLUID if needs_fluid_out else SLOT_ITEM
    product_name = _pick_product(rng, db, state, product_kind)
    if product_name is None:
        return None
    try:
        recipe = make_recipe(rng, db, state, product_kind, product_name)
        return recipe
    except ValueError:
        return None


def _pick_product(
    rng: random.Random, db: VanillaDB, state: ProgressionState, kind: str
) -> str | None:
    already = {
        r["results"][0]["name"]
        for r in state.recipes
        if r["results"] and r["results"][0]["type"] == kind
    }
    if kind == SLOT_ITEM:
        candidates = sorted(
            (n for n in state.obtained_items
             if not n.startswith("randputf-")
             and n not in ENVIRONMENTAL_ITEMS
             and n not in already
             and not _is_building_item(db, n)
             and n not in _ROCKET_CHAIN_ITEM_NAMES),
        )
    else:
        candidates = sorted(n for n in state.obtained_fluids if n not in already)
    return rng.choice(candidates) if candidates else None


def _is_building_item(db: VanillaDB, name: str) -> bool:
    """Un item posable est produit par SON OWN recette de déploiement
    (randputf-<bâtiment>), jamais comme produit générique d'un autre bâtiment :
    chaque recette de bâtiment reste ainsi unlockée par sa propre tech
    (pas de doublon d'unlock, §13)."""
    item = db.items.get(name)
    return item is not None and item.place_result is not None
