"""Export de la seed vers le dossier du mod.

Ecrit deux fichiers :
- seed.json : source de vérité (validation, partage, debug) ;
- seed.lua  : miroir généré (return {...}) que data.lua charge nativement,
  evitant tout parseur JSON en data-stage.

Structure seed :
{
  meta: {seed, generator_version, factorio_version},
  pools: {item_resources: [...], fluid_resources: [...],
          raw_resources: [...], environmental_resources: [...],
          vehicle_weapons: [<items gun de la pool montée §7>],
          vehicle_range_scaling: {base_size, scale}},
  map:   {patches: [{kind, resource, richness,
                     center:{x,y}, count, well_seed, cluster_radius  -- gisement §6.5 (item ET fluide)
                    }],
          lakes: [{resource, richness}]}, -- lacs de fluide §7.5
  starter_kit: [{type, name, count}],
  free_researches: [...],
  recipes: [{name, ingredients:[{type,name,amount,produced_by?}],
             results:[{type,name,amount}], crafted_in?, category?,
             on_the_spot_unlock?}],
  technologies: [{id, localised_name, prerequisites, unit{count,ingredients},
                  effects}],
  progression_order: [...],
  vehicle_armament: {<véhicule>: [<items gun assignés §7>]} -- pool cachée :
                 ne sert QU'à l'assignation ; le mod CLONE chaque arme pour
                 le véhicule (jamais craftée).
  building_fluid_assignments: {<bâtiment>: {input: <fluide>, output?: <fluide>}}
                 -- §6/§10 : fluides assignés aux bâtiments à comportement fixe
                 (turbines, boilers). Le mod applique les filters et tooltips.
}
"""

from __future__ import annotations

import json
from pathlib import Path

from tool.audit.difficulty import compute_difficulty
from tool.common.db import SLOT_FLUID, SLOT_ITEM
from tool.parsers.vanilla import (
    canonical_recipe_map,
    environmental_items_from_dump,
    inject_pumped_fluids,
    is_hidden_prototype,
    rocket_chain_from_dump,
    rocket_meta_from_chain,
    science_pack_names,
    science_pack_order,
)

LUA_HEADER = "-- Généré par randputF tool. Ne pas éditer à la main.\n"


def write_seed_files(seed: dict, out_dir: Path) -> None:
    """Exporte la seed en ``seed.json`` + ``seed.lua`` (plus labels locale)
    dans ``out_dir``. Injecte au passage ``seed["difficulty"]`` : le total de
    l'ardoise, affiché par le mod au spawn (calculé à l'export, jamais
    pendant la pipeline)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Difficulté injectée à l'export (jamais dans le pipeline) : le mod
    # l'affiche en chat au spawn. ``difficulty`` = total de l'ardoise.
    total = compute_difficulty(seed).total
    exported = dict(seed)
    if "meta" in seed:
        meta = dict(seed.get("meta") or {})
        rocket = meta.get("rocket")
        if isinstance(rocket, dict):
            rocket = dict(rocket)
            rocket.pop("rocket_recipe_data", None)
            meta["rocket"] = rocket
        exported["meta"] = meta
    exported["difficulty"] = {
        "total": total,
        "total_k": int(round(total / 1000)),
    }
    (out_dir / "seed.json").write_text(
        json.dumps(exported, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "seed.lua").write_text(
        LUA_HEADER + "return " + _to_lua(exported) + "\n", encoding="utf-8"
    )
    locale_en = out_dir.parent / "locale" / "en"
    locale_fr = out_dir.parent / "locale" / "fr"
    for locale_dir in (locale_en, locale_fr):
        if locale_dir.exists():
            locale_dir.mkdir(parents=True, exist_ok=True)
            (locale_dir / "seed.cfg").write_text(
                _locale_cfg(exported), encoding="utf-8"
            )


def _locale_cfg(seed: dict) -> str:
    """[autoplace-control-names] pour chaque patch (alias index -> resource) et
    chaque lac (§7.5, contrôle `randputf-lac-ctl-N` -> fluide)."""
    lines = ["[autoplace-control-names]"]
    seen = {}
    index = 0
    for patch in (seed.get("map") or {}).get("patches") or []:
        resource = patch.get("resource", "")
        if resource in seen:
            continue
        seen[resource] = True
        index += 1
        lines.append(f"randputf-ctl-{index}={resource}")
    for i, lake in enumerate((seed.get("map") or {}).get("lakes") or [], start=1):
        lines.append(f"randputf-lac-ctl-{i}={lake.get('resource', '')}")
    return "\n".join(lines) + "\n"


def _to_lua(value, indent: int = 0) -> str:
    """Sérialise une valeur Python en littéral Lua indenté.

    Gère dicts (clés via ``_lua_key``), listes/tuples, booléens, nombres,
    ``None`` (→ ``nil``) et chaînes (échappement ``\\``, ``"``, saut de ligne).
    ``indent`` est le niveau d'indentation courant. Retourne le texte Lua.
    """
    pad = "  " * indent
    child_pad = "  " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key, item in value.items():
            lua_key = _lua_key(key)
            lines.append(f"{child_pad}{lua_key} = {_to_lua(item, indent + 1)},")
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    if isinstance(value, (list, tuple)):
        if not value:
            return "{}"
        lines = ["{"]
        for item in value:
            lines.append(f"{child_pad}{_to_lua(item, indent + 1)},")
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "nil"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _lua_key(key: str) -> str:
    """Rend une clé de table Lua valide.

    Retourne la clé nue si c'est un identifiant ASCII ne commençant pas par un
    chiffre, sinon la forme entre crochets ``["..."]`` (sans échappement
    supplémentaire, les clés étant supposées sans guillemet).
    """
    if key.isidentifier() and key.isascii() and not key[0].isdigit():
        return key
    return f'["{key}"]'


def _extract_entities(dump: dict) -> dict[str, dict]:
    """Retourne le dict des entités du dump indexé par nom.

    Gère les entités avec ou sans clé 'name' : si 'name' est présent,
    on l'utilise comme clé ; sinon on recourt au nom tel que apparait
    dans la structure (ex: 'iron-ore', 'crude-oil') en récupérant la
    première clé de dictionnaire disponible.
    """
    entities: dict[str, dict] = {}
    for name, entry in (dump.get("entities") or {}).items():
        if isinstance(entry, dict):
            # Utiliser 'name' si présent, sinon la première clé du dict
            key = entry.get("name", name)
            entities[str(key)] = entry
    return entities


def _slot_type(entry: dict, name: str, dump: dict) -> str:
    """Conserve le type de slot déclaré par le dump, avec repli par prototype."""
    kind = entry.get("type")
    if kind in (SLOT_ITEM, SLOT_FLUID):
        return str(kind)
    if name in (dump.get("fluids") or {}):
        return SLOT_FLUID
    return SLOT_ITEM


def _fluidbox_recipes(dump: dict) -> list[dict]:
    """Conversions de fluides déduites des ``fluidboxes`` de toutes les entités.

    Toute entité qui déclare des filtres d'entrée et de sortie distincts décrit
    une conversion réelle du dump. Les boucles de transport (même fluide en
    entrée et sortie, ``input-output``) ne produisent rien.
    """
    out: list[dict] = []
    for name, entry in _extract_entities(dump).items():
        detail = (entry.get("fluidboxes") or {}).get("detail") or {}
        inputs: list[dict] = []
        results: list[dict] = []
        seen_inputs: set[str] = set()
        seen_outputs: set[str] = set()
        for part in detail.values():
            if not isinstance(part, dict) or not part.get("filter"):
                continue
            fluid = str(part["filter"])
            slot = {"type": SLOT_FLUID, "name": fluid, "amount": 100}
            production = part.get("production_type")
            if production in ("input", "input-output") and fluid not in seen_inputs:
                inputs.append(slot)
                seen_inputs.add(fluid)
            if production in ("output", "input-output") and fluid not in seen_outputs:
                results.append(slot)
                seen_outputs.add(fluid)
        if not inputs or not results or seen_outputs <= seen_inputs:
            continue
        suffix = "-".join(str(result["name"]) for result in results)
        out.append(
            {
                "name": f"dump-{name}-{suffix}",
                "results": results,
                "ingredients": inputs,
                "enabled": True,
                "hidden_active": False,
                "energy": 0,
                "crafting_categories": [],
                "crafting_speed": 1,
                "crafted_in": name,
            }
        )
    return out


def _extract_recipes(dump: dict) -> list[dict]:
    """Extrait les recettes du dump pour le seed vanilla.

    ``dump`` est le JSON de l'exporteur. Exclut les barils sans consommateur hors barillage (un baril réellement utilisé comme intermédiaire moddé est conservé), Kovarex, le retraitement du combustible nucléaire, les recettes paramétrées et les prototypes neutralisés (``hidden`` et désactivés). Les recettes cachées encore actives, ou débloquées par une tech, sont conservées : les mods les utilisent comme vraies voies de production (ex. fusée). Pour un dump moddé, ``randputf-X`` remplace la recette vanilla ``X`` ; pour un ancien dump sans champs d'état, le même choix est déduit du préfixe. Retourne une liste de recettes normalisées (nom, catégorie, ingrédients, produits).
    """
    recipes: list[dict] = []
    all_recipes = dump.get("recipes") or {}
    tech_unlocked_recipes = {
        str(effect.get("recipe"))
        for tech in (dump.get("technologies") or {}).values()
        if isinstance(tech, dict)
        for effect in tech.get("effects") or []
        if isinstance(effect, dict)
        and effect.get("type") == "unlock-recipe"
        and effect.get("recipe")
    }
    canonical = canonical_recipe_map(all_recipes)
    barrel_items = {
        str(name)
        for name, item in (dump.get("items") or {}).items()
        if isinstance(item, dict) and item.get("subgroup") == "barrel"
    }
    if "barrel" in (dump.get("items") or {}):
        barrel_items.add("barrel")
    barrel_products: dict[str, set[str]] = {}
    for name, entry in all_recipes.items():
        if not isinstance(entry, dict):
            continue
        barrel_products[str(name)] = {
            str(product.get("name"))
            for product in entry.get("products") or entry.get("results") or []
            if isinstance(product, dict) and product.get("name") in barrel_items
        }
    barrel_conversions = {
        str(name)
        for name, products in barrel_products.items()
        if name != "barrel"
        and products
        and (
            "barrel" in name
            or "barrel" in str((all_recipes.get(name) or {}).get("category") or "")
        )
    }
    pumped_fluids: set[str] = set()
    for entry in (dump.get("entities") or {}).values():
        if not isinstance(entry, dict):
            continue
        if entry.get("pumped_fluid"):
            pumped_fluids.add(str(entry["pumped_fluid"]))
        pumped_fluids.update(str(fluid) for fluid in entry.get("pumped_fluids") or ())

    needed_barrels: set[str] = set()
    needed_fluids: set[str] = set()
    primary_barrels: set[str] = set()
    for name, entry in all_recipes.items():
        if name in barrel_conversions or not isinstance(entry, dict):
            continue
        for ingredient in entry.get("ingredients") or []:
            if not isinstance(ingredient, dict) or not ingredient.get("name"):
                continue
            if ingredient.get("name") in barrel_items:
                needed_barrels.add(str(ingredient["name"]))
            if _slot_type(ingredient, str(ingredient["name"]), dump) == SLOT_FLUID:
                needed_fluids.add(str(ingredient["name"]))
        for product in entry.get("products") or entry.get("results") or []:
            if not isinstance(product, dict) or not product.get("name"):
                continue
            if _slot_type(product, str(product["name"]), dump) == SLOT_FLUID:
                needed_fluids.add(str(product["name"]))
        primary_barrels.update(barrel_products.get(str(name), set()))
    for name, entry in all_recipes.items():
        if not isinstance(entry, dict):
            continue
        if name.startswith("randputf-randputf-"):
            continue
        # Un dump moddé expose l'état réel : les prototypes neutralisés restent
        # dans le JSON (liens intacts) mais ne participent pas à la génération.
        hidden_active = is_hidden_prototype(entry)
        if hidden_active and not entry.get("enabled") and name not in tech_unlocked_recipes:
            continue
        # Repli pour les dumps anciens sans hidden : randputf-X remplace X.
        if not name.startswith("randputf-") and name in canonical:
            continue
        if any(part in name for part in ("kovarex", "nuclear-fuel-reprocessing", "parameter-0")):
            continue
        if name in barrel_conversions:
            produced_barrels = barrel_products[name]
            conversion_fluids = {
                str(res.get("name"))
                for res in (entry.get("products") or entry.get("results") or [])
                if isinstance(res, dict)
                and res.get("name")
                and _slot_type(res, str(res["name"]), dump) == SLOT_FLUID
            }
            conversion_fluids.update(
                str(ing.get("name"))
                for ing in entry.get("ingredients") or []
                if isinstance(ing, dict)
                and ing.get("name")
                and _slot_type(ing, str(ing["name"]), dump) == SLOT_FLUID
            )
            useful_fluids = (conversion_fluids & needed_fluids) - pumped_fluids
            if produced_barrels & primary_barrels and not useful_fluids:
                continue
            if not (produced_barrels & needed_barrels) and not useful_fluids:
                continue
        category = entry.get("category")
        if category and category.startswith("parameter-"):
            continue
        products = entry.get("products") or entry.get("results") or []
        results = [
            {
                "type": _slot_type(p, str(p.get("name")), dump),
                "name": p.get("name"),
                "amount": p.get("amount", 1),
            }
            for p in products
            if isinstance(p, dict) and p.get("name")
        ]
        if not results:
            continue
        ingredients = [
            {
                "type": _slot_type(ing, str(ing.get("name")), dump),
                "name": ing.get("name"),
                "amount": ing.get("amount", 0),
            }
            for ing in (entry.get("ingredients") or [])
            if isinstance(ing, dict) and ing.get("name")
        ]
        buildings = _building_by_category(dump)
        recipes.append(
            {
                "name": name,
                "results": results,
                "ingredients": ingredients,
                "enabled": bool(entry.get("enabled", False)),
                "hidden_active": hidden_active and name not in tech_unlocked_recipes,
                "energy": entry.get("energy", 0),
                "crafting_categories": entry.get("crafting_categories") or [],
                "crafting_speed": entry.get("crafting_speed", 1),
                "main_product": str(entry.get("main_product") or ""),
                "crafted_in": buildings.get(entry.get("category")),
            }
        )
    return recipes


def _extract_technologies(dump: dict) -> list[dict]:
    """Extrait et normalise les technologies du dump.

    Chaque technologie conserve son identifiant, son nom localisé, ses
    prérequis, son unité de recherche, ses effets et son éventuel
    déclencheur, dans une forme directement exploitable par la seed.
    """
    techs: list[dict] = []
    for name, entry in (dump.get("technologies") or {}).items():
        if not isinstance(entry, dict):
            continue
        if name.startswith("randputf-randputf-"):
            continue
        if is_hidden_prototype(entry):
            continue
        unit = entry.get("unit") or {}
        unit_count = unit.get("count", 0)
        unit_time = unit.get("time", 0)
        ingredients = [
            {"name": ing.get("name"), "amount": ing.get("amount", 0)}
            for ing in (unit.get("ingredients") or [])
            if isinstance(ing, dict) and ing.get("name")
        ]
        techs.append(
            {
                "id": name,
                "localised_name": name.replace("-", " ").title(),
                "prerequisites": [pr for pr in (entry.get("prerequisites") or []) if isinstance(pr, str)],
                "unit": {"count": unit_count, "time": unit_time, "ingredients": ingredients},
                "effects": entry.get("effects") or [],
                "research_trigger": entry.get("research_trigger"),
                "research_unit_count_formula": entry.get("research_unit_count_formula"),
            }
        )
    return techs


def _topo_sort(tech_ids: list[str], prerequisites: dict[str, list[str]]) -> list[str]:
    """Ordonne les technologies par dépendances.

    ``tech_ids`` est l'ensemble des techs et ``prerequisites`` associe chaque tech à ses prérequis. Retourne une liste déterministe : à chaque étape, la plus petite tech dont tous les prérequis connus sont déjà sortis.
    """
    known = set(tech_ids)
    indegree = {tid: 0 for tid in tech_ids}
    successors: dict[str, list[str]] = {tid: [] for tid in tech_ids}
    for tid in tech_ids:
        for prereq in prerequisites.get(tid, []):
            if prereq in known:
                indegree[tid] += 1
                successors[prereq].append(tid)

    ready = sorted(tid for tid, deg in indegree.items() if deg == 0)
    order: list[str] = []
    while ready:
        tid = ready.pop(0)
        order.append(tid)
        for succ in successors[tid]:
            indegree[succ] -= 1
            if indegree[succ] == 0:
                ready.append(succ)
        ready.sort()

    remaining = [tid for tid in tech_ids if tid not in set(order)]
    order.extend(sorted(remaining))
    return order


def build_vanilla_seed(dump: dict) -> dict:
    """Construit un seed vanilla compatible avec analyze_playthrough / analyze_complexity.

    À partir du dump Factorio (dump.json), retourne un dict seed contenant :
    - meta : seed, generator_version
    - pools : raw_resources (items + fluides bruts)
    - technologies : liste techs avec prerequisites + unit
    - progression_order : ordre topologique des techs
    - recipes : liste des recettes utiles
    - entities : entités du dump indexées par nom
    - items / fluids : dictionnaires d'infos d'items/fluides
    """
    # Entonnoir unique du dump vanilla : toutes les entrees qui consomment le
    # dump brut (rapport, complexite, partie simulee) passent par ici, puis
    # les entites resolues se propagent par mutation (meme dict).
    inject_pumped_fluids(dump)
    science = science_pack_names(dump)
    entities = _extract_entities(dump)
    recipes = _extract_recipes(dump)
    all_recipes = dump.get("recipes") or {}
    for recipe in recipes:
        raw = all_recipes.get(recipe["name"]) or {}
        if raw.get("category") == "crafting":
            recipe["crafted_in"] = None
    recipes.extend(_fluidbox_recipes(dump))
    technologies = _extract_technologies(dump)

    # Catégories de forage déduites des foreuses du dump (solide vs fluide).
    solid_categories: set[str] = set()
    fluid_categories: set[str] = set()
    for entry in entities.values():
        if entry.get("type") != "mining-drill":
            continue
        categories = entry.get("resource_categories") or []
        boxes = entry.get("fluidboxes")
        detail = boxes.get("detail") if isinstance(boxes, dict) else None
        fluid_drill = bool(detail) and any(
            isinstance(box, dict) and box.get("production_type") == "output"
            for box in detail.values()
        )
        (fluid_categories if fluid_drill else solid_categories).update(categories)
    default_solid = sorted(solid_categories)[0] if solid_categories else None
    default_fluid = sorted(fluid_categories)[0] if fluid_categories else None

    # Collecter les noms de ressources brutes et items/fluides
    raw_set: set[str] = set()
    item_set: set[str] = set()
    fluid_set: set[str] = set()

    for name, entry in entities.items():
        etype = entry.get("type")
        if etype == "resource":
            raw_set.add(name)
        elif etype == "item":
            item_set.add(name)
        elif etype == "fluid":
            fluid_set.add(name)

    # Items et fluides de premier niveau du dump.
    for name, entry in (dump.get("items") or {}).items():
        if isinstance(entry, dict):
            item_set.add(str(name))
    for name, entry in (dump.get("fluids") or {}).items():
        if isinstance(entry, dict):
            fluid_set.add(str(name))

    items_dict: dict[str, dict] = {}
    fluids_dict: dict[str, dict] = {}
    for name, entry in (dump.get("items") or {}).items():
        if isinstance(entry, dict):
            item = {
                "type": "item",
                "subgroup": entry.get("subgroup"),
                "stack_size": entry.get("stack_size"),
            }
            # Produits de lancement (ex. satellite -> packs de science) :
            # gardés tels quels, c'est la source de vérité du lancement.
            launch_products = [
                {"name": str(product["name"]), "amount": product.get("amount", 1)}
                for product in entry.get("rocket_launch_products") or []
                if isinstance(product, dict) and product.get("name")
            ]
            if launch_products:
                item["rocket_launch_products"] = launch_products
            item["used_by_labs"] = bool(entry.get("used_by_labs"))
            item["science_capacity"] = int(entry.get("science_capacity") or 0)
            item["is_science_pack"] = str(name) in science
            items_dict[str(name)] = item
    for name, entry in (dump.get("fluids") or {}).items():
        if isinstance(entry, dict):
            fluid_entry = {
                "type": "fluid",
                "subgroup": entry.get("subgroup"),
                "stack_size": entry.get("stack_size"),
                "default_temperature": entry.get("default_temperature", 15),
            }
            # Un fluide peut etre un pack de science (mods) : meme fait que
            # les items, ce que les recherches/lab consomment.
            fluid_entry["is_science_pack"] = str(name) in science
            fluids_dict[str(name)] = fluid_entry

    # L'extracteur peut fournir ``mineable_properties`` (temps, produits,
    # fluide requis) : on le normalise vers les champs attendus par le moteur.
    # Toute entité qui le déclare compte (gisements, arbres…).
    for name, entry in list(entities.items()):
        props = entry.get("mineable_properties")
        if not isinstance(props, dict):
            continue
        products = [
            {"name": str(product["name"]), "amount": product.get("amount", 1)}
            for product in props.get("products") or []
            if isinstance(product, dict) and product.get("name")
        ]
        if products and not entry.get("mineable_products"):
            entry["mineable_products"] = products
        if entry.get("mineable_time") is None and props.get("mining_time") is not None:
            entry["mineable_time"] = props["mining_time"]
        if props.get("required_fluid") and not entry.get("required_fluid"):
            entry["required_fluid"] = props["required_fluid"]
        if (
            props.get("fluid_amount") is not None
            and entry.get("fluid_amount") is None
        ):
            entry["fluid_amount"] = props["fluid_amount"]
        # Catégorie de forage : les gisements seulement (les arbres se
        # récoltent à la main, sans foreuse).
        if entry.get("type") == "resource" and not entry.get("resource_category"):
            names = [product["name"] for product in products] or [str(name)]
            is_fluid = any(product_name in fluids_dict for product_name in names)
            category = default_fluid if is_fluid else default_solid
            if category:
                entry["resource_category"] = category

    # Le dump ne décrit un gisement que par ``{"type": "resource"}`` : on
    # complète produit et catégorie de forage à partir des foreuses. Le temps de
    # minage n'est repris que s'il existe réellement dans le dump : sinon on ne
    # l'invente pas (l'extracteur doit fournir ``mineable_time``).
    for name, entry in list(entities.items()):
        if entry.get("type") != "resource" or entry.get("mineable_products"):
            continue
        product = str(name)
        category = default_fluid if product in fluids_dict else default_solid
        synthesized = {
            **entry,
            "mineable_products": [{"name": product, "amount": 1}],
            "resource_category": category,
        }
        if entry.get("mineable_time") is not None:
            synthesized["mineable_time"] = entry["mineable_time"]
        entities[name] = synthesized

    # Ressources brutes : produits minables déclarés par le dump (gisements,
    # arbres compris) et fluides pompés depuis la carte (``pumped_fluid``).
    # Rien n'est codé en dur.
    for entry in entities.values():
        for product in entry.get("mineable_products") or []:
            product_name = (
                product.get("name") if isinstance(product, dict) else product
            )
            if product_name:
                raw_set.add(str(product_name))
        pumped = entry.get("pumped_fluid")
        if pumped:
            raw_set.add(str(pumped))
        for fluid in entry.get("pumped_fluids") or ():
            raw_set.add(str(fluid))

    recipes = [
        recipe
        for recipe in recipes
        if not recipe.pop("hidden_active", False)
        or all(ing["name"] in raw_set for ing in recipe["ingredients"])
    ]

    # Technologies prereq mapping pour topo sort
    prereqs: dict[str, list[str]] = {
        t["id"]: t["prerequisites"] for t in technologies
    }
    progression = _topo_sort(
        [t["id"] for t in technologies], prereqs
    )
    tech_by_id = {t["id"]: t for t in technologies}
    technologies = [tech_by_id[tid] for tid in progression if tid in tech_by_id]

    meta = dump.get("meta") or {}
    rocket = rocket_meta_from_chain(rocket_chain_from_dump(dump))
    science_order = science_pack_order(dump, science)
    return {
        "meta": {
            "seed": meta.get("seed", "vanilla"),
            "origin": "dump",
            "generator_version": meta.get("game_version", "2.0"),
            "science_packs": sorted(science),
            "science_pack_order": list(science_order),
            "rocket": rocket,
        },
        "pools": {
            "item_resources": sorted(item_set),
            "fluid_resources": sorted(fluid_set),
            "raw_resources": sorted(raw_set),
            "environmental_resources": sorted(environmental_items_from_dump(dump)),
        },
        "technologies": technologies,
        "progression_order": progression,
        "recipes": recipes,
        "entities": entities,
        "items": items_dict,
        "fluids": fluids_dict,
        "starter_kit": [],
        "free_researches": [],
    }


def tag_progression(seed: dict, analysis: dict) -> dict:
    """Tague la CHAÎNE DE PROGRESSION sur le seed, depuis l'analyse.

    « Fait avancer le jeu » = tout ce que la partie doit extraire ou
    produire pour mener les recherches à terme : packs de science,
    ingrédients des packs, bâtiments qui les fabriquent et leurs propres
    ingrédients, brut miné/pompé. C'est la fermeture du graphe de
    complexité (``item_stats`` de l'analyse), pas une liste en dur.

    Pose ``is_progression`` (vrai/faux explicite) sur chaque item/fluide du
    seed ; ``is_science_pack`` est déjà posé par ``build_vanilla_seed``
    depuis les faits du dump. Retourne le résumé : noms de la fermeture,
    total, dont packs de science."""
    stats = (analysis or {}).get("item_stats") or {}
    closure = {str(name) for name in stats}
    packs = 0
    for section in ("items", "fluids"):
        entries = seed.get(section) or {}
        if not isinstance(entries, dict):
            continue
        for name, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            in_closure = str(name) in closure
            entry["is_progression"] = in_closure
            if in_closure and entry.get("is_science_pack"):
                packs += 1
    return {"names": sorted(closure), "count": len(closure), "packs": packs}


def _building_by_category(dump: dict) -> dict[str, str]:
    """Choisit un atelier de référence par catégorie de recette.

    On prend l'atelier débloqué le plus tôt, puis le plus lent, pour rester
    proche d'une partie ``normale`` : ``assembling-machine-1`` pour ``crafting``,
    ``stone-furnace`` pour ``smelting``, etc. ``character`` est ignoré sauf pour
    ``hand-crafting`` afin que les recettes d'atelier ne soient pas comptées à la main.
    Les variantes d'entité (``*-turd``/``*-legacy``) sont résolues vers
    l'item qui les pose : ``crafted_in`` doit rester un item craftable.
    """
    from collections import defaultdict
    options: dict[str, list[tuple[bool, bool, int, float, str, str | None]]] = defaultdict(list)
    entities = _extract_entities(dump)
    recipes = dump.get("recipes") or {}
    items = dump.get("items") or {}
    techs = dump.get("technologies") or {}
    tech_order = {
        tid: index
        for index, tid in enumerate(
            _topo_sort(
                list(techs),
                {
                    tid: (tech.get("prerequisites") or [])
                    for tid, tech in techs.items()
                    if isinstance(tech, dict)
                },
            )
        )
    }
    unlock_rank: dict[str, int] = {}
    for tid, tech in techs.items():
        if not isinstance(tech, dict):
            continue
        rank = tech_order.get(tid, len(tech_order))
        for effect in tech.get("effects") or []:
            if not isinstance(effect, dict) or effect.get("type") != "unlock-recipe":
                continue
            recipe = str(effect.get("recipe") or "")
            if recipe:
                unlock_rank[recipe] = min(unlock_rank.get(recipe, rank), rank)
    far = len(tech_order) + 1
    craftable = {
        product.get("name")
        for recipe in recipes.values()
        if isinstance(recipe, dict) and not recipe.get("hidden")
        for product in recipe.get("products") or []
        if product.get("type") in (None, "item")
    }

    def placing_item(name: str, entry: dict) -> str | None:
        item = items.get(name)
        if isinstance(item, dict):
            placed = item.get("place_result")
            if placed in (None, "", name):
                return name
        for candidate in entry.get("items_to_place_this") or []:
            candidate = str(candidate)
            if isinstance(items.get(candidate), dict):
                return candidate
        return None

    for name, entry in entities.items():
        if not isinstance(entry, dict):
            continue
        categories = entry.get("crafting_categories") or []
        speed = float(entry.get("crafting_speed") or 0)
        item_name = placing_item(name, entry)
        rank = min(
            unlock_rank.get(name, far),
            unlock_rank.get(item_name, far) if item_name else far,
        )
        for category in categories:
            if category in {"hand-crafting"}:
                continue
            options[category].append(
                (
                    item_name is None,
                    item_name not in craftable,
                    rank,
                    round(speed, 6),
                    name,
                    item_name,
                )
            )

    chosen: dict[str, str] = {}
    for category, candidates in options.items():
        candidates.sort(
            key=lambda cand: (
                cand[0],
                cand[1],
                not bool((recipes.get(cand[4]) or {}).get("enabled", False)),
                cand[2],
                cand[3],
                cand[5] or cand[4],
                cand[4],
            )
        )
        chosen[category] = candidates[0][5] or candidates[0][4]
    return chosen
