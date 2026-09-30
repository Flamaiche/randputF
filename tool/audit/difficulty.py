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
    """Ardoise de difficulté d'une seed : coûts bruts par ressource, dépenses
    par tech et coûts unitaires — agrégés pour le total affiché au spawn."""
    raw_totals: Counter[str] = field(default_factory=Counter)
    spent_per_tech: dict = field(default_factory=dict)
    unit_costs: dict = field(default_factory=dict)

    @property
    def total(self) -> float:
        """Total de l'ardoise : somme des coûts bruts de toutes ressources."""
        return sum(self.raw_totals.values())


def _primary_recipe(by_product: dict[str, list[dict]], product: str) -> dict | None:
    """Recette PRIMAIRE d'un produit (``randputf-<produit>``), sinon la
    première recette alternative (relais/ease). Les doublons/ease ne sont
    jamais cumulés : un produit n'est compté qu'une fois. ``rocket-part`` est
    réservé à la recette exempte du silo.
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
    for res in recipe.get("results", []):
        if res.get("name") == product:
            return float(res.get("amount", 1))
    return 1.0


def unit_costs(
    raw: set[str], by_product: dict[str, list[dict]]
) -> dict[str, Counter[str]]:
    """Coût unitaire brut de chaque produit (mémoïsé, DAG primaire).

    ``cost[p][r]`` = quantité de ressource brute ``r`` pour produire 1 unité de
    ``p``. Un produit déjà calculé est réutilisé tel quel (diamond-safe) ; un
    produit sans recette (non brut) est compté comme feuille de secours.
    """
    memo: dict[str, Counter[str]] = {}

    def cost(product: str) -> Counter[str]:
        """Coût unitaire brut de ``product`` (mémoïsé) : lui-même si brut,
        sinon la décomposition de sa recette primaire."""
        if product in raw:
            if product not in memo:
                memo[product] = Counter({product: 1.0})
            return memo[product]
        if product in memo:
            return memo[product]
        recipe = _primary_recipe(by_product, product)
        if recipe is None:
            memo[product] = Counter({product: 1.0})
            return memo[product]
        produced = _produced_amount(recipe, product)
        acc: Counter[str] = Counter()
        for ing in recipe.get("ingredients", []):
            scale = float(ing.get("amount", 1)) / produced
            sub = cost(ing["name"])
            for k, v in sub.items():
                acc[k] += v * scale
        memo[product] = acc
        return acc

    # Calcule tous les produits (y compris les bruts, mémoïsés en feuille).
    for p in by_product:
        cost(p)
    cost("rocket-part")
    return memo


def compute_difficulty(seed: dict) -> DifficultyReport:
    """Ardoise : science packs de toutes les techs + chaîne de la fusée."""
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


def summarize_difficulty(report: DifficultyReport) -> str:
    """Tableau des totaux finaux par ressource brute (+ total général)."""
    lines = []
    for name in sorted(report.raw_totals,
                       key=lambda n: (report.raw_totals[n] <= 0, -report.raw_totals[n], n)):
        if report.raw_totals[name] <= 0:
            continue
        lines.append(f"{name:28s} {report.raw_totals[name]:10.1f}")
    lines.append("-" * 40)
    lines.append(f"{'TOTAL':28s} {report.total:10.1f}")
    return "\n".join(lines)