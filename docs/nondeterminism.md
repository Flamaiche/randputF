# Non-déterminisme du pipeline — Inventaire complet

## Problème

Le pipeline `tool generate` n'est **pas déterministe** : deux runs avec la même seed
produisent des `seed.lua` différents. Les `rng.choice()`/`rng.sample()`/`rng.shuffle()`
sont appelés sur des listes issues de `dict`/`set` dont l'ordre d'itération varie entre
les runs Python.

## Solution envisagée

Chaque point de choix non-déterministe est associé à une **pool de possibilités finie**.
La seed fournit un index/clé pour choisir dans cette pool → totally déterministe,
et chaque seed = une combinaison unique de choix.

---

## 1. Choix d'items/resource patches (Phase 1 — map_patches.py)

### 1a. Items solides tirés en patches
- **Fichier** : `tool/generator/map_patches.py:77`
- **Code** : `rng.sample(item_candidates, n_items)`
- **Pool** : `db.beltable_items()` = **209 items** (tous les items beltables non-tool)
- **Ce que ça fait** : choisit N items solides qui seront posés en carte (gisements)
- **Seed** : `n_items` = nombre tiré (1-3), puis `rng.sample()` choisit lesquels
- **Impact** : détermine quels items sont miniables en carte (pierre, fer, cuivre, etc.)

### 1b. Fluides tirés en patches
- **Fichier** : `tool/generator/map_patches.py:79`
- **Code** : `rng.sample(fluid_candidates, n_fluids)`
- **Pool** : `db.pipable_fluids()` = **8 fluids** (water, crude-oil, heavy-oil, light-oil, lubricant, steam, petroleum-gas, sulfuric-acid)
- **Ce que ça fait** : choisit N fluids qui seront en carte (gisements fluides)
- **Seed** : identique
- **Impact** : détermine quels fluids sont disponibles via pumpjack

### 1c. Shuffle final des patches
- **Fichier** : `tool/generator/map_patches.py:82`
- **Code** : `rng.shuffle(patches)`
- **Pool** : liste de N items + M fluids (quelques dizaines max)
- **Impact** : l'ordre des patches dans la seed (post-shuffle)
- **Note** : secondaire — l'ordre des patches n'affecte pas le gameplay

---

## 2. Chaîne initiale (Phase 2 — starter_chain.py)

### 2a. Extracteur pour ressource
- **Fichier** : `tool/generator/starter_chain.py:177`
- **Code** : `extractor = rng.choice(candidates)`
- **Pool** : `_extractors_for_resource(db, kind, name)` — taille variable :
  - `kind=SLOT_FLUID, name=water` → **1** (offshore-pump)
  - `kind=SLOT_FLUID, name!=water` → **1-2** (offshore-pump si no_electric, sinon pumpjack)
  - `kind=SLOT_ITEM` → **2** (burner-mining-drill, electric-mining-drill)
- **Ce que ça fait** : choisit l'extracteur pour chaque ressource de patch
- **Impact** : détermine quels bâtiments extracteurs seront disponibles au démarrage
- **Exemple concret** : si heavy-oil est un patch → pumpjack choisi → son craft doit être accessible

### 2b. Transformateur (fabricateur)
- **Fichier** : `tool/generator/starter_chain.py:238`
- **Code** : `chosen = rng.choice(transformers)`
- **Pool** : `db.buildings_of_type("transformer")` filtré starters = **~5-8** (stone-furnace, steel-furnace, assembling-machine-1/2, etc.)
- **Ce que ça fait** : choisit le bâtiment de transformation principal (four, assembleur…)
- **Impact** : détermine la catégorie de craft (smelting, crafting, etc.)

### 2c. Bâtiment de recherche (lab)
- **Fichier** : `tool/generator/starter_chain.py:266`
- **Code** : `item = rng.choice(candidates)`
- **Pool** : items avec `place_result` = building type "research" = **1** (lab)
- **Impact** : nul (pool=1)

### 2d. Premier science pack
- **Fichier** : `tool/generator/starter_chain.py:296`
- **Code** : `item = rng.choice(packs)`
- **Pool** : items `is_science_pack` = **7** (automation, logistic, military, chemical, production, utility, space)
- **Ce que ça fait** : choisit le premier pack craftable (gratuit au démarrage)
- **Impact** : détermine quelle branche de science est ouverte en premier

### 2e. Item kit cible (armes/munitions)
- **Fichier** : `tool/generator/starter_chain.py:340`
- **Code** : `chosen = rng.choice(candidates)`
- **Pool** : items matchant patterns (weapon/gun/armor) = **~10-15**
- **Ce que ça fait** : choisit l'arme principale du kit de départ
- **Impact** : détermine l'arme que le joueur a au spawn

### 2f. Gun pour l'arme
- **Fichier** : `tool/generator/starter_chain.py:349`
- **Code** : `gun = rng.choice(guns)`
- **Pool** : items `is_handheld_gun` = **6** (pistol, submachine-gun, shotgun, combat-shotgun, rocket-launcher, flamethrower)
- **Ce que ça fait** : choisit le type d'arme à munitions
- **Impact** : détermine quel gun est craftable

### 2g. Munitions alignées
- **Fichier** : `tool/generator/starter_chain.py:355`
- **Code** : `ammo = rng.choice(matching or ammos)`
- **Pool** : items `is_ammo` = **14** (bullet, shotgun-shell, rocket, flask, etc.)
- **Ce que ça fait** : choisit les munitions alignées avec le gun
- **Impact** : détermine quel type de munition est craftable

---

## 3. Recettes et ateliers (recipes.py)

### 3a. Atelier pour recette (whitelist)
- **Fichier** : `tool/generator/recipes.py:445`
- **Code** : `rng.choice(candidates)`
- **Pool** : `db.buildings.values()` filtré whitelist = variable (souvent 1-5)
- **Impact** : choix du bâtiment fabricant pour une recette

### 3b. Atelier pour recette (déjà unlocké)
- **Fichier** : `tool/generator/recipes.py:453`
- **Code** : `rng.choice(candidates)`
- **Pool** : `db.buildings.values()` filtré `state.unlocked_buildings` = variable
- **Impact** : quel atelier libre fabrique la recette

### 3c. Atelier pour recette (tout bâtiment)
- **Fichier** : `tool/generator/recipes.py:462`
- **Code** : `rng.choice(candidates)`
- **Pool** : `db.buildings.values()` hors exclusions = variable (~10-30)
- **Impact** : dernier repli pour choisir un atelier

### 3d. Combustible pour bâtiment burner
- **Fichier** : `tool/generator/recipes.py:519`
- **Code** : `rng.choice(fuel_items)`
- **Pool** : `db.fuel_items()` hors rocket-chain = **~5** (wood, coal, solid-fuel, rocket-fuel, nuclear-fuel)
- **Impact** : détermine quel combustible est assigné aux fours/brûleurs

---

## 4. Phase récursive (recursive_phase.py)

### 4a. Couverture d'items
- **Fichier** : `tool/generator/recursive_phase.py:222`
- **Code** : `rng.shuffle(items)`
- **Pool** : `db.beltable_items()` = **209 items**
- **Ce que ça fait** : mélange l'ordre de couverture (quels items ont des recettes)
- **Impact** : détermine l'ordre de création des recettes d'extension

### 4b. Munitions manquantes
- **Fichier** : `tool/generator/recursive_phase.py:301`
- **Code** : `rng.shuffle(missing)`
- **Pool** : items `is_ammo` manquants = variable
- **Impact** : ordre de création des recettes de munitions

### 4c. Bâtiment distribution (transporteur)
- **Fichier** : `tool/generator/recursive_phase.py:374`
- **Code** : `rng.choice(candidates)`
- **Pool** : `db.buildings_of_type("distribution")` = **5** (4 power poles + beacon)
- **Impact** : choisit le transporteur/connexions

### 4d. Bâtiment par catégorie
- **Fichier** : `tool/generator/recursive_phase.py:459`
- **Code** : `rng.choice(candidates)`
- **Pool** : `db.buildings_of_type(category)` = variable par catégorie
- **Impact** : choisit quel bâtiment fabrique une recette d'un type donné

### 4e. Gun pour arme montée
- **Fichier** : `tool/generator/recursive_phase.py:466`
- **Code** : `rng.choice(candidates)`
- **Pool** : items `is_handheld_gun` = **6**
- **Impact** : arme assignée aux véhicules (tank, spidertron, etc.)

### 4f. Science pack pour recherche
- **Fichier** : `tool/generator/recursive_phase.py:469`
- **Code** : `rng.choice(candidates)`
- **Pool** : items `is_science_pack` = **7**
- **Impact** : quel pack est consommé par une tech

### 4g. Item obtenu pour ingrédient
- **Fichier** : `tool/generator/recursive_phase.py:620`
- **Code** : `rng.choice(candidates)`
- **Pool** : `state.obtained_items` (set) = variable (quelques dizaines)
- **Impact** : choisit un item déjà obtainable comme ingrédient

### 4h. Fluide obtenu pour ingrédient
- **Fichier** : `tool/generator/recursive_phase.py:620`
- **Code** : `rng.choice(candidates)`
- **Pool** : `state.obtained_fluids` (set) = variable (0-8)
- **Impact** : choisit un fluide déjà obtainable comme ingrédient

---

## 5. Électricité (electricity.py)

### 5a. Pylône
- **Fichier** : `tool/generator/electricity.py` (`_pick_pole`)
- **Code** : `rng.choice(poles)`
- **Pool** : bâtiments taggés `is_distribution` = **5**
- **Impact** : type de pylône généré

### 5b. Générateur
- **Fichier** : `tool/generator/electricity.py` (`_pick_functional_generator`)
- **Code** : shuffle + test des générateurs candidats (`_candidate_generators`)
- **Pool** : bâtiments taggés `is_generator` + `produces_electricity` = **4**
- **Impact** : type de générateur qui amorce le réseau (C1)

### 5c. Fluide du générateur à vapeur — ⚠️ point non déterministe corrigé
- **Fichier** : `tool/generator/electricity.py` (`_unlock_generator`)
- **Code** (avant fix) : `available = [f for f in lake_resources if ...]` puis `rng.choice(available)`
- **Pool** : `lake_resources` (set) = fluides des lacs (0-8)
- **Impact** : quel fluide de lac le premier steam-engine/steam-turbine consomme
- **Risque** : l'itération d'un **set** alimente un `rng.choice` → ordre variable
  entre processus (`PYTHONHASHSEED`) → le `input` du générateur changeait
  (`heavy-oil` vs `water` sur la même seed).
- **Fix** : `sorted(lake_resources)` avant la dérivation de la liste.
- **Même motif ailleurs** : `building_fluids.py` (`assign_building_fluids`) faisait
  `available = list(lake_resources)` → corrigé avec `sorted(lake_resources)`.
- **Garde** : `tests/test_determinism.py` régénère la seed en sous-processus
  sous `PYTHONHASHSEED` 0/1 et compare `seed.json` octet par octet.

### 5d. Claim des ateliers débloqués « sur le tas » (claim anti-orpheline)
- **Fichier** : `tool/generator/recursive_phase.py:854`
- **Code** : `for name in state.unlocked_buildings - buildings_before:`
  `step_buildings.append(name)` — itération d'un **set** qui alimente
  `step["unlocks_buildings"]`.
- **Impact** : l'ordre des effets `unlock-recipe` d'une tech varie entre
  processus (`PYTHONHASHSEED`) → le `seed.json` diffère au byte près pour
  certaines seeds.
- **Découvert sur** : seed 1299 — tech `randputf-combat-submachine-gun`,
  recettes de bâtiments `chemical-plant`/`oil-refinery`/`assembling-machine-1`/
  `assembling-machine-3` en rotation selon le hash. **Pré-existant** : révélé
  en baseline comme en gaté.
- **Fix** : `sorted(state.unlocked_buildings - buildings_before)`.
- **Preuve** : `seed.json` octet-pour-octet identique sous `PYTHONHASHSEED`
  0/1/2 pour seeds 37/412/1299, baseline et gatées.
- **Même motif ailleurs** : `_export_late_raws` (`pipeline.py`) itère déjà
  trié (`sorted(late_plan.gated)`, `sorted(late_plan.startup)`).

---

## 6. Lacs (lakes.py)

### 6a. Fluide du lac
- **Fichier** : `tool/generator/lakes.py:63`
- **Code** : `rng.choice(candidates)`
- **Pool** : `db.pipable_fluids()` = **8** fluids
- **Ce que ça fait** : choisit quel fluide sera dans un lac
- **Impact** : détermine quel fluide est pompable via offshore-pump sur les lacs

---

## Récapitulatif des pools

| Pool | Taille | Utilisé dans |
|------|--------|-------------|
| Items beltables | 209 | patches (1a), couverture (4a) |
| Fluids pipables | 8 | patches (1b), lacs (7a) |
| Extractors water | 1 | choix fixe |
| Extractors ground | 2 | choix extracteur sol (2a) |
| Extractors fluid | 1-2 | choix extracteur fluide (2a) |
| Transformers | ~5-8 | fabricateur starter (2b) |
| Generators | 5 | électricité (5b, 6a) |
| Distribution | 5 | pylônes (5a, 4c) |
| Research | 1 | lab fixe |
| Fuel items | ~5 | combustible (3d, 6b, 6c) |
| Science packs | 7 | pack starter (2d), tech (4f) |
| Handheld guns | 6 | arme kit (2f), véhicule (4e) |
| Ammo | 14 | munitions (2g, 4b) |
| Items obtenus (set) | variable | ingrédients (4g, 6d) |
| Fluids obtenus (set) | variable | ingrédients (4h) |

---

## Stratégie de correction

**Option A — Tri alphabétique** (rapide, déterministe mais rigide) :
Chaque liste est triée par `name` avant `rng.choice/sample`. → 1 seule seed possible.

**Option B — Index dans la seed** (flexible, déterministe) :
Chaque choix est un paramètre de seed. Ex : `"choices": {"patch_item_0": 42, "patch_item_1": 17, ...}`.
Le RNG n'est plus utilisé pour ces choix → la seed contrôle tout.
Avec N choix de pools de taille P, on a P^N combinaisons possibles.

**Recommandation** : Option B. La seed.json gagne un champ `"choices"` avec un index
par pool. Le code utilise `candidates[seed.choices["key"] % len(candidates)]` au lieu
de `rng.choice(candidates)`. C'est totalement déterministe, portable, et le nombre
de seeds possibles est astronomique (209^2 × 8^2 × 5^3 × ... = 10^15+).

## ✅ Résolution (diagnostic concluant)

La cause racine **finalement identifiée** ne venait pas des pools de choix (rares),
mais d'une **itération de frozenset ordonnant des recettes** dans la chaîne fusée :

- `tool/common/db.py:29` : `ROCKET_CHAIN = frozenset({"processing-unit", "low-density-structure", "rocket-fuel"})`.
- `tool/generator/endgame_phase.py:47` : `targets = list(ROCKET_CHAIN)` → ordre non déterministe
  entre process (PYTHONHASHSEED aléatoire) → les 3 recettes de `rocket-part`
  (dont `processing-unit` et `rocket-fuel`) étaient générées dans un ordre variable
  dans `state.recipes`, décalant le flot RNG postérieur et inversant 2 recettes du seed.

**Comment c'était prouvé** (instrumentation `pipeline.py`) :
- `all_tech_steps` **identique** entre 2 process,
- état RNG avant la récursion **identique**,
- état RNG avant `build_linear_tech_tree` **identique**,
- mais `md5` de l'ordre des recettes du seed **différent** → la divergence était
  *purement* dans l'ordre d'insertion des recettes, pas dans le choix RNG.
- Diff pointu : seuls `randputf-processing-unit` ↔ `randputf-rocket-fuel` échangés.

**Fix** : `targets = sorted(ROCKET_CHAIN)` (`endgame_phase.py:47`). Après correction,
2 runs `tool generate --seed 5` produisent des `seed.lua` et `seed.json`
**octet-pour-octet identiques** (vérifié sur les 10 fichiers du mod).
La suite de tests passe toujours (elle compte aujourd'hui 722 tests ; à
l'époque de cette correction, elle en comptait 71).

Après les correctifs (chaîne fusée, §5c, §5d), les itérations de
`set`/`frozenset` restantes (ex. `map_patches.py:101` `hero`, `recipes.py:522`)
ne servent QUE des tests d'appartenance (`in`/`not in`), déterministes —
aucune ne trie une séquence exportée.

**Régression** : `tests/test_determinism.py` régénère les seeds **1337 et 1299**
en sous-processus sous `PYTHONHASHSEED` 0/1 et compare `seed.json` octet par
octet — l'ordre des effets de la tech `randputf-combat-submachine-gun`
(correctif §5d) est couvert par ce garde.

---

## 7. Dépendance à l'ordre d'un même processus (multi-seeds, sweeps) — corrigé

Problème distinct du hash-order : enchaîner plusieurs seeds dans le **même
processus** (sweeps, boucles de tests) produisait des seeds différentes selon
leur position.

- **Cause racine** : la passe B du jalonnement (§16 `late_raws`) faisait
  `cfg.setdefault("starter", {})["deferred"] = sorted(map(list, plan.gated))`
  — le config du caller est partagé par **copie superficielle** entre seeds
  (`dict(config)` ne copie pas le sous-dict `starter`) → `deferred` était muté
  **en place** dans la config partagée et n'était ré-écrasé que par les seeds
  qui rejouent la passe B. Le retour anticipé « gating inerte » (§5 des
  DEVIANCES) rendait alors une seed inerte dépendante du jalon `deferred` laissé
  par la seed non-inerte précédente.
- **Découvert sur** : seed 1269 — défaite en gaté (tech 21, `light-oil` du pack
  `automation-science-pack`) quand on la générait après ~40 autres seeds dans le
  même process, victoire 101/101 en process vierge. Pré-existant mais amplifié
  par le shortcut inerte (avant, chaque seed rejouait la passe B et ré-écrasait
  `deferred` avec SON plan).
- **Fix** : copie défensive `cfg = dict(cfg); cfg["starter"] = dict(starter)` au
  lieu de muter le dict partagé (`pipeline.py`, passe B).
- **Preuve** : seed 1269 byte-identique (hash `c8c55ecf05e4`) en process vierge,
  après 1 seed, et après **1400 seeds cumulées** — victoire 101/101 dans tous
  les cas ; `BASE["starter"]` reste intact après génération. Sweep gaté **0-2000
  re-joué sous le code corrigé : 2000 victoires / 0 défaite** (contigu).
- **Garde** : `test_seed_1757_gating_inerte_victoire_comme_baseline` et le test
  d'ordre (seed 1269 après cumul) couvrent ce mode ; les sweeps s'exécutent
  maintenant dans des conditions équivalentes au process vierge appliqué une
  fois par seed.
