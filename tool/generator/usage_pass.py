"""D2 — garantie d'usage « dure » (bâtiment avant usage, niveau seed).

Passe post-récursion / avant relais (pipeline.generate_seed). Complète la
garantie de fabricabilité MONTANTE (C2, pilotée par la recette, `_pick_building`)
par une garantie DESCENDANTE, vérifiée sur le primaire déjà assemblé
(`state.recipes`), et CORRIGÉE par construction :

- **U1 — usage non-nul** : tout atelier débloqué (recette ``randputf-<b>``
  présente) qui n'est ni un bâtiment du kit de départ, ni un bâtiment terminal
  (lab, rocket-silo — usage = rôle moteur), héberge ≥ 1 recette de la seed
  (par ``crafted_in``). Un bâtiment mort = contenu débloqué, jamais utile.
- **U2 — ordre strict** : pour chaque recette R hébergée dans un bâtiment B
  (``crafted_in == B``), l'index de la tech qui débloque R est ≥ l'index de la
  tech qui débloque B (B est « la tech d'avant » à son premier usage).
  Exceptions : les bâtiments du **kit** (réputés débloqués en tech 0) et
  l'**auto-consommation** du bootstrap (recette ET bâtiment tous deux unlockés
  par les techs gratuites du starter — paradoxe œuf/poule déjà absorbé).

**Index de déblocage (proxy)** : la passe tourne AVANT le relais et avant
`build_linear_tech_tree` ; elle utilise l'ORDRE des macro-steps
(starter.tech_steps puis recursive puis endgame) comme proxy d'index tech.
Le groupement en techs (`build_linear_tech_tree`) ne fait que COMPRESSER des
steps consécutifs (monotone) : une correction validée au niveau step garantit
donc l'invariant au niveau tech final.

**Corrections** (déterministes, aucune RNG) :

- U1 : si un atelier unlocké est mort, on lui **rattache** une recette du pool
  (une recette hébergée ailleurs dont l'unlock est ≥ celui du bâtiment, source
  gardant ≥ 1 recette pour ne pas créer un nouveau mort). Repli : retirer le
  déblocage (jamais de contenu mort) quand l'item du bâtiment n'est consommé
  nulle part ; sinon warning (cas jamais observé sur 0-200).
- U2 : si R est posée dans B avec `unlock(R) < unlock(B)` (hors exemptions),
  on **bascule** R sur un atelier déjà disponible (index ≤ index de R,
  capacités compatibles) — toujours faisable sur 0-200 (`no_alt=0`). On ne
  touche JAMAIS aux bâtiments à recette cachée (`has_hidden_recipe`) ni aux
  recettes qu'ils hébergent (mécanique fixe du générateur).

``crafted_in``/``category`` des recettes sont les seuls champs mutés — le graphe
produit→ingrédient et les séquences d'unlock restent intacts (anti-cycle §8 et
« unlock unique » §13 préservés).
"""

from __future__ import annotations

import logging

from tool.common.db import SLOT_ITEM, SLOT_FLUID, VanillaDB, has_hidden_recipe
from tool.generator.recipes import (
    _auto_select_occupied_ingredients,
    _is_atelier,
    _item_for_building,
    _recipe_category,
)
from tool.prototypes.usage import UsageConfig

log = logging.getLogger(__name__)


def _hosted_map(state) -> dict[str, list[dict]]:
    """Recettes hébergées par bâtiment (``crafted_in`` non vide)."""
    hosted: dict[str, list[dict]] = {}
    for recipe in state.recipes:
        crafted_in = recipe.get("crafted_in")
        if crafted_in:
            hosted.setdefault(crafted_in, []).append(recipe)
    return hosted


def _recipe_needs_fluid(recipe: dict) -> tuple[bool, bool]:
    """(a un ingrédient fluide, a un résultat fluide)."""
    fluid_ing = any(
        ing.get("type") == SLOT_FLUID for ing in recipe.get("ingredients", [])
    )
    results = recipe.get("results") or []
    fluid_out = bool(results and results[0].get("type") == SLOT_FLUID)
    return fluid_ing, fluid_out


def _fits(building, recipe: dict) -> bool:
    """L'atelier peut-il héberger la recette (slots item/fluide) ? La catégorie
    est remappée à la volée via ``_recipe_category`` (déjà supportée par B)."""
    if has_hidden_recipe(building) or not _is_atelier(building):
        return False
    fluid_ing, fluid_out = _recipe_needs_fluid(recipe)
    n_item = sum(1 for ing in recipe.get("ingredients", []) if ing.get("type") != SLOT_FLUID)
    n_fluid = sum(1 for ing in recipe.get("ingredients", []) if ing.get("type") == SLOT_FLUID)
    if building.item_input_slots < n_item:
        return False
    if building.fluid_inputs < n_fluid:
        return False
    if fluid_out and building.fluid_outputs < 1:
        return False
    _recipe_category(building, fluid_ing, fluid_out)  # jamais None (sécurité)
    return True


def _rehome(recipe: dict, building) -> None:
    """Déplace une recette vers l'atelier ``building`` (crafted_in + category)."""
    fluid_ing, fluid_out = _recipe_needs_fluid(recipe)
    recipe["crafted_in"] = building.name
    recipe["category"] = _recipe_category(building, fluid_ing, fluid_out)


def _self_hosted(db: VanillaDB, building, recipe: dict) -> bool:
    """La recette serait hébergée dans un bâtiment dont l'item EST son produit
    (ex. randputf-stone-furnace dans stone-furnace) : cercle atelier=produit —
    la recette exige le bâtiment qu'elle fabrique, injouable sans kit."""
    item = _item_for_building(db, building.name)
    if item is None:
        return False
    res = (recipe.get("results") or [{}])[0]
    return res.get("type") == SLOT_ITEM and res.get("name") == item.name


def _auto_select_conflict(state, building, recipe: dict) -> bool:
    """Le bâtiment à auto-sélection (four) héberge déjà un ingrédient de
    ``recipe`` : l'y déplacer créerait une recette ambiguë au craft."""
    if not getattr(building, "auto_select", False):
        return False
    names = {ing.get("name") for ing in recipe.get("ingredients", [])}
    return bool(names & _auto_select_occupied_ingredients(state, building.name))


def _hosting_cycle(db: VanillaDB, state, building, recipe: dict) -> bool:
    """Déplacer ``recipe`` (produit P) vers l'atelier ``building`` (item B)
    formerait un CYCLE transitif d'hébergement si B dépend DÉJÀ de P.

    Graphe de dépendance dirigé, arête « A dépend de B » :
    - chaque ingrédient de la recette (produit A consomme l'ingrédient) ;
    - l'ATELIER qui héberge la recette (produit A exige l'item du bâtiment).
    Cycle mutuel exemple : randputf-assembling-machine-2 hébergé dans
    steel-furnace ET randputf-steel-furnace hébergé dans assembling-machine-2 —
    fabriquer A exige B, fabriquer B exige A. ``_self_hosted`` ne couvre que le
    cercle DIRECT (atelier=produit) ; ici on suit la fermeture transitive."""
    res = (recipe.get("results") or [{}])[0]
    product = (res.get("type"), res.get("name"))
    if product[0] != SLOT_ITEM:
        return False  # un procédé fluide n'exige pas d'item de bâtiment
    b_item = _item_for_building(db, building.name)
    if b_item is None:
        return False
    # Graphe de dépendance dirigé « X require Y » (Forward) : chaque recette
    # de produit ``p`` dépend de ses ingrédients ET de l'item de son atelier.
    # Cycle ssi B →* P : déplacer la recette du produit P dans l'atelier B
    # referme une boucle si l'atelier exige déjà (transitivement) ce produit —
    # ex. AM2 in AM3, AM3 in rocket-silo, rocket-silo in oil-refinery,
    # oil-refinery in AM2 (déplacer AM3 vers rocket-silo boucle).
    requires: dict[(str, str), set[(str, str)]] = {}
    for r in state.recipes:
        rres = r.get("results") or []
        if not rres:
            continue
        p = (rres[0].get("type"), rres[0]["name"])
        deps = requires.setdefault(p, set())
        for ing in r.get("ingredients") or []:
            deps.add((ing.get("type"), ing["name"]))
        ci = r.get("crafted_in")
        bi = _item_for_building(db, ci) if ci else None
        if bi is not None:
            deps.add((SLOT_ITEM, bi.name))
    # On marche depuis l'item de l'atelier cible vers P : « pour fabriquer B
    # il faudrait déjà le produit P ».
    frontier = [(SLOT_ITEM, b_item.name)]
    visited = {frontier[0]}
    while frontier:
        current = frontier.pop()
        for dep in requires.get(current, ()):
            if dep == product:
                return True
            if dep in visited:
                continue
            visited.add(dep)
            frontier.append(dep)
    return False


def _prepower_ok(building, recipe: dict, free: set[str]) -> bool:
    """Une recette unlockée par une tech gratuite du starter garde un atelier
    NON-électrique (promesse §10ter / bootstrap inline) : la re-héberger dans
    un bâtiment électrique la rendrait injouable avant l'électricité."""
    if recipe["name"] not in free:
        return True
    return getattr(building, "energy_type", "") != "electric"


def _unlock_proxy(ordered_steps, *, starter_steps: int) -> tuple[dict[str, int], set[str]]:
    """Proxy d'index de déblocage (ordre des macro-steps) + recettes des techs
    gratuites du starter (double-free bootstrap).

    ``unlock[name]`` = index du PREMIER step qui réclame le nom (recette
    `randputf-<x>` directe ou `unlocks_buildings` transformé en `randputf-<b>`),
    miroir du « unlock unique » de `build_linear_tech_tree`.
    """
    unlock: dict[str, int] = {}
    for index, step in enumerate(ordered_steps):
        for recipe in step.get("unlocks_recipes", []):
            unlock.setdefault(recipe, index)
        for building in step.get("unlocks_buildings", []):
            unlock.setdefault(f"randputf-{building}", index)
    free = {
        recipe
        for step in ordered_steps[:starter_steps]
        for recipe in step.get("unlocks_recipes", [])
    }
    free |= {
        f"randputf-{building}"
        for step in ordered_steps[:starter_steps]
        for building in step.get("unlocks_buildings", [])
    }
    return unlock, free


def _kit_buildings(starter, db: VanillaDB, cfg: UsageConfig) -> set[str]:
    """Bâtiments livrés par le kit de départ : items du kit dont le
    ``place_result`` est un bâtiment connu (fabricateur, extracteurs), plus les
    exemptions explicites de la config."""
    kit = set(cfg.kit_exempt)
    for entry in starter.kit:
        if entry.get("type") != "item":
            continue
        item = db.items.get(entry["name"])
        if item is not None and item.place_result in db.buildings:
            kit.add(item.place_result)
    return kit


def _claim_index(steps: list[dict], name: str) -> int | None:
    """Index du PREMIER step qui réclame ``name`` (unlocks_recipes ou
    unlocks_buildings transformé) — miroir de `_unlock_proxy`."""
    for index, step in enumerate(steps):
        if name in step.get("unlocks_recipes", []):
            return index
        if name.startswith("randputf-") and name[len("randputf-"):] in step.get(
            "unlocks_buildings", []
        ):
            return index
    return None


def _reorder_claim(
    state, steps: list[dict], recipe_name: str, building_name: str, *, force: bool = False
) -> str:
    """Repli U2 — « précéder B » : décale le claim d'unlock de ``recipe_name``
    sur le step qui débloque ``building_name`` (unlock ≈ égalités, l'invariant
    U2 devient une égalité). Ne touche pas au graphe de fabrication.

    ``force=True`` court-circuite le garde-fou « item consommé avant le
    bâtiment » : réservé au cas où l'item de R reste fabricable tôt par une
    AUTRE recette (recette jumelle — original environnemental d'un relais), donc
    repousser le claim de R ne rend aucune recette injouable.

    Retourne ``"done"`` si le reorder a eu lieu, sinon un motif d'échec :
    - ``"none"`` : pas de claim déplaçable (cas dégénéré) ;
    - ``"consumed:<recette>"`` : l'item de R est consommé par une recette
      débloquée AVANT le bâtiment — repousser son unlock créerait une recette
      injouable ; c'est précisément une *auto-consommation du bootstrap* (§7),
      à exempter par l'appelant.
    """
    item = recipe_name[len("randputf-"):] if recipe_name.startswith("randputf-") else recipe_name
    s_recipe = _claim_index(steps, recipe_name)
    s_building = _claim_index(steps, f"randputf-{building_name}")
    if s_recipe is None or s_building is None or s_recipe >= s_building:
        return "none"
    # Consommateurs débloqués avant le bâtiment : repousser R les bloquerait.
    unlock_before = set()
    for step in steps[:s_building]:
        for r in step.get("unlocks_recipes", []):
            unlock_before.add(r)
        for b in step.get("unlocks_buildings", []):
            unlock_before.add(f"randputf-{b}")
    for other in state.recipes:
        if other["name"] not in unlock_before:
            continue
        if any(
            ing.get("type") != SLOT_FLUID and ing.get("name") == item
            for ing in other.get("ingredients", [])
        ):
            if force:
                break  # recette jumelle : l'item reste fabricable tôt
            return f"consumed:{other['name']}"
    # Déplace le claim : retire de l'étape d'origine, pose sur celle de B.
    s_recipe_step = steps[s_recipe]
    if recipe_name in s_recipe_step.get("unlocks_recipes", []):
        s_recipe_step["unlocks_recipes"] = [
            r for r in s_recipe_step["unlocks_recipes"] if r != recipe_name
        ]
    elif recipe_name[len("randputf-"):] in s_recipe_step.get("unlocks_buildings", []):
        s_recipe_step["unlocks_buildings"] = [
            b for b in s_recipe_step["unlocks_buildings"]
            if b != recipe_name[len("randputf-"):]
        ]
    target = steps[s_building]
    target.setdefault("unlocks_recipes", []).append(recipe_name)
    return "done"


def _product_of(recipe: dict) -> tuple:
    """(type, nom) du premier résultat d'une recette (clé produit)."""
    res = recipe.get("results") or [{}]
    return (res[0].get("type"), res[0].get("name"))


def _has_twin(state, recipe: dict) -> bool:
    """Vrai si une AUTRE recette produit le même item/fluide (recette jumelle —
    ex. l'original environnemental d'un relais). Garantit que différer
    l'unlock de ``recipe`` ne rend pas son produit introuvable tôt."""
    prod = _product_of(recipe)
    return any(r is not recipe and _product_of(r) == prod for r in state.recipes)


def _auto_select_conflicts(db: VanillaDB, state) -> list[tuple[str, str, list[dict]]]:
    """Conflits d'auto-sélection : ``(bâtiment, ingrédient, [recettes])`` pour
    chaque atelier à auto-sélection hébergeant ≥ 2 recettes de seed partageant
    un ingrédient (la première recette du prototype l'emporterait, la seconde
    serait inatteignable)."""
    out: list[tuple[str, str, list[dict]]] = []
    for bname, recipes in _hosted_map(state).items():
        building = db.buildings.get(bname)
        if building is None or not getattr(building, "auto_select", False):
            continue
        by_ing: dict[str, list[dict]] = {}
        for recipe in recipes:
            for ing in recipe.get("ingredients", []):
                by_ing.setdefault(ing.get("name"), []).append(recipe)
        for ing, rs in by_ing.items():
            if ing is not None and len(rs) >= 2:
                out.append((bname, ing, rs))
    return out


def _auto_select_target(
    db: VanillaDB,
    state,
    recipe: dict,
    source_name: str,
    unlock: dict[str, int],
    free: set[str],
    kit: set[str],
):
    """Meilleur atelier alternatif (hors ``source_name``) pour ``recipe`` sans
    conflit d'auto-sélection. Préférence : non-auto-sélection, puis unlock le
    plus tôt, puis nom (déterminisme). ``None`` si aucun atelier valable.

    ``_hosting_cycle`` est ignoré pour une recette à recette jumelle : le
    produit reste fabricable par sa jumelle (original environnemental), donc
    l'héberger dans un bâtiment qui le consomme ne referme pas de vraie
    boucle."""
    twin = _has_twin(state, recipe)
    best = None
    for name, other in sorted(db.buildings.items()):
        if name == source_name:
            continue
        if has_hidden_recipe(other) or not _is_atelier(other):
            continue
        _r_self = _self_hosted(db, other, recipe)
        _r_pre = not _prepower_ok(other, recipe, free)
        _r_cyc = (not twin) and _hosting_cycle(db, state, other, recipe)
        _r_as = _auto_select_conflict(state, other, recipe)
        _r_fit = not _fits(other, recipe)
        if _r_self or _r_pre or _r_cyc or _r_as or _r_fit:
            continue
        i_other = 0 if name in kit else unlock.get(f"randputf-{name}")
        if i_other is None and name not in state.unlocked_buildings:
            continue
        score = (
            bool(getattr(other, "auto_select", False)),
            i_other if i_other is not None else 10**9,
            name,
        )
        if best is None or score < best[0]:
            best = (score, other)
    return best[1] if best else None


def _correct_auto_select(
    db: VanillaDB,
    state,
    unlock: dict[str, int],
    free: set[str],
    kit: set[str],
    steps: list[dict],
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Auto-sélection (four) : un atelier à auto-sélection ne peut héberger deux
    recettes partageant un ingrédient. Déplace une des recettes en conflit vers
    un atelier alternatif sans conflit (jamais de recette perdue), puis recale
    son claim d'unlock sur celui de son nouveau bâtiment (le produit reste
    fabricable avant par sa recette jumelle). Déterministe, borné — chaque
    déplacement supprime ≥ 1 conflit (cible vérifiée sans conflit).

    Replis quand aucun atelier alternatif sans conflit n'existe :
    - retirer l'ingrédient en conflit (recette multi-ingrédients) ;
    - renvoyer une recette starter gratuite au craft manuel (retrait d'hôte).

    Retourne (déplacées, claims réordonnés, ingrédients retirés,
    recettes renvoyées au craft manuel)."""
    moved: list[str] = []
    reordered: list[str] = []
    trimmed: list[str] = []
    handcrafted: list[str] = []
    for _ in range(256):
        conflicts = _auto_select_conflicts(db, state)
        if not conflicts:
            break
        _bname, _ing, recipes = min(conflicts, key=lambda c: (c[0], c[1]))
        # Préfère déplacer une recette JUMELLE (produit fourni par une autre
        # recette) : différer son unlock reste sûr. Sinon par nom (stabilité).
        recipes = sorted(recipes, key=lambda r: (not _has_twin(state, r), r["name"]))
        progressed = False
        for recipe in recipes:
            target = _auto_select_target(
                db, state, recipe, recipe.get("crafted_in"), unlock, free, kit
            )
            if target is None:
                continue
            i_target = 0 if target.name in kit else unlock.get(f"randputf-{target.name}")
            i_recipe = unlock.get(recipe["name"])
            # Une recette SANS jumelle ne peut être différée que si sa cible
            # n'arrive pas après elle (sinon son produit serait introuvable tôt).
            if (
                not _has_twin(state, recipe)
                and i_target is not None
                and i_recipe is not None
                and i_target > i_recipe
            ):
                continue
            _rehome(recipe, target)
            moved.append(recipe["name"])
            reason = _reorder_claim(
                state, steps, recipe["name"], target.name, force=_has_twin(state, recipe)
            )
            if reason == "done":
                reordered.append(recipe["name"])
            progressed = True
            break
        if not progressed:
            # Repli 1 : aucun atelier alternatif sans conflit (bâtiment saturé,
            # seule option déverrouillée tôt). On retire l'ingrédient en conflit
            # d'une des recettes — même esprit que le repli « suppression des
            # fluides » de `_make_recipe` : la recette reste fabricable (plus
            # simple), on ne perd jamais de produit, et l'ordre/claims ne
            # bougent pas. On garde ≥ 1 ingrédient par recette.
            victim = _trim_conflict_ingredient(recipes, _ing)
            if victim is not None:
                trimmed.append(victim["name"])
                progressed = True
            else:
                # Repli 2 : recette mono-ingrédient (four 1-slot). Si elle fait
                # partie des recettes STARTER gratuites (fabriquées à la main),
                # on lui retire son hôte : elle redevient une recette de craft
                # manuel, donc plus aucun conflit d'auto-sélection. La recette
                # reste fabricable (le craft à la main est une voie valide).
                manual = _handcraft_starter_recipe(recipes, free)
                if manual is None:
                    break
                handcrafted.append(manual["name"])
                progressed = True
    return moved, reordered, trimmed, handcrafted


def _handcraft_starter_recipe(recipes, free):
    """Passe une recette starter gratuite en craft manuel (retire ``crafted_in``
    et ``category``). Déterministe (nom). Retourne la recette modifiée ou
    ``None`` si aucune des recettes en conflit n'est starter-gratuite."""
    candidates = sorted(
        (r for r in recipes if r["name"] in free), key=lambda r: r["name"]
    )
    if not candidates:
        return None
    recipe = candidates[0]
    recipe.pop("crafted_in", None)
    recipe.pop("category", None)
    return recipe


def _trim_conflict_ingredient(recipes, ingredient):
    """Retire ``ingredient`` de la recette la plus fournie qui en garde ≥ 1
    autre. Déterministe (nombre d'ingrédients décroissant, puis nom). Retourne
    la recette modifiée ou ``None`` si aucune ne peut être allégée."""
    candidates = sorted(
        (
            r
            for r in recipes
            if any(i["name"] == ingredient for i in r["ingredients"])
            and len(r["ingredients"]) > 1
        ),
        key=lambda r: (-len(r["ingredients"]), r["name"]),
    )
    if not candidates:
        return None
    victim = candidates[0]
    victim["ingredients"] = [
        i for i in victim["ingredients"] if i["name"] != ingredient
    ]
    return victim


def _correct_u2(
    db: VanillaDB,
    state,
    unlock: dict[str, int],
    free: set[str],
    kit: set[str],
    steps: list[dict],
) -> tuple[int, list[str]]:
    """U2 — ordre strict : bascule les recettes posées avant leur bâtiment sur
    un atelier déjà disponible ; repli : précéder B (décaler le claim d'unlock
    de R après celui de B). Retourne (nombre de bascules, reorders effectués)."""
    shipped = 0
    reordered: list[str] = []
    hosted = _hosted_map(state)
    locked = set(state.unlocked_buildings)

    for recipe in state.recipes:
        crafted_in = recipe.get("crafted_in")
        if not crafted_in:
            continue
        building = db.buildings.get(crafted_in)
        if building is None or has_hidden_recipe(building) or not _is_atelier(building):
            continue
        i_recipe = unlock.get(recipe["name"])
        if i_recipe is None:
            continue
        i_building = 0 if crafted_in in kit else unlock.get(f"randputf-{crafted_in}")
        if i_building is None:
            continue
        if i_recipe >= i_building:
            continue
        # Exception double-free : recette ET bâtiment unlockés par les techs
        # gratuites du starter (auto-consommation du bootstrap §7).
        if recipe["name"] in free and f"randputf-{crafted_in}" in free:
            continue

        fluid_ing, fluid_out = _recipe_needs_fluid(recipe)
        n_item = sum(1 for ing in recipe["ingredients"] if ing.get("type") != SLOT_FLUID)
        n_fluid = sum(1 for ing in recipe["ingredients"] if ing.get("type") == SLOT_FLUID)
        candidates = []
        for other_name, other in db.buildings.items():
            if other_name == crafted_in or other_name not in locked:
                continue
            if _self_hosted(db, other, recipe) or not _prepower_ok(other, recipe, free):
                continue
            if _hosting_cycle(db, state, other, recipe):
                continue
            if _auto_select_conflict(state, other, recipe):
                continue
            if has_hidden_recipe(other) or not _is_atelier(other):
                continue
            if other.item_input_slots < n_item:
                continue
            if other.fluid_inputs < n_fluid:
                continue
            if fluid_out and other.fluid_outputs < 1:
                continue
            if fluid_ing and fluid_out and not (other.fluid_inputs and other.fluid_outputs):
                continue
            i_other = 0 if other_name in kit else unlock.get(f"randputf-{other_name}")
            if i_other is None or i_other > i_recipe:
                continue
            candidates.append((i_other, other_name))

        host_list = hosted.get(crafted_in, [])
        if candidates and len(host_list) > 1:
            candidates.sort()
            target = db.buildings[candidates[0][1]]
            _rehome(recipe, target)
            shipped += 1
            # Maintient la carte hébergée à jour en local.
            host_list.remove(recipe)
            hosted.setdefault(target.name, []).append(recipe)
            continue
        # Repli « précéder B » : la bascule est impossible (aucun atelier assez
        # tôt, ou la source perdrait toute recette). On décale alors le claim
        # d'unlock de R sur le step qui débloque B — l'invariant devient une
        # égalité. Si l'item de R est consommé par une recette débloquée AVANT le
        # bâtiment, décaler l'unlock casserait cette recette : c'est une
        # auto-consommation du bootstrap (§7) et on l'exempte par principe
        # (l'item doit rester fabriquable tôt via sa recette relais/ease).
        reason = _reorder_claim(state, steps, recipe["name"], crafted_in)
        if reason == "done":
            reordered.append(recipe["name"])
        elif reason.startswith("consumed:"):
            continue
        elif reason is not None:
            log.warning(
                "[randputF] usage_pass U2 ni basculable ni recevable (%s), "
                "exempt bootstrap auto-consommation (host=%s)",
                reason,
                crafted_in,
            )

    return shipped, reordered


def _correct_u1(
    db: VanillaDB,
    state,
    unlock: dict[str, int],
    free: set[str],
    kit: set[str],
    terminals: frozenset[str],
    ordered_steps: list[dict],
) -> tuple[list[str], list[str], list[str]]:
    """U1 — usage non-nul : rattache une recette à tout atelier unlocké mort ;
    repli : retirer le déblocage (jamais observé). Retourne (rattachés,
    retirés, warnings)."""
    attached: list[str] = []
    removed: list[str] = []
    warnings: list[str] = []
    hosted = _hosted_map(state)
    locked = set(state.unlocked_buildings)
    steps: list[dict] = ordered_steps

    for building_name in locked:
        if building_name in kit or building_name in terminals:
            continue
        recipe_name = f"randputf-{building_name}"
        if recipe_name not in unlock:
            continue
        building = db.buildings.get(building_name)
        if building is None or not _is_atelier(building):
            continue
        if hosted.get(building_name):
            continue  # usage non-nul déjà

        i_building = 0 if building_name in kit else unlock[recipe_name]
        candidates = []
        for recipe in state.recipes:
            source = recipe.get("crafted_in")
            if not source or source == building_name:
                continue
            i_recipe = unlock.get(recipe["name"])
            if i_recipe is None or i_recipe < i_building:
                continue  # U2 : ne pas poser une recette AVANT le bâtiment
            if _self_hosted(db, building, recipe) or not _prepower_ok(building, recipe, free):
                continue
            if _hosting_cycle(db, state, building, recipe):
                continue
            if _auto_select_conflict(state, building, recipe):
                continue
            if len(hosted.get(source, [])) <= 1:
                continue  # la source garde ≥ 1 recette
            if not _fits(building, recipe):
                continue
            candidates.append((i_recipe, recipe["name"], source))

        candidates.sort()
        if not candidates:
            # Repli : retirer le déblocage si l'item n'est consommé nulle part
            # (pas de contenu mort). Jamais observé sur 0-200.
            consumed = any(
                ing.get("type") == "item" and ing.get("name") == building_name
                for recipe in state.recipes
                for ing in recipe.get("ingredients", [])
            )
            if not consumed:
                removed.append(building_name)
                _remove_building_unlock(state, steps, building_name, recipe_name)
            else:
                warnings.append(
                    f"{building_name}: consommé mais aucun candidat à rattacher"
                )
            continue

        _, recipe_name, _source = candidates[0]
        recipe = next(r for r in state.recipes if r["name"] == recipe_name)
        _rehome(recipe, building)
        attached.append(building_name)
        hosted = _hosted_map(state)

    return attached, removed, warnings


def _remove_building_unlock(
    state, steps: list[dict], building_name: str, recipe_name: str
) -> None:
    """Retire le déblocage : la recette est retirée des recettes, le bâtiment
    désinscrit et le claim est effacé des macro-steps (le tree builder ne doit
    pas réclamer ``randputf-<b>`` disparu). Repli jamais utilisé sur 0-200."""
    state.recipes[:] = [r for r in state.recipes if r.get("name") != recipe_name]
    state.unlocked_buildings.discard(building_name)
    if steps:
        for step in steps:
            step.get("unlocks_buildings", [])[:] = [
                b for b in step["unlocks_buildings"] if b != building_name
            ]
            step.get("unlocks_recipes", [])[:] = [
                r for r in step["unlocks_recipes"] if r != recipe_name
            ]


def enforce_usage(
    db: VanillaDB,
    state,
    starter,
    ordered_steps: list[dict],
    config: dict,
) -> dict:
    """Applique la garantie d'usage dure (D2) sur le primaire assemblé.

    ``state`` = ``starter.state`` après `expand_recursive` + `ensure_rocket_chain`
    (toutes les recettes primaires présentes). ``ordered_steps`` = ordre des
    macro-steps retenu par le tree builder (starter puis récursif puis endgame).
    Retourne un rapport de correction (u2_basculees, u1_rattachees, removed,
    warnings) pour les logs.
    """
    cfg = UsageConfig.from_config(config)
    if not cfg.enabled:
        return {"u2_basculees": 0, "u2_reordonees": [], "u1_rattachees": [],
                "removed": [], "warnings": [], "auto_select_deplacees": [],
                "auto_select_ingredients_retires": [],
                "auto_select_craft_manuel": []}

    kit = _kit_buildings(starter, db, cfg)
    unlock, free = _unlock_proxy(
        ordered_steps, starter_steps=len(starter.tech_steps)
    )

    # Auto-sélection d'abord : résout les conflits four (deux recettes à
    # ingrédient commun sur un même bâtiment) en déplaçant une recette vers un
    # atelier alternatif ; U2/U1 voient ensuite l'hébergement corrigé.
    moved, as_reordered, as_trimmed, as_handcrafted = _correct_auto_select(
        db, state, unlock, free, kit, ordered_steps
    )

    # U2 — ordre strict bâtiment/usage ; U1 — usage non-nul.
    shipped, reordered = _correct_u2(db, state, unlock, free, kit, ordered_steps)
    attached, removed, warnings = _correct_u1(
        db, state, unlock, free, kit, cfg.terminal_buildings, ordered_steps
    )
    reordered = as_reordered + reordered

    report = {
        "u2_basculees": shipped,
        "u2_reordonees": reordered,
        "u1_rattachees": attached,
        "removed": removed,
        "warnings": warnings,
        "auto_select_deplacees": moved,
        "auto_select_ingredients_retires": as_trimmed,
        "auto_select_craft_manuel": as_handcrafted,
    }
    if (
        shipped or reordered or attached or removed or moved or as_trimmed
        or as_handcrafted
    ):
        log.info(
            "[randputF] usage_pass: %d auto-sélection déplacées, %d ingrédients "
            "retirés, %d craft manuel (auto-sélection), %d U2 basculées, "
            "%d U2 réordonnées, %d U1 rattachées, %d retirées",
            len(moved), len(as_trimmed), len(as_handcrafted), shipped,
            len(reordered), len(attached), len(removed),
        )
    for warning in warnings:
        log.warning("[randputF] usage_pass warning: %s", warning)
    return report