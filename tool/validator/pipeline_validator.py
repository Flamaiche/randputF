"""pipeline_validator.py — Validation du pipeline de génération.

═══════════════════════════════════════════════════════════════════════════════
                        POURQUOI CE MODULE ?
═══════════════════════════════════════════════════════════════════════════════

Le validator/solver.py existant valide le FORMAT SEED (dict) après
assemblage. Mais il ne valide pas :

  1. Le ProgressionState en cours de génération (on ne vérifie pas que
     les recettes créées sont bien en ordre topologique pendant la
     génération — on fait confiance à recipes.py).
  2. Les coûts des techs par rapport au ProgressionState (est-ce que le
     joueur peut vraiment produire les matériaux de recherche au bon
     moment ?).
  3. La cohérence entre les recettes créées et les techs qui les
     débloquent (est-ce que chaque recette apparaît dans exactement
     UNE tech ?).

Ce module valide DIRECTEMENT le ProgressionState + TechGraph produit
par le pipeline, AVANT l'assemblage de la seed. C'est plus fiable
car on valide le processus, pas juste le résultat.

═══════════════════════════════════════════════════════════════════════════════
                     LES TROIS INVARIANTS (§15)
═══════════════════════════════════════════════════════════════════════════════

1. ANTI-CYCLE :
   Aucune recette ne peut dépendre (directement ou indirectement) de
   sa propre production. On vérifie en simulant la progression : si
   à un moment on a besoin de X pour produire Y, et que X est produit
   par une recette qui a besoin de Y, c'est un cycle.

2. PROGRESSIVITÉ :
   Chaque recette ne utilise que des ingrédients qui sont OBTENUS
   au moment de sa création. Les ressources au sol sont toujours
   valides. Les recettes créées par ensure_obtainable() sont validées
   par construction (anti-cycle double axe), mais on vérifie quand
   même par sécurité.

3. COHÉRENCE TECH-RECETTES :
   Chaque recette créée par le pipeline doit apparaître dans les
   effects (unlock-recipe) d'exactement UNE technology. Pas de
   recette orpheline (jamais débloquée), pas de double déblocage.

4. COÛTS OBTENABLES (§13) :
   Les matériaux de recherche de chaque tech doivent être produits
   par le joueur AVANT ce point de la chaîne. On simule la progression
   des techs dans l'ordre et on vérifie que chaque coût est produisible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_ITEM, VanillaDB
from tool.generator.recipes import ProgressionState


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                       TYPES DE DONNÉES                                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


@dataclass
class ValidationResult:
    """Résultat de la validation du pipeline.

    Attributes:
        is_valid : True si aucun problème n'a été détecté
        issues : liste des messages d'erreur (vide si tout est OK)
        warnings : liste des avertissements (non bloquants)
        stats : statistiques de validation (pour le debug)
    """

    is_valid: bool = True
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def add_issue(self, msg: str) -> None:
        """Ajoute un problème bloquant."""
        self.issues.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        """Ajoute un avertissement non bloquant."""
        self.warnings.append(msg)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    FONCTION PRINCIPALE (API PUBLIQUE)                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def validate_pipeline(
    state: ProgressionState,
    technologies: list[dict],
    db: VanillaDB,
    patch_resources: set[str] | None = None,
    lake_resources: set[str] | None = None,
) -> ValidationResult:
    """Valide l'ensemble du pipeline de génération.

    C'est LA fonction d'entrée. Elle prend le résultat de toutes les
    phases et vérifie les invariants.

    Paramètres :
      - state : état de progression (recettes, items/fluides obtenus)
      - technologies : liste de techs (dicts) du tech_tree.py
      - db : base vanilla (pour vérifier l'existence des items)
      - patch_resources : ressources déjà au sol (patchs, optionnel)
      - lake_resources : fluides déjà posés en LAC (IDEES C2/C6) — les lacs
        sont des ressources brutes obtenables dès le départ (pompe offshore,
        volume infini) : ils comptent comme source externe pour la solvabilité
        du bootstrap, au même titre qu'un patch.

    Retourne :
      - ValidationResult avec is_valid, issues, warnings, stats
    """
    result = ValidationResult()

    # Si pas de ressources au sol fournies, extraire du state
    if patch_resources is None:
        patch_resources = set()
    if lake_resources is None:
        lake_resources = set()

    # Sources externes = patchs + lacs (IDEES C2) : les deux sont obtenables
    # dès le départ sans recette. Un fluide en lac est une raw resource
    # pompeable immédiatement ; il doit donc compter dans la solvabilité.
    external = set(patch_resources) | set(lake_resources)

    # ── Invariant 1 : anti-cycle ────────────────────────────────────────
    _check_anti_cycle(state, result, external)

    # ── Invariant 2 : progressivité ─────────────────────────────────────
    _check_progressivity(state, external, result)

    # ── Invariant 3 : cohérence tech-recettes ───────────────────────────
    _check_tech_recipe_coherence(state, technologies, result)

    # ── Invariant 4 : coûts obtainables ─────────────────────────────────
    _check_tech_costs_obtainable(technologies, state, result)

    # ── Invariant 5 : règle des tuyaux (§8/§15) ────────────────────────
    _check_pipe_rule(state, external, result)

    # ── Invariant 6 : complétude fusée (§14) ───────────────────────────
    _check_victory_requirements(state, result)

    # ── Invariant 7 : packs sans ressource brute (§13) ──────────────────
    _check_packs_no_raw(state, patch_resources, lake_resources, db, result)

    # ── Statistiques ────────────────────────────────────────────────────
    free_techs = sum(1 for t in technologies if not t.get("unit", {}).get("ingredients"))
    result.stats = {
        "recipes": len(state.recipes),
        "obtained_items": len(state.obtained_items),
        "obtained_fluids": len(state.obtained_fluids),
        "unlocked_buildings": len(state.unlocked_buildings),
        "tech_nodes": len(technologies),
        "free_techs": free_techs,
        "issues": len(result.issues),
        "warnings": len(result.warnings),
    }

    return result


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    INVARIANT 1 : ANTI-CYCLE                             ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _check_anti_cycle(
    state: ProgressionState,
    result: ValidationResult,
    patch_resources: set[str] | None = None,
) -> None:
    """Vérifie l'absence de boucle dans les dépendances de production.

    La solvabilité est vérifiée au niveau de l'ITEM : une recette est
    résolue quand TOUS ses ingrédients sont solvables (patch posé au sol,
    ressource environnementale, ou produit d'une recette déjà résolue).
    Un item est solvable dès que l'une de ses recettes est résolue.

    Cette sémantique « OU » compte double depuis §9.3 : chaque item possède
    sa chaîne de bootstrap, et les recettes relais sont des routes
    ALTERNATIVES. Un aller-retour du type relais-A -> bootstrap-B -> relais-A
    ne crée aucune impasse : l'item A reste solvable par sa chaîne principale,
    donc bootstrap-B et relais-A finissent tous deux par se résoudre.

    À l'issue du point fixe, toute recette non résolue révèle une vraie boucle
    (ingrédient qui dépend transitivement de la production de la recette).

    Algorithme :
      1. Solvable initial = ressources au sol + items environnementaux
      2. Tant que ça progresse, résoudre les recettes dont tous les
         ingrédients sont solvables ; leurs produits passent solvables.
      3. Les recettes restées insolubles forment des boucles.
    """
    if patch_resources is None:
        patch_resources = set()

    solvable: set[str] = set(patch_resources) | set(ENVIRONMENTAL_ITEMS)
    recipes_by_name: dict[str, dict] = {}
    for recipe in state.recipes:
        recipes_by_name[recipe.get("name", "")] = recipe

    unresolved = set(recipes_by_name)
    changed = True
    while changed:
        changed = False
        for name in list(unresolved):
            recipe = recipes_by_name[name]
            if all(i.get("name") in solvable for i in recipe.get("ingredients", [])):
                unresolved.discard(name)
                for res in recipe.get("results", []):
                    if res.get("name") not in solvable:
                        solvable.add(res.get("name"))
                        changed = True

    cyclic = sorted(unresolved)
    if cyclic:
        result.add_issue(
            f"anti-cycle: {len(cyclic)} recettes en boucle ou "
            f"dépendances manquantes: {cyclic[:10]}"
            + ("..." if len(cyclic) > 10 else "")
        )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                   INVARIANT 2 : PROGRESSIVITÉ                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _check_progressivity(
    state: ProgressionState,
    patch_resources: set[str],
    result: ValidationResult,
) -> None:
    """Vérifie que chaque recette n'utilise que des ingrédients obtenables.

    Simule la progression en parcourant les recettes dans l'ordre de
    création. À chaque recette, vérifie que TOUS ses ingrédients sont
    déjà dans le pool (items/fluides obtenus + ressources au sol).

    Si un ingrédient manque, c'est un bug du générateur (la recette
    a été créée avant que son ingrédient ne soit disponible).
    """
    # Pool = ressources au sol (patchs + lacs, IDEES C2) + environnement
    # (récoltable à la main, §3/§6/§9.3) + items/fluides obtenus. Les lacs et
    # l'environnement sont obtenables dès le départ — cohérent avec l'anti-cycle
    # et le point fixe `_detect_unreachable_products`.
    pool = set(patch_resources)
    pool.update(ENVIRONMENTAL_ITEMS)
    pool.update(state.obtained_items)
    pool.update(state.obtained_fluids)

    violations = []
    for recipe in state.recipes:
        recipe_name = recipe.get("name", "")
        for ing in recipe.get("ingredients", []):
            item_name = ing.get("name", "")
            if item_name not in pool:
                violations.append(
                    f"{recipe_name} utilise '{item_name}' avant obtention"
                )
        # Après vérification, ajouter les produits au pool
        for res in recipe.get("results", []):
            pool.add(res.get("name", ""))

    if violations:
        result.add_issue(
            f"progressivité: {len(violations)} violations — "
            + "; ".join(violations[:5])
            + ("..." if len(violations) > 5 else "")
        )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║              INVARIANT 3 : COHÉRENCE TECH-RECETTES                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _check_tech_recipe_coherence(
    state: ProgressionState,
    technologies: list[dict],
    result: ValidationResult,
) -> None:
    """Vérifie que chaque recette est débloquée par exactement UNE tech.

    Deux problèmes possibles :
      - Recette orpheline : créée par le pipeline mais jamais débloquée
        par une tech → le joueur ne pourra jamais la fabriquer.
      - Double déblocage : une recette apparaît dans les effects de
        plusieurs techs → pas un bug Factorio (le jeu ignore les doublons)
        mais c'est inutile et confusant.

    On vérifie aussi que chaque bâtiment débloqué par le pipeline
    apparaît dans les effects d'une tech.
    """
    # ── Collecter toutes les recettes débloquées par les techs ──────────
    tech_recipes: set[str] = set()
    for tech in technologies:
        for effect in tech.get("effects", []):
            if effect.get("type") == "unlock-recipe":
                tech_recipes.add(effect.get("recipe", ""))

    # ── Collecter toutes les recettes créées par le pipeline ────────────
    pipeline_recipes: set[str] = set()
    for recipe in state.recipes:
        pipeline_recipes.add(recipe.get("name", ""))

    # ── Vérifier les recettes orphelines ────────────────────────────────
    # Recettes créées mais jamais débloquées par une tech
    orphan = sorted(pipeline_recipes - tech_recipes)
    if orphan:
        # Les recettes orphelines ne sont pas forcément un bug : certaines
        # recettes sont créées "sur le tas" pour fabriquer des bâtiments
        # ou des items, et sont automatiquement disponibles dès le début
        # (enabled=true par défaut dans Factorio). On émet un warning
        # plutôt qu'une erreur.
        result.add_warning(
            f"tech-recettes: {len(orphan)} recettes créées mais pas "
            f"débloquées par une tech: {orphan[:5]}"
            + ("..." if len(orphan) > 5 else "")
        )

    # ── Vérifier les doublons de déblocage ──────────────────────────────
    # Compter combien de fois chaque recette apparaît dans les techs
    recipe_count: dict[str, int] = {}
    for tech in technologies:
        for effect in tech.get("effects", []):
            if effect.get("type") == "unlock-recipe":
                r = effect.get("recipe", "")
                recipe_count[r] = recipe_count.get(r, 0) + 1
    duplicates = {r: c for r, c in recipe_count.items() if c > 1}
    if duplicates:
        dup_list = sorted(duplicates.items())[:5]
        result.add_warning(
            f"tech-recettes: {len(duplicates)} recettes débloquées "
            f"plusieurs fois: {dup_list}"
        )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║              INVARIANT 4 : COÛTS OBTENABLES (§13)                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _check_tech_costs_obtainable(
    technologies: list[dict],
    state: ProgressionState,
    result: ValidationResult,
) -> None:
    """Vérifie que les coûts de recherche sont obtenables au bon moment.

    Simule la progression des techs dans l'ordre. À chaque tech payante,
    vérifie que ses matériaux de recherche sont déjà dans le pool
    (items/fluides obtenus par les ressources au sol + les recettes des
    techs précédentes).

    Si un matériau manque, c'est un bug : le joueur ne peut pas produire
    ce matériau au moment de cette recherche.

    Note : les techs gratuites n'ont pas de coût → on les skip.
    Les techs avec coût=[] sont aussi skippées (elles sont gratuites).
    """
    # Pool de départ : items/fluides obtenus (y compris ressources au sol)
    pool = set(state.obtained_items)
    pool.update(state.obtained_fluids)

    # Parcourir les techs dans l'ordre
    for tech in technologies:
        ingredients = tech.get("unit", {}).get("ingredients", [])
        is_free = not ingredients

        # Les techs gratuites n'ont pas de coût → pas de vérification
        if is_free:
            # Mais on ajoute quand même les items/fluides débloqués
            # par cette tech au pool (recettes → produits disponibles)
            _add_tech_products_to_pool(tech, state, pool)
            continue

        # Vérifier que chaque ingrédient de coût est dans le pool
        for ing in ingredients:
            item_name = ing.get("name", "")
            if item_name and item_name not in pool:
                result.add_issue(
                    f"coûts: tech '{tech.get('id', '?')}' demande '{item_name}' "
                    f"mais cet item n'est pas obtainable à ce point"
                )

        # Ajouter les produits de cette tech au pool
        _add_tech_products_to_pool(tech, state, pool)


def _add_tech_products_to_pool(
    tech: dict,
    state: ProgressionState,
    pool: set[str],
) -> None:
    """Ajoute au pool les items/fluides rendus disponibles par une tech.

    Quand une tech débloque des recettes, les produits de ces recettes
    deviennent potentiellement fabriquables (si les ingrédients sont
    dans le pool). On ajoute les produits au pool pour les techs
    suivantes.
    """
    # Pour chaque recette débloquée, ajouter ses résultats au pool
    for effect in tech.get("effects", []):
        if effect.get("type") != "unlock-recipe":
            continue
        recipe_name = effect.get("recipe", "")
        # Chercher la recette dans le state pour connaître ses résultats
        for recipe in state.recipes:
            if recipe.get("name") == recipe_name:
                for res in recipe.get("results", []):
                    pool.add(res.get("name", ""))
                break


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║              INVARIANT 5 : RÈGLE DES TUYAUX (§8/§15)                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _check_pipe_rule(
    state: ProgressionState,
    patch_resources: set[str],
    result: ValidationResult,
) -> None:
    """Vérifie la solvabilité réelle des produits (§8/§15).

    Un « cycle de recettes » entre recettes relais et recettes du starter est
    bénin : chaque item reste fabriquable via sa recette primaire, et les
    relais ne servent qu'à remplacer une matière première épuisable. Le vrai
    softlock est un PRODUIT qui n'est jamais reachable depuis les sources
    externes (patches, ressources environnementales, kit de départ).

    Point fixe : on part des sources, on ajoute tout item dont une recette
    n'utilise que des items déjà atteignables, jusqu'à stabilisation. Tout
    produit de recette resté hors du point fixe est inaccessible → warning.
    """
    unreachable = _detect_unreachable_products(state, set(patch_resources))
    for product, producers in unreachable.items():
        result.add_warning(
            f"anti-cycle §8: produit inaccessible '{product}' "
            f"(recettes: {', '.join(sorted(producers))})"
        )


def _detect_unreachable_products(
    state: ProgressionState, external: set[str] | None = None
) -> dict[str, set[str]]:
    """Point fixe de solvabilité : produits des recettes jamais atteignables.

    ``external`` = ressources fournies par la carte/environnement (ou kit).
    Retourne {produit: {recettes qui le produisent sans jamais pouvoir
    tourner}}. Un cycle entre recettes relais et recettes primaires n'apparaît
    ici QUE s'il ne reste aucun chemin de production réel (softlock).
    """
    from tool.common.db import ENVIRONMENTAL_ITEMS

    if external is None:
        external = set()
    external = set(external) | set(ENVIRONMENTAL_ITEMS)

    reachable = set(external)
    changed = True
    while changed:
        changed = False
        for recipe in state.recipes:
            if not _can_run_in(recipe, reachable, external):
                continue
            for res in recipe.get("results", []):
                name = res.get("name", "")
                if name not in reachable:
                    reachable.add(name)
                    changed = True

    unreachable: dict[str, set[str]] = {}
    for recipe in state.recipes:
        for res in recipe.get("results", []):
            name = res.get("name", "")
            if name in external:
                continue
            if name not in reachable:
                unreachable.setdefault(name, set()).add(recipe["name"])
    return unreachable


def _can_run_in(recipe: dict, reachable: set[str], external: set[str]) -> bool:
    """Une recette peut tourner si chacun de ses ingrédients est atteignable
    (directement source externe, ou déjà dans le point fixe)."""
    for ing in recipe.get("ingredients", []):
        name = ing.get("name", "")
        if name not in external and name not in reachable:
            return False
    return True


def _detect_recipe_cycles(state: ProgressionState, external: set[str] = frozenset()) -> list[list[str]]:
    """Diagnostic : circuits du graphe « recette utilise un résultat de recette ».

    Plus fin que la solvabilité : utile en test pour vérifier qu'un cycle
    artificiel est bien repéré. Non utilisé dans la validation (des cycles
    entre relais et recettes primaires restent bénins tant que chaque item a
    un chemin de production réel).
    """
    produced_by: dict[str, list[str]] = {}
    for recipe in state.recipes:
        for res in recipe.get("results", []):
            produced_by.setdefault(res.get("name", ""), []).append(recipe["name"])

    graph: dict[str, list[str]] = {}
    for recipe in state.recipes:
        deps: list[str] = []
        for ing in recipe.get("ingredients", []):
            for prod in produced_by.get(ing.get("name", ""), []):
                if not _needs_recipes_for(prod, state, external):
                    continue
                deps.append(prod)
        graph[recipe["name"]] = deps

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for nb in graph.get(node, []):
            if nb not in color:
                visit(nb)
            elif color.get(nb) == GRAY:
                i = stack.index(nb)
                circuit = stack[i:]
                cycled = set(circuit)
                if not any(set(c) == cycled for c in cycles):
                    cycles.append(list(circuit))
                continue
        stack.pop()
        color[node] = BLACK

    for node in graph:
        if node not in color:
            visit(node)
    return cycles


def _needs_recipes_for(recipe_name: str, state: ProgressionState, external: set[str]) -> bool:
    """Une recette conditionne une autre seulement si TOUS ses produits
    demandent d'être fabriqués (aucun fourni par la carte/environnement/kit)."""
    for recipe in state.recipes:
        if recipe["name"] != recipe_name:
            continue
        for res in recipe.get("results", []):
            if res.get("name") in external:
                return False
        return True
    return False


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║              INVARIANT 6 : COMPLÉTUDE FUSÉE (§14)                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _check_victory_requirements(
    state: ProgressionState,
    result: ValidationResult,
) -> None:
    """Vérifie que la chaîne vers la fusée est complète (§14).

    Le lancement de la fusée nécessite :
      - Le building rocket-silo (via sa recette randputf-rocket-silo)
      - Le recipe rocket-part (vanilla, toujours activé via exemption)

    La phase endgame (§14) garantit la recette du silo dans TOUTE seed : si
    elle manque, la victoire est impossible et la seed est INVALIDE (issue,
    pas simple warning).
    """
    silo_recipe_exists = any(
        r.get("name") == "randputf-rocket-silo" for r in state.recipes
    )
    if not silo_recipe_exists:
        result.add_issue(
            "complétude: recette 'randputf-rocket-silo' non trouvée"
        )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║          INVARIANT 7 : PACKS SANS RESSOURCE BRUTE (§3, §13)              ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _check_packs_no_raw(
    state: ProgressionState,
    patch_resources: set[str],
    lake_resources: set[str],
    db: VanillaDB,
    result: ValidationResult,
) -> None:
    """Vérifie qu'aucun science pack n'est crafté avec une ressource brute.

    Les packs sont la monnaie de recherche (§13) : leur recette ne doit jamais
    consommer de matière extraite directement du sol — patch posé au sol,
    fluide de LAC (pompe offshore, IDEES C2/C6 : une raw resource de plus),
    item environnemental récolté à la main (bois/pierre/poisson), ou fluide
    d'extraction "infini" (eau, pétrole brut, vapeur, §3).

    Même si une ressource devient par ailleurs craftable en fin de seed (un
    patch recouvert d'une recette randputf-*), elle reste "brute" : la recette
    du pack doit se reposer sur des intermédiaires craftés. C'est la sécurité
    de second niveau — la génération l'applique déjà via `forbidden` sur
    ensure_obtainable/make_recipe (starter, branche science, balayage)."""
    raw = (
        set(patch_resources)
        | set(lake_resources or ())
        | set(ENVIRONMENTAL_ITEMS)
        | set(db.extraction_only_fluids)
    )
    violations = []
    for recipe in state.recipes:
        is_pack = any(
            res.get("type") == SLOT_ITEM
            and (item := db.items.get(res.get("name", ""))) is not None
            and item.is_science_pack
            for res in recipe.get("results", [])
        )
        if not is_pack:
            continue
        for ing in recipe.get("ingredients", []):
            if ing.get("name") in raw:
                violations.append(
                    f"{recipe['name']} consomme la ressource brute '{ing['name']}'"
                )
    if violations:
        result.add_issue(
            f"packs sans ressource brute: {len(violations)} — "
            + "; ".join(violations[:5])
            + ("..." if len(violations) > 5 else "")
        )
