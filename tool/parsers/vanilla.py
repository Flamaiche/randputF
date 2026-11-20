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
from tool.common.tagsets import RAIL_TYPES, VEHICLE_GUNS, VIRTUAL_ITEM_TYPES


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


# Préfixe des artefacts générés par randputF (recettes/items/entités/fluides).
_RANDPUTF_PREFIX = "randputf-"


def _recipe_product_names(entry: dict) -> set[str]:
    """Noms des produits d'une recette du dump (items et fluides)."""
    return {
        str(product.get("name"))
        for product in entry.get("products") or []
        if isinstance(product, dict) and product.get("name")
    }


def is_hidden_prototype(entry: dict) -> bool:
    """Vrai si le prototype est neutralisé (``hidden = true``).

    ``enabled = false`` seul n'est PAS un critère : une recette normale est
    souvent désactivée au chargement puis débloquée par une technologie.
    """
    return entry.get("hidden") is True


def _is_stacked_randputf(name: str) -> bool:
    """Artefact d'un dump déjà randomisé deux fois (``randputf-randputf-…``)."""
    return name.startswith(_RANDPUTF_PREFIX * 2)


def canonical_recipe_map(recipes: dict) -> dict[str, str]:
    """Normalise les recettes préfixées : produit logique -> recette canonique.

    Une recette ``randputf-X`` est canonique pour le produit ``X`` quand son
    nom, préfixe retiré, est exactement un de ses produits. La recette vanilla
    ``X`` est alors ignorée par la génération ; les autres recettes préfixées
    (``randputf-ease-X``, ``randputf-relay-X``, recettes de fluides…) restent
    des alternatives et ne remplacent rien.

    Les recettes neutralisées (``hidden = true``) ne sont jamais canoniques :
    un dump moddé expose ainsi l'état réel, sans deviner à partir du nom seul.
    """
    canonical: dict[str, str] = {}
    for name, entry in recipes.items():
        if not isinstance(entry, dict) or is_hidden_prototype(entry):
            continue
        if not name.startswith(_RANDPUTF_PREFIX):
            continue
        logical = name[len(_RANDPUTF_PREFIX):]
        if logical.startswith(_RANDPUTF_PREFIX):
            continue
        if logical in _recipe_product_names(entry):
            canonical[logical] = name
    return canonical


def _resolve_pumped_fluid(entry: dict, layer_fluids: dict[str, set[str]]) -> str | None:
    """Fluide pompe par une entite, depuis les FAITS du dump uniquement :

    1. filtre d'une fluidbox de sortie declaree par le prototype ;
    2. chainage par tuiles : couches requises par les regles de placement
       (``tile_buildability_rules``) -> tuiles portant ces couches -> leur
       champ ``fluid`` (doc du jeu : « The fluid offshore pump produces on
       this tile »).

    Plusieurs fluides distincts => ambigu, aucun nom invente.

    Un CONVERTISSEUR n'extrait pas : ses filtres decrivent sa production
    (boiler : water en entree, steam en sortie). La resolution ne s'applique
    donc qu'aux sources pures, sans boite de fluide en entree."""
    boxes = entry.get("fluidboxes") or {}
    if not isinstance(boxes, dict) or int(boxes.get("input", 0) or 0) > 0:
        return None
    detail = boxes.get("detail") or {}
    if isinstance(detail, dict):
        for box in detail.values():
            if not isinstance(box, dict):
                continue
            if box.get("production_type") in ("output", "input-output"):
                filt = box.get("filter")
                if filt:
                    return str(filt)
    fluids: set[str] = set()
    for rule in entry.get("tile_buildability_rules") or []:
        if not isinstance(rule, dict):
            continue
        for layer in rule.get("required_tiles") or []:
            fluids |= layer_fluids.get(str(layer), set())
    if len(fluids) == 1:
        return fluids.pop()
    return None


_LAKE_TILES_DATA_TYPE = "randputf.lake_tiles"


def _lake_tile_fluids(dump: dict) -> tuple[str | None, dict[str, str]]:
    """Mapping canonique expose par ``mod-data`` : tuile de lac -> fluide.

    Retourne ``(source, {tuile: fluide})``. La source est la tuile fantome
    remplacee au runtime ; les tuiles de ``results[source]`` sont les seules
    ressources reelles (le fluide fantome n'y figure pas). Absent des dumps
    vanilla : les appelants gardent alors leur repli par les faits des tuiles.
    """
    mod_data = dump.get("mod_data")
    if not isinstance(mod_data, dict):
        return None, {}
    for entry in mod_data.values():
        if not isinstance(entry, dict):
            continue
        if entry.get("data_type") != _LAKE_TILES_DATA_TYPE:
            continue
        data = entry.get("data")
        if not isinstance(data, dict):
            continue
        source = data.get("source")
        results = data.get("results")
        fluids = data.get("fluids")
        if (
            not isinstance(source, str)
            or not isinstance(results, dict)
            or not isinstance(fluids, dict)
        ):
            continue
        tiles = results.get(source)
        if not isinstance(tiles, list):
            continue
        mapping = {
            str(tile): str(fluids[tile])
            for tile in tiles
            if isinstance(tile, str) and isinstance(fluids.get(tile), str)
        }
        return source, mapping
    return None, {}


def inject_pumped_fluids(dump: dict) -> dict:
    """Resout et pose ``pumped_fluid``/``pumped_fluids`` sur chaque entite.

    Le dump 0.1.5+ n'embarque plus de ``pumped_fluid`` (fin du litteral
    historique de l'exporter) : la valeur est RECALCULEE depuis les filtres
    et les tuiles. Un dump modde peut en plus porter ``mod_data``
    (``randputf.lake_tiles``) : le mapping tuile -> fluide y est canonique et
    remplace la deduction ambigue quand plusieurs lacs se partagent une couche.
    Idempotent : rejouer sur un dump deja resolu redonne les memes valeurs."""
    tiles = dump.get("tiles")
    if not isinstance(tiles, dict):
        tiles = {}
    layer_fluids: dict[str, set[str]] = {}
    for tile in tiles.values():
        if not isinstance(tile, dict):
            continue
        fluid = tile.get("fluid")
        if not fluid:
            continue
        for layer in tile.get("collision_layers") or []:
            layer_fluids.setdefault(str(layer), set()).add(str(fluid))
    source, lake_fluids = _lake_tile_fluids(dump)
    source_layers: set[str] = set()
    if source and isinstance(tiles.get(source), dict):
        source_layers = {
            str(layer)
            for layer in (tiles[source].get("collision_layers") or [])
        }
    lake_fluid_names = sorted(set(lake_fluids.values()))
    entities = dump.get("entities")
    if not isinstance(entities, dict):
        return dump
    for entry in entities.values():
        if not isinstance(entry, dict):
            continue
        resolved = _resolve_pumped_fluid(entry, layer_fluids)
        required_layers: set[str] = set()
        for rule in entry.get("tile_buildability_rules") or []:
            if isinstance(rule, dict):
                required_layers.update(
                    str(layer) for layer in (rule.get("required_tiles") or [])
                )
        uses_lake_source = bool(
            lake_fluid_names and source_layers and required_layers & source_layers
        )
        if uses_lake_source and (
            resolved is None or resolved in lake_fluid_names
        ):
            entry["pumped_fluids"] = lake_fluid_names
            if resolved:
                entry["pumped_fluid"] = resolved
            elif len(lake_fluid_names) == 1:
                entry["pumped_fluid"] = lake_fluid_names[0]
            else:
                entry.pop("pumped_fluid", None)
        else:
            entry.pop("pumped_fluids", None)
            if resolved:
                entry["pumped_fluid"] = resolved
            else:
                entry.pop("pumped_fluid", None)
    return dump


def science_pack_names(dump: dict) -> set[str]:
    """Items/fluides qui font AVANCER les recherches (faits du dump).

    Un pack de science est ce que le jeu CONSOMME pour chercher :
    - ingredient d'unite d'une technologie (pack coute par une tech,
      y compris modde) ;
    - accepte par un lab (``lab_inputs``) — un lab a ``lab_inputs`` vide
      accepte tout, seules les techs le couvrent alors.

    Aucune convention de subgroup (l'heuristique historique
    ``subgroup == "science-pack"`` etait une convention vanilla) : un pack
    modde dans un subgroup quelconque est reconnu des qu'une recherche
    ou un lab l'exige."""
    techs = dump.get("technologies") or {}
    entries = (
        techs.values()
        if isinstance(techs, dict)
        else [t for t in techs if isinstance(t, dict)]
    )
    names: set[str] = set()
    for tech in entries:
        unit = tech.get("unit")
        ingredients = unit.get("ingredients") if isinstance(unit, dict) else None
        for ingredient in ingredients or []:
            if isinstance(ingredient, dict) and ingredient.get("name"):
                names.add(str(ingredient["name"]))
    for entry in (dump.get("entities") or {}).values():
        if not isinstance(entry, dict):
            continue
        for name in entry.get("lab_inputs") or []:
            names.add(str(name))
    for name, entry in (dump.get("items") or {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("used_by_labs") and _number(entry.get("science_capacity"), 0) > 0:
            names.add(str(name))
    return names


def science_pack_order(dump: dict, names: set[str] | frozenset[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for entry in (dump.get("entities") or {}).values():
        if not isinstance(entry, dict):
            continue
        for name in entry.get("lab_inputs") or []:
            name = str(name)
            if name in names and name not in seen:
                ordered.append(name)
                seen.add(name)
    ordered.extend(sorted(set(names) - seen))
    return tuple(ordered)


def _recipe_facts(name: str, recipe: dict) -> dict:
    """Réduit une recette du dump aux faits consommés par l'audit.

    Retourne ``{name, ingredients, results}`` avec des listes ``name``/``amount``
    normalisées, sans aucun nom de produit inventé.
    """
    def rows(entries) -> list[dict]:
        return [
            {"name": str(entry["name"]), "amount": entry.get("amount", 1)}
            for entry in entries or ()
            if isinstance(entry, dict) and entry.get("name")
        ]

    return {
        "name": name,
        "ingredients": rows(recipe.get("ingredients")),
        "results": rows(recipe.get("products") or recipe.get("results")),
    }


def rocket_chain_from_dump(dump: dict) -> dict:
    """Chaîne de lancement DÉRIVÉE des faits du dump (aucun nom en dur).

    Le joueur « devine » comment gagner, comme il le ferait en jeu :
    - un bâtiment de lancement se reconnaît à ``rocket_parts_required``
      (il assemble des pièces de fusée) ;
    - la catégorie générique ``rocket-building`` désigne les recettes de
      fusée (les autres catégories d'une entité rocket-silo — fermes,
      paramètres — ne sont pas des étapes de lancement) ;
    - les produits de lancement (science spatiale et équivalents moddés)
      viennent des ``rocket_launch_products`` des items et entités.

    Retourne ``{launch_buildings, rocket_recipes, rocket_recipe_data,
    victory_items, launch_products}`` — tout dérivé, donc correct pour tout
    mod qui respecte ces faits, quel que soit le nom de ses items."""
    entities = dump.get("entities") or {}
    recipes = dump.get("recipes") or {}
    parts_entries = {
        name: entry for name, entry in entities.items()
        if isinstance(entry, dict) and entry.get("rocket_parts_required")
    }
    rocket_building_category = "rocket-building"
    standard_silos = [
        name for name, entry in parts_entries.items()
        if rocket_building_category in (entry.get("crafting_categories") or [])
    ]
    launch_buildings = sorted(standard_silos or parts_entries)
    categories: set[str] = set()
    for name in launch_buildings:
        entry = entities[name]
        if isinstance(entry, dict):
            available = {str(c) for c in entry.get("crafting_categories") or []}
            if standard_silos:
                available &= {rocket_building_category}
            categories |= available
    victory_items: set[str] = set(launch_buildings)
    rocket_recipes: list[str] = []
    for name, recipe in recipes.items():
        if not isinstance(recipe, dict) or str(recipe.get("category")) not in categories:
            continue
        ingredients = recipe.get("ingredients") or []
        if not ingredients:
            continue  # pseudo-recette de paramétrage : rien à fabriquer
        rocket_recipes.append(str(name))
        for ing in ingredients:
            if isinstance(ing, dict) and ing.get("name"):
                victory_items.add(str(ing["name"]))
    launch_products: set[str] = set()
    launch_items: set[str] = set()
    launch_requirements: dict[str, dict] = {}
    sections = [entities, dump.get("items") or {}]
    for name, entry in [(name, entry) for section in sections for name, entry in section.items()]:
        if not isinstance(entry, dict):
            continue
        products = entry.get("rocket_launch_products") or []
        if products:
            launch_items.add(str(name))
        for product in products:
            if not isinstance(product, dict) or not product.get("name"):
                continue
            product_name = str(product["name"])
            launch_products.add(product_name)
            launch_requirements.setdefault(
                product_name,
                {
                    "item": str(name),
                    "amount": product.get("amount", 1),
                },
            )
    item_requirements: dict[str, dict] = {}
    for name, entry in (dump.get("items") or {}).items():
        if not isinstance(entry, dict):
            continue
        for product in entry.get("rocket_launch_products") or []:
            if not isinstance(product, dict) or not product.get("name"):
                continue
            item_requirements[str(product["name"])] = {
                "item": str(name),
                "amount": product.get("amount", 1),
            }
    launch_requirements.update(item_requirements)
    ordered_recipes = sorted(rocket_recipes)
    rocket_recipe = ordered_recipes[0] if ordered_recipes else ""
    recipe = recipes.get(rocket_recipe) if rocket_recipe else None
    rocket_part_product = ""
    if isinstance(recipe, dict):
        result_names = [
            str(result["name"])
            for result in recipe.get("products") or recipe.get("results") or []
            if isinstance(result, dict) and result.get("name")
        ]
        main_product = str(recipe.get("main_product") or "")
        rocket_part_product = (
            main_product if main_product in result_names
            else (result_names[0] if result_names else "")
        )
    parts_required = [
        int(entry["rocket_parts_required"])
        for entry in entities.values()
        if isinstance(entry, dict) and entry.get("rocket_parts_required")
    ]
    return {
        "launch_buildings": launch_buildings,
        "rocket_recipes": ordered_recipes,
        "rocket_recipe": rocket_recipe,
        "rocket_recipe_data": _recipe_facts(rocket_recipe, recipe) if isinstance(recipe, dict) else {},
        "rocket_part_product": rocket_part_product,
        "rocket_parts_required": max(parts_required) if parts_required else 0,
        "victory_items": sorted(victory_items),
        "launch_products": sorted(launch_products),
        "launch_items": sorted(launch_items),
        "launch_requirements": launch_requirements,
    }


def rocket_meta_from_chain(chain: dict) -> dict:
    return {
        "launch_buildings": list(chain.get("launch_buildings") or ()),
        "rocket_recipe": chain.get("rocket_recipe") or "",
        "rocket_recipe_data": dict(chain.get("rocket_recipe_data") or {}),
        "rocket_part_product": chain.get("rocket_part_product") or "",
        "rocket_parts_required": int(chain.get("rocket_parts_required") or 0),
        "launch_items": list(chain.get("launch_items") or ()),
        "victory_items": list(chain.get("victory_items") or ()),
    }


def load_db_from_dump(dump: dict) -> VanillaDB:
    """Construit la VanillaDB depuis le dump du mod compagnon : items/fluides
    post-filtre junk, bâtiments taggés (§9), recettes canonisées. ``seed_value``
    hérite de la version du jeu (meta du dump).

    Un dump moddé est accepté tel quel : les recettes vanilla remplacées sont
    ignorées via ``canonical_recipes`` (``X -> randputf-X``), mais leur nom réel
    et les prototypes préfixés restent disponibles pour les liens."""
    meta = dump.get("meta", {})
    db = VanillaDB(seed_value=int(meta.get("game_version_numeric", 0)))
    active_mods = meta.get("active_mods") or ()
    db.is_modded = any(
        isinstance(mod, dict) and mod.get("name") not in (None, "", "base")
        for mod in active_mods
    )
    recipes = dump.get("recipes") or {}
    db.canonical_recipes = canonical_recipe_map(recipes)
    inject_pumped_fluids(dump)
    science = science_pack_names(dump)
    db.science_packs = frozenset(science)
    db.science_pack_order = science_pack_order(dump, science)
    db.rocket_chain = rocket_chain_from_dump(dump)
    mounted_guns = {
        gun
        for entity in (dump.get("entities") or {}).values()
        for gun in (entity.get("guns") or ())
    }
    mounted_guns.update(VEHICLE_GUNS)
    db.vehicle_guns = frozenset(mounted_guns)
    environmental = environmental_items_from_dump(dump)

    for name, entry in (dump.get("items") or {}).items():
        if _is_stacked_randputf(name):
            continue
        if name.startswith(_RANDPUTF_PREFIX):
            db.modded_items[name] = entry
            continue
        if is_junk(name):
            db.excluded_items[name] = entry
            continue
        itype = entry.get("type", "item")
        subgroup = _safe_group(entry)
        # Catégories de combustible — détection automatique du format du dump :
        # - Factorio >= 2.1.20 : ``fuel_categories`` (tableau) ;
        # - Factorio < 2.1.20 : ``fuel_category`` (string unique).
        # Les deux cohabitent dans l'exporter (il émet les deux) ; le modèle
        # garde la liste complète et sa première catégorie en repli.
        fuel_categories = tuple(entry.get("fuel_categories") or ())
        if not fuel_categories and entry.get("fuel_category"):
            fuel_categories = (entry["fuel_category"],)
        fuel_category = fuel_categories[0] if fuel_categories else ""
        db.items[name] = ItemDef(
            name=name,
            subgroup=subgroup,
            place_result=entry.get("place_result"),
            fuel_value=_fuel_value(entry.get("fuel_value")),
            is_ammo=itype == "ammo",
            is_gun=itype == "gun",
            is_armor=itype == "armor",
            is_science_pack=name in science,
            # 2.1.20 : les packs de science passent de ``tool`` à ``item``.
            # ``is_tool`` reste le rôle (consommable de recherche), pas le
            # type : tout ce qu'une recherche consomme a ce rôle.
            is_tool=itype == "tool" or name in science,
            ammo_category=entry.get("ammo_category") or "",
            item_type=itype,
            fuel_categories=fuel_categories,
            fuel_category=fuel_category,
            burnt_result=entry.get("burnt_result"),
            stack_size=int(entry.get("stack_size") or 0),
            used_by_labs=bool(entry.get("used_by_labs")),
            science_capacity=int(_number(entry.get("science_capacity"), 0) or 0),
            # --- Tags §9 : items (docs/tags.md §12) ---
            is_environmental=_is_environmental_item(name, subgroup, itype, environmental),
            is_virtual_item=_is_virtual_item(name, itype, entry.get("place_result")),
            is_module=itype == "module",
            is_capsule_throwable=itype == "capsule",
            is_mounted_gun=name in mounted_guns,
        )

    for name, entry in (dump.get("fluids") or {}).items():
        if _is_stacked_randputf(name):
            continue
        if name.startswith(_RANDPUTF_PREFIX):
            db.modded_fluids[name] = entry
            continue
        if is_junk(name):
            db.excluded_fluids[name] = entry
            continue
        db.fluids[name] = FluidDef(
            name=name,
            fuel_value=_fuel_value(entry.get("fuel_value")),
        )

    for name, entry in (dump.get("entities") or {}).items():
        if _is_stacked_randputf(name):
            continue
        if name.startswith(_RANDPUTF_PREFIX):
            db.modded_buildings[name] = entry
            continue
        # Les entités cheat/junk finiraient par remplir l'arbre tech de fillers.
        if is_junk(name):
            db.excluded_items[name] = entry
            continue
        bdef = tag_parse_entity(name, entry)
        if bdef:
            db.buildings[name] = bdef

    for name, entry in recipes.items():
        if _is_stacked_randputf(name):
            continue
        # Recette vanilla remplacée : la version randputF est la seule
        # canonique. On ne la supprime pas du dump, seulement de la DB de
        # génération ; le nom réel ``randputf-X`` est conservé pour les liens.
        if not name.startswith(_RANDPUTF_PREFIX) and name in db.canonical_recipes:
            continue
        db.recipes[name] = RecipeRef(
            name=name,
            category=entry.get("category") or "",
            ingredients=tuple(_parse_stack(i) for i in entry.get("ingredients", [])),
            products=tuple(_parse_stack(p) for p in (entry.get("products") or entry.get("results") or [])),
            energy=float(entry.get("energy", 0.5)),
            main_product=str(entry.get("main_product") or ""),
            enabled=entry.get("enabled"),
            hidden=entry.get("hidden"),
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
    """Nom du sous-groupe d'un prototype, tolérant aux deux formats du dump.

    ``entry["subgroup"]`` peut être une chaîne ou un objet ``{"name": ...}``
    (selon la version de l'exporteur). Retourne le nom, ou ``""`` si le champ
    est absent ou vide.
    """
    group = entry.get("subgroup")
    if isinstance(group, dict):
        return group.get("name", "")
    return group or ""


def _number(raw, default: float | None = None) -> float | None:
    if raw is None:
        return default
    if isinstance(raw, dict):
        raw = raw.get("value")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _fuel_value(raw) -> float | None:
    """Normalise une valeur énergétique du dump en nombre de joules.

    Accepte ``None`` (retourne ``None``), un dict ``{"value": ...}`` (retourne
    sa valeur, ``None`` si nulle) ou un nombre/chaîne convertible (retourne le
    ``float``). Une valeur non convertible donne ``None`` au lieu de lever.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return float(raw.get("value", 0)) or None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_stack(stack: dict) -> tuple:
    """Convertit une ligne ingrédient/produit du dump en tuple canonique.

    Retourne ``(type, name, amount)`` avec ``type`` par défaut ``"item"``,
    ``name`` par défaut ``""`` et ``amount`` converti en ``float`` (1 si
    absent). Utilisé pour les ingrédients comme pour les produits.
    """
    return (stack.get("type", "item"), stack.get("name", ""), float(stack.get("amount", 1)))


def _entity_flags(entry: dict) -> set[str]:
    raw = entry.get("flags")
    if isinstance(raw, dict):
        return {str(name) for name, active in raw.items() if active}
    if isinstance(raw, (list, tuple, set)):
        return {str(flag) for flag in raw}
    return set()


def environmental_items_from_dump(dump: dict) -> set[str]:
    """Items récoltables déduits des prototypes d'entités du dump.

    Une entité posable sur l'eau (``placeable-water``) dont l'item porte le
    même nom est une ressource environnementale. Les dumps sans ``flags``
    retombent sur le type ``fish`` ; le lien vanille ``fish`` → ``raw-fish``
    reste couvert par ``ENVIRONMENTAL_ITEMS``.
    """
    items = dump.get("items") or {}
    derived: set[str] = set()
    for name, entry in (dump.get("entities") or {}).items():
        if not isinstance(entry, dict) or str(name) not in items:
            continue
        flags = _entity_flags(entry)
        water = "placeable-water" in flags if flags else entry.get("type") == "fish"
        if water:
            derived.add(str(name))
    return derived | {str(name) for name in ENVIRONMENTAL_ITEMS if name in items}


def _is_environmental_item(
    name: str, subgroup: str, itype: str, derived: set[str] | None = None
) -> bool:
    """Item récoltable à la main : liste vanilla et entités aquatiques du dump."""
    return name in ENVIRONMENTAL_ITEMS or bool(derived and name in derived)


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
    raw_speed = e.get("crafting_speed")
    crafting_speed = float(raw_speed) if raw_speed is not None else None
    productivity = float(e.get("productivity") or 0.0)
    lab_inputs = e.get("lab_inputs") or []
    rocket_parts = e.get("rocket_parts_required")
    target_temp = e.get("target_temperature")
    max_power = float(e.get("max_power_output") or 0)
    energy_prod = float((e.get("energy_source") or {}).get("production") or 0)
    energy_usage = _number(e.get("energy_usage"))
    mining_speed = _number(e.get("mining_speed"))
    buffer_capacity = _number(energy_src.get("buffer_capacity"), 0.0) or 0.0
    has_heat = bool(e.get("has_heat_output"))
    supply_area = e.get("supply_area_distance")
    pumping_speed = e.get("pumping_speed")
    pumped_fluid = e.get("pumped_fluid")
    pumped_fluids = frozenset(str(f) for f in (e.get("pumped_fluids") or ()))
    if not pumped_fluids and pumped_fluid:
        pumped_fluids = frozenset({str(pumped_fluid)})
    # Capacité posée par l'extracteur : machine à auto-sélection de recette
    # (interface sans sélecteur). Jamais recalculée ici.
    auto_select = bool(e.get("auto_select"))

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
    # entree (offshore-pump, pumpjack) ou categories de minage. En 2.1,
    # ``pumping_speed`` a disparu de l'offshore-pump : une source 'void' avec
    # une sortie fluide reste structurellement un extracteur.
    is_void_fluid_source = energy_type == "void" and fluid_in == 0 and fluid_out > 0
    is_extractor = bool(
        resource_categories
        or pumped_fluid
        or pumped_fluids
        or (pumping_speed is not None and fluid_in == 0 and fluid_out > 0)
        or is_void_fluid_source
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

    if pumped_fluid or pumped_fluids:
        medium = "lake"
    elif "basic-fluid" in resource_categories:
        medium = "deposit"
    elif functional == "extractor" and fluid_out > 0 and not resource_categories:
        # Sortie de fluide sans categorie de minage = source de lac (offshore-pump).
        medium = "lake"
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
    is_energy_storage = is_accumulator or (
        buffer_capacity > 0
        and entity_type != "roboport"
        and not (is_research or is_crafter or is_generator or is_distribution or is_extractor)
    )
    is_offgrid = produces_electricity and (
        energy_type != "electric" or entity_type == "solar-panel"
    )
    # Consomme du courant : source 'electric' SANS être producteur ni stockeur.
    consumes_electricity = (
        energy_type == "electric" and not produces_electricity and not is_accumulator
    )
    is_lake_extractor = is_extractor and medium == "lake"
    is_deposit_extractor = is_extractor and medium == "deposit"
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
    is_offshore_pump = is_lake_extractor  # seule source d'eau du vanilla
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
        is_lake_extractor=is_lake_extractor,
        is_deposit_extractor=is_deposit_extractor,
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
        auto_select=auto_select,
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
        has_pumping=bool(pumped_fluid or pumped_fluids) or (pumping_speed is not None and fluid_in == 0 and fluid_out > 0),
        has_fluid_input=fluid_in > 0,
        has_fluid_output=fluid_out > 0,
        has_fuel=energy_type == "burner",
        has_target_temperature=target_temp is not None,
        has_rocket_parts=bool(rocket_parts),
        crafting_categories=craft_categories,
        resource_categories=resource_categories,
        crafting_speed=crafting_speed,
        productivity=productivity,
        energy_type=energy_type,
        energy_usage=energy_usage,
        mining_speed=mining_speed,
        buffer_capacity=buffer_capacity,
        fuel_categories=tuple(energy_src.get("fuel_categories") or ()),
        pumped_fluid=pumped_fluid,
        pumped_fluids=pumped_fluids,
        item_input_slots=int(e.get("ingredient_count") or 0),
        fluid_inputs=fluid_in,
        fluid_outputs=fluid_out,
        produces_heat=is_heat_source,
        produces_electricity=produces_electricity,
        directives=directives,
    )


def summarize_db(db: VanillaDB) -> str:
    """Résume le contenu d'une base vanilla.

    ``db`` est la base parsée ; le résultat est une chaîne multi-lignes avec les compteurs d'items, fluides, bâtiments par tag et recettes. Sert à l'audit de parse (``randputf parse``).
    """
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
