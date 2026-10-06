# Nomenclature : le modèle de la seed et le rejoueur

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

Le rejoueur (`tool/replay/player.py`) agit comme un **audit externe** : il simule une seed finale sans rien inventer. Il exploite uniquement les champs écrits par `generate_seed` dans `seed`. Le vocabulaire doit être IDENTIQUE entre les deux composants : tout écart de terme serait interprété comme une erreur d'algorithme. Ce document définit la correspondance exacte des termes.

## 1. Table de correspondance seed → rejoueur

| Concept | Générateur (seed) | Rejoueur (consomme tel quel) |
|---|---|---|
| recette | `seed["recipes"][]` {`name`, `ingredients[{type,name,amount}]`, `results[…]`, `crafted_in`, `category`, `energy`} | même liste/objets ; `items_by_name` mappe **item sorti → recettes** |
| sortie | `results[].amount` (jamais appelé « sortie ») | `int(res.get("amount", 1))` — repris comme « sortie » dans le rejoueur et les discussions |
| atelier | `crafted_in` (recette sans clé = craft à la main) | `recipe.get("crafted_in")` |
| tech | `seed["technologies"][]` {`id`, `prerequisites`, `unit{ingredients[{name,amount}], count}`, `craft_trigger`, `effects[{type:"unlock-recipe", recipe}]`} | `technologies`, `unit`, `craft_trigger` (niveau tech) |
| item / fluide | `type: "item"` / `"fluid"` | `SLOT_ITEM` / `SLOT_FLUID` (`tool/common/db.py`) |
| raw / patch / lac | `seed["map"].patches[{resource, kind, count}]`, `.lakes[{resource}]` | idem ; patch item = ramassé à la main = stock FINI `item_patch_counts` |
| jalon tardif | `seed["late_raws"].startup` / `.gated[{name, tier}]` | `late_tier[(kind, name)] = tier` ; tier = index de la chaîne des packs |
| déclencheur prologue | `tech.craft_trigger` (item à fabriquer) | `_craft(trigger, 1)` avant les packs |

## 2. La règle de MAÎTRISE (propre au rejoueur)

Le joueur ne dispose pas d'une recette « infinie » tant qu'il ne l'a pas **prouvée** :

- Chaque recette doit être produite jusqu'à atteindre **10 × sa sortie**.
  (`_mastery_goal[name] = 10 × max(results[].amount)`, ex. sortie 2 → maîtrise à 20). L'**atelier** (`crafted_in`) est fabriqué à nouveau pour chaque passe et n'est jamais réutilisé.
- Une fois ce seuil atteint, la sortie est considérée comme **infinie** (plus besoin de la crafter pour l'utiliser) : elle est conservée dans `_craft`.
- La passe `_mastery_sweep` s'exécute **à chaque tech débloquée** pour tester les nouvelles recettes. Elle ne reteste que les recettes dont un ingrédient ou l'atelier vient de devenir sûr (**worklist inverse**, point fixe du rescan exhaustif : tout échec restaure l'état précédent sans laisser de trace).

Sorties du rapport (`ReplayReport`) :

- `mastered` / `mastered_tier` : items dont la recette a atteint 10×sortie, et l'échelon (`_current_tier`) de cette maîtrise.
- `never_masterable` : sorties de recettes débloquées mais jamais prouvées (le seuil de 10×sortie n'est jamais atteint en fin de partie). Cela mesure la « couverture » de jouabilité.
- `blocker{tech, kind, item}` : première technologie non recherchée (`kind ∈ {"prereqs","trigger","cost","lab"}`).
- `obtainable_items` / `obtainable_fluids` / `victory`.

## 3. Écarts de vocabulaire CONNUS (à ne pas re-chercher)

1. **« extracteur »** — deux sens coexistent. Le générateur écrit `seed["extractor_timing"]` (passe C3 : timing de DÉBLOCAGE dans l'arbre). Le rejoueur ignore ce champ et modélise la **capacité physique** (`_infer_extractors`, `data-updates.lua`) : un patch item est miné par toute foreuse opérationnelle, un patch fluide nécessite un pumpjack, un lac nécessite une pompe offshore. C'est un choix assumé.
2. **« maîtrise » / « infini »** — ces concepts appartiennent uniquement à l'audit. Le générateur ne les exporte jamais (pas de `had`, `mastered`, etc.).
3. **Nom de recette ≠ nom de l'item sorti** — par exemple, `randputf-stone-furnace` produit `stone-furnace`. Il ne faut jamais comparer un résultat de technologie (`effects.recipe`, `randputf-*`) à un item sans utiliser le mapping recette→sortie.
4. **`_current_tier` du rejoueur est un miroir** et non l'objet du générateur. Il réplique l'index de la chaîne des packs côté rejoueur (technologies recherchées et packs produisibles). La valeur de jalon d'une ressource brute est lue directement dans `late_raws.gated[].tier`.

## 4. Garantie

Toutes les données produites par le rejoueur utilisent les mêmes `id`/`name` que la seed. Il consomme exclusivement : `seed["recipes"]`, `seed["technologies"]`, `seed["map"]`, `seed["late_raws"]`, `seed["starter_kit"]`, `seed["wreck"]`, `seed["free_researches"]` et `seed["building_fluid_assignments"]`. Ces champs sont tous issus de `generate_seed`. Toute incohérence entre le rejoueur et le jeu provient d'une décision algorithmique du générateur, pas d'un problème de vocabulaire.
