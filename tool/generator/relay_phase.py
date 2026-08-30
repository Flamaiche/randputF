"""Phase du relais des ressources non-infinies (README §7, §8 et §9.3).

Au tout début, le joueur possède toutes les ressources : patchs ET ressources
environnementales (arbres -> wood, rochers -> stone, poissons -> raw-fish).
Ces dernières ne sont PAS infinies : elles servent de matière première du
bootstrap (fabriquer les extracteurs, les premiers bâtiments, etc.), mais ce
n'est pas tenable à long terme.

Cette phase tourne APRÈS toutes les phases productrices de recettes (starter,
électricité, récursif) et crée, pour chaque produit dont la recette générée
utilise un item environnemental en ingrédient, une RECETTE RELAIS :

- même produit ;
- ingrédients tirés uniquement dans le POOL GELÉ DE DÉBUT DE RUN (instantané
  de l'état APRÈS le starter + électricité, AVANT le récursif) : un relais ne
  dépend jamais d'un bâtiment ou d'un item débloqué seulement après (science
  packs, oil-refinery, etc.) — il reste donc utilisable dès le départ ;
- bâtiment de craft limité à ceux déjà obtenables dans ce même instantané
  (jamais de déblocage sur le tas hors pool) ;
- recettes relais dispatchées, réparties au hasard, dans les 3 techs qui
  suivent les techs gratuites du starter, puis consolidées en techs de
  prologue (≤ 5 unlocks chacune, §13 — jamais une tech géante). Ces prologue
  ne se paient PAS en science packs : elles se
  débloquent par HAND-CRAFT d'un item du bootstrap (§7, §9.3) — façon vanilla
  (automation/logistics), le joueur fabrique l'item à la main et la tech
  s'active tout de suite, au lieu de rester dépendant du bois/pierre/poisson
  ou d'attendre un laboratoire.

Anti-cycle §8 : les recettes relais ne dépendent jamais d'un produit relais
plus ancien (le set de produits relayés est ajouté aux ingrédients interdits
des relais suivants). Le graphe relais est donc un DAG.
"""

from __future__ import annotations

import random

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_ITEM, VanillaDB
from tool.generator.recipes import ProgressionState, _make_recipe
from tool.generator.tech_tree import _MAX_PER_TECH
from tool.prototypes.relay import RelayConfig

_config = RelayConfig()

# Suffixes des techs de dispatch (jamais un chiffre : un nom de tech en `-N`
# force des niveaux contigus dans Factorio).
_DISPATCH_LABELS = ("a", "b", "c")


def set_config(config: dict) -> None:
    global _config
    _config = RelayConfig.from_config(config)


def build_relay_recipes(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    base: ProgressionState | None = None,
) -> list[dict]:
    """Crée les recettes relais et les ajoute à ``state.recipes``.

    ``base`` est l'instantané GELÉ du pool de début de run (état après le
    starter + électricité, avant le récursif) : les ingrédients d'un relais et
    son bâtiment de craft en sont exclusivement tirés. ``state`` est l'état
    complet (contient les recettes finales à scanner). Sans ``base`` fourni,
    on prend l'état courant (utile pour les tests unitaires).

    Retourne la liste des produits relayés :
    ``[{product_kind, product, recipe_name}, ...]``.

    Le scan est relancé jusqu'à stabilité : les recettes créées « sur le tas »
    pendant le tirage d'un relais (déblocage d'un bâtiment, §9.3) peuvent à
    leur tour consommer des environnementaux et méritent leur propre relais.
    """
    if base is None:
        base = state
    relays: list[dict] = []
    relayed_products: set[str] = set()
    while True:
        added = 0
        for recipe in list(state.recipes):
            if not _uses_environmental(recipe):
                continue
            product = next(
                (r for r in recipe.get("results", []) if r["type"] == SLOT_ITEM),
                None,
            )
            # Jamais de relais pour un environnemental lui-même (il n'a pas de
            # recette, il se récolte à la main).
            if product is None or product["name"] in ENVIRONMENTAL_ITEMS:
                continue
            if product["name"] in relayed_products:
                continue
            relay = _make_relay_recipe(rng, db, base, product, relayed_products)
            if relay is None:
                continue
            state.recipes.append(relay)
            relayed_products.add(product["name"])
            relays.append(
                {
                    "product_kind": product["type"],
                    "product": product["name"],
                    "recipe_name": relay["name"],
                }
            )
            added += 1
        if added == 0:
            break
    return relays


def dispatch_relay_steps(
    relays: list[dict],
    rng: random.Random | None = None,
) -> list[dict]:
    """Répartit les recettes relais dans les 3 techs qui SUIVENT les techs
    gratuites du starter (§9.3).

    La répartition est aléatoire (mélangée) quand un ``rng`` est fourni ;
    sinon l'ordre de création est conservé (déterministe, pour les tests).

    Chaque step se recherche immédiatement (cost=[], count=1, sans packs) :
    ce sont les 3 premières recherches que le joueur lance après le bootstrap,
    pas des free_researches — le bootstrap reste en route unique le temps
    d'arriver aux recettes propres."""
    names = [r["recipe_name"] for r in relays]
    if not names:
        return []
    if rng is not None:
        rng.shuffle(names)
    n_steps = min(len(names), _config.max_dispatch_steps)
    base, extra = divmod(len(names), n_steps)
    steps: list[dict] = []
    index = 0
    for i in range(n_steps):
        size = base + (1 if i < extra else 0)
        chunk = names[index : index + size]
        index += size
        label = _DISPATCH_LABELS[i]
        steps.append(
            {
                "id": f"randputf-relay-dispatch-{label}",
                "title": f"Ressources durables ({label.upper()})",
                "unlocks_recipes": chunk,
                "unlocks_buildings": [],
                "cost": [],
                "count": 1,
            }
        )
    return steps


def consolidate_intro_steps(
    relay_steps: list[dict],
    trigger_candidates: list[str] | None = None,
    rng: random.Random | None = None,
) -> list[dict]:
    """Consolide les recettes du bootstrap en techs « prologue ».

    Prend les recettes débloquées par les dispatches relais (les recettes
    propres du bootstrap) et les regroupe en techs prologue de **≤ 5 unlocks
    chacune** (plafond §13, être une tech de démarrage ne dispense pas du
    plafond de taille).

    Ces techs NE sont PAS des free_researches NI des recherches en laboratoire
    payées en science packs (cost=[]) : chacune se débloque par HAND-CRAFT
    d'un item du bootstrap (``trigger_candidates``, un item par prologue,
    tous distincts) — façon vanilla (automation/logistics se débloquent en
    fabriquant un objet). Au runtime, `control.lua` active la tech dès que le
    joueur fabrique l'item déclencheur à la main.

    ``rng`` fourni : tirage des déclencheurs ET mélange des recettes. Sinon
    déterminisme (déclencheur vide) pour les tests.
    """
    recipes: list[str] = []
    for step in relay_steps:
        recipes.extend(step["unlocks_recipes"] or [])

    unique: list[str] = []
    seen: set[str] = set()
    for r in recipes:
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if not unique:
        return []

    rng_local = rng or random.Random(0)
    if rng is not None:
        rng_local.shuffle(unique)

    # Regroupement des recettes du bootstrap en techs de prologue : jamais une
    # tech géante (toutes les recettes relais d'un coup) — chaque tech ne
    # dépasse pas le plafond de 5 unlocks (§13), comme toute autre tech.
    used_triggers: set[str] = set()
    steps: list[dict] = []
    for i, start in enumerate(range(0, len(unique), _MAX_PER_TECH)):
        chunk = unique[start : start + _MAX_PER_TECH]
        # Nombre d'items du déclencheur à HAN-CRAFTER pour débloquer la tech
        # (§9.3) : 2^(n + indice_science/4), JAMAIS un singleton (crafter 1
        # item = tech triviale, auto-complétée par la moindre fabrication du
        # bootstrap). `n` est tiré au hasard dans (1, 6] (1 exclu, 6 inclu) :
        # n ∈ {2,3,4,5,6}. `indice_science` = position de la science dans
        # l'ordre du tech tree : le prologue précède la chaîne des sciences,
        # il se cale donc sur la PREMIÈRE science (indice 1) — réutilisable tel
        # quel pour un tirage aléatoire parmi les techs plus profondes.
        n = rng_local.randint(2, 6)
        craft_trigger_count = round(2 ** (n + 1 / 4))
        steps.append(
            {
                "id": f"randputf-prologue-{i + 1}",
                "title": f"Prologue ({i + 1})",
                "unlocks_recipes": chunk,
                "unlocks_buildings": [],
                "cost": [],
                "count": 1,
                "craft_trigger": _pick_trigger(
                    rng_local, trigger_candidates, used_triggers
                ),
                "craft_trigger_count": craft_trigger_count,
            }
        )
    return steps


def _pick_trigger(
    rng: random.Random,
    candidates: list[str] | None,
    used: set[str],
) -> str | None:
    """Tire UN item de bootstrap distinct (jamais déjà attribué) comme
    déclencheur hand-craft d'une tech de prologue. ``candidates``
    absent/vide -> None (déterminisme test)."""
    if not candidates:
        return None
    pool = [c for c in candidates if c not in used]
    if not pool:
        return None
    rng.shuffle(pool)
    chosen = pool[0]
    used.add(chosen)
    return chosen


def _uses_environmental(recipe: dict) -> bool:
    for ingredient in recipe.get("ingredients", []):
        if (
            ingredient.get("type") == SLOT_ITEM
            and ingredient.get("name") in ENVIRONMENTAL_ITEMS
        ):
            return True
    return False


def _make_relay_recipe(
    rng: random.Random,
    db: VanillaDB,
    base: ProgressionState,
    product: dict,
    relayed_products: set[str],
) -> dict | None:
    """Tire la recette relais d'un produit.

    ``base`` (instantané gelé du début de run) fournit SON pool pour les
    ingrédients ET SES bâtiments comme whitelist de craft : un relais compile
    uniquement avec ce qui est déjà obtenable dès le départ.

    Ingrédients interdits : items environnementaux + produit lui-même +
    produits déjà relayés (dans l'ordre de création, les relais ne peuvent
    jamais dépendre d'un relais plus ancien -> DAG, anti-cycle §8)."""
    forbidden = (
        set(ENVIRONMENTAL_ITEMS) | relayed_products | {product["name"]}
    )
    eligible = [entry for entry in base.pool() if entry[1] not in forbidden]
    if not eligible:
        return None
    if product["type"] == SLOT_ITEM and not any(
        kind == SLOT_ITEM for kind, _ in eligible
    ):
        return None
    try:
        return _make_recipe(
            rng,
            db,
            base,
            product["type"],
            product["name"],
            frozenset(forbidden),
            recipe_name=f"{_config.prefix}{product['name']}",
            building_whitelist=frozenset(base.unlocked_buildings),
        )
    except ValueError:
        return None