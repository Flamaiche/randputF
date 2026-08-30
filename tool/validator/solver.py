"""Vérification des invariants de solvabilité (README §15).

IMPLEMENTE generiquement sur la structure seed :
1. anti-cycle : tri topologique (Kahn) sur le graphe prerequis -> produit ;
2. progressivite : chaque recette n'utilise que des choses deja atteignables
   au moment de son deblocage, sauf marquage explicite on_the_spot_unlock ;
3. completude : presence d'une chaine vers les prerequis fusée (hook, la
   definition exacte des composants requis sera figée avec le moteur).
"""

from __future__ import annotations

from tool.common.db import ENVIRONMENTAL_ITEMS


def validate_seed(seed: dict) -> list[str]:
    issues: list[str] = []
    issues += _check_anti_cycle(seed)
    issues += _check_progressivity(seed)
    issues += _check_completeness(seed)
    return issues


def _recipe_graph(seed: dict) -> dict[str, set[str]]:
    known_recipes = {r["name"] for r in seed.get("recipes", [])}
    graph: dict[str, set[str]] = {}
    for recipe in seed.get("recipes", []):
        deps = {
            ingredient["produced_by"]
            for ingredient in recipe.get("ingredients", [])
            if ingredient.get("produced_by") in known_recipes
        }
        graph[recipe["name"]] = deps
    return graph


def _check_anti_cycle(seed: dict) -> list[str]:
    graph = _recipe_graph(seed)
    remaining = {node: set(deps) for node, deps in graph.items()}
    queue = sorted(node for node, deps in remaining.items() if not deps)
    resolved: set[str] = set()
    while queue:
        node = queue.pop(0)
        resolved.add(node)
        for other, deps in remaining.items():
            if node in deps:
                deps.discard(node)
                if not deps and other not in resolved:
                    queue.append(other)
    cyclic = sorted(set(graph) - resolved)
    if cyclic:
        return [f"anti-cycle: recettes en boucle ou dépendances manquantes: {cyclic}"]
    return []


def _check_progressivity(seed: dict) -> list[str]:
    issues: list[str] = []
    # Pool initial : patchs + lacs (§7.5) + ressources environnementales
    # (arbres/rochers/poissons) toujours récoltables à la main (README §3, §6
    # et §9.3).
    pool: set[str] = {p["resource"] for p in seed.get("map", {}).get("patches", [])}
    pool |= {la["resource"] for la in seed.get("map", {}).get("lakes", [])}
    pool |= set(ENVIRONMENTAL_ITEMS)
    for recipe in seed.get("recipes", []):
        missing = [ing["name"] for ing in recipe.get("ingredients", []) if ing["name"] not in pool]
        if missing and not recipe.get("on_the_spot_unlock"):
            issues.append(f"progressivité: {recipe['name']} utilise {missing} avant obtention")
        for product in recipe.get("results", []):
            pool.add(product["name"])
        for ingredient in recipe.get("ingredients", []):
            pool.add(ingredient["name"])
    return issues


def _check_completeness(seed: dict) -> list[str]:
    required = seed.get("victory_requirements", [])
    produced = {p["name"] for r in seed.get("recipes", []) for p in r.get("results", [])}
    patched = {p["resource"] for p in seed.get("map", {}).get("patches", [])}
    patched |= {la["resource"] for la in seed.get("map", {}).get("lakes", [])}
    missing = [req for req in required if req not in produced | patched]
    if missing:
        return [f"complétude: exigences de victoire inatteignables: {missing}"]
    return []
