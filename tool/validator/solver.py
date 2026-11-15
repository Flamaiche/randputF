"""Vérification des invariants de solvabilité.

Implémente génériquement sur la structure seed :
1. anti-cycle : tri topologique (Kahn) sur le graphe prerequis → produit ;
2. progressivite : chaque recette n'utilise que des choses atteignables au
   moment de son deblocage, sauf ``on_the_spot_unlock`` ;
3. completude : presence d'une chaine vers les prerequis fusee.
"""

from __future__ import annotations

from tool.common.db import ENVIRONMENTAL_ITEMS


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


def _check_progressivity(seed: dict) -> list[str]:
    """Vérifie que chaque recette n'utilise que des items déjà atteignables.

    Le pool initial contient les ressources des patchs, des lacs et les items
    environnementaux (récoltables à la main). Les recettes sont parcourues
    dans l'ordre de la seed ; une recette dont un ingrédient manque au pool
    est signalée, sauf si elle porte ``on_the_spot_unlock``. Après contrôle,
    ses résultats et ingrédients rejoignent le pool. Retourne la liste des
    messages de violation (vide si tout est progressif).
    """
    issues: list[str] = []
    # Pool initial : patchs + lacs + ressources environnementales
    # (toujours récoltables à la main).
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
    """Vérifie que chaque exigence de victoire est productible ou patchée.

    Compare ``seed["victory_requirements"]`` à l'union des résultats de
    recettes et des ressources présentes sur la carte (patchs + lacs).
    Retourne la liste des exigences inatteignables (vide si la seed offre
    une voie complète vers la victoire).
    """
    required = seed.get("victory_requirements", [])
    produced = {p["name"] for r in seed.get("recipes", []) for p in r.get("results", [])}
    patched = {p["resource"] for p in seed.get("map", {}).get("patches", [])}
    patched |= {la["resource"] for la in seed.get("map", {}).get("lakes", [])}
    missing = [req for req in required if req not in produced | patched]
    if missing:
        return [f"complétude: exigences de victoire inatteignables: {missing}"]
    return []
