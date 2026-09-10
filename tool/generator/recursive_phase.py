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

# Modèle « chaleur » (§10bis) : garde à une seule émission des prérequis heat.
# Posé à True dès que la triade source+transport est débloquée (ou rien à
# faire : aucun sink dans le pool). Reseté dans ``expand_recursive``.
_heat_prereq_emitted: bool = False

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
    lake_resources: frozenset[str] = frozenset(),
) -> None:
    global _tech_steps, _unlocked_science_packs, _raw_resources, _heat_prereq_emitted
    _tech_steps = []
    _heat_prereq_emitted = False
    _unlocked_science_packs = []
    _raw_resources = db.raw_resources({p.resource for p in patches}) | frozenset(lake_resources)
    state = starter.state
    # C2/C5 : les LACS sont des fluides brut obtenables DÈS LE DÉPART (pompe
    # offshore, volume infini), comme les patchs. Il faut donc les marquer dans
    # ``state.obtained_fluids`` : sinon les fabricateurs à recette fixe
    # (boiler/heat-exchanger — ``_make_fixed_fluid_recipe``) choisiraient leur
    # input/output dans TOUS les fluides pipables y compris les inobtenables,
    # et le validateur signalerait « utilise X avant obtention » (progressivité)
    # + recettes en boucle. Les patchs fluides le sont déjà via
    # ``_ensure_extraction`` ; les lacs ne l'étaient pas (quirk pré-existant).
    for fluid in lake_resources:
        state.mark_obtained(SLOT_FLUID, fluid)
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
        and not i.is_environmental
        and i.name not in _ROCKET_CHAIN_SWEEP_EXCLUDED
        and i.name not in excluded_guns
        and not i.is_virtual_item
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


def _is_network_dependent_item(db: VanillaDB, item) -> bool:
    """Item dont le bâtiment posé (place_result) dépend du RÉSEAU (électrique
    ou circuits) : tourelle laser (consumes_electricity, tags §7), radar,
    combinators et lampe (tags §8). Ces usages sont placés dans un TIER TARDIF
    du balayage §9.6 — jamais avant que le réseau ne soit acquis : une tourelle
    balistique (ammo, sans courant) peut arriver tôt, une laser (courant) doit
    attendre la fin du balayage."""
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
    """Assure une recette randputf-* + une tech à CHAQUE item restant.

    Ordre des items mélangé par la graine (chaque seed explore le contenu
    dans un ordre différent). Chaque item devient une tech « randputf-content-
    <item> » qui unlocke SA recette ; les ingrédients proviennent du pool
    obtenable courant (jamais d'ingrédient pas encore fabricable). Les techs
    arrivent APRÈS la récursion pondérée : les 7 science packs sont donc déjà
    unlockés et tout coût de pack est payable (§13).

    Tier tardif (§7/§8) : les items dépendant du réseau (tourelle laser, radar,
    combinator, lampe) sont DEFERRÉS APRÈS tout le contenu « passif » — le
    balayage garde sa randomisation interne mais garantit qu'un usage à
    courant/network n'est jamais débloqué avant le reste."""
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


def _dispatch_companions(rng: random.Random, db: VanillaDB, state: ProgressionState, item_name: str) -> list[dict]:
    """C3 : « companion guarantee » — dispatch des items dépendants.

    Un item compagnon est une ressource sans laquelle le produit déployé est du
    contenu mort (façon `_dispatch_vehicle_ammo` §12.1) :
    - un robot (logistic/construction) sans roboport ne vole pas ;
    - un roboport sans robot ne sert à rien ;
    - un premier solaire sans accumulateur = blackout nocturne (§10).

    Quand ``item_name`` (déployé par une tech) appartient à un groupe compagnon
    (config), on crée IMMÉDIATEMENT la recette de chaque membre du groupe qui
    n'en a pas encore, et on retourne des steps DISPATCH isolés (≤ 3) qui
    suivent la tech du produit : le joueur reçoit le compagnon au labo dans la
    foulée. Les membres déjà craftables ne sont pas rejoués.

    Retourne les steps dispatch (à étendre APRÈS le step du produit)."""
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
    (§11).

    Règle : si AUCUNE munition de la catégorie de l'arme n'a encore de recette,
    on génère les munitions manquantes (déblocage sur le tas §9.3) et on les
    ajoute à la MÊME tech que l'arme — sinon une arme débloquée seule serait
    inutilisable (flamethrower sans flamethrower-ammo, etc.). Si au moins une
    munition de la catégorie est déjà débloquée, on ne force rien (l'arme a
    déjà de quoi tirer).
    Retourne les recettes randputf-<munition> à unlocked la même tech."""
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
    unlocked: list[str] = []
    for ammo in missing:
        make_recipe(rng, db, state, SLOT_ITEM, ammo)
        unlocked.append(f"randputf-{ammo}")
    return unlocked


def _ensure_heat_prereq(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
) -> None:
    """Modèle « chaleur » (§10bis) : garantit la TRIADE avant le consommateur.

    Un heat SINK (ex. heat-exchanger) ne fonctionne qu'avec une SOURCE (ex.
    nuclear-reactor) reliée par un TRANSPORT (ex. heat-pipe). Au premier
    instant où un sink va recevoir sa recette de craft, on DÉPLOIE d'abord —
    dans l'ordre SOURCE puis TRANSPORT — des steps de tech qui débloquent leur
    item/bâtiment : leurs unlock sont ainsi STRICTEMENT ANTÉRIEURS à ceux du
    consommateur (miroir de la garantie « extracteur avant besoin » du starter,
    §7). Le modèle est inerte sans sink dans le pool : aucune insertion.

    Une seule émission par seed (``_heat_prereq_emitted``) : le premier sink
    qui apparaît déclenche la garantie ; les suivants héritent de l'ordre.
    """
    global _heat_prereq_emitted
    if _heat_prereq_emitted:
        return
    _heat_prereq_emitted = True
    roles = find_heat_roles(db)
    if not roles["sinks"]:
        return
    if not roles["sources"] or not roles["transports"]:
        return
    # Déployer SÉPARÉMENT ce qui manque : une source déjà débloquée avant le
    # sink est déjà antérieure (son step est déjà dans l'arbre) ; on ne force
    # que l'élément absent (ex. le heat-pipe) pour que LA TRIADE soit en place
    # strictement avant le consommateur.
    missing_sources = [n for n in roles["sources"] if n not in state.unlocked_buildings]
    missing_transports = [n for n in roles["transports"] if n not in state.unlocked_buildings]
    needed = []
    if missing_sources:
        needed.append(rng.choice(missing_sources))
    if missing_transports:
        needed.append(rng.choice(missing_transports))
    for name in needed:
        building = db.buildings[name]
        # Catégorie de déploiement naturelle du bâtiment (comme la récursion) ;
        # un bâtiment sans rôle fonctionnel (heat-pipe) part en balayage-contenu
        # et déploie alors son ITEM (la branche content attend un ItemDef).
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
            # tel quel — robustesse identique au kit (§8), le validateur
            # signalerait l'ordre si la chaîne était bifide.
            continue
        state.unlocked_buildings.add(name)


def _ensure_pole_cadence(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    steps_so_far: int,
) -> bool:
    """Force la présence de PYLÔNES RÉELS (poteaux électriques) à une cadence
    garantie.

    Seuls les vrais poteaux comptent (``is_power_pole`` : small/medium/big +
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
    """Choisit un pylône RÉEL (poteau électrique) non encore débloqué — jamais
    le beacon (distribution sans transport de courant, §9.1/§10)."""
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
    """Amore la filière de coût : enregistre le premier science pack (choisi et
    rendu craftable par le starter) comme source de coût des techs récursives.

    La recette de ce pack est déjà unlockée GRATUITEMENT par la tech
    starter-transformation ; ici on ne fait qu'initialiser la chaîne des
    packs disponibles pour les coûts (§13)."""
    name = starter.first_science_pack
    if not name:
        # Le starter n'a pas pu seedé de pack (ex. pool déjà vidé de ses packs
        # non-obtenus). On amorce quand même la filière avec un pack du jeu :
        # toute tech récursive exige un coût (§13), et `rng.choice` sur une
        # liste vide planterait. Le pack choisi aura de toute façon une recette
        # (balayage de couverture §9.6).
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


# Les catégories de la phase récursive (§9) sont choisies par TAGS : un
# bâtiment multi-tags (ex. heat-exchanger is_crafter + is_generator) est
# éligible dans CHAQUE catégorie qu'il porte. Son deployment (dans une seule
# catégorie) le retire des autres via ``state.unlocked_buildings``.
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
            # Un bâtiment SANS ITEM (character...) ne peut être « déployé » :
            # aucun produit à unlock — un step de tech vide serait un bug.
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
    # CONSOMMATEUR de heat → on débloque d'abord sa SOURCE + son TRANSPORT, à
    # des techs STRICTEMENT ANTÉRIEURES. Placé AVANT le snapshot
    # ``buildings_before`` pour que source/transport ne soient pas ré-claimés
    # dans la tech du consommateur lui-même.
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
    # ce step et lui associer un fabricateur à recette fixe (IDEES C7) au même
    # niveau de recherche que ce liquide.
    fluids_before = set(state.obtained_fluids)
    # Ateliers débloqués AVANT cet élément : ceux qui le seront « sur le tas »
    # pendant sa génération (déblocage d'un atelier de craft via _pick_building
    # → _unlock_building, §9.3) produisent une recette randputf-<bâtiment> qui
    # doit être claimée par CETTE tech — sinon recette orpheline (jamais
    # unlockée). On les ajoute à `unlocks_buildings` en fin de traitement.
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
        # Tech DÉDIÉE (jamais fusionnée avec la suivante) : utilisée par les
        # prérequis de la chaîne heat (§10bis) pour garantir que source et
        # transport restent STRICTEMENT antérieurs au consommateur.
        step["isolate"] = True

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
            # normal (les assembleurs existent déjà à ce stade). Seuls les
            # producteurs de COURANT comptent (tag ``produces_electricity``) :
            # le réacteur (chaleur seule) ne démarre jamais le réseau.
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
        # tout équivalent de mod à sortie fluide OU item — ``is_fixed_crafter``)
        # héberge UNE recette unique entièrement randomisée (« fluide → fluide »
        # ou « item → item/fluide »), pas un atelier général multi-recettes. On
        # force EXACTEMENT une recette, portée par CE bâtiment
        # (voir _make_recipe_for_building).
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
        # Munitions (§11) : si AUCUNE munition de la catégorie de l'arme n'est
        # encore débloquée, on génère les manquantes avec l'arme, dans la MÊME
        # tech — sinon l'arme débloquée serait inutilisable. Si une munition est
        # déjà obtenable (avant ou à la même tech), on n'ajoute rien.
        step_recipes.extend(_ensure_handheld_ammo(rng, db, state, item))

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
        # C3 : same pour les compagnons (robot↔roboport, solaire→accumulateur).
        pending_dispatch = (
            _dispatch_vehicle_ammo(rng, db, state, item.name)
            if item.name in _vehicle_armament
            else []
        )
        pending_dispatch.extend(_dispatch_companions(rng, db, state, item.name))
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

    # §6/§10 + IDEES C7 : PAIRING « fluide introduit → fabricateur à recette
    # fixe ». Si ce step a introduit un NOUVEAU fluide X (nouveau lac/patch
    # fluide pris au pool, ou fluide produit par la recette de cet élément),
    # on force l'utilité des fabricateurs à recette fixe (boiler/heat-exchanger,
    # taggés ``is_fixed_fluid_crafter``) non encore déployés : on leur attribue
    # une recette qui PRODUIT X (output = X, input = tout fluide ≠ X) et on les
    # débloque au MÊME niveau de recherche que ce liquide. Source unique de
    # vérité : la recette (jamais un tirage arbitraire hors du solvables).
    new_fluids = sorted(state.obtained_fluids - fluids_before)
    if new_fluids:
        # Pairing « fluide » : SEULS les fabricateurs à recette fluide
        # (boiler/heat-exchanger) peuvent produire le fluide X ; un
        # transformateur à sortie ITEM (``is_fixed_crafter``) en est exclu.
        pending = [
            b for b in db.buildings.values()
            if is_fixed_fluid_crafter(b) and b.name not in state.unlocked_buildings
        ]
        rng.shuffle(pending)
        for fluid_x in new_fluids:
            if not pending:
                break
            crafter = pending.pop()
            # Modèle « chaleur » (§10bis) : ce fabricateur à recette fixe est
            # un heat SINK → sa SOURCE + son TRANSPORT doivent être débloqués
            # AVANT cette tech (les steps de prérequis sont insérés ici, avant
            # l'append du step courant en fin d'élément).
            if getattr(crafter, "is_heat_sink", False):
                _ensure_heat_prereq(rng, db, state)
            try:
                recipe = _make_fixed_recipe_for_crafter(
                    rng, db, state, crafter, output_fluid=fluid_x
                )
            except ValueError:
                continue
            step_recipes.append(recipe["name"])
            step_buildings.append(crafter.name)
            state.unlocked_buildings.add(crafter.name)
            # Assignation input/output déjà enregistrée par
            # _make_fixed_recipe_for_crafter (recette = source unique).

    # Claim des ateliers débloqués « sur le tas » pendant cet élément : sans
    # cela, leur recette randputf-<bâtiment> resterait orpheline (voir
    # buildings_before). Dédup en conservant l'ordre (le bâtiment de l'élément
    # d'abord, puis les on-the-fly).
    for name in state.unlocked_buildings - buildings_before:
        if name not in step_buildings:
            step_buildings.append(name)

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
    force_building=None,
) -> dict | None:
    needs_fluid_out = building.fluid_outputs > 0
    product_kind = SLOT_FLUID if needs_fluid_out else SLOT_ITEM

    # §6/§10 + IDEES C7 : FABRICATEUR À RECETTE FIXE (boiler/heat-exchanger,
    # et tout équivalent de mod à sortie fluide OU item — ``is_fixed_crafter``,
    # shim). Sa « recette » UNIQUE est entièrement randomisée par
    # ``_make_fixed_recipe_for_crafter`` : sortie fluide (output = un fluide
    # pipable ≠ input, input amorçable) ou sortie item (output = item obtenable
    # non encore produit, inputs déjà obtenus). La recette réelle gouverne — la
    # branche fluide enregistre l'assignation input/output dans
    # `state.building_fluid_assignments` (source unique).
    # Les générateurs/extracteurs/lab (soleil/combustible → électricité, champ
    # → ressource, packs → recherche) ne sont PAS taggés ``has_hidden_recipe``
    # (sortie non-item/fluide = mécanique moteur, pas une recette) →
    # comportement figé (jamais de fake crafted_in). Le nuclear-reactor, lui,
    # EST taggé (entrée item pseudo-combustible → sortie item résidu, §recette
    # cachée item→item) MAIS reste un générateur → il n'est pas un atelier et
    # ne reçoit aucune recette randomisée ici : seuls les transformateurs à
    # recette cachée (`is_fixed_crafter`) en reçoivent une.
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
    """Recette UNIQUE randomisée d'un fabricateur à recette FIXE (détection par
    capacités, ``is_fixed_crafter``) : la « recette propre » du bâtiment est
    remplacée par une recette de craft solvable, portée par CE bâtiment.

    Deux branches selon la sortie physique :
    - **Sortie fluide** (boiler/heat-exchanger) : recette « fluide → fluide ».
      Output = un fluide pipable PU (pas seulement les obtenus : c'est le rôle
      du fabricateur de le produire — on force son utilité à la sortie). S'il
      est imposé (pairing IDEES C7 : le fabricateur produit le fluide X tout
      juste débloqué), ``output_fluid`` le force. Input = un fluide déjà obtenu
      (lac/obtenu autrement) ≠ output, pour que le fabricateur soit amorçable
      (jamais en cycle §10).
    - **Sortie item** (transformateur item d'un mod) : recette « item(/fluide)
      → item ». Output = un item obtenable non encore produit par une autre
      recette (être LE producteur), inputs = items (et éventuellement un fluide
      si ``fluid_inputs > 0``) déjà obtenus SANS ce fabricateur (anti-boucle).
      ``output_item`` force l'output lorsqu'il est imposé par l'appelant.

    Enregistre l'assignation {@input, @output} dans
    ``state.building_fluid_assignments`` POUR LA BRANCHE FLUIDE (le mod
    n'applique les filters qu'aux fluid boxes) : la seed et le mod s'appuient
    sur CETTE recette, pas sur un tirage indépendant.
    """
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
    """Branche « fluide → fluide » de ``_make_fixed_recipe_for_crafter``
    (boiler/heat-exchanger). Voir la doc de l'appelant."""
    all_names = [f.name for f in db.pipable_fluids()]
    # Input : fluide déjà obtainable SANS ce fabricateur (anti-boucle §10) —
    # un lac/fluide obtenu. En dernier recours, tout fluide pipable.
    input_pool = sorted(set(state.obtained_fluids) & set(all_names)) or all_names
    if output_fluid is not None:
        input_pool = [f for f in input_pool if f != output_fluid]
        if not input_pool:
            input_pool = [f for f in all_names if f != output_fluid]
    if not input_pool:
        raise ValueError(f"aucun input ≠ {output_fluid} pour {building.name} (1 seul fluide pipable)")
    input_fluid = rng.choice(input_pool)

    # Output : tout fluide pipable ≠ input, de préférence NON déjà produit par
    # une autre recette (forcer l'utilité du fabricateur = être LE producteur
    # d'un fluide que personne ne produit encore).
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
    # un boiler/heat-exchanger n'a pas de slot item pour la recette, seulement
    # du combustible — §6/§10). Le fabricateur PORTE la recette (`crafted_in`).
    # Nom unique par fabricateur : deux fabricateurs peuvent produire le MÊME
    # fluide (pas de doublon de prototype recette dans le mod).
    recipe = _bake_recipe(
        rng, db, state, SLOT_FLUID, output_fluid,
        [(SLOT_FLUID, input_fluid)],
        recipe_name=f"randputf-{building.name}-{output_fluid}",
    )
    recipe["category"] = _recipe_category(building, True, True)
    recipe["crafted_in"] = building.name
    state.recipes.append(recipe)
    state.mark_obtained(SLOT_FLUID, output_fluid)

    # Assignation input/output DÉRIVÉE de la recette (source unique de vérité) :
    # le filter du mod + le tooltip réflètent EXACTEMENT la recette jouable.
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
    """Branche « (item/fluide) → item » de ``_make_fixed_recipe_for_crafter``
    (transformateur item d'un mod, ``is_fixed_crafter`` à sortie item).
    Voir la doc de l'appelant."""
    if output_item is None:
        # Output : item obtenable non encore produit par une autre recette
        # (forcer l'utilité = être LE producteur) ; item de bâtiment/rocket-exclu.
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

    # Inputs : items (et éventuellement un fluide) DÉJÀ obtenus SANS ce
    # fabricateur — amorçage, jamais de cycle SOLVABLE (§10). Limités par les
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
        # Un transformateur item qui accepte aussi un fluide (ex. four d'un mod
        # refroidi à l'eau) : on ajoute un ingrédient fluide obtenable quand
        # la recette supporte des fluides.
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
    """Branche « item → item (résidu) » de ``_make_fixed_recipe_for_crafter``
    pour un combusteur à résidu (``fuel_residues`` non vide) : le réacteur
    nucléaire. L'output = LE résidu de combustion (burnt_result : l'item que
    le bâtiment produit en brûlant son combustible — depleted-uranium-fuel-cell
    pour le réacteur). Les inputs = items déjà obtenus SANS ce fabricateur,
    dont le pseudo-combustible (entrée d'un combusteur = un item quelconque,
    §6) ; on garantit au moins un ingrédient item pour que la machine ait une
    matière à brûler. Anti-boucle : jamais l'output lui-même, jamais un item
    dont la production exigerait ce bâtiment."""
    residues = list(getattr(building, "fuel_residues", ()) or ())
    if not residues:
        raise ValueError(f"{building.name} sans résidu de combustion (recette résidu impossible)")
    output_item = rng.choice(residues)

    if output_item in state.obtained_items:
        # Déjà obtenu autrement : on choisit un autre résidu, sinon on force
        # quand même (le réacteur reste LE producteur) mais cette branche ne
        # doit normalement pas se déclencher.
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
    """Un output imposé pour un fabricateur fixe doit être un item réellement
    obtenable COMME produit de recette (pas un racket/env/posable)."""
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
    # C2 (équilibre production/consommation) : côté PRODUCTION on préfère les
    # produits rares (sous-produits) et on freine ce qui est déjà pléthore
    # (produit mais peu consommé). Poids = 1 / facteur d'ingrédient.
    state.ensure_balance_target(rng)
    weights = [1.0 / max(state.balance_factor(n), 1e-6) for n in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


def _is_building_item(db: VanillaDB, name: str) -> bool:
    """Un item posable est produit par SON OWN recette de déploiement
    (randputf-<bâtiment>), jamais comme produit générique d'un autre bâtiment :
    chaque recette de bâtiment reste ainsi unlockée par sa propre tech
    (pas de doublon d'unlock, §13)."""
    item = db.items.get(name)
    return item is not None and item.place_result is not None
