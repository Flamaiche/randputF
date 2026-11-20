"""Vérification des invariants de solvabilité.

Implémente génériquement sur la structure seed :
1. anti-cycle : tri topologique (Kahn) sur le graphe prerequis → produit ;
2. progressivite : chaque recette n'utilise que des choses atteignables au
   moment de son deblocage, sauf ``on_the_spot_unlock`` ;
3. completude : presence d'une chaine vers les prerequis fusee.
"""

from __future__ import annotations

from tool.common.cycles import find_recipe_cycle
from tool.common.db import seed_environmental_items

MAX_CYCLE_DEPTH = 5
MAX_CYCLE_EXPANSIONS = 2000


def validate_seed(seed: dict) -> list[str]:
    """Valide la graine (anti-cycle, progressivité, complétude d'une tech
    finale — le joueur a une voie vers le lancement) et renvoie la liste des
    problèmes éventuels (vide si la seed est valide)."""
    issues: list[str] = []
    issues += _check_anti_cycle(seed)
    issues += _check_progressivity(seed)
    issues += _check_completeness(seed)
    return issues


def _recipe_graph(seed: dict) -> dict[str, set[str]]:
    """Graphe de dépendances recette → recettes productrices.

    Pour chaque recette de ``seed["recipes"]``, collecte les ``produced_by``
    de ses ingrédients qui désignent une recette connue de la seed. Les
    ingrédients bruts (sans ``produced_by`` ou pointant hors seed) sont
    ignorés. Retourne ``{nom_recette: {noms_des_dépendances}}``.
    """
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
    """Détecte les cycles du graphe de recettes par tri topologique (Kahn).

    Part des recettes sans dépendance puis retire progressivement les arêtes
    résolues. Retourne une liste vide si toutes les recettes sont résolues,
    sinon un unique message listant les recettes restantes (cycle ou
    dépendance manquante).
    """
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


def _initial_pool(seed: dict) -> set[str]:
    """Ressources disponibles sans aucune recette.

    Patchs, lacs, ressources brutes du dump et items environnementaux
    (récoltables à la main) sont toujours acquis au départ.
    """
    pool: set[str] = {
        p["resource"] for p in seed.get("map", {}).get("patches", [])
    }
    pool |= {la["resource"] for la in seed.get("map", {}).get("lakes", [])}
    pool |= set((seed.get("pools") or {}).get("raw_resources") or ())
    pool |= set((seed.get("pools") or {}).get("process_fluids") or ())
    pool |= seed_environmental_items(seed)
    return pool


def _check_progressivity(seed: dict) -> list[str]:
    """Vérifie que chaque recette n'utilise que des items déjà atteignables.

    Une seed générée est ordonnée : parcours séquentiel, comme le joueur qui
    débloque les recettes. Un dump est un état statique sans ordre de
    déblocage : on calcule le point fixe des recettes fabricables, sinon
    l'ordre du JSON inventerait des violations. ``on_the_spot_unlock`` reste
    toujours franchissable. Retourne la liste des violations.
    """
    ordered = (seed.get("meta") or {}).get("origin") != "dump"
    if ordered:
        return _check_progressivity_ordered(seed)
    return _check_progressivity_unordered(seed)


def _find_obtainable_cycle(
    target: str, pending: list[dict], pool: set[str]
) -> set[str] | None:
    producers: dict[str, list[dict]] = {}
    for recipe in pending:
        for res in recipe.get("results") or []:
            name = res.get("name")
            if name:
                producers.setdefault(name, []).append(recipe)
    return find_recipe_cycle(
        target,
        pending,
        producers,
        infinite=pool,
        available=pool,
        require_positive=False,
        max_depth=MAX_CYCLE_DEPTH,
        max_expansions=MAX_CYCLE_EXPANSIONS,
    )


def _check_progressivity_ordered(seed: dict) -> list[str]:
    issues: list[str] = []
    pool = _initial_pool(seed)
    for recipe in seed.get("recipes", []):
        missing = [
            ing["name"]
            for ing in recipe.get("ingredients", [])
            if ing["name"] not in pool
        ]
        if missing and not recipe.get("on_the_spot_unlock"):
            issues.append(
                f"progressivité: {recipe['name']} utilise {missing} avant obtention"
            )
        for product in recipe.get("results", []):
            pool.add(product["name"])
        for ingredient in recipe.get("ingredients", []):
            pool.add(ingredient["name"])
    return issues


def _check_progressivity_unordered(seed: dict) -> list[str]:
    pending = list(seed.get("recipes", []))
    pool = _initial_pool(seed)
    while True:
        progressed = False
        for recipe in list(pending):
            missing = [
                ing["name"]
                for ing in recipe.get("ingredients", [])
                if ing["name"] not in pool
            ]
            if missing and not recipe.get("on_the_spot_unlock"):
                continue
            pending.remove(recipe)
            for product in recipe.get("results", []):
                pool.add(product["name"])
            for ingredient in recipe.get("ingredients", []):
                pool.add(ingredient["name"])
            progressed = True
        for name, item in (seed.get("items") or {}).items():
            if not isinstance(item, dict) or name not in pool:
                continue
            burnt = item.get("burnt_result")
            if burnt and burnt not in pool:
                pool.add(burnt)
                progressed = True
            for product in item.get("rocket_launch_products") or []:
                product_name = product.get("name") if isinstance(product, dict) else None
                if product_name and product_name not in pool:
                    pool.add(product_name)
                    progressed = True
        if not progressed:
            targets = sorted(
                {
                    ing["name"]
                    for recipe in pending
                    for ing in recipe.get("ingredients") or []
                    if ing["name"] not in pool
                }
            )
            for target in targets:
                cycle = _find_obtainable_cycle(target, pending, pool)
                if cycle is None:
                    continue
                pool |= cycle
                progressed = True
                break
        if not progressed:
            break
    issues: list[str] = []
    for recipe in pending:
        missing = [
            ing["name"]
            for ing in recipe.get("ingredients", [])
            if ing["name"] not in pool
        ]
        issues.append(
            f"progressivité: {recipe['name']} utilise {missing} jamais obtenable"
        )
    return issues


def _check_completeness(seed: dict) -> list[str]:
    """Vérifie que chaque exigence de victoire est productible ou patchée.

    Compare ``seed["victory_requirements"]`` à l'union des résultats de
    recettes et des ressources présentes sur la carte (patchs + lacs).
    Retourne la liste des exigences inatteignables (vide si la seed offre
    une voie complète vers la victoire).
    """
    required = seed.get("victory_requirements", [])
    produced = {p["name"] for r in seed.get("recipes", []) for p in r.get("results", [])}
    patched = _initial_pool(seed)
    missing = [req for req in required if req not in produced | patched]
    if missing:
        return [f"complétude: exigences de victoire inatteignables: {missing}"]
    return []
