# Nomenclature : le modèle de la seed et le rejoueur

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

Le rejoueur (`tool/replay/player.py`) réalise un audit externe : il simule l'exécution d'une seed finale sans aucun ajout. Il s'appuie exclusivement sur les données générées par `generate_seed` au sein de `seed`. La terminologie doit être strictement identique entre les deux briques : la moindre divergence passerait pour une anomalie algorithmique. Ce document fixe la correspondance exacte du vocabulaire.

## 1. Table de correspondance seed → rejoueur

| Concept | Générateur (seed) | Rejoueur (consomme tel quel) |
|---|---|---|
| recette | `seed["recipes"][]` {`name`, `ingredients[{type,name,amount}]`, `results[…]`, `crafted_in`, `category`, `energy`} | Même liste et objets ; `items_by_name` associe chaque item sorti à ses recettes |
| sortie | `results[].amount` (jamais désigné ainsi côté générateur) | `int(res.get("amount", 1))` — désigné sous le terme « sortie » dans le rejoueur et les échanges |
| atelier | `crafted_in` (absence de clé = fabrication à la main) | `recipe.get("crafted_in")` |
| tech | `seed["technologies"][]` {`id`, `prerequisites`, `unit{ingredients[{name,amount}], count}`, [optionnel: `craft_trigger`], `effects[{type:"unlock-recipe", recipe}]`} | `technologies`, `unit`, `craft_trigger` (niveau tech) |
| item / fluide | `type: "item"` / `"fluid"` | `SLOT_ITEM` / `SLOT_FLUID` (`tool/common/db.py`) |
| raw / patch / lac | `seed["map"].patches[{resource, kind, count}]`, `.lakes[{resource}]` | Idem ; un patch d'item se ramasse à la main et constitue un stock fini dans `item_patch_counts` |
| jalon tardif | `seed["late_raws"].startup` / `.gated` (dict `name` → {`kind`, `tier`}) | `late_tier[(kind, name)] = tier` ; tier = index de la chaîne des packs |
| déclencheur prologue | `tech.craft_trigger` (item à fabriquer) | `_craft(trigger, 1)` exécuté avant la chaîne des packs |

## 2. La règle de MAÎTRISE (propre au rejoueur)

Une recette ne devient accessible de manière infinie qu'après avoir été dûment **prouvée** :

- Toute recette doit être produite jusqu'à atteindre **10 × sa sortie** (`_mastery_goal[name] = 10 × max(results[].amount)`, par exemple une sortie de 2 exige une maîtrise à 20). L'**atelier** (`crafted_in`) est reconstruit à chaque tentative et n'est jamais conservé.
- Ce seuil franchi, la sortie devient **infinie** et n'a plus besoin d'être fabriquée : elle rejoint `_craft`.
- La passe `_mastery_sweep` intervient **à chaque technologie débloquée** afin de vérifier les nouvelles recettes. Seules sont réévaluées les recettes dont un ingrédient ou l'atelier vient d'être validé (**worklist inverse**, point fixe d'un réexamen complet : en cas d'échec, l'état antérieur est rétabli sans conserver la moindre trace).

Résultats du rapport (`ReplayReport`) :

- `mastered` / `mastered_tier` : items dont la recette a atteint le seuil de 10×sortie, accompagnés du palier (`_current_tier`) correspondant.
- `never_masterable` : sorties de recettes débloquées qui restent non prouvées en fin de partie (seuil de 10×sortie jamais atteint). Cet indicateur évalue la couverture de la jouabilité.
- `blocker{tech, kind, item}` : toute première technologie restée non recherchée (`kind ∈ {"prereqs","trigger","cost","lab"}`).
- `obtainable_items` / `obtainable_fluids` / `victory`.

## 3. Écarts de vocabulaire CONNUS (à ne pas re-chercher)

1. **« extracteur »** — deux notions distinctes se côtoient. Le générateur enregistre `seed["extractor_timing"]` (passe C3 : timing de déblocage dans l'arbre). De son côté, le rejoueur fait abstraction de cette donnée pour modéliser la **capacité physique** (`_infer_extractors`, `data-updates.lua`) : n'importe quelle foreuse en service extrait un patch item, un patch fluide exige un pumpjack, tandis qu'un lac requiert une pompe offshore. Cette divergence est délibérée.
2. **« maîtrise » / « infini »** — ces notions relèvent exclusivement du processus d'audit. Le générateur ne les transmet jamais (pas de champ `had`, `mastered`, etc.).
3. **Nom de recette ≠ nom de l'item sorti** — à titre d'exemple, `randputf-stone-furnace` fabrique `stone-furnace`. Un résultat de technologie (`effects.recipe`, `randputf-*`) ne doit jamais être comparé directement à un item sans passer par la correspondance recette→sortie.
4. **`_current_tier` du rejoueur est un miroir** et non l'objet du générateur. Il reproduit l'index de la chaîne des packs pour le rejoueur (technologies recherchées et packs produisibles). Le jalon d'une ressource brute se lit directement dans `late_raws.gated[name].tier`.

## 4. Garantie

L'ensemble des données générées par le rejoueur réutilise les identifiants `id` et `name` définis dans la seed. Il consomme de manière exclusive : `seed["recipes"]`, `seed["technologies"]`, `seed["map"]`, `seed["late_raws"]`, `seed["starter_kit"]`, `seed["wreck"]`, `seed["free_researches"]` et `seed["building_fluid_assignments"]`. L'ensemble de ces champs découle directement de `generate_seed`. Une discordance entre le rejoueur et le comportement en jeu s'explique toujours par un choix d'algorithme du générateur, jamais par un décalage de vocabulaire.
