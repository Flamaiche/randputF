"""Diagnostic SCC du graphe de production (§10ter, redesign).

L'ancien garde cassait les cycles inaccessibles sans électricité ou à rendement
net ≤ 0 en réécrivant/ajoutant des recettes de secours. Depuis le redesign
« bootstrap inline », la correction est faite à la création (oracle early,
`early_oracle.EarlyOracle`) et cette passe n'existe plus.

Ce module ne conserve QUE le diagnostic : ``find_cycles`` repère les SCC
du graphe produit→ingrédients et classe chaque cycle (atteignable sans
électricité ? rendement net ?). NET≤0 n'est plus un gate de correction —
seule l'atteignabilité pré-élec compte (assurée à la création).
"""
from __future__ import annotations

from tool.common.db import SLOT_FLUID, SLOT_ITEM, VanillaDB


def _item_products(db: VanillaDB, recipes: list[dict]) -> list[str]:
    """Produits (items) ayant au moins une recette, triés (déterminisme)."""
    return sorted(
        {
            res["name"]
            for recipe in recipes
            for res in recipe.get("results", [])
            if res["type"] == SLOT_ITEM
        }
    )


def _product_nodes(db: VanillaDB, recipes: list[dict]) -> list[str]:
    """Produits (items ET fluides) ayant au moins une recette, triés.

    Le cycle à casser se joue au niveau produit — que les recettes produisent un
    item ou un fluide — toutes les arêtes item→ingrédient entrent dans le graphe
    (anti-boucle transitive §10ter-redesign)."""
    return sorted(
        {
            res["name"]
            for recipe in recipes
            for res in recipe.get("results", [])
            if res["type"] in (SLOT_ITEM, SLOT_FLUID)
        }
    )


def _dependency_graph(db: VanillaDB, recipes: list[dict]):
    """Graphe produit → ingrédients-produits (anti-dépendance pour l'analyse).

    Nœud = produit item de la seed ; arête p→q s'il existe une recette
    produisant p ET consommant q (q lui-même produit par une recette de la
    seed). Retourne ``(succ, pred, self_loops)`` triés (déterminisme)."""
    nodes = _product_nodes(db, recipes)
    node_set = set(nodes)
    succ = {n: [] for n in nodes}
    pred = {n: [] for n in nodes}
    self_loops: set[str] = set()
    for recipe in recipes:
        res_items = [
            r["name"] for r in recipe.get("results", [])
            if r["type"] in (SLOT_ITEM, SLOT_FLUID) and r["name"] in node_set
        ]
        if not res_items:
            continue
        for product in res_items:
            for ing in recipe.get("ingredients", []):
                if ing["type"] not in (SLOT_ITEM, SLOT_FLUID) or ing["name"] not in node_set:
                    continue
                if ing["name"] == product:
                    self_loops.add(product)
                    continue
                if ing["name"] not in succ[product]:
                    succ[product].append(ing["name"])
                    pred[ing["name"]].append(product)
    for n in nodes:
        succ[n].sort()
        pred[n].sort()
    return succ, pred, self_loops


def _find_sccs(nodes: list[str], succ: dict[str, list[str]], pred: dict[str, list[str]]):
    """Composantes fortement connexes (Kosaraju itératif, ordre déterministe).

    Retourne ``(composante_par_nœud, liste de composantes triées)``."""
    visited: set[str] = set()
    order: list[str] = []
    for start in nodes:
        if start in visited:
            continue
        visited.add(start)
        stack: list[list] = [[start, 0]]
        while stack:
            u, idx = stack[-1]
            if idx < len(succ[u]):
                v = succ[u][idx]
                stack[-1][1] = idx + 1
                if v not in visited:
                    visited.add(v)
                    stack.append([v, 0])
            else:
                order.append(u)
                stack.pop()

    comp_of: dict[str, set[str]] = {}
    components: list[set[str]] = []
    visited.clear()
    for start in reversed(order):
        if start in visited:
            continue
        visited.add(start)
        comp: set[str] = set()
        stack = [start]
        while stack:
            u = stack.pop()
            comp.add(u)
            for v in pred[u]:
                if v not in visited:
                    visited.add(v)
                    stack.append(v)
        for n in comp:
            comp_of[n] = comp
        components.append(comp)
    return comp_of, components


def find_cycles(
    db: VanillaDB,
    recipes: list[dict],
    early_items: set[str],
) -> list[dict]:
    """Tous les cycles de production de la seed (SCC produit→ingrédients, y
    compris self-loops) avec leur diagnostic :

    - ``members`` : membres de la boucle (triés) ;
    - ``reachable`` : au moins un membre est dans le watershed pré-électricité ;
    - ``net_yield`` : Σ quantités membres produites − Σ quantités membres
      consommées par les recettes du cycle (≥ 1 contributeurs membres).
      Négatif → le cycle ne peut rien exporter vers l'extérieur.

    Une SCC à 1 nœud sans self-loop n'est pas un cycle (trivial). L'ordre de
    retour est trié par membre — déterminisme total."""
    succ, pred, self_loops = _dependency_graph(db, recipes)
    nodes = list(succ.keys())
    comp_of, components = _find_sccs(nodes, succ, pred)
    cycles: list[dict] = []
    for comp in components:
        members = sorted(comp)
        is_cycle = len(comp) >= 2 or any(m in self_loops for m in members)
        if not is_cycle:
            continue
        produced = 0
        consumed = 0
        for recipe in recipes:
            member_results = [
                r for r in recipe.get("results", [])
                if r["type"] in (SLOT_ITEM, SLOT_FLUID) and r["name"] in comp
            ]
            if not member_results:
                continue
            produced += sum(r.get("amount", 1) for r in member_results)
            consumed += sum(
                ing.get("amount", 1)
                for ing in recipe.get("ingredients", [])
                if ing["type"] in (SLOT_ITEM, SLOT_FLUID) and ing["name"] in comp
            )
        cycles.append(
            {
                "members": members,
                "reachable": bool(set(members) & early_items),
                "net_yield": produced - consumed,
            }
        )
    cycles.sort(key=lambda c: c["members"])
    return cycles