# Runtime Lua — ce que le mod fait de la seed

Ce document détaille, **fichier par fichier** et selon l'ordre d'exécution réel de Factorio, le traitement de la seed générée par l'outil Python dans le mod randputF : clés lues, actions exécutées, chronologie et éléments **non** raccordés.

Chaque référence `fichier:ligne` s'appuie directement sur le code.

---

## 1. Les cinq fichiers Lua

| Fichier | Lignes | Phase Factorio | Rôle |
|---------|--------|----------------|------|
| `mod/data.lua` | 241 | `data` | Recettes, technologies, sous-groupe d'inventaire |
| `mod/data-updates.lua` | 931 | `data-updates` | Ressources au sol, véhicules armés, fluides génériques, tuiles de lac |
| `mod/data-final-fixes.lua` | 101 | `data-final-fixes` | Neutralisation du vanilla, enregistrement des autoplace controls |
| `mod/control.lua` | 927 | runtime | Kit de départ, loot du crash, purge d'eau, lacs, gisements |
| `exporter/control.lua` | 806 | runtime (mod compagnon) | Dump `vanilla_dump.json` pour le tool Python |

Le fichier `mod/seed/seed.lua` (plusieurs milliers de lignes) ne constitue pas du code du mod. Il représente le miroir produit à partir de `seed.json` (`tool/exporters/mod_seed.py:63-65`). Sa documentation figure dans [`seed.md`](seed.md).

## 2. Le contrat `seed` → Lua

Les quatre fichiers du mod chargent la seed **de la même manière** :

```lua
local seed = {}
do
  local ok, loaded = pcall(require, "seed.seed")
  if ok and type(loaded) == "table" then
    seed = loaded
  end
end
```

`mod/data.lua:1-7`, `mod/data-updates.lua:5-11`, `mod/data-final-fixes.lua:3-9`, `mod/control.lua:7-13`.

| Propriété | Conséquence |
|-----------|-------------|
| `pcall` + `type == "table"` | Un mod installé **sans** seed ne casse pas la data-stage : le mod se charge, il ne randomise rien |
| Miroir Lua et non JSON | Aucun parseur JSON en data-stage ; le coût est un fichier de 8 000 lignes lu nativement (`tool/exporters/mod_seed.py:5-7`) |
| `require` et non `dofile` | Le résultat est **mémoïsé** par Lua : les quatre fichiers du mod voient la même table |
| `or {}` sur chaque accès | `seed.pools or {}`, `(seed.map or {}).patches or {}`… : un champ manquant ne lève jamais |

**Convention de préfixe.** Deux casses coexistent intentionnellement :

| Préfixe | Sens | Exemples |
|---------|------|----------|
| `randputf-` | Objets **créés ou modifiés** par le mod | `randputf-steel-furnace`, `randputf-minerai-iron-ore`, `randputf-lac-water` |
| `randputF:` | Préfixe de **flux RNG** Python (jamais visible en Lua) | `randputF:wells:` — voir [`nondeterminism.md`](nondeterminism.md) §2 |

L'exporter identifie le second préfixe via une constante dédiée : `_RANDPUTF_PREFIX = "randputf-"` en Python (`tool/parsers/vanilla.py:61`) et `RANDPUTF_PREFIX = "randputf-"` en Lua (`exporter/control.lua:773`). **Toute modification de l'un doit être répercutée dans l'autre** — comme rappelé en commentaire (`exporter/control.lua:770-772`).

## 3. `mod/data.lua` — recettes et technologies

### 3.1 Sous-groupe d'inventaire

`mod/data.lua:9-16` crée le `item-subgroup` `randputf` au sein de `intermediate-products`, avec `order = "z-randputf"`. Il accueille l'ensemble des produits dépourvus de sous-groupe hérité.

### 3.2 Recherche de prototypes

Deux fonctions d'aide interviennent à travers tout le fichier :

| Helper | Ligne | Rôle |
|---------|-------|------|
| `find_item_proto(name)` | `mod/data.lua:30-40` | Cherche `data.raw.item` puis les 16 tables item-like (`ITEM_LIKE_TYPES`, `mod/data.lua:21-26`) : `gun`, `tool`, `capsule`, `ammo`, `armor`, `module`, `blueprint`, `rail-planner`… |
| `find_entity_proto(name)` | `mod/data.lua:43-51` | Parcourt **toutes** les tables `data.raw` |

L'usage de `find_item_proto` s'impose car armes et munitions disposent de leur propre table. Une recherche limitée à `data.raw.item` les ignorerait.

### 3.3 Construction des recettes

Le fichier boucle sur `seed.recipes` (`mod/data.lua:53-120`), à raison d'une recette par entrée :

| Action | Ligne | Détail |
|--------|-------|--------|
| Ingrédients | 52-59 | `type` par défaut `item` |
| Résultats | 60-69 | Le **premier** résultat devient `main_product` |
| Sous-groupe | 71-83 | Item → sous-groupe et `order` hérités du proto produit ; fluide → sous-groupe `fluid` |
| Nom localisé | 88 | `randputf-` retiré, `-` → espaces |
| `enabled` | 89 | `recipe_seed.enabled == true` |
| `energy_required` | 92 | `recipe_seed.energy or 0.5` |
| `category` | 96-98 | Posée **seulement** si la catégorie existe déjà dans `data.raw["recipe-category"]` |
| `crafted_in` | 100-116 | Restreint la recette au bâtiment précis (2.0) |
| Injection de catégorie | 102-115 | Si le bâtiment n'a pas la catégorie nécessaire, elle est **ajoutée à son prototype** |

> Le paramètre `enabled` vaut `false` par défaut. L'outil Python n'émet **jamais** la clé `enabled` sur une recette (aucune occurrence dans `tool/generator/*.py`). Toutes les recettes apparaissent désactivées à la création, puis s'activent au runtime via les technologies — voir §6.2.

L'ajout de `crafting_categories` sur un prototype vanilla constitue une **mutation directe** de `data.raw`. Cette opération est valide en data-stage et offre le seul moyen d'héberger une recette sur un bâtiment dépourvu de catégorie.

### 3.4 Construction des technologies

`tech_template = data.raw.technology["automation"]` (`mod/data.lua:122`) sert de structure de base. Chaque technologie effectue un `table.deepcopy` de ce prototype (`mod/data.lua:189`), puis :

| Action | Ligne | Détail |
|--------|-------|--------|
| Identité | 183-184 | `name = tech_seed.id`, `localised_name` de la seed |
| Prérequis | 185-188 | Table reconstruite vide puis remplie (jamais héritée du template) |
| `unit` | 189-197 | `{count, time or 30, ingredients}` ; les ingrédients ne gardent que `name` et `amount` |
| `research_trigger` | 199-211 | Si `craft_trigger` présent : `unit` devient `{1, 1, {}}` et un `craft-item` prend le relais |
| `effects` | 212-215 | Table vide puis remplie — jamais les effets du template |
| Icônes | 216-221 | Grille 2×2 des produits débloqués |
| Nettoyage | 222-224 | `upgrade = false`, `level = nil`, `max_level = nil` |

Le bloc `research_trigger` gère la mécanique de **hand-craft**. Une technologie de prologue réclame nominalement 1 seconde et 0 ingrédient sans s'auto-compléter : elle s'achève en fabriquant l'item déclencheur. L'émission des déclencheurs provient de `tool/generator/relay_phase.py:188-189` avec `craft_trigger_count = round(2 ** (n + 1/4))`.

### 3.5 Icônes de technologie

| Fonction | Ligne | Rôle |
|----------|-------|------|
| `ICON_OUTPUT_SIZE = 64` | 123 | Taille d'affichage par icône sur un canvas 128 |
| `icon_layouts` | 124-129 | Positions pour 1, 2, 3 et 4 icônes |
| `proto_icon` | 131-140 | `icons[1]` (2.0) ou `icon` (1.x) |
| `tech_icons_for_effects` | 142-179 | Parcourt les effets `unlock-recipe`, prend le premier proto résolvable, **plafonne à 4** |

### 3.6 Bloc dormant

`mod/data.lua:235-241` désactiverait **toutes** les technologies vanilla si `seed.meta.disable_vanilla_techs` valait vrai. **Cette clé n'est jamais émise par le tool** (aucune occurrence dans `tool/` ni dans `mod/seed/seed.json`), rendant ce bloc inerte. La désactivation effective du vanilla s'exécute dans `data-final-fixes.lua` (§5).

## 4. `mod/data-updates.lua` — neuf blocs

### 4.1 Réarmement des véhicules

`mod/data-updates.lua:17-82`, basé sur `seed.vehicle_armament`.

| Action | Ligne | Détail |
|--------|-------|--------|
| Lecture du scaling | 18-20 | `base_size` (défaut 2.0), `scale` (défaut 0.4) |
| `entity_size` | 24-30 | Extent maximal de la `selection_box` (tank 2.6, spidertron 2, artillery-wagon 6) |
| `scaled_range` | 34-38 | `range × (1 + max(taille − base, 0) × scale)`, arrondi au plus proche (`math.floor(x + 0.5)`) |
| `clone_gun_for` | 42-56 | **Clone** de `data.raw.gun[gun]` nommé `randputf-<véhicule>-<arme>`, portée rescalée |
| Application | 59-82 | `car` et `spider-vehicle` prennent une **liste** `guns` ; `artillery-wagon` prend un `gun` unique |

La **pool** des armes provient de la seed (`seed.vehicle_armament`, `mod/data-updates.lua:58`), sans valeur en dur — `pools.vehicle_weapons` est exporté mais **jamais lu en Lua** (§9). Le clone permet de définir une portée propre. L'arme d'origine subsiste mais ne reste plus assignée au véhicule.

### 4.2 Gabarits de ressource

`mod/data-updates.lua:84-96` recherche un prototype `resource` appartenant aux catégories `basic-solid` puis `basic-fluid` en guise de gabarits. À défaut, le code se rabat sur `iron-ore` et `crude-oil`. L'ensemble des patchs dérive de clones de ces deux modèles.

### 4.3 Entités de ressource : une par ressource unique

`mod/data-updates.lua:163-273`. Les patchs subissent un dédoublonnage par nom d'entité (`mod/data-updates.lua:136-144`) : deux patchs associés au même item partagent une entité unique.

| Constante | Ligne | Valeur |
|-----------|-------|--------|
| `seed_hash` | 153-160 | Hash polynôme `h = h*131 + octet (mod 2^31−1)` — les seeds > 2^53 ne cassent pas Lua |
| `map_seed_hash` | 161 | Dérivé de `seed.meta.seed` |

Pour chaque ressource unique :

| Action | Ligne | Détail |
|--------|-------|--------|
| `autoplace-control` | 171-178 | `randputf-ctl-<i>` (index = **rang de première apparition**), catégorie `resource` |
| Initialisation du patch set | 179 | `resource_autoplace.initialize_patch_set` |
| `minable` | 190-193 / 207-210 | Fluide → 1 unité de fluide ; item → 1 unité d'item |
| `autoplace` | 197-205 / 213-221 | **`base_density = 0`** : le moteur ne pose rien, le runtime pose tout |
| `seed1` | 204 / 221 | `map_seed_hash * 1000 + i` — propre à chaque ressource |
| Icône | 224-235 | Icône du fluide ou de l'item ; **warn** si un patch item n'a pas d'icône |
| `stages` | 238-249 | Minerais solides : 4 positions, échelle 0.25–0.45 — l'icône de l'item **sur le sol** |
| `map_color` | 250-254 | Dérivé du hash par composante : `((map_seed_hash × K + i × J) mod 101 + 30) / 255`, avec (K, J) = (131, 47) pour `r`, (197, 83) pour `g`, (251, 127) pour `b` — composantes 30..130 |

L'affectation `base_density = 0` forme la pièce maîtresse du modèle : **les gisements sont posés au runtime**, garantissant le placement exact de `count` blocs (§6.8).

Les deux appels `data:extend` sont encadrés par un `pcall` et tracent leur décompte (`mod/data-updates.lua:259-273`), évitant qu'une table invalide ne bloque la data-stage.

### 4.4 Lacs : couleur

`mod/data-updates.lua:280-410`, s'applique uniquement si `seed.map.lakes` contient des données.

La couleur de base du fluide (`base_color`) apparaît presque toujours trop sombre ou trop saturée sur la minimap. L'ajustement s'effectue via cette séquence :

| Étape | Ligne | Rôle |
|-------|-------|------|
| `lake_fallbacks` | 282-288 | 5 teintes de secours pour les fluides sans chromatisme |
| `hue_allowed` | 303-325 | Fenêtres de teinte acceptables : jaune/orange 12–62°, vert 70–150°, cyan/bleu 165–235°. **Exclut rouge vif, brun, vert foncé, bleu nuit** |
| `force_lake_range` | 330-356 | Remonte la luminosité à ≥ 0.60, puis rabat vers la teinte claire la plus proche (distance euclidienne) |
| `pastel_floor` | 360-390 | Saturation minimale 0.35, puis plafond de luminosité 0.90 |
| `lake_color` | 396-410 | Point d'entrée : secours si `lum < 0.18` ou `spread < 0.10` |

Les valeurs de seuil (`LAKE_MIN_LUM` 0.60, `LAKE_MIN_SAT` 0.35, `LAKE_MAX_LUM` 0.90) correspondent à des **constantes locales** (`mod/data-updates.lua:293-295`). Elles traduisent des choix de lisibilité et non des paramètres de gameplay.

### 4.5 Lacs : tuiles et neutralisation de l'eau vanilla

Le fonctionnement repose sur trois étapes.

**a. Le fluide et la tuile fantômes** (`mod/data-updates.lua:430-468`)

| Objet | Nom | Ligne |
|-------|-----|-------|
| Fluide fantôme | `randputf-neutre` | 430-442 |
| Tuile fantôme | `randputf-lac-neutre` | 443-466 |

La tuile fantôme consiste en une **copie de `water`** paramétrée avec `autoplace = {probability_expression = "water_base(0, 100)"}`. Le moteur d'altitude la place exactement aux emplacements prévus pour l'eau. Elle s'affiche en blanc, sans shader (`effect = nil`, `map_color` blanc, `tint` forcé).

**b. Neutralisation de l'eau vanilla** (`mod/data-updates.lua:471-493`)

Une `noise-expression` `randputf-no-water = "-999"` est générée. Chaque tuile d'eau de nauvis reçoit ensuite `property_expression_names["tile:<nom>:probability"]` → `randputf-no-water`. Ce traitement couvre l'intégralité des 7 tuiles d'eau (`mod/data-updates.lua:416-422`, avec liste de secours en cas d'absence de `water_tile_type_names`).

**c. Une tuile par fluide de lac** (`mod/data-updates.lua:495-579`)

| Action | Ligne | Détail |
|--------|-------|--------|
| `autoplace-control` | 506-518 | `randputf-lac-ctl-<i>` par lac, catégorie `resource` pour apparaître dans le menu de carte |
| Tuile `randputf-lac-<fluide>` | 519-566 | Clone de `water`, `fluid = <fluide>`, couleurs alignées sur la couleur corrigée |
| `autoplace = {probability_expression = 0}` | 546 | Jamais générée : posée par `surface.set_tiles` au runtime |
| Berges | 579-638 | Les tuiles de lac sont ajoutées aux `transitions[].to_tiles` des 7 tuiles d'eau ; `bordered` est **trié** (ligne 570) pour un data-stage déterministe |
| Inscription mapgen | 640-671 | La tuile fantôme **et** les tuiles-par-fluide sont inscrites dans `autoplace_settings.tile` : sans cela `set_tiles` refuse la tuile |

> Le booleen `has_border` (`mod/data-updates.lua:543`) vaut constamment `true` à cet endroit, car il est assigné la ligne précédente au cours de l'itération. Le traitement du cas « lac sans bordure » (lignes 547-553) s'avère donc **inerte** sans s'exécuter.

### 4.6 Catégories de combustible unifiées

`mod/data-updates.lua:679-695` : **chaque** brûleur vanilla accepte la totalité des `fuel-category`. L'objectif vise à prévenir le don d'un combustible inutilisable dans le kit de départ. Il s'agit d'une mutation globale de `data.raw` affectant également les prototypes issus d'autres mods, ce qui reste assumé et consigné en journal.

### 4.7 Pompe offshore requalifiée

`mod/data-updates.lua:701-711` : la pompe vanilla **ne reçoit aucun** `resource_categories`. Son rôle consiste à pomper directement une **tuile** de lac sans électricité (`energy_source` void). Les patchs fluides demeurent extraits par pumpjack. Seuls le nom et la description font l'objet d'un remplacement.

### 4.8 Fluides génériques

`mod/data-updates.lua:712-870` s'articule autour de trois fonctions d'aide et de deux passes.

| Helper | Ligne | Rôle |
|--------|-------|------|
| `collect_fluid_boxes` | 715-745 | Cherche `fluid_box`, `output_fluid_box`, `fluid_boxes`, `energy_source.fluid_box`, `burner.fuel_fluid_box` — aucune forme codée en dur |
| `parse_energy_kj` | 749-759 | `"0.2kJ"`, `"1MJ"` → kJ ; un nombre est lu comme des **Joules** |
| `compute_temp_power_cap` | 763-796 | Puissance d'un générateur à mode température : `(T_max − T_défaut) × usage × chaleur × effectivité × 60` |

**Passe 1 — retrait des filtres** (`mod/data-updates.lua:791-849`) :

| Action | Ligne | Détail |
|--------|-------|--------|
| Puissance figée | 803-812 | Pour un générateur **sans** `max_power_output`, la capacité est calculée **avant** le retrait du filtre — sinon le prototype devient invalide |
| Filtres retirés | 815-820 | `box.filter = nil` sur toutes les boxes |
| Tooltips | 821-831 | `boiler-any-fluid-description` / `generator-any-fluid-description` si entrée |
| Boilers transformés | 833-840 | `crafting_categories = {"crafting-with-fluid"}` pour héberger une recette fluide→fluide |

**Passe 2 — générateurs en mode combustible** (`mod/data-updates.lua:851-870`) :

| Action | Ligne | Effet |
|--------|-------|-------|
| `burns_fluid = true` | 854-858 | Sur **tous** les générateurs : la puissance vient du `fuel_value` du fluide, plus de la température |
| `fuel_value = "200kJ"` | 860-863 | Sur **tous** les fluides |

> La mutation des `fuel_value` vanilla bloque précisément la validation de l'exporter : une extraction réalisée sur une partie randomisée ressemblerait à du contenu légitime (`exporter/control.lua:760-786`).

### 4.9 Fluides assignés par la seed

`mod/data-updates.lua:872-930`, s'appuie sur `seed.building_fluid_assignments`.

| Action | Ligne | Détail |
|--------|-------|--------|
| Résolution du prototype | 876-890 | Nom exact, puis préfixe `randputf-` ; on garde le candidat qui a des fluid boxes |
| Filtres | 895-905 | `input` sur les boxes d'entrée, `output` sur les sorties |
| Générateurs exclus | 895 | `proto.type ~= "generator"` : un générateur `burns_fluid` reste sans filtre |
| Tooltips | 907-919 | `assigned-fluid-in-description` / `assigned-fluid-in-out-description` |

La seed impose ses choix : ces assignations **remplacent** les configurations définies lors de la passe 1, hors générateurs.

## 5. `mod/data-final-fixes.lua` — neutralisation du vanilla

Ce fichier s'exécute en dernier après l'ensemble des mods.

| Action | Ligne | Détail |
|--------|-------|--------|
| Recettes vanilla désactivées | 25-37 | `enabled = false` **et** `hidden = true`, sauf `rocket-part` (`EXEMPT_RECIPES`, ligne 14-16) |
| Technologies vanilla désactivées | 40-52 | Idem ; `EXEMPT_TECHS` est **vide** (ligne 19) |
| Contrôles d'autoplace masqués | 58-62 | Les contrôles vanilla de catégorie `resource` sont `hidden = true` : le menu de génération de carte ne propose que randputF |
| Ressources vanilla à `size = 0` | 79-83 | Elles **restent listées** (sinon `default_enable_all` les réactiverait) mais ne sont jamais posées |
| Contrôles randputF enregistrés | 86-97 | Par **planète** : `randputf-ctl-<i>` et l'entité associée, `frequency = 1, size = 1` |

Chaque neutralisation utilise `pcall` : un prototype en lecture seule génère un journal d'avertissement sans bloquer le jeu (`mod/data-final-fixes.lua:27`, `42`).

**Invariant d'index.** Les contrôles `randputf-ctl-<i>` suivent une numérotation basée sur le **rang de première apparition** du patch dans `seed.map.patches`. Trois emplacements doivent calculer cet ordre de manière identique :

| Producteur | Ligne |
|------------|-------|
| Création des entités et contrôles | `mod/data-updates.lua:137-144`, `163` |
| Enregistrement par planète | `mod/data-final-fixes.lua:86-97` |
| Noms affichés en jeu | `tool/exporters/mod_seed.py:81-88` (`locale/*/seed.cfg`) |

Le même principe de correspondance s'applique à `randputf-lac-ctl-<i>` : `mod/data-updates.lua:506` et `tool/exporters/mod_seed.py:89-90`.

## 6. `mod/control.lua` — le runtime

### 6.1 Cartographie des événements

| Événement | Ligne | Action |
|-----------|-------|--------|
| `on_configuration_changed` | 719-721 | Neutralise le kit freeplay |
| `on_init` | 723-751 | Storage, freeplay, techs gratuites, premier balayage des crash sites |
| `on_load` | 753-755 | **Vide** — l'API 2.0 interdit toute mutation ; le kit n'est jamais redonné |
| `on_player_created` | 757-773 | Récap chat + kit complet, réarme les deux filets |
| `on_player_respawned` | 775-789 | Kit mince (pistol + 10 munitions) |
| `on_tick` | 791-881 | Filet de kit, normaliseur, purge d'eau, balayage crash |
| `on_surface_created` | 883-888 | Crash sites de la nouvelle surface |
| `on_built_entity`, `on_robot_built_entity`, `on_script_built_entity` | 902-915 | Remplissage forcé du lac sous une `offshore-pump` (filtre `type = offshore-pump`) |
| `on_chunk_generated` | 917-926 | Crash sites, lacs, gisements — dans cet ordre |

Le code n'utilise **pas** `on_player_joined`. Réarmer cet événement viderait l'inventaire d'un joueur rejoignant une partie en cours (`mod/control.lua:789`).

### 6.2 Techs gratuites et activation des recettes

`mod/control.lua:727-743`, s'applique sur `seed.free_researches`. Pour chaque technologie : attribution de `tech.researched = true`, puis **rejouage manuel des effets** `unlock-recipe`. Cette étape pallié l'absence de mise à jour automatique par Factorio lors d'un passage forcé à `researched = true`. C'est le seul endroit où une recette `randputf-*` passe à `enabled = true` en dehors de la progression normale.

### 6.3 Kit de départ

L'attribution emprunte trois chemins exclusifs selon l'événement déclencheur.

| Chemin | Fonction | Ligne | Contenu |
|--------|----------|-------|---------|
| Spawn complet | `apply_spawn_kit` | 409-416 | `clear_spawn_inventory` puis `give_starter_kit` |
| Respawn mince | `apply_respawn_kit` | 457-464 | `clear_spawn_inventory` puis `give_respawn_kit` (pistol + 10 `firearm-magazine`, lignes 421-424) |
| Normaliseur | `normalize_kit` | 336-407 | Ramène chaque item du plan à sa quantité cible |

`clear_spawn_inventory` (`mod/control.lua:191-212`) vide l'inventaire principal, `character_guns` et **`character_ammo`** (emplacement de munitions). `character_ammo_inventory` n'existant pas en 2.0.77, les munitions du pistolet vanilla resteraient sinon verrouillées.

`kit_plan` (`mod/control.lua:287-305`) rassemble `seed.starter_kit` sous la forme `{nom → {count, type}}`, par un calcul unique.

`normalize_kit` opère de façon **chirurgicale** sans jamais appeler `clear()` :

| Étape | Ligne | Action |
|-------|-------|--------|
| 1 | 324-338 | Gun/ammo hors de leur slot cible : comptés puis retirés du principal (`remove` refuse `math.huge`, d'où le comptage) |
| 2 | 339-360 | Excédent dans le slot cible : retiré **depuis la fin** du slot, `clear()` seulement si le stack est entièrement consommé |
| 3 | 361-372 | Déficit : ré-équipé dans le slot cible |
| 4 | 376-382 | Items machine manquants : ré-insertés |

> **Le champ `type` de la seed est ignoré au runtime.** `kit_plan` et `give_starter_kit` consultent `prototypes.item[entry.name]` (`mod/control.lua:293`, `292`) pour déterminer la nature de l'objet. L'outil émettant `type = "item"` par défaut pour chaque entrée (`tool/generator/starter_chain.py:597`, `603`), `starter_kit[].type` désigne en réalité le **slot** (`SLOT_ITEM`). Armes et munitions rejoignent ainsi la branche `player.insert` au lieu des inventaires spécifiques du personnage.

### 6.4 Les deux filets du kit

| Filet | Constantes | Rôle |
|------|-----------|------|
| `SPAWN_SETTLE_TICKS` | 1200 (`mod/control.lua:267`) | Si le personnage apparaît en retard (cutscene du crash), le kit est réessayé chaque tick jusqu'à 1200 |
| `KIT_ENFORCE_TICKS` | `{300, 900, 1800}` (`mod/control.lua:279`) | Normaliseur à trois points de contrôle : le scénario crash-site injecte des items en différé |

L'enchaînement `ARMED` + `KIT_APPLIED` (`mod/control.lua:792-806`) évite toute distribution en double. La réinitialisation `KIT_APPLIED[idx] = nil` survient **exclusivement** dans `on_player_created` (`mod/control.lua:765`), permettant de différencier une apparition initiale d'une réapparition (`mod/control.lua:782-789`).

### 6.5 Loot du crash site

| Élément | Ligne | Détail |
|---------|-------|--------|
| `WRECK_SETTLE_TICKS` | 19 | Fenêtre de balayage = 300 ticks |
| `WRECK_SWEEP_INTERVAL` | 20 | Balayage tous les 10 ticks pendant la fenêtre |
| `init_wreck` | 25-33 | `game` est **nil** pendant `on_load` : le stop est calculé au runtime, jamais en `on_load` |
| `draw_slot_count` | 35-51 | Tirage pondéré 0..3 depuis `seed.wreck.counts` (somme = 78 : `{24, 23, 16, 15}`) |
| `process_crash_container` | 56-101 | Vide l'inventaire, remplit slot par slot |
| Force-fill | 86-90 | Un conteneur n'est **jamais** vide : 1 matériau forcé au slot 1 si tous les tirages sont nuls |
| Idempotence | 91-93 | Marque `unit_number` dans `storage.randputf.wreck_processed` |

Le conteneur utilise un générateur RNG local : `game.create_random_generator(base * 1000003 + unit_number)` (`mod/control.lua:73`). Le contenu reste **stable par conteneur**, peu importe l'ordre de découverte.

### 6.6 Purge de l'eau vanilla

| Élément | Ligne | Détail |
|---------|-------|--------|
| `WATER_PURGE_CHUNKS_PER_TICK` | 223 | 32 chunks par tick |
| `WATER_TILES` | 226-230 | Les 7 tuiles d'eau ; les tuiles `randputf-lac-*` sont **excluses** |
| `purge_chunk_water` | 235-260 | Remplace chaque tuile d'eau par la **terre dominante du chunk** |
| Balayage en anneau | 827-862 | Curseur `(ring, x, y)` persisté, spirale jusqu'à `|R| > 256` |
| Amorce | 864-866 | `water_purge_done` empêche de rescanner une carte neuve |

L'appel `surface.set_tiles(tiles, false)` (`mod/control.lua:262`) transmet `false` en second paramètre pour couper `correct_tiles` : l'action vise à **altérer** le terrain sans effectuer de correction de bordure.

### 6.7 Lacs : flood-fill au runtime

| Fonction | Ligne | Rôle |
|----------|-------|------|
| `init_lake_fluids` | 478-487 | Construit `LAKE_FLUID_TILES` (ordre de la seed) et `LAKE_FLUID_LOOKUP` |
| `next_lake_fluid_tile` | 490-498 | Tourniquet **persisté** dans `storage.randputf.lake_index` |
| `flood_fill_phantom` | 501-532 | BFS sur la tuile fantôme, borné à l'`area` du chunk |
| `neighbor_lake_fluid` | 534-549 | Cherche un voisin déjà coloré → **propagation inter-chunks** |
| `fill_lake` | 551-566 | `voisin coloré` sinon `tourniquet`, puis `set_tiles` avec `correct_tiles` (**activé**) |
| `fill_lakes_in_area` | 569-581 | Parcourt le chunk, un fill par tuile fantôme trouvée |

Le traitement favorise la **continuité spatiale** par rapport à la séquence de la seed. Deux lacs adjacents adoptent le même fluide, tandis qu'un plan d'eau isolé prend le fluide suivant du tourniquet.

`init_lake_fluids()` s'exécute lors du **chargement du module** (`mod/control.lua:716`). Sans dépendance envers `game`, son exécution est garantie pendant `on_load`.

Poser une `offshore-pump` sur une tuile fantôme déclenche un remplissage local dans un rayon de 128 (`mod/control.lua:891-900`), permettant d'anticiper la génération automatique du chunk.

### 6.8 Gisements au runtime

| Élément | Ligne | Détail |
|---------|-------|--------|
| `WELL_MIX` | 585 | 2654435761 (Knuth), masqué sous 2^31 |
| `place_resource_block` | 590-608 | `can_place_entity` puis `create_entity` ; `e.amount = richesse`, `initial_amount` sous `pcall` |
| `tile_hash` | 622-627 | Hash entier pur, **miroir exact** de `tool/generator/map_patches.py:179` |
| `block_positions_in_area` | 632-689 | Deux algorithmes distincts |

**Fluides** (`mod/control.lua:644-655`) : puits dispersés. Pour chaque puits, un tirage RNG local `(well_seed + idx * WELL_MIX) % 2^31` définit un angle et un rayon dans l'intervalle `0.25..1 × radius`. L'emplacement calculé reste **indépendant de l'ordre de génération des chunks**.

**Items** (`mod/control.lua:656-689`) : champ organique sous forme de disque bruité.

| Constante | Valeur | Rôle |
|-----------|--------|------|
| `NOISE_WOBBLE` | 0.20 | Amplitude du bruit sur le bord |
| `NOISE_CORE` | 0.72 | Fraction du rayon traitée comme cœur |
| `NOISE_CORE_KEEP` | 0.99 | Probabilité de poser une tuile au cœur |
| `NOISE_DILUTE` | 0.85 | Densité maximale de l'anneau externe |

Deux variables de hash décorrélées interviennent : `seed_a = well_seed` pour le wobble et `seed_b = well_seed + 1618033989` pour la densité.

> **Exactitude du champ `count`.** L'outil évalue `count` en répliquant la logique de `item_field_tiles` côté Python (`tool/generator/map_patches.py:190`), reproduite à l'identique dans le mod via `tile_hash` et ses seuils. Cette correspondance stricte garantit qu'aucune dérive n'affecte `count` ni la richesse distribuée par tuile (`mod/control.lua:703-708`).

`per_tile` (`mod/control.lua:705-708`) : pour un fluide, la richesse s'applique **par puits**. Pour un item, la valeur s'entend **par tuile**, soit `max(1, floor(richness / count))`. Cette distinction explique la séparation en deux branches au niveau de `apply_craft_quantity`.

## 7. `exporter/control.lua` — le dump vanilla

Mod autonome de collecte, hors chaîne de génération randputF. Son exécution produit `data/vanilla_dump.json`, utilisé comme base par l'outil Python.

| Action | Ligne | Détail |
|--------|-------|--------|
| `dump_all_items` | 125-226 | `fuel_value`, `stack_size`, `subgroup`, `place_result`, `burnt_result`, `ammo_category` |
| `dump_fluids` | 228-239 | `default_temperature` en plus |
| `dump_entities` | 399-622 | Classement par **capacité** : craft (`crafting_categories`), extraction (`resource_categories`), pompage (`pumping_speed`), fluides, énergie, production |
| `dump_recipes` | 624-658 | Ingrédients, produits, catégorie, énergie, `enabled`, `hidden` |
| `dump_technologies` | 661-761 | Prérequis, unité de recherche, effets, `enabled`, `hidden` |
| Écriture | 780-787 | `helpers.write_file("randputF/vanilla_dump.json")` sous `pcall` |

Trois spécificités liées à la version 2.0 font l'objet de commentaires dans le code :

| Point d'attention | Ligne | Traitement |
|-------|-------|-----------|
| Absence de `energy_source` générique | 299-346 | Teste les champs un par un (`burner_prototype`, `electric_energy_source_prototype`…) et déduit la catégorie selon la clé identifiée |
| `production_type` (2.0) vs `flow_direction` (1.x) | 254-272 | Prise en charge des deux clés |
| `get_supply_area_distance()` (méthode 2.0) | 550-556 | Appel sécurisé sous pcall, champ ignoré en cas d'échec |

### 7.1 Export avec ou sans randputF

`exporter/control.lua` n'a plus de garde-fou : l'export s'écrit même si `randputF` est actif. Le dump contient alors du contenu vanilla, des recettes `randputf-*` et des altérations de prototypes : modification de `fuel_value` des fluides fixée à 200 kJ (`mod/data-updates.lua:861`), suppression de filtres (`mod/data-updates.lua:818`), ou encore élargissement de `fuel_categories` (`mod/data-updates.lua:687`).

Ce dump moddé est une photographie complète : les recettes et technologies vanilla neutralisées restent présentes avec leurs liens, mais portent `enabled = false` et `hidden = true`. Le tool ne filtre plus les clés `randputf-*` et n'essaie plus de rejeter les mutations : il canonise à la lecture. Pour un produit `X`, une recette `randputf-X` active devient la recette canonique ; la recette vanilla `X` est ignorée pour la génération. La clé logique est normalisée (`X`), tandis que `VanillaDB.recipes` conserve le nom réel `randputf-X` pour ne pas casser les effets de technologies. Les recettes `randputf-ease-*`, `randputf-relay-*` et les recettes de fluides restent des alternatives. Les items, fluides et entités déjà préfixés sont conservés dans des buckets `modded_*` hors des pools de génération, et les artefacts `randputf-randputf-…` sont ignorés. Un dump moddé peut donc produire une seed différente du dump vanilla historique, ce qui est attendu.

## 8. Clés de seed consommées, par fichier

| Clé | `data.lua` | `data-updates.lua` | `data-final-fixes.lua` | `control.lua` |
|-----|---|---|---|---|
| `meta.seed` | — | 150 | — | 72, 131 |
| `meta.factorio_version` | — | — | — | — |
| `meta.generator_version` | — | — | — | — |
| `pools.vehicle_range_scaling` | — | 18 | — | — |
| `map.patches` | — | 97 | 70 | 144, 696 |
| `map.lakes` | — | 278 | — | 137, 481 |
| `recipes` | 53 | — | — | — |
| `technologies` | 188 | — | — | — |
| `free_researches` | — | — | — | 728 |
| `vehicle_armament` | — | 58 | — | — |
| `building_fluid_assignments` | — | 871 | — | — |
| `starter_kit` | — | — | — | 292, 314 |
| `wreck` | — | — | — | 64 |
| `difficulty` | — | — | — | 133 |
| `meta.disable_vanilla_techs` | 235 **dormant** | — | — | — |

Points particuliers :

- `meta.factorio_version` et `meta.generator_version` sont **générés sans jamais être lus** par le mod (aucune occurrence dans `mod/*.lua` ni `exporter/*.lua`). Ces clés servent d'informations de suivi pour l'outil et l'audit.
- `pools.vehicle_weapons` apparaît dans les données générées (`tool/generator/pipeline.py:444`) sans lecture côté Lua, qui exploite uniquement `vehicle_armament` (`mod/data-updates.lua:58`).
- `difficulty` est ajoutée **pendant l'export** (`tool/exporters/mod_seed.py:53-58`) et n'apparaît pas dans l'objet `seed` d'origine du pipeline.

## 9. Ce qui est câblé mais inactif

| Cas | Emplacement | État |
|-----|-------------|-------|
| `meta.disable_vanilla_techs` | `mod/data.lua:235-241` | **Inerte** : clé jamais émise. La désactivation réelle est en data-final-fixes |
| `has_border` / lac sans bordure | `mod/data-updates.lua:543`, `547-553` | **Inerte** : la variable est toujours `true` |
| `respawn_items` freeplay | `mod/control.lua:174` | Actif si le mod freeplay est installé |
| `pools.vehicle_weapons` | `tool/generator/pipeline.py:444` | Exporté et documenté, mais **non consommé** en Lua : le mod n'utilise que `vehicle_armament` |
| `extractor_timing` | `tool/generator/pipeline.py:465` | Idem : conservé pour l'audit et les tests, explicitement ignoré par le mod (commentaire ligne 458-461) |

## 10. Lectures associées

- [`pipeline.md`](pipeline.md) — origine et génération de chaque clé.
- [`seed.md`](seed.md) — structure détaillée de `seed.json`.
- [`ressources.md`](ressources.md) — mécanismes de placement des gisements et des lacs (§6).
- [`starter.md`](starter.md) — fonctionnement du kit de départ (§7/§8).
- [`nondeterminism.md`](nondeterminism.md) — flux RNG déterminant la génération des cartes.
- [`witness.md`](witness.md) — empreinte md5 du mod généré.
