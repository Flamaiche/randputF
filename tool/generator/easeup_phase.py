"""Phase « ease-up » : recettes alternatives pour les crafts trop lourds.

Un « craft négatif » : un produit dont le graphe de production est TROP
PROFOND (beaucoup de sauts de recettes avant les ressources de base) ou
contient une BOUCLE. Cas concret relevé par le joueur : le premier pylône
exigeait ``utility-science-pack`` en ingrédient.

Tourne APRÈS toutes les phases productrices de recettes (starter, électricité,
récursif, endgame, relais) :

1. Détection : profondeur (= 1 + profondeur max de ses ingrédients, le plus
   petit chemin parmi ses recettes) et boucles, sur le graphe FINAL. Un
   produit est « lourd » si profondeur ≥ ``depth_threshold`` ou boucle.
2. Classement par impact : d'abord les plus consommés (bloquants), puis les
   plus profonds, les boucles d'abord.
3. Pour chaque produit retenu, une recette ALTERNATIVE ``randputf-ease-<item>``
   tirée du POOL GELÉ DE DÉBUT DE RUN (même ``base`` que les relais §9.3) :
   un ease-up ne dépend jamais d'un item débloqué en profondeur de seed.
4. Déblocage : techs de type PROLOGUE (hand-craft d'un item du bootstrap,
   ≤ 5 unlocks, §13) insérées juste après le bootstrap/relais.

Anti-cycle §8 : une recette ease-up n'utilise jamais son propre produit ni un
produit déjà ease-up — le graphe reste acyclique.

Flux RNG INDÉPENDANT (``make_rng``) : la phase n'altère pas les tirages des
phases précédentes — une seed existante se régénère à l'identique plus les
recettes/techs ease-up (additif pur).
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict

from tool.common.db import ENVIRONMENTAL_ITEMS, ROCKET_CHAIN, SLOT_ITEM, VanillaDB
from tool.generator.recipes import ProgressionState, _make_recipe
from tool.prototypes.easeup import EaseupConfig

_config = EaseupConfig()

# Suffixes des techs ease-up (jamais un chiffre : un nom de tech en `-N`
# force des niveaux contigus dans Factorio).
_BASE_LABELS = "abcdefghijklmnopqrstuvwxyz"

# Items de la chaîne de LANÇage (§14) : jamais ease-up. Un raccourci vers le
# produit lancé ou le silo trivialiserait la victoire.
_ENDGAME_EXCLUDED = frozenset({"rocket", "satellite", "rocket-silo", "rocket-part"})


def set_config(config: dict) -> None:
    global _config
    _config = EaseupConfig.from_config(config)


def make_rng(seed_value: int) -> random.Random:
    # Flux indépendant des autres phases (comme les lacs) : la phase ease-up
    # ne change pas le tirage du reste de la seed.
    return random.Random(f"randputF:easeup:{seed_value}")


def build_ease_up_recipes(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    base: ProgressionState | None = None,
    trigger_candidates: list[str] | None = None,
    used_triggers=(),
    steps_rng: random.Random | None = None,
) -> tuple[list[dict], list[dict]]:
    """Détecte les crafts lourds et ajoute leurs recettes alternatives.

    ``state`` : état complet (recettes FINALES à scanner) ; ``base`` :
    instantané GELÉ du pool de début de run (ingrédients + bâtiments des
    recettes ease-up). Retourne ``(eased, steps)`` : ``eased`` = produits
    ``{product_kind, product, recipe_name}``, ``steps`` = macro-steps de
    déblocage (techs prologue hand-craft).
    """
    if base is None:
        base = state
    candidates = _detect_heavy(db, state, base)
    eased: list[dict] = []
    eased_products: set[str] = set()
    seen_recipes = {r["name"] for r in state.recipes}
    for kind, name in candidates:
        recipe = _make_ease_recipe(rng, db, base, kind, name, eased_products)
        if recipe is None or recipe["name"] in seen_recipes:
            continue
        state.recipes.append(recipe)
        seen_recipes.add(recipe["name"])
        eased_products.add(name)
        eased.append(
            {
                "product_kind": kind,
                "product": name,
                "recipe_name": recipe["name"],
            }
        )
    steps = dispatch_ease_steps(eased, trigger_candidates, used_triggers, steps_rng or rng)
    return eased, steps


def dispatch_ease_steps(
    eased: list[dict],
    trigger_candidates: list[str] | None = None,
    used_triggers=(),
    rng: random.Random | None = None,
) -> list[dict]:
    """Regroupe les recettes ease-up en techs de type prologue (≤ 5 unlocks).

    Chaque tech se débloque par HAND-CRAFT d'un item du bootstrap (façon relais
    §9.3) : ``trigger_candidates`` fournis, un item par tech, tous distincts
    entre elles ET distincts des triggers déjà pris (``used_triggers``). Avec
    un ``rng`` : mélange des recettes et tirage.
    """
    names = [e["recipe_name"] for e in eased]
    if not names:
        return []
    rng_local = rng or random.Random(0)
    if rng is not None:
        rng_local.shuffle(names)

    used = set(used_triggers or ())
    steps: list[dict] = []
    label_index = 0
    for start in range(0, len(names), _config.unlocks_per_tech):
        chunk = names[start : start + _config.unlocks_per_tech]
        label = _label(label_index)
        label_index += 1
        n = rng_local.randint(2, 6)
        steps.append(
            {
                "id": f"randputf-ease-{label}",
                "title": f"Alternative ({label.upper()})",
                "unlocks_recipes": chunk,
                "unlocks_buildings": [],
                "cost": [],
                "count": 1,
                "craft_trigger": _pick_trigger(rng_local, trigger_candidates, used),
                "craft_trigger_count": round(2 ** (n + 1 / 4)),
            }
        )
    return steps


def _label(index: int) -> str:
    """Suffixe de tech (jamais un chiffre) : a,b,…,z, puis aa,ab,…"""
    if index < len(_BASE_LABELS):
        return _BASE_LABELS[index]
    first, second = divmod(index - len(_BASE_LABELS), len(_BASE_LABELS))
    return _BASE_LABELS[first] + _BASE_LABELS[second]


def _pick_trigger(
    rng: random.Random,
    candidates: list[str] | None,
    used: set[str],
) -> str | None:
    """Tire UN item du bootstrap distinct (jamais déjà attribué)."""
    if not candidates:
        return None
    pool = [c for c in candidates if c not in used]
    if not pool:
        return None
    rng.shuffle(pool)
    chosen = pool[0]
    used.add(chosen)
    return chosen


def _producers(state: ProgressionState) -> dict[tuple[str, str], list[int]]:
    """(kind, name) du produit → indices des recettes qui le produisent."""
    by_product: dict[tuple[str, str], list[int]] = defaultdict(list)
    for ridx, recipe in enumerate(state.recipes):
        for res in recipe.get("results", []):
            by_product[(res["type"], res["name"])].append(ridx)
    return by_product


def _usage_counter(state: ProgressionState) -> Counter:
    """Nombre de recettes (pas de quantité) qui consomment chaque ingrédient."""
    usage: Counter = Counter()
    for recipe in state.recipes:
        for ing in recipe.get("ingredients", []):
            usage[(ing["type"], ing["name"])] += 1
    return usage


def _compute_depths(state: ProgressionState) -> dict[tuple[str, str], int]:
    """Profondeur (nombre de sauts de recettes) de chaque produit.

    depth(P) = min sur les recettes qui produisent P de
    (1 + max depth de ses ingrédients) ; un ingrédient sans recette (ressource
    brute, environnemental, fluide) a depth 0. Relaxation de type
    Bellman-Ford bornée → convergente et hors boucles.
    """
    depth: dict[tuple[str, str], int] = {}
    produced: set[tuple[str, str]] = set()

    for recipe in state.recipes:
        for res in recipe.get("results", []):
            produced.add((res["type"], res["name"]))

    # Ingrédients jamais produits = sources (profondeur 0).
    for recipe in state.recipes:
        for ing in recipe.get("ingredients", []):
            key = (ing["type"], ing["name"])
            if key not in produced:
                depth[key] = 0

    by_product = _producers(state)

    def rec_depth(ridx: int) -> int:
        ings = state.recipes[ridx].get("ingredients", [])
        if not ings:
            return 1
        return 1 + max(depth.get((i["type"], i["name"]), 0) for i in ings)

    # Borne suffisante : la profondeur ne peut pas dépasser le nb de recettes.
    for _ in range(len(state.recipes) + 1):
        changed = False
        for ridx, _recipe in enumerate(state.recipes):
            d = rec_depth(ridx)
            for res in _recipe.get("results", []):
                key = (res["type"], res["name"])
                if depth.get(key, 10**9) > d:
                    depth[key] = d
                    changed = True
        if not changed:
            break
    return depth


def _is_circular(
    product: tuple[str, str],
    by_product: dict[tuple[str, str], list[int]],
    state: ProgressionState,
) -> bool:
    """Un produit est sur une boucle s'il se ré-atteint via ses ingrédients.

    BFS borné (pas de stack overflow sur le graphe final) : on part du produit,
    on traverse ses recettes de production ; si on retombe sur lui → boucle.
    ``visited`` garantit la terminaison même sur un sous-graphe fermé sans
    cycle contenant P.
    """
    frontier = {product}
    visited: set[tuple[str, str]] = set()
    for _ in range(len(state.recipes)):
        nxt: set[tuple[str, str]] = set()
        for key in frontier:
            for ridx in by_product.get(key, []):
                for ing in state.recipes[ridx].get("ingredients", []):
                    ikey = (ing["type"], ing["name"])
                    if ikey == product:
                        return True
                    if ikey not in visited:
                        visited.add(ikey)
                        nxt.add(ikey)
        if not nxt:
            break
        frontier = nxt
    return False


def _detect_heavy(
    db: VanillaDB,
    state: ProgressionState,
    base: ProgressionState,
) -> list[tuple[str, str]]:
    """Produits « crafts négatifs » : profondeur ≥ seuil OU sur une boucle.

    Retourne (kind, name) classés par impact décroissant (nombre de recettes
    qui les consomment en ingrédient), plafonnés à ``max_recipes``.
    """
    depths = _compute_depths(state)
    by_product = _producers(state)
    usage = _usage_counter(state)

    base_names = {n for _k, n in base.pool()}
    seen_relay_or_ease = {
        r["results"][0]["name"]
        for r in state.recipes
        if r["results"]
        and (
            r["name"].startswith("randputf-relay-")
            or r["name"].startswith(_config.prefix)
        )
    }

    ranked: list[tuple[int, bool, int, str, str]] = []
    for (kind, name), depth in depths.items():
        if name in base_names:
            continue
        if name in seen_relay_or_ease:
            continue
        item = db.items.get(name)
        if item is not None and item.is_science_pack:
            continue
        if name in ROCKET_CHAIN or name in _ENDGAME_EXCLUDED:
            continue
        circular = _is_circular((kind, name), by_product, state)
        if not circular and depth < _config.depth_threshold:
            continue
        # Tri : d'abord les plus PROFONDS (lourds à fabriquer), puis les boucles
        # (crafts infaisables par ce chemin), puis les plus CONSOMMÉS (les plus
        # bloquants). Les boucles bénignes (§8) restent éligibles mais ne
        # dévorent pas les slots au détriment d'un vrai craft lourd.
        ranked.append((-depth, not circular, -usage.get((kind, name), 0), kind, name))

    ranked.sort()
    return [(kind, name) for _d, _c, _u, kind, name in ranked[:_config.max_recipes]]


def _make_ease_recipe(
    rng: random.Random,
    db: VanillaDB,
    base: ProgressionState,
    kind: str,
    name: str,
    eased_products: set[str],
) -> dict | None:
    """Recette alternative d'un produit lourd, tirée du pool gelé de début.

    ``base`` fournit son pool (ingrédients) ET ses bâtiments (whitelist) :
    un ease-up compile uniquement avec ce qui est déjà obtenable dès le
    départ. Ingrédients interdits : environnementaux + produit lui-même +
    produits déjà ease-up (anti-cycle §8).
    """
    forbidden = set(ENVIRONMENTAL_ITEMS) | eased_products | {name}
    eligible = [entry for entry in base.pool() if entry[1] not in forbidden]
    if not eligible:
        return None
    if kind == SLOT_ITEM and not any(k == SLOT_ITEM for k, _ in eligible):
        return None
    try:
        return _make_recipe(
            rng,
            db,
            base,
            kind,
            name,
            frozenset(forbidden),
            recipe_name=f"{_config.prefix}{name}",
            building_whitelist=frozenset(base.unlocked_buildings),
        )
    except ValueError:
        return None