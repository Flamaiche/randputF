from __future__ import annotations

from collections import Counter
from typing import Callable

RecipeCheck = Callable[[dict], bool] | None


def find_recipe_cycle(
    target: str,
    recipes: list[dict],
    producers_by_name: dict[str, list[dict]],
    *,
    infinite: set[str],
    available: set[str],
    require_positive: bool = True,
    require_infinite_external: bool = False,
    require_starter: bool = True,
    check_recipe: RecipeCheck = None,
    max_depth: int = 4,
    max_expansions: int = 600,
    max_multiplier: int = 64,
) -> set[str] | None:
    allowed = {recipe["name"] for recipe in recipes}
    distances: dict[str, int] = {target: 0}
    changed = True
    while changed:
        changed = False
        for recipe in recipes:
            known = [
                distances[ing["name"]]
                for ing in recipe.get("ingredients") or []
                if ing.get("name") in distances
            ]
            if not known:
                continue
            step = min(known) + 1
            for res in recipe.get("results") or []:
                name = res.get("name")
                if name and distances.get(name, step + 1) > step:
                    distances[name] = step
                    changed = True

    result: set[str] | None = None
    visits = 0

    def evaluate(nodes: tuple[str, ...], chain: tuple[dict, ...]) -> set[str] | None:
        members = set(nodes)
        flows: list[tuple[Counter[str], Counter[str]]] = []
        external: list[str] = []
        for recipe in chain:
            if check_recipe is not None and not check_recipe(recipe):
                return None
            produced: Counter[str] = Counter()
            consumed: Counter[str] = Counter()
            for res in recipe.get("results") or []:
                name = res.get("name")
                if name in members:
                    produced[name] += max(1, int(res.get("amount", 1) or 1))
            for ing in recipe.get("ingredients") or []:
                name = ing.get("name")
                if name in members:
                    consumed[name] += max(1, int(ing.get("amount", 1) or 1))
                elif name:
                    external.append(name)
            flows.append((produced, consumed))
        external_pool = infinite if require_infinite_external else available
        if any(name not in external_pool for name in external):
            return None
        if require_starter:
            starter = any(
                member in infinite or member in available for member in members
            )
            if not starter:
                starter = any(
                    name not in members and name in available for name in external
                )
            if not starter:
                return None
        multipliers = [1] * len(chain)
        for _ in range(max_multiplier):
            produced_total: Counter[str] = Counter()
            consumed_total: Counter[str] = Counter()
            for count, (produced, consumed) in zip(multipliers, flows):
                for name, amount in produced.items():
                    produced_total[name] += amount * count
                for name, amount in consumed.items():
                    consumed_total[name] += amount * count
            positive = produced_total[target] > consumed_total[target]
            balanced = all(
                produced_total[member] >= consumed_total[member]
                for member in members
            )
            if balanced and (not require_positive or positive):
                return members
            deficits = [
                member
                for member in members
                if produced_total[member] < consumed_total[member]
            ]
            if not deficits:
                return None if require_positive else members
            deficit = max(
                deficits, key=lambda member: consumed_total[member] - produced_total[member]
            )
            choices = [
                i
                for i, (produced, consumed) in enumerate(flows)
                if produced[deficit] - consumed[deficit] > 0
            ]
            if not choices:
                return None
            index = max(
                choices, key=lambda i: flows[i][0][deficit] - flows[i][1][deficit]
            )
            gain = flows[index][0][deficit] - flows[index][1][deficit]
            missing = consumed_total[deficit] - produced_total[deficit]
            step = (missing + gain - 1) // gain
            if multipliers[index] + step > max_multiplier:
                return None
            multipliers[index] += step
        return None

    def dfs(
        current: str,
        nodes: tuple[str, ...],
        chain: tuple[dict, ...],
        used: frozenset[str],
    ) -> None:
        nonlocal result, visits
        if (
            result is not None
            or len(chain) > max_depth
            or visits > max_expansions
        ):
            return
        candidates = [
            recipe
            for recipe in producers_by_name.get(current, [])
            if recipe["name"] in allowed and recipe["name"] not in used
        ]
        candidates.sort(
            key=lambda recipe: (len(recipe.get("ingredients") or []), recipe["name"])
        )
        for recipe in candidates:
            visits += 1
            if visits > max_expansions:
                return
            next_chain = chain + (recipe,)
            next_used = used | {recipe["name"]}
            ingredients = sorted(
                recipe.get("ingredients") or [],
                key=lambda ing: (
                    distances.get(ing.get("name"), 10**9),
                    ing.get("name") or "",
                ),
            )
            for ing in ingredients:
                name = ing.get("name")
                if not name:
                    continue
                if name == target:
                    found = evaluate(nodes, next_chain)
                    if found is not None:
                        result = found
                        return
                elif name in distances and name in producers_by_name and name not in nodes:
                    dfs(name, nodes + (name,), next_chain, next_used)
                    if result is not None:
                        return

    dfs(target, (target,), (), frozenset())
    return result
