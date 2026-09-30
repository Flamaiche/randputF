# Nomenclature : le modèle de la seed et le rejoueur

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

Le rejoueur (`tool/replay/player.py`) est un **audit externe** : il rejoue une
seed finale *sans rien inventer*. Il ne lit que les champs que
`generate_seed` écrit dans `seed` — le vocabulaire doit donc être IDENTIQUE
des deux côtés, sinon un écart de vocabulaire passe pour une erreur
d'algorithme (et inversement). Ce document fixe la correspondance exacte afin
qu'on parle toujours des mêmes choses.

## 1. Table de correspondance seed → rejoueur

| Concept | Générateur (seed) | Rejoueur (consomme tel quel) |
|---|---|---|
| recette | `seed["recipes"][]` {`name`, `ingredients[{type,name,amount}]`, `results[…]`, `crafted_in`, `category`, `energy`} | même liste/objets ; `items_by_name` mappe **item sorti → recettes** |
| sortie | `results[].amount` (jamais appelé « sortie ») | `int(res.get("amount", 1))` — reprisé « sortie » dans le rejoueur/discussion |
| atelier | `crafted_in` (recette sans clé = craft à la main) | `recipe.get("crafted_in")` |
| tech | `seed["technologies"][]` {`id`, `prerequisites`, `unit{ingredients[{name,amount}], count}`, `craft_trigger`, `effects[{type:"unlock-recipe", recipe}]`} | `technologies`, `unit`, `craft_trigger` (niveau tech) |
| item / fluide | `type: "item"` / `"fluid"` | `SLOT_ITEM` / `SLOT_FLUID` (`tool/common/db.py`) |
| raw / patch / lac | `seed["map"].patches[{resource, kind, count}]`, `.lakes[{resource}]` | idem ; patch item = ramassé à la main = stock FINI `item_patch_counts` |
| jalon tardif | `seed["late_raws"].startup` / `.gated[{name, tier}]` | `late_tier[(kind, name)] = tier` ; tier = index de la chaîne des packs |
| déclencheur prologue | `tech.craft_trigger` (item à fabriquer) | `_craft(trigger, 1)` avant les packs |

## 2. La règle de MAÎTRISE (propre au rejoueur)

Un joueur n'a pas la recette « infinie » tant qu'il ne l'a pas **prouvée** :

- chaque recette doit être fabriquée jusqu'à **10 × sa sortie**
  (`_mastery_goal[name] = 10 × max(results[].amount)`, ex. sortie 2 → maîtrise
  à 20). L'**atelier** (`crafted_in`) est recrafé à chaque passe (jamais
  réutilisé) ;
- une fois la quantité atteinte, la sortie devient **infinie** (plus besoin de
  la recrafter pour l'employer) : garde dans `_craft` ;
- la passe `_mastery_sweep` est lancée **à chaque tech débloquée** (« tester
  toutes les recettes nouvelles ») et ne reteste que les recettes dont un
  ingrédient/atelier vient de devenir sûr (**worklist inverse**, point fixe
  exact du rescan exhaustif : un échec restaure inv/had sans trace).

Sorties du rapport (`ReplayReport`) :

- `mastered` / `mastered_tier` : items dont la recette a atteint 10×sortie, et
  l'échelon (`_current_tier`) auquel la maîtrise a eu lieu ;
- `never_masterable` : sorties de recettes débloquées jamais prouvées (jamais
  10×sortie atteints en fin de partie) — la « couverture » de jouabilité ;
- `blocker{tech, kind, item}` : première tech non recherchée
  (`kind ∈ {"prereqs","trigger","cost","lab"}`) ;
- `obtainable_items` / `obtainable_fluids` / `victory`.

## 3. Écarts de vocabulaire CONNUS (à ne pas re-chercher)

1. **« extracteur »** — deux sens distincts : le générateur écrit
   `seed["extractor_timing"]` (passe C3 : timing de DÉBLOCAGE au fil de
   l'arbre) ; le rejoueur l'ignore volontairement et modélise la **capacité
   physique** (`_infer_extractors`, `data-updates.lua`) : un patch item est
   miné par toute foreuse obtenable et opérationnelle, un patch fluide exige un
   pumpjack, un lac se pompe par pompe offshore. Assumé.
2. **« maîtrise » / « infini »** — concepts de l'audit uniquement, jamais
   écrits par le générateur (il n'exporte pas `had`, `mastered`, etc.).
3. **Nom de recette ≠ nom de l'item sorti** — `randputf-stone-furnace` produit
   `stone-furnace`. Ne jamais comparer un résultat de tech (`effects.recipe`,
   `randputf-*`) à un item sans passer par le mapping recette→sortie.
4. **`_current_tier` du rejoueur est un miroir**, pas l'objet du générateur :
   il réplique l'index de chaîne des packs côté rejoueur (techs recherchées +
   packs produisibles) ; la valeur de jalon d'une raw elle, est lue
   directement dans `late_raws.gated[].tier`.

## 4. Garantie

Tout ce que le rejoueur sort parle des mêmes `id`/`name` que la seed : il ne
consomme que `seed["recipes"]`, `seed["technologies"]`, `seed["map"]`,
`seed["late_raws"]`, `seed["starter_kit"]`, `seed["wreck"]`,
`seed["free_researches"]`, `seed["building_fluid_assignments"]` — tous générés
par `generate_seed`. Une incohérence rejoueur↔jeu est donc une décision
d'algorithme du générateur, pas un malentendu de vocabulaire.