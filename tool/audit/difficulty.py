"""Audit de DIFFICULTÉ : ardoise de ressources brutes pour finir une run.

Mesure la difficulté d'une seed par le nombre de ressources brutes
(``pools.raw_resources``) consommées pour :
  1. la recherche de TOUTES les techs (coût en science packs de chaque tech,
     ``unit.count * amount`` par ingrédient) ;
  2. la chaîne de lancement : bâtiments, pièces de fusée et produits de
     lancement décrits par ``seed['meta']['rocket']`` (faits du dump, y
     compris la recette réservée exempte du silo). Aucun nom vanilla n'est
     supposé ici.

L'expansion descend chaque produit vers ses INGRÉDIENTS via sa RECETTE
PRIMAIRE (``randputf-<produit>``, sinon relais/ease comme solution de secours) :
les recettes alternatives (relay/ease) créent des cycles dans le graphe COMPLET
(comptés et exclus ici), mais le graphe primaire est un DAG — vérifié en test,
aucune expansion ne boucle.

Une recette ``randputf-<produit>`` peut produire ``amount`` unités (≠ 1) :
le nombre de crafts est donc ``besoin / amount``, chaque craft consommant les
ingrédients déclarés. Un produit partagé par plusieurs branches (diamond) n'est
calculé qu'UNE fois, puis réutilisé (mémoïsation du coût unitaire brut).

``compute_difficulty(seed)`` renvoie un ``DifficultyReport`` dont
``raw_totals`` agrège les totaux finaux par ressource brute (utilisateur :
« totaux finaux simples »).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

_PREFIX = "randputf-"


def _scaled_progress(
    on_progress: Callable[[int], None] | None, low: int, high: int
) -> Callable[[int], None] | None:
    if on_progress is None:
        return None
    span = high - low
    return lambda percent: on_progress(low + percent * span // 100)


@dataclass
class DifficultyReport:
    """Ardoise de difficulté d'une seed.

    `raw_totals` agrège les quantités de ressources brutes, `spent_per_tech` les coûts de recherche par technologie et `unit_costs` le coût brut d'une unité de chaque produit. Sert au total affiché au spawn et aux séries de difficulté.
    """
    raw_totals: Counter[str] = field(default_factory=Counter)
    spent_per_tech: dict = field(default_factory=dict)
    unit_costs: dict = field(default_factory=dict)

    @property
    def total(self) -> float:
        """Retourne le total de l'ardoise de difficulté.

        Additionne les quantités de toutes les ressources brutes de ``raw_totals`` ; les entrées à zéro n'ont aucun effet. Aucun paramètre ; retourne un ``float`` destiné à l'affichage du total général.
        """
        return sum(self.raw_totals.values())


def _rocket_meta(seed: dict) -> dict:
    """Faits de lancement portés par la seed (aucun repli inventé)."""
    rocket = (seed.get("meta") or {}).get("rocket") or {}
    return {
        "launch_buildings": list(rocket.get("launch_buildings") or ()),
        "rocket_recipe": str(rocket.get("rocket_recipe") or ""),
        "rocket_recipe_data": dict(rocket.get("rocket_recipe_data") or {}),
        "rocket_part_product": str(rocket.get("rocket_part_product") or ""),
        "rocket_parts_required": int(rocket.get("rocket_parts_required") or 0),
        "launch_items": list(rocket.get("launch_items") or ()),
    }


def _primary_recipe(
    by_product: dict[str, list[dict]],
    product: str,
    reserved_recipes: dict[str, dict] | None = None,
) -> dict | None:
    """Retourne la recette primaire d'un produit.

    `by_product` indexe les recettes par produit et `product` est le nom recherché. Une recette réservée (ex. pièce de fusée exempte du silo) prend le pas. Sinon, privilégie `randputf-<produit>`, puis la première alternative. Retourne `None` si le produit n'a aucune recette.
    """
    reserved = (reserved_recipes or {}).get(product)
    if reserved is not None:
        return reserved
    cands = by_product.get(product, [])
    if not cands:
        return None
    for r in cands:
        if r["name"] == f"{_PREFIX}{product}":
            return r
    return cands[0]


def _produced_amount(recipe: dict, product: str) -> float:
    """Quantité de ``product`` produite par une recette.

    Parcourt ``recipe["results"]`` et retourne le champ ``amount`` de la
    première ligne dont le ``name`` correspond (converti en ``float``).
    Retourne ``1.0`` si le produit n'apparaît pas, ce qui neutralise la
    division du coût unitaire sans faire échouer l'audit.
    """
    for res in recipe.get("results", []):
        if res.get("name") == product:
            return float(res.get("amount", 1))
    return 1.0


def unit_costs(
    raw: set[str],
    by_product: dict[str, list[dict]],
    reserved_recipes: dict[str, dict] | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> dict[str, Counter[str]]:
    """Calcule le coût unitaire brut de chaque produit.

    `raw` est l'ensemble des ressources brutes, `by_product` l'index produit → recettes et `reserved_recipes` les recettes imposées (produit → recette). Retourne `{produit: Counter({ressource: quantité})}` ; les cycles sont cassés en traitant le produit comme une feuille. `on_progress`, s'il est fourni, reçoit un pourcentage de cette phase.
    """
    reserved = reserved_recipes or {}
    memo: dict[str, Counter[str]] = {}
    visiting: set[str] = set()

    def cost(product: str) -> Counter[str]:
        """Retourne le coût unitaire brut de `product`.

        Mémoïse le résultat ; un produit brut vaut une unité de lui-même, sinon le coût est décomposé depuis sa recette primaire.
        """
        if product in raw:
            if product not in memo:
                memo[product] = Counter({product: 1.0})
            return memo[product]
        if product in memo:
            return memo[product]
        if product in visiting:
            # Cycle (le graphe PRIMAIRE d'une seed est un DAG garanti ; une
            # baseline vanilla, elle, peut boucler : kovarex, coal-liquefaction).
            # On casse en traitant le produit comme une feuille.
            return Counter({product: 1.0})
        recipe = _primary_recipe(by_product, product, reserved)
        if recipe is None:
            memo[product] = Counter({product: 1.0})
            return memo[product]
        produced = _produced_amount(recipe, product)
        visiting.add(product)
        acc: Counter[str] = Counter()
        for ing in recipe.get("ingredients", []):
            scale = float(ing.get("amount", 1)) / produced
            sub = cost(ing["name"])
            for k, v in sub.items():
                acc[k] += v * scale
        visiting.discard(product)
        memo[product] = acc
        return acc

    # Calcule tous les produits (y compris les bruts, mémoïsés en feuille).
    products = list(by_product)
    for index, p in enumerate(products, 1):
        cost(p)
        if on_progress is not None:
            on_progress(index * 70 // max(1, len(products)))
    reserved_products = list(reserved)
    for index, p in enumerate(reserved_products, 1):
        cost(p)
        if on_progress is not None:
            on_progress(70 + index * 30 // max(1, len(reserved_products)))
    return memo


def compute_difficulty(
    seed: dict, on_progress: Callable[[int], None] | None = None
) -> DifficultyReport:
    """Calcule l'ardoise de difficulté complète d'une seed.

    `seed` fournit recettes, technologies et ressources brutes. Additionne les packs de toutes les recherches et la chaîne de lancement décrite par ``meta.rocket``. Retourne un `DifficultyReport` renseigné. `on_progress`, s'il est fourni, reçoit un pourcentage du calcul.
    """
    report = DifficultyReport()

    by_product: dict[str, list[dict]] = defaultdict(list)
    for r in seed.get("recipes", []):
        for res in r.get("results", []):
            by_product[res["name"]].append(r)

    raw = set(seed["pools"]["raw_resources"])
    rocket = _rocket_meta(seed)
    reserved = {}
    if rocket["rocket_part_product"] and rocket["rocket_recipe_data"]:
        reserved[rocket["rocket_part_product"]] = rocket["rocket_recipe_data"]
    costs = unit_costs(
        raw,
        by_product,
        reserved,
        _scaled_progress(on_progress, 0, 30),
    )
    report.unit_costs = costs

    # 1. Coût de recherche : somme sur toutes les techs (hors prologue/ease,
    #    craft_trigger sans coût). unit.count * amount par ingrédient.
    self_bill = Counter()
    spent_per_tech: dict[str, Counter] = {}
    techs = seed.get("technologies", [])
    for index, tech in enumerate(techs, 1):
        unit = tech.get("unit") or {}
        ings = unit.get("ingredients") or []
        cost = Counter()
        for ing in ings:
            cost[ing["name"]] += int(unit.get("count", 1)) * float(ing.get("amount", 1))
        if cost:
            spent_per_tech[tech["id"]] = cost
            self_bill.update(cost)
        if on_progress is not None:
            on_progress(30 + index * 20 // max(1, len(techs)))
    report.spent_per_tech = spent_per_tech

    # 2. Chaîne de lancement : bâtiments, pièces (recette réservée) et
    #    produits exigés par le lancement.
    launch_bill = Counter()
    for building in rocket["launch_buildings"]:
        launch_bill[building] += 1
    if rocket["rocket_part_product"]:
        launch_bill[rocket["rocket_part_product"]] += rocket["rocket_parts_required"]
    for item in rocket["launch_items"]:
        launch_bill[item] += 1

    totals: Counter[str] = Counter()
    final_items = list(self_bill.items()) + list(launch_bill.items())
    for index, (product, qty) in enumerate(final_items, 1):
        for k, v in costs.get(product, Counter()).items():
            totals[k] += v * qty
        if on_progress is not None:
            on_progress(50 + index * 40 // max(1, len(final_items)))

    report.raw_totals = totals
    if on_progress is not None:
        on_progress(100)
    return report


def _tech_sequence(seed: dict) -> tuple[dict[str, dict], list[str]]:
    """Ordre de progression d'une seed (ou d'une baseline vanilla) : la
    ``progression_order`` trie les techs connues, puis un parcours topologique
    des prérequis comble les manquantes. Renvoie ``(tmap, ordered)``."""
    tmap = {t["id"]: t for t in (seed.get("technologies") or []) if t.get("id")}
    ordered: list[str] = []
    seen: set[str] = set()
    for tid in seed.get("progression_order") or []:
        if tid in tmap and tid not in seen:
            ordered.append(tid)
            seen.add(tid)
    missing = set(tmap) - seen
    while missing:
        frontier = [
            t for t in missing
            if all(p in seen for p in (tmap[t].get("prerequisites") or []))
        ]
        if not frontier:  # prérequis hors périmètre / cycle : on tranche par nom
            frontier = sorted(missing)
        frontier.sort(key=lambda t: (tmap[t].get("localised_name") or t))
        for tid in frontier:
            ordered.append(tid)
            seen.add(tid)
            missing.discard(tid)
    return tmap, ordered


def _recipe_products(seed: dict) -> dict[str, list[str]]:
    """Indexe les produits de chaque recette d'une seed.

    `seed` est le dict de seed. Retourne `{nom_recette: [noms_produits]}` ; sert à attribuer les déblocages aux technologies.
    """
    out: dict[str, list[str]] = {}
    for recipe in seed.get("recipes") or []:
        prods = [res.get("name") for res in recipe.get("results") or [] if res.get("name")]
        if prods:
            out[recipe.get("name", "")] = prods
    return out


def _expand_to_raw(
    costs: dict[str, Counter[str]], bill: Counter[str]
) -> Counter[str]:
    """Décompose un besoin de produits en ressources brutes.

    `costs` est l'index des coûts unitaires et `bill` associe un produit à sa quantité. Retourne un `Counter` ressource → quantité totale.
    """
    raw: Counter[str] = Counter()
    for product, qty in bill.items():
        for key, value in costs.get(product, Counter()).items():
            raw[key] += value * qty
    return raw


def difficulty_series(
    seed: dict,
    *,
    report: DifficultyReport | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> list[dict]:
    """Série de difficulté par tech, dans l'ordre de progression.

    Chaque point porte : le rang, l'id/le nom de la tech, le coût brut de la recherche
    recherche (``raw``), le cumul depuis le début (``cumulative``) et la liste
    des produits qu'elle débloque (``products`` = « items à crafter »). Un point
    final « Lancement » ferme la chaîne décrite par ``meta.rocket``, de sorte
    que le cumul final égale ``compute_difficulty(seed).total``. ``report`` évite
    de recalculer l'ardoise ; ``on_progress`` reçoit un pourcentage de la série.
    """
    if report is None:
        report = compute_difficulty(seed, _scaled_progress(on_progress, 0, 30))
    else:
        if on_progress is not None:
            on_progress(30)
    tmap, ordered = _tech_sequence(seed)
    prodmap = _recipe_products(seed)
    if on_progress is not None:
        on_progress(32)

    cumulative: Counter[str] = Counter()
    series: list[dict] = []
    for index, tid in enumerate(ordered, 1):
        tech = tmap[tid]
        raw = _expand_to_raw(report.unit_costs, report.spent_per_tech.get(tid, Counter()))
        cumulative.update(raw)
        products: list[str] = []
        seen: set[str] = set()
        for eff in tech.get("effects") or []:
            if eff.get("type") != "unlock-recipe":
                continue
            for product in prodmap.get(eff.get("recipe", ""), []):
                if product not in seen:
                    seen.add(product)
                    products.append(product)
        series.append({
            "num": index,
            "id": tid,
            "name": tech.get("localised_name") or tid,
            "raw": dict(raw),
            "raw_total": sum(raw.values()),
            "cumulative": dict(cumulative),
            "cumulative_total": sum(cumulative.values()),
            "products": products,
        })
        if on_progress is not None:
            on_progress(32 + index * 48 // max(1, len(ordered)))

    rocket = _rocket_meta(seed)
    launch_bill: Counter[str] = Counter()
    for building in rocket["launch_buildings"]:
        launch_bill[building] += 1.0
    if rocket["rocket_part_product"]:
        launch_bill[rocket["rocket_part_product"]] += float(rocket["rocket_parts_required"])
    for item in rocket["launch_items"]:
        launch_bill[item] += 1.0
    launch_raw = _expand_to_raw(report.unit_costs, launch_bill)
    cumulative.update(launch_raw)
    series.append({
        "num": len(series) + 1,
        "id": "randputf-rocket",
        "name": "Lancement",
        "raw": dict(launch_raw),
        "raw_total": sum(launch_raw.values()),
        "cumulative": dict(cumulative),
        "cumulative_total": sum(cumulative.values()),
        "products": [rocket["rocket_part_product"]] if rocket["rocket_part_product"] else [],
    })
    if on_progress is not None:
        on_progress(100)
    return series


def summarize_difficulty(report: DifficultyReport) -> str:
    """Met en forme les totaux finaux par ressource brute.

    `report` est un `DifficultyReport`. Retourne une chaîne multi-lignes terminée par le total général, prête pour l'affichage CLI.
    """
    lines = []
    for name in sorted(report.raw_totals,
                       key=lambda n: (report.raw_totals[n] <= 0, -report.raw_totals[n], n)):
        if report.raw_totals[name] <= 0:
            continue
        lines.append(f"{name:28s} {report.raw_totals[name]:10.1f}")
    lines.append("-" * 40)
    lines.append(f"{'TOTAL':28s} {report.total:10.1f}")
    return "\n".join(lines)