"""Validation du pipeline de génération.

Valide le ProgressionState + TechGraph produits par le pipeline, AVANT
l'assemblage de la seed (validator/solver.py ne valide que le format final).

Invariants :
1. anti-cycle : pas de recette dépendant de sa propre production.
2. progressivité : chaque recette n'utilise que des ingrédients obtenus.
3. cohérence tech-recettes : chaque recette débloquée par exactement UNE tech.
4. coûts obtenables : matériaux de recherche produisibles au bon moment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_ITEM, VanillaDB
from tool.generator.recipes import ProgressionState


@dataclass
class ValidationResult:
    """Résultat de la validation du pipeline.

    - is_valid : aucun problème détecté
    - issues : messages d'erreur bloquants
    - warnings : avertissements non bloquants
    - stats : statistiques de validation
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


# ── Fonction principale (API publique) ─────────────────────────────────────


def validate_pipeline(
    state: ProgressionState,
    technologies: list[dict],
    db: VanillaDB,
    patch_resources: set[str] | None = None,
    lake_resources: set[str] | None = None,
) -> ValidationResult:
    """Valide l'ensemble du pipeline. Fonction d'entrée : prend le résultat
    de toutes les phases et vérifie les invariants.

    - state : état de progression (recettes, items/fluides obtenus)
    - technologies : liste de techs du tech_tree.py
    - db : base vanilla
    - patch_resources : ressources déjà au sol (patchs, optionnel)
    - lake_resources : fluides déjà posés en LAC — ressources brutes
      obtenables dès le départ (pompe offshore, volume infini) : ils comptent
      comme source externe pour la solvabilité du bootstrap, au même titre
      qu'un patch.

    Retourne un ValidationResult (is_valid, issues, warnings, stats).
    """
    result = ValidationResult()

    # Si pas de ressources au sol fournies, extraire du state
    if patch_resources is None:
        patch_resources = set()
    if lake_resources is None:
        lake_resources = set()

    # Sources externes = patchs + lacs : obtenables dès le départ sans recette ;
    # un fluide en lac est une raw resource pompeable immédiatement.
    external = set(patch_resources) | set(lake_resources)

    # ── Invariant 1 : anti-cycle ────────────────────────────────────────
    _check_anti_cycle(state, result, external)

    # ── Invariant 2 : progressivité ─────────────────────────────────────
    _check_progressivity(state, external, result)

    # ── Invariant 3 : cohérence tech-recettes ───────────────────────────
    _check_tech_recipe_coherence(state, technologies, result)

    # ── Invariant 4 : coûts obtainables ─────────────────────────────────
    _check_tech_costs_obtainable(technologies, state, result)

    # ── Invariant 5 : règle des tuyaux ────────────────────────────────────
    _check_pipe_rule(state, external, result)

    # ── Invariant 6 : complétude fusée ───────────────────────────────────
    _check_victory_requirements(state, result)

    # ── Invariant 7 : packs sans ressource brute ──────────────────────────
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


# ── Invariant 1 : anti-cycle ────────────────────────────────────────────────


def _check_anti_cycle(
    state: ProgressionState,
    result: ValidationResult,
    patch_resources: set[str] | None = None,
) -> None:
    """Vérifie l'absence de boucle dans les dépendances de production.

    Solvabilité au niveau de l'ITEM : une recette est résolue quand TOUS ses
    ingrédients sont solvables (patch, ressource environnementale, ou produit
    d'une recette résolue) ; un item est solvable dès qu'une de ses recettes
    l'est. La sémantique « OU » compte double depuis les recettes relais :
    un aller-retour relais-A → bootstrap-B → relais-A ne crée aucune impasse
    (item A reste solvable par sa chaîne principale). À l'issue du point
    fixe, toute recette non résolue révèle une vraie boucle.

    Algorithme : part de solvable = ressources au sol + environnementaux,
    résout itérativement les recettes dont tous les ingrédients sont
    solvables ; les restées insolubles forment les boucles.
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


# ── Invariant 2 : progressivité ─────────────────────────────────────────────


def _check_progressivity(
    state: ProgressionState,
    patch_resources: set[str],
    result: ValidationResult,
) -> None:
    """Vérifie que chaque recette n'utilise que des ingrédients obtenables.

    Parcourt les recettes dans l'ordre de création : tous les ingrédients
    doivent être déjà dans le pool (items/fluides obtenus + ressources au
    sol). Un ingrédient manquant = bug du générateur.
    """
    # Pool = ressources au sol + environnement (obtenables dès le départ) +
    # items/fluides obtenus, cohérent avec l'anti-cycle et le point fixe.
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


# ── Invariant 3 : cohérence tech-recettes ───────────────────────────────────


def _check_tech_recipe_coherence(
    state: ProgressionState,
    technologies: list[dict],
    result: ValidationResult,
) -> None:
    """Vérifie que chaque recette est débloquée par exactement UNE tech.

    - Recette orpheline : créée par le pipeline, jamais débloquée → le joueur
      ne pourra pas la fabriquer.
    - Double déblocage : une recette dans les effects de plusieurs techs
      (inutile et confusant, même si Factorio ignore les doublons).
    """
    # Recettes débloquées par les techs
    tech_recipes: set[str] = set()
    for tech in technologies:
        for effect in tech.get("effects", []):
            if effect.get("type") == "unlock-recipe":
                tech_recipes.add(effect.get("recipe", ""))

    # Recettes créées par le pipeline
    pipeline_recipes: set[str] = set()
    for recipe in state.recipes:
        pipeline_recipes.add(recipe.get("name", ""))

    orphan = sorted(pipeline_recipes - tech_recipes)
    if orphan:
        # Orphelines = recettes créées "sur le tas" (fabriquer bâtiments/items),
        # auto-disponibles au début (enabled par défaut) : warning, pas erreur.
        result.add_warning(
            f"tech-recettes: {len(orphan)} recettes créées mais pas "
            f"débloquées par une tech: {orphan[:5]}"
            + ("..." if len(orphan) > 5 else "")
        )

    # Doublons : compter les déblocages par recette
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


# ── Invariant 4 : coûts obtenables ──────────────────────────────────────────


def _check_tech_costs_obtainable(
    technologies: list[dict],
    state: ProgressionState,
    result: ValidationResult,
) -> None:
    """Vérifie que les coûts de recherche sont obtenables au bon moment.

    Simule la progression des techs dans l'ordre : chaque ingrédient de coût
    d'une tech payante doit être déjà dans le pool (sinon bug : matériau non
    produisible à ce point). Les techs gratuites (cost vuides) sont skippées.
    """
    # Pool de départ : items/fluides obtenus (y compris ressources au sol)
    pool = set(state.obtained_items)
    pool.update(state.obtained_fluids)

    # Parcourir les techs dans l'ordre
    for tech in technologies:
        ingredients = tech.get("unit", {}).get("ingredients", [])
        is_free = not ingredients

        # Techs gratuites : pas de coût à vérifier, ajouter les produits au pool.
        if is_free:
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
    Les produits des recettes débloquées deviennent potentiellement
    fabriquables pour les techs suivantes.
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


# ── Invariant 5 : règle des tuyaux ──────────────────────────────────────────


def _check_pipe_rule(
    state: ProgressionState,
    patch_resources: set[str],
    result: ValidationResult,
) -> None:
    """Vérifie la solvabilité réelle des produits.

    Un cycle entre recettes relais et recettes du starter est bénin (chaque
    item reste fabriquable via sa recette primaire). Le vrai softlock est un
    PRODUIT jamais atteignable depuis les sources externes (patches,
    environnement, kit) : point fixe depuis les sources, tout produit hors
    point fixe → warning.
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
    tourner}}. Un cycle relais/primaire n'apparaît QUE s'il ne reste aucun
    chemin de production réel (softlock).
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

    Plus fin que la solvabilité ; utile en test. Non utilisé dans la
    validation (cycles relais/primaire bénins tant que chaque item a un
    chemin de production réel).
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


# ── Invariant 6 : complétude fusée ──────────────────────────────────────────


def _check_victory_requirements(
    state: ProgressionState,
    result: ValidationResult,
) -> None:
    """Vérifie que la chaîne vers la fusée est complète.

    Lancement = building rocket-silo (via la recette randputf-rocket-silo) +
    recipe rocket-part (vanilla, exemption). La phase endgame garantit la
    recette du silo dans toute seed : si elle manque, la seed est INVALIDE
    (issue, pas warning).
    """
    silo_recipe_exists = any(
        r.get("name") == "randputf-rocket-silo" for r in state.recipes
    )
    if not silo_recipe_exists:
        result.add_issue(
            "complétude: recette 'randputf-rocket-silo' non trouvée"
        )


# ── Invariant 7 : packs sans ressource brute ────────────────────────────────


def _check_packs_no_raw(
    state: ProgressionState,
    patch_resources: set[str],
    lake_resources: set[str],
    db: VanillaDB,
    result: ValidationResult,
) -> None:
    """Vérifie qu'aucun science pack n'est crafté avec une ressource brute.

    Packs = monnaie de recherche : leur recette ne doit jamais consommer de
    matière extraite directement du sol (patch, fluide de lac, item
    environnemental, fluide d'extraction). Une ressource reste « brute » même
    si elle devient craftable en fin de seed. Sécurité de second niveau — la
    génération l'applique déjà via `forbidden`."""
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
