"""Tests de la phase relais (docs/recettes.md §9.3).

Les items environnementaux (arbres/rochers/poissons) servent au bootstrap du
début mais ne sont pas infinis : pour chaque produit dont la recette générée
en consomme, on crée une RECETTE RELAIS (même produit, ingrédients durables
uniquement) dispatchée dans les 3 premières techs.
"""

from __future__ import annotations

import random

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_FLUID, SLOT_ITEM
from tool.common.demo import build_demo_db
from tool.generator.map_patches import Patch
from tool.generator.relay_phase import build_relay_recipes, dispatch_relay_steps
from tool.generator.recipes import ProgressionState
from tool.generator.starter_chain import build_starter_chain


def _env_recipe(product: str, *durable: str) -> dict:
    """Recette bootstrap qui consomme TOUS les environnementaux (+ durables)."""
    ingredients = [
        {"type": SLOT_ITEM, "name": e, "amount": 1} for e in ENVIRONMENTAL_ITEMS
    ]
    ingredients += [{"type": SLOT_ITEM, "name": d, "amount": 1} for d in durable]
    return {
        "name": f"randputf-{product}",
        "energy": 1.0,
        "ingredients": ingredients,
        "results": [{"type": SLOT_ITEM, "name": product, "amount": 1}],
    }


def _make_state(*obtained: str) -> tuple[object, ProgressionState]:
    db = build_demo_db()
    state = ProgressionState()
    for name in obtained:
        state.mark_obtained(SLOT_FLUID, name) if name == "water" else state.mark_obtained(
            SLOT_ITEM, name
        )
    for env in ENVIRONMENTAL_ITEMS:
        state.mark_obtained(SLOT_ITEM, env)
    return db, state


def _relay_recipes_of(state: ProgressionState):
    return [r for r in state.recipes if r["name"].startswith("randputf-relay-")]


def test_relais_sans_ingredients_environnementaux():
    """Le relais produit le même item, mais uniquement avec du durable."""
    db, state = _make_state("iron-ore", "copper-ore", "coal")
    state.recipes.append(_env_recipe("transport-belt"))
    relays = build_relay_recipes(random.Random(1), db, state)
    assert relays, "un relais doit exister pour transport-belt"
    relay = next(r for r in _relay_recipes_of(state) if r["results"][0]["name"] == "transport-belt")
    env_ings = [i["name"] for i in relay["ingredients"] if i["name"] in ENVIRONMENTAL_ITEMS]
    assert not env_ings, f"relais encore dépendant des environnementaux: {env_ings}"
    assert relay["results"][0]["name"] == "transport-belt"
    assert relay["name"].startswith("randputf-relay-")


def test_relais_uniquement_pour_produits_non_environnementaux():
    """Jamais de recette relais pour wood/stone/raw-fish eux-mêmes."""
    db, state = _make_state("iron-ore")
    state.recipes.append(_env_recipe("wood"))  # produit environnemental
    relays = build_relay_recipes(random.Random(2), db, state)
    assert relays == []
    assert _relay_recipes_of(state) == []


def test_pas_de_relais_sans_recette_environnementale():
    db, state = _make_state("iron-ore")
    state.recipes.append(
        {
            "name": "randputf-iron-gear-wheel",
            "energy": 1.0,
            "ingredients": [{"type": SLOT_ITEM, "name": "iron-ore", "amount": 2}],
            "results": [{"type": SLOT_ITEM, "name": "iron-gear-wheel", "amount": 1}],
        }
    )
    relays = build_relay_recipes(random.Random(3), db, state)
    assert relays == []


def test_relais_pas_de_dependance_vers_relais_plus_ancien():
    """Graphe des relais = DAG : un relais ne dépend jamais d'un produit déjà
    relayé (sinon cycle relais->bootstrap->relais, §15.1)."""
    db, state = _make_state("coal")  # un seul item durable -> les relais se
    # recroisent forcément sur les produits déjà relayés
    state.mark_obtained(SLOT_ITEM, "transport-belt")
    state.mark_obtained(SLOT_ITEM, "electronic-circuit")
    state.recipes.append(_env_recipe("transport-belt"))
    state.recipes.append(_env_recipe("electronic-circuit"))

    relays = build_relay_recipes(random.Random(4), db, state)
    assert len(relays) >= 2

    relay_products = [r["product"] for r in relays]
    for i, info in enumerate(relays):
        recipe = next(r for r in _relay_recipes_of(state) if r["name"] == info["recipe_name"])
        for ing in recipe["ingredients"]:
            if ing["name"] in relay_products:
                # Seul un relais PLUS TARDIF peut fournir un ingrédient :
                # les edges relais vont toujours vers l'avant -> acyclique.
                assert relay_products.index(ing["name"]) > i, (
                    f"relais {info['recipe_name']} dépend d'un relais plus ancien"
                )


def test_relais_skippe_quand_pas_d_item_durable():
    """Seed 100% fluides sans item durable : le relais ne peut pas exister,
    on saute (la recette bootstrap environnementale reste la seule route)."""
    db, state = _make_state("water")  # obtenus : water + environnementaux
    state.recipes.append(_env_recipe("transport-belt"))
    relays = build_relay_recipes(random.Random(5), db, state)
    assert relays == []


def test_dispatch_dans_3_techs_max_gratuites():
    db, state = _make_state("iron-ore", "copper-ore", "coal")
    for product in ("transport-belt", "pipe-item", "iron-gear-wheel", "copper-cable", "steel-plate"):
        state.recipes.append(_env_recipe(product))
    relays = build_relay_recipes(random.Random(6), db, state)
    names = {r["recipe_name"] for r in relays}
    steps = dispatch_relay_steps(relays)

    assert 1 <= len(steps) <= 3
    unlocked = []
    for step in steps:
        assert step["cost"] == []
        assert step["count"] == 1
        unlocked.extend(step["unlocks_recipes"])
    assert sorted(unlocked) == sorted(names)  # chaque recette relais, une fois
    assert len(unlocked) == len(set(unlocked))


def test_dispatch_repartition_aleatoire_melange_les_relais():
    """Avec un rng seedé, les recettes relais sont réparties en ALÉATOIRE dans
    les 3 techs (mélangées), et non dans l'ordre de création."""
    db, state = _make_state("coal")
    for product in ("transport-belt", "pipe-item", "iron-gear-wheel", "copper-cable", "steel-plate"):
        state.recipes.append(_env_recipe(product))
    relays = build_relay_recipes(random.Random(7), db, state)

    ordered = dispatch_relay_steps(relays)
    shuffled = dispatch_relay_steps(relays, random.Random(7))

    assert shuffled != ordered, "le rng doit mélanger la répartition des relais"

    def flat(steps):
        return [r for s in steps for r in s["unlocks_recipes"]]

    assert sorted(flat(ordered)) == sorted(flat(shuffled))
    assert len(flat(shuffled)) == len(set(flat(shuffled)))
    assert 1 <= len(shuffled) <= 3
    assert all(s["cost"] == [] for s in shuffled)


def test_relais_limites_au_pool_de_base():
    """Les relais se tirent dans le pool GELÉ du début de run (après starter +
    électricité, avant récursif) : un item uniquement obtenable en profondeur
    (science pack, bâtiment tardif) n'apparaît JAMAIS dans un relais."""
    db, state = _make_state("iron-ore", "coal")
    state.mark_obtained(SLOT_ITEM, "science-pack")  # pool FINAL (post-récursif)
    state.recipes.append(_env_recipe("transport-belt"))

    base = ProgressionState()
    for env in ENVIRONMENTAL_ITEMS:
        base.mark_obtained(SLOT_ITEM, env)
    base.mark_obtained(SLOT_ITEM, "iron-ore")
    base.mark_obtained(SLOT_ITEM, "coal")

    relays = build_relay_recipes(random.Random(8), db, state, base)
    assert relays, "transport-belt consomme des environnementaux -> un relais existe"
    relay = next(r for r in _relay_recipes_of(state) if r["name"] == relays[0]["recipe_name"])
    ingredient_names = {i["name"] for i in relay["ingredients"]}
    assert "science-pack" not in ingredient_names, (
        f"relais dépendant d'un item du pool final: {sorted(ingredient_names)}"
    )
    assert not ingredient_names & set(ENVIRONMENTAL_ITEMS)


def test_integration_starter_100pct_fluides():
    """Cas d'école (seed 5) : starter sans patch item -> l'extracteur se
    fabrique au bootstrap avec du poisson ; la phase relais produit la version
    propre dispatchée en 1-3 techs."""
    db = build_demo_db()
    rng = random.Random(5)
    chain = build_starter_chain(rng, db, [Patch("fluid", "water", 1000)])

    env_using = [
        r for r in chain.state.recipes
        if any(i.get("name") in ENVIRONMENTAL_ITEMS for i in r.get("ingredients", []))
    ]
    assert env_using, "le starter 100% fluides doit consommer des environnementaux"

    base = ProgressionState()
    for env in ENVIRONMENTAL_ITEMS:
        base.mark_obtained(SLOT_ITEM, env)
    base.mark_obtained(SLOT_ITEM, "iron-ore")
    base.mark_obtained(SLOT_ITEM, "coal")
    relays = build_relay_recipes(rng, db, chain.state, base)
    assert relays, "au moins un relais doit exister"
    for info in relays:
        recipe = next(r for r in chain.state.recipes if r["name"] == info["recipe_name"])
        env_ings = {
            i["name"] for i in recipe["ingredients"]
            if i["name"] in ENVIRONMENTAL_ITEMS
        }
        assert not env_ings
        assert recipe["results"][0]["name"] == info["product"]
    steps = dispatch_relay_steps(relays)
    assert len(steps) <= 3
    assert all(s["cost"] == [] for s in steps)

def test_consolidate_intro_une_seule_tech_avec_peu_de_recettes():
    """§7 : pas assez de recettes distinctes pour 2 techs -> une seule."""
    import random
    from tool.generator.relay_phase import consolidate_intro_steps

    relay_steps = [
        {"id": "x1", "unlocks_recipes": ["randputf-relay-a"], "cost": [], "count": 1},
    ]
    steps = consolidate_intro_steps(relay_steps, None, random.Random(42))
    assert len(steps) == 1
    names = steps[0]["unlocks_recipes"]
    assert names == ["randputf-relay-a"]
    assert all(s["cost"] == [] for s in steps)


def test_consolidate_intro_max_cinq_unlocks_par_tech():
    """§7 : consolidation des recettes relais en techs prologue de ≤ 5 unlocks
    chacune (plafond §13, jamais de tech géante). Les techs débloquent
    UNIQUEMENT les recettes relais (le premier science pack est unlocké par le
    starter, pas par la prologue §7/§13)."""
    import random
    from tool.generator.relay_phase import consolidate_intro_steps

    relay_steps = [
        {"id": "x1", "unlocks_recipes": [f"randputf-relay-{c}" for c in "abcdef"]},
        {"id": "x2", "unlocks_recipes": [f"randputf-relay-{c}" for c in "gh"]},
    ]
    for seedv in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
        steps = consolidate_intro_steps(relay_steps, None, random.Random(seedv))
        assert 1 <= len(steps), f"seed {seedv}: aucune tech"
        all_recipes = [r for s in steps for r in s["unlocks_recipes"]]
        assert sorted(all_recipes) == sorted([
            f"randputf-relay-{c}" for c in "abcdefgh"
        ])
        seen = set()
        for r in all_recipes:
            assert r not in seen, f"seed {seedv}: doublon {r}"
            seen.add(r)
        for s in steps:
            assert len(s["unlocks_recipes"]) <= 5, f"seed {seedv}: {len(s['unlocks_recipes'])} unlocks"
            assert s["count"] == 1
            assert s["id"].startswith("randputf-prologue-")


def test_consolidate_intro_sans_relais():
    """§7 : aucune recette -> aucune tech de prologue."""
    import random
    from tool.generator.relay_phase import consolidate_intro_steps

    assert consolidate_intro_steps([], None, random.Random(3)) == []


def test_consolidate_intro_se_debloque_par_hand_craft():
    """§9.3 : chaque tech de prologue se débloque par HAND-CRAFT d'un item
    du bootstrap (déclencheur distinct, jamais en double) — pas par un coût
    de science pack (cost reste vide, count=1). La quantité à craft suit
    2^(n + 1/4) avec n ∈ (1, 6] (1 exclu, 6 inclu) — jamais un singleton."""
    import random
    from tool.generator.relay_phase import consolidate_intro_steps

    relay_steps = [
        {"id": "x1", "unlocks_recipes": ["randputf-relay-a"]},
    ]
    candidates = [
        "automation-science-pack", "boiler", "centrifuge",
    ]
    steps = consolidate_intro_steps(
        relay_steps, candidates, random.Random(9)
    )
    assert 1 <= len(steps) <= 2
    for s in steps:
        assert s["cost"] == [], f"{s['id']} n'a pas de coût packs"
        assert s["count"] == 1
        assert s["craft_trigger"], f"{s['id']} doit avoir un déclencheur hand-craft"
        assert s["craft_trigger"] in candidates
        count = s["craft_trigger_count"]
        assert isinstance(count, int) and 5 <= count <= 76, f"{s['id']}: quantité {count}"
    # déclencheurs tous distincts entre techs
    triggers = [s["craft_trigger"] for s in steps]
    assert len(triggers) == len(set(triggers))
