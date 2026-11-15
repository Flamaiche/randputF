"""Audit de DIFFICULTÉ : ardoise de ressources brutes pour finir une run.

Mesure la difficulté d'une seed par le nombre de ressources brutes
(``pools.raw_resources``) consommées pour :
  1. la recherche de TOUTES les techs (coût en science packs de chaque tech,
     ``unit.count * amount`` par ingrédient) ;
  2. la chaîne de la fusée : 1 rocket-silo, 100 rocket-part (recette vanilla
     EXEMPTE du silo, jamais désactivée), 1 satellite.

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
from dataclasses import dataclass, field

# Chaîne de la fusée : rocket-part se crafe dans le SILO via la recette vanilla
# EXEMPTE (data-final-fixes), jamais désactivée ni déployée par la génération.
ROCKET_PART_RECIPE = {
    "results": [{"name": "rocket-part", "amount": 1}],
    "ingredients": [
        {"name": "processing-unit", "type": "item", "amount": 10},
        {"name": "low-density-structure", "type": "item", "amount": 10},
        {"name": "rocket-fuel", "type": "item", "amount": 10},
    ],
}
ROCKET_PARTS_TO_LAUNCH = 100

_PREFIX = "randputf-"


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


def _primary_recipe(by_product: dict[str, list[dict]], product: str) -> dict | None:
    """Retourne la recette primaire d'un produit.

    `by_product` indexe les recettes par produit et `product` est le nom recherché. Privilégie `randputf-<produit>`, sinon la première alternative ; `rocket-part` est réservé à la recette du silo. Retourne `None` si le produit n'a aucune recette.
    """
    if product == "rocket-part":
        return ROCKET_PART_RECIPE
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
    raw: set[str], by_product: dict[str, list[dict]]
) -> dict[str, Counter[str]]:
    """Calcule le coût unitaire brut de chaque produit.

    `raw` est l'ensemble des ressources brutes et `by_product` l'index produit → recettes. Retourne `{produit: Counter({ressource: quantité})}` ; les cycles sont cassés en traitant le produit comme une feuille.
    """
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
        recipe = _primary_recipe(by_product, product)
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
    for p in by_product:
        cost(p)
    cost("rocket-part")
    return memo


def compute_difficulty(seed: dict) -> DifficultyReport:
    """Calcule l'ardoise de difficulté complète d'une seed.

    `seed` fournit recettes, technologies et ressources brutes. Additionne les packs de toutes les recherches et la chaîne de la fusée (silo, 100 rocket-part, satellite). Retourne un `DifficultyReport` renseigné.
    """
    report = DifficultyReport()

    by_product: dict[str, list[dict]] = defaultdict(list)
    for r in seed.get("recipes", []):
        for res in r.get("results", []):
            by_product[res["name"]].append(r)

    raw = set(seed["pools"]["raw_resources"])
    costs = unit_costs(raw, by_product)
    report.unit_costs = costs

    # 1. Coût de recherche : somme sur toutes les techs (hors prologue/ease,
    #    craft_trigger sans coût). unit.count * amount par ingrédient.
    self_bill = Counter()
    spent_per_tech: dict[str, Counter] = {}
    for tech in seed.get("technologies", []):
        unit = tech.get("unit") or {}
        ings = unit.get("ingredients") or []
        cost = Counter()
        for ing in ings:
            cost[ing["name"]] += int(unit.get("count", 1)) * float(ing.get("amount", 1))
        if cost:
            spent_per_tech[tech["id"]] = cost
            self_bill.update(cost)
    report.spent_per_tech = spent_per_tech

    # 2. Chaîne de la fusée : 1 silo, 100 rocket-part (recette exempte du silo),
    #    1 satellite.
    launch_bill = Counter()
    launch_bill["rocket-silo"] += 1
    launch_bill["rocket-part"] += ROCKET_PARTS_TO_LAUNCH
    launch_bill["satellite"] += 1

    totals: Counter[str] = Counter()
    for product, qty in self_bill.items():
        for k, v in costs.get(product, Counter()).items():
            totals[k] += v * qty
    for product, qty in launch_bill.items():
        for k, v in costs.get(product, Counter()).items():
            totals[k] += v * qty

    report.raw_totals = totals
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


def difficulty_series(seed: dict) -> list[dict]:
    """Série de difficulté par tech, dans l'ordre de progression.

    Chaque point porte : le rang, l'id/le nom de la tech, le coût brut de SA
    recherche (``raw``), le cumul depuis le début (``cumulative``) et la liste
    des produits qu'elle débloque (``products`` = « items à crafter »). Un point
    final « Fusée » ferme la chaîne (silo + 100 rocket-part + satellite), de
    sorte que le cumul final égale ``compute_difficulty(seed).total``.
    """
    report = compute_difficulty(seed)
    tmap, ordered = _tech_sequence(seed)
    prodmap = _recipe_products(seed)

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

    launch_bill: Counter[str] = Counter({
        "rocket-silo": 1.0,
        "rocket-part": float(ROCKET_PARTS_TO_LAUNCH),
        "satellite": 1.0,
    })
    launch_raw = _expand_to_raw(report.unit_costs, launch_bill)
    cumulative.update(launch_raw)
    series.append({
        "num": len(series) + 1,
        "id": "randputf-rocket",
        "name": "Lancement (fusée)",
        "raw": dict(launch_raw),
        "raw_total": sum(launch_raw.values()),
        "cumulative": dict(cumulative),
        "cumulative_total": sum(cumulative.values()),
        "products": ["rocket-part"],
    })
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