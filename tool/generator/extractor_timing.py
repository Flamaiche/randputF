"""C3 — déblocage « juste-au-besoin » des extracteurs (niveau seed).

Passe post-récursion / post-ease (pipeline.generate_seed), juste avant la
deuxième passe de garantie d'usage (usage_pass). La tech gratuite
``randputf-starter-extraction`` débloque la recette de craft de TOUS les
extracteurs du run (patchs + lacs, §7/§7.5) — même ceux dont la ressource
n'est consommée qu'en profondeur de seed, ou jamais. C3 repositionne ces
claims d'unlock :

- ressource consommée dès le starter → l'extracteur reste (ou revient) dans
  ``randputf-starter-extraction`` (tech gratuite) ;
- ressource consommée plus tard → le claim est posé au PREMIER consommateur
  (``min(first-consumer, premier-usage-item)``). Si l'ATELIER qui fabrique
  l'extracteur a été planté plus profond par le balayage §9.6, on ne remonte
  PAS le contenu early (ni vers le kit) et on ne repousse pas la recette vers
  l'atelier : la RECETTE est RÉGÉNÉRÉE pour se coordonner avec le jalon
  ``target`` — ingrédients et fabricateur re-randomisés dans le pool obtenable
  à ``≤ target``, comme n'importe quelle recette (§7/§8) ;
- ressource jamais consommée → le claim part sur un step PAYANT tiré
  aléatoirement (stream RNG dédié et déterministe, façon balayage §9.6),
  toujours ≥ l'index de l'atelier.

D4bis (« forêt starter ») : une ressource consommée par la BOÎTE DU SPAWN —
fermeture des recettes des techs gratuites, déclencheur de la 1re tech payante,
fluide de la turbine du 1er générateur — garde TOUJOURS son extracteur à la
tech gratuite. La différer bloquerait la partie au spawn (pas d'électricité,
pas de lab) sur une chaîne acyclique qu'aucun §15 ne voit — c'est le rejoueur
(§15ter) qui l'a mesuré (~50 % de graines).

Seules les listes ``unlocks_recipes`` des macro-steps sont mutées : le graphe
produit→ingrédient reste intact, l'« unlock unique » (§13) est préservé.

Invariant garanti par construction : le claim est posé au plus tard des
CONTRAINTES DU JALON (atelier OU premier usage, §15) — l'extracteur n'est
JAMAIS débloqué après le moment où sa ressource est réellement nécessaire, et
son CORPS (ingrédients + atelier) est re-baké pour rester craftable à ce jalon
(le claim d'unlock n'est jamais que l'atelier, il est calé sur le besoin).
Quand le jalon est un jalon PRÉ-ÉLECTRIQUE (plateau des techs gratuites), le
re-tirage se confine au watershed sans électricité et à ce qui est obtenu
strictement AVANT le step (rien de débloqué au même step : le solveur §15
traite les unlocks d'un même step comme simultanés).

Sûreté (vérifiée, pas une mécanique) :
- la recette d'extracteur est FORCÉE au starter (``force=True``, ingrédients du
  watershed pré-élec) puis, si C3 la régénère pour un jalon pré-électrique,
  re-bakée DANS le watershed et sans atelier électrique (``x2_environmental``
  si le repli est handcraft, comme toute recette bootstrap) → craftable dès
  son claim sans réseau ;
- les science packs sont créés avec ``forbidden=raw_resources`` (§13) → la tech
  qui paie un claim ne dépend jamais de la ressource gateée (pas de circularité
  coût↔extraction) ;
- l'électricité est garantie au starter (§10) → un premier consommateur profond
  est forcément après le générateur : jamais d'extracteur électrique réclamé
  avant de pouvoir fonctionner.
"""

from __future__ import annotations

import logging
import random

from tool.common.db import (
    SLOT_FLUID,
    SLOT_ITEM,
    VanillaDB,
    has_hidden_recipe,
)
from tool.generator import recipes as _recipes_mod
from tool.generator.early_oracle import build_early_sources, compute_early_reachable
from tool.generator.recipes import (
    _ancestor_products,
    _bake_recipe,
    _is_atelier,
    _item_for_building,
    _recipe_category,
)
from tool.generator.usage_pass import _fits, _hosting_cycle, _self_hosted

log = logging.getLogger(__name__)

STARTER_EXTRACTION_ID = "randputf-starter-extraction"


def _extractor_resources(db: VanillaDB, state) -> dict[str, list[tuple[str, str]]]:
    """Recette d'extracteur -> ressources extraites (groupées par recette).

    Miroir de `starter_chain.build_tech_steps` (extractor_item_recipes) : les
    steps ``"type": "extract"`` portent resource + extracteur ; la recette
    canonique de l'item qui place l'extracteur est ``randputf-<item>``.
    """
    by_recipe: dict[str, list[tuple[str, str]]] = {}
    for step in state.steps:
        if step.get("type") != "extract":
            continue
        item = _item_for_building(db, step["extractor"])
        if item is None:
            continue
        res = step["resource"]
        by_recipe.setdefault(f"randputf-{item.name}", []).append(
            (res["type"], res["name"])
        )
    return by_recipe


def _claim_indexes(steps: list[dict]) -> dict[str, int]:
    """Index du PREMIER step qui réclame chaque recette — miroir de
    `usage_pass._claim_index` : une recette ``randputf-<x>`` est aussi réclamée
    par ``unlocks_buildings: [x]`` (les techs bâtiments, ex. génératrices)."""
    out: dict[str, int] = {}
    for index, step in enumerate(steps):
        for name in step.get("unlocks_recipes", []):
            out.setdefault(name, index)
        for building in step.get("unlocks_buildings", []):
            out.setdefault(f"randputf-{building}", index)
    return out


def _first_consumers(
    state, claim: dict[str, int], resources: set[tuple[str, str]]
) -> dict[tuple[str, str], int]:
    """Premier consommateur (index de claim) par ressource extraite.

    Une ressource absente du résultat n'est consommée par AUCUNE recette
    claimée — l'extracteur est alors « jamais utilisé » (fallback aléatoire).
    """
    first: dict[tuple[str, str], int] = {}
    for recipe in state.recipes:
        i = claim.get(recipe["name"])
        if i is None:
            continue
        for ing in recipe.get("ingredients", []):
            key = (ing.get("type"), ing.get("name"))
            if key not in resources:
                continue
            if key not in first or i < first[key]:
                first[key] = i
    return first


def _first_item_consumer(state, claim: dict[str, int], item_name: str) -> int | None:
    """Premier index de claim d'une recette qui consomme ``item_name`` comme
    ingrédient.

    C3 mesure l'usage d'un extracteur par la ressource qu'il EXTRAIT. Mais le
    bâtiment-extracteur lui-même est souvent un ingrédient d'autres recettes
    (ex. pumpjack×4 dans offshore-pump, EMD×N dans les variantes) : si sa
    recette de craft est différée au premier usage de la ressource extraite,
    elle peut arriver APRÈS une recette qui le consomme en tant que bâtiment →
    quantité intenable (rejoueur §15ter). La borne est donc le mini du premier
    usage de la ressource ET du premier usage du bâtiment comme ingrédient.
    """
    first: int | None = None
    for recipe in state.recipes:
        i = claim.get(recipe["name"])
        if i is None:
            continue
        for ing in recipe.get("ingredients", []):
            if ing.get("type") == SLOT_ITEM and ing.get("name") == item_name:
                if first is None or i < first:
                    first = i
    return first


def _atelier_claim(
    state, db: VanillaDB, claim: dict[str, int], kit: set[str], recipe_name: str
) -> int:
    """Index du déblocage de l'atelier qui fabrique ``recipe_name`` (0 si kit
    ou sans atelier). L'extracteur ne peut être débloqué avant que l'atelier
    qui le fabrique soit disponible (U2)."""
    recipe = next((r for r in state.recipes if r["name"] == recipe_name), None)
    if recipe is None:
        return 0
    crafted_in = recipe.get("crafted_in")
    if not crafted_in or crafted_in in kit:
        return 0
    return claim.get(f"randputf-{crafted_in}", 0)


def _kit_buildings(starter, db: VanillaDB) -> set[str]:
    """Bâtiments fournis par le kit de départ (réputés débloqués en tech 0)."""
    kit: set[str] = set()
    for entry in starter.kit:
        if entry.get("type") != "item":
            continue
        item = db.items.get(entry["name"])
        if item is not None and item.place_result in db.buildings:
            kit.add(item.place_result)
    return kit


def _move_claim(source: int, target: int, steps: list[dict], recipe: str) -> None:
    """Déplace ``recipe`` (``randputf-<x>``) de steps[source] vers steps[target]
    (unlock unique). Le claim peut provenir de ``unlocks_recipes`` (le nom de
    recette ``randputf-<x>``) OU de ``unlocks_buildings`` (le bâtiment ``<x>``) —
    on retire des deux listes côté source, puis on pose la recette côté cible."""
    if source == target:
        return
    building = (
        recipe.removeprefix("randputf-") if recipe.startswith("randputf-") else recipe
    )
    src = steps[source]
    src["unlocks_recipes"] = [
        r for r in src.get("unlocks_recipes", []) if r != recipe
    ]
    src["unlocks_buildings"] = [
        b for b in src.get("unlocks_buildings", []) if b != building
    ]
    steps[target].setdefault("unlocks_recipes", []).append(recipe)


def _regenerate_extractor_recipe(
    db: VanillaDB,
    state,
    claim: dict[str, int],
    kit: set[str],
    rng: random.Random,
    recipe: dict,
    target: int,
    allowed_items: set[str] | None = None,
    allowed_buildings: set[str] | None = None,
    strict_pool: bool = False,
) -> None:
    """Régénère la recette d'extracteur pour la coordonner avec le jalon
    ``target`` — re-randomisée comme n'importe quelle recette (§7/§8) :

    - **ingrédients** re-tirés dans le pool obtenable à ``≤ target`` (items
      produits par une recette claimée ``≤ target``, environnementaux du spawn,
      items du kit), acycliques (the chapeau : on exclut les ancêtres du
      produit — jamais un ingrédient qui referme un cycle produit→produit) ;
    - **fabricateur** re-tiré parmi les ateliers débloqués à ``≤ target``
      (miroir de la bascule U2) — repli **handcraft** (aucun atelier) quand
      aucun ne convient (c'est déjà un état valide du générateur,
      ``crafted_in`` absent).

    Le claim d'unlock (le jalon choisi par C3) et le produit restent
    inchangés : seul le CORPS de la recette est re-baké
    (``ingredients``/``energy``/``results``/``crafted_in``). La recette reste
    craftable dès son déblocage quel que soit l'index : le reintérieur au
    moment le plus tard des ingrédients ET de l'atelier est borné par
    ``target``.
    """
    res = (recipe.get("results") or [{}])[0]
    if res.get("type") != SLOT_ITEM:
        return
    product = res.get("name")

    # Pool d'ingrédients : items dont UNE recette est claimée ≤ target (ou
    # obtenable au spawn : environnemental / kit). Exclut le produit et ses
    # ancêtres (anti-cycle §8).
    item_claim: dict[str, int] = {}
    for r in state.recipes:
        i = claim.get(r["name"])
        if i is None:
            continue
        for out in r.get("results") or []:
            if out.get("type") != SLOT_ITEM:
                continue
            name = out["name"]
            item_claim[name] = i if name not in item_claim else min(item_claim[name], i)
    # Jalon PRÉ-ÉLECTRIQUE (`strict_pool`) : les ingrédients doivent être
    # obtenus AVANT le step cible — un item débloqué au même step
    # (`claim == target`) n'est pas encore obtenu quand la recette se débloque
    # (§15 solveur, ordre intra-tech). Le pool se réduit alors aux
    # environnementaux/kit et aux produits de steps strictement antérieurs.
    if strict_pool:
        pool = {name for name, i in item_claim.items() if i < target}
        for name, itemdef in db.items.items():
            if itemdef.is_environmental:
                pool.add(name)
        for building_name in kit:
            # Un bâtiment du kit est lui-même débloqué à un step : s'il est
            # débloqué au MÊME step que la cible, il n'est pas encore obtenu
            # (§15 solveur) — on l'écarte, le repli restant les
            # environnementaux (wood/stone/raw-fish), forme du bootstrap §9.1.
            i_building = claim.get(f"randputf-{building_name}")
            if i_building is not None and i_building >= target:
                continue
            item = _item_for_building(db, building_name)
            if item is not None:
                pool.add(item.name)
    else:
        pool = {name for name, i in item_claim.items() if i <= target}
        for name, itemdef in db.items.items():
            if itemdef.is_environmental:
                pool.add(name)
        for building_name in kit:
            item = _item_for_building(db, building_name)
            if item is not None:
                pool.add(item.name)
    if allowed_items is not None:
        # Jalon PRÉ-ÉLECTRIQUE (extracteur du starter) : on ne re-tire que dans
        # le watershed atteignable sans électricité, sinon la ressource promise
        # au spawn deviendrait injouable (§9.1/§9.3, bootstrap_guard).
        pool &= allowed_items
    pool.discard(product)
    ancestors = _ancestor_products(db, state, SLOT_ITEM, product)
    eligible = sorted(
        {name for name in pool if (SLOT_ITEM, name) not in ancestors}
    )
    if not eligible:
        return

    max_ing = min(_recipes_mod._config.roll_ingredient_count(rng), len(eligible))
    picked = rng.sample(eligible, max_ing)
    if not picked:
        return
    chosen = [(SLOT_ITEM, name) for name in picked]
    baked = _bake_recipe(
        rng, db, state, SLOT_ITEM, product, chosen,
        recipe_name=recipe["name"], record=False,
    )

    # Fabricateur : ateliers débloqués à ≤ target qui hébergent le re-bake
    # (fits, non auto-hébergé, pas de cycle d'hébergement) ; repli handcraft.
    n_item = len(picked)
    candidates = []
    for building_name, building in db.buildings.items():
        if building_name in kit:
            i_building = 0
        else:
            i_building = claim.get(f"randputf-{building_name}")
            if i_building is None or i_building > target:
                continue
            if strict_pool and i_building >= target:
                # Atelier débloqué au MÊME step : pas encore obtenu (§15).
                continue
        if has_hidden_recipe(building) or not _is_atelier(building):
            continue
        if allowed_buildings is not None and building_name not in allowed_buildings:
            continue
        if building.item_input_slots < n_item:
            continue
        candidates.append((i_building, building_name))
    candidates.sort()

    fabricator = None
    for _i, building_name in candidates:
        building = db.buildings[building_name]
        if _self_hosted(db, building, baked):
            continue
        if _hosting_cycle(db, state, building, baked):
            continue
        if not _fits(building, baked):
            continue
        fabricator = building
        break

    if fabricator is None:
        # Repli handcraft : convention bootstrap (§9.1/§9.3) — une recette
        # craftable à la main (ni atelier ni catégorie) DOUBLE ses ingrédients
        # environnementaux, le début de run se jouant sur ces ressources rares.
        baked = _bake_recipe(
            rng, db, state, SLOT_ITEM, product, chosen,
            recipe_name=recipe["name"], x2_environmental=True, record=False,
        )

    recipe["name"] = baked["name"]
    recipe["energy"] = baked["energy"]
    recipe["ingredients"] = baked["ingredients"]
    recipe["results"] = baked["results"]
    if fabricator is not None:
        recipe["crafted_in"] = fabricator.name
        recipe["category"] = _recipe_category(fabricator, False, False)
    else:
        recipe.pop("crafted_in", None)
        recipe.pop("category", None)



def _startup_raw_resources(state, extractors, all_tech_steps: list[dict], free_count: int):
    """Ressources brutes consommées par la « boîte à outils » du SPAWN.

    D4bis : la passe juste-au-besoin ne doit JAMAIS différer un extracteur dont
    la ressource est consommée AVANT la première recherche — sinon la partie est
    bloquée au spawn (lab, trigger, électricité coupés) sur une chaîne
    ACYCLIQUE invisible pour les §15. Sont « au spawn » :

    - la fermeture des recettes débloquées par les techs gratuites (lab, poêle,
      turbines…) ; la fermeture s'arrête aux recettes gratuites : un ingrédient
      dont la recette est PAYANTE est un problème de recettes, hors extracteurs ;
    - le déclencheur (craft_trigger) de la premiere tech payante — la toute
      première recherche doit être lançable dès le spawn ;
    - les fluides consommés par les bâtiments du spawn (assignation §6/§10) :
      la turbine du premier générateur reçoit son entrée (un lac) dès
      l'électricité — si son extracteur est différé, plus d'électricité au
      spawn, donc plus rien d'électrique.
    """
    free_recipes: set[str] = set()
    for step in all_tech_steps[:free_count]:
        free_recipes.update(step.get("unlocks_recipes", []))
    extracted: set[tuple[str, str]] = {
        key for rs in extractors.values() for key in rs
    }
    producers: dict[str, set[str]] = {}
    byname: dict[str, dict] = {}
    for recipe in state.recipes:
        byname[recipe["name"]] = recipe
        if recipe["name"] in free_recipes:
            for res in recipe.get("results", []):
                producers.setdefault(res["name"], set()).add(recipe["name"])
    roots: list[str] = sorted(free_recipes)
    # Déclencheur de la première tech payante : item craftable au spawn ; sa
    # recette (si elle est gratuite) ferme l'ensemble.
    if free_count < len(all_tech_steps):
        trig = all_tech_steps[free_count].get("craft_trigger")
        if trig:
            roots.extend(sorted(producers.get(trig, ())))
    raws: set[tuple[str, str]] = set()
    processed: set[str] = set()
    while roots:
        name = roots.pop()
        if name in processed or name not in byname:
            continue
        processed.add(name)
        for ing in byname[name].get("ingredients", []):
            key = (ing.get("type"), ing.get("name"))
            if key in extracted:
                raws.add(key)
            else:
                roots.extend(
                    p for p in producers.get(ing.get("name"), ()) if p not in processed
                )
    # Fluides consommés par les bâtiments du spawn (ex. turbine → notre lac).
    for assignment in (getattr(state, "building_fluid_assignments", None) or {}).values():
        inp = assignment.get("input")
        if inp:
            raws.add((SLOT_FLUID, inp))
    return raws


def apply_extractor_timing(
    db: VanillaDB,
    starter,
    all_tech_steps: list[dict],
    *,
    seed_value: int,
    patch_resources: set[str] | None = None,
    lake_resources: set[str] | None = None,
) -> dict:
    """Applique le déblocage juste-au-besoin. Retourne un rapport sérialisable
    (l'audit et les tests le rejoignent comme source de vérité)."""
    report: dict = {"extractors": {}, "starter": [], "timed": [], "random": []}
    extractors = _extractor_resources(db, starter.state)
    if not extractors:
        return report

    claim = _claim_indexes(all_tech_steps)
    resources = {resource for rs in extractors.values() for resource in rs}
    first = _first_consumers(starter.state, claim, resources)
    kit = _kit_buildings(starter, db)
    extraction_idx = next(
        (i for i, step in enumerate(all_tech_steps)
         if step.get("id") == STARTER_EXTRACTION_ID),
        None,
    )

    rng = random.Random(f"randputf:extractor-timing:{seed_value}")
    free_count = len(starter.tech_steps)
    paid = list(range(free_count, len(all_tech_steps)))
    startup_raw = _startup_raw_resources(
        starter.state, extractors, all_tech_steps, free_count
    )

    # Watershed pré-électrique, calculé paresseusement : une régénération d'un
    # extracteur du starter doit rester jouable SANS électricité (§9.1/§9.3).
    early_items: set[str] | None = None
    early_buildings: set[str] | None = None

    def _pre_electric() -> tuple[set[str], set[str]]:
        nonlocal early_items, early_buildings
        if early_items is not None:
            return early_items, early_buildings or set()
        src_items, src_fluids = build_early_sources(
            db, patch_resources or set(), lake_resources or set()
        )
        early_items, early_fluids = compute_early_reachable(
            db, starter.state.recipes, src_items, src_fluids
        )
        early_buildings = {
            b.name for b in db.buildings.values()
            if b.energy_type != "electric" and b.item_input_slots > 0
        }
        return early_items, early_buildings

    for recipe, rs in sorted(extractors.items()):
        s = claim.get(recipe)
        if s is None:
            continue
        report["extractors"][recipe] = [
            {"type": kind, "name": name} for kind, name in rs
        ]
        atelier = _atelier_claim(starter.state, db, claim, kit, recipe)
        needy = [first[key] for key in rs if key in first]
        needed = min(needy) if needy else None
        # Le bâtiment-extracteur est-il consommé comme ingrédient AVANT la tech
        # gratuite ? (ex. pumpjack×4 dans offshore-pump). La ressource extraite
        # n'étant utile qu'en profondeur, C3 pousserait le craft APRÈS ce
        # consommateur → quantité intenable. On borne par le premier usage item.
        item = recipe.removeprefix("randputf-")
        item_first = _first_item_consumer(starter.state, claim, item)
        if item_first is not None:
            needed = item_first if needed is None else min(needed, item_first)
        startup = any(key in startup_raw for key in rs)

        if needed is None:
            # Jamais consommé : comme les autres bâtiments (§9.6), le claim part
            # sur un step payant, tiré sur un RNG dédié déterministe, et jamais
            # avant l'atelier qui le fabrique.
            target = max(rng.choice(paid), atelier) if paid else atelier
        else:
            if startup:
                # D4bis : ressource consommée par la boîte du SPAWN (techs
                # gratuites / trigger de la 1re tech / fluide de la turbine) →
                # l'extracteur reste À LA TECH GRATUITE. Le différer couperait
                # le bootstrap sans même une recherche possible.
                target = extraction_idx if extraction_idx is not None else needed
            else:
                # Au premier besoin, PAS au plus tard. La recette n'est JAMAIS
                # repoussée vers un atelier profond : une quantité intenable
                # (item consommé comme ingrédient avant son unlock) en naîtrait.
                target = needed
            # Transitivité montante : si l'atelier qui fabrique l'extracteur
            # (bâtiment de contenu planté profond par le balayage §9.6) est
            # débloqué plus profond que le besoin, on NE repousse PAS la recette
            # (quantité intenable) et on NE remonte PAS le contenu early : on
            # RÉGÉNÈRE la recette d'extracteur pour qu'elle se coordonne avec
            # le jalon `target` — ingrédients et fabricateur re-randomisés dans
            # le pool obtenable à ≤ target (repli handcraft si aucun atelier).
            if atelier > target:
                recipe_obj = next(
                    (r for r in starter.state.recipes if r["name"] == recipe), None
                )
                if recipe_obj is not None:
                    if target < free_count:
                        # Jalon dans le plateau des techs GRATUITES : la recette
                        # doit rester craftable SANS électricité et sans
                        # dépendre d'un item/atelier débloqué au même step
                        # (§9.1-§9.3 watershed, bootstrap_guard, §15 solveur).
                        _i, p_buildings = _pre_electric()
                        _regenerate_extractor_recipe(
                            db, starter.state, claim, kit, rng, recipe_obj, target,
                            allowed_buildings=p_buildings, strict_pool=True,
                        )
                    else:
                        _regenerate_extractor_recipe(
                            db, starter.state, claim, kit, rng, recipe_obj, target
                        )

        if target != s:
            _move_claim(s, target, all_tech_steps, recipe)
        if needed is None:
            bucket = "random"
        elif startup:
            bucket = "starter"
        else:
            bucket = "timed"
        report[bucket].append(recipe)
        if startup and target >= free_count:
            log.warning(
                "[randputF] extractor_timing: %s requis au spawn mais atelier %d "
                ">= plateau gratuit %d — fabricable seulement en profondeur",
                recipe, atelier, free_count,
            )

    if report["timed"] or report["random"]:
        log.info(
            "[randputF] extractor_timing: %d au starter, %d au premier usage, "
            "%d aléatoires (jamais utilisés)",
            len(report["starter"]), len(report["timed"]), len(report["random"]),
        )
    return report