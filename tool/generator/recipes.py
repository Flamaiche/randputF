"""Primitives partagees de creation de recettes (§7/§8).

- make_recipe / _make_recipe : recette pour un produit (ingredients ponderes
  dans le pool deja valide, montants, batiment compatible).
- ensure_obtainable : garantit qu'un item/fluide est obtenable, en creant au
  besoin sa recette (et recursivement les intermediaires manquants).

Anti-cycle §8 garanti par construction : ingredients tires EXCLUSIVEMENT dans
le pool deja valide (le produit est ajoute a sa propre liste interdite) et
batiments resolus sequentiellement (item d'abord, inscription ensuite) ;
le garde ``pending`` detecte toute reentrance (cycle chaudiere > assembleur >
chaudiere impossible).
- Anti-boucle transitive (§10ter-redesign) : pour produire ``name``, on interdit
  non seulement ``name`` lui-meme mais tout ingredient deja ATTEIGNABLE depuis
  ``name`` dans le graphe de dependances courant (cloture des ancetres). Quel
  que soit le craft de ``name`` (primaire, relais, ease, balayage), un
  ingredient ne peut jamais refermer de cycle produit→produit : le graphe
  complet reste un DAG, cycle et « craft negatif » exclus a la source.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

from tool.common.db import (
    SLOT_FLUID,
    SLOT_ITEM,
    ROCKET_CHAIN,
    VALID_RECIPE_CATEGORIES,
    ItemDef,
    VanillaDB,
    has_hidden_recipe,
    is_fixed_crafter,
    is_fixed_fluid_crafter,
)
from tool.generator.early_oracle import EarlyOracle
from tool.prototypes.recipes import RecipeConfig

_config = RecipeConfig()

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
    # Équilibre production/consommation (C2) : compteurs cumulés, cible tirée
    # une fois par seed ; pondère le tirage des ingrédients (consommer le
    # surplus) et le choix des produits (ne pas reproduire la pléthore).
    production: Counter = field(default_factory=Counter)
    consumption: Counter = field(default_factory=Counter)
    balance_target: float | None = None
    # Assignation de fluides aux bâtiments à comportement fixe (§6/§10) :
    # {building_name: {"input": fluid, "output"?: fluid}}. Rempli par
    # electricity.resolve_electricity et building_fluids.assign_building_fluids.
    building_fluid_assignments: dict = field(default_factory=dict)
    # Bootstrap inline (§10ter) : watershed pré-électricité, actif pendant le
    # starter + l'électricité. Actif, `_make_recipe` tire UNIQUEMENT dans ce
    # watershed et sans atelier électrique — toute recette promise du starter
    # est jouable pré-élec par construction.
    early: EarlyOracle = field(default_factory=EarlyOracle)

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

    def ensure_balance_target(self, rng: random.Random) -> None:
        """C2 : tire une fois la cible d'équilibre cons/prod de la seed,
        uniformément entre `balance_min` et `balance_max` (défaut 3/16..2/3)."""
        if self.balance_target is None:
            self.balance_target = rng.uniform(_config.balance_min, _config.balance_max)

    def record_recipe(self, recipe: dict) -> None:
        """C2 : incrémente production/consommation depuis une recette posée."""
        for res in recipe.get("results") or []:
            self.production[res["name"]] += res.get("amount", 1)
        for ing in recipe.get("ingredients") or []:
            self.consumption[ing["name"]] += ing.get("amount", 1)

    def balance_factor(self, name: str) -> float:
        """C2 : facteur de pondération d'équilibre pour `name`.

        ratio = consommation / production : bas = produit peu consommé
        (pléthore), haut = consommé mais peu produit (rare). La cible
        `balance_target` est le ratio « juste ». Orienté par usage : comme
        ingrédient on récompense la pléthore (facteur > 1) et on pénalise la
        rareté (< 1) ; le signe inverse sert côté production. Absent du
        comptage → 1.0."""
        if name not in self.production and name not in self.consumption:
            return 1.0
        ratio = self.consumption.get(name, 0) / (self.production.get(name, 0) + 1e-9)
        t = self.balance_target or 1.0
        return _config.balance_weight(ratio, t)


def ensure_obtainable(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    kind: str,
    name: str,
    forbidden: frozenset[str] = frozenset(),
    exclude_buildings: frozenset[str] = frozenset(),
    handcraft: bool = False,
    force: bool = False,
    finite_materials: bool = False,
) -> None:
    """Garantit que ``name`` est produisible, en creant sa recette si besoin.

    ``force=True`` crée la recette même si l'item est déjà obtenu (cas d'un
    patch au sol, §6) : un extracteur-patch doit avoir une recette starter
    (tech d'extraction, §7), sinon il ne serait craftable qu'en profondeur.
    ``finite_materials=True`` interdit items environnementaux et fluides (la
    recette se fabrique exclusivement avec de la matière produite)."""
    if state.is_obtained(kind, name) and not force:
        return
    # Dédup : recette déjà présente (ex. bootstrap) → rien à créer, pas de
    # double step, on marque simplement l'obtention.
    for existing in state.recipes:
        if (
            existing["results"]
            and existing["results"][0]["type"] == kind
            and existing["results"][0]["name"] == name
        ):
            state.mark_obtained(kind, name)
            return
    key = f"{kind}:{name}"
    if key in state.pending:
        raise ValueError(f"dépendance circulaire détectée sur {key}")
    state.pending.add(key)
    try:
        recipe = _make_recipe(
            rng, db, state, kind, name, forbidden | {name}, exclude_buildings,
            handcraft=handcraft, finite_materials=finite_materials,
        )
        state.early.extend(db, recipe)
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
    force_building=None,
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
        recipe = _make_recipe(rng, db, state, product_kind, product_name, forbidden | {product_name}, force_building=force_building)
    finally:
        state.pending.discard(key)
    state.early.extend(db, recipe)
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
    force_building=None,
    finite_materials: bool = False,
) -> dict:
    """Tire une recette brute pour ``product_name``.

    ``recipe_name`` : nom different du canonique ``randputf-<produit>``
    (recettes relais §9.3, qui coexistent avec la recette de bootstrap).
    ``building_whitelist`` : ateliers restreints à la liste (jamais de
    déblocage sur le tas en dehors) — relais §9.3.
    ``handcraft`` : recette craftable à la main — ingrédients 100% solides,
    aucun atelier. Réservé au bootstrap (§10) : le générateur d'amorçage ne
    peut exiger un atelier électrique (boucle bootstrap sinon).

    Les recettes de bootstrap (craftables à la main) DOUBLENT le coût de leurs
    ingrédients non infinis (wood/stone/raw-fish, `is_environmental`) : le
    début se joue sur ces ressources rares ; les relais (§9.3) fournissent
    ensuite les recettes « propres » sans elles."""
    eligible = [entry for entry in state.pool() if entry[1] not in forbidden]
    if not eligible:
        raise ValueError(
            f"pool vide pour produire {product_kind} {product_name} : "
            "aucune branche valide disponible"
        )
    # Anti-boucle transitive (§10ter-redesign) : interdire tout ingrédient déjà
    # capable de produire `product` via le graphe de dependances existant —
    # sinon la nouvelle arête referme un cycle produit→produit (quel que soit
    # le craft en cours : primaire, relais, ease, balayage §9.6). Le produit
    # lui-meme est deja dans ``forbidden`` ; ici on ferme la cloture des
    # ancetres. Quand le pool deja obtenu est entierement « en amont », on
    # limite le retrait aux ancetres directs cerclables (graphe si reduit, la
    # nouvelle arête ne peut pas boucler) au lieu d'echouer.
    ancestors = _ancestor_products(db, state, product_kind, product_name)
    if ancestors:
        narrow = [e for e in eligible if (e[0], e[1]) not in ancestors]
        if narrow:
            eligible = narrow
    if state.early.active:
        # Bootstrap inline (§10ter) : jamais d'ingrédient hors du watershed
        # pré-électricité courant — tout produit promis reste jouable sans
        # réseau (correct-by-construction).
        item_pool = [
            e for e in eligible
            if e[0] == SLOT_ITEM and state.early.in_watershed(SLOT_ITEM, e[1])
        ]
        fluid_pool = [
            e for e in eligible
            if e[0] == SLOT_FLUID and state.early.in_watershed(SLOT_FLUID, e[1])
        ]
        if not item_pool and not fluid_pool:
            raise ValueError(
                f"pool early vide pour produire {product_kind} {product_name} : "
                "aucun ingrédient obtenable sans électricité"
            )
        eligible = item_pool + fluid_pool
    if finite_materials:
        # Recette à matière finie (§7, chest du kit) : on bannit les items
        # environnementaux et tout fluide (infinis) — que des items produits.
        eligible = [
            e for e in eligible
            if e[0] == SLOT_ITEM
            and not db.items.get(e[1], ItemDef(name=e[1])).is_environmental
        ]
        if not eligible:
            raise ValueError(
                f"aucun ingrédient fini pour produire {product_kind} {product_name}"
            )

    max_ingredients = min(_config.roll_ingredient_count(rng), len(eligible))

    if handcraft:
        # Bootstrap du premier générateur (§10) : AUCUN atelier, ingrédients
        # 100% solides, et on bannit tout ingrédient dont la production exige
        # déjà un bâtiment électrique (il ne serait craftable qu'une fois le
        # réseau en place — anti-boucle).
        item_eligible = [
            e for e in eligible if e[0] == SLOT_ITEM
            and not _production_is_electric(db, state, e[1])
        ]
        n_item_ing = min(max_ingredients, len(item_eligible))
        ingredients = _sample_items_weighed(rng, db, item_eligible, n_item_ing, state)
        rng.shuffle(ingredients)
        return _bake_recipe(rng, db, state, product_kind, product_name, ingredients, recipe_name,
                            x2_environmental=True)

    needs_fluid_out = product_kind == SLOT_FLUID
    max_fluid_ing = _available_fluid_inputs(db, state, exclude_buildings, building_whitelist)
    fluid_eligible = [e for e in eligible if e[0] == SLOT_FLUID]
    item_eligible = [e for e in eligible if e[0] == SLOT_ITEM]
    if _is_extractor_item(db, product_kind, product_name):
        # Un extracteur se fabrique uniquement avec des items — jamais avec un
        # fluide, surtout pas celui qu'il sert à extraire (anti-cycle §8).
        max_fluid_ing = 0
        fluid_eligible = []
    n_fluid_ing = min(rng.randint(0, min(len(fluid_eligible), max_fluid_ing)), max_ingredients)
    if needs_fluid_out and n_fluid_ing == 0:
        # Sortie fluide sans entrée fluide autorisée (ex. chaudière), mais on
        # garde au moins un fluide d'entrée quand c'est possible.
        n_fluid_ing = min(1, min(len(fluid_eligible), max_fluid_ing))
    n_item_ing = min(max_ingredients - n_fluid_ing, len(item_eligible))
    ingredients = (
        rng.sample(fluid_eligible, n_fluid_ing)
        + _sample_items_weighed(rng, db, item_eligible, n_item_ing, state)
    )
    rng.shuffle(ingredients)

    building = _pick_building(
        rng, db, state, n_item_ing, n_fluid_ing, needs_fluid_out, product_name,
        exclude_buildings, building_whitelist, force_building=force_building,
    )
    if building is None and needs_fluid_out:
        raise ValueError(
            f"recette {product_name} sans bâtiment mais avec des fluides : "
            "aucun atelier fluide disponible "
            f"(n_fluid_ing={n_fluid_ing}, needs_fluid_out=True, "
            f"unlocked={sorted(state.unlocked_buildings)})"
        )
    if building is None and n_fluid_ing > 0:
        # Bootstrap (§2) : sans atelier capable de traiter des fluides, on
        # retire les fluides de la recette (produit craftable à la main).
        n_fluid_ing = 0
        n_item_ing = min(max_ingredients - 0, len(item_eligible))
        ingredients = _sample_items_weighed(rng, db, item_eligible, n_item_ing, state)
        rng.shuffle(ingredients)
        building = _pick_building(
            rng, db, state, n_item_ing, 0, False, product_name, exclude_buildings,
            building_whitelist, force_building=force_building,
        )

    recipe = _bake_recipe(rng, db, state, product_kind, product_name, ingredients, recipe_name,
                          x2_environmental=(building is None))
    if building is None:
        # Bootstrap à la main (dernier recours, cf. four de pierre vanilla) :
        # recette sans catégorie ni atelier, fabricable dans l'inventaire.
        return recipe
    recipe["category"] = _recipe_category(building, n_fluid_ing > 0, needs_fluid_out)
    recipe["crafted_in"] = building.name
    return recipe


def _ancestor_products(
    db: VanillaDB, state: ProgressionState, kind: str, name: str
) -> frozenset[tuple[str, str]]:
    """Ensemble des produits interdits comme ingredients de ``name`` pour
    garantir un graphe acyclique (anti-boucle transitive §10ter-redesign).

    Arête produit → ingrédient : « A dépend de B » si une recette produisant A
    consomme B. Ajouter une recette pour ``name`` avec l'ingrédient X referme un
    cycle si un chemin X →* ``name`` existe deja. On retourne donc tous les X
    dont la fermeture descendante atteint ``name`` : on remonte depuis ``name``
    les produits qui le consomment (puis recurse). Chaque nœud remonte est un
    ingrédient interdit — quel que soit le craft de ``name`` (primaire, relais,
    ease, balayage §9.6)."""
    node = (kind, name)
    consumers: dict[(str, str), set[(str, str)]] = {}
    for recipe in state.recipes:
        for res in recipe.get("results") or []:
            product = (res.get("type"), res["name"])
            for ing in recipe.get("ingredients") or []:
                consumers.setdefault((ing.get("type"), ing["name"]), set()).add(product)
    forbidden: set[(str, str)] = set()
    frontier = [node]
    visited = {node}
    while frontier:
        current = frontier.pop()
        for user in consumers.get(current, ()):
            if user in visited:
                continue
            visited.add(user)
            forbidden.add(user)
            frontier.append(user)
    return frozenset(forbidden)


def _bake_recipe(rng, db, state, product_kind, product_name, ingredients, recipe_name=None,
                 x2_environmental: bool = False, record: bool = True):
    """Assemble le dictionnaire de recette (nom, energy, ingrédients, résultats) ;
    le choix du bâtiment (`crafted_in`/`category`) est laissé à l'appelant.
    Sans atelier → aucune catégorie (« crafting » par défaut, inventaire).

    ``x2_environmental`` : les recettes de bootstrap (craftables à la main)
    doublent leurs ingrédients non infinis (wood/stone/raw-fish) — ressources
    rares du début de run (§9.1/§9.3) ; les ingrédients produits restent à
    quantité normale.
    ``record=False`` : remplacement de recette existante (§10ter), l'appelant
    ajuste le comptage production/consommation."""
    final_name = recipe_name if recipe_name is not None else _config.recipe_name(product_name)
    result_amount = _config.roll_result_amount(rng)
    if product_kind == SLOT_ITEM and not _item_is_stackable(db, product_name):
        # Item non-stackable (armure, arme, véhicule...) : au plus un exemplaire
        # par recette (erreur de chargement sinon).
        result_amount = 1
    recipe = {
        "name": final_name,
        "energy": _config.roll_energy(rng, len(ingredients)),
        "ingredients": [
            {"type": kind, "name": name, "amount": _bootstrap_amount(rng, db, name, x2_environmental)}
            for kind, name in ingredients
        ],
        "results": [
            {"type": product_kind, "name": product_name, "amount": result_amount}
        ],
    }
    # C2 : alimente le comptage production/consommation (quantités déjà
    # rollées). `record=False` = remplacement de recette (§10ter), l'appelant
    # ajuste le comptage lui-même.
    if record:
        state.record_recipe(recipe)
    return recipe


def _bootstrap_amount(rng, db, name: str, x2_environmental: bool) -> int:
    """Quantité d'un ingrédient de bootstrap : doublée pour les ressources non
    infinies (``is_environmental``) — rareté levée ensuite par le relais (§9.3)."""
    amount = _roll_amount(rng, db, name)
    if x2_environmental:
        item = db.items.get(name)
        if item is not None and item.is_environmental:
            amount *= 2
    return amount


def _has_production_item(db: VanillaDB, state: ProgressionState) -> bool:
    """Un item « de production » = hors environnement et hors kit de combat.
    Sans aucun, la partie est en cold start et les environnementaux
    (arbres/rochers/poissons) servent de matière première."""
    for name in state.obtained_items:
        item = db.items.get(name)
        if item is not None and item.is_environmental:
            continue
        if item is None:
            return True
        if item.subgroup != "combat":
            return True
    return False


def _sample_items_weighed(rng, db, eligible, n: int, state: ProgressionState):
    """Échantillonne ``n`` items sans remise, pondérés par leur statut
    environnemental : prioritaires en cold start, rares ensuite (petites
    quantités, surtout en début)."""
    if n <= 0 or not eligible:
        return []
    state.ensure_balance_target(rng)
    cold_start = not _has_production_item(db, state)
    pool = list(eligible)
    picked = []
    for _ in range(min(n, len(pool))):
        weights = [
            _environmental_weight(db, entry[1], cold_start) * state.balance_factor(entry[1])
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


def _environmental_weight(db: VanillaDB, name: str, cold_start: bool) -> float:
    """Poids d'un environnemental comme ingrédient : fort en cold start, faible
    ensuite. Décidé par tag ``is_environmental`` (item inconnu → 1.0)."""
    item = db.items.get(name)
    if item is None or not item.is_environmental:
        return 1.0
    if cold_start:
        return _config.environmental_weight_starved
    return _config.environmental_weight_rich


def _roll_amount(rng, db, name: str) -> int:
    """Quantité d'un ingrédient. Les environnementaux restent en petite quantité
    (même prioritaires) ; un item non-stackable ne peut être consommé qu'en 1
    exemplaire par recette (erreur de chargement sinon)."""
    if not _item_is_stackable(db, name):
        return 1
    item = db.items.get(name)
    if item is not None and item.is_environmental:
        return rng.randint(1, _config.environmental_amount_max)
    return _config.roll_ingredient_amount(rng)


def _item_is_stackable(db: VanillaDB, name: str) -> bool:
    """Item inconnu → supposé empilable (ne jamais bloquer une recette)."""
    item = db.items.get(name)
    return item is None or item.is_stackable


def _recipe_category(building, fluid_ing: bool, fluid_out: bool) -> str:
    """Catégorie de craft réelle supportée par le bâtiment : une valeur de
    ``crafting_categories`` présente dans data.raw["recipe-category"] et qui
    accepte les fluides (les tags ``is_crafter`` n'ont rien à voir)."""
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


def _is_fixed_recipe_transformer(b) -> bool:
    """Transformateur à RECETTE FIXE dont le générateur randomise la recette
    UNIQUE (sortie fluide boiler/heat-exchanger OU item d'un mod).

    @deprecated shim — délègue à ``is_fixed_crafter`` (tool.common.db),
    détecté par capacités au chargement du dump."""
    return is_fixed_crafter(b)


def _production_is_electric(db: VanillaDB, state: ProgressionState, item_name: str) -> bool:
    """L'item est-il produit par une recette en bâtiment ÉLECTRIQUE ? Sert à
    bannir les ingrédients du bootstrap du premier générateur (§10) : un tel
    ingrédient ne serait craftable qu'une fois le réseau en place, mais c'est
    ce générateur qui l'amorce (boucle)."""
    for r in state.recipes:
        res = r.get("results") or []
        if res and res[0].get("type") == SLOT_ITEM and res[0].get("name") == item_name:
            ci = r.get("crafted_in")
            if ci and ci in db.buildings and db.buildings[ci].energy_type == "electric":
                return True
            return False
    return False


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
    force_building=None,
):
    def fits(b) -> bool:
        # D4ter : jamais héberger une recette dans un bâtiment dont l'item EST
        # le produit (randputf-stone-furnace dans stone-furnace) : cercle
        # atelier=produit — la recette exige le bâtiment qu'elle fabrique.
        self_item = _item_for_building(db, b.name)
        if self_item is not None and self_item.name == product_name:
            return False
        # Un bâtiment à RECETTE CACHÉE (has_hidden_recipe : boiler/heat-
        # exchanger, nuclear-reactor, équivalents de mod) est exclu du pool
        # des ateliers : sa recette unique est randomisée par le générateur.
        # Bootstrap inline (§10ter) : en mode « early », aucun atelier
        # électrique — le réseau n'existe pas encore.
        return (
            not has_hidden_recipe(b)
            and (not state.early.active or b.energy_type != "electric")
            and _is_atelier(b)
            and b.item_input_slots >= n_item_ing
            and b.fluid_inputs >= n_fluid_ing
            and (not needs_fluid_out or b.fluid_outputs >= 1)
        )

    def blocked(b) -> bool:
        return _blocked_building(db, state, b.name)

    if force_building is not None:
        # Transformateur à recette fixe (§6/§10) : la recette reste hébergée
        # par CE bâtiment (déjà débloqué). Il convient si ses fluid boxes
        # acceptent entrée fluide et sortie ; en mode « early » un atelier
        # électrique est inacceptable. Jamais un atelier dont l'item EST le
        # produit (cercle atelier=produit).
        force_item = _item_for_building(db, force_building.name)
        if (
            force_item is None or force_item.name != product_name
        ) and force_building.name not in exclude_buildings and (
            not state.early.active or force_building.energy_type != "electric"
        ) and force_building.item_input_slots >= n_item_ing and (
            force_building.fluid_inputs >= n_fluid_ing
        ) and (not needs_fluid_out or force_building.fluid_outputs >= 1):
            return force_building
        return None

    if whitelist is not None:
        candidates = sorted(
            (
                b
                for b in db.buildings.values()
                if b.name in whitelist and b.name not in exclude_buildings and fits(b)
            ),
            key=lambda b: b.name,
        )
        return rng.choice(candidates) if candidates else None

    candidates = sorted(
        (
            b
            for b in db.buildings.values()
            if b.name in state.unlocked_buildings and b.name not in exclude_buildings and fits(b)
        ),
        key=lambda b: b.name,
    )
    if candidates:
        return rng.choice(candidates)

    candidates = sorted(
        (
            b
            for b in db.buildings.values()
            if b.name not in exclude_buildings and fits(b) and not blocked(b)
        ),
        key=lambda b: b.name,
    )
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
    """Garantit un combustible ITEM à tout bâtiment burner (four, foreuse
    thermique, chaudière, boiler) : on rend obtenable sur le tas (§9.3) un item
    combustible du pool (recette ``randputf-<fuel>`` si besoin) ; un fuel déjà
    obtenu est un no-op. Chaîne fusée (dont rocket-fuel) exclue (§14). Échec
    (pool vide / circularité) = bâtiment sans combustible, jamais de seed
    cassée."""
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
    """Vrai si le produit place une entité extractrice (perceuse, pumpjack,
    pompe offshore). De telles entités se fabriquent uniquement avec des items
    (jamais de fluide ingrédient, anti-cycle §8)."""
    if product_kind != SLOT_ITEM:
        return False
    item = db.items.get(product_name)
    if item is None or not item.place_result:
        return False
    building = db.buildings.get(item.place_result)
    return building is not None and building.is_extractor
