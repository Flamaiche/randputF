"""Phase 3 : récursion pondérée (§9). Pool de ressources s'élargit à chaque itération.

- expand_recursive() remplit _tech_steps (macro-steps pour le tech tree).
- state.recipes = toutes les recettes (starter + récursif).
"""

from __future__ import annotations

import random

from tool.common.db import (
    ROCKET_CHAIN,
    SLOT_FLUID,
    SLOT_ITEM,
    VanillaDB,
    VEHICLE_GUNS,
    is_fixed_fluid_crafter,
)
from tool.generator.heat import find_heat_roles
from tool.generator.map_patches import Patch
from tool.generator.recipes import (
    ProgressionState,
    _bake_recipe,
    _is_fixed_recipe_transformer,
    _item_for_building,
    _recipe_category,
    _sample_items_weighed,
    ensure_obtainable,
    make_recipe,
)
from tool.generator.starter_chain import StarterChain
from tool.prototypes.recursive import RecursiveConfig

_config = RecursiveConfig()

_tech_steps: list[dict] = []
_unlocked_science_packs: list[str] = []

# C7 soft-pity (fabricateurs à recette fixe, boiler/heat-exchanger) : un
# « event fluide » (tech introduisant ≥ 1 fluide non couvert) a 50 % de chance
# de placer UN fabricateur fixe ; s'il échoue, le prochain event est garanti
# (pity = 1). Réarmé dans ``expand_recursive``.
_fluid_pity: int = 0

# Steps ayant introduit un fluide (pour le flush final des fabricateurs restés
# non placés). Réarmé dans ``expand_recursive``.
_fluid_steps: list[tuple[dict, list[str]]] = []

# Chaleur (§10bis) : les prérequis heat ne sont émis qu'une fois par seed.
# Réarmé dans ``expand_recursive``.
_heat_prereq_emitted: bool = False

# Ressources brutes de la seed (patches + environnement + fluides d'extraction,
# §3/§13). Un science pack ne se craft jamais avec l'une d'elles.
_raw_resources: frozenset[str] = frozenset()

# Assignation véhicule → armes montées distinctes (§7), remplie au début du
# balayage de couverture ; exportée dans ``vehicle_armament``. La pool ne sert
# qu'à cette assignation (les armes montées n'ont ni recette ni unlock).
_vehicle_armament: dict[str, list[str]] = {}

# Chaîne fusée (§14) : unlockée par sa propre tech de fin d'arbre, jamais par
# la récursion (sinon doublon d'unlock avec randputf-endgame-rocket).
_ROCKET_CHAIN_ITEM_NAMES = frozenset(ROCKET_CHAIN)

# Balayage de couverture complète (§9.6) : items hors catégories fonctionnelles
# (belts, inserters, chests, combinators...) → recette randputf-* + tech.
# Exclus : chaîne fusée (endgame §14), armes montées (mortes sans véhicule,
# randomisées en §7), environnementaux et outils.
_ROCKET_CHAIN_SWEEP_EXCLUDED = _ROCKET_CHAIN_ITEM_NAMES | {"rocket-silo"}

def _roman_value(n: int) -> str:
    """Romanisation d'un suffixe numérique d'ID de tech : Factorio exige des
    paliers contigus pour les noms en `xxx-N` (erreur de chargement sinon,
    §9.6)."""
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
    lake_resources: frozenset[str] = frozenset(),
) -> None:
    global _tech_steps, _unlocked_science_packs, _raw_resources
    global _heat_prereq_emitted, _fluid_pity, _fluid_steps
    _tech_steps = []
    _heat_prereq_emitted = False
    _fluid_pity = 0
    _fluid_steps = []
    _unlocked_science_packs = []
    _raw_resources = db.raw_resources({p.resource for p in patches}) | frozenset(lake_resources)
    state = starter.state
    # Les LACS sont des fluides obtenables dès le départ (pompe offshore,
    # volume infini), comme les patchs : à marquer dans ``obtained_fluids``,
    # sinon les fabricateurs à recette fixe choisiraient des inputs inobtenables.
    for fluid in lake_resources:
        state.mark_obtained(SLOT_FLUID, fluid)
    buildings_unlocked = len(state.unlocked_buildings)
    iterations_since_new = 0
    max_iterations = _config.max_iterations

    # §13 : le premier science pack est rendu craftable par le starter (recette
    # gratuite unlockée par starter-transformation) ; sans lui aucune tech n'a
    # de coût. Les suivants se débloquent en chaîne (chacun coûte le précédent).
    _seed_first_science(rng, db, state, starter)

    for _ in range(max_iterations):
        # Cadence des pylônes (§9.4) : 3 pôles à des jalons espacés (~20 steps) ;
        # au-delà ils sont randomisés comme de simples items/bâtiments.
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

    # Balayage de couverture complète (§9.6, « randomisation complète ») : la
    # récursion pondérée ne touche que 4 catégories + combat + science ; ce
    # balayage garantit à chaque item restant un craft randputf-* + une tech
    # de filière (packs déjà tous unlockés, coûts payables §13).
    _expand_content_coverage(rng, db, state)

    # Flush final (C7) : fabricateurs fixes jamais placés par le soft-pity →
    # collés aléatoirement sur une tech à fluide, avec leur recette fixe.
    _flush_leftover_fluid_crafters(rng, db, state)


def _coverage_items(db: VanillaDB, state: ProgressionState) -> list:
    """Items craftables restant après la récursion (balayage complet §9.6).

    Un item est « couvert » dès qu'une recette produit son nom (même déjà
    obtenable en patch). Exclus : chaîne fusée (endgame), armes montées
    (VEHICLE_GUNS, jamais craftées — la seed les clone à la volée, §12.1),
    ressources environnementales et outils."""
    excluded_guns = VEHICLE_GUNS
    return [
        i
        for i in db.beltable_items()
        if not _has_product_recipe(state, i.name)
        and not i.is_environmental
        and i.name not in _ROCKET_CHAIN_SWEEP_EXCLUDED
        and i.name not in excluded_guns
        and not i.is_virtual_item
    ]


def _has_product_recipe(state: ProgressionState, name: str) -> bool:
    """Une recette produit déjà ``name`` ? (via le produit, pas l'état obtenu.)"""
    return any(
        (r.get("results") or []) and r["results"][0]["type"] == SLOT_ITEM
        and r["results"][0]["name"] == name
        for r in state.recipes
    )


def _is_network_dependent_item(db: VanillaDB, item) -> bool:
    """Item dont le bâtiment posé dépend du RÉSEAU (current ou circuits) :
    tourelle laser, radar, combinators, lampe. Placé en tier tardif du
    balayage §9.6 — jamais avant l'acquisition du réseau."""
    if not item.place_result:
        return False
    building = db.buildings.get(item.place_result)
    if building is None:
        return False
    return (
        building.is_laser_turret
        or building.is_radar
        or building.is_circuit_io
        or building.is_rgb_lamp
    )


def _expand_content_coverage(rng: random.Random, db: VanillaDB, state: ProgressionState) -> None:
    """Assure une recette randputf-* + une tech à chaque item restant.

    Items mélangés par la graine ; chaque item devient une tech
    « randputf-content-<item> » aux ingrédients du pool obtenable courant
    (jamais d'ingrédient non fabricable). Les techs arrivent après la
    récursion : les packs sont déjà tous unlockés (§13). Les items dépendant
    du réseau (laser, radar, combinator, lampe) sont différés après le contenu
    passif (§7/§8)."""
    global _vehicle_armament
    _vehicle_armament = _assign_vehicle_weapons(rng)
    items = _coverage_items(db, state)
    rng.shuffle(items)
    deferred = []
    main = []
    for i in items:
        (deferred if _is_network_dependent_item(db, i) else main).append(i)
    for item in main + deferred:
        if _has_product_recipe(state, item.name):
            continue
        try:
            _generate_for_element(rng, db, state, "content", item)
        except ValueError:
            continue


def _assign_vehicle_weapons(rng: random.Random) -> dict[str, list[str]]:
    """Armes montées par véhicule armé (§7/§12.1).

    Chaque ``armed_vehicles`` reçoit ``roll_vehicle_slot_count`` emplacements
    tirés dans ``vehicle_weapons`` (avec ou sans remise selon config). La pool
    ne sert qu'à l'assignation : aucune recette/unlock n'est généré pour ces
    armes. Consomme le flot RNG de la récursion (déterministe par graine)."""
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
    """§12.1 : munitions des armes montées, créées sur le tas et dispatchées
    (≤ 3 steps isolés) juste après la tech du véhicule.

    Pour chaque munition d'une arme du véhicule sans recette encore, on crée
    la recette immédiatement et on retourne des steps DISPATCH isolés placés
    après la tech du véhicule : le joueur reçoit véhicule + munitions à la
    suite. Les munitions déjà unlockées ne sont pas rejouées."""
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


def _dispatch_companions(rng: random.Random, db: VanillaDB, state: ProgressionState, item_name: str) -> list[dict]:
    """C3 : « companion guarantee » — recettes créées sur le tas + dispatch.

    Un compagnon est une ressource sans laquelle le produit déployé est du
    contenu mort (robot↔roboport, solaire→accumulateur, §10). On crée la
    recette de chaque membre du groupe sans recette et on retourne des steps
    DISPATCH isolés (≤ 3) suivant la tech du produit. Membres déjà craftables
    non rejoués."""
    group = _config.companion_group_for(item_name)
    if not group:
        return []
    missing = [m for m in group if m != item_name and not _has_product_recipe(state, m)]
    if not missing:
        return []
    rng.shuffle(missing)
    buckets: list[list[str]] = [[] for _ in range(min(3, len(missing)))]
    for i, m in enumerate(missing):
        make_recipe(rng, db, state, SLOT_ITEM, m)
        buckets[i % len(buckets)].append(m)
    steps: list[dict] = []
    for bucket in buckets:
        if not bucket:
            continue
        steps.append({
            "id": _tech_id(f"companion-{item_name}", bucket[0]),
            "title": f"Companions of {item_name}: {', '.join(bucket)}",
            "unlocks_recipes": [f"randputf-{m}" for m in bucket],
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


def _ensure_handheld_ammo(
    rng: random.Random, db: VanillaDB, state: ProgressionState, gun
) -> list[str]:
    """Garantit une munition à une arme de poing débloquée par une tech combat
    (§11) : si la catégorie de l'arme n'a aucune munition craftée, on génère
    UNE seule munition aléatoire parmi celles restantes dans la MÊME tech
    (sinon arme inutilisable) ; sinon rien."""
    category = gun.ammo_category if gun is not None else ""
    if not category:
        return []
    ammos = [
        a.name for a in db.items.values()
        if a.is_ammo and a.ammo_category == category
    ]
    if not ammos:
        return []
    missing = [a for a in ammos if not _has_product_recipe(state, a)]
    if not missing:
        return []
    pick = rng.choice(missing)
    make_recipe(rng, db, state, SLOT_ITEM, pick)
    return [f"randputf-{pick}"]


def _ensure_heat_prereq(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
) -> None:
    """Modèle « chaleur » (§10bis) : garantit SOURCE + TRANSPORT avant le sink.

    Un heat sink (heat-exchanger) ne fonctionne qu'avec une source
    (nuclear-reactor) reliée par un transport (heat-pipe). Au premier sink qui
    reçoit sa recette, on déploie les éléments manquants (source puis
    transport) dans des steps antérieurs au consommateur. Une seule émission
    par seed (``_heat_prereq_emitted``)."""
    global _heat_prereq_emitted
    if _heat_prereq_emitted:
        return
    _heat_prereq_emitted = True
    roles = find_heat_roles(db)
    if not roles["sinks"]:
        return
    if not roles["sources"] or not roles["transports"]:
        return
    # Déploie seulement ce qui manque : un élément déjà débloqué est déjà
    # antérieur au sink ; on force l'absent pour que la triade soit en place.
    missing_sources = [n for n in roles["sources"] if n not in state.unlocked_buildings]
    missing_transports = [n for n in roles["transports"] if n not in state.unlocked_buildings]
    needed = []
    if missing_sources:
        needed.append(rng.choice(missing_sources))
    if missing_transports:
        needed.append(rng.choice(missing_transports))
    for name in needed:
        building = db.buildings[name]
        # Catégorie de déploiement du bâtiment (comme la récursion) ; un
        # bâtiment sans rôle fonctionnel (heat-pipe) part en content (item).
        if building.is_generator:
            cat, element = "generator", building
        elif building.is_crafter:
            cat, element = "transformer", building
        elif building.is_extractor:
            cat, element = "extractor", building
        elif building.is_distribution:
            cat, element = "distribution", building
        else:
            cat, element = "content", db.items.get(name)
            if element is None:
                continue
        try:
            _generate_for_element(rng, db, state, cat, element, isolate=True)
        except ValueError:
            # Panel intenable (pool vide, boucle) : on laisse le consommateur
            # tel quel — le validateur signalerait l'ordre si la chaîne bifidait.
            continue
        state.unlocked_buildings.add(name)


def _ensure_pole_cadence(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    steps_so_far: int,
) -> bool:
    """Force des pylônes réels (small/medium/big + substation, jamais le
    beacon) à une cadence garantie : chaque jalon ``dist_marks`` exige
    ``dist_guaranteed`` pôles au plus ; à la première itération on force un
    pôle si aucun n'est débloqué. Chaque pôle forcé est d'un type différent
    (``_pick_real_pole``).

    Retourne True si un poteau a été forcé (pas de tirage normal ce tour)."""
    needed = sum(1 for m in _config.dist_marks if steps_so_far >= m)
    needed = min(needed, _config.dist_guaranteed)
    if steps_so_far == 0:
        needed = max(needed, 1)
    if needed <= 0:
        return False
    n_poles = sum(
        1 for b in db.buildings_with_tag("is_power_pole") if _has_product_recipe(state, b.name)
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
    """Choix d'un pylône réel (poteau électrique) non débloqué, jamais le
    beacon (distribution sans transport de courant, §9.1/§10)."""
    candidates = [
        b
        for b in db.buildings_with_tag("is_distribution")
        if b.is_power_pole and b.name not in state.unlocked_buildings
    ]
    return rng.choice(candidates) if candidates else None


def _seed_first_science(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    starter: StarterChain,
) -> None:
    """Amore la filière de coût : enregistre le premier science pack (choisi
    et rendu craftable par le starter) comme source de coût des techs (§13)."""
    name = starter.first_science_pack
    if not name:
        # Aucun pack seedé par le starter : on en prend un du jeu pour amorcer
        # la filière (toute tech récursive exige un coût, §13 ; `rng.choice`
        # sur liste vide planterait). Il aura une recette au balayage §9.6.
        packs = sorted(
            (i.name for i in db.items.values()
             if i.is_science_pack and i.name not in _unlocked_science_packs),
            key=lambda n: n,
        )
        if packs:
            name = rng.choice(packs)
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


# Catégories de la phase récursive (§9) choisies par TAGS : un bâtiment
# multi-tags est éligible dans chaque catégorie qu'il porte ; son deployment
# le retire des autres via ``state.unlocked_buildings``.
_CATEGORY_TAGS = {
    "transformer": "is_crafter",
    "extractor": "is_extractor",
    "generator": "is_generator",
    "distribution": "is_distribution",
}


def _has_undeployed_buildings(
    db: VanillaDB, state: ProgressionState, category: str
) -> bool:
    tag = _CATEGORY_TAGS[category]
    for b in db.buildings_with_tag(tag):
        if b.name not in _config.excluded_buildings and b.name not in state.unlocked_buildings:
            # Un bâtiment sans item (character...) n'a aucun produit à unlock.
            if _item_for_building(db, b.name) is not None:
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
            b for b in db.buildings_with_tag(_CATEGORY_TAGS[category])
            if b.name not in _config.excluded_buildings and b.name not in state.unlocked_buildings
            and _item_for_building(db, b.name) is not None
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
    isolate: bool = False,
) -> None:
    from tool.generator.recipes import _unlock_building, _item_for_building

    # Modèle « chaleur » (§10bis) : le bâtiment en cours de déploiement est un
    # sink → on débloque d'abord source + transport, avant le snapshot
    # ``buildings_before`` pour qu'ils ne soient pas ré-claimés par cette tech.
    if (
        category in ("transformer", "extractor", "generator", "distribution")
        and getattr(element, "is_heat_sink", False)
    ):
        _ensure_heat_prereq(rng, db, state)

    step_id = _tech_id(category, element.name)
    step_recipes = []
    step_buildings = []
    pending_dispatch: list[dict] = []
    # Fluides obtenus AVANT cet élément : pour détecter un fluide introduit par
    # ce step et lui associer un fabricateur à recette fixe (C7) au même niveau.
    fluids_before = set(state.obtained_fluids)
    # Ateliers débloqués « sur le tas » pendant cet élément : leur recette
    # randputf-<bâtiment> doit être claimée par cette tech (sinon orpheline).
    buildings_before = set(state.unlocked_buildings)
    step = {
        "id": step_id,
        "title": f"{category.title()}: {element.name}",
        "unlocks_recipes": [],
        "unlocks_buildings": [],
        "cost": [],
        "count": _config.roll_tech_count(rng),
    }
    if isolate:
        # Tech dédiée (jamais fusionnée) : utilisée par les prérequis de la
        # chaîne heat (§10bis).
        step["isolate"] = True

    if category in ("transformer", "extractor", "generator", "distribution"):
        building = element
        item = _item_for_building(db, building.name)
        handcraft = False
        if category == "generator":
            # Premier générateur électrique = craftable à la main (§10) : s'il
            # arrive après un starter sans électricité, il amorce le réseau
            # (jamais un atelier électrique requis pour le fabriquer, sinon
            # boucle). Seuls les producteurs de courant comptent (chaleur
            # seule, ex. réacteur, ne démarre pas le réseau).
            handcraft = not any(
                b.name in state.unlocked_buildings
                for b in db.buildings.values()
                if getattr(b, "produces_electricity", False)
            )
        if item is not None:
            ensure_obtainable(
                rng, db, state, SLOT_ITEM, item.name, handcraft=handcraft
            )
            step_buildings.append(building.name)
            # C3 : un bâtiment peut être un « compagnon produisant » — ex.
            # solar-panel (générateur) sans accumulateur = blackout nocturne.
            pending_dispatch.extend(_dispatch_companions(rng, db, state, item.name))
        state.unlocked_buildings.add(building.name)

        # §6/§10 : un transformateur à RECETTE FIXE (boiler/heat-exchanger, ou
        # équivalent à sortie fluide OU item) héberge UNE recette unique
        # randomisée (« fluide → fluide » ou « item → item/fluide »).
        fixed = _is_fixed_recipe_transformer(building)
        num_recipes = 1 if fixed else _config.roll_recipes_count(rng)
        for _ in range(num_recipes):
            recipe = _make_recipe_for_building(
                rng, db, state, building, force_building=building if fixed else None
            )
            if recipe:
                step_recipes.append(recipe["name"])

    elif category == "combat":
        item = element
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name)
        step_recipes.append(f"randputf-{item.name}")
        # Munitions (§11) : si aucune munition de la catégorie n'est craftée,
        # on génère les manquantes dans la même tech (sinon arme inutilisable).
        step_recipes.extend(_ensure_handheld_ammo(rng, db, state, item))

    elif category == "science":
        item = element
        # §13 : recette d'un pack tirée SANS ressource brute (patches,
        # environnement, fluides d'extraction) : packs craftés d'intermédiaires.
        ensure_obtainable(rng, db, state, SLOT_ITEM, item.name, forbidden=_raw_resources)
        step_recipes.append(f"randputf-{item.name}")
        # Chaque nouveau pack coûte le pack précédent (filière payable
        # production → consommation, §13).
        pack = rng.choice(_unlocked_science_packs)
        step["cost"] = [{"type": "item", "name": pack, "amount": _config.roll_science_cost(rng)}]
        _unlocked_science_packs.append(item.name)

    elif category == "content":
        item = element
        # Véhicule armé (§12.1) : munitions des armes montées + compagnons
        # (robot↔roboport, solaire→accumulateur) dispatchées après cette tech.
        pending_dispatch = (
            _dispatch_vehicle_ammo(rng, db, state, item.name)
            if item.name in _vehicle_armament
            else []
        )
        pending_dispatch.extend(_dispatch_companions(rng, db, state, item.name))
        # Garde §13 : un pack posé au sol (patch) atteint le balayage sans
        # recette → recette de secours tirée sans ressource brute.
        recipe = make_recipe(
            rng, db, state, SLOT_ITEM, item.name,
            forbidden=_raw_resources if item.is_science_pack else frozenset(),
        )
        step_recipes.append(recipe["name"])

    # TOUTE tech récursive (buildings, armes, packs) paie un coût en science
    # pack (§13) : grâce à _seed_first_science, le pool n'est jamais vide ici.
    if not step["cost"]:
        pack = rng.choice(_unlocked_science_packs)
        step["cost"] = [{"type": "item", "name": pack, "amount": _config.roll_science_cost(rng)}]

    # Pairing « fluide introduit → fabricateur à recette fixe » (C7) : si ce
    # step a introduit un NOUVEAU fluide, on DÉBLOQUE AU PLUS un fabricateur
    # fixe (boiler/heat-exchanger) dont la recette PRODUIT X.
    # Soft-pity : premier event fluide = 50 % de placer un fabricateur ; s'il
    # échoue, le prochain event est GARANTI (pity 100 %). Un event ne place
    # AUCUN doublon : un fluide introduit au MÊME niveau par un fabricateur
    # fixe (ex. heat-exchanger → petroleum-gas) n'est pas éligible (assignation
    # = source de vérité) — un producteur fixe par fluide.
    fixed_outputs = {
        a["output"]
        for a in state.building_fluid_assignments.values()
        if a.get("output") is not None
    }
    new_fluids = sorted(
        f for f in state.obtained_fluids - fluids_before if f not in fixed_outputs
    )
    if new_fluids:
        # Seuls les fabricateurs à recette fluide peuvent produire X ; un
        # transformateur à sortie ITEM (``is_fixed_crafter``) en est exclu.
        pending = [
            b for b in db.buildings.values()
            if is_fixed_fluid_crafter(b) and b.name not in state.unlocked_buildings
        ]
        if pending:
            chance = 1.0 if _fluid_pity else 0.5
            if rng.random() < chance:
                rng.shuffle(pending)
                crafter = pending.pop()
                fluid_x = rng.choice(new_fluids)
                # Chaleur (§10bis) : ce fabricateur fixe est un heat SINK →
                # source et transport débloqués avant cette tech.
                if getattr(crafter, "is_heat_sink", False):
                    _ensure_heat_prereq(rng, db, state)
                try:
                    recipe = _make_fixed_recipe_for_crafter(
                        rng, db, state, crafter, output_fluid=fluid_x
                    )
                except ValueError:
                    # Panel intenable (pool vide, boucle) : event raté → garantie
                    # au prochain event.
                    _fluid_pity = 1
                else:
                    step_recipes.append(recipe["name"])
                    step_buildings.append(crafter.name)
                    state.unlocked_buildings.add(crafter.name)
                    _fluid_pity = 0
            else:
                # Tirage perdu : le prochain event est garanti.
                _fluid_pity = 1
        # Mémorise la tech pour le flush final (fabricateurs restés non placés).
        _fluid_steps.append((step, new_fluids))

    # Claim des ateliers débloqués « sur le tas » pendant cet élément : sans
    # quoi leur recette resterait orpheline (voir buildings_before). Dédup en
    # conservant l'ordre (bâtiment de l'élément d'abord, puis on-the-fly).
    for name in state.unlocked_buildings - buildings_before:
        if name not in step_buildings:
            step_buildings.append(name)

    step["unlocks_recipes"] = step_recipes
    step["unlocks_buildings"] = step_buildings
    _tech_steps.append(step)
    # Véhicule armé (§12.1) : steps DISPATCH des munitions (≤ 3 isolés) juste
    # après la tech du véhicule.
    _tech_steps.extend(pending_dispatch)


def _flush_leftover_fluid_crafters(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
) -> None:
    """C7 (flush final) : fabricateurs à recette fixe restés non placés par le
    soft-pity → placés aléatoirement dans une tech ayant introduit un fluide,
    avec une recette fixe. Output = fluide déjà obtenu, de préférence SANS
    producteur fixe (« un producteur par fluide »)."""
    leftover = [
        b for b in db.buildings.values()
        if is_fixed_fluid_crafter(b) and b.name not in state.unlocked_buildings
    ]
    if not leftover or not _fluid_steps:
        return
    produced = {
        a["output"]
        for a in state.building_fluid_assignments.values()
        if a.get("output") is not None
    }
    for crafter in leftover:
        # Chaleur (§10bis) : un fabricateur fixe heat SINK (heat-exchanger) a
        # besoin de source + transport avant sa tech.
        if getattr(crafter, "is_heat_sink", False):
            _ensure_heat_prereq(rng, db, state)
        candidates = sorted(f for f in state.obtained_fluids if f not in produced)
        if not candidates:
            candidates = sorted(state.obtained_fluids)
        rng.shuffle(candidates)
        for fluid_x in candidates:
            try:
                recipe = _make_fixed_recipe_for_crafter(
                    rng, db, state, crafter, output_fluid=fluid_x
                )
            except ValueError:
                continue
            step, _ = rng.choice(_fluid_steps)
            step.setdefault("unlocks_recipes", []).append(recipe["name"])
            step.setdefault("unlocks_buildings", []).append(crafter.name)
            state.unlocked_buildings.add(crafter.name)
            produced.add(fluid_x)
            break
        # Aucun fluide tenable (pool trop petit) → fabricateur absent de la
        # seed : acceptable, il servirait de doublon de toute façon.


def _make_recipe_for_building(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
    force_building=None,
) -> dict | None:
    needs_fluid_out = building.fluid_outputs > 0
    product_kind = SLOT_FLUID if needs_fluid_out else SLOT_ITEM

    # §6/§10 : fabricateur à RECETTE FIXE (boiler/heat-exchanger, ou équivalent
    # à sortie fluide OU item). Sa « recette » UNIQUE est randomisée par
    # ``_make_fixed_recipe_for_crafter`` ; la recette réelle gouverne
    # (assignation input/output enregistrée dans `building_fluid_assignments`).
    if _is_fixed_recipe_transformer(building):
        try:
            return _make_fixed_recipe_for_crafter(rng, db, state, building)
        except ValueError:
            return None

    product_name = _pick_product(rng, db, state, product_kind)
    if product_name is None:
        return None
    try:
        recipe = make_recipe(
            rng, db, state, product_kind, product_name, force_building=force_building
        )
        return recipe
    except ValueError:
        return None


def _make_fixed_recipe_for_crafter(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
    output_fluid: str | None = None,
    output_item: str | None = None,
) -> dict:
    """Recette UNIQUE d'un fabricateur à recette fixe (``is_fixed_crafter``) :
    la recette propre du bâtiment est remplacée par une recette solvable, portée
    par CE bâtiment.

    Deux branches selon la sortie :
    - **fluide** (boiler/heat-exchanger) : « fluide → fluide ». Output = fluide
      pipable PU (forcer l'utilité du fabricateur au déploiement), imposable via
      ``output_fluid`` (pairing C7). Input = fluide déjà obtenu ≠ output
      (amorçage, jamais en cycle §10).
    - **item** (transformateur d'un mod) : « item(/fluide) → item ». Output =
      item obtenable non encore produit (être LE producteur), imposable via
      ``output_item`` ; inputs = items déjà obtenus SANS ce fabricateur
      (anti-boucle).
    - **résidu** : réacteur nucléaire (``fuel_residues``) — output = résidu de
      combustion, inputs = items obtenus (anti-boucle : jamais l'output ni un
      item produit par ce bâtiment).

    Enregistre l'assignation {@input, @output} dans
    ``state.building_fluid_assignments`` (branche fluide) : le mod applique les
    filters sur CETTE recette, pas sur un tirage indépendant."""
    if getattr(building, "fluid_outputs", 0) > 0:
        return _make_fixed_fluid_recipe(rng, db, state, building, output_fluid)
    if output_fluid is not None:
        raise ValueError(
            f"output_fluid={output_fluid} imposé sur {building.name} sans "
            "sortie fluide (variante item)"
        )
    if getattr(building, "item_output_slots", 0) > 0:
        return _make_fixed_item_recipe(rng, db, state, building, output_item)
    residues = getattr(building, "fuel_residues", ()) or ()
    if residues:
        return _make_fixed_residue_recipe(rng, db, state, building)
    raise ValueError(
        f"{building.name} taggé is_fixed_crafter mais sans sortie fluide, "
        "ni sortie item, ni résidu de combustion (recevrait une recette impossible)"
    )


def _make_fixed_fluid_recipe(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
    output_fluid: str | None = None,
) -> dict:
    """Branche « fluide → fluide » (boiler/heat-exchanger). Voir l'appelant."""
    all_names = [f.name for f in db.pipable_fluids()]
    # Input : fluide déjà obtenu SANS ce fabricateur (anti-boucle §10), en
    # dernier recours tout fluide pipable.
    input_pool = sorted(set(state.obtained_fluids) & set(all_names)) or all_names
    if output_fluid is not None:
        input_pool = [f for f in input_pool if f != output_fluid]
        if not input_pool:
            input_pool = [f for f in all_names if f != output_fluid]
    if not input_pool:
        raise ValueError(f"aucun input ≠ {output_fluid} pour {building.name} (1 seul fluide pipable)")
    input_fluid = rng.choice(input_pool)

    # Output : tout fluide pipable ≠ input, de préférence non déjà produit par une
    # autre recette (le fabricateur = LE producteur du fluide).
    already_produced = {
        r["results"][0]["name"]
        for r in state.recipes
        if r["results"] and r["results"][0]["type"] == SLOT_FLUID
    }
    if output_fluid is None:
        output_candidates = [f for f in all_names if f != input_fluid and f not in already_produced]
        if not output_candidates:
            output_candidates = [f for f in all_names if f != input_fluid]
        output_fluid = rng.choice(output_candidates)

    # Recette « fluide → fluide » pilotée directement (jamais d'ingrédient item :
    # pas de slot item pour la recette, seulement du combustible — §6/§10). Nom
    # unique par fabricateur (pas de doublon de prototype dans le mod).
    recipe = _bake_recipe(
        rng, db, state, SLOT_FLUID, output_fluid,
        [(SLOT_FLUID, input_fluid)],
        recipe_name=f"randputf-{building.name}-{output_fluid}",
    )
    recipe["category"] = _recipe_category(building, True, True)
    recipe["crafted_in"] = building.name
    state.recipes.append(recipe)
    state.mark_obtained(SLOT_FLUID, output_fluid)

    # Assignation input/output dérivée de la recette (source unique de vérité) :
    # le filter du mod + le tooltip reflètent exactement la recette jouable.
    state.building_fluid_assignments[building.name] = {
        "input": input_fluid,
        "output": output_fluid,
    }
    return recipe


def _make_fixed_item_recipe(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
    output_item: str | None = None,
) -> dict:
    """Branche « (item/fluide) → item » (transformateur item du mod). Voir
    l'appelant."""
    if output_item is None:
        # Output : item obtenable non encore produit (être LE producteur) ;
        # hors items de bâtiment et chaîne fusée.
        already_produced = {
            r["results"][0]["name"]
            for r in state.recipes
            if r["results"] and r["results"][0]["type"] == SLOT_ITEM
        }
        candidates = sorted(
            n for n in state.obtained_items
            if n not in already_produced
            and not (db.items.get(n) is not None and db.items[n].is_environmental)
            and n not in _ROCKET_CHAIN_ITEM_NAMES
            and not n.startswith("randputf-")
            and not _is_building_item(db, n)
        )
        if not candidates:
            raise ValueError(
                f"aucun item de sortie pour le fabricateur fixe {building.name}"
            )
        output_item = rng.choice(candidates)
    elif not _is_recipe_output_item_plausible(db, state, output_item):
        raise ValueError(
            f"item imposé {output_item} non obtenable pour {building.name}"
        )

    # Inputs : items (et éventuellement un fluide) déjà obtenus SANS ce
    # fabricateur — amorçage, jamais de cycle solvable (§10). Limités par les
    # vrais slots du bâtiment (item_input_slots / fluid_inputs).
    item_pool = [
        (SLOT_ITEM, n) for n in sorted(state.obtained_items) if n != output_item
    ]
    max_ingredients = min(
        max(getattr(building, "item_input_slots", 1), 1),
        len(item_pool),
    )
    if max_ingredients <= 0:
        raise ValueError(
            f"aucun ingrédient item disponible pour {building.name} (item {output_item})"
        )
    n_item = rng.randint(1, max_ingredients)
    ingredients = _sample_items_weighed(rng, db, item_pool, n_item, state)
    fluid_ing = False
    if getattr(building, "fluid_inputs", 0) > 0 and state.obtained_fluids:
        # Un transformateur item qui accepte aussi un fluide : on ajoute un
        # ingrédient fluide obtenable quand la recette supporte des fluides.
        fluid_pool = [f for f in sorted(state.obtained_fluids)]
        ingredients.append((SLOT_FLUID, rng.choice(fluid_pool)))
        fluid_ing = True
    rng.shuffle(ingredients)

    recipe = _bake_recipe(
        rng, db, state, SLOT_ITEM, output_item, ingredients,
        recipe_name=f"randputf-{building.name}-{output_item}",
    )
    recipe["category"] = _recipe_category(building, fluid_ing, False)
    recipe["crafted_in"] = building.name
    state.recipes.append(recipe)
    state.mark_obtained(SLOT_ITEM, output_item)
    return recipe


def _make_fixed_residue_recipe(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
) -> dict:
    """Branche « item → item (résidu) » pour un combusteur à résidu
    (``fuel_residues``, ex. nuclear-reactor) : output = résidu de combustion
    (burnt_result). Inputs = items déjà obtenus SANS ce fabricateur, dont le
    pseudo-combustible (entrée d'un combusteur = un item quelconque, §6) ;
    au moins un ingrédient item. Anti-boucle : jamais l'output ni un item
    produit par ce bâtiment."""
    residues = list(getattr(building, "fuel_residues", ()) or ())
    if not residues:
        raise ValueError(f"{building.name} sans résidu de combustion (recette résidu impossible)")
    output_item = rng.choice(residues)

    if output_item in state.obtained_items:
        # Déjà obtenu : on choisit un autre résidu si possible (le réacteur
        # reste le producteur sinon).
        others = [r for r in residues if r not in state.obtained_items]
        if others:
            output_item = rng.choice(others)

    item_pool = [
        (SLOT_ITEM, n) for n in sorted(state.obtained_items) if n != output_item
    ]
    if not item_pool:
        raise ValueError(
            f"aucun ingrédient item disponible pour {building.name} (résidu {output_item})"
        )
    max_ingredients = min(max(getattr(building, "item_input_slots", 1), 1), len(item_pool))
    n_item = rng.randint(1, max_ingredients)
    ingredients = _sample_items_weighed(rng, db, item_pool, n_item, state)
    rng.shuffle(ingredients)

    recipe = _bake_recipe(
        rng, db, state, SLOT_ITEM, output_item, ingredients,
        recipe_name=f"randputf-{building.name}-{output_item}",
    )
    recipe["category"] = _recipe_category(building, False, False)
    recipe["crafted_in"] = building.name
    state.recipes.append(recipe)
    state.mark_obtained(SLOT_ITEM, output_item)
    return recipe


def _is_recipe_output_item_plausible(db: VanillaDB, state: ProgressionState, name: str) -> bool:
    """Output imposé plausible : item réel du pool, obtenable comme produit."""
    return name in db.items and name in state.obtained_items


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
             and not (db.items.get(n) is not None and db.items[n].is_environmental)
             and n not in already
             and not _is_building_item(db, n)
             and n not in _ROCKET_CHAIN_ITEM_NAMES),
        )
    else:
        candidates = sorted(n for n in state.obtained_fluids if n not in already)
    if not candidates:
        return None
    # C2 : côté production on préfère les produits rares (poids = 1 / facteur).
    state.ensure_balance_target(rng)
    weights = [1.0 / max(state.balance_factor(n), 1e-6) for n in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


def _is_building_item(db: VanillaDB, name: str) -> bool:
    """Un item posable est produit par sa propre recette de déploiement
    (randputf-<bâtiment>), jamais comme produit générique d'un autre bâtiment
    (pas de doublon d'unlock, §13)."""
    item = db.items.get(name)
    return item is not None and item.place_result is not None
