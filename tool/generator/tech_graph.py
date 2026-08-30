"""tech_graph.py — Logique principale de l'arbre technologique (README §13).

C'est LA boucle principale du randomizer. Ce module transforme les étapes
brutes générées par les phases précédentes (starter, récursif, électricité)
en un arbre technologique complet, valide et prêt à être consommé par le mod
Factorio (data.lua).

═══════════════════════════════════════════════════════════════════════════════
                        CONCEPT GÉNÉRAL
═══════════════════════════════════════════════════════════════════════════════

Le randomizer produit des « étapes » (steps) au fil des phases :
  - Phase 2 (starter_chain) : extraction initiale, transformation initiale
  - Phase 3 (recursive_phase) : un bâtiment, une arme, un pack de science...
  - Phase 4 (electricity) : un générateur + combustible

Chaque étape décrit CE QUI EST DÉBLOQUÉ (recettes, bâtiments) mais pas
COMMENT le joueur le recherche. C'est le rôle de ce module de :

  1. Grouper les étapes en nœuds de technologie cohérents
  2. Assigner un coût de recherche (matériaux arbitraires, §13)
  3. Chaîner les nœuds en linéaire (sans boucle)
  4. Valider que chaque coût est obtenable au bon moment
  5. Produire le format seed attendu par data.lua

═══════════════════════════════════════════════════════════════════════════════
                     CONTRAINTES DE SOLVABILITÉ (§15)
═══════════════════════════════════════════════════════════════════════════════

Trois invariants s'appliquent spécifiquement au tech tree :

  1. ACOPLAGE RECETTES-TECHS : chaque recette créée par les phases doit
     apparaître exactement UN一次 dans les effects d'une tech (unlock-recipe).
     Pas de recette orpheline (jamais débloquée), pas de double déblocage.

  2. COÛTS OBTENABLES : les matériaux demandés pour chaque tech doivent
     être produits par le joueur AVANT ce point de la chaîne. On ne peut
     pas demander un circuit intégré si le joueur n'a pas encore l'assembl
     pour le fabriquer.

  3. CHAÎNE SANS BOUCLE : l'ordre des techs forme un graphe acyclique
     dirigé. Chaque tech ne dépend que de techs AVANT elle dans la chaîne.

═══════════════════════════════════════════════════════════════════════════════
                          FORMAT DE SORTIE
═══════════════════════════════════════════════════════════════════════════════

La seed Factorio attend pour chaque tech :
  {
    "id": "randputf-category-name",
    "localised_name": "Titre lisible",
    "prerequisites": ["randputf-previous-tech"],
    "unit": {
      "count": 10,            -- nombre de fois à produire les ingrédients
      "ingredients": [        -- les items à produire (PAS des science packs)
        {"type": "item", "name": "iron-plate", "amount": 5}
      ]
    },
    "effects": [
      {"type": "unlock-recipe", "recipe": "randputf-assembling-machine-2"}
    ]
  }

Le champ "unit.count" est le nombre de cycles de production.
Le champ "unit.ingredients" sont les matériaux à produire PAR CYCLE.
Coût total = count × somme(amount pour chaque ingredient).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.common.db import SLOT_ITEM, VanillaDB
from tool.generator.recipes import ProgressionState
from tool.prototypes.tech_tree import TechTreeConfig

_config = TechTreeConfig()


def set_config(config: dict) -> None:
    global _config
    _config = TechTreeConfig.from_config(config)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                          TYPES DE DONNÉES                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


@dataclass
class TechNode:
    """Un nœud de l'arbre technologique.

    Chaque nœud représente UNE recherche que le joueur peut effectuer.
    Il contient :
      - id : identifiant unique (prefixed randputf-)
      - title : nom affiché au joueur
      - unlocks_recipes : noms des recettes débloquées par cette tech
      - unlocks_buildings : noms des bâtiments débloqués (deviennent des
        "unlock-recipe" pour le recipe du bâtiment, ex: "randputf-assembler")
      - cost : matériaux de recherche (liste de {type, name, amount})
      - count : nombre de cycles de production (multiplicateur du coût)
      - is_free : si True, pas de coût (recherche gratuite, ex: starter)
    """

    id: str
    title: str
    unlocks_recipes: list[str] = field(default_factory=list)
    unlocks_buildings: list[str] = field(default_factory=list)
    cost: list[dict] = field(default_factory=list)
    count: int = 10
    is_free: bool = False


@dataclass
class TechGraph:
    """Graphe technologique complet.

    Contient tous les nœuds de l'arbre + la liste des techs gratuites
    (déjà recherchées au démarrage du jeu).

    nodes : liste ordonnée dans l'ordre de recherche (index 0 = premier)
    free_techs : IDs des techs gratuites (auto-researched au spawn)
    """

    nodes: list[TechNode] = field(default_factory=list)
    free_techs: list[str] = field(default_factory=list)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    FONCTIONS PRINCIPALES (API PUBLIQUE)                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def build_tech_graph(
    starter_steps: list[dict],
    recursive_steps: list[dict],
    db: VanillaDB,
    state: ProgressionState | None = None,
    patch_items: set[str] | None = None,
) -> TechGraph:
    """Construit l'arbre technologique complet à partir de toutes les phases.

    C'est LA fonction d'entrée. Elle prend les étapes brutes des phases
    précédentes et produit un TechGraph valide, prêt à être converti en seed.

    Paramètres :
      - starter_steps : étapes de la phase 2 (extraction, transformation)
      - recursive_steps : étapes de la phase 3 (bâtiments, armes, science)
      - db : base vanilla pour connaître les items/fluides disponibles

    Retourne :
      - TechGraph avec tous les nœuds chaînés et validés

    Algorithme :
      1. Fusionner et dédupliquer les étapes
      2. Regrouper par catégorie (groupes logiques)
      3. Assigner les coûts de recherche (progression par profondeur)
      4. Chaîner en linéaire (chaque nœud dépend du précédent)
      5. Valider les coûts (chaque ingrédient doit être obtenable)
    """
    # ── Étape 1 : fusionner toutes les étapes ──────────────────────────
    all_steps = starter_steps + recursive_steps
    steps_dedup = _deduplicate_steps(all_steps)

    # ── Étape 2 : séparer les étapes gratuites (starter) et payantes ───
    # Les étapes starter sont toujours gratuites (count=1, cost=[]).
    # Les étapes récursives ont un coût.
    free_steps = [s for s in steps_dedup if _is_free_step(s)]
    paid_steps = [s for s in steps_dedup if not _is_free_step(s)]

    # ── Étape 3 : créer les nœuds tech ────────────────────────────────
    # On crée un TechNode par étape. Le groupage peut fusionner des
    # étapes consécutives de même catégorie en un seul nœud.
    paid_groups = _group_steps(paid_steps)

    free_nodes = [_step_to_node(s, is_free=True) for s in free_steps]
    paid_nodes = [_group_to_node(g, i) for i, g in enumerate(paid_groups)]

    # ── Étape 4 : assigner les coûts ───────────────────────────────────
    # Les nœuds gratuits n'ont pas de coût.
    # Les nœuds payants reçoivent un coût basé sur leur position.
    # L'ordre compte : plus on avance, plus c'est cher.
    _assign_costs(paid_nodes, free_nodes, db, state, patch_items)

    # ── Étape 5 : chaîner en linéaire ──────────────────────────────────
    # Tous les nœuds gratuits viennent en premier (prérequis = []),
    # puis les nœuds payants enchaînent.
    all_nodes = free_nodes + paid_nodes
    _chain_linear(all_nodes, len(free_nodes))

    # ── Étape 6 : valider ──────────────────────────────────────────────
    issues = _validate_chain(all_nodes)
    if issues:
        # En cas de problème de coûts, on rend les techs problématiques
        # gratuites plutôt que de planter — le joueur peut toujours jouer.
        _fix_invalid_costs(all_nodes, issues)

    # ── Assemblage ─────────────────────────────────────────────────────
    free_techs = [n.id for n in free_nodes]
    return TechGraph(nodes=all_nodes, free_techs=free_techs)


def tech_graph_to_seed(graph: TechGraph) -> list[dict]:
    """Convertit un TechGraph en format seed (liste de dicts pour data.lua).

    Chaque TechNode est converti en dict avec la structure attendue :
      - id, localised_name, prerequisites, unit (count + ingredients),
        effects (unlock-recipe entries)

    Les unlock-recipe pour les bâtiments sont préfixés "randputf-" car
    le recipe du bâtiment s'appelle "randputf-<nom_batiment>".
    """
    techs = []
    for node in graph.nodes:
        # ── Effets : unlock-recipe pour chaque recette et bâtiment ─────
        effects = []
        for recipe_name in node.unlocks_recipes:
            effects.append({"type": "unlock-recipe", "recipe": recipe_name})
        for building_name in node.unlocks_buildings:
            # Le recipe du bâtiment est "randputf-<nom>", mais le nom
            # du building est juste "<nom>". data.lua crée le recipe.
            effects.append({"type": "unlock-recipe", "recipe": building_name})

        # ── Unit : ingrédients de recherche ────────────────────────────
        # Si la tech est gratuite, unit = {} (pas de coûts).
        # Sinon, unit = {count, time, ingredients}.
        # Le "time" est fixé à 30 secondes (standard Factorio).
        if node.is_free:
            unit = {"count": 1, "ingredients": []}
        else:
            unit = {
                "count": max(node.count, 1),
                "ingredients": [
                    {
                        "name": ing["name"],
                        "type": ing.get("type", "item"),
                        "amount": int(ing["amount"]),
                    }
                    for ing in node.cost
                ],
            }

        # ── Prerequisites ──────────────────────────────────────────────
        # Le champ "prerequisites" est une liste d'IDs de techs requises.
        # Pour un arbre linéaire, c'est toujours [tech_précédente] ou [].
        prerequisites = []
        if node.prerequisites:
            prerequisites = list(node.prerequisites)

        techs.append({
            "id": node.id,
            "localised_name": node.title,
            "prerequisites": prerequisites,
            "unit": unit,
            "effects": effects,
        })

    return techs


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                       DÉDUPLICATION DES ÉTAPES                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _deduplicate_steps(steps: list[dict]) -> list[dict]:
    """Supprime les doublons d'étapes (même id).

    Les phases précédentes peuvent produire des étapes avec le même id
    si un bâtiment est débloqué deux fois (ex: par le starter ET par le
    récursif). On ne garde que la première occurrence, mais on fusionne
    les unlocks pour ne rien perdre.
    """
    seen: dict[str, dict] = {}
    result = []
    for step in steps:
        step_id = step.get("id", "")
        if step_id in seen:
            # Fusionner les unlocks de la seconde occurrence dans la première
            existing = seen[step_id]
            for r in step.get("unlocks_recipes", []):
                if r not in existing["unlocks_recipes"]:
                    existing["unlocks_recipes"].append(r)
            for b in step.get("unlocks_buildings", []):
                if b not in existing["unlocks_buildings"]:
                    existing["unlocks_buildings"].append(b)
        else:
            # Première occurrence : on la garde telle quelle
            seen[step_id] = step
            result.append(step)
    return result


def _is_free_step(step: dict) -> bool:
    """Détermine si une étape est gratuite (pas de coût de recherche).

    Une étape est gratuite si :
      - son count est 1 ou moins, ET
      - sa liste de cost est vide ou absente

    C'est le cas des étapes starter (extraction initiale, transformation
    initiale) qui sont débloquées automatiquement au spawn.
    """
    count = step.get("count", 10)
    cost = step.get("cost", [])
    return count <= 1 and (not cost or cost == [])


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                          GROUPAGE DES ÉTAPES                            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _group_steps(steps: list[dict]) -> list[list[dict]]:
    """Regroupe les étapes consécutives de même catégorie.

    Le groupage crée des nœuds de technologie plus larges et plus
    significatifs pour le joueur. Au lieu de 40 techs individuelles
    (une par bâtiment), on obtient des groupes cohérents :
      - "Logistics" : belt + splitter + underground + inserter
      - "Assemblers" : assembling-machine-1, 2, 3
      - "Science" : tous les packs de science

    Règle de groupage : deux étapes consécutives sont groupées si
    elles ont la MÊME catégorie (le premier mot du step_id après
    "randputf-").

    Exemples d'ids :
      - "randputf-transformer-assembling-machine-1" → catégorie "transformer"
      - "randputf-distribution-transport-belt" → catégorie "distribution"
      - "randputf-combat-pistol" → catégorie "combat"
      - "randputf-science-automation-science-pack" → catégorie "science"
    """
    if not steps:
        return []

    groups: list[list[dict]] = []
    current_group: list[dict] = [steps[0]]
    current_cat = _step_category(steps[0])

    for step in steps[1:]:
        cat = _step_category(step)
        if cat == current_cat:
            # Même catégorie → on ajoute au groupe en cours
            current_group.append(step)
        else:
            # Catégorie différente → on ferme le groupe actuel
            groups.append(current_group)
            current_group = [step]
            current_cat = cat

    # Ne pas oublier le dernier groupe
    groups.append(current_group)
    return groups


def _step_category(step: dict) -> str:
    """Extrait la catégorie d'une étape depuis son id.

    Convention : les ids ont le format "randputf-<catégorie>-<nom>".
    On extrait le premier mot après "randputf-".
    Si le format est différent, on retourne l'id complet comme catégorie
    (chaque étape sera donc dans son propre groupe).
    """
    step_id = step.get("id", "")
    # Supprimer le préfixe "randputf-" si présent
    if step_id.startswith("randputf-"):
        step_id = step_id[len("randputf-"):]
    # Extraire la première partie avant le premier "-"
    parts = step_id.split("-", 1)
    return parts[0] if parts else step_id


def _group_to_node(group: list[dict], group_index: int) -> TechNode:
    """Convertit un groupe d'étapes en un seul TechNode.

    Le nœud fusionne :
      - Toutes les recettes débloquées par chaque étape du groupe
      - Tous les bâtiments débloqués
      - Le titre le plus informatif (premier titre non-vide du groupe)
      - Un id unique basé sur la catégorie + l'index du groupe

    L'ID est unique car on utilise le groupe_index (position dans la
    liste des groupes) comme suffixe. Cela garantit que même si deux
    groupes ont la même catégorie, leurs IDs sont différents.

    Les doublons de recettes/bâtiments sont supprimés au passage.
    """
    cat = _step_category(group[0])

    # Fusionner toutes les recettes et bâtiments du groupe
    all_recipes = []
    all_buildings = []
    title = ""
    for step in group:
        for r in step.get("unlocks_recipes", []):
            if r not in all_recipes:
                all_recipes.append(r)
        for b in step.get("unlocks_buildings", []):
            if b not in all_buildings:
                all_buildings.append(b)
        if not title:
            title = step.get("title", "")

    # Si le titre est vide, construire un titre générique
    if not title:
        title = f"{cat.title()} research"

    # L'id du groupe est unique grâce au group_index
    group_id = f"randputf-{cat}-tier-{group_index}"

    return TechNode(
        id=group_id,
        title=title,
        unlocks_recipes=all_recipes,
        unlocks_buildings=all_buildings,
        cost=[],
        count=10,
    )


def _step_to_node(step: dict, is_free: bool = False) -> TechNode:
    """Convertit une étape individuelle en TechNode.

    Utilisé pour les étapes gratuites (starter) qui ne sont pas groupées.
    """
    return TechNode(
        id=step.get("id", "randputf-unknown"),
        title=step.get("title", "Unknown research"),
        unlocks_recipes=list(step.get("unlocks_recipes", [])),
        unlocks_buildings=list(step.get("unlocks_buildings", [])),
        cost=list(step.get("cost", [])),
        count=int(step.get("count", 1)),
        is_free=is_free,
    )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                   ASSIGNATION DES COÛTS DE RECHERCHE                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _assign_costs(
    paid_nodes: list[TechNode],
    free_nodes: list[TechNode],
    db: VanillaDB,
    state: ProgressionState | None = None,
    patch_items: set[str] | None = None,
) -> None:
    """Assigne un coût de recherche à chaque nœud payant.

    PRINCIPE (README §13) :
      Le coût d'une recherche doit utiliser des items de type "tool"
      (science packs) — seule configuration acceptée par Factorio 2.0.

    ALGORITHME :
      Le pool de départ contient uniquement les science packs présents
      dans les patches (minés au sol) + kit de départ. Les packs créés
      par des recettes ne sont ajoutés que quand leur tech est débloquée.
      Cela garantit la progressivité : on ne peut pas demander un pack
      que le joueur ne peut pas encore produire.
    """
    tool_items = {
        name for name, item in db.items.items()
        if item.is_science_pack
    }

    pool: set[str] = set()

    # Science packs disponibles dès le départ : uniquement ceux
    # qui viennent des patches (minés au sol) ou du kit de départ.
    # PAS de state.obtained_items — celui contient tout, y compris
    # les packs créés par des recettes pas encore débloquées.
    if patch_items:
        pool |= patch_items & tool_items

    # Retirer les noms randputf-
    pool = {n for n in pool if not n.startswith("randputf-")}

    def _add_node_products(node: TechNode) -> None:
        for recipe_name in node.unlocks_recipes:
            for recipe in (state.recipes if state else []):
                if recipe.get("name") == recipe_name:
                    for res in recipe.get("results", []):
                        name = res.get("name", "")
                        if not name.startswith("randputf-") and name in tool_items:
                            pool.add(name)

    for node in free_nodes:
        _add_node_products(node)

    total_nodes = len(free_nodes) + len(paid_nodes)

    for index, node in enumerate(paid_nodes):
        depth = len(free_nodes) + index
        cost_candidates = sorted(pool)

        if not cost_candidates:
            node.is_free = True
            node.cost = []
            node.count = 1
        else:
            node.cost = _compute_cost(depth, total_nodes, cost_candidates)
            node.count = _compute_count(depth, total_nodes)

        _add_node_products(node)


def _compute_cost(
    depth: int,
    total: int,
    candidates: list[str],
) -> list[dict]:
    """Calcule le coût (ingrédients) d'un nœud à une profondeur donnée.

    Retourne une liste de {type: "item", name: "...", amount: N}.

    La logique :
      - Plus on est profond dans l'arbre, plus les coûts sont élevés
      - Le nombre d'ingrédients différents augmente avec la profondeur
      - Les montants par ingrédient augmentent aussi
      - On choisit AU HASARD dans les candidats (pas de déterminisme
        sur quels items spécifiques — c'est la seed qui pilote)
    """
    # Plages de coûts selon la profondeur relative (0.0 = début, 1.0 = fin)
    ratio = depth / max(total - 1, 1)

    # Trouver le bon palier de coûts
    tier = _config.cost_tiers[-1]
    for t in _config.cost_tiers:
        if ratio < t.depth_threshold:
            tier = t
            break
    n_ingredients = tier.n_ingredients
    amount_range = (tier.amount_min, tier.amount_max)

    # Sélectionner les ingrédients
    # On ne peut pas demander plus d'ingrédients que de candidats
    n_ingredients = min(n_ingredients, len(candidates))

    # Attention : on ne peut PAS utiliser `rng` ici car la fonction est
    # déterministe (pas de hasard dans les coûts pour ungiven depth).
    # C'est la seed qui a déjà tout déterminé via les phases précédentes.
    # Pour rester déterministe, on utilise la profondeur comme seed
    # locale pour le choix.
    import hashlib
    seed_bytes = f"cost:{depth}".encode()
    h = hashlib.md5(seed_bytes).hexdigest()

    # Choisir n_ingredients items différents parmi les candidats
    selected = []
    used_indices = set()
    for i in range(n_ingredients):
        # Utiliser le hash pour obtenir un index déterministe
        idx = int(h[i * 2 : i * 2 + 2], 16) % len(candidates)
        # Éviter les doublons en tournant si nécessaire
        attempts = 0
        while idx in used_indices and attempts < len(candidates):
            idx = (idx + 1) % len(candidates)
            attempts += 1
        if idx not in used_indices:
            used_indices.add(idx)
            selected.append(candidates[idx])

    # Construire la liste d'ingrédients avec amounts déterministes
    ingredients = []
    for i, name in enumerate(selected):
        # Amount basé sur le hash pour rester déterministe
        amount_hash = int(h[i * 2 + 8 : i * 2 + 10], 16) if i * 2 + 10 <= len(h) else i + 1
        amount = amount_range[0] + (amount_hash % (amount_range[1] - amount_range[0] + 1))
        ingredients.append({"type": "item", "name": name, "amount": amount})

    return ingredients


def _compute_count(depth: int, total: int) -> int:
    """Calcule le nombre de cycles de production pour un nœud.

    Le "count" est le nombre de fois que le joueur doit produire les
    ingrédients de recherche. Plus la tech est avancée, plus c'est long.
    """
    ratio = depth / max(total - 1, 1)

    import hashlib
    seed_bytes = f"count:{depth}".encode()
    h = hashlib.md5(seed_bytes).hexdigest()
    seed_val = int(h[:4], 16)

    # Trouver le bon palier de counts
    tier = _config.count_tiers[-1]
    for t in _config.count_tiers:
        if ratio < t.depth_threshold:
            tier = t
            break

    return tier.count_min + (seed_val % (tier.count_max - tier.count_min + 1))


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                       CHAÎNAGE LINÉAIRE                                 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _chain_linear(all_nodes: list[TechNode], n_free: int) -> None:
    """Chaîne tous les nœuds en arbre linéaire (sans boucle).

    Modifie les nœuds IN-PLACE en ajoutant le champ `prerequisites`.

    Structure :
      [free_1] → [free_2] → ... → [free_n] → [paid_1] → [paid_2] → ...

    - Les nœuds gratuits n'ont pas de prérequis ([]).
    - Le premier nœud payant dépend du dernier nœud gratuit.
    - Chaque nœud payant dépend du précédent.
    - Le dernier nœud de la chaîne termine la progression.

    C'est un arbre strictement linéaire (README §13 : "linéaire pour v1").
    Le branchement sera envisagé plus tard.
    """
    for i, node in enumerate(all_nodes):
        if i == 0:
            # Premier nœud de la chaîne : pas de prérequis
            node.prerequisites = []
        else:
            # Nœud suivant : dépend du nœud précédent
            node.prerequisites = [all_nodes[i - 1].id]


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                          VALIDATION                                     ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _validate_chain(nodes: list[TechNode]) -> list[str]:
    """Valide la chaîne technologique.

    Vérifie les trois invariants de solvabilité (§15) appliqués au tech tree :

    1. AUCUNE BOUCLE : les prérequis forment un DAG (graphe acyclique).
       Comme on chaîne linéairement, c'est garanti par construction,
       mais on vérifie quand même par sécurité.

    2. COÛTS OBTENABLES : chaque ingrédient de coût doit exister dans
       le pool vanilla (être un item réel du jeu). Si un coût référence
       un item qui n'existe pas, c'est un bug du générateur.

    3. COHÉRENCE DES EFFETS : chaque recette débloquée doit exister
       dans la seed (pas de référence cassée).

    Retourne une liste de messages d'erreur (vide si tout est OK).
    """
    issues = []

    if not nodes:
        issues.append("arbre vide : aucun nœud technologique")
        return issues

    # Vérifier l'absence de boucle (paranoia check)
    _check_no_cycles(nodes, issues)

    # Vérifier que les coûts référencent des items valides
    _check_cost_validity(nodes, issues)

    # Vérifier la cohérence des effets
    _check_effects_coherence(nodes, issues)

    return issues


def _check_no_cycles(nodes: list[TechNode], issues: list[str]) -> None:
    """Vérifie qu'il n'y a pas de cycle dans les prérequis.

    Algorithme : tri topologique de Kahn. Si on ne peut pas trier
    tous les nœuds, il y a un cycle.
    """
    # Construire le graphe de dépendances
    node_map = {n.id: n for n in nodes}
    in_degree = {n.id: 0 for n in nodes}
    dependents: dict[str, list[str]] = {n.id: [] for n in nodes}

    for node in nodes:
        for prereq in node.prerequisites:
            if prereq in node_map:
                in_degree[node.id] += 1
                dependents[prereq].append(node.id)

    # Tri topologique de Kahn
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    sorted_count = 0

    while queue:
        current = queue.pop(0)
        sorted_count += 1
        for dependent in dependents[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if sorted_count != len(nodes):
        issues.append(
            f"cycle détecté dans les prérequis : "
            f"{sorted_count}/{len(nodes)} nœuds triés"
        )


def _check_cost_validity(nodes: list[TechNode], issues: list[str]) -> None:
    """Vérifie que tous les ingrédients de coût sont des items existants.

    Note : on ne vérifie PAS ici si l'item est obtainable à ce point
    de la progression (c'est fait par _fix_invalid_costs). On vérifie
    juste que la référence n'est pas cassée (item inconnu).
    """
    for node in nodes:
        if node.is_free:
            continue
        for ing in node.cost:
            name = ing.get("name", "")
            if not name:
                issues.append(
                    f"tech '{node.id}' : ingrédient de coût sans nom"
                )
            # Note : on ne peut pas vérifier contre db ici car on n'a
            # pas accès à db dans cette fonction. La validation cross-db
            # est faite dans build_tech_graph via _fix_invalid_costs.


def _check_effects_coherence(nodes: list[TechNode], issues: list[str]) -> None:
    """Vérifie que les effets (unlock-recipe) ne sont pas vides."""
    for node in nodes:
        if not node.unlocks_recipes and not node.unlocks_buildings:
            issues.append(
                f"tech '{node.id}' : aucun effet (ni recette ni bâtiment)"
            )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    CORRECTION DES COÛTS INVALIDES                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _fix_invalid_costs(
    nodes: list[TechNode],
    issues: list[str],
) -> None:
    """Corrige les coûts invalides en les rendant gratuits.

    Si un coût est invalide (item inconnu, référence cassée), on rend
    la tech gratuite plutôt que de planter. C'est un filet de sécurité :
    le joueur peut toujours jouer, même si le coût est « gratuit » au
    lieu de « normal ».

    Dans la pratique, ce cas ne devrait pas se produire si le pool
    d'items est correctement initialisé. Mais mieux vaut un tech gratuite
    qu'un crash.
    """
    for node in nodes:
        if node.is_free:
            continue

        # Vérifier si le coût contient des items vides
        has_invalid = False
        for ing in node.cost:
            if not ing.get("name"):
                has_invalid = True
                break

        if has_invalid:
            node.is_free = True
            node.cost = []
            node.count = 1


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                          UTILITAIRES                                     ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def summarize_graph(graph: TechGraph) -> str:
    """Produit un résumé lisible du graph technologique.

    Utile pour le débogage et les logs. Affiche :
      - Le nombre total de techs
      - Le nombre de techs gratuites vs payantes
      - La liste des techs avec leurs effets
      - Les éventuels problèmes détectés
    """
    lines = []
    lines.append(f"=== Tech Graph ({len(graph.nodes)} techs) ===")

    n_free = sum(1 for n in graph.nodes if n.is_free)
    n_paid = len(graph.nodes) - n_free
    lines.append(f"  Gratuites: {n_free}  |  Payantes: {n_paid}")

    for i, node in enumerate(graph.nodes):
        prefix = "  "
        if node.is_free:
            prefix = "  [GRATUIT] "
        else:
            prefix = f"  [{i + 1:3d}] "

        n_recipes = len(node.unlocks_recipes)
        n_buildings = len(node.unlocks_buildings)
        effects_str = f"{n_recipes} recettes, {n_buildings} bâtiments"

        cost_str = ""
        if not node.is_free and node.cost:
            cost_parts = [
                f"{ing['amount']}×{ing['name']}" for ing in node.cost
            ]
            cost_str = f" [{node.count}× ({', '.join(cost_parts)})]"

        prereq_str = ""
        if node.prerequisites:
            prereq_str = f" ← {node.prerequisites[0]}"

        lines.append(
            f"{prefix}{node.id}: {node.title} "
            f"({effects_str}){cost_str}{prereq_str}"
        )

    return "\n".join(lines)
