# Tags de bâtiment (BuildingDef) et d'item (ItemDef)

La base normalisée classe chaque entité du dump avec des **tags orthogonaux
cumulables** (`is_*`), remplaçant l'ancien `functional_type` exclusif
(research/transformer/generator/distribution/extractor/other). Un bâtiment peut
porter plusieurs rôles à la fois : `heat-exchanger` est ainsi `is_crafter` +
`is_generator`, `character` est `is_crafter` + `is_extractor`. La logique du
générateur ne repose QUE sur les tags ; `equivalent_functional_type`
(`tool/parsers/vanilla.py`) peut reconstruire l'ancienne classification
exclusive pour vérification.

Ce document est la **référence unique** des tags (l'ancienne roadmap
`docs/tag_idee.md` a été fusionnée ici et supprimée). Les tags se lisent dans
`tool/common/db.py` (déclaration) et se calculent par **capacités intrinsèques**
dans `tool/parsers/vanilla.py` (`tag_parse_entity` — aucune liste de noms).

**Vérification** : `tool/audit/tags.py` (CLI `randputf audit`) contrôle les
invariants d'orthogonalité/cohérence sur l'ensemble du dump et la démo ; la
consommation DE chaque tag est listée colonne « Consommé par ».

## 1. Tags de rôle fonctionnel (cumulables)

Tous déterminés **par capacités intrinsèques** dans `tag_parse_entity`.

| Tag | Signification | Déterminé par | Consommé par |
|-----|---------------|---------------|--------------|
| `is_research` | Consomme des science packs → produit de la **recherche** (lab) | `lab_inputs` non vide | `starter_chain`, `map_patches`, `recipes` |
| `is_crafter` | **Atelier** : sortie item/fluide, transforme des entrées en produit de craft (fours, assembling-machines, usine chimique, le personnage…) | catégories de craft, `rocket_parts_required`, `target_temperature` | `recursive_phase` (catégorie `transformer`), `starter_chain`, `recipes`, `building_fluids` |
| `is_generator` | Producteur d'**énergie** (électricité OU chaleur : turbine, steam-engine, solar-panel, réacteur, heat-exchanger) | `max_power_output` > 0, `production` > 0, sortie chaleur ; jamais un `accumulator` | `recursive_phase` (catégorie `generator`), `building_fluids` |
| `is_distribution` | Infrastructure de **distribution** (`supply_area_distance` : pylônes, beacon) | `supply_area_distance` non nul | `recursive_phase`, `electricity` (pylônes via `is_power_pole`) |
| `is_extractor` | **Extrait** une ressource de l'environnement → item/fluide (minerais, offshore-pump, pumpjack) | `resource_categories`, `pumped_fluid`, pompage sans entrée | `recipes` (`_is_extractor_item`), `starter_chain` (`_extractors_for_resource`), `extractors_for_medium` |
| `is_other` | Aucune capacité reconnue (backup, jamais perdu) | = !(tous les rôles ci-dessus) | `summarize_db` uniquement (non consommé par le générateur) |

`PRODUCING_TAGS = ("is_research", "is_crafter", "is_generator", "is_extractor")`
(liste partagée dans `db.py`) regroupe les rôles ayant une production propre.
Les « distribution » et « other » ne produisent rien.

Exemples de comptage sur `data/vanilla_dump.json` : `is_research` 1,
`is_crafter` 13, `is_generator` 6 (5 anciens + heat-exchanger), `is_distribution`
5, `is_extractor` 5 (4 anciens + character), `is_other` 509 (total 537 bâtiments,
somme 539 = 537 + 2 double-tags).

### 1.1. Raffinements de rôle (électricité, extraction, distribution)

| Tag | Signification | Déterminé par | Consommé par |
|-----|---------------|---------------|--------------|
| `is_power_pole` | poteau électrique | `type == 'electric-pole'` | `electricity`, `tech_tree` (jalons réseau), `recursive_phase` |
| `is_beacon` | module de transmission d'effet | `type == 'beacon'` | raffinage **usage en vue** (affine `is_distribution`) |
| `is_accumulator` | stockeur d'énergie | `type == 'accumulator'` | audit (distingué du producteur) |
| `is_energy_storage` | stockage d'énergie (pas de production) | `buffer_capacity` ; repli = `is_accumulator` (le dump n'exporte pas `buffer_capacity`) | raffinage (alias de l'accumulateur), audit |
| `is_offgrid` | producteur hors réseau (solaire, burner-generator) | `produces_electricity` + énergie non `electric` OU `type == 'solar-panel'` | audit |
| `consumes_electricity` | consomme du courant | `energy_type == 'electric'` sans production ni stockage | audit, tier tardif du balayage (via `_is_network_dependent_item`) |
| `is_water_extractor` / `is_fluid_extractor` / `is_ground_extractor` | extracteur par MEDIUM | `is_extractor` + `medium` (water/fluid/ground) | `extractors_for_medium`, `starter_chain` |

## 2. Logistique & transport (raffinement des `is_other`)

Bâtiments `is_other` raffinés **par type de prototype** (aucune liste de noms).

Les transports du kit de départ sont sélectionnés **par tag** :
`starter_chain._ensure_transport_item` résout chaque rôle (belt, splitter,
underground, pipe, pipe_to_ground, inserter) vers le tag du bâtiment POSÉ par
l'item (`place_result`). Les motifs de noms en dur
(`StarterConfig.transport_patterns`) ont été **supprimés**.

| Tag | Déterminé par | Consommé par |
|-----|---------------|--------------|
| `is_belt` | `type == 'transport-belt'` | `starter_chain` (rôle `belt`) |
| `is_splitter` | `type == 'splitter'` | `starter_chain` (rôle `splitter`) |
| `is_underground_belt` | `type == 'underground-belt'` | `starter_chain` (rôle `underground`) |
| `is_inserter` | `type == 'inserter'` | `starter_chain` (rôle `inserter`, proba `inserter_chance`) |
| `is_pipe` | `type == 'pipe'` | `starter_chain` (rôle `pipe`) |
| `is_pipe_to_ground` | `type == 'pipe-to-ground'` | `starter_chain` (rôle `pipe_to_ground`) |
| `is_fluid_transport` | `is_pipe` ou `is_pipe_to_ground` | dérivé (via les deux ci-dessus) |
| `is_chest` | `type == 'container'` | raffinage **usage en vue** (relais, kit, spawn) |
| `is_logistics_chest` | `type == 'logistic-container'` | raffinage **usage en vue** (balayage, réseau robot) |
| `is_storage` | `is_chest` ou `is_logistics_chest` | raffinage **usage en vue** |
| `is_roboport` | `type == 'roboport'` | raffinage **usage en vue** (C3 robot↔roboport) |
| `is_robot` | robots **logistiques/construction** (le robot de combat est `is_combat_robot`, §7 — jamais confondu) | raffinage **usage en vue** (C3, §12) |

## 3. Train & véhicules (raffinement des `is_other`)

Tags **usage en vue** : le pool d'armement des véhicules (§12.1) et la
constante de test `ARMED_VEHICLES` restent pilotés par config tant que
`is_mounted_gun` n'est pas exportable (le dump ne distingue pas une arme montée
d'une arme de poing). Ces tags alimenteront ce pool dès que l'exporter
exposera « can be used by hand » (gap IDEES).

| Tag | Déterminé par |
|-----|---------------|
| `is_rail` | `type` ∈ `RAIL_TYPES` (droits/courbes/half-diagonal/legacy/surélevés) |
| `is_rail_support` | `type == 'rail-support'` |
| `is_rail_signal` | `type` ∈ {`rail-signal`, `rail-chain-signal`} |
| `is_train_stop` | `type == 'train-stop'` |
| `is_locomotive` | `type == 'locomotive'` |
| `is_wagon` | `type` ∈ {`cargo-wagon`, `fluid-wagon`, `artillery-wagon`} |
| `is_spider_vehicle` | `type == 'spider-vehicle'` |
| `is_vehicle` | `is_locomotive` ou `is_wagon` ou `is_spider_vehicle` ou `type == 'car'` |

## 4. Production spécialisée (raffinement d'`is_crafter`)

| Tag | Déterminé par | Consommé par |
|-----|---------------|--------------|
| `is_furnace` | catégorie `smelting` | audit, `recursive_phase` (premier atelier handcraftable) |
| `is_assembler` | catégorie `crafting` / `advanced-crafting` / `crafting-with-fluid` | audit, `recursive_phase` |
| `is_chemical_plant` | catégorie `chemistry` | audit |
| `is_refinery` | catégorie `oil-processing` | audit |
| `is_centrifuge` | catégorie `centrifuging` | audit |
| `is_rocket_parts_crafter` | catégorie `rocket-building` OU pièces de fusée | `endgame_phase`, audit |

NB : `character` (crafting à la main) est lui aussi `is_assembler` — la
catégorie `crafting` le qualifie, conformément au signal.

## 5. Énergie & chaleur (raffinement d'`is_generator`)

boiler ET heat-exchanger partagent le type `'boiler'` dans le dump : on les
distingue par l'énergie de la source (`burner` vs `heat`). `is_steam_engine` /
`is_steam_turbine` ne sont PAS des tags (distinction PAR PUISSANCE via
`produces_electricity`, pas de nom).

| Tag | Déterminé par | Consommé par |
|-----|---------------|--------------|
| `is_boiler` | `type == 'boiler'` + `energy_type == 'burner'` | `is_fixed_fluid_crafter` (C7), `building_fluids` |
| `is_heat_exchanger` | `type == 'boiler'` + `energy_type == 'heat'` | `is_fixed_fluid_crafter` (C7), `building_fluids` |
| `is_solar` | `type == 'solar-panel'` | audit, tests |
| `is_reactor` | `type == 'reactor'` | audit (voir §6 `fuel_residues`) |
| `is_heat_transport` | `type == 'heat-pipe'` | `recursive_phase` (envoyé par `_ensure_heat_prereq`) |
| `is_burner_generator` | `type == 'burner-generator'` | raffinage **usage en vue** |

## 6. Extraction (raffinement d'`is_extractor`)

`pumpjack` a `type == 'mining-drill'` dans le dump : détection par
`resource_categories ⊇ basic-fluid`. `is_offshore_pump` = médium eau (le dump
n'expose pas `pumped_fluid`).

| Tag | Déterminé par | Consommé par |
|-----|---------------|--------------|
| `is_mining_drill` | `type == 'mining-drill'` (minerai solide via médium ground) | `starter_chain`, `map_patches` |
| `is_pumpjack` | `type == 'mining-drill'` + `resource_categories ⊇ basic-fluid` | `starter_chain` (fluides profonds) |
| `is_offshore_pump` | `is_water_extractor` (médium eau) | `starter_chain` (patch water), `map_patches` |
| `is_well_pump` | `type == 'pump'` | raffinage **usage en vue** |

## 7. Sortie spéciale (orthogonale aux rôles)

Sorties **non recettables** (jamais des produits de recette de craft) — elles se
cumulent entre elles et avec les rôles.

| Tag | Signification | Exemples | Consommé par |
|-----|---------------|----------|--------------|
| `produces_electricity` | VRAI producteur de **courant** | steam-engine, turbine, burner-generator, solar-panel | `electricity`, `building_fluids` (`_is_steam_generator`), `recursive_phase` (premier générateur craftable à la main) |
| `produces_heat` | Producteur de **chaleur** (pas de courant) — restreint à la SOURCE | nuclear-reactor | `electricity` (exclut le réacteur du réseau), `recursive_phase` (`_ensure_heat_prereq`), tests |

Le réacteur est `is_generator` + `produces_heat`, jamais `produces_electricity` :
il est écarté de l'électricité PAR CAPACITÉS, sans liste de noms. L'accumulateur
affiche une puissance de décharge mais n'est ni `produces_electricity` ni
`is_generator`.

### 5bis. Modèle « chaleur » (producteur / transport / consommateur)

La chaleur est un milieu transportable à la manière d'un fluide, mais qui ne
circule qu'entre les bâtiments capables de l'échanger. Trois tags ORTHOGONAUX
par capacités (docs/energie.md §10bis) ; `produces_heat` est restreint à la SOURCE (il
corrige l'ancien `has_heat_output` qui taguait aussi la heat-pipe et
l'échangeur).

| Tag | Déterminé par | Exemples (vanilla) | Consommé par |
|-----|---------------|--------------------|--------------|
| `is_heat_source` | `type == 'reactor'` **ou** (`has_heat_output` ET `energy_type == 'burner'`) | nuclear-reactor | `recursive_phase._ensure_heat_prereq` |
| `is_heat_transport` | `type == 'heat-pipe'` | heat-pipe | `recursive_phase._ensure_heat_prereq` |
| `is_heat_sink` | `energy_type == 'heat'` | heat-exchanger | `recursive_phase._ensure_heat_prereq` |

La triade est garantie « à la volée » : au premier sink qui reçoit sa recette
fluide→fluide, la SOURCE et le TRANSPORT manquants sont débloqués dans des
techs **isolées strictement antérieures** (jamais fusionnées avec la tech du
consommateur). Aucun sink dans le pool → modèle parfaitement inerte.

## 8. « Recette cachée » et fabricateurs à recette fixe

Détection **par capacités** (aucune liste de noms), voir `tool/common/db.py`.

| Tag / Prédicat | Signification | Réglé par | Consommé par |
|----------------|---------------|-----------|--------------|
| `has_hidden_recipe` (champ) | Production codée en dur = une VRAIE recette non accessible avant la transformation du mod | estampillé post-parse dans `load_db_from_dump` (dépend des résidus de combustible) | `recipes` (`_is_atelier`), `recursive_phase` |
| `has_hidden_recipe(b)` (fonction) | Prédicat : tag producteur (`PRODUCING_TAGS`) + entrée (item/fluide/combustible) + sortie item/fluide/residu + **aucune** catégorie de craft valide | — | calcule le champ |
| `is_fixed_crafter(b)` | Sous-ensemble `has_hidden_recipe` + `is_crafter` + sortie fluide OU item **ou** `fuel_residues` non vide (combusteur à résidu) : reçoit réellement une recette randomisée ; en vanilla boiler/heat-exchanger (item→item → fluide→fluide item) ET **nuclear-reactor** (item→item via `fuel_residues` = depleted-uranium-fuel-cell) | — | `recursive_phase` (`_make_fixed_recipe_for_crafter` / `_make_fixed_residue_recipe`), `recipes`, `mod/data.lua` (catégorie de craft accordée au bâtiment `crafted_in`) |
| `is_fixed_fluid_crafter(b)` | `is_fixed_crafter` restreint au « fluide → fluide » (boiler, heat-exchanger) | — | `recursive_phase` (pairing IDEES C7), `building_fluids`, `recipes` |
| `fuel_residues` (champ) | Sorties item issues de la combustion (`burnt_result` des combustibles du bâtiment) | estampillé post-parse | alimente `has_hidden_recipe` et `fuel_item_flow` |

Les générateurs/extracteurs/lab restants (champ → ressource, combustible →
électricité, packs → recherche) ont une sortie non recettable : jamais marqués
`has_hidden_recipe`, leur comportement reste figé.

Le cas **réacteur** (item quelconque → depleted-uranium-fuel-cell en résidu)
est une recette cachée item→item : `is_fixed_crafter` le route vers SA recette
`randputf-nuclear-reactor-depleted-uranium-fuel-cell` (crafted_in =
nuclear-reactor). Au chargement, `mod/data.lua` accorde au bâtiment la
crafting_category de la recette si elle lui manque (un réacteur vanilla ne
craft rien par lui-même) — sans liste de noms, via `crafted_in` + recherche de
prototype d'entité.

## 9. Capables brut (`has_*`) — métadonnée informative

Déterminées par `tag_parse_entity`, **non consommées** par le générateur
(documentation/requalification) :

| Tag | Signification |
|-----|---------------|
| `has_crafting` | Possède au moins une catégorie de craft |
| `has_mining` | Possède des catégories de ressources minables |
| `has_pumping` | Pompage (fluide pompé ou vitesse de pompage sans entrée) |
| `has_fluid_input` | Au moins un fluid box d'entrée |
| `has_fluid_output` | Au moins un fluid box de sortie |
| `has_fuel` | Source d'énergie `burner` |
| `has_target_temperature` | Température cible définie |
| `has_rocket_parts` | Requiert des pièces de fusée (silo) |

## 10. Combat & défense (§7)

Bâtiments `is_other` (aucune production) raffinés par TYPE de prototype :
tourelles (4 familles + union `is_turret`), muraille/porte, mine, robot de
combat. **Consommés par** `recursive_phase._is_network_dependent_item` :
la tourelle LASER (seul usage à réseau du §7) est différée dans un tier tardif
du balayage §9.6 — une balistique bootstrap peut arriver tôt. Les autres tags
§7 sont des **raffinages vérifiés** (classification + audit) : la tourelle
balistique/flamme/artillerie n'a aucun usage réseau et suit le balayage normal.
`is_combat_robot` est strictement disjoint de `is_robot` (logistique).

| Tag | Déterminé par | Consommé par |
|-----|---------------|--------------|
| `is_turret` | union : `ammo-turret` / `electric-turret` / `fluid-turret` / `artillery-turret` | audit |
| `is_gun_turret` | `type == 'ammo-turret'` | raffinage, audit |
| `is_laser_turret` | `type == 'electric-turret'` | tier tardif (différé) |
| `is_flame_turret` | `type == 'fluid-turret'` | raffinage, audit |
| `is_artillery` | `type == 'artillery-turret'` | raffinage, audit |
| `is_defensive_wall` | `type` ∈ {`wall`, `gate`} | raffinage, audit |
| `is_landmine` | `type == 'land-mine'` | raffinage, audit |
| `is_combat_robot` | `type == 'combat-robot'` | raffinage, audit (disjoint `is_robot`) |

## 11. Signal-réseau & électronique (§8)

Bâtiments `is_other` dépendant du RÉSEAU (courant + circuits) :
combinators, lampe, radar. **Consommés par** `recursive_phase._is_network_dependent_item`
via l'union `is_circuit_io` + `is_rgb_lamp` + `is_radar` → tier tardif du
balayage, jamais posés avant le réseau. `is_circuit_combinator` et
`is_constant_combinator` (membres de l'union, signalés indirectement par elle)
sont des raffinages vérifiés. ⚠️ Le dump n'exporte PAS `energy_source` pour
constant-combinator / power-switch / display-panel : `consumes_electricity` n'y
est pas vérifiable (pour l'instant l'invariant d'audit porte sur le typage
seul).

| Tag | Déterminé par | Consommé par |
|-----|---------------|--------------|
| `is_circuit_combinator` | `type` ∈ {arithmetic, decider, selector-combinator} | raffinage (membre de `is_circuit_io`), audit |
| `is_constant_combinator` | `type == 'constant-combinator'` | raffinage (membre de `is_circuit_io`), audit |
| `is_circuit_io` | union combinators + {programmable-speaker, display-panel, power-switch} | tier tardif |
| `is_rgb_lamp` | `type == 'lamp'` (électrique) | tier tardif |
| `is_radar` | `type == 'radar'` | tier tardif |

## 12. Tags items (§9)

Tags sur `ItemDef`, décidés par type brut du dump (`item_type`), sous-groupe et
ensembles — plus les propriétés dérivées :

| Tag / Prédicat | Déterminé par | Consommé par |
|-----|---------------|--------------|
| `is_environmental` | `ENVIRONMENTAL_ITEMS` (source de vérité via `_is_environmental_item`) | poids environnementaux (`recipes._environmental_weight`), anti-cycle, pools, `_excludable_items` (map_patches), tests |
| `is_virtual_item` | `item_type` ∈ types contrôle ET `place_result` absent (le rail, type `rail-planner` mais posable, n'est PAS virtuel) | exclusion des pools craftables / patchs (`_coverage_items`, map_patches) |
| `is_module` | `item_type == 'module'` | pools de craft |
| `is_capsule_throwable` | `item_type == 'capsule'` | pools de craft |
| `is_ammo` | `item_type == 'ammo'` | `_dispatch_vehicle_ammo` (§12.1), `starter_chain` (kit) |
| `is_gun` | `item_type == 'gun'` | `map_patches` (exclusion), `_dispatch_vehicle_ammo`, audit |
| `is_armor` | `item_type == 'armor'` | raffinage **usage en vue** (audit) |
| `is_tool` | `item_type == 'tool'` | `starter_chain`, pools (mais jamais crafté) |
| `is_science_pack` | `subgroup == 'science-pack'` — RAFFINAGE d'`is_tool` (les packs SONT de type tool) | `starter_chain`, `map_patches`, `recursive_phase`, audit |
| `is_handheld_gun` (propriété) | `is_gun` ET hors `VEHICLE_GUNS` (armes montées) | `VEHICLE_GUNS` (soft list, gap `is_mounted_gun`) |
| `is_stackable` (propriété) | `stack_size > 1` du dump ; sinon déduit du type (`NON_STACKABLE_ITEM_TYPES`) | clamp des produits/ingrédients (§9.6) |

Invariant vérifié par l'audit (`tool/audit/tags.py`) : un item environnemental
ou virtuel n'est produit par AUCUNE recette (cycle/erreur Factorio).

## 13. Helpers / API

- `VanillaDB.buildings_with_tag(tag)` — tous les bâtiments portant un tag donné
  (un multi-tags apparaît dans chaque catégorie qu'il porte).
- `VanillaDB.extractors_for_medium(medium)` — les `is_extractor` filtrés par
  `medium` (« water », « fluid », « ground », ou tout).
- `VanillaDB.fuel_item_flow(b)` / `has_fuel_item_flow(b)` / `fuel_residues(b)` —
  vue normalisée d'une machine à combustible (item → item résidu).
- `equivalent_functional_type(b)` — reconstruit l'ancien rôle exclusif
  (research → transformer → generator → distribution → extractor → other) :
  outil de vérification + décisions d'héritage du dump (medium, directives).
- `medium` (champ associé aux extracteurs) : `water` (offshore-pump),
  `fluid` (`resource_categories` contenant `basic-fluid`, ex. pumpjack),
  `ground` (minerais), `""` (character).
- `BuildingDef.directives` — héritages bruts du dump (`fluid_inputs`,
  `rocket_parts_required`, `lab_inputs`).

## 14. Ensembles dérivés en dur (résiduels)

Certaines listes figées dans `tool/common/db.py` restent nécessaires en
attendant des tags plus fins / un signal exporté :

- `ENVIRONMENTAL_ITEMS` — items récoltés à la main ; **source de vérité** du
  tag `is_environmental` (`_is_environmental_item`) et consommée en plus par
  validator/solver/starters. Le tag est consommé par les générateurs ; la
  constante reste pour lecture directe.
- `NON_STACKABLE_ITEM_TYPES` — types d'items non-empilables (fallback quand le
  dump n'emporte pas `stack_size`) : conservateur, fondé sur des TYPES.
- `VEHICLE_GUNS` — armes MONTÉES uniquement ; `ItemDef.is_handheld_gun` en
  dépend. ⚠️ Aucune détection par capacités possible (`tank-machine-gun` et
  `pistol` sont indistinguables dans le dump) : cette soft list restera tant
  que l'exporter n'expose pas « can be used by hand » (`is_mounted_gun` ⏳).
- `ROCKET_CHAIN` — chaîne fusée (choix de conception, pas une donnée moteur).
- `ARMED_VEHICLES` (tests) — constante de TEST nominale (tank/spidertron/
  artillery-wagon) : subsiste comme assertion, remplacée par `is_vehicle` dès
  `is_mounted_gun`.

Migrés / supprimés : `POWER_POLES` (→ `is_power_pole`), `TOOL_LIKE_ITEMS`
(→ `is_virtual_item`, constante supprimée), `transport_patterns` du kit de
départ (→ §2, champ `StarterConfig` supprimé).