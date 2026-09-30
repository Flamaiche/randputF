"""Normalisation du dump JSON produit par le mod exporter vers VanillaDB.

Le dump est ecrit par Factorio au runtime (prototypes API 2.0) dans
script-output/randputF/vanilla_dump.json. Ce module le transforme en schema
intermediaire stable utilise par le generateur.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tool.common.db import BuildingDef, FluidDef, ItemDef, RecipeRef, VanillaDB, has_hidden_recipe, ENVIRONMENTAL_ITEMS
from tool.common.tagsets import RAIL_TYPES, VIRTUAL_ITEM_TYPES


JUNK_PREFIXES = ("parameter-",)
JUNK_SUFFIXES = ("-unknown",)
JUNK_NAMES = {
    "no-item",
    "science",
    "electric-energy-interface",
    "hidden-electric-energy-interface",
    "heat-interface",
    "bottomless-chest",
    "proxy-container",
    "empty-module-slot",
    "lane-splitter",
    "one-way-valve",
    "overflow-valve",
    "top-up-valve",
    "linked-belt",
    "linked-chest",
    "infinity-pipe",
    "infinity-chest",
    "infinity-cargo-wagon",
    "simple-entity-with-force",
    "simple-entity-with-owner",
    "cut-paste-tool",
    "loader",
    "fast-loader",
    "express-loader",
    "coin",
    "copper-wire",
}


def is_junk(name: str) -> bool:
    """Vrai si l'item est écarté du pool (noms, préfixes ou suffixes « junk »
    balistiques/équipements/supports sans capacité reconnue)."""
    return (
        name in JUNK_NAMES
        or any(name.startswith(p) for p in JUNK_PREFIXES)
        or any(name.endswith(s) for s in JUNK_SUFFIXES)
    )


# Préfixe partagé avec le garde-fou Lua (exporter/control.lua, RANDPUTF_PREFIX).
# Toute modification ici doit être répercutée là-bas et inversement.
_RANDPUTF_PREFIX = "randputf-"
_POLLUTABLE_SECTIONS = ("items", "fluids", "entities", "recipes")

# Invariant vanilla 2.0 : ces fluides ne sont PAS des carburants (fuel_value 0).
# La passe carburant de randputF les mute en place à 200 000 — un signal fiable
# de dump pollué par le canal MUTATION (indétectable par le filtre de noms).
# parameter-0..9 et fluid-unknown (internes 2.0, fuel_value 0 en base) sont
# inclus : mesurés mutés dans un vrai dump pollué, ce sont aussi des cibles
# possibles de la passe carburant.
_VANILLA_NON_FUEL_FLUIDS = (
    "water",
    "crude-oil",
    "heavy-oil",
    "light-oil",
    "petroleum-gas",
    "sulfuric-acid",
    "steam",
    "lubricant",
    "parameter-0",
    "parameter-1",
    "parameter-2",
    "parameter-3",
    "parameter-4",
    "parameter-5",
    "parameter-6",
    "parameter-7",
    "parameter-8",
    "parameter-9",
    "fluid-unknown",
)


def _strip_randputf_artefacts(dump: dict) -> dict:
    """Retire du dump les artefacts générés par le mod randputF (clés préfixées
    ``randputf-`` dans les sections items/fluides/entités/recettes).

    L'exporter et le mod principal peuvent être actifs ensemble : l'exporter
    lit alors les prototypes APRÈS la data-stage de randputF, un dump
    « pollué ». Sans filtre, le tool re-randomiserait des recettes déjà
    randomisées — empilant le préfixe (``randputf-randputf-…``) et tirant des
    tirages fantômes — des seeds valides qui ne correspondent plus à rien de
    documenté, sans rien casser. Le filtre rend l'erreur impossible : un dump
    pollué et un dump propre produisent exactement la même seed.
    """
    clean = dict(dump)
    for section in _POLLUTABLE_SECTIONS:
        entries = dump.get(section)
        if not isinstance(entries, dict):
            continue
        clean[section] = {
            name: entry
            for name, entry in entries.items()
            if not name.startswith(_RANDPUTF_PREFIX)
        }
    return clean


def _check_dump_integrity(dump: dict) -> None:
    """Rejette un dump MUTÉ EN PLACE (canal silencieux, indétectable par le
    filtre de noms ci-dessus).

    Si randputF a tourné avant l'export, sa passe carburant modifie des fluides
    vanilla existants : ``fuel_value`` 0 → 200 000 sur des clés dont le nom est
    inchangé. Ces valeurs ressemblent à du contenu légitime — seul un invariant
    versionné les trahit. L'exporter REFUSE déjà un export pollué (garde-fou
    runtime) ; ce contrôle protège les dumps pollués déjà sur disque et rend
    l'erreur impossible à rater au chargement.

    Limite assumée, et pourquoi elle est sans conséquence : l'invariant ne
    couvre QUE le canal fluides. Toute mutation seule d'un autre canal passe —
    pas seulement le canal entities (fuel_categories += "nuclear" sur les
    brûleurs, filtres boiler/heat-exchanger), aussi recipes/items/etc. Il n'en a
    pas besoin : la passe carburant mute TOUJOURS des fluides (co-occurrence
    structurelle garantie par ``mod/data-updates.lua`` : boucle non conditionnelle
    ``for _, proto in pairs(data.raw.fluid)``) — un dump réellement pollué est
    donc systématiquement attrapé par l'invariant fluides, SAUF s'il est la
    seule mutation présente. La frontière de vérité reste le refus de l'exporter
    ; ce garde est une défense en profondeur pour les dumps anciens.
    """
    for name in _VANILLA_NON_FUEL_FLUIDS:
        entry = (dump.get("fluids") or {}).get(name)
        if entry is None:
            continue
        fuel_value = entry.get("fuel_value") or 0
        if fuel_value > 0:
            raise ValueError(
                f"Dump pollue : {name} a fuel_value={fuel_value} (attendu 0 en "
                "vanilla 2.0) — la data-stage de randputF a mute des prototypes "
                "vanilla en place. Re-exporte le dump avec randputF desactive "
                "(l'exporter refuse un export pollue)."
            )


def load_db_from_dump(dump: dict) -> VanillaDB:
    """Construit la VanillaDB depuis le dump du mod compagnon : items/fluides
    post-filtre junk, bâtiments taggés (§9), recettes. ``seed_value`` hérite
    de la version du jeu (meta du dump)."""
    dump = _strip_randputf_artefacts(dump)
    _check_dump_integrity(dump)
    meta = dump.get("meta", {})
    db = VanillaDB(seed_value=int(meta.get("game_version_numeric", 0)))

    for name, entry in (dump.get("items") or {}).items():
        if is_junk(name):
            db.excluded_items[name] = entry
            continue
        itype = entry.get("type", "item")
        subgroup = _safe_group(entry)
        db.items[name] = ItemDef(
            name=name,
            subgroup=subgroup,
            place_result=entry.get("place_result"),
            fuel_value=_fuel_value(entry.get("fuel_value")),
            is_ammo=itype == "ammo",
            is_gun=itype == "gun",
            is_armor=itype == "armor",
            is_science_pack=subgroup == "science-pack",
            is_tool=itype == "tool",
            ammo_category=entry.get("ammo_category") or "",
            item_type=itype,
            fuel_category=entry.get("fuel_category") or "",
            burnt_result=entry.get("burnt_result"),
            stack_size=int(entry.get("stack_size") or 0),
            # --- Tags §9 : items (docs/tags.md §12) ---
            is_environmental=_is_environmental_item(name, subgroup, itype),
            is_virtual_item=_is_virtual_item(name, itype, entry.get("place_result")),
            is_module=itype == "module",
            is_capsule_throwable=itype == "capsule",
        )

    for name, entry in (dump.get("fluids") or {}).items():
        if is_junk(name):
            db.excluded_fluids[name] = entry
            continue
        db.fluids[name] = FluidDef(
            name=name,
            fuel_value=_fuel_value(entry.get("fuel_value")),
        )

    for name, entry in (dump.get("entities") or {}).items():
        # Les entités cheat/junk finiraient par remplir l'arbre tech de fillers.
        if is_junk(name):
            db.excluded_items[name] = entry
            continue
        bdef = tag_parse_entity(name, entry)
        if bdef:
            db.buildings[name] = bdef

    for name, entry in (dump.get("recipes") or {}).items():
        db.recipes[name] = RecipeRef(
            name=name,
            category=entry.get("category") or "",
            ingredients=tuple(_parse_stack(i) for i in entry.get("ingredients", [])),
            products=tuple(_parse_stack(p) for p in entry.get("products", [])),
            energy=float(entry.get("energy", 0.5)),
        )

    # POST-PARSE : le tag « recette cachée » dépend des RÉSIDUS de combustible
    # (``burnt_result`` des items), une info de la base items indisponible à la
    # volée pendant le parse. On stampe les résidus PUIS le tag sur chaque
    # bâtiment. Le réacteur (item → item résidu) devient une recette cachée
    # sans aucune liste de noms.
    for b in db.buildings.values():
        b.fuel_residues = db.fuel_residues(b)
        b.has_hidden_recipe = has_hidden_recipe(b)
    return db


def _safe_group(entry: dict) -> str:
    group = entry.get("subgroup")
    if isinstance(group, dict):
        return group.get("name", "")
    return group or ""


def _fuel_value(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return float(raw.get("value", 0)) or None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_stack(stack: dict) -> tuple:
    return (stack.get("type", "item"), stack.get("name", ""), float(stack.get("amount", 0)))


def _is_environmental_item(name: str, subgroup: str, itype: str) -> bool:
    """Item récoltable à la main (wood/stone/raw-fish) : enrichissement de
    ``ENVIRONMENTAL_ITEMS`` via un tag. Le dump ne distingue pas récolté à la
    main / miné (même type ``raw-resource``) : on se rabat sur l'ensemble
    existant comme source de vérité."""
    return name in ENVIRONMENTAL_ITEMS


def _is_virtual_item(name: str, itype: str, place_result: str) -> bool:
    """Items « contrôle » non fabricables / non empilables (blueprint, planners,
    remotes) : détectés par type ET par absence d'objet posé. Le rail vanilla
    (``rail-planner`` 2.0) n'est PAS virtuel : il se fabrique et se pose."""
    return itype in VIRTUAL_ITEM_TYPES and not place_result


def equivalent_functional_type(b: BuildingDef) -> str:
    """RECONSTRUIT l'ancien type fonctionnel exclusif (research/transformer/
    generator/distribution/extractor/other) depuis les TAGS cumulables, dans
    le même ordre de priorité que l'ancien ``_parse_entity``. Outil de
    VÉRIFICATION : la logique ne repose plus que sur les tags, mais ce « rôle
    gagnant » sert encore aux décisions d'héritage du dump (medium,
    directives fluid_inputs)."""
    if b.is_research:
        return "research"
    if b.is_crafter:
        return "transformer"
    if b.is_generator:
        return "generator"
    if b.is_distribution:
        return "distribution"
    if b.is_extractor:
        return "extractor"
    return "other"


def tag_parse_entity(name: str, e: dict) -> BuildingDef | None:
    """Tagging PAR CAPACITES in trinseques, sans liste de types : chaque
    bâtiment reçoit des TAGS ORTHOGONAUX CUMULABLES (atelier et générateur à
    la fois) :
    - consommation de science packs (lab_inputs) → ``is_research`` ;
    - categories de craft / pieces de fusee / temperature cible → ``is_crafter`` ;
    - production electrique ou chaleur → ``is_generator`` ;
    - perimetre de supply (pylônes) → ``is_distribution`` ;
    - categories de ressources minables ou pompage → ``is_extractor`` ;
    - sinon → ``is_other`` (backup, jamais perdu).

    ``equivalent_functional_type`` reproduit l'ancien classement EXCLUSIF ;
    réutilisé ici pour les décisions d'héritage du dump (medium, directives).
    """
    directives: dict = {}

    energy_src = e.get("energy_source") or {}
    entity_type = e.get("type", "")
    energy_type = energy_src.get("type") or ""
    craft_categories = tuple(e.get("crafting_categories") or ())
    resource_categories = tuple(e.get("resource_categories") or ())
    lab_inputs = e.get("lab_inputs") or []
    rocket_parts = e.get("rocket_parts_required")
    target_temp = e.get("target_temperature")
    max_power = float(e.get("max_power_output") or 0)
    energy_prod = float((e.get("energy_source") or {}).get("production") or 0)
    has_heat = bool(e.get("has_heat_output"))
    supply_area = e.get("supply_area_distance")
    pumping_speed = e.get("pumping_speed")
    pumped_fluid = e.get("pumped_fluid")

    fluidboxes = e.get("fluidboxes") or {}
    fluid_in = int(fluidboxes.get("input", 0) or 0)
    fluid_out = int(fluidboxes.get("output", 0) or 0)

    if rocket_parts:
        directives["rocket_parts_required"] = int(rocket_parts)

    if lab_inputs:
        # Le lab consomme des science packs : bâtiment de RECHERCHE, pas atelier.
        directives["lab_inputs"] = tuple(lab_inputs)
        is_research = True
    else:
        is_research = False

    if craft_categories or rocket_parts or target_temp is not None:
        # Le personnage lui-meme tombe ici : fabrication a la main.
        is_crafter = True
    else:
        is_crafter = False

    # Un accumulateur affiche un max_power_output (decharge) mais ne PRODUIT
    # pas d'energie : exclu des generateurs (l'electricite le prendrait pour
    # source de courant). Le réacteur (has_heat_output) produit de la CHALEUR.
    is_accumulator = entity_type == "accumulator"
    is_generator = (
        not is_accumulator
        and (max_power > 0 or energy_prod > 0 or (has_heat and bool(energy_type)))
    )
    # Poteaux electriques : distribution du reseau.
    is_distribution = bool(supply_area)
    # Un extracteur CREE sa ressource depuis le monde : fluides sortants sans
    # entree (offshore-pump, pumpjack) ou categories de minage.
    is_extractor = bool(
        resource_categories
        or pumped_fluid
        or (pumping_speed is not None and fluid_in == 0 and fluid_out > 0)
    )
    # Aucune capacite reconnue : range en "other", jamais perdu.
    is_other = not (is_research or is_crafter or is_generator or is_distribution or is_extractor)

    # « Rôle gagnant » (ex-classement exclusif) — sert aux décisions d'héritage
    # du dump (medium, directives).
    functional = equivalent_functional_type(
        SimpleNamespace(
            is_research=is_research,
            is_crafter=is_crafter,
            is_generator=is_generator,
            is_distribution=is_distribution,
            is_extractor=is_extractor,
        )
    )

    # Électricité vs chaleur (TAGS orthogonaux) : un vrai producteur produit de
    # l'électricité ; un réacteur produit de la CHALEUR. L'accumulateur affiche
    # une puissance de décharge mais ne PRODUIT pas de courant.
    produces_electricity = (
        not is_accumulator and (max_power > 0 or energy_prod > 0)
    )

    if pumped_fluid:
        medium = "water"
    elif "basic-fluid" in resource_categories:
        medium = "fluid"
    elif functional == "extractor" and fluid_out > 0 and not resource_categories:
        # Sortie de fluide sans categorie de minage = source d'eau (offshore-pump).
        medium = "water"
    elif functional == "extractor":
        medium = "ground"
    else:
        medium = ""

    if fluid_in > 0 and functional != "generator":
        directives["fluid_inputs"] = True

    # --- Tags §1 : raffinement des rôles (docs/tags.md §1.1) ---
    is_power_pole = entity_type == "electric-pole"
    is_beacon = entity_type == "beacon"
    # Stockage d'énergie : le dump n'emporte pas ``buffer_capacity`` (exporter) —
    # on se rabat sur le seul accumulateur de type (indice API 2.0, pas une
    # liste de noms). À rouvrir quand l'exporter émettra la capacité réelle.
    is_energy_storage = is_accumulator
    is_offgrid = produces_electricity and (
        energy_type != "electric" or entity_type == "solar-panel"
    )
    # Consomme du courant : source 'electric' SANS être producteur ni stockeur.
    consumes_electricity = (
        energy_type == "electric" and not produces_electricity and not is_accumulator
    )
    is_water_extractor = is_extractor and medium == "water"
    is_fluid_extractor = is_extractor and medium == "fluid"
    is_ground_extractor = is_extractor and medium == "ground"

    # --- Tags §2 : logistique & transports (docs/tags.md §2) ---
    is_belt = entity_type == "transport-belt"
    is_underground_belt = entity_type == "underground-belt"
    is_splitter = entity_type == "splitter"
    is_inserter = entity_type == "inserter"
    is_pipe = entity_type == "pipe"
    is_pipe_to_ground = entity_type == "pipe-to-ground"
    is_fluid_transport = is_pipe or is_pipe_to_ground
    # Les poitrines cheat/finies (bottomless/linked/infinity) sont exclues
    # plus haut (is_junk).
    is_chest = entity_type == "container"
    is_logistics_chest = entity_type == "logistic-container"
    is_storage = is_chest or is_logistics_chest
    is_roboport = entity_type == "roboport"
    # Robots logistiques/de construction uniquement (le robot de combat est
    # une unité offensive distincte, taggée ``is_combat_robot``).
    is_robot = entity_type in ("logistic-robot", "construction-robot")

    # --- Tags §3 : train & véhicules (docs/tags.md §3) ---
    is_rail = entity_type in RAIL_TYPES
    is_rail_support = entity_type == "rail-support"
    is_rail_signal = entity_type in ("rail-signal", "rail-chain-signal")
    is_train_stop = entity_type == "train-stop"
    is_locomotive = entity_type == "locomotive"
    is_wagon = entity_type in ("cargo-wagon", "fluid-wagon", "artillery-wagon")
    is_spider_vehicle = entity_type == "spider-vehicle"
    is_vehicle = is_locomotive or is_wagon or is_spider_vehicle or entity_type == "car"

    # --- Tags §4 : production spécialisée (docs/tags.md §4) ---
    cats = set(craft_categories)
    is_furnace = bool(cats & {"smelting"})
    is_assembler = bool(cats & {"crafting", "advanced-crafting", "crafting-with-fluid"})
    is_chemical_plant = bool(cats & {"chemistry"})
    is_refinery = bool(cats & {"oil-processing"})
    is_centrifuge = bool(cats & {"centrifuging"})
    is_rocket_parts_crafter = bool(cats & {"rocket-building"}) or bool(rocket_parts)

    # --- Tags §5 : énergie & chaleur (docs/tags.md §5) ---
    # boiler ET heat-exchanger partagent le type 'boiler' : distingués par
    # l'énergie de la source ('burner' vs 'heat').
    is_boiler = entity_type == "boiler" and energy_type == "burner"
    is_heat_exchanger = entity_type == "boiler" and energy_type == "heat"
    is_solar = entity_type == "solar-panel"
    is_reactor = entity_type == "reactor"
    is_heat_transport = entity_type == "heat-pipe"
    # Modèle « chaleur » (docs/tags.md §5bis) : une SOURCE PRODUIT la chaleur
    # (réacteur) ; un CONSOMMATEUR la DEMANDE (échangeur). ``produces_heat``
    # est restreint à la source.
    is_heat_source = entity_type == "reactor" or (has_heat and energy_type == "burner")
    is_heat_sink = energy_type == "heat"
    is_burner_generator = entity_type == "burner-generator"

    # --- Tags §6 : extraction (docs/tags.md §6) ---
    is_mining_drill = entity_type == "mining-drill"
    is_pumpjack = entity_type == "mining-drill" and "basic-fluid" in resource_categories
    is_offshore_pump = is_water_extractor  # seule source d'eau du vanilla
    is_well_pump = entity_type == "pump"

    # --- Tags §7 : combat & défense (docs/tags.md §10) ---
    # 4 familles de tourelles vanilla = 4 types API distincts ; is_turret est
    # l'union. Aucun ne produit (is_other) : raffinements orthogonaux au rôle.
    is_gun_turret = entity_type == "ammo-turret"
    is_laser_turret = entity_type == "electric-turret"
    is_flame_turret = entity_type == "fluid-turret"
    is_artillery = entity_type == "artillery-turret"
    is_turret = is_gun_turret or is_laser_turret or is_flame_turret or is_artillery
    is_defensive_wall = entity_type in ("wall", "gate")
    is_landmine = entity_type == "land-mine"
    # Robot de COMBAT (destroyer/defender/distractor) : distinct du robot
    # logistique/construction (is_robot, jamais confondu).
    is_combat_robot = entity_type == "combat-robot"

    # --- Tags §8 : signal-réseau & électronique (docs/tags.md §11) ---
    # Combinators : les 3 types de calcul + l'émetteur constant. is_circuit_io
    # est l'union avec speaker/display/switch. Consommateurs de courant ;
    # tag de réseau circuits orthogonal au rôle (is_other).
    is_circuit_combinator = entity_type in (
        "arithmetic-combinator", "decider-combinator", "selector-combinator",
    )
    is_constant_combinator = entity_type == "constant-combinator"
    is_circuit_io = (
        is_circuit_combinator
        or is_constant_combinator
        or entity_type in ("programmable-speaker", "display-panel", "power-switch")
    )
    is_rgb_lamp = entity_type == "lamp" and consumes_electricity
    is_radar = entity_type == "radar"

    return BuildingDef(
        name=name,
        entity_type=entity_type,
        medium=medium,
        is_research=is_research,
        is_crafter=is_crafter,
        is_generator=is_generator,
        is_distribution=is_distribution,
        is_extractor=is_extractor,
        is_other=is_other,
        is_power_pole=is_power_pole,
        is_beacon=is_beacon,
        is_accumulator=is_accumulator,
        is_energy_storage=is_energy_storage,
        is_offgrid=is_offgrid,
        consumes_electricity=consumes_electricity,
        is_water_extractor=is_water_extractor,
        is_fluid_extractor=is_fluid_extractor,
        is_ground_extractor=is_ground_extractor,
        is_belt=is_belt,
        is_underground_belt=is_underground_belt,
        is_splitter=is_splitter,
        is_inserter=is_inserter,
        is_pipe=is_pipe,
        is_pipe_to_ground=is_pipe_to_ground,
        is_fluid_transport=is_fluid_transport,
        is_chest=is_chest,
        is_logistics_chest=is_logistics_chest,
        is_storage=is_storage,
        is_roboport=is_roboport,
        is_robot=is_robot,
        is_rail=is_rail,
        is_rail_support=is_rail_support,
        is_rail_signal=is_rail_signal,
        is_train_stop=is_train_stop,
        is_locomotive=is_locomotive,
        is_wagon=is_wagon,
        is_vehicle=is_vehicle,
        is_spider_vehicle=is_spider_vehicle,
        is_furnace=is_furnace,
        is_assembler=is_assembler,
        is_chemical_plant=is_chemical_plant,
        is_refinery=is_refinery,
        is_centrifuge=is_centrifuge,
        is_rocket_parts_crafter=is_rocket_parts_crafter,
        is_boiler=is_boiler,
        is_heat_exchanger=is_heat_exchanger,
        is_solar=is_solar,
        is_reactor=is_reactor,
        is_heat_transport=is_heat_transport,
        is_heat_source=is_heat_source,
        is_heat_sink=is_heat_sink,
        is_burner_generator=is_burner_generator,
        is_mining_drill=is_mining_drill,
        is_pumpjack=is_pumpjack,
        is_offshore_pump=is_offshore_pump,
        is_well_pump=is_well_pump,
        is_turret=is_turret,
        is_gun_turret=is_gun_turret,
        is_laser_turret=is_laser_turret,
        is_flame_turret=is_flame_turret,
        is_artillery=is_artillery,
        is_defensive_wall=is_defensive_wall,
        is_landmine=is_landmine,
        is_combat_robot=is_combat_robot,
        is_circuit_combinator=is_circuit_combinator,
        is_constant_combinator=is_constant_combinator,
        is_circuit_io=is_circuit_io,
        is_rgb_lamp=is_rgb_lamp,
        is_radar=is_radar,
        has_crafting=bool(craft_categories),
        has_mining=bool(resource_categories),
        has_pumping=bool(pumped_fluid) or (pumping_speed is not None and fluid_in == 0 and fluid_out > 0),
        has_fluid_input=fluid_in > 0,
        has_fluid_output=fluid_out > 0,
        has_fuel=energy_type == "burner",
        has_target_temperature=target_temp is not None,
        has_rocket_parts=bool(rocket_parts),
        crafting_categories=craft_categories,
        resource_categories=resource_categories,
        energy_type=energy_type,
        fuel_categories=tuple(energy_src.get("fuel_categories") or ()),
        pumped_fluid=pumped_fluid,
        item_input_slots=int(e.get("ingredient_count") or 0),
        fluid_inputs=fluid_in,
        fluid_outputs=fluid_out,
        produces_heat=is_heat_source,
        produces_electricity=produces_electricity,
        directives=directives,
    )


def summarize_db(db: VanillaDB) -> str:
    """Résumé textuel de la base (items/fluides/bâtiments par tag, recettes)
    pour l'audit de parse — ex. `randputf parse`."""
    mediums = sorted({b.medium for b in db.buildings.values() if b.is_extractor and b.medium})
    others = sum(1 for b in db.buildings.values() if b.is_other)
    lines = [
        f"Items: {len(db.items)} ({len(db.fuel_items())} combustibles) + {len(db.excluded_items)} exclus",
        f"Fluides: {len(db.fluids)} ({len(db.fuel_fluids())} combustibles) + {len(db.excluded_fluids)} exclus",
        f"Bâtiments classés: {len(db.buildings)}",
        f"  extracteurs (is_extractor): total={len(db.buildings_with_tag('is_extractor'))} "
        + ", ".join(f"{m}={len(db.extractors_for_medium(m))}" for m in mediums),
        f"  ateliers (is_crafter): {len(db.buildings_with_tag('is_crafter'))}",
        f"  recherche (is_research): {len(db.buildings_with_tag('is_research'))}",
        f"  générateurs (is_generator): {len(db.buildings_with_tag('is_generator'))}",
        f"  distribution (is_distribution): {len(db.buildings_with_tag('is_distribution'))} "
        f"[pylônes (is_power_pole): {len(db.buildings_with_tag('is_power_pole'))}]",
        f"  non classés (is_other): {others}",
        f"Recettes vanilla connues: {len(db.recipes)}",
    ]
    return "\n".join(lines)
