"""Primitives partagees de creation de recettes (README §7 et §8).

Coeur du generateur : deux fonctions que toutes les phases consomment.

- make_recipe / _make_recipe : tire une recette pour un produit donne
  (ingredients pondere dans le pool deja valide, montants, batiment compatible).
- ensure_obtainable : garantit qu'un item ou un fluide est obtenable, en
  creant au besoin la recette qui le produit (et recursivement les
  intermediaires manquants, ex. le batiment de craft).

Anti-cycle §8 garanti par construction, sur DEUX axes :

1. Ingredients : tires EXCLUSIVEMENT dans le pool deja valide au moment de
   la creation (ressources au sol, kit, recettes enregistrees avant), jamais
   dans l'ensemble en cours de fabrication ; le produit est ajoute a sa
   propre liste interdite.
2. Batiments (crafted_in) : un bâtiment n'est utilisable comme atelier qu'une
   fois son item obtenable resolu (deblockage sequentiel : item d'abord,
   inscription ensuite). Un garde ``pending`` detecte toute reentrance sur
   un produit deja en cours de resolution, ce qui rend impossible tout
   cycle du type chaudiere -> assembleur -> chaudiere.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.common.db import ENVIRONMENTAL_ITEMS, ROCKET_CHAIN, SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.prototypes.recipes import RecipeConfig

_config = RecipeConfig()

# Catégories de craft réelles du jeu (data.raw["recipe-category"] de base).
VALID_RECIPE_CATEGORIES = frozenset({
    "crafting",
    "basic-crafting",
    "advanced-crafting",
    "smelting",
    "chemistry",
    "crafting-with-fluid",
    "oil-processing",
    "rocket-building",
    "centrifuging",
})

# Seules ces catégories acceptent des fluides en ingrédients.
FLUID_RECIPE_CATEGORIES = frozenset({
    "crafting-with-fluid",
    "chemistry",
    "oil-processing",
})


def set_config(config: dict) -> None:
    global _config
    _config = RecipeConfig.from_config(config)


@dataclass
class ProgressionState:
    """Etat de progression partage par toutes les phases du pipeline."""

    obtained_items: set[str] = field(default_factory=set)
    obtained_fluids: set[str] = field(default_factory=set)
    unlocked_buildings: set[str] = field(default_factory=set)
    recipes: list[dict] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    pending: set[str] = field(default_factory=set)

    def is_obtained(self, kind: str, name: str) -> bool:
        if kind == SLOT_ITEM:
            return name in self.obtained_items
        return name in self.obtained_fluids

    def mark_obtained(self, kind: str, name: str) -> None:
        if kind == SLOT_ITEM:
            self.obtained_items.add(name)
        else:
            self.obtained_fluids.add(name)

    def pool(self) -> list[tuple[str, str]]:
        return [(SLOT_ITEM, n) for n in sorted(self.obtained_items)] + [
            (SLOT_FLUID, n) for n in sorted(self.obtained_fluids)
        ]


def ensure_obtainable(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    kind: str,
    name: str,
    forbidden: frozenset[str] = frozenset(),
    exclude_buildings: frozenset[str] = frozenset(),
    handcraft: bool = False,
) -> None:
    """Garantit que ``name`` est produisible, en creant sa recette si besoin."""
    if state.is_obtained(kind, name):
        return
    key = f"{kind}:{name}"
    if key in state.pending:
        raise ValueError(f"dépendance circulaire détectée sur {key}")
    state.pending.add(key)
    try:
        recipe = _make_recipe(
            rng, db, state, kind, name, forbidden | {name}, exclude_buildings,
            handcraft=handcraft,
        )
        state.recipes.append(recipe)
        state.mark_obtained(kind, name)
    finally:
        state.pending.discard(key)
    state.steps.append(
        {
            "type": "craft",
            "target": {"type": kind, "name": name},
            "recipe": recipe["name"],
            "crafted_in": recipe.get("crafted_in"),
        }
    )


def make_recipe(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    product_kind: str,
    product_name: str,
    forbidden: frozenset[str] = frozenset(),
) -> dict:
    """Tire et enregistre une recette pour ``product_name``, puis le marque obtenu."""
    for existing in state.recipes:
        if (
            existing["results"]
            and existing["results"][0]["type"] == product_kind
            and existing["results"][0]["name"] == product_name
        ):
            return existing
    key = f"{product_kind}:{product_name}"
    if key in state.pending:
        raise ValueError(f"dépendance circulaire détectée sur {key}")
    state.pending.add(key)
    try:
        recipe = _make_recipe(rng, db, state, product_kind, product_name, forbidden | {product_name})
    finally:
        state.pending.discard(key)
    state.recipes.append(recipe)
    state.mark_obtained(product_kind, product_name)
    return recipe


def _make_recipe(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    product_kind: str,
    product_name: str,
    forbidden: frozenset[str],
    exclude_buildings: frozenset[str] = frozenset(),
    recipe_name: str | None = None,
    building_whitelist: frozenset[str] | None = None,
    handcraft: bool = False,
) -> dict:
    """Tire une recette brute pour ``product_name``.

    ``recipe_name`` permet d'attribuer un nom different du nom canonique
    ``randputf-<produit>`` (utilise par les recettes relais §9.3, qui doivent
    coexister avec la recette de bootstrap du meme produit).

    ``building_whitelist`` restreint le choix de l'atelier aux bâtiments de la
    liste (jamais de déblocage sur le tas en dehors) : utilisé par les relais
    pour rester sur les bâtiments réellement obtenables dès le début du run.

    ``handcraft`` force une recette **craftable à la main** : ingrédients 100%
    solides (jamais de fluide) et AUCUN atelier (pas de catégorie → « crafting »
    par défaut, fabricable dans l'inventaire). Réservé au premier générateur
    électrique (§10) : un atelier électrique (assembling-machine-2, usine
    chimique...) exigerait l'électricité que ce générateur est censé amorcer —
    boucle bootstrap sinon."""
    eligible = [entry for entry in state.pool() if entry[1] not in forbidden]
    if not eligible:
        raise ValueError(
            f"pool vide pour produire {product_kind} {product_name} : "
            "aucune branche valide disponible"
        )

    max_ingredients = min(_config.roll_ingredient_count(rng), len(eligible))

    if handcraft:
        item_eligible = [e for e in eligible if e[0] == SLOT_ITEM]
        n_item_ing = min(max_ingredients, len(item_eligible))
        ingredients = _sample_items_weighed(rng, db, item_eligible, n_item_ing, state)
        rng.shuffle(ingredients)
        return _bake_recipe(rng, db, product_kind, product_name, ingredients, recipe_name)

    needs_fluid_out = product_kind == SLOT_FLUID
    max_fluid_ing = _available_fluid_inputs(db, state, exclude_buildings, building_whitelist)
    fluid_eligible = [e for e in eligible if e[0] == SLOT_FLUID]
    item_eligible = [e for e in eligible if e[0] == SLOT_ITEM]
    if _is_extractor_item(db, product_kind, product_name):
        # Un extracteur (perceuse, pumpjack, pompe offshore...) se fabrique
        # UNIQUEMENT avec des items : jamais avec un fluide — surtout pas avec
        # celui qu'il sert justement à extraire (anti-cycle §8).
        max_fluid_ing = 0
        fluid_eligible = []
    n_fluid_ing = min(rng.randint(0, min(len(fluid_eligible), max_fluid_ing)), max_ingredients)
    if needs_fluid_out and n_fluid_ing == 0:
        # Une sortie fluide sans entrée fluide reste autorisée (ex. chaudière),
        # mais on préfère garder au moins un fluide quand c'est possible.
        n_fluid_ing = min(1, min(len(fluid_eligible), max_fluid_ing))
    n_item_ing = min(max_ingredients - n_fluid_ing, len(item_eligible))
    ingredients = (
        rng.sample(fluid_eligible, n_fluid_ing)
        + _sample_items_weighed(rng, db, item_eligible, n_item_ing, state)
    )
    rng.shuffle(ingredients)

    building = _pick_building(
        rng, db, state, n_item_ing, n_fluid_ing, needs_fluid_out, product_name,
        exclude_buildings, building_whitelist,
    )
    if building is None and needs_fluid_out:
        raise ValueError(
            f"recette {product_name} sans bâtiment mais avec des fluides : "
            "aucun atelier fluide disponible "
            f"(n_fluid_ing={n_fluid_ing}, needs_fluid_out=True, "
            f"unlocked={sorted(state.unlocked_buildings)})"
        )
    if building is None and n_fluid_ing > 0:
        # Bootstrap (§2) : si aucun atelier ne peut encore traiter des fluides,
        # on retire les fluides de la recette (ex. premier bâtiment d'une seed
        # 100% fluides) ; le produit, lui, est un item craftable à la main.
        n_fluid_ing = 0
        n_item_ing = min(max_ingredients - 0, len(item_eligible))
        ingredients = _sample_items_weighed(rng, db, item_eligible, n_item_ing, state)
        rng.shuffle(ingredients)
        building = _pick_building(
            rng, db, state, n_item_ing, 0, False, product_name, exclude_buildings,
            building_whitelist,
        )

    recipe = _bake_recipe(rng, db, product_kind, product_name, ingredients, recipe_name)
    if building is None:
        # Bootstrap a la main (dernier recours, cf. four de pierre vanilla) :
        # recette sans categorie ni atelier, fabricable dans l'inventaire.
        return recipe
    recipe["category"] = _recipe_category(building, n_fluid_ing > 0, needs_fluid_out)
    recipe["crafted_in"] = building.name
    return recipe


def _bake_recipe(rng, db, product_kind, product_name, ingredients, recipe_name=None):
    """Assemble le dictionnaire de recette (nom, energy, ingrédients, résultats)
    hors atelier : le choix du bâtiment (`crafted_in`/`category`) est laissé à
    l'appelant. Sans atelier la recette a aucune catégorie → « crafting » par
    défaut, fabricable dans l'inventaire du joueur."""
    final_name = recipe_name if recipe_name is not None else _config.recipe_name(product_name)
    result_amount = _config.roll_result_amount(rng)
    if product_kind == SLOT_ITEM and not _item_is_stackable(db, product_name):
        # Item non-stackable (armure, arme, véhicule...) : une recette ne peut
        # en produire qu'un seul exemplaire (erreur de chargement sinon).
        result_amount = 1
    return {
        "name": final_name,
        "energy": _config.roll_energy(rng),
        "ingredients": [
            {"type": kind, "name": name, "amount": _roll_amount(rng, db, name)}
            for kind, name in ingredients
        ],
        "results": [
            {"type": product_kind, "name": product_name, "amount": result_amount}
        ],
    }


def _has_production_item(db: VanillaDB, state: ProgressionState) -> bool:
    """Un item « de production » est hors ressources environnementales et hors
    kit de combat : patch item posé ou item déjà fabriqué par une recette.
    Tant qu'il n'en existe aucun, la partie est en cold start et les items
    environnementaux (arbres/rochers/poissons) font office de matière première
    — en particulier pour fabriquer les extracteurs."""
    for name in state.obtained_items:
        if name in ENVIRONMENTAL_ITEMS:
            continue
        item = db.items.get(name)
        if item is None:
            return True
        if item.subgroup != "combat":
            return True
    return False


def _sample_items_weighed(rng, db, eligible, n: int, state: ProgressionState):
    """Échantillonne ``n`` items sans remise, pondérés par leur statut
    environnemental. En cold start (aucun item de production), les items
    environnementaux sont prioritaires ; dès que l'économie possède un item
    de production, ils redevenent rares (petites quantités, surtout en début)."""
    if n <= 0 or not eligible:
        return []
    cold_start = not _has_production_item(db, state)
    pool = list(eligible)
    picked = []
    for _ in range(min(n, len(pool))):
        weights = [
            _environmental_weight(entry[1], cold_start)
            for entry in pool
        ]
        total = sum(weights)
        threshold = rng.uniform(0.0, total)
        acc = 0.0
        for index, weight in enumerate(weights):
            acc += weight
            if threshold <= acc:
                picked.append(pool.pop(index))
                break
    return picked


def _environmental_weight(name: str, cold_start: bool) -> float:
    """Poids d'un item environnemental comme ingrédient : fort uniquement en
    cold start (seed sans aucun item de production), faible ensuite."""
    if name not in ENVIRONMENTAL_ITEMS:
        return 1.0
    if cold_start:
        return _config.environmental_weight_starved
    return _config.environmental_weight_rich


def _roll_amount(rng, db, name: str) -> int:
    """Quantité d'un ingrédient. Les ressources environnementales restent en
    petite quantité même quand elles sont prioritaires (sans patch item). Un
    item non-stackable (armure, arme, véhicule...) ne peut jamais être
    consommé qu'en 1 exemplaire par recette (erreur de chargement sinon)."""
    if not _item_is_stackable(db, name):
        return 1
    if name in ENVIRONMENTAL_ITEMS:
        return rng.randint(1, _config.environmental_amount_max)
    return _config.roll_ingredient_amount(rng)


def _item_is_stackable(db: VanillaDB, name: str) -> bool:
    """Item inconnu → supposé empilable (ne jamais bloquer une recette)."""
    item = db.items.get(name)
    return item is None or item.is_stackable


def _recipe_category(building, fluid_ing: bool, fluid_out: bool) -> str:
    """Catégorie de craft réelle supportée par le bâtiment.

    ``building.functional_type`` (transformer/extractor/...) n'est pas une
    recipe-category du jeu : il faut une valeur de ``crafting_categories`` qui
    existe dans data.raw["recipe-category"] et accepte les fluides.
    """
    cats = [c for c in building.crafting_categories if c in VALID_RECIPE_CATEGORIES]
    if fluid_ing or fluid_out:
        cats = [c for c in cats if c in FLUID_RECIPE_CATEGORIES]
    if not cats:
        # Sécurité : jamais de fluide en catégorie "crafting" (erreur 2.0).
        return "crafting-with-fluid" if (fluid_ing or fluid_out) else "crafting"
    return cats[0]


def _available_fluid_inputs(db, state, exclude_buildings: frozenset[str],
                            whitelist: set[str] | None = None) -> int:
    """Nombre max d'entrées fluides parmi les bâtiments réellement utilisables
    à ce moment : débloqués prioritairement, sinon déblocables sans cycle."""
    def fluid_of(b) -> int:
        return b.fluid_inputs

    def usable(b) -> bool:
        if whitelist is not None:
            return b.name in whitelist and _is_atelier(b)
        return b.name in state.unlocked_buildings and _is_atelier(b)

    unlocked = [b for b in db.buildings.values()
                if usable(b) and b.name not in exclude_buildings]
    if unlocked:
        return max((fluid_of(b) for b in unlocked), default=1)

    if whitelist is not None:
        return 1

    reachable = [b for b in db.buildings.values()
                 if b.name not in exclude_buildings and _is_atelier(b)
                 and not _blocked_building(db, state, b.name)]
    return max((fluid_of(b) for b in reachable), default=1)


def _max_fluid_inputs(db) -> int:
    """Nombre max d'entrées fluides qu'un bâtiment de craft du jeu accepte."""
    best = 0
    for b in db.buildings.values():
        if _is_atelier(b):
            best = max(best, b.fluid_inputs)
    return max(best, 1)


def _is_atelier(b) -> bool:
    """Un atelier est un bâtiment capable de fabriquer : il possède au moins
    une recipe-category réelle dans ses crafting_categories."""
    return bool(b.crafting_categories and any(c in VALID_RECIPE_CATEGORIES for c in b.crafting_categories))


def _blocked_building(db, state, building_name: str) -> bool:
    item = _item_for_building(db, building_name)
    return item is not None and f"{SLOT_ITEM}:{item.name}" in state.pending


def _weighted_choice(rng: random.Random, weighted: list[tuple[int, int]]) -> int:
    values, weights = zip(*weighted)
    return rng.choices(values, weights=weights, k=1)[0]


def _pick_building(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    n_item_ing: int,
    n_fluid_ing: int,
    needs_fluid_out: bool,
    product_name: str,
    exclude_buildings: frozenset[str],
    whitelist: frozenset[str] | None = None,
):
    def fits(b) -> bool:
        return (
            _is_atelier(b)
            and b.item_input_slots >= n_item_ing
            and b.fluid_inputs >= n_fluid_ing
            and (not needs_fluid_out or b.fluid_outputs >= 1)
        )

    def blocked(b) -> bool:
        return _blocked_building(db, state, b.name)

    if whitelist is not None:
        # Whitelist = pas de déblocage sur le tas : uniquement les bâtiments
        # déjà obtenables (relais §9.3, gelés sur le pool de début de run).
        candidates = [
            b
            for b in db.buildings.values()
            if b.name in whitelist and b.name not in exclude_buildings and fits(b)
        ]
        return rng.choice(candidates) if candidates else None

    candidates = [
        b
        for b in db.buildings.values()
        if b.name in state.unlocked_buildings and b.name not in exclude_buildings and fits(b)
    ]
    if candidates:
        return rng.choice(candidates)

    candidates = [
        b
        for b in db.buildings.values()
        if b.name not in exclude_buildings and fits(b) and not blocked(b)
    ]
    if not candidates:
        return None
    building = rng.choice(candidates)
    _unlock_building(rng, db, state, building, product_name, exclude_buildings)
    return building


def _unlock_building(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
    requester: str,
    exclude_buildings: frozenset[str] = frozenset(),
    handcraft: bool = False,
) -> None:
    """Debloque un bâtiment : son item est resolu AVANT son inscription."""
    item = _item_for_building(db, building.name)
    if item is not None:
        ensure_obtainable(
            rng,
            db,
            state,
            SLOT_ITEM,
            item.name,
            frozenset({item.name, requester}),
            exclude_buildings=exclude_buildings | frozenset({building.name}),
            handcraft=handcraft,
        )
    state.unlocked_buildings.add(building.name)
    _ensure_burner_fuel(rng, db, state, building)


def _ensure_burner_fuel(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    building,
) -> None:
    """Garantit un combustible à tout bâtiment en consommant un (burner) :
    four, foreuse thermique, chaudière (boiler), burner-generator…

    Un bâtiment dont `energy_type == "burner"` a besoin d'un combustible ITEM
    pour fonctionner (les fluides sont gérés à part, §10). On pioche un item
    combustible au hasard parmi tous et on le rend OBTENABLE sur le tas (§9.3)
    : s'il n'est pas encore produit par la seed, on crée sa recette
    (`randputf-<fuel>`). Un fuel déjà obtenu est un no-op.

    La chaîne fusée (dont `rocket-fuel`) est exclue du tirage : réservée à la
    fin de partie (§14). Échec (pool vide / circularité) = on laisse le
    bâtiment sans combustible plutôt que de faire capoter la seed — même
    robustesse que le kit (§8)."""
    if building is None or building.energy_type != "burner":
        return
    fuel_items = [
        item for item in db.fuel_items() if item.name not in ROCKET_CHAIN
    ]
    if not fuel_items:
        return
    fuel = rng.choice(fuel_items)
    try:
        ensure_obtainable(rng, db, state, SLOT_ITEM, fuel.name)
    except ValueError:
        pass


def _item_for_building(db: VanillaDB, entity_name: str):
    return next((i for i in db.items.values() if i.place_result == entity_name), None)


def _is_extractor_item(db: VanillaDB, product_kind: str, product_name: str) -> bool:
    """Vrai si le produit est l'item qui place une entité extractrice (perceuse,
    pumpjack, pompe offshore). De telles entités se fabriquent uniquement avec
    des items : jamais avec un fluide ingrédient (anti-cycle §8)."""
    if product_kind != SLOT_ITEM:
        return False
    item = db.items.get(product_name)
    if item is None or not item.place_result:
        return False
    building = db.buildings.get(item.place_result)
    return building is not None and building.functional_type == "extractor"
